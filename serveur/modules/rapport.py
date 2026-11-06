# ─── Génération du rapport de nettoyage ────────────────────────────────────────

def generer_rapport(inspection: dict, nettoyage: dict) -> dict:
    """Produit un rapport simple : ce qui a été nettoyé, avant/après."""
    lignes_avant = inspection["nb_lignes"]
    lignes_apres = nettoyage["nb_lignes_final"]
    lignes_supprimees = lignes_avant - lignes_apres

    return {
        "lignes_avant": lignes_avant,
        "lignes_apres": lignes_apres,
        "lignes_supprimees": lignes_supprimees,
        "nb_colonnes": inspection.get("nb_colonnes", 0),
        "operations": nettoyage["journal"],
    }