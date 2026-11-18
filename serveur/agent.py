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
        f"- Sujet : {c.get('sujet', '')}",
        f"- Question centrale : {c.get('question_centrale', '')}",
        f"- Colonne principale étudiée : {c.get('colonne_principale', '')}",
    ]
    # Description de chaque colonne (gardée ou non pour l'analyse), écrite par Atlas
    for col in (dashboard.get("description") or {}).get("colonnes") or []:
        lignes.append(f"- Colonne « {col['nom']} » ({'utilisée' if col.get('gardee') else 'non utilisée'} pour l'analyse) : {col.get('description', '')}")
    for col in dashboard.get("colonnes_calculees") or []:
        lignes.append(f"- Colonne calculée « {col['nom']} » : {col.get('explication', '')}")
    if dashboard.get("classement_facteurs"):
        lignes.append("- Classement des facteurs (écart de la colonne principale entre le groupe le plus haut et le plus bas) : " + " ; ".join(
            f"{f['facteur']} = {f['ecart']} (le plus haut : {f['groupe_le_plus_haut']} {f['valeur_haute']}, le plus bas : {f['groupe_le_plus_bas']} {f['valeur_basse']})"
            + ("" if f.get("important") else ", peu important")
            for f in dashboard["classement_facteurs"]))
    for k in dashboard.get("kpi") or []:
        lignes.append(f"- Chiffre clé « {k['titre']} » : {k['valeur']} {k.get('unite') or k.get('detail') or ''}".rstrip())
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
    for piste in dashboard.get("pistes") or []:
        lignes.append(f"- Piste d'analyse proposée : {piste}")
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
#  Outils partagés avec l'Analyste (analyste.py) : fiche allégée, appel au modèle,
#  mise en forme des résultats SQL, filtres et devises.
# ═══════════════════════════════════════════════════════════════════════════════

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


def _taille_reponse(messages: list[dict]) -> int:
    """Groq compte l'entrée + la réponse maximale dans sa limite par minute : la réponse s'adapte à l'entrée."""
    entree = sum(len(str(m.get("content", ""))) for m in messages) // 3
    return max(1500, min(4500, 7600 - entree))


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
                max_tokens=_taille_reponse(messages_envoyes),
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