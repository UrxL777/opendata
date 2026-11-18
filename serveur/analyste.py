"""
L'Analyste (Atlas dans son rôle de data analyst) : construit le dashboard automatique d'un jeu de données.

Le partage du travail :
  1. Python lit tout le fichier et donne des FAITS sur chaque colonne (cases vides, valeurs différentes,
     colonne vide ou identique partout). Pour le reste, il donne seulement un AVIS.
  2. Atlas comprend le sens : il décrit chaque colonne et décide lesquelles servent à l'analyse.
  3. Atlas trouve la question phare et ÉCRIT LES REQUÊTES SQL (une ou deux) qui y répondent,
     avec la façon de dessiner chaque graphique.
  4. Python exécute les requêtes avec DuckDB (lecture seule) et renvoie les erreurs à Atlas,
     qui corrige (3 essais au maximum).
  5. Atlas écrit le texte à partir des résultats ; Python le contrôle (chiffres inventés, causes,
     devises) avant l'enregistrement. React dessine ensuite les graphiques.
"""
import json
import re

import pandas as pd

from agent import _appeler_analyste, mettre_en_forme_resultat, retirer_devises_inventees, _valeurs_filtre, \
    completion_avec_secours
from modules.requetes import executer_requete

SEUIL_ECARTER = 30   # % de cases vides au-delà duquel une colonne est écartée de l'analyse
MAX_GRAPHIQUES = 2   # une question phare : un graphique, deux si la question a deux parties
MAX_FILTRES = 3
MAX_ESSAIS = 3       # essais pour corriger une requête qui échoue
MAX_POINTS_DATES = 31
MOIS = ["janvier", "février", "mars", "avril", "mai", "juin", "juillet", "août",
        "septembre", "octobre", "novembre", "décembre"]


# ─── 1. Python : les faits sur chaque colonne ─────────────────────────────────

def _simple(v):
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return None
    if hasattr(v, "item"):
        v = v.item()
    if isinstance(v, float):
        return round(v, 4)
    s = str(v)
    return s if len(s) <= 60 else s[:60] + "…"


def profiler(df: pd.DataFrame) -> dict:
    """Résumé de chaque colonne, calculé sur tout le fichier. Python ne décide que des faits sûrs."""
    n = len(df)
    textes = [c for c in df.columns if df[c].dtype == object]
    colonnes = []
    for c in df.columns:
        s = df[c]
        vides = int(s.isna().sum())
        nb = int(s.nunique(dropna=True))
        info = {"nom": c, "type": "nombre" if pd.api.types.is_numeric_dtype(s) else
                ("date" if pd.api.types.is_datetime64_any_dtype(s) else "texte"),
                "cases_vides": vides, "pct_vides": round(vides / n * 100, 1) if n else 0, "valeurs_differentes": nb}
        v = s.dropna()
        if info["type"] == "nombre" and len(v):
            info.update({"min": _simple(v.min()), "max": _simple(v.max()), "moyenne": _simple(v.mean())})
        if len(v):
            info["valeurs_frequentes"] = [_simple(x) for x in v.value_counts().head(6).index]
        # Faits sûrs : Python décide
        if vides == n:
            info["fait_python"] = f"entièrement vide ({vides} lignes sur {n})"
        elif nb == 1:
            info["fait_python"] = f"identique sur toutes les lignes (« {_simple(v.iloc[0])} »)"
        elif info["pct_vides"] > SEUIL_ECARTER:
            info["fait_python"] = f"{vides} cases vides sur {n} ({info['pct_vides']} %), trop pour être fiable"
        else:
            # Avis seulement : Atlas décide, selon le sens de la colonne
            for autre in textes:
                if autre != c and df[autre].nunique() == nb and 1 < nb < n \
                        and df.groupby(c)[autre].nunique().max() == 1 \
                        and df[autre].astype(str).str.len().mean() > s.astype(str).str.len().mean():
                    info["avis_python"] = f"semble être un code qui répète la colonne {autre} ; à toi de juger"
                    break
        colonnes.append(info)
    exemples = df.sample(min(5, n), random_state=42).to_dict(orient="records") if n else []
    exemples = [{k: _simple(v) for k, v in ligne.items()} for ligne in exemples]
    return {"nb_lignes": n, "nb_colonnes": df.shape[1], "colonnes": colonnes, "lignes_exemple": exemples}


def _profil_compact(profil: dict, budget_caracteres: int = 14000) -> dict:
    """Allège le profil d'un fichier très large pour rester sous la limite de tokens de Groq."""
    texte = json.dumps(profil, ensure_ascii=False, default=str)
    if len(texte) <= budget_caracteres:
        return profil
    allege = dict(profil, lignes_exemple=profil["lignes_exemple"][:2])
    allege["colonnes"] = [{k: v for k, v in c.items() if k != "valeurs_frequentes"} | (
        {"valeurs_frequentes": c["valeurs_frequentes"][:2]} if c.get("valeurs_frequentes") else {})
        for c in profil["colonnes"]]
    return allege


# ─── 2. Atlas : la description des colonnes ───────────────────────────────────

PROMPT_DESCRIPTION = """Tu es Atlas, l'assistant de la plateforme OpenData. Quelqu'un vient de publier un jeu de données et tu dois le présenter à des personnes qui ne connaissent pas forcément la data.
Tu ne vois pas le fichier : Python l'a lu en entier et te donne un résumé de chaque colonne.

Écris :
- "description_jeu" : deux phrases simples qui disent de quoi parle ce jeu de données et ce que représente une ligne.
- "colonnes" : toutes les colonnes du fichier, dans l'ordre, sans en oublier une seule. Pour chacune, une phrase correcte et naturelle qui explique simplement ce qu'elle contient. Si elle ne sert pas à l'analyse, la phrase le fait comprendre naturellement, avec la raison. Indique "gardee" : true ou false.
  Une colonne qui a un "fait_python" n'est pas gardée, et ta phrase reprend ce fait. Un "avis_python" est seulement un avis : c'est toi qui décides, selon le sens de la colonne. Ne garde pas non plus ce qui ne sert pas à comprendre le sujet : informations techniques sur le fichier, colonne qui répète ou se déduit d'une autre.
- "mesure_principale" : le nom exact de la colonne de nombres qui mesure ce dont parle le jeu de données, ou null s'il n'y en a pas.
- "unite_mesure" : l'unité de cette mesure seulement si elle est écrite dans le titre, les colonnes ou les valeurs, sinon null. Ne devine jamais une devise.

Réponds uniquement en JSON : {"description_jeu": "...", "colonnes": [{"nom": "...", "description": "...", "gardee": true}], "mesure_principale": "...", "unite_mesure": null}"""


def decrire_colonnes(profil: dict, titre: str, description: str) -> dict:
    """Atlas décrit chaque colonne ; le code a le dernier mot sur les faits sûrs et complète les oublis."""
    entree = json.dumps({"titre": titre, "description_publiee": description, **_profil_compact(profil)},
                        ensure_ascii=False, default=str)
    desc = _appeler_analyste([{"role": "system", "content": PROMPT_DESCRIPTION},
                              {"role": "user", "content": entree}], "description des colonnes")
    faits = {c["nom"]: c.get("fait_python") for c in profil["colonnes"]}
    proposees = {str(c.get("nom")): c for c in (desc.get("colonnes") or []) if isinstance(c, dict)}
    colonnes = []
    for c in profil["colonnes"]:
        nom, fait = c["nom"], faits.get(c["nom"])
        p = proposees.get(nom)
        if p and str(p.get("description") or "").strip():
            phrase = str(p["description"]).strip()
        elif fait:
            phrase = f"Cette colonne n'est pas utilisée pour l'analyse : elle est {fait}."
        else:
            phrase = "Cette colonne n'a pas pu être décrite."
        colonnes.append({"nom": nom, "description": phrase, "gardee": bool(p and p.get("gardee")) and not fait})
    mesure = desc.get("mesure_principale")
    return {
        "description_jeu": str(desc.get("description_jeu") or "").strip(),
        "colonnes": colonnes,
        "mesure_principale": mesure if mesure in faits else None,
        "unite_mesure": desc.get("unite_mesure") or None,
    }


# ─── 3 et 4. Atlas écrit les requêtes, Python les exécute ─────────────────────

PROMPT_PLAN = """Tu es Atlas, data analyst. Tu reçois la description d'un jeu de données et de ses colonnes utiles, avec un résumé calculé par Python sur tout le fichier.
Les données sont dans une table DuckDB nommée donnees.

Trouve la question phare : la question la plus importante qu'on puisse se poser sur ce fichier. Jamais sur le nombre de lignes, et sans supposer de cause.
Pour y répondre, écris une ou deux requêtes SQL (deux seulement si la question a deux parties), et pour chacune le graphique à dessiner.
Règles pour les requêtes :
- DuckDB, uniquement SELECT, sur la table donnees ; noms de colonnes exacts entre guillemets doubles ; seulement les colonnes utiles.
- Le résultat a deux colonnes : la première pour l'axe x, la seconde pour la valeur.
- Arrondis les valeurs à 2 décimales et exclus les lignes où la colonne de l'axe x est vide.
- Pour une évolution sur des dates, regroupe par mois avec strftime(colonne, '%Y-%m'). Garde toutes les périodes.
- Pour un classement de plus de 20 éléments, garde les 10 premiers et les 10 derniers.
- Pour une mesure qui ne s'additionne pas (prix, taux, moyenne, valeur par habitant), utilise la moyenne.
- Le titre d'une évolution indique la période couverte et l'unité de temps.
Pour chaque graphique : "titre" (clair pour quelqu'un qui n'est pas du domaine), "type" ("barres" ou "courbe"), "libelle_x", "libelle_y" (noms d'axes courts en français, sans format technique comme YYYY-MM), "sql".
Ajoute "pistes" : une ou deux phrases, sans chiffre, qui proposent au data analyst d'autres analyses qu'il pourrait faire lui-même.

Réponds uniquement en JSON : {"question_phare": "...", "graphiques": [{"titre": "...", "type": "...", "libelle_x": "...", "libelle_y": "...", "sql": "..."}], "pistes": ["..."]}"""

PROMPT_CORRIGER = """Ta requête SQL (DuckDB, table donnees) n'a pas pu être utilisée. Voici la raison. Corrige-la.
Réponds uniquement en JSON : {"sql": "..."}"""


def _periode_lisible(v) -> str:
    m = re.match(r"^(\d{4})-(\d{2})", str(v))
    return f"{MOIS[int(m.group(2)) - 1]} {m.group(1)}" if m else str(v)


def _probleme_resultat(res: dict, type_graphique: str) -> str | None:
    """Rend la raison pour laquelle un résultat n'est pas utilisable, sinon None."""
    if not res["ok"]:
        return res["erreur"]
    lignes = [l for l in res["lignes"] if l and l[0] is not None]
    if len(res["colonnes"]) < 2 or not lignes:
        return "Le résultat doit avoir deux colonnes (x puis la valeur) et au moins une ligne."
    if not all(isinstance(l[1], (int, float)) and not isinstance(l[1], bool) for l in lignes if l[1] is not None):
        return "La deuxième colonne du résultat doit être un nombre."
    if res["tronque"]:
        return "Le résultat dépasse 50 lignes : regroupe davantage, ou garde les 10 premiers et les 10 derniers."
    if type_graphique == "courbe" and len(lignes) > MAX_POINTS_DATES and re.match(r"^\d{4}-\d{2}-\d{2}", str(lignes[0][0])):
        return "Trop de points jour par jour : regroupe les dates par mois avec strftime(colonne, '%Y-%m')."
    return None


def executer_graphique(chemin: str, graphique: dict, colonnes_utiles: list) -> dict | None:
    """Exécute la requête d'Atlas ; en cas d'erreur, Atlas la corrige (MAX_ESSAIS au total)."""
    sql, type_graphique = str(graphique.get("sql") or ""), graphique.get("type")
    for essai in range(MAX_ESSAIS):
        res = executer_requete(chemin, sql)
        probleme = _probleme_resultat(res, type_graphique)
        if not probleme:
            graphique["sql"] = sql
            return res
        print(f"[ANALYSTE] Requête refusée (essai {essai + 1}) : {probleme}")
        if essai == MAX_ESSAIS - 1:
            break
        correction = _appeler_analyste([
            {"role": "system", "content": PROMPT_CORRIGER},
            {"role": "user", "content": json.dumps({"sql": sql, "raison": probleme, "colonnes": colonnes_utiles},
                                                   ensure_ascii=False)},
        ], f"correction {essai + 1}")
        sql = str(correction.get("sql") or "")
    return None


# ─── 5. Atlas écrit le texte, Python le contrôle ──────────────────────────────

PROMPT_MESSAGE = """Tu es Atlas, data analyst. Tu reçois la question phare d'un jeu de données et les résultats calculés par Python sur tout le fichier. Ces chiffres sont exacts.
Écris :
- "reponse" : deux ou trois phrases qui répondent directement à la question phare.
- "graphiques" : pour chaque graphique reçu, avec le même "id" : un "texte" de deux à quatre phrases qui disent ce que montre le graphique.
- "chiffres_cles" : deux ou trois chiffres importants tirés des résultats, chacun avec "titre" (court), "valeur" (le chiffre, avec l'unité si elle est donnée) et "detail" (qui ou quand).
- "noms_filtres" : pour chaque colonne de "filtres", un nom court en français qui dit ce qu'elle contient, en traduisant les noms anglais (ex. pour une colonne « sex » : « Sexe »).
- "nom_mesure" : le nom court en français de la moyenne de la mesure étudiée (ex. « Prix moyen », « Consommation moyenne »).

Règles :
- Utilise seulement les chiffres des résultats. Tu peux les écrire avec moins de décimales si c'est plus lisible, en arrondissant selon la règle : 5 et plus vers le haut. N'écris pas de zéros inutiles après la virgule, ni « environ » ou « ~ ». Ne calcule rien toi-même.
- Écris les nombres à la française : virgule pour les décimales, espace pour les milliers.
- Écris l'unité seulement si "unite_mesure" est donnée. Aucune devise ni unité qui n'est pas dans le titre ou les colonnes.
- Décris ce que montrent les chiffres, sans en donner les causes.
- Ne compare que ce qui a été calculé.
- Recopie les noms exactement comme dans les résultats, ou traduis-les fidèlement. Pour dire qui est le plus haut ou le plus bas, utilise "le_plus_haut" et "le_plus_bas" (et "debut" et "fin" pour une évolution), déjà repérés par Python.
- Jamais le nombre de lignes du fichier.

Réponds uniquement en JSON : {"reponse": "...", "graphiques": [{"id": "g1", "texte": "..."}], "chiffres_cles": [{"titre": "...", "valeur": "...", "detail": "..."}], "noms_filtres": {"colonne": "Nom lisible"}, "nom_mesure": "..."}"""

MOTS_DE_CAUSE = (r"\b(influenc\w*|impact\w*|détermin\w*|facteur\w*|à cause|en raison|reflèt\w*|refl[eè]te\w*|"
                 r"expliqu\w*|entraîn\w*|provoqu\w*|due?s? à|culturel\w*|législati\w*|coût de la vie)\b")
REMPLACEMENTS_QUESTION = {r"\bexpliquent\b": "vont de pair avec", r"\bexplique\b": "va de pair avec",
                          r"\bdéterminent\b": "vont de pair avec", r"\bdétermine\b": "va de pair avec",
                          r"\bl'influence\b": "le lien", r"\bl'impact\b": "le lien", r"\bimpact\b": "lien", r"\bfacteurs\b": "caractéristiques",
                          r"\bfacteur\b": "caractéristique", r"\binfluencent\b": "vont de pair avec",
                          r"\binfluence\b": "va de pair avec", r"\bimpactent\b": "vont de pair avec",
                          r"\bimpacte\b": "va de pair avec", r"\bQuels caractéristiques\b": "Quelles caractéristiques"}


def nombres_du_texte(texte: str) -> list:
    trouves = []
    for m in re.finditer(r"(?<![\w.])(?:[-+‑−]?\d{1,3}(?:[   ]\d{3})+(?:[.,]\d+)?|[-+‑−]?\d+(?:[.,]\d+)?)", texte):
        s = (m.group(0).replace(" ", "").replace(" ", "").replace(" ", "").replace(",", ".")
             .replace("‑", "-").replace("−", "-").lstrip("+"))
        try:
            trouves.append((m.group(0), float(s)))
        except ValueError:
            pass
    return trouves


def nombres_autorises(*sources) -> set:
    """Tous les nombres présents dans les résultats (et leurs arrondis), les seuls qu'Atlas peut écrire."""
    autorises = set()

    def parcourir(x):
        if isinstance(x, bool):
            return
        if isinstance(x, (int, float)):
            for d in (0, 1, 2):
                autorises.add(round(float(x), d)); autorises.add(round(abs(float(x)), d))
        elif isinstance(x, str):
            for _, v in nombres_du_texte(x):
                autorises.add(v)
        elif isinstance(x, dict):
            for v in x.values():
                parcourir(v)
        elif isinstance(x, (list, tuple)):
            for v in x:
                parcourir(v)
    for s in sources:
        parcourir(s)
    return autorises


def _inconnus(texte: str, autorises: set) -> list:
    return sorted({brut for brut, v in nombres_du_texte(texte)
                   if not any(abs(v - a) <= max(0.051, abs(a) * 0.0005) for a in autorises)})


def _textes(msg: dict) -> str:
    morceaux = [msg["reponse"]] + [g["texte"] for g in msg["graphiques"]]
    morceaux += [f"{k['titre']} {k['valeur']} {k['detail']}" for k in msg["chiffres_cles"]]
    return " ".join(morceaux)


def _normaliser(msg) -> dict:
    """Atlas ne renvoie pas toujours exactement la forme demandée : on la remet d'aplomb."""
    msg = msg if isinstance(msg, dict) else {}
    graphiques = [g for g in (msg.get("graphiques") or []) if isinstance(g, dict)]
    cles = [k if isinstance(k, dict) else {"titre": str(k)} for k in (msg.get("chiffres_cles") or [])]
    return {
        "reponse": str(msg.get("reponse") or ""),
        "graphiques": [{"id": str(g.get("id")), "texte": str(g.get("texte") or "")} for g in graphiques],
        "chiffres_cles": [{"titre": str(k.get("titre") or ""), "valeur": str(k.get("valeur") or ""),
                           "detail": str(k.get("detail") or "")} for k in cles][:3],
    }


def _phrase_acceptable(phrase: str, autorises: set) -> bool:
    return not _inconnus(phrase, autorises) and not re.search(MOTS_DE_CAUSE, phrase, re.I)


def neutraliser(texte: str) -> str:
    """« l'impact du nombre d'escales sur le prix » → « le lien entre le nombre d'escales et le prix »."""
    articles = {"du": "le ", "de la": "la ", "des": "les ", "de l'": "l'", "de": "", "d'": ""}
    texte = re.sub(r"\b(?:l'|un |une )?(?:impact|influence|effet)s? (du|de la|des|de l'|de|d')\s?(.+?) sur ",
                   lambda m: f"le lien entre {articles[m.group(1)]}{m.group(2)} et ", texte, flags=re.I)
    for motif, neutre in REMPLACEMENTS_QUESTION.items():
        texte = re.sub(motif, neutre, texte, flags=re.I)
    return texte


def sans_cause(textes: list[str]) -> list[str]:
    """
    Les phrases qui supposent une cause (« influence », « impact »…) sont reformulées par Atlas (petit modèle,
    un seul appel), en gardant le sens. Si la reformulation échoue, le code remplace lui-même les mots.
    """
    a_revoir = [i for i, x in enumerate(textes) if re.search(MOTS_DE_CAUSE, x, re.I)]
    if not a_revoir:
        return textes
    resultat = list(textes)
    try:
        reponse = completion_avec_secours(
            messages=[{"role": "system", "content": (
                "Reformule chaque phrase en français correct sans supposer de cause : remplace les idées d'influence, "
                "d'impact ou d'explication par « va de pair avec », « est lié à » ou « le lien entre … et … ». "
                "Garde le même sens, la même longueur et les mêmes noms. Aucun chiffre ajouté. "
                'Réponds uniquement en JSON : {"phrases": ["...", "..."]} dans le même ordre.')},
                {"role": "user", "content": json.dumps({"phrases": [textes[i] for i in a_revoir]}, ensure_ascii=False)}],
            response_format={"type": "json_object"}, temperature=0.1, max_tokens=800, timeout=30)
        contenu = reponse.choices[0].message.content or ""
        nouvelles = json.loads(contenu[contenu.find("{"): contenu.rfind("}") + 1]).get("phrases") or []
        for i, nouvelle in zip(a_revoir, nouvelles):
            chiffres_avant = {v for _, v in nombres_du_texte(textes[i])}
            if isinstance(nouvelle, str) and nouvelle.strip() and {v for _, v in nombres_du_texte(nouvelle)} <= chiffres_avant:
                resultat[i] = nouvelle.strip()
    except Exception as e:
        print(f"[ANALYSTE] Reformulation impossible : {str(e)[:150]}")
    return [neutraliser(x) if re.search(MOTS_DE_CAUSE, x, re.I) else x for x in resultat]


def _filtrer(texte: str, autorises: set) -> str:
    """Dernier filet : une phrase qui garde un nombre inventé ou une cause non prouvée est retirée."""
    phrases = re.split(r"(?<=[.!?])\s+", texte.strip())
    return " ".join(p for p in phrases if p and _phrase_acceptable(p, autorises))


def _sans_zeros_inutiles(texte: str) -> str:
    """3,00 → 3 ; 25,00 % → 25 % ; 12,50 → 12,5 ; et pas de « ~ » devant un nombre."""
    texte = re.sub(r"~\s*(?=\d)", "", texte)
    texte = re.sub(r"(\d),00(?!\d)", r"\1", texte)
    return re.sub(r"(\d,\d)0(?!\d)", r"\1", texte)


def _reperes(graphique: dict) -> dict:
    """Python repère lui-même le plus haut, le plus bas, le début et la fin : Atlas n'a qu'à les recopier."""
    lignes = [l for l in graphique["resultat"]["lignes"] if isinstance(l[1], (int, float))]
    if not lignes:
        return {}
    haut, bas = max(lignes, key=lambda l: l[1]), min(lignes, key=lambda l: l[1])
    reperes = {"le_plus_haut": haut[:2], "le_plus_bas": bas[:2]}
    if graphique["type"] == "courbe":
        reperes.update({"debut": lignes[0][:2], "fin": lignes[-1][:2]})
    return reperes


def ecrire_message(question: str, graphiques: list, unite: str | None, reference: str, filtres: list) -> dict:
    """Atlas écrit le texte ; Python refuse les chiffres inventés et les causes (2 réécritures), puis nettoie."""
    entree = json.dumps({"question_phare": question, "unite_mesure": unite, "filtres": [f["colonne"] for f in filtres],
                         "graphiques": [{"id": g["id"], "titre": g["titre"], "colonnes": g["resultat"]["colonnes"],
                                         "lignes": g["resultat"]["lignes"], **_reperes(g)} for g in graphiques]},
                        ensure_ascii=False, default=str)
    autorises = nombres_autorises([g["resultat"]["lignes"] for g in graphiques])
    messages = [{"role": "system", "content": PROMPT_MESSAGE}, {"role": "user", "content": entree}]
    brut = _appeler_analyste(messages, "texte")
    noms_filtres = brut.get("noms_filtres") if isinstance(brut.get("noms_filtres"), dict) else {}
    msg = _normaliser(brut)
    for essai in range(2):
        faux = _inconnus(_textes(msg), autorises)
        causes = sorted({m.group(0).lower() for m in re.finditer(MOTS_DE_CAUSE, _textes(msg), re.I)})
        if not faux and not causes:
            break
        print(f"[ANALYSTE] Texte refusé : nombres absents {faux}, mots de cause {causes} → Atlas réécrit")
        msg = _normaliser(_appeler_analyste(messages + [{"role": "user", "content":
            f"Ton texte a été refusé. Nombres absents des résultats : {faux}. Mots de cause interdits : {causes}. "
            "Réécris sans eux : uniquement les chiffres des résultats, et décris sans expliquer les causes."}],
            f"texte corrigé {essai + 1}"))

    def net(t):
        return retirer_devises_inventees(_sans_zeros_inutiles(_filtrer(t, autorises)), reference)
    msg["reponse"] = net(msg["reponse"])
    for g in msg["graphiques"]:
        g["texte"] = net(g["texte"])
    cles = []
    for k in msg["chiffres_cles"]:
        if not _phrase_acceptable(f"{k['valeur']} {k['detail']}", autorises):
            continue
        detail = re.sub(r",?\s*\(?\d[\d\s ]*lignes?\)?", "", k["detail"]).strip(" ,")
        cles.append({"titre": net(k["titre"]), "valeur": net(k["valeur"]), "detail": net(detail)})
    msg["chiffres_cles"] = cles
    msg["noms_filtres"] = {str(k): str(v).strip()[:40] for k, v in noms_filtres.items() if str(v).strip()}
    msg["nom_mesure"] = net(str(brut.get("nom_mesure") or "")).strip()[:40]
    return msg


# ─── Le dashboard complet ─────────────────────────────────────────────────────

def analyser_dataset(fiche: dict, chemin_propre: str) -> dict:
    """
    Construit le dashboard automatique, dans le format attendu par le site
    (comprehension, kpi, graphiques, filtres, conclusion), plus la description des colonnes.
    """
    titre, description = fiche.get("titre") or "", fiche.get("description") or ""
    print(f"\n[ANALYSTE] ── Début de l'analyse : {titre or '(sans titre)'}")
    df = pd.read_parquet(chemin_propre) if chemin_propre.endswith(".parquet") else pd.read_csv(chemin_propre)
    profil = profiler(df)
    reference = " ".join([titre, description] + [str(c) for c in df.columns])

    # 1-2. Python donne les faits, Atlas décrit et choisit les colonnes
    desc = decrire_colonnes(profil, titre, description)
    gardees = [c["nom"] for c in desc["colonnes"] if c["gardee"]]
    print(f"[ANALYSTE] Colonnes gardées par Atlas : {gardees}")
    if not gardees:
        raise ValueError("Aucune colonne utile pour une analyse.")
    utiles = [dict(c, description=next(d["description"] for d in desc["colonnes"] if d["nom"] == c["nom"]))
              for c in profil["colonnes"] if c["nom"] in gardees]

    # 3. Atlas : question phare et requêtes SQL
    plan = _appeler_analyste([
        {"role": "system", "content": PROMPT_PLAN},
        {"role": "user", "content": json.dumps({"titre": titre, "description": desc["description_jeu"],
                                                "colonnes_utiles": utiles}, ensure_ascii=False, default=str)},
    ], "question phare et requêtes")
    question = str(plan.get("question_phare") or "")
    question = sans_cause([question])[0]  # pas de cause dans la question
    print(f"[ANALYSTE] Question phare : {question}")

    # 4. Python exécute (Atlas corrige en cas d'erreur)
    graphiques = []
    for i, g in enumerate([g for g in (plan.get("graphiques") or []) if isinstance(g, dict)][:MAX_GRAPHIQUES], 1):
        res = executer_graphique(chemin_propre, g, gardees)
        if res is None:
            continue
        x, y = res["colonnes"][0], res["colonnes"][1]
        res = mettre_en_forme_resultat({**res, "lignes": [l for l in res["lignes"] if l[0] is not None]}, x, None)
        lignes = res["lignes"]
        type_graphique = "courbe" if g.get("type") == "courbe" else "barres"
        titre_g = str(g.get("titre") or question)
        if type_graphique == "courbe" and lignes:
            # La période du titre est écrite par Python d'après le résultat réel
            titre_g = re.sub(r"\s*\([^)]*\)\s*$", "", titre_g) + \
                f" ({_periode_lisible(lignes[0][0])} – {_periode_lisible(lignes[-1][0])})"
        elif len(lignes) > 8 or max((len(str(l[0])) for l in lignes), default=0) > 14:
            type_graphique = "barres_horizontales"   # beaucoup de groupes ou des noms longs
        graphiques.append({
            "id": f"g{i}", "titre": retirer_devises_inventees(titre_g, reference), "question": question,
            "type": type_graphique, "x": x, "y": y, "serie": None,
            "libelle_x": re.sub(r"\s*\((?:YYYY|AAAA|yyyy|aaaa)[^)]*\)", "", str(g.get("libelle_x") or x)).strip(),
            "libelle_y": retirer_devises_inventees(str(g.get("libelle_y") or y), reference),
            "libelle_serie": None, "effectif": None, "phrase": "", "sql": g["sql"], "resultat": res,
        })
    if not graphiques:
        raise ValueError("Aucune requête de graphique n'a réussi.")

    # Les filtres : des colonnes de groupes gardées par Atlas (2 à 15 valeurs)
    filtres = []
    for c in utiles:
        # Un filtre n'a de sens que si ses valeurs reviennent sur plusieurs lignes
        if c["type"] == "texte" and 2 <= c["valeurs_differentes"] <= 15 and c["valeurs_differentes"] <= profil["nb_lignes"] / 2:
            valeurs = _valeurs_filtre(chemin_propre, c["nom"], [])
            if valeurs:
                filtres.append({"colonne": c["nom"], "valeurs": valeurs, "libelle": c["nom"]})
        if len(filtres) == MAX_FILTRES:
            break

    # Une colonne de dates donne un filtre par mois (colonne calculée « mois », comme dans Power BI)
    colonnes_calculees = []
    date = next((c["nom"] for c in utiles if c["type"] == "date"), None)
    if date and len(filtres) < MAX_FILTRES + 1:
        calcul = {"nom": "mois", "expression": 'strftime("' + date.replace('"', '""') + '", \'%Y-%m\')',
                  "explication": f"Le mois de la colonne {date}"}
        valeurs = _valeurs_filtre(chemin_propre, "mois", [calcul]) if "mois" not in df.columns else None
        if valeurs:
            colonnes_calculees.append(calcul)
            filtres.insert(0, {"colonne": "mois", "valeurs": valeurs, "libelle": "Mois"})

    # 5. Atlas écrit le texte, Python le contrôle
    msg = ecrire_message(question, graphiques, desc["unite_mesure"], reference, filtres)
    textes = {g["id"]: g["texte"] for g in msg["graphiques"]}
    for g in graphiques:
        g["phrase"] = textes.get(g["id"], "")

    for f in filtres:
        if f["colonne"] != "mois":
            f["libelle"] = msg["noms_filtres"].get(f["colonne"], f["colonne"])

    # Un indicateur calculé par Python et recalculé à chaque filtre : la moyenne de la mesure
    kpi = []
    mesure = desc["mesure_principale"]
    if mesure in gardees and pd.api.types.is_numeric_dtype(df[mesure]):
        sql = f'SELECT ROUND(AVG("{mesure.replace(chr(34), chr(34) * 2)}"), 2) AS valeur FROM donnees'
        r = executer_requete(chemin_propre, sql, None, colonnes_calculees)
        if r["ok"] and r["lignes"] and isinstance(r["lignes"][0][0], (int, float)):
            kpi.append({"id": "k0", "titre": msg["nom_mesure"] or f"Moyenne de {mesure}", "format": "nombre",
                        "unite": desc["unite_mesure"] or "", "valeur": r["lignes"][0][0], "sql": sql,
                        "colonne": mesure, "sans_base": True})

    pistes = [p for p in (plan.get("pistes") or []) if isinstance(p, str) and p.strip() and not nombres_du_texte(p)][:2]
    pistes = [p for p in sans_cause(pistes) if not re.search(MOTS_DE_CAUSE, p, re.I)]
    dashboard = {
        "version": 2,
        "comprehension": {"question_centrale": question, "sujet": desc["description_jeu"],
                          "colonne_principale": desc["mesure_principale"]},
        "description": {"description_jeu": desc["description_jeu"], "colonnes": desc["colonnes"]},
        "colonnes_calculees": colonnes_calculees,
        # La moyenne recalculée à chaque filtre, puis les chiffres clés d'Atlas (contrôlés), avec les vrais noms
        "kpi": kpi + [{"id": f"k{i}", "titre": k["titre"], "valeur": k["valeur"], "detail": k["detail"], "texte": True}
                      for i, k in enumerate(msg["chiffres_cles"][:2 if kpi else 3], 1)],
        "graphiques": graphiques,
        "filtres": filtres,
        "conclusion": msg["reponse"],
        "pistes": pistes,
        "effectif_min": 0,
    }
    print(f"[ANALYSTE] ✓ Dashboard prêt : {len(graphiques)} graphique(s), {len(dashboard['kpi'])} chiffre(s) clé(s), "
          f"{len(filtres)} filtre(s)")
    return dashboard
