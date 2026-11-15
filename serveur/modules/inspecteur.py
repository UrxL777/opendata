import re
import warnings
import pandas as pd
import chardet
import os

# Une colonne de texte est considérée comme une colonne de dates si au moins 80 % de ses
# valeurs sont des dates lisibles. Seuil prudent : convertir une colonne à tort rendrait vides
# toutes les valeurs qui ne sont pas des dates.
SEUIL_DATES = 0.8

# Une valeur « ressemble » à une date si elle contient des chiffres séparés par - / . ou :
# (ex. 2025-01-15, 15/02/2025, 14:30) ou un nom de mois en anglais.
FORME_DATE = re.compile(
    r"\d{1,4}\s*[-/.:]\s*\d{1,2}"
    r"|\b(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\b",
    re.IGNORECASE,
)


def convertir_en_dates(serie: pd.Series) -> pd.Series:
    """
    Convertit une colonne de texte en dates. Accepte plusieurs formats dans la même colonne
    et lit le jour avant le mois (02/03/2025 = 2 mars). Une valeur illisible devient vide,
    elle n'est jamais inventée.
    """
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        return pd.to_datetime(serie, errors="coerce", format="mixed", dayfirst=True)


def proportion_de_dates(serie: pd.Series) -> float:
    """Part des valeurs (non vides) qui sont des dates lisibles, entre 0 et 1."""
    valeurs = serie.dropna().astype(str).str.strip()
    valeurs = valeurs[valeurs != ""].head(500)
    if valeurs.empty:
        return 0.0
    ressemble = valeurs.str.contains(FORME_DATE)
    lisible = convertir_en_dates(valeurs).notna()
    return float((ressemble & lisible).mean())

# ─── Lecture du fichier selon son format ───────────────────────────────────────

def detecter_encodage(chemin: str) -> str:
    """Détecte l'encodage d'un fichier texte (utile pour les CSV)."""
    with open(chemin, "rb") as f:
        resultat = chardet.detect(f.read(50000))
    return resultat.get("encoding") or "utf-8"


def lire_fichier(chemin: str, nom_fichier: str) -> pd.DataFrame:
    """Lit un fichier CSV, Excel ou JSON et retourne un DataFrame."""
    ext = os.path.splitext(nom_fichier)[1].lower()

    if ext == ".csv":
        encodage = detecter_encodage(chemin)
        # Essayer plusieurs séparateurs et encodages en cascade
        for sep in [",", ";"]:
            for enc in [encodage, "utf-8", "latin-1"]:
                try:
                    return pd.read_csv(chemin, encoding=enc, sep=sep, on_bad_lines="skip")
                except Exception:
                    continue
        raise ValueError("Impossible de lire le fichier CSV avec les encodages testés.")

    elif ext in (".xlsx", ".xls"):
        return pd.read_excel(chemin)

    elif ext == ".json":
        return pd.read_json(chemin)

    else:
        raise ValueError(f"Format non supporté : {ext}. Formats acceptés : CSV, Excel, JSON.")


# ─── Détection du rôle sémantique d'une colonne ────────────────────────────────

def detecter_role(serie: pd.Series, nom_colonne: str) -> str:
    """
    Estime le rôle sémantique d'une colonne selon son contenu.
    Retourne : 'quantitative', 'categorielle', 'date', 'texte_libre', 'identifiant'
    """
    # Mots-clés qui suggèrent un identifiant, comparés à des mots ENTIERS du nom
    # ("Humidity" contient "id" mais n'est pas un identifiant)
    nom = re.sub(r"([a-z])([A-Z])", r"\1 \2", str(nom_colonne)).lower()
    mots_du_nom = set(re.split(r"[^a-z0-9]+", nom))
    mots_identifiant = {"id", "code", "matricule", "numero", "num", "ref", "telephone", "tel", "postal", "cp", "uuid", "siret", "siren"}
    if mots_du_nom & mots_identifiant:
        return "identifiant"

    # Colonne déjà convertie en dates
    if pd.api.types.is_datetime64_any_dtype(serie):
        return "date"

    # Colonne de texte : date si au moins SEUIL_DATES (80 %) des valeurs sont des dates
    if serie.dtype == object and proportion_de_dates(serie) >= SEUIL_DATES:
        return "date"

    # Colonne numérique
    if pd.api.types.is_numeric_dtype(serie) and not pd.api.types.is_bool_dtype(serie):
        valeurs = serie.dropna()
        nb_uniques = valeurs.nunique()
        nb_lignes = valeurs.count()
        # Des nombres entiers tous différents ressemblent à un identifiant
        if pd.api.types.is_integer_dtype(serie) and nb_uniques == nb_lignes and nb_lignes > 10:
            return "identifiant"
        # Nombres entiers, même enregistrés avec une virgule (3.0) quand la colonne a des vides
        entiers = pd.api.types.is_integer_dtype(serie) or bool((valeurs % 1 == 0).all())
        # Un nombre à virgule (montant, prix, température…) est toujours une mesure
        if not entiers:
            return "quantitative"
        # Peu de valeurs entières qui se répètent (nombre d'enfants, note de 1 à 5…) : une catégorie
        if nb_uniques <= 20 and nb_uniques <= nb_lignes / 2:
            return "categorielle"
        return "quantitative"

    # Colonne texte
    if serie.dtype == object:
        nb_uniques = serie.nunique()
        nb_lignes = serie.count()
        if nb_lignes == 0:
            return "inconnu"
        ratio = nb_uniques / nb_lignes
        if ratio > 0.8:
            return "texte_libre"
        return "categorielle"

    return "inconnu"


# ─── Inspection principale ─────────────────────────────────────────────────────

def inspecter(chemin: str, nom_fichier: str) -> dict:
    """
    Point d'entrée principal de l'inspecteur.
    Retourne un dictionnaire complet décrivant le fichier.
    """
    try:
        df = lire_fichier(chemin, nom_fichier)
    except Exception as e:
        return {"erreur": str(e), "lisible": False}

    if df.empty:
        return {"erreur": "Le fichier est vide ou ne contient aucune donnée.", "lisible": False}

    nb_lignes, nb_colonnes = df.shape

    # Analyse colonne par colonne
    colonnes = []
    for nom in df.columns:
        serie = df[nom]
        nb_manquants = int(serie.isna().sum())
        pct_manquants = round(nb_manquants / nb_lignes * 100, 1) if nb_lignes > 0 else 0
        nb_uniques = int(serie.nunique())
        role = detecter_role(serie, nom)

        colonnes.append({
            "nom": nom,
            "type_technique": str(serie.dtype),
            "role_estime": role,
            "nb_manquants": nb_manquants,
            "pct_manquants": pct_manquants,
            "nb_valeurs_uniques": nb_uniques,
            "colonne_vide": nb_manquants == nb_lignes,
        })

    # Doublons (ignoré si fichier trop volumineux)
    if nb_lignes <= 100_000:
        nb_doublons = int(df.duplicated().sum())
    else:
        nb_doublons = -1  # non calculé

    # Colonnes vides
    colonnes_vides = [c["nom"] for c in colonnes if c["colonne_vide"]]

    # Résumé qualité global
    total_cellules = nb_lignes * nb_colonnes
    total_manquants = sum(c["nb_manquants"] for c in colonnes)
    pct_manquants_global = round(total_manquants / total_cellules * 100, 1) if total_cellules > 0 else 0

    return {
        "lisible": True,
        "nom_fichier": nom_fichier,
        "nb_lignes": nb_lignes,
        "nb_colonnes": nb_colonnes,
        "colonnes": colonnes,
        "nb_doublons": nb_doublons,
        "colonnes_vides": colonnes_vides,
        "qualite": {
            "total_manquants": total_manquants,
            "pct_manquants_global": pct_manquants_global,
            "nb_doublons": nb_doublons,
            "nb_colonnes_vides": len(colonnes_vides),
        },
       "apercu": df.head(5).where(pd.notnull(df.head(5)), None).to_dict(orient="records"),
    }


# ─── Fiche d'identité du jeu de données PROPRE (pour l'Analyste) ───────────────

def _valeur_simple(v, longueur_max: int = 60):
    """Rend une valeur lisible en JSON (dates en texte, NaN en None, textes raccourcis)."""
    if v is None:
        return None
    try:
        if pd.isna(v):
            return None
    except (TypeError, ValueError):
        pass
    if isinstance(v, pd.Timestamp):
        return v.isoformat()
    if hasattr(v, "item"):  # nombres numpy → nombres Python
        v = v.item()
    if isinstance(v, float):
        return round(v, 4)
    if isinstance(v, str) and len(v) > longueur_max:
        return v[:longueur_max] + "…"
    return v


def _role_colonne_propre(serie: pd.Series, nom: str) -> str:
    """Rôle d'une colonne après nettoyage (les dates sont déjà de vraies dates)."""
    if pd.api.types.is_datetime64_any_dtype(serie):
        return "date"
    if pd.api.types.is_bool_dtype(serie):
        return "categorielle"
    return detecter_role(serie, nom)


def _type_simple(serie: pd.Series) -> str:
    """Type de la colonne en mots simples, pour que l'Analyste écrive un SQL correct."""
    if pd.api.types.is_bool_dtype(serie):
        return "booleen"
    if pd.api.types.is_integer_dtype(serie):
        return "entier"
    if pd.api.types.is_float_dtype(serie):
        return "decimal"
    if pd.api.types.is_datetime64_any_dtype(serie):
        return "date"
    return "texte"


def fiche_identite(df: pd.DataFrame, titre: str = "", description: str = "", roles_imposes: dict | None = None) -> dict:
    """
    Décrit le jeu de données PROPRE pour l'Analyste, sans lui donner les données elles-mêmes.
    Pour chaque colonne : son type, son rôle et des statistiques adaptées à ce rôle.
    Le jeu de données est lu en entier par Python ; seule cette description sera envoyée au modèle.
    """
    nb_lignes, nb_colonnes = df.shape
    colonnes = []

    for nom in df.columns:
        serie = df[nom]
        # Un rôle corrigé par Atlas au nettoyage (et accepté par le serveur) remplace celui deviné par Python
        role = (roles_imposes or {}).get(str(nom)) or _role_colonne_propre(serie, nom)
        nb_manquants = int(serie.isna().sum())
        info = {
            "nom": str(nom),
            "type": _type_simple(serie),
            "role": role,
            "pct_manquants": round(nb_manquants / nb_lignes * 100, 1) if nb_lignes else 0,
            "nb_valeurs_differentes": int(serie.nunique(dropna=True)),
        }
        valeurs = serie.dropna()

        if role == "quantitative" and pd.api.types.is_numeric_dtype(serie) and not valeurs.empty:
            info.update({
                "min": _valeur_simple(valeurs.min()),
                "max": _valeur_simple(valeurs.max()),
                "moyenne": _valeur_simple(valeurs.mean()),
                "mediane": _valeur_simple(valeurs.median()),
                "ecart_type": _valeur_simple(valeurs.std()) if len(valeurs) > 1 else None,
            })

        elif role == "categorielle" and not valeurs.empty:
            comptes = valeurs.value_counts().head(10)
            info["valeurs_frequentes"] = [
                {"valeur": _valeur_simple(v), "pct": round(int(n) / len(valeurs) * 100, 1)}
                for v, n in comptes.items()
            ]
            if pd.api.types.is_numeric_dtype(serie) and not pd.api.types.is_bool_dtype(serie):
                info["min"] = _valeur_simple(valeurs.min())
                info["max"] = _valeur_simple(valeurs.max())

        elif role == "date" and not valeurs.empty:
            dates = valeurs if pd.api.types.is_datetime64_any_dtype(serie) else pd.to_datetime(valeurs, errors="coerce").dropna()
            if not dates.empty:
                info["premiere_date"] = _valeur_simple(dates.min())
                info["derniere_date"] = _valeur_simple(dates.max())

        else:  # texte libre, identifiant, inconnu : quelques exemples suffisent
            info["exemples"] = [_valeur_simple(v) for v in valeurs.drop_duplicates().head(3)]

        colonnes.append(info)

    # 10 lignes d'exemple, prises dans tout le fichier (pas seulement le début)
    echantillon = df.sample(n=min(10, nb_lignes), random_state=42).sort_index() if nb_lignes else df
    lignes_exemple = [
        {str(c): _valeur_simple(v) for c, v in ligne.items()}
        for ligne in echantillon.to_dict(orient="records")
    ]

    return {
        "titre": titre or "",
        "description": description or "",
        "nb_lignes": int(nb_lignes),
        "nb_colonnes": int(nb_colonnes),
        "table_sql": "donnees",
        "colonnes": colonnes,
        "lignes_exemple": lignes_exemple,
    }