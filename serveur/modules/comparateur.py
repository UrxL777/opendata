# ─── Comparaison d'un nouveau fichier avec un jeu déjà publié ─────────────────
#
# Règle : mêmes colonnes ET au moins 70 % des lignes de l'ancien fichier
# retrouvées dans le nouveau = nouvelle version du jeu.
# Tout le reste = nouveau jeu de données.

import re
import unicodedata
import pandas as pd

SEUIL_LIGNES = 70.0      # % minimum de lignes de l'ancien fichier retrouvées
LIMITE_LIGNES = 200_000  # au-delà, on compare un échantillon de l'ancien fichier


def normaliser_nom(nom) -> str:
    """'  Année de naissance ' → 'annee_de_naissance'"""
    texte = unicodedata.normalize("NFD", str(nom).strip().lower())
    texte = "".join(c for c in texte if unicodedata.category(c) != "Mn")
    return re.sub(r"[^a-z0-9]+", "_", texte).strip("_")


def memes_colonnes(colonnes_anciennes, colonnes_nouvelles) -> bool:
    """Vrai si les deux fichiers ont exactement les mêmes colonnes (ordre, casse et accents ignorés)."""
    anciennes = sorted(normaliser_nom(c) for c in colonnes_anciennes)
    nouvelles = sorted(normaliser_nom(c) for c in colonnes_nouvelles)
    return anciennes == nouvelles


def _valeurs_texte(serie: pd.Series) -> pd.Series:
    """Écrit les valeurs de la même façon quel que soit le format (1, 1.0 → '1')."""
    if pd.api.types.is_numeric_dtype(serie) and not pd.api.types.is_bool_dtype(serie):
        return serie.map(lambda v: "" if pd.isna(v) else format(float(v), ".10g"))
    return serie.astype(str).str.strip().where(serie.notna(), "")


def pourcentage_lignes_communes(df_ancien: pd.DataFrame, df_nouveau: pd.DataFrame) -> float:
    """Pourcentage des lignes de l'ancien fichier retrouvées à l'identique dans le nouveau."""
    if df_ancien.empty:
        return 0.0
    if len(df_ancien) > LIMITE_LIGNES:
        pas = len(df_ancien) // LIMITE_LIGNES + 1
        df_ancien = df_ancien.iloc[::pas]

    # Mêmes colonnes dans le même ordre pour les deux fichiers
    noms_nouveaux = {normaliser_nom(c): c for c in df_nouveau.columns}
    colonnes = sorted(df_ancien.columns, key=normaliser_nom)
    ancien = pd.DataFrame({i: _valeurs_texte(df_ancien[c]) for i, c in enumerate(colonnes)})
    nouveau = pd.DataFrame({i: _valeurs_texte(df_nouveau[noms_nouveaux[normaliser_nom(c)]])
                            for i, c in enumerate(colonnes)})

    hash_anciens = pd.util.hash_pandas_object(ancien, index=False)
    hash_nouveaux = set(pd.util.hash_pandas_object(nouveau, index=False))
    return round(float(hash_anciens.isin(hash_nouveaux).mean()) * 100, 1)


def comparer(df_ancien: pd.DataFrame, df_nouveau: pd.DataFrame) -> dict:
    """Point d'entrée : le nouveau fichier est-il une nouvelle version de l'ancien ?"""
    if not memes_colonnes(df_ancien.columns, df_nouveau.columns):
        return {"nouvelle_version": False, "memes_colonnes": False, "pct_lignes": 0.0}

    pct_lignes = pourcentage_lignes_communes(df_ancien, df_nouveau)
    return {
        "nouvelle_version": pct_lignes >= SEUIL_LIGNES,
        "memes_colonnes": True,
        "pct_lignes": pct_lignes,
    }
