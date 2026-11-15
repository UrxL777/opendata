import os
import json
import re
import time
import pandas as pd
from openai import OpenAI
from supabase import create_client
from dotenv import load_dotenv
from modules.requetes import executer_requete

load_dotenv()

client = OpenAI(
    api_key=os.getenv("GROQ_API_KEY"),
    base_url="https://api.groq.com/openai/v1",
)

supabase = create_client(
    os.getenv("SUPABASE_URL"),
    os.getenv("SUPABASE_SERVICE_KEY"),
)

MODELE = "openai/gpt-oss-20b"               # suggestions de titre/catégorie et Atlas
MODELE_ANALYSTE = "openai/gpt-oss-120b"     # l'Analyste : un autre modèle, donc un quota Groq séparé
MODELE_SECOURS = "qwen/qwen3.8-27b"         # prend le relais si le quota du modèle principal est épuisé


def _limite_ou_indisponible(erreur: Exception) -> bool:
    """Vrai si Groq refuse à cause d'un quota épuisé, d'une demande trop grosse ou d'un modèle indisponible."""
    message = str(erreur).lower()
    return any(m in message for m in ("429", "413", "rate limit", "503", "over capacity", "model_decommissioned", "does not exist"))


def completion_avec_secours(**parametres):
    """
    Appelle le modèle principal (MODELE). Si Groq refuse parce que son quota est épuisé,
    la même demande est envoyée automatiquement au modèle de secours : l'utilisateur reçoit
    quand même une réponse, sans rien voir.
    """
    try:
        return client.chat.completions.create(model=MODELE, **parametres)
    except Exception as e:
        if not _limite_ou_indisponible(e):
            raise
        print(f"[SECOURS] Modèle principal indisponible ({str(e)[:120]}) → modèle de secours {MODELE_SECOURS}")
        reponse = client.chat.completions.create(model=MODELE_SECOURS, **parametres)
        # Certains modèles écrivent leur réflexion entre <think> et </think> : on ne garde que la réponse
        message = reponse.choices[0].message
        if message.content:
            message.content = re.sub(r"<think>.*?</think>", "", message.content, flags=re.DOTALL).strip()
        return reponse


# ─── Lecture d'un échantillon du fichier ───────────────────────────────────────

def _lire_echantillon(chemin: str, nom_fichier: str) -> str:
    """Lit début, milieu et fin du fichier pour donner un aperçu à l'agent."""
    print(f"[AGENT] _lire_echantillon : {nom_fichier} ({chemin})")
    try:
        ext = os.path.splitext(nom_fichier)[1].lower()
        if ext == ".csv":
            df = None
            for enc in ["utf-8", "latin-1", "cp1252"]:
                try:
                    df = pd.read_csv(chemin, encoding=enc, on_bad_lines="skip")
                    print(f"[AGENT] CSV lu avec encodage '{enc}'")
                    break
                except Exception:
                    continue
            if df is None:
                return "Impossible de lire le fichier CSV avec les encodages testés."
        elif ext in (".xlsx", ".xls"):
            df = pd.read_excel(chemin)
        elif ext == ".json":
            df = pd.read_json(chemin)
        else:
            print(f"[AGENT] Format non supporté : {ext}")
            return "Format non supporté pour la lecture d'échantillon."

        total = len(df)
        milieu = total // 2

        debut = df.head(10)
        centre = df.iloc[max(0, milieu - 2): milieu + 3]
        fin = df.tail(10)
        echantillon = pd.concat([debut, centre, fin]).drop_duplicates()

        resultat = (
            f"Colonnes ({len(df.columns)}) : {list(df.columns)}\n"
            f"Nombre total de lignes : {total}\n\n"
            f"Aperçu (début, milieu, fin) :\n"
            f"{echantillon.to_string(index=False, max_cols=30, max_colwidth=30)}"
        )
        print(f"[AGENT] Échantillon généré : {len(resultat)} caractères, {total} lignes, {len(df.columns)} colonnes")
        return resultat
    except Exception as e:
        print(f"[AGENT] ✗ Erreur lecture échantillon : {e}")
        return f"Impossible de lire le fichier : {e}"


# ─── Prompt système ────────────────────────────────────────────────────────────

def prompt_systeme(contexte: str) -> str:
    return f"""Tu es Atlas, l'assistant data analyst de la plateforme OpenData. Tu accompagnes les étudiants et analystes dans l'exploration de leurs données pour construire leur portfolio.

Ta personnalité :
- Tu es chaleureux, bienveillant et naturel, comme un collègue data analyst qui aide un étudiant. Tu donnes envie de continuer la conversation.
- Tu ne fais PAS de nouvelle analyse à la place de l'utilisateur : tu expliques, tu conseilles et tu orientes. En revanche, tu expliques volontiers le dashboard automatique décrit dans le contexte, comme l'analyste qui l'a construit.
- Tu réponds dans la langue de l'utilisateur (français par défaut) et tu le TUTOIES toujours, jamais de « vous ».

Comment réagir selon la situation :
- Salutation (bonjour, salut, coucou…) : tu salues chaleureusement, puis tu proposes 3 exemples de questions adaptées à CE jeu de données. Tu ne te présentes pas. Pas de code, pas de méthode.
  Exemple : « Salut ! Content de t'aider à explorer ce jeu de données. Tu peux par exemple me demander : … » suivi de 3 questions en liste.
- Question sur toi (qui es-tu, que fais-tu…) : seulement dans ce cas, tu te présentes : tu es Atlas, l'assistant d'OpenData qui aide à comprendre et analyser les jeux de données de la plateforme.
- Remerciement ou message court (merci, ok, d'accord…) : tu réponds simplement et poliment, en une phrase, et tu proposes de continuer. Pas de code.
- Question sur le dashboard, un graphique, un indicateur ou un facteur (« que montre le graphique 2 ? », « pourquoi les fumeurs paient plus ? », « quel facteur compte le plus ? ») : tu réponds avec les VRAIS chiffres du dashboard donnés dans le contexte, en langage simple. Tu expliques ce que montre le graphique, ce qu'il faut en retenir, et sa limite éventuelle (un groupe de moins de 30 lignes est peu fiable ; un lien entre deux colonnes ne prouve pas une cause). Les graphiques sont numérotés dans l'ordre d'affichage (graphique 1, graphique 2…). Si la réponse n'est pas dans le dashboard, dis-le honnêtement et propose comment la trouver. Pas de code, sauf si on te le demande.
- Demande d'autres questions à explorer (« quelles autres questions peut-on se poser ? », « que peut-on analyser d'autre ? ») : tu proposes 3 à 5 questions d'analyse DIFFÉRENTES de la question centrale du dashboard, réalisables avec les colonnes de ce jeu de données. Pour chacune, en une ou deux lignes : les colonnes à utiliser, le calcul à faire (moyenne par groupe, comptage, évolution par mois…) et le graphique adapté. Tu ne donnes AUCUN chiffre pour ces nouvelles questions : tu ne les as pas calculées, seul le dashboard contient des chiffres vérifiés. Pas de code, sauf si on te le demande.
- Question sur les données ou sur une analyse : tu réponds d'abord en une ou deux phrases simples, en langage naturel, qui répondent directement à la question (quelle méthode et pourquoi). Ensuite seulement, tu proposes : « Veux-tu que je te montre comment le faire en Python ? »
- Demande de code, ou réponse positive à ta proposition (oui, vas-y, montre-moi…) : tu donnes le code.
- Demande d'explication (je ne comprends pas, explique…) : tu expliques avec des mots simples, pas à pas, sans redonner tout le code.
- Utilisateur perdu ou hésitant : tu lui proposes 2 ou 3 pistes simples parmi lesquelles choisir.
- Question sans rapport avec la data ou ce jeu de données : tu expliques gentiment que tu es Atlas, l'assistant d'OpenData, là pour aider à comprendre et analyser ce jeu de données, et que tu n'es pas là pour d'autres sujets. Puis tu proposes une question sur le jeu de données.

Règles importantes :
- Tu ne donnes JAMAIS de code de toi-même : uniquement si l'utilisateur le demande ou accepte ta proposition.
- Tu n'as accès à AUCUN outil et tu n'exécutes jamais de code : tu écris toujours le code directement dans ta réponse.
- Quand tu donnes du code, il est court, commenté en français, et suivi d'une phrase qui explique ce qu'il produit.
- Dans le code, utilise EXACTEMENT les noms de colonnes listés dans « Noms exacts des colonnes » du contexte (par exemple `Rain`, `Humidity`), sans les traduire ni les inventer. Si une colonne contient du texte (par exemple « rain » / « no rain »), convertis-la en nombres avant de calculer (par exemple rain → 1, no rain → 0). Ne traduis JAMAIS les identifiants dans le code.
- Tu termines par UNE seule question courte pour relancer la conversation. Ta proposition de code compte comme cette question : dans ce cas, n'en pose pas d'autre.
- Tu adaptes la longueur à la question : une question simple appelle une réponse courte. Ne sur-explique jamais.
- N'invente jamais une devise ou une unité : utilise-la seulement si elle est écrite dans le titre, la description ou le nom d'une colonne. Sinon, écris le nombre seul (« 32 050 » et non « 32 050 € »).
- Ne laisse JAMAIS une réponse vide.

Mise en forme :
- Tu utilises le Markdown avec modération : listes à puces, gras, et blocs de code uniquement pour du code.
- N'utilise JAMAIS de tableaux Markdown, sauf si l'utilisateur demande explicitement un « tableau » ou une « table ».
- N'utilise JAMAIS de traits horizontaux (---), de séparateurs visuels, ni d'emojis (aucun emoji, y compris 🎯 ou 1️⃣).
- Pour présenter les chiffres d'un graphique, utilise une courte liste à puces, pas un tableau (sauf si l'utilisateur demande un tableau).

Contexte du jeu de données :
{contexte}"""


# ─── Construction du contexte à partir de la base ─────────────────────────────

def texte_dashboard(dashboard: dict) -> str:
    """Résume le dashboard de l'Analyste en texte, pour le contexte d'Atlas (avec les vrais chiffres)."""
    c = dashboard.get("comprehension") or {}
    lignes = [
        "DASHBOARD AUTOMATIQUE (c'est toi, Atlas, qui l'as construit dans ton rôle d'analyste ; tous les chiffres viennent de calculs sur le fichier complet) :",
        f"- Sujet : {c.get('sujet', '')} Une ligne = {c.get('une_ligne_represente', '')}.",
        f"- Question centrale : {c.get('question_centrale', '')}",
        f"- Colonne principale étudiée : {c.get('colonne_principale', '')}",
    ]
    for col in dashboard.get("colonnes_calculees") or []:
        lignes.append(f"- Colonne calculée « {col['nom']} » : {col.get('explication', '')}")
    if dashboard.get("classement_facteurs"):
        lignes.append("- Classement des facteurs (écart de la colonne principale entre le groupe le plus haut et le plus bas) : " + " ; ".join(
            f"{f['facteur']} = {f['ecart']} (le plus haut : {f['groupe_le_plus_haut']} {f['valeur_haute']}, le plus bas : {f['groupe_le_plus_bas']} {f['valeur_basse']})"
            + ("" if f.get("important") else ", peu important")
            for f in dashboard["classement_facteurs"]))
    for k in dashboard.get("kpi") or []:
        lignes.append(f"- Indicateur « {k['titre']} » : {k['valeur']} {k.get('unite', '')}".rstrip())
    for i, g in enumerate(dashboard.get("graphiques") or [], 1):
        res = g.get("resultat") or {}
        donnees = "; ".join(
            ", ".join(f"{nom}={val}" for nom, val in zip(res.get("colonnes", []), ligne))
            for ligne in (res.get("lignes") or [])[:20])
        lignes.append(f"- Graphique {i} « {g['titre']} » ({g['type']}) : répond à « {g.get('question', '')} ». "
                      f"Données : {donnees}. Conclusion affichée : {g.get('phrase', '')}")
    if dashboard.get("filtres"):
        lignes.append("- Filtres disponibles : " + ", ".join(f["colonne"] for f in dashboard["filtres"]))
    if dashboard.get("conclusion"):
        lignes.append(f"- Conclusion générale : {dashboard['conclusion']}")
    return "\n".join(lignes)


def construire_contexte(jeu_id: str) -> str:
    """Récupère les infos du jeu de données et le rapport d'analyse depuis Supabase."""
    print(f"[AGENT] construire_contexte : jeu_id={jeu_id}")
    try:
        rep_jeu = supabase.table("jeux_de_donnees") \
            .select("titre, description, fichiers(id, nom_fichier)") \
            .eq("id", jeu_id) \
            .maybe_single() \
            .execute()

        if not rep_jeu or not rep_jeu.data:
            print(f"[AGENT] ✗ Aucun jeu de données trouvé pour id={jeu_id}")
            return "Aucune information disponible sur ce jeu de données."

        jeu = rep_jeu.data
        fichiers = jeu.get("fichiers") or []
        if isinstance(fichiers, dict):
            fichiers = [fichiers]

        print(f"[AGENT] Jeu trouvé : '{jeu.get('titre')}' | {len(fichiers)} fichier(s)")

        rapport = {}
        apercu = []
        try:
            # Le rapport est rangé sous le numéro du JEU de données (voir main.py) ;
            # les anciens rapports pouvaient l'être sous le numéro du fichier.
            identifiants = [jeu_id] + ([fichiers[0]["id"]] if fichiers else [])
            for identifiant in identifiants:
                rep_analyse = supabase.table("analyses") \
                    .select("resultats") \
                    .eq("fichier_id", identifiant) \
                    .eq("statut", "termine") \
                    .maybe_single() \
                    .execute()
                if rep_analyse is not None and rep_analyse.data:
                    resultats = rep_analyse.data.get("resultats", {})
                    # Les colonnes, les dimensions et la qualité sont dans l'inspection
                    rapport = resultats.get("inspection") or resultats.get("rapport", {})
                    apercu = resultats.get("apercu", [])
                    print(f"[AGENT] Rapport trouvé : {rapport.get('nb_lignes')} lignes × {rapport.get('nb_colonnes')} colonnes | {len(apercu)} lignes d'aperçu")
                    break
            else:
                print(f"[AGENT] Aucun rapport d'analyse disponible")
        except Exception as e:
            print(f"[AGENT] ✗ Erreur récupération analyse : {e}")

        # Le dashboard automatique de l'Analyste, pour qu'Atlas puisse l'expliquer
        texte_dash = ""
        try:
            rep_dash = supabase.table("dashboards") \
                .select("statut, contenu") \
                .eq("jeu_de_donnees_id", jeu_id) \
                .maybe_single() \
                .execute()
            if rep_dash is not None and rep_dash.data:
                if rep_dash.data.get("statut") == "termine" and rep_dash.data.get("contenu"):
                    texte_dash = texte_dashboard(rep_dash.data["contenu"])
                elif rep_dash.data.get("statut") == "en_cours":
                    texte_dash = "Le dashboard automatique de ce jeu de données est en cours de préparation."
        except Exception as e:
            print(f"[AGENT] ✗ Erreur récupération dashboard : {e}")

        lignes = [
            f"Jeu de données : {jeu.get('titre', 'Sans titre')}",
            f"Description : {jeu.get('description', 'Aucune description.')}",
        ]

        if fichiers:
            noms = [f["nom_fichier"] for f in fichiers]
            lignes.append(f"Fichiers : {', '.join(noms)}")

        if rapport:
            nb_lignes = rapport.get("nb_lignes", "?")
            nb_colonnes = rapport.get("nb_colonnes", "?")
            lignes.append(f"Dimensions : {nb_lignes} lignes × {nb_colonnes} colonnes")

            colonnes_info = rapport.get("colonnes", [])
            if colonnes_info:
                noms_col = [str(c["nom"]) for c in colonnes_info]
                lignes.append(f"Noms exacts des colonnes (à utiliser tels quels dans le code) : {', '.join(noms_col)}")
                lignes.append("Détail des colonnes : " + ", ".join(
                    f"{c['nom']} ({c.get('nb_valeurs_uniques', '?')} valeurs différentes)" for c in colonnes_info))

            qualite = rapport.get("qualite", {})
            if qualite:
                pct = qualite.get("pct_manquants_global", 0)
                doublons = qualite.get("nb_doublons", 0)
                lignes.append(f"Qualité : {pct}% de valeurs manquantes, {doublons} doublons")

        if apercu:
            lignes.append(
                f"\nAperçu des premières lignes :\n"
                f"{json.dumps(apercu, ensure_ascii=False, indent=2)}"
            )

        if texte_dash:
            lignes.append("\n" + texte_dash)

        contexte = "\n".join(lignes)
        print(f"[AGENT] Contexte construit ({len(contexte)} chars)")
        return contexte

    except Exception as e:
        print(f"[AGENT] ✗ ERREUR construire_contexte : {e}")
        return f"Erreur lors de la récupération du contexte : {e}"


# ─── Suggestion de titre, description et catégorie (appelée à l'upload) ────────

def suggerer(chemin: str, nom_fichier: str) -> dict:
    """Suggère un titre, une description et une catégorie pour un jeu de données."""
    print(f"\n[SUGGERER-AGENT] ── fichier={nom_fichier}")

    # Récupérer les catégories disponibles depuis Supabase
    categories = []
    try:
        recup_cat = supabase.table("categories").select("id, nom").execute()
        categories = recup_cat.data or []
        print(f"[SUGGERER-AGENT] {len(categories)} catégories disponibles : {[c['nom'] for c in categories]}")
    except Exception as e:
        print(f"[SUGGERER-AGENT] ✗ Erreur récupération catégories : {e}")

    echantillon = _lire_echantillon(chemin, nom_fichier)
    echantillon_court = echantillon[:1000]
    print(f"[SUGGERER-AGENT] Échantillon envoyé ({len(echantillon_court)} chars)")

    liste_cats = "\n".join([f"- id {c['id']} : {c['nom']}" for c in categories])

    try:
        reponse = completion_avec_secours(
            messages=[
                {
                    "role": "system",
                    "content": (
                        "Tu es un expert en données ouvertes. "
                        "À partir d'un aperçu de fichier et d'une liste de catégories, "
                        "réponds UNIQUEMENT avec un objet JSON contenant exactement trois clés : "
                        "'titre' (string court et descriptif), "
                        "'description' (2 phrases max résumant le contenu), "
                        "'categorie_id' (entier, l'id de la catégorie existante la plus adaptée) "
                        "OU 'nouvelle_categorie' (string, un nom de catégorie court et précis) "
                        "si et seulement si AUCUNE catégorie existante ne correspond au contenu du fichier. "
                        "N'utilise 'nouvelle_categorie' qu'en dernier recours absolu. "
                        "Aucun texte avant ou après le JSON. "
                        "Le titre, la description et la nouvelle catégorie doivent TOUJOURS être rédigés en français."
                    ),
                },
                {
                    "role": "user",
                    "content": (
                        f"Fichier : '{nom_fichier}'\n\n"
                        f"Catégories disponibles :\n{liste_cats}\n\n"
                        f"Aperçu du fichier :\n{echantillon_court}"
                    ),
                },
            ],
            max_tokens=600,
        )

        contenu = reponse.choices[0].message.content.strip()
        print(f"[SUGGERER-AGENT] Réponse brute du modèle : {contenu}")

        match = re.search(r'\{.*\}', contenu, re.DOTALL)
        if not match:
            print(f"[SUGGERER-AGENT] ✗ Aucun JSON trouvé, fallback")
            return {"titre": nom_fichier, "description": "Aucune description générée.", "categorie_id": None}

        resultat = json.loads(match.group())
        print(f"[SUGGERER-AGENT] ✓ JSON extrait : {resultat}")

        # Si le modèle a proposé une nouvelle catégorie, on l'insère dans Supabase
        if "nouvelle_categorie" in resultat and resultat["nouvelle_categorie"]:
            nom_nouvelle_cat = resultat["nouvelle_categorie"].strip()
            print(f"[SUGGERER-AGENT] Nouvelle catégorie proposée : '{nom_nouvelle_cat}'")

            # Vérifier qu'elle n'existe pas déjà (sécurité doublon)
            existante = next((c for c in categories if c["nom"].lower() == nom_nouvelle_cat.lower()), None)
            if existante:
                print(f"[SUGGERER-AGENT] Catégorie déjà existante, utilisation de l'id {existante['id']}")
                resultat["categorie_id"] = existante["id"]
            else:
                rep_insert = supabase.table("categories").insert({"nom": nom_nouvelle_cat}).execute()
                if rep_insert.data:
                    nouvel_id = rep_insert.data[0]["id"]
                    print(f"[SUGGERER-AGENT] ✓ Nouvelle catégorie créée : id={nouvel_id}")
                    resultat["categorie_id"] = nouvel_id
                else:
                    print(f"[SUGGERER-AGENT] ✗ Échec insertion catégorie")
                    resultat["categorie_id"] = None

            del resultat["nouvelle_categorie"]

        return resultat

    except Exception as e:
        print(f"[SUGGERER-AGENT] ✗ ERREUR appel modèle : {e}")
        raise


# ═══════════════════════════════════════════════════════════════════════════════
#  L'ANALYSTE : création automatique d'un dashboard pour chaque jeu de données
#  Le modèle ne voit jamais les données : il lit la fiche d'identité, écrit du SQL,
#  le serveur l'exécute (modules/requetes.py) et lui rend seulement les résultats.
# ═══════════════════════════════════════════════════════════════════════════════

MAX_KPI = 4             # indicateurs clés au maximum
MAX_GRAPHIQUES = 6      # graphiques au maximum
MAX_FILTRES = 4         # filtres au maximum
MAX_ESSAIS = 3          # essais pour corriger une requête qui échoue
EFFECTIF_MIN = 30       # en dessous, un groupe est trop petit pour être fiable


def effectif_minimum(nb_lignes: int) -> int:
    """Taille minimale d'un groupe fiable : 30, ou moins pour un petit fichier (un dixième des lignes, au moins 2)."""
    return min(EFFECTIF_MIN, max(2, nb_lignes // 10))
SEUIL_IMPORTANCE = 0.15 # un facteur est important si son écart vaut au moins 15 % de celui du premier
MAX_TOKENS_REPONSE = 3500  # tokens réservés pour chaque réponse (l'offre gratuite de Groq limite à 8 000 par minute)


def _reduire_fiche(fiche: dict, niveau: int, avec_exemples: bool) -> dict:
    """
    Réduit la fiche par paliers :
    1 : 6 valeurs fréquentes, 2 exemples, 5 lignes d'exemple ;  2 : 3 valeurs fréquentes, 2 lignes d'exemple ;
    3 : l'essentiel de chaque colonne (nom, type, rôle, min, max) ;  4 : en plus, 40 colonnes au maximum.
    """
    essentiel = ("nom", "type", "role", "nb_manquants", "pct_manquants", "nb_valeurs_differentes", "min", "max", "premiere_date", "derniere_date")
    colonnes = []
    for c in fiche["colonnes"]:
        if niveau >= 3:
            petite = {k: v for k, v in c.items() if k in essentiel}
        else:
            petite = {k: v for k, v in c.items() if k not in ("valeurs_frequentes", "exemples", "ecart_type")}
            if c.get("valeurs_frequentes"):
                petite["valeurs_frequentes"] = c["valeurs_frequentes"][:6 if niveau == 1 else 3]
            if c.get("exemples") and avec_exemples and niveau == 1:
                petite["exemples"] = [str(e)[:40] for e in c["exemples"][:2]]
        colonnes.append(petite)
    if niveau >= 4 and len(colonnes) > 40:
        # On garde d'abord les colonnes utiles à l'analyse (mesures, catégories, dates)
        utiles = [c for c in colonnes if c.get("role") in ("quantitative", "categorielle", "date")]
        autres = [c for c in colonnes if c not in utiles]
        colonnes = (utiles + autres)[:40]
    compacte = {k: fiche[k] for k in ("titre", "description", "nb_lignes", "nb_colonnes", "table_sql") if k in fiche}
    compacte["colonnes"] = colonnes
    if len(colonnes) < len(fiche["colonnes"]):
        compacte["remarque"] = f"Seules {len(colonnes)} colonnes sur {len(fiche['colonnes'])} sont décrites (fichier très large)."
    if avec_exemples and niveau <= 2:
        compacte["lignes_exemple"] = [
            {k: (str(v)[:40] if isinstance(v, str) else v) for k, v in ligne.items()}
            for ligne in fiche.get("lignes_exemple", [])[:5 if niveau == 1 else 2]
        ]
    return compacte


def fiche_compacte(fiche: dict, avec_exemples: bool = True, budget_tokens: int = 3000) -> dict:
    """
    Version allégée de la fiche, pour rester sous la limite de tokens de Groq (8 000 par minute),
    même pour un fichier qui a des dizaines de colonnes : on réduit par paliers jusqu'à tenir dans le budget.
    """
    for niveau in (1, 2, 3, 4):
        compacte = _reduire_fiche(fiche, niveau, avec_exemples)
        if len(json.dumps(compacte, ensure_ascii=False)) / 3.5 <= budget_tokens:
            break
    return compacte


# ─── Atlas décide du traitement des cases vides (au moment du nettoyage) ───────

PROMPT_MANQUANTS = """Tu es Atlas, l'assistant data analyst de la plateforme OpenData. Un jeu de données vient d'être publié. Il va servir à construire un dashboard descriptif (moyennes, comparaisons entre groupes, évolutions), pas à entraîner un modèle de machine learning.
Tu reçois sa fiche d'identité (colonnes, rôles, nombre de cases vides "nb_manquants" et leur pourcentage "pct_manquants", statistiques, exemples). Tu ne vois pas les données elles-mêmes. Les rôles ont été devinés par un programme qui ne comprend pas le sens des colonnes : toi, tu le comprends.

MISSION 1 : VÉRIFIER LES RÔLES.
Rôles possibles : "quantitative" (des nombres qu'on peut additionner ou moyenner : prix, âge, température), "categorielle" (des groupes : compagnie, région, oui/non, nombre d'escales), "date", "identifiant" (un numéro ou un code unique par ligne, ou un code qu'on ne calcule jamais : code postal, numéro de client), "texte_libre" (phrases, commentaires, ou valeurs presque toutes différentes qui ne forment pas de groupes).
Ne corrige que les rôles vraiment faux (ex. un code postal classé "quantitative" → "identifiant" ; des notes de 1 à 5 classées "quantitative" restent "quantitative"). Si tous les rôles sont justes, "roles_corriges" est vide.

MISSION 2 : LES CASES VIDES.
Pour CHAQUE colonne dont "nb_manquants" est supérieur à 0 (même une seule case vide), choisis ce qu'il faut faire de ses cases vides, comme un data analyst expérimenté qui comprend le sens de la colonne.
Tu choisis UNIQUEMENT parmi ces 4 actions :
- "laisser_vide" : on ne devine pas. Les cases vides ne comptent pas dans les calculs. C'est le choix par défaut, le plus honnête pour un dashboard.
- "mediane" : remplir avec la médiane (une colonne de nombres seulement).
- "moyenne" : remplir avec la moyenne (une colonne de nombres seulement, sans valeurs extrêmes).
- "mode" : remplir avec la valeur la plus fréquente.

Pour bien juger :
- Remplir une case, c'est inventer une valeur. Fais-le seulement si c'est sans risque pour l'analyse : très peu de cases vides ET une valeur de remplacement très probable (ex. 1 % de vides dans une colonne où presque toutes les lignes ont la même valeur).
- Si deviner la valeur fausserait les comptes ou les comparaisons (ex. attribuer une compagnie, une région, un sexe, un prix à une ligne qui n'en a pas), choisis "laisser_vide".
- Identifie aussi la "colonne_principale" : la colonne que l'on cherche à expliquer (prix, frais, ventes, note…). On ne remplit jamais ses cases vides.
- "raison" : une phrase courte en français, compréhensible par quelqu'un qui n'est pas data analyst, qui explique ton choix à partir du sens de CETTE colonne (ex. « On ne peut pas deviner la compagnie d'un vol : la remplir fausserait le nombre de vols par compagnie. »). Jamais la même phrase générale pour toutes les colonnes.

Réponds UNIQUEMENT avec ce JSON (les noms de colonnes écrits exactement comme dans la fiche) :
{"roles_corriges": {"nom exact": {"role": "identifiant", "raison": "..."}}, "colonne_principale": "nom exact", "colonnes": {"nom exact": {"action": "laisser_vide", "raison": "..."}}}"""


def choisir_traitement_manquants(fiche: dict) -> dict:
    """
    Atlas lit la fiche d'identité et, en un seul appel : corrige les rôles faux, et choisit pour chaque colonne
    qui a des cases vides une action du menu (laisser_vide, mediane, moyenne, mode).
    Le nettoyeur vérifie ces choix avant de les appliquer.
    Un seul appel au modèle ; la fiche a la même taille quel que soit le nombre de lignes du fichier.
    """
    avec_vides = [c["nom"] for c in fiche["colonnes"] if c.get("nb_manquants", 0) > 0]
    print(f"[NETTOYAGE] Atlas décide pour {len(avec_vides)} colonne(s) avec des cases vides : {avec_vides}")
    reponse = completion_avec_secours(
        messages=[
            {"role": "system", "content": PROMPT_MANQUANTS},
            {"role": "user", "content": json.dumps(fiche_compacte(fiche, budget_tokens=2500), ensure_ascii=False)},
        ],
        response_format={"type": "json_object"},
        temperature=0.1,
        max_tokens=2000,
        timeout=40,
    )
    texte = reponse.choices[0].message.content or ""
    debut, fin = texte.find("{"), texte.rfind("}")
    decision = json.loads(texte[debut:fin + 1])
    if not isinstance(decision, dict):
        raise ValueError("Réponse d'Atlas illisible.")
    if not isinstance(decision.get("colonnes"), dict):
        decision["colonnes"] = {}
    if getattr(reponse, "usage", None):
        print(f"[NETTOYAGE] Tokens utilisés : {reponse.usage.total_tokens}")
    return decision


TYPES_GRAPHIQUES ={"barres", "barres_horizontales", "barres_groupees", "courbe", "camembert"}

PROMPT_ANALYSTE_ROLE = """Tu es Atlas, l'assistant data analyst de la plateforme OpenData, dans ton rôle d'analyste : tu construis automatiquement un dashboard pour chaque jeu de données publié, comme un data analyst expérimenté.
Tu ne vois jamais les données elles-mêmes : tu reçois leur fiche d'identité (colonnes, rôles, statistiques, lignes d'exemple). Tu écris des requêtes SQL (DuckDB) que le serveur exécute sur le fichier complet, puis tu interprètes les résultats.

Règles générales :
- Tu réponds UNIQUEMENT avec un objet JSON valide, sans aucun texte avant ou après.
- Tous les textes (titres, phrases) sont en français, courts, compréhensibles par quelqu'un qui n'est pas data analyst.
- Tu n'inventes jamais de colonne ni de chiffre."""

PROMPT_COMPRENDRE = PROMPT_ANALYSTE_ROLE + """

ÉTAPE 1 : COMPRENDRE LE JEU DE DONNÉES.
À partir de la fiche, détermine :
1. "sujet" : de quoi parle le jeu de données, en une phrase.
2. "une_ligne_represente" : ce que représente une ligne (un assuré, une vente, un jour de météo…).
3. "colonne_principale" : la colonne que l'on cherche à expliquer, celle qui intéresse le plus un décideur (frais, ventes, note, prix, résultat…). C'est le nom EXACT d'une colonne de la fiche. De préférence une colonne quantitative ; s'il n'y en a aucune de pertinente, une colonne catégorielle (ex. la couleur choisie, la présence de pluie).
4. "valeur_cible" : seulement si la colonne principale est catégorielle, la valeur qui intéresse le plus, écrite exactement comme dans la fiche (ex. "rain", "oui"). Sinon null.
5. "question_centrale" : LA question à laquelle le dashboard va répondre (ex. « Qu'est-ce qui fait varier les frais d'assurance ? »).
6. "colonnes_calculees" : comme les colonnes calculées de Power BI, pour regrouper en catégories lisibles :
   - Chaque colonne quantitative qui peut expliquer la colonne principale (âge, IMC, revenu, température…) est transformée en 3 à 6 tranches lisibles. Si une norme officielle existe, utilise-la (ex. IMC selon l'OMS : moins de 18.5 Sous-poids, moins de 25 Poids normal, moins de 30 Surpoids, sinon Obésité). Sinon, des tranches simples qui s'appuient sur le min et le max de la fiche (ex. âge : 18-25, 26-40, 41-55, 56-64).
   - Une colonne catégorielle qui a des groupes rares (moins de 30 lignes : regarde les pourcentages de la fiche et le nombre de lignes) est regroupée (ex. enfants : 0, 1, 2, « 3 et plus » ; ou « Autres » pour les valeurs rares).
   - Une colonne date peut donner une colonne de période : strftime("date", '%Y-%m') pour le mois, ou CAST(year("date") AS VARCHAR) pour l'année.
   - Format : {"nom": "categorie_imc", "expression": "CASE WHEN \\"bmi\\" < 18.5 THEN '1. Sous-poids' WHEN \\"bmi\\" < 25 THEN '2. Poids normal' WHEN \\"bmi\\" < 30 THEN '3. Surpoids' ELSE '4. Obésité' END", "explication": "Catégories d'IMC selon l'OMS"}
   - "nom" : lettres sans accent, chiffres et _ uniquement (ex. categorie_age), différent des colonnes existantes. "expression" : une formule SQL DuckDB (CASE WHEN, strftime, year…), sans SELECT ni FROM. Les noms de colonnes entre guillemets doubles.
   - Les libellés des tranches doivent se trier dans le bon ordre (ex. '18-25', '26-40' ou '1. Sous-poids', '2. Poids normal').
7. "facteurs" : la liste des colonnes qui peuvent expliquer la colonne principale (colonnes catégorielles existantes ou colonnes calculées). Chaque facteur a entre 2 et 15 groupes. N'y mets pas les identifiants, le texte libre, les coordonnées géographiques (latitude, longitude), ni la colonne principale, ni une colonne calculée à partir de la colonne principale (une colonne ne s'explique pas par elle-même). Pour une colonne quantitative, mets sa version en tranches. Ne mets jamais à la fois une colonne et sa version calculée : choisis la plus lisible.
   Un facteur est une CARACTÉRISTIQUE (quoi, qui, où, quand : type de produit, catégorie, lieu, période, profil…), jamais une autre mesure du même phénomène (ex. pour expliquer les ventes au détail, n'utilise pas les ventes en entrepôt ni les transferts : ce sont d'autres mesures de la même activité).
   Si le fichier a une colonne par année ou par période (ex. colonnes 2010, 2011, 2012…), c'est un format « large » : la question centrale porte sur l'évolution dans le temps et sur les écarts entre groupes (continent, catégorie…) ; une année n'explique jamais une autre année.

Réponds avec ce JSON :
{"sujet": "...", "une_ligne_represente": "...", "colonne_principale": "...", "valeur_cible": null, "question_centrale": "...", "colonnes_calculees": [...], "facteurs": ["...", "..."]}"""

PROMPT_QUESTIONNER = PROMPT_ANALYSTE_ROLE + """

ÉTAPE 2 : CHOISIR LES CALCULS DU DASHBOARD.
Tu reçois ta compréhension du jeu de données, tes colonnes calculées, la fiche, et le CLASSEMENT DES FACTEURS calculé par le serveur sur tout le fichier : pour chaque facteur, l'écart de la colonne principale entre le groupe le plus haut et le plus bas. Plus l'écart est grand, plus le facteur compte. Le champ "important" vaut true pour les facteurs qui comptent vraiment : ce sont les SEULS facteurs à étudier dans les graphiques.

Construis un dashboard COHÉRENT qui répond à la question centrale. Les graphiques ne sont pas indépendants : ils racontent une histoire, du général au détail, et aident à prendre une décision.
- "kpi" : 2 à 4 indicateurs clés (ex. nombre total, moyenne de la colonne principale, part d'un groupe important). Chaque KPI : {"titre": "...", "colonne": "nom exact de la colonne mesurée (ex. la colonne principale pour une moyenne), ou null si le KPI compte simplement des lignes", "sql": "requête qui rend UNE seule ligne et UNE seule valeur"}.
- "graphiques" : 3 à 6 graphiques au maximum, par ordre d'importance :
  1. le facteur le plus important (la colonne principale comparée entre ses groupes) ;
  2. les autres facteurs marqués "important": true, un graphique chacun ;
  3. au moins un CROISEMENT des deux facteurs les plus importants (ex. frais par tranche d'âge, une série pour les fumeurs et une pour les non-fumeurs) : c'est souvent là que se trouve le vrai message ;
  4. s'il y a une colonne de période : l'évolution dans le temps ;
  5. éventuellement la répartition de la colonne principale (par tranches).
  JAMAIS de graphique sur un facteur marqué "important": false, même pour remplir.
  Chaque graphique : {"id": "g1", "question": "...", "pourquoi": "...", "famille": "comparaison" | "croisement" | "evolution" | "repartition" | "composition" | "classement" | "relation", "sql": "..."}.
- Les filtres du dashboard sont choisis par le serveur (les facteurs importants) : tu n'as pas à les donner.

Règles SQL (DuckDB) :
- Une seule table : donnees. Elle contient les colonnes de la fiche ET tes colonnes calculées (utilise-les directement par leur nom).
- Noms de colonnes entre guillemets doubles, exactement comme dans la fiche (ex. "Wind_Speed").
- Une seule requête SELECT (ou WITH) par graphique ou KPI, sans point-virgule.
- Toujours résumer (GROUP BY, AVG, SUM, COUNT) : au maximum 50 lignes de résultat. Les dates sont regroupées par mois ou par année.
- Pour chaque groupe, ajoute TOUJOURS une colonne nb = COUNT(*).
- Arrondis : ROUND(..., 0) pour les montants, ROUND(..., 1) pour les pourcentages et les petites valeurs.
- Trie les résultats de façon lisible (ordre des tranches, ou du plus grand au plus petit).
- Pour un croisement : une ligne par combinaison, avec le facteur 1, le facteur 2, la valeur et nb. Le facteur 2 (celui des séries) a au plus 5 groupes : choisis un facteur qui a peu de groupes, ou une version regroupée.
- Si la colonne principale est catégorielle, la valeur étudiée est le pourcentage de la valeur cible : ROUND(100.0 * AVG(CASE WHEN "colonne" = 'valeur' THEN 1 ELSE 0 END), 1) AS pct_valeur.
- Ne parle jamais du fichier lui-même (lignes supprimées, valeurs manquantes) : c'est le rôle du rapport de nettoyage.

Réponds avec ce JSON :
{"kpi": [...], "graphiques": [...]}"""

PROMPT_CORRIGER = """Certaines requêtes ont échoué lors de l'exécution. Voici les erreurs renvoyées par DuckDB.
Réécris UNIQUEMENT les requêtes concernées en corrigeant l'erreur (vérifie les noms exacts des colonnes et la syntaxe DuckDB).
Réponds avec ce JSON : {"corrections": [{"id": "...", "sql": "..."}]}. Si une requête ne peut pas être corrigée, ne la mets pas."""

PROMPT_PRESENTER = PROMPT_ANALYSTE_ROLE + """

ÉTAPE 3 : PRÉSENTER LE DASHBOARD.
Tu reçois les résultats RÉELS de tes calculs (colonnes et lignes). Pour chacun, décide comment l'afficher et écris la conclusion.
- UNITÉS ET DEVISES : n'invente jamais une devise ou une unité. Utilise-la seulement si elle est écrite dans le titre, la description ou le nom d'une colonne (ex. « charges en dollars », « prix_eur »). Sinon, n'écris aucune devise : « 32 050 » et non « 32 050 € ».
- "kpi" : pour chaque KPI (même id) : {"id": "k1", "titre": "titre court", "format": "nombre" | "monnaie" | "pourcentage", "unite": "unité certaine, ou chaîne vide"}.
- "graphiques" : pour chaque graphique (même id) : {"id": "g1", "titre": "titre court", "type": "barres" | "barres_horizontales" | "barres_groupees" | "courbe" | "camembert", "x": "...", "y": "...", "serie": "..." ou null, "libelle_x": "...", "libelle_y": "...", "libelle_serie": "..." ou null, "phrase": "..."}.
  - "x" : la colonne du résultat pour l'axe horizontal (ou les catégories) ; "y" : la colonne de la valeur ; "serie" : la colonne qui sépare les séries (seulement pour barres_groupees, ou une courbe à plusieurs séries), sinon null. Ce sont des noms qui existent EXACTEMENT dans le résultat du graphique. "y" n'est jamais "nb", sauf si le graphique compte des éléments.
  - "libelle_x", "libelle_y", "libelle_serie" : les noms lisibles à afficher sur le graphique (ex. « Tranche d'âge », « Frais moyens », « Fumeur »).
  - Choix du type : comparer des groupes → barres ; beaucoup de groupes ou des noms longs → barres_horizontales ; croisement de deux facteurs → barres_groupees (ou courbe si le premier facteur est ordonné : tranches, mois) ; évolution dans le temps → courbe ; parts d'un tout avec 6 parts au maximum → camembert.
  - "phrase" : une ou deux phrases de conclusion avec les vrais chiffres du résultat. Pas de cause affirmée (écris « sont plus élevés chez », jamais « causent »). Ne compare jamais en citant un groupe dont nb est inférieur à 30 sans préciser entre parenthèses qu'il ne compte que ce petit nombre de lignes.
- "conclusion" : 2 à 3 phrases qui répondent à la question centrale, comme un analyste qui présente son dashboard à un décideur.
- "ordre" : la liste des id des graphiques dans l'ordre d'affichage (du général au détail).
- "libelles_filtres" : pour chaque filtre reçu, un nom court et lisible en français à afficher sur le bouton (ex. {"smoker": "Fumeur", "categorie_age": "Tranche d'âge"}). La clé est le nom EXACT de la colonne du filtre.

Réponds avec ce JSON :
{"kpi": [...], "graphiques": [...], "conclusion": "...", "ordre": ["g1", "..."], "libelles_filtres": {"colonne": "Nom lisible"}}"""


def _attente_limite(erreur: Exception) -> float | None:
    """
    Si Groq refuse parce que la limite de tokens par minute est atteinte (erreur 429),
    rend le nombre de secondes à attendre (indiqué par Groq), sinon None.
    """
    message = str(erreur)
    if "429" not in message and "rate limit" not in message.lower():
        return None
    delai = re.search(r"try again in (?:(\d+)h)?(?:(\d+)m)?([\d.]+)s", message)
    if not delai:
        return 20.0
    return int(delai.group(1) or 0) * 3600 + int(delai.group(2) or 0) * 60 + float(delai.group(3)) + 1


def _appeler_analyste(messages: list[dict], etape: str) -> dict:
    """
    Appelle le modèle et rend sa réponse JSON.
    Réessaie si le modèle se trompe de format, et attend si la limite de Groq est atteinte.
    """
    messages_envoyes = list(messages)
    attentes = 0
    essai = 0
    while essai < 3:
        try:
            reponse = client.chat.completions.create(
                model=MODELE_ANALYSTE,
                messages=messages_envoyes,
                max_tokens=MAX_TOKENS_REPONSE,
                temperature=0.2,
                response_format={"type": "json_object"},
            )
            if getattr(reponse, "usage", None):
                print(f"[ANALYSTE] Tokens ({etape}) : {reponse.usage.prompt_tokens} envoyés + "
                      f"{reponse.usage.completion_tokens} reçus = {reponse.usage.total_tokens}")
            contenu = (reponse.choices[0].message.content or "").strip()
            correspondance = re.search(r"\{.*\}", contenu, re.DOTALL)
            if not correspondance:
                raise ValueError("Réponse sans JSON")
            resultat = json.loads(correspondance.group())
            print(f"[ANALYSTE] ✓ {etape} (essai {essai + 1})")
            return resultat
        except Exception as e:
            attente = _attente_limite(e)
            if attente is not None and attente > 120:
                # Quota du jour épuisé : inutile d'attendre, la relance automatique refera l'analyse plus tard
                raise RuntimeError(f"Quota de Groq épuisé ({etape}) : nouvel essai possible plus tard.") from e
            if attente is not None and attentes < 6:
                # Limite de Groq atteinte : on patiente, sans compter cet essai comme un échec
                attentes += 1
                print(f"[ANALYSTE] Limite de Groq atteinte ({etape}) : attente de {attente:.0f} s")
                time.sleep(min(attente, 90))
                continue
            print(f"[ANALYSTE] ✗ {etape}, essai {essai + 1} : {str(e)[:300]}")
            essai += 1
            if essai == 3:
                raise
            messages_envoyes = list(messages) + [{
                "role": "system",
                "content": "Rappel : tu n'as accès à aucun outil. Réponds uniquement avec un objet JSON valide, sans texte autour.",
            }]


def _colonnes_calculees_valides(chemin: str, proposees: list) -> list:
    """Garde seulement les colonnes calculées qui fonctionnent et donnent au moins 2 groupes."""
    valides = []
    for colonne in proposees or []:
        if not isinstance(colonne, dict):
            continue
        nom = str(colonne.get("nom", ""))
        essai = executer_requete(chemin, f'SELECT COUNT(DISTINCT "{nom}") AS n FROM donnees', None, valides + [colonne])
        if essai["ok"] and essai["lignes"] and (essai["lignes"][0][0] or 0) >= 2:
            valides.append({"nom": nom, "expression": colonne["expression"], "explication": colonne.get("explication", "")})
        else:
            print(f"[ANALYSTE] Colonne calculée '{nom}' écartée : {essai.get('erreur', 'moins de 2 groupes')}")
    return valides


def _classer_facteurs(chemin: str, comprehension: dict, colonnes_calculees: list, roles: dict,
                      effectif_min: int) -> list:
    """
    Le serveur MESURE l'importance de chaque facteur (sans IA) : l'écart de la colonne principale
    entre le groupe le plus haut et le plus bas, sur tout le fichier. Les groupes de moins de
    effectif_min lignes sont ignorés pour ne pas tirer de conclusion d'un petit groupe.
    """
    principale = comprehension["colonne_principale"]
    cible = comprehension.get("valeur_cible")
    p = '"' + principale.replace('"', '""') + '"'
    if roles.get(principale) == "quantitative":
        valeur, unite = f"AVG({p})", "moyenne"
    else:
        cible_sql = "'" + str(cible).replace("'", "''") + "'"
        valeur, unite = f"100.0 * AVG(CASE WHEN CAST({p} AS VARCHAR) = {cible_sql} THEN 1 ELSE 0 END)", "pourcentage"

    noms_possibles = set(roles) | {c["nom"] for c in colonnes_calculees}
    # Une colonne calculée à partir de la colonne principale ne peut pas l'expliquer (raisonnement circulaire)
    motif_principale = re.compile(r'(?<![\w"])"?' + re.escape(principale) + r'"?(?![\w"])')
    derivees = {c["nom"] for c in colonnes_calculees if motif_principale.search(c["expression"])}
    # Des coordonnées GPS en tranches n'ont pas de sens pour un décideur : on les écarte
    motif_coordonnees = re.compile(r"(^|[^a-z])(lat|lon|lng|latitude|longitude|coord|coordonnees|gps)([^a-z]|$)", re.IGNORECASE)
    expressions = {c["nom"]: c["expression"] for c in colonnes_calculees}
    classement = []
    for facteur in comprehension.get("facteurs") or []:
        if facteur not in noms_possibles or facteur == principale or facteur in derivees:
            continue
        if motif_coordonnees.search(str(facteur)) or motif_coordonnees.search(expressions.get(facteur, "").replace('"', " ")):
            print(f"[ANALYSTE] Facteur '{facteur}' écarté : coordonnées géographiques")
            continue
        f = '"' + str(facteur).replace('"', '""') + '"'
        sql = (f"SELECT {f} AS groupe, ROUND({valeur}, 2) AS valeur, COUNT(*) AS nb FROM donnees "
               f"WHERE {f} IS NOT NULL AND {p} IS NOT NULL GROUP BY 1")
        res = executer_requete(chemin, sql, None, colonnes_calculees)
        if not res["ok"]:
            print(f"[ANALYSTE] Facteur '{facteur}' non mesuré : {res['erreur']}")
            continue
        groupes = [l for l in res["lignes"] if l[2] >= effectif_min and l[1] is not None]
        if len(res["lignes"]) > 15 or len(groupes) < 2:
            continue
        haut = max(groupes, key=lambda l: l[1])
        bas = min(groupes, key=lambda l: l[1])
        classement.append({
            "facteur": facteur, "ecart": round(haut[1] - bas[1], 2), "mesure": unite,
            "groupe_le_plus_haut": haut[0], "valeur_haute": haut[1],
            "groupe_le_plus_bas": bas[0], "valeur_basse": bas[1], "nb_groupes": len(res["lignes"]),
        })
    classement.sort(key=lambda c: c["ecart"], reverse=True)
    # Un facteur est « important » si son écart vaut au moins SEUIL_IMPORTANCE de celui du premier
    if classement:
        plus_grand = classement[0]["ecart"] or 1
        for c in classement:
            c["important"] = c["ecart"] >= SEUIL_IMPORTANCE * plus_grand
    return classement


def mettre_en_forme_resultat(resultat: dict, x: str, serie: str | None) -> dict:
    """
    Prépare le résultat d'un graphique pour l'affichage : retire les catégories vides
    (ex. une date illisible) et remet les tranches dans l'ordre. Sert au dashboard de base
    ET aux résultats recalculés quand un visiteur filtre.
    """
    colonnes = resultat.get("colonnes") or []
    lignes = resultat.get("lignes") or []
    if x in colonnes:
        lignes = [l for l in lignes if l[colonnes.index(x)] is not None]
        return _trier_si_ordonne({**resultat, "lignes": lignes}, x, serie if serie in colonnes else None)
    return {**resultat, "lignes": lignes}


def _trier_si_ordonne(resultat: dict, x: str, serie: str | None) -> dict:
    """
    Remet dans l'ordre naturel les catégories ordonnées (tranches « 1. … », « 18-25 », mois « 2025-01 »…),
    pour qu'elles ne s'affichent pas dans le désordre.
    """
    colonnes, lignes = resultat["colonnes"], resultat["lignes"]
    ix = colonnes.index(x)
    valeurs = [l[ix] for l in lignes if l[ix] is not None]
    if not valeurs or not all(isinstance(v, (int, float)) or re.match(r"^\s*\d", str(v)) for v in valeurs):
        return resultat
    def cle(ligne):
        v = ligne[ix]
        if isinstance(v, (int, float)):
            return (0, v, "")
        nombre = re.match(r"^\s*(\d+(?:[.,]\d+)?)", str(v))
        return (0, float(nombre.group(1).replace(",", ".")) if nombre else 0, str(v))
    iserie = colonnes.index(serie) if serie else None
    lignes_triees = sorted(lignes, key=lambda l: (str(l[iserie]) if iserie is not None else "",) + cle(l))
    return {**resultat, "lignes": lignes_triees}


def base_du_kpi(chemin: str, colonne: str | None, filtres: dict | None, colonnes_calculees: list) -> dict:
    """
    Sur combien de lignes un KPI est calculé (la phrase « calculé sur N » sous le chiffre).
    Python compte, avec les mêmes filtres que le KPI : aucun token.
    nb = lignes qui ont une valeur dans la colonne mesurée ; nb_sans_valeur = lignes où elle est vide.
    """
    c = '"' + str(colonne).replace('"', '""') + '"' if colonne else "*"
    res = executer_requete(chemin, f"SELECT COUNT(*) AS total, COUNT({c}) AS nb FROM donnees", filtres, colonnes_calculees)
    if not res["ok"] or not res["lignes"]:
        return {"nb": None, "nb_sans_valeur": None}
    total, nb = res["lignes"][0]
    return {"nb": nb, "nb_sans_valeur": total - nb}


def _valeurs_filtre(chemin: str, colonne: str, colonnes_calculees: list) -> list | None:
    """Liste des valeurs possibles d'un filtre, avec leur effectif. None si le filtre n'est pas utilisable."""
    c = '"' + str(colonne).replace('"', '""') + '"'
    res = executer_requete(chemin, f"SELECT {c} AS valeur, COUNT(*) AS nb FROM donnees WHERE {c} IS NOT NULL GROUP BY 1 ORDER BY 1",
                           None, colonnes_calculees)
    if not res["ok"] or not (2 <= len(res["lignes"]) <= 15):
        return None
    return [{"valeur": l[0], "nb": l[1]} for l in res["lignes"]]


DEVISES = [
    (("$", "usd", "dollar"), r"\s?(\$|\bUSD\b|\bUS\$|\bdollars?\b)"),
    (("€", "eur", "euro"), r"\s?(€|\bEUR\b|\beuros?\b)"),
    (("fcfa", "cfa", "xof", "franc"), r"\s?(\bF ?CFA\b|\bCFA\b|\bXOF\b|\bfrancs?\b)"),
    (("₹", "inr", "roupie", "rupee"), r"\s?(₹|\bINR\b|\broupies?\b|\brupees?\b)"),
    (("£", "gbp", "livre", "pound"), r"\s?(£|\bGBP\b|\blivres? sterling\b)"),
]


def retirer_devises_inventees(texte: str, reference: str) -> str:
    """Retire d'un texte les devises qui n'apparaissent pas dans le titre, la description ou les noms de colonnes."""
    if not texte:
        return texte
    reference = reference.lower()
    for mots, motif in DEVISES:
        if not any(m in reference for m in mots):
            texte = re.sub(motif, "", texte, flags=re.IGNORECASE)
    return re.sub(r"\s*\(\s*\)", "", texte).strip()


def valider_dashboard(comprehension: dict, colonnes_calculees: list, classement: list,
                      kpi_calcules: dict, graphiques_calcules: dict, presentation: dict,
                      filtres: list, effectif_min: int = EFFECTIF_MIN, reference: str = "") -> dict:
    """
    Le serveur CONTRÔLE le travail de l'Analyste avant de l'enregistrer :
    types de graphiques autorisés, colonnes qui existent dans les résultats, limites (4 KPI,
    6 graphiques), et les données affichées viennent UNIQUEMENT des résultats SQL.
    """
    # KPI : une seule valeur, venue du résultat SQL
    kpi = []
    for p in presentation.get("kpi") or []:
        calcul = kpi_calcules.get(p.get("id"))
        if not calcul or not calcul["resultat"]["lignes"]:
            continue
        valeur = calcul["resultat"]["lignes"][0][0]
        if not isinstance(valeur, (int, float)) or isinstance(valeur, bool):
            continue
        kpi.append({
            "id": p["id"], "titre": retirer_devises_inventees(str(p.get("titre") or calcul["titre"]), reference),
            "format": p.get("format") if p.get("format") in ("nombre", "monnaie", "pourcentage") else "nombre",
            "unite": retirer_devises_inventees(str(p.get("unite") or ""), reference), "valeur": valeur, "sql": calcul["sql"],
            "colonne": calcul.get("colonne"),
        })
        if len(kpi) == MAX_KPI:
            break

    # Graphiques, dans l'ordre choisi par l'Analyste
    presentations = {g.get("id"): g for g in presentation.get("graphiques") or [] if isinstance(g, dict)}
    ordre = [i for i in (presentation.get("ordre") or []) if i in presentations]
    ordre += [i for i in presentations if i not in ordre]
    graphiques = []
    for gid in ordre:
        p, calcul = presentations[gid], graphiques_calcules.get(gid)
        if not calcul:
            continue
        colonnes = calcul["resultat"]["colonnes"]
        x, y, serie = p.get("x"), p.get("y"), p.get("serie")
        lignes = calcul["resultat"]["lignes"]
        if x in colonnes:
            # Les catégories vides (ex. une date illisible) ne sont pas affichées
            lignes = [l for l in lignes if l[colonnes.index(x)] is not None]
        if not lignes or x not in colonnes or y not in colonnes or x == y:
            print(f"[ANALYSTE] Graphique {gid} écarté : axes invalides ({x}, {y}) pour {colonnes}")
            continue

        def numerique(colonne):
            valeurs = [l[colonnes.index(colonne)] for l in lignes if l[colonnes.index(colonne)] is not None]
            return bool(valeurs) and all(isinstance(v, (int, float)) and not isinstance(v, bool) for v in valeurs)

        # La valeur (y) doit être un nombre ; si l'Analyste a inversé les axes, on les remet dans le bon sens
        if not numerique(y):
            if numerique(x):
                x, y = y, x
                lignes = [l for l in calcul["resultat"]["lignes"] if l[colonnes.index(x)] is not None]
                p = {**p, "libelle_x": p.get("libelle_y"), "libelle_y": p.get("libelle_x")}
            else:
                print(f"[ANALYSTE] Graphique {gid} écarté : la valeur « {y} » n'est pas un nombre")
                continue
        if serie not in colonnes or serie in (x, y):
            serie = None
        type_graphique = p.get("type") if p.get("type") in TYPES_GRAPHIQUES else "barres"
        if type_graphique == "barres_groupees" and not serie:
            type_graphique = "barres"
        if type_graphique == "camembert" and (serie or len(lignes) > 6):
            type_graphique = "barres"
        graphiques.append({
            "id": gid, "titre": retirer_devises_inventees(str(p.get("titre") or calcul["question"]), reference),
            "question": calcul["question"], "pourquoi": calcul.get("pourquoi", ""), "famille": calcul.get("famille", ""),
            "type": type_graphique, "x": x, "y": y, "serie": serie,
            "libelle_x": str(p.get("libelle_x") or x),
            "libelle_y": retirer_devises_inventees(str(p.get("libelle_y") or y), reference),
            "libelle_serie": str(p.get("libelle_serie") or serie) if serie else None,
            "effectif": "nb" if "nb" in colonnes else None,
            "phrase": retirer_devises_inventees(str(p.get("phrase") or ""), reference), "sql": calcul["sql"],
            "resultat": mettre_en_forme_resultat({**calcul["resultat"], "lignes": lignes}, x, serie),
        })
        if len(graphiques) == MAX_GRAPHIQUES:
            break

    if not graphiques:
        raise ValueError("Aucun graphique valide n'a pu être construit.")

    # Nom lisible de chaque filtre, donné par Atlas ; à défaut, le nom de la colonne
    libelles = presentation.get("libelles_filtres") if isinstance(presentation.get("libelles_filtres"), dict) else {}
    filtres = [{**f, "libelle": str(libelles.get(f["colonne"]) or f["colonne"]).strip()[:40]} for f in filtres]

    return {
        "version": 1,
        "comprehension": comprehension,
        "colonnes_calculees": colonnes_calculees,
        "classement_facteurs": classement,
        "kpi": kpi,
        "graphiques": graphiques,
        "filtres": filtres,
        "conclusion": retirer_devises_inventees(str(presentation.get("conclusion") or ""), reference),
        "effectif_min": effectif_min,
    }


def analyser_dataset(fiche: dict, chemin_propre: str) -> dict:
    """
    L'Analyste : à partir de la fiche d'identité et du jeu de données propre (fichier local),
    construit le dashboard de base. Rend le dashboard (dictionnaire prêt à enregistrer en JSON).
    """
    print(f"\n[ANALYSTE] ── Début de l'analyse : {fiche.get('titre') or '(sans titre)'}")
    roles = {c["nom"]: c["role"] for c in fiche["colonnes"]}
    fiche_json = json.dumps(fiche_compacte(fiche), ensure_ascii=False)

    # Étape 1 : comprendre
    comprehension = _appeler_analyste([
        {"role": "system", "content": PROMPT_COMPRENDRE},
        {"role": "user", "content": f"Fiche d'identité du jeu de données :\n{fiche_json}"},
    ], "étape 1 (comprendre)")
    if comprehension.get("colonne_principale") not in roles:
        quantitatives = [n for n, r in roles.items() if r == "quantitative"]
        categorielles = [n for n, r in roles.items() if r == "categorielle"]
        if not quantitatives and not categorielles:
            raise ValueError("Aucune colonne exploitable pour une analyse.")
        comprehension["colonne_principale"] = (quantitatives or categorielles)[-1]
    if roles[comprehension["colonne_principale"]] != "quantitative" and not comprehension.get("valeur_cible"):
        colonne = next(c for c in fiche["colonnes"] if c["nom"] == comprehension["colonne_principale"])
        frequentes = colonne.get("valeurs_frequentes") or [{"valeur": None}]
        comprehension["valeur_cible"] = frequentes[0]["valeur"]
    print(f"[ANALYSTE] Sujet : {comprehension.get('sujet')} | principale : {comprehension['colonne_principale']}")

    colonnes_calculees = _colonnes_calculees_valides(chemin_propre, comprehension.pop("colonnes_calculees", []))
    print(f"[ANALYSTE] Colonnes calculées : {[c['nom'] for c in colonnes_calculees]}")

    # Le serveur mesure l'importance des facteurs
    effectif_min = effectif_minimum(fiche.get("nb_lignes") or 0)
    classement = _classer_facteurs(chemin_propre, comprehension, colonnes_calculees, roles, effectif_min)
    print(f"[ANALYSTE] Classement des facteurs : {[(c['facteur'], c['ecart']) for c in classement]}")

    # Étape 2 : choisir les calculs
    messages = [
        {"role": "system", "content": PROMPT_QUESTIONNER},
        {"role": "user", "content": json.dumps({
            "comprehension": comprehension, "colonnes_calculees": colonnes_calculees,
            "classement_facteurs": classement, "fiche": fiche_compacte(fiche, avec_exemples=False, budget_tokens=2000),
        }, ensure_ascii=False)},
    ]
    plan = _appeler_analyste(messages, "étape 2 (questionner)")

    calculs = {}
    for i, k in enumerate((plan.get("kpi") or [])[:MAX_KPI], 1):
        if isinstance(k, dict) and k.get("sql"):
            colonne = k.get("colonne")
            noms_valides = set(roles) | {c["nom"] for c in colonnes_calculees}
            calculs[f"k{i}"] = {"type": "kpi", "titre": k.get("titre", ""), "sql": k["sql"],
                                "colonne": colonne if colonne in noms_valides else None}
    for i, g in enumerate((plan.get("graphiques") or [])[:MAX_GRAPHIQUES], 1):
        if isinstance(g, dict) and g.get("sql"):
            calculs[f"g{i}"] = {"type": "graphique", "question": g.get("question", ""), "pourquoi": g.get("pourquoi", ""),
                                "famille": g.get("famille", ""), "sql": g["sql"]}

    # Exécution des requêtes, avec correction par l'Analyste en cas d'erreur
    a_executer = list(calculs)
    for essai in range(MAX_ESSAIS):
        erreurs = {}
        for cid in a_executer:
            res = executer_requete(chemin_propre, calculs[cid]["sql"], None, colonnes_calculees)
            if res["ok"] and res["lignes"] and not res["tronque"]:
                calculs[cid]["resultat"] = res
            elif res["ok"] and res["tronque"]:
                erreurs[cid] = (f"Le résultat dépasse {len(res['lignes'])} lignes et a été coupé : regroupe davantage "
                                "(par année au lieu de par mois, ou les principaux groupes seulement).")
            else:
                erreurs[cid] = res.get("erreur") or "Le résultat est vide."
        print(f"[ANALYSTE] Exécution {essai + 1} : {len(a_executer) - len(erreurs)} réussie(s), {len(erreurs)} erreur(s)")
        if not erreurs or essai == MAX_ESSAIS - 1:
            break
        messages += [
            {"role": "assistant", "content": json.dumps(plan, ensure_ascii=False)},
            {"role": "user", "content": PROMPT_CORRIGER + "\n" + json.dumps(
                [{"id": cid, "sql": calculs[cid]["sql"], "erreur": e} for cid, e in erreurs.items()], ensure_ascii=False)},
        ]
        corrections = _appeler_analyste(messages, f"correction {essai + 1}")
        a_executer = []
        for c in corrections.get("corrections") or []:
            if isinstance(c, dict) and c.get("id") in erreurs and c.get("sql"):
                calculs[c["id"]]["sql"] = c["sql"]
                a_executer.append(c["id"])
        if not a_executer:
            break

    kpi_calcules = {cid: c for cid, c in calculs.items() if c["type"] == "kpi" and "resultat" in c}
    graphiques_calcules = {cid: c for cid, c in calculs.items() if c["type"] == "graphique" and "resultat" in c}
    if not graphiques_calcules:
        raise ValueError("Aucune requête de graphique n'a réussi.")

    # Les filtres : le serveur prend les facteurs importants, dans l'ordre du classement
    filtres = []
    for colonne in [c["facteur"] for c in classement if c.get("important")]:
        valeurs = _valeurs_filtre(chemin_propre, colonne, colonnes_calculees)
        if valeurs:
            filtres.append({"colonne": colonne, "valeurs": valeurs})
        if len(filtres) == MAX_FILTRES:
            break

    # Étape 3 : présenter
    presentation = _appeler_analyste([
        {"role": "system", "content": PROMPT_PRESENTER},
        {"role": "user", "content": json.dumps({
            "question_centrale": comprehension.get("question_centrale"), "comprehension": comprehension,
            "kpi": [{"id": cid, "titre": c["titre"], "resultat": c["resultat"]} for cid, c in kpi_calcules.items()],
            "graphiques": [{"id": cid, "question": c["question"], "famille": c["famille"], "resultat": c["resultat"]}
                           for cid, c in graphiques_calcules.items()],
            "filtres": [{"colonne": f["colonne"], "exemples_de_valeurs": [v["valeur"] for v in f["valeurs"][:5]]}
                        for f in filtres],
        }, ensure_ascii=False)},
    ], "étape 3 (présenter)")

    dashboard = valider_dashboard(comprehension, colonnes_calculees, classement,
                                  kpi_calcules, graphiques_calcules, presentation, filtres, effectif_min,
                                  reference=" ".join([fiche.get("titre") or "", fiche.get("description") or ""]
                                                     + [c["nom"] for c in fiche["colonnes"]]))
    for k in dashboard["kpi"]:
        k.update(base_du_kpi(chemin_propre, k.get("colonne"), None, colonnes_calculees))
    print(f"[ANALYSTE] ✓ Dashboard prêt : {len(dashboard['kpi'])} KPI, {len(dashboard['graphiques'])} graphiques, "
          f"{len(dashboard['filtres'])} filtres")
    return dashboard


# ─── Chat principal ────────────────────────────────────────────────────────────

def chat(jeu_id: str, messages: list[dict]) -> str:
    """Répond à un message de l'utilisateur dans le contexte du jeu de données."""
    print(f"\n[CHAT] ── jeu_id={jeu_id} | {len(messages)} message(s) dans l'historique")
    contexte = construire_contexte(jeu_id)
    prompt = prompt_systeme(contexte)

    messages_recents = messages[-8:]
    dernier_msg = messages_recents[-1].get("content", "")[:150] if messages_recents else ""
    print(f"[CHAT] Dernier message : {dernier_msg}")
    print(f"[CHAT] Messages envoyés au modèle : {len(messages_recents)} (sur {len(messages)} total)")

    # Le modèle gpt-oss tente parfois d'utiliser un outil (exécuter du code) que l'on ne fournit pas :
    # Groq refuse alors la requête. On réessaie avec un rappel explicite.
    messages_envoyes = [{"role": "system", "content": prompt}] + messages_recents
    for essai in range(3):
        try:
            reponse = completion_avec_secours(
                messages=messages_envoyes,
                max_tokens=1500,
            )
            resultat = reponse.choices[0].message.content or ""
            # Les devises absentes du jeu de données sont retirées (sauf dans les blocs de code)
            morceaux = resultat.split("```")
            resultat = "```".join(retirer_devises_inventees(m, contexte) if i % 2 == 0 else m
                                  for i, m in enumerate(morceaux))
            print(f"[CHAT] ✓ Réponse générée ({len(resultat)} chars, essai {essai + 1}) :\n{resultat[:300]}...")
            return resultat
        except Exception as e:
            if "called a tool" in str(e) and essai < 2:
                print(f"[CHAT] Le modèle a voulu utiliser un outil, nouvel essai ({essai + 2}/3)")
                messages_envoyes = messages_envoyes + [{"role": "system", "content": "Rappel : tu n'as accès à aucun outil. Écris le code directement dans ta réponse, en Markdown."}]
                continue
            print(f"[CHAT] ✗ ERREUR appel modèle : {e}")
            raise