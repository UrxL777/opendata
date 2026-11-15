import pandas as pd
import numpy as np
from modules.inspecteur import convertir_en_dates, proportion_de_dates, SEUIL_DATES

# ─── Corrections automatiques sûres (catégorie 1) ──────────────────────────────

def nettoyer_textes(df: pd.DataFrame) -> tuple[pd.DataFrame, list]:
    """Supprime les espaces superflus et normalise la casse des colonnes texte."""
    operations = []
    for col in df.select_dtypes(include="object").columns:
        avant = df[col].copy()
        df[col] = df[col].str.strip()
        df[col] = df[col].str.replace(r"\s+", " ", regex=True)
        # Remplacer les chaînes vides par NaN
        df[col] = df[col].replace("", np.nan)
        if not df[col].equals(avant):
            operations.append(f"Colonne '{col}' : espaces en trop retirés, cases vides considérées comme manquantes.")
    return df, operations


def supprimer_colonnes_vides(df: pd.DataFrame) -> tuple[pd.DataFrame, list]:
    """Supprime les colonnes entièrement vides."""
    operations = []
    cols_vides = [col for col in df.columns if df[col].isna().all()]
    if cols_vides:
        df = df.drop(columns=cols_vides)
        operations.append(f"Colonnes entièrement vides supprimées : {cols_vides}")
    return df, operations


def supprimer_doublons_exacts(df: pd.DataFrame) -> tuple[pd.DataFrame, list]:
    """Supprime les lignes entièrement dupliquées."""
    operations = []
    nb_avant = len(df)
    df = df.drop_duplicates()
    nb_supprimes = nb_avant - len(df)
    if nb_supprimes > 0:
        operations.append(f"{nb_supprimes} ligne(s) dupliquée(s) exacte(s) supprimée(s).")
    return df, operations


# ─── Corrections conditionnelles (catégorie 2) ─────────────────────────────────

def convertir_dates(df: pd.DataFrame, colonnes_inspection: list) -> tuple[pd.DataFrame, list]:
    """Convertit les colonnes identifiées comme dates par l'inspecteur."""
    operations = []
    cols_dates = [c["nom"] for c in colonnes_inspection if c["role_estime"] == "date" and c["nom"] in df.columns]
    for col in cols_dates:
        try:
            if pd.api.types.is_datetime64_any_dtype(df[col]):
                continue
            avant = int(df[col].notna().sum())
            df[col] = convertir_en_dates(df[col])
            illisibles = avant - int(df[col].notna().sum())
            message = f"Colonne '{col}' convertie en date (formats harmonisés)."
            if illisibles:
                message += f" {illisibles} date(s) illisible(s) laissée(s) vide(s), aucune n'est inventée."
            operations.append(message)
        except Exception:
            operations.append(f"Colonne '{col}' : conversion en date échouée, conservée telle quelle.")
    return df, operations


# Le « menu » : les seules actions qu'Atlas a le droit de choisir pour les cases vides d'une colonne.
# Atlas décide (il comprend le sens des colonnes), Python vérifie puis applique.
ACTIONS_MANQUANTS = ("laisser_vide", "mediane", "moyenne", "mode")
MAX_PCT_IMPUTATION = 40  # au-delà, remplir reviendrait à inventer une trop grande partie de la colonne


def _choix_controle(col: str, choix: dict, role: str, numerique: bool, pct: float,
                    colonne_principale: str | None) -> tuple[str, str]:
    """Rend l'action finale et, si le code a refusé le choix d'Atlas, la règle appliquée."""
    action = choix.get("action")
    if action not in ACTIONS_MANQUANTS:
        return "laisser_vide", "choix hors menu"
    if action == "laisser_vide":
        return action, ""
    if col == colonne_principale:
        return "laisser_vide", "la colonne principale n'est jamais remplie"
    if role in ("date", "identifiant", "texte_libre"):
        return "laisser_vide", "une date, un identifiant ou un texte libre n'est jamais rempli"
    if action in ("mediane", "moyenne") and not numerique:
        return "laisser_vide", "médiane et moyenne seulement pour des nombres"
    if pct > MAX_PCT_IMPUTATION:
        return "laisser_vide", f"plus de {MAX_PCT_IMPUTATION} % de cases vides"
    return action, ""


ROLES_POSSIBLES = ("quantitative", "categorielle", "date", "identifiant", "texte_libre")
NOMS_ROLES = {"quantitative": "quantitative (des nombres à calculer)", "categorielle": "catégorielle (des groupes)",
              "date": "date", "identifiant": "identifiant", "texte_libre": "texte libre"}


def corriger_roles(df: pd.DataFrame, colonnes_inspection: list, decision: dict | None) -> tuple[pd.DataFrame, list, dict]:
    """
    Applique les corrections de rôle proposées par Atlas (decision["roles_corriges"] = {nom: {"role", "raison"}}),
    après vérification par Python. Met à jour colonnes_inspection et rend les rôles acceptés.
    """
    operations, acceptes = [], {}
    corrections = (decision or {}).get("roles_corriges") or {}
    if not isinstance(corrections, dict):
        return df, operations, acceptes
    infos = {c["nom"]: c for c in colonnes_inspection}

    for col, choix in corrections.items():
        if col not in df.columns or not isinstance(choix, dict):
            continue
        nouveau, ancien = choix.get("role"), infos.get(col, {}).get("role_estime", "inconnu")
        if nouveau not in ROLES_POSSIBLES or nouveau == ancien:
            continue
        refus = ""
        if pd.api.types.is_datetime64_any_dtype(df[col]) and nouveau != "date":
            refus = "la colonne a déjà été reconnue comme date"
        elif nouveau == "quantitative" and not pd.api.types.is_numeric_dtype(df[col]):
            refus = "la colonne ne contient pas que des nombres"
        elif nouveau == "date" and not pd.api.types.is_datetime64_any_dtype(df[col]):
            if proportion_de_dates(df[col]) < SEUIL_DATES:
                refus = f"moins de {int(SEUIL_DATES * 100)} % des valeurs sont des dates"
            else:
                df[col] = convertir_en_dates(df[col])
        raison = str(choix.get("raison") or "").strip()
        if refus:
            operations.append(f"Colonne '{col}' : Atlas proposait le rôle « {NOMS_ROLES[nouveau]} », "
                              f"refusé par le serveur ({refus}).")
            continue
        if col in infos:
            infos[col]["role_estime"] = nouveau
        acceptes[col] = nouveau
        operations.append(f"Colonne '{col}' : rôle corrigé par Atlas, {NOMS_ROLES.get(ancien, ancien)} → "
                          f"{NOMS_ROLES[nouveau]}." + (f" Atlas : {raison}" if raison else ""))
    return df, operations, acceptes


def imputer_valeurs_manquantes(df: pd.DataFrame, colonnes_inspection: list, decision: dict | None = None) -> tuple[pd.DataFrame, list]:
    """
    Traite les cases vides selon la décision d'Atlas (decision = {"colonne_principale": ..., "colonnes": {nom: {"action", "raison"}}}).
    Sans décision (Atlas indisponible), rien n'est rempli : on n'invente aucune valeur.
    """
    operations = []
    decision = decision or {}
    choix_atlas = decision.get("colonnes") or {}
    colonne_principale = decision.get("colonne_principale")
    roles = {c["nom"]: c["role_estime"] for c in colonnes_inspection}
    nb_lignes = len(df)

    for col in df.columns:
        nb_manquants = int(df[col].isna().sum())
        if nb_manquants == 0:
            continue
        pct = round(nb_manquants / nb_lignes * 100, 1) if nb_lignes else 0
        debut = f"Colonne '{col}' : {nb_manquants} valeur(s) manquante(s) ({pct} %)"
        choix = choix_atlas.get(col) if isinstance(choix_atlas.get(col), dict) else {}
        raison = str(choix.get("raison") or "").strip()
        action, regle = _choix_controle(col, choix, roles.get(col, ""), pd.api.types.is_numeric_dtype(df[col]),
                                        pct, colonne_principale)

        valeur = None
        if action == "mediane":
            valeur = df[col].median()
        elif action == "moyenne":
            valeur = df[col].mean()
        elif action == "mode" and df[col].notna().any():
            valeur = df[col].mode()[0]
        if valeur is None or (isinstance(valeur, float) and np.isnan(valeur)):
            action = "laisser_vide"

        if action == "laisser_vide":
            message = f"{debut}, laissée(s) vide(s) : elle(s) ne compte(nt) pas dans les calculs."
        else:
            if isinstance(valeur, (float, np.floating)):
                valeur = round(float(valeur), 2)
            df[col] = df[col].fillna(valeur)
            nom_action = {"mediane": "la médiane", "moyenne": "la moyenne", "mode": "la valeur la plus fréquente"}[action]
            message = f"{debut}, remplie(s) avec {nom_action} ('{valeur}')."

        if not decision:
            message += " Décision par défaut : Atlas n'a pas pu être consulté."
        elif not choix:
            message += " Décision par défaut : Atlas ne s'est pas prononcé sur cette colonne."
        else:
            if raison:
                message += f" Atlas : {raison}"
            if regle:
                message += f" (Atlas proposait « {choix.get('action')} », refusé par le serveur : {regle}.)"
        operations.append(message)

    return df, operations


# ─── Détection des anomalies (catégorie 3 — signalement uniquement) ────────────

def detecter_anomalies(df: pd.DataFrame, colonnes_inspection: list) -> list:
    """
    Détecte les valeurs atypiques dans les colonnes quantitatives via IQR.
    Ne modifie rien — signale uniquement.
    """
    alertes = []
    cols_quant = [c["nom"] for c in colonnes_inspection if c["role_estime"] == "quantitative" and c["nom"] in df.columns]

    for col in cols_quant:
        serie = df[col].dropna()
        if len(serie) < 10:
            continue
        q1 = serie.quantile(0.25)
        q3 = serie.quantile(0.75)
        iqr = q3 - q1
        borne_inf = q1 - 1.5 * iqr
        borne_sup = q3 + 1.5 * iqr
        atypiques = serie[(serie < borne_inf) | (serie > borne_sup)]
        if len(atypiques) > 0:
            alertes.append({
                "colonne": col,
                "nb_atypiques": len(atypiques),
                "borne_inferieure": round(borne_inf, 2),
                "borne_superieure": round(borne_sup, 2),
                "message": f"{len(atypiques)} valeur(s) hors de [{round(borne_inf,2)}, {round(borne_sup,2)}]. À vérifier."
            })
    return alertes


# ─── Point d'entrée principal ──────────────────────────────────────────────────

def nettoyer(df: pd.DataFrame, colonnes_inspection: list, choisir_traitement=None) -> dict:
    """
    Applique toutes les étapes de nettoyage dans l'ordre.
    choisir_traitement : fonction qui reçoit le jeu presque propre et rend la décision d'Atlas
    sur les cases vides. Si elle échoue ou n'est pas donnée, les cases vides restent vides.
    Retourne le DataFrame nettoyé + le journal des opérations.
    """
    journal = []

    df, ops = nettoyer_textes(df)
    journal.extend(ops)

    df, ops = supprimer_colonnes_vides(df)
    journal.extend(ops)

    df, ops = supprimer_doublons_exacts(df)
    journal.extend(ops)

    df, ops = convertir_dates(df, colonnes_inspection)
    journal.extend(ops)

    # Atlas : un seul appel, deux missions (vérifier les rôles, choisir le traitement des cases vides)
    decision = None
    if choisir_traitement is not None:
        try:
            decision = choisir_traitement(df)
        except Exception as e:
            print(f"[NETTOYAGE] Atlas n'a pas pu être consulté : {str(e)[:200]}")

    colonnes_inspection = [dict(c) for c in colonnes_inspection]  # copie : l'inspection d'origine reste intacte
    df, ops, roles_atlas = corriger_roles(df, colonnes_inspection, decision)
    journal.extend(ops)

    df, ops = imputer_valeurs_manquantes(df, colonnes_inspection, decision)
    journal.extend(ops)

    anomalies = detecter_anomalies(df, colonnes_inspection)

    return {
        "df_nettoye": df,
        "journal": journal,
        "anomalies": anomalies,
        "nb_lignes_final": len(df),
        "nb_colonnes_final": len(df.columns),
        "roles_atlas": roles_atlas,
    }