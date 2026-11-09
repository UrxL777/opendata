import os
import json
import re
import pandas as pd
from openai import OpenAI
from supabase import create_client
from dotenv import load_dotenv

load_dotenv()

client = OpenAI(
    api_key=os.getenv("GROQ_API_KEY"),
    base_url="https://api.groq.com/openai/v1",
)

supabase = create_client(
    os.getenv("SUPABASE_URL"),
    os.getenv("SUPABASE_SERVICE_KEY"),
)

MODELE = "openai/gpt-oss-20b"


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
- Tu ne fais PAS l'analyse à la place de l'utilisateur : tu expliques, tu conseilles et tu orientes.
- Tu réponds dans la langue de l'utilisateur (français par défaut) et tu le TUTOIES toujours, jamais de « vous ».

Comment réagir selon la situation :
- Salutation (bonjour, salut, coucou…) : tu salues chaleureusement, puis tu proposes 3 exemples de questions adaptées à CE jeu de données. Tu ne te présentes pas. Pas de code, pas de méthode.
  Exemple : « Salut ! Content de t'aider à explorer ce jeu de données. Tu peux par exemple me demander : … » suivi de 3 questions en liste.
- Question sur toi (qui es-tu, que fais-tu…) : seulement dans ce cas, tu te présentes : tu es Atlas, l'assistant d'OpenData qui aide à comprendre et analyser les jeux de données de la plateforme.
- Remerciement ou message court (merci, ok, d'accord…) : tu réponds simplement et poliment, en une phrase, et tu proposes de continuer. Pas de code.
- Question sur les données ou sur une analyse : tu réponds d'abord en une ou deux phrases simples, en langage naturel, qui répondent directement à la question (quelle méthode et pourquoi). Ensuite seulement, tu proposes : « Veux-tu que je te montre comment le faire en Python ? »
- Demande de code, ou réponse positive à ta proposition (oui, vas-y, montre-moi…) : tu donnes le code.
- Demande d'explication (je ne comprends pas, explique…) : tu expliques avec des mots simples, pas à pas, sans redonner tout le code.
- Utilisateur perdu ou hésitant : tu lui proposes 2 ou 3 pistes simples parmi lesquelles choisir.
- Question sans rapport avec la data ou ce jeu de données : tu expliques gentiment que tu es Atlas, l'assistant d'OpenData, là pour aider à comprendre et analyser ce jeu de données, et que tu n'es pas là pour d'autres sujets. Puis tu proposes une question sur le jeu de données.

Règles importantes :
- Tu ne donnes JAMAIS de code de toi-même : uniquement si l'utilisateur le demande ou accepte ta proposition.
- Quand tu donnes du code, il est court, commenté en français, et suivi d'une phrase qui explique ce qu'il produit.
- Dans le code, utilise EXACTEMENT les noms de colonnes listés dans « Noms exacts des colonnes » du contexte (par exemple `Rain`, `Humidity`), sans les traduire ni les inventer. Si une colonne contient du texte (par exemple « rain » / « no rain »), convertis-la en nombres avant de calculer (par exemple rain → 1, no rain → 0). Ne traduis JAMAIS les identifiants dans le code.
- Tu termines par UNE seule question courte pour relancer la conversation. Ta proposition de code compte comme cette question : dans ce cas, n'en pose pas d'autre.
- Tu adaptes la longueur à la question : une question simple appelle une réponse courte. Ne sur-explique jamais.
- Ne laisse JAMAIS une réponse vide.

Mise en forme :
- Tu utilises le Markdown avec modération : listes à puces, gras, et blocs de code uniquement pour du code.
- N'utilise JAMAIS de tableaux Markdown, sauf si l'utilisateur demande explicitement un « tableau » ou une « table ».
- N'utilise JAMAIS de traits horizontaux (---), de séparateurs visuels, ni d'emojis numérotés (1️⃣, 2️⃣, etc.).

Contexte du jeu de données :
{contexte}"""


# ─── Construction du contexte à partir de la base ─────────────────────────────

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
            if fichiers:
                fichier_id = fichiers[0]["id"]
                print(f"[AGENT] Recherche analyse pour fichier_id={fichier_id}")
                rep_analyse = supabase.table("analyses") \
                    .select("resultats") \
                    .eq("fichier_id", fichier_id) \
                    .eq("statut", "termine") \
                    .maybe_single() \
                    .execute()
                if rep_analyse is not None and rep_analyse.data:
                    resultats = rep_analyse.data.get("resultats", {})
                    # Les colonnes, les dimensions et la qualité sont dans l'inspection
                    rapport = resultats.get("inspection") or resultats.get("rapport", {})
                    apercu = resultats.get("apercu", [])
                    print(f"[AGENT] Rapport trouvé : {rapport.get('nb_lignes')} lignes × {rapport.get('nb_colonnes')} colonnes | {len(apercu)} lignes d'aperçu")
                else:
                    print(f"[AGENT] Aucun rapport d'analyse disponible")
        except Exception as e:
            print(f"[AGENT] ✗ Erreur récupération analyse : {e}")

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
        reponse = client.chat.completions.create(
            model=MODELE,
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

    try:
        reponse = client.chat.completions.create(
            model=MODELE,
            messages=[{"role": "system", "content": prompt}] + messages_recents,
            max_tokens=1500,
        )
        resultat = reponse.choices[0].message.content
        print(f"[CHAT] ✓ Réponse générée ({len(resultat)} chars) :\n{resultat[:300]}...")
        return resultat
    except Exception as e:
        print(f"[CHAT] ✗ ERREUR appel modèle : {e}")
        raise