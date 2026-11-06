import pandas as pd
import chardet
import os

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
    nom = nom_colonne.lower()

    # Mots-clés qui suggèrent un identifiant
    mots_identifiant = ["id", "code", "matricule", "numero", "num", "ref", "telephone", "tel", "postal"]
    if any(mot in nom for mot in mots_identifiant):
        return "identifiant"

    # Tenter une conversion en date (sans infer_datetime_format, supprimé en pandas 2.2)
    if serie.dtype == object:
        try:
            pd.to_datetime(serie.dropna().head(50), errors="raise")
            return "date"
        except Exception:
            pass

    # Colonne numérique
    if pd.api.types.is_numeric_dtype(serie):
        nb_uniques = serie.nunique()
        nb_lignes = serie.count()
        if nb_uniques == nb_lignes and nb_lignes > 10:
            return "identifiant"
        if nb_uniques <= 20:
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