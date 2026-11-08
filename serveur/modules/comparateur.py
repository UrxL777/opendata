# ─── Comparaison d'un nouveau fichier avec un jeu déjà publié ─────────────────
#
# Sert à reconnaître une nouvelle version d'un jeu de données :
#   1. les colonnes doivent correspondre (par nom, ou par contenu si renommées)
#   2. les lignes de l'ancien fichier doivent se retrouver dans le nouveau

import re
import unicodedata
import pandas as pd

SEUIL_COLONNES = 70.0   # % minimum de colonnes associées
SEUIL_LIGNES = 70.0     # % minimum de lignes de l'ancien fichier retrouvées
LIMITE_LIGNES = 200_000  # au-delà, on compare un échantillon de l'ancien fichier


def normaliser_nom(nom) -> str:
    """'  Année de naissance ' → 'annee_de_naissance'"""
    texte = unicodedata.normalize("NFD", str(nom).strip().lower())
    texte = "".join(c for c in texte if unicodedata.category(c) != "Mn")
    return re.sub(r"[^a-z0-9]+", "_", texte).strip("_")


def _valeurs_texte(serie: pd.Series) -> pd.Series:
    """Écrit les valeurs de la même façon quel que soit le format (1, 1.0 → '1')."""
    if pd.api.types.is_numeric_dtype(serie) and not pd.api.types.is_bool_dtype(serie):
        return serie.map(lambda v: "" if pd.isna(v) else format(float(v), ".10g"))
    return serie.astype(str).str.strip().where(serie.notna(), "")


def associer_colonnes(df_ancien: pd.DataFrame, df_nouveau: pd.DataFrame) -> tuple[dict, float]:
    """
    Associe chaque colonne de l'ancien fichier à une colonne du nouveau.
    Retourne ({colonne_ancienne: colonne_nouvelle}, pourcentage de colonnes associées).
    """
    association = {}
    noms_nouveaux = {normaliser_nom(c): c for c in df_nouveau.columns}

    # 1. Par nom
    for col in df_ancien.columns:
        cible = noms_nouveaux.get(normaliser_nom(col))
        if cible is not None and cible not in association.values():
            association[col] = cible

    # 2. Par contenu, pour les colonnes renommées
    nouvelles_libres = [c for c in df_nouveau.columns if c not in association.values()]
    for col in [c for c in df_ancien.columns if c not in association]:
        valeurs_anciennes = set(_valeurs_texte(df_ancien[col]).unique()) - {""}
        if not valeurs_anciennes:
            continue
        meilleure, meilleur_score = None, 0.0
        for candidate in nouvelles_libres:
            valeurs_nouvelles = set(_valeurs_texte(df_nouveau[candidate]).unique())
            score = len(valeurs_anciennes & valeurs_nouvelles) / len(valeurs_anciennes) * 100
            if score > meilleur_score:
                meilleure, meilleur_score = candidate, score
        if meilleure is not None and meilleur_score >= SEUIL_COLONNES:
            association[col] = meilleure
            nouvelles_libres.remove(meilleure)

    # Rapporté au plus grand des deux fichiers : trop de colonnes ajoutées
    # ou supprimées fait baisser le pourcentage.
    total = max(len(df_ancien.columns), len(df_nouveau.columns)) or 1
    return association, round(len(association) / total * 100, 1)


def pourcentage_lignes_communes(df_ancien: pd.DataFrame, df_nouveau: pd.DataFrame, association: dict) -> float:
    """Pourcentage des lignes de l'ancien fichier retrouvées à l'identique dans le nouveau."""
    if not association or df_ancien.empty:
        return 0.0
    if len(df_ancien) > LIMITE_LIGNES:
        pas = len(df_ancien) // LIMITE_LIGNES + 1
        df_ancien = df_ancien.iloc[::pas]

    colonnes = list(association)
    ancien = pd.DataFrame({i: _valeurs_texte(df_ancien[c]) for i, c in enumerate(colonnes)})
    nouveau = pd.DataFrame({i: _valeurs_texte(df_nouveau[association[c]]) for i, c in enumerate(colonnes)})

    hash_anciens = pd.util.hash_pandas_object(ancien, index=False)
    hash_nouveaux = set(pd.util.hash_pandas_object(nouveau, index=False))
    return round(float(hash_anciens.isin(hash_nouveaux).mean()) * 100, 1)


def comparer(df_ancien: pd.DataFrame, df_nouveau: pd.DataFrame) -> dict:
    """Point d'entrée : le nouveau fichier est-il une nouvelle version de l'ancien ?"""
    association, pct_colonnes = associer_colonnes(df_ancien, df_nouveau)
    if pct_colonnes < SEUIL_COLONNES:
        return {"nouvelle_version": False, "pct_colonnes": pct_colonnes, "pct_lignes": 0.0}

    pct_lignes = pourcentage_lignes_communes(df_ancien, df_nouveau, association)
    return {
        "nouvelle_version": pct_lignes >= SEUIL_LIGNES,
        "pct_colonnes": pct_colonnes,
        "pct_lignes": pct_lignes,
    }
