"""
Exécution sécurisée des requêtes SQL de l'Analyste avec DuckDB.

Le modèle d'IA écrit des requêtes SQL ; ce module les exécute sur le jeu de données
propre (format Parquet), sans que la requête puisse toucher à autre chose :
  1. le jeu de données est chargé dans une table « donnees » (filtres déjà appliqués) ;
  2. DuckDB n'a ensuite plus accès aux fichiers ni à Internet ;
  3. seule UNE requête de LECTURE est acceptée (SELECT ou WITH) ;
  4. le résultat est limité à LIMITE_LIGNES lignes et à DUREE_MAX secondes.
"""

import datetime
import decimal
import math
import re
import threading

import duckdb

LIMITE_LIGNES = 50   # nombre maximum de lignes rendues
DUREE_MAX = 10       # secondes maximum pour une requête

# Mots refusés dans une requête de l'Analyste (en plus du blocage de l'accès aux fichiers)
MOTS_INTERDITS = {
    "insert", "update", "delete", "drop", "alter", "create", "replace", "truncate",
    "copy", "attach", "detach", "install", "load", "pragma", "export", "import",
    "call", "set", "reset", "checkpoint", "vacuum", "grant", "revoke",
}
FONCTIONS_INTERDITES = re.compile(
    r"\b(read_\w+|glob|parquet_\w+|sniff_csv|getenv|current_setting|duckdb_\w+)\s*\(",
    re.IGNORECASE,
)


def _sans_commentaires(sql: str) -> str:
    """Retire les commentaires SQL (-- … et /* … */)."""
    sql = re.sub(r"/\*.*?\*/", " ", sql, flags=re.DOTALL)
    return re.sub(r"--[^\n]*", " ", sql)


def verifier_sql(sql: str) -> str | None:
    """Rend un message d'erreur si la requête n'est pas acceptable, sinon None."""
    if not sql or not sql.strip():
        return "La requête est vide."
    propre = _sans_commentaires(sql).strip().rstrip(";").strip()
    # On enlève le contenu des textes entre apostrophes pour ne pas analyser les valeurs
    sans_textes = re.sub(r"'(?:[^']|'')*'", "''", propre)
    if ";" in sans_textes:
        return "Une seule requête est autorisée (pas de point-virgule au milieu)."
    premier_mot = sans_textes.split(None, 1)[0].lower() if sans_textes else ""
    if premier_mot not in ("select", "with"):
        return "Seules les requêtes de lecture (SELECT ou WITH) sont autorisées."
    mots = set(re.findall(r"[a-z_]+", sans_textes.lower()))
    interdits = mots & MOTS_INTERDITS
    if interdits:
        return f"Mot interdit dans la requête : {', '.join(sorted(interdits))}."
    if FONCTIONS_INTERDITES.search(sans_textes):
        return "Lecture de fichiers ou de paramètres interdite : utilise uniquement la table donnees."
    return None


def _guillemets(nom: str) -> str:
    """Écrit un nom de colonne entre guillemets, sans risque d'injection."""
    return '"' + str(nom).replace('"', '""') + '"'


def _valeur_json(v):
    """Convertit une valeur DuckDB en valeur JSON (dates en texte, NaN en null…)."""
    if v is None:
        return None
    if isinstance(v, float):
        return None if math.isnan(v) or math.isinf(v) else round(v, 6)
    if isinstance(v, decimal.Decimal):
        return float(v)
    if isinstance(v, (datetime.datetime, datetime.date, datetime.time)):
        return v.isoformat()
    if isinstance(v, datetime.timedelta):
        return str(v)
    if isinstance(v, (bytes, bytearray)):
        return None
    if isinstance(v, (list, tuple)):
        return [_valeur_json(x) for x in v]
    if isinstance(v, dict):
        return {str(k): _valeur_json(x) for k, x in v.items()}
    return v


NOM_VALIDE = re.compile(r"^[a-z][a-z0-9_]{0,39}$")


def verifier_colonne_calculee(colonne: dict, noms_existants: list) -> str | None:
    """
    Vérifie une colonne calculée proposée par l'Analyste, comme une colonne calculée Power BI.
    Ex. {"nom": "categorie_imc", "expression": "CASE WHEN bmi < 18.5 THEN 'Sous-poids' ... END"}
    Rend un message d'erreur, ou None si elle est acceptable.
    """
    nom = str(colonne.get("nom", ""))
    expression = str(colonne.get("expression", "")).strip()
    if not NOM_VALIDE.match(nom):
        return f"Nom de colonne calculée invalide : « {nom} » (minuscules, chiffres et _ uniquement)."
    if nom in noms_existants:
        return f"La colonne « {nom} » existe déjà."
    if not expression:
        return f"Expression vide pour la colonne « {nom} »."
    sans_textes = re.sub(r"'(?:[^']|'')*'", "''", _sans_commentaires(expression))
    mots = set(re.findall(r"[a-z_]+", sans_textes.lower()))
    if ";" in sans_textes or mots & (MOTS_INTERDITS | {"select", "from", "union"}) or FONCTIONS_INTERDITES.search(sans_textes):
        return f"Expression interdite pour la colonne « {nom} » : seule une formule (ex. CASE WHEN) est permise."
    return None


def _charger(con, chemin: str, filtres: dict | None, colonnes_calculees: list | None) -> None:
    """
    Charge le jeu de données dans la table « donnees » :
    1. lecture du fichier ;  2. plus aucun accès aux fichiers ;
    3. ajout des colonnes calculées ;  4. application des filtres.
    """
    chemin_sql = "'" + chemin.replace("'", "''") + "'"
    lecture = "read_parquet" if chemin.lower().endswith(".parquet") else "read_csv_auto"
    con.execute(f"CREATE TABLE donnees_brutes AS SELECT * FROM {lecture}({chemin_sql})")

    # À partir d'ici, DuckDB ne peut plus lire aucun fichier
    con.execute("SET enable_external_access = false")

    # Colonnes calculées (catégorie IMC, tranches d'âge…), chacune vérifiée avant d'être ajoutée
    colonnes = [ligne[0] for ligne in con.execute("DESCRIBE donnees_brutes").fetchall()]
    ajouts = []
    for colonne in colonnes_calculees or []:
        probleme = verifier_colonne_calculee(colonne, colonnes + [a["nom"] for a in ajouts])
        if probleme:
            raise ValueError(probleme)
        ajouts.append(colonne)
    selection = ", ".join(["*"] + [f"({c['expression']}) AS {_guillemets(c['nom'])}" for c in ajouts])
    con.execute(f"CREATE TABLE donnees_completes AS SELECT {selection} FROM donnees_brutes")
    con.execute("DROP TABLE donnees_brutes")

    colonnes = [ligne[0] for ligne in con.execute("DESCRIBE donnees_completes").fetchall()]
    conditions, parametres = [], []
    for colonne, valeur in (filtres or {}).items():
        if colonne not in colonnes:
            raise ValueError(f"Filtre sur une colonne inconnue : {colonne}")
        valeurs = valeur if isinstance(valeur, list) else [valeur]
        valeurs = [v for v in valeurs if v is not None]
        if not valeurs:
            continue
        marques = ", ".join("?" for _ in valeurs)
        conditions.append(f"CAST({_guillemets(colonne)} AS VARCHAR) IN ({marques})")
        parametres.extend(str(v) for v in valeurs)

    clause = (" WHERE " + " AND ".join(conditions)) if conditions else ""
    con.execute(f"CREATE TABLE donnees AS SELECT * FROM donnees_completes{clause}", parametres)
    con.execute("DROP TABLE donnees_completes")


def executer_requete(chemin: str, sql: str, filtres: dict | None = None,
                     colonnes_calculees: list | None = None) -> dict:
    """
    Exécute une requête de lecture sur le jeu de données propre.

    chemin  : fichier local du jeu de données propre (.parquet, ou .csv)
    sql     : la requête écrite par l'Analyste, qui lit la table « donnees »
    filtres : facultatif, ex. {"region": "southeast"} ou {"region": ["southeast", "northwest"]}
              (on peut aussi filtrer sur une colonne calculée, ex. {"categorie_imc": "Obésité"})
    colonnes_calculees : facultatif, ex. [{"nom": "categorie_imc", "expression": "CASE WHEN … END"}]

    Rend {"ok": True, "colonnes": [...], "lignes": [[...], ...], "tronque": bool}
    ou   {"ok": False, "erreur": "message"}.
    """
    probleme = verifier_sql(sql)
    if probleme:
        return {"ok": False, "erreur": probleme}

    requete = _sans_commentaires(sql).strip().rstrip(";").strip()
    con = duckdb.connect(":memory:")
    minuteur = threading.Timer(DUREE_MAX, con.interrupt)
    try:
        _charger(con, chemin, filtres, colonnes_calculees)

        # DuckDB ne peut déjà plus lire de fichier ; on bloque aussi tout changement de réglage
        con.execute("SET lock_configuration = true")

        minuteur.start()
        curseur = con.execute(f"SELECT * FROM ({requete}) AS resultat LIMIT {LIMITE_LIGNES + 1}")
        noms = [d[0] for d in curseur.description]
        lignes = curseur.fetchall()
        minuteur.cancel()

        tronque = len(lignes) > LIMITE_LIGNES
        lignes = [[_valeur_json(v) for v in ligne] for ligne in lignes[:LIMITE_LIGNES]]
        return {"ok": True, "colonnes": noms, "lignes": lignes, "tronque": tronque}

    except duckdb.InterruptException:
        return {"ok": False, "erreur": f"La requête a dépassé {DUREE_MAX} secondes."}
    except Exception as e:
        message = str(e).strip().splitlines()[0] if str(e).strip() else type(e).__name__
        return {"ok": False, "erreur": message[:500]}
    finally:
        minuteur.cancel()
        con.close()
