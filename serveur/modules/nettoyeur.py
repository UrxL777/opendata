import pandas as pd
import numpy as np
from dateutil import parser as dateutil_parser

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
            operations.append(f"Colonne '{col}' : espaces nettoyés, chaînes vides converties en NaN.")
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
            df[col] = pd.to_datetime(df[col], errors="coerce")
            operations.append(f"Colonne '{col}' convertie en date.")
        except Exception:
            operations.append(f"Colonne '{col}' : conversion en date échouée, conservée telle quelle.")
    return df, operations


def imputer_valeurs_manquantes(df: pd.DataFrame, colonnes_inspection: list) -> tuple[pd.DataFrame, list]:
    """
    Impute les valeurs manquantes selon le type de colonne.
    - Quantitative : médiane (résistante aux valeurs atypiques)
    - Catégorielle : mode (valeur la plus fréquente)
    - Identifiant / texte libre / date : on ne touche pas
    """
    operations = []
    for col_info in colonnes_inspection:
        col = col_info["nom"]
        if col not in df.columns:
            continue
        if col_info["pct_manquants"] == 0:
            continue

        role = col_info["role_estime"]
        nb_manquants = col_info["nb_manquants"]

        if role == "quantitative":
            mediane = df[col].median()
            df[col] = df[col].fillna(mediane)
            operations.append(f"Colonne '{col}' ({nb_manquants} manquants) : imputée avec la médiane ({round(mediane, 2)}).")

        elif role == "categorielle":
            if df[col].notna().any():
                mode = df[col].mode()[0]
                df[col] = df[col].fillna(mode)
                operations.append(f"Colonne '{col}' ({nb_manquants} manquants) : imputée avec le mode ('{mode}').")

        else:
            operations.append(f"Colonne '{col}' ({nb_manquants} manquants, rôle : {role}) : conservée sans imputation.")

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

def nettoyer(df: pd.DataFrame, colonnes_inspection: list) -> dict:
    """
    Applique toutes les étapes de nettoyage dans l'ordre.
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

    df, ops = imputer_valeurs_manquantes(df, colonnes_inspection)
    journal.extend(ops)

    anomalies = detecter_anomalies(df, colonnes_inspection)

    return {
        "df_nettoye": df,
        "journal": journal,
        "anomalies": anomalies,
        "nb_lignes_final": len(df),
        "nb_colonnes_final": len(df.columns),
    }