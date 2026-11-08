# Point d'entrée FastAPI — pipeline d'analyse des jeux de données
import os, tempfile, shutil, traceback, hashlib, math, asyncio
import pandas as pd
import httpx
from fastapi import FastAPI, UploadFile, File, Query, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from supabase import create_client
from dotenv import load_dotenv
from contextlib import asynccontextmanager

from modules.inspecteur import inspecter, lire_fichier
from modules.nettoyeur import nettoyer
from modules.rapport import generer_rapport
from modules.comparateur import comparer, memes_colonnes
from agent import suggerer as agent_suggerer, chat as agent_chat

load_dotenv()

supabase = create_client(
    os.getenv("SUPABASE_URL"),
    os.getenv("SUPABASE_SERVICE_KEY"),
)


async def _tache_reanalyse():
    """Vérifie toutes les 5 minutes les fichiers sans analyse terminée."""
    await asyncio.sleep(30)
    while True:
        try:
            print("[REANALYSE] Vérification des fichiers non analysés...")
            res_fichiers = supabase.table("fichiers").select("id, nom_fichier, chemin_stockage").execute()
            tous_fichiers = res_fichiers.data or []

            res_analyses = supabase.table("analyses").select("fichier_id").eq("statut", "termine").execute()
            ids_termines = {row["fichier_id"] for row in (res_analyses.data or [])}

            a_reanalyser = [f for f in tous_fichiers if f["id"] not in ids_termines]
            print(f"[REANALYSE] {len(a_reanalyser)} fichier(s) à traiter")

            for fichier in a_reanalyser:
                try:
                    contenu = supabase.storage.from_("jeux-donnees").download(fichier["chemin_stockage"])
                    async with httpx.AsyncClient(timeout=120) as client:
                        await client.post(
                            f"{os.getenv('API_URL', 'http://localhost:8000')}/analyser",
                            params={"fichier_id": fichier["id"]},
                            files={"fichier": (fichier["nom_fichier"], contenu)},
                        )
                    print(f"[REANALYSE] ✓ {fichier['nom_fichier']}")
                except Exception as e:
                    print(f"[REANALYSE] ✗ {fichier['nom_fichier']} : {e}")

        except Exception as e:
            print(f"[REANALYSE] Erreur générale : {e}")

        await asyncio.sleep(300)


@asynccontextmanager
async def lifespan(app: FastAPI):
    asyncio.create_task(_tache_reanalyse())
    yield


app = FastAPI(title="OpenData API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class RequeteChat(BaseModel):
    jeu_id: str
    messages: list[dict]


def _nettoyer_nan(obj):
    """Remplace les NaN/Inf par None pour la sérialisation JSON Supabase."""
    if isinstance(obj, float) and (math.isnan(obj) or math.isinf(obj)):
        return None
    if isinstance(obj, dict):
        return {k: _nettoyer_nan(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_nettoyer_nan(v) for v in obj]
    return obj


def calculer_hash(chemin: str, extension: str = "") -> str:
    """Calcule le hash MD5 du contenu + format du fichier."""
    h = hashlib.md5()
    h.update(extension.lower().strip(".").encode())
    with open(chemin, "rb") as f:
        for bloc in iter(lambda: f.read(8192), b""):
            h.update(bloc)
    return h.hexdigest()


def hash_contenu_dataframe(chemin: str, extension: str) -> str | None:
    """Hash du contenu normalisé, indépendant du format."""
    try:
        ext = extension.lower().strip(".")
        if ext == "csv":
            df = None
            for enc in ["utf-8", "latin-1", "cp1252"]:
                try:
                    df = pd.read_csv(chemin, encoding=enc, on_bad_lines="skip")
                    break
                except Exception:
                    continue
        elif ext in ("xlsx", "xls"):
            df = pd.read_excel(chemin)
        elif ext == "json":
            df = pd.read_json(chemin)
        else:
            return None
        if df is None:
            return None
        df = df.reindex(sorted(df.columns), axis=1)
        contenu_csv = df.fillna('').astype(str).to_csv(index=False)
        return hashlib.md5(contenu_csv.encode("utf-8", errors="replace")).hexdigest()
    except Exception:
        return None


@app.post("/analyser")
async def analyser(
    fichier: UploadFile = File(...),
    fichier_id: str = Query(None),
    utilisateur_id: str = Query(None),
):
    print(f"\n[ANALYSER] ── Fichier reçu : {fichier.filename} | fichier_id={fichier_id}")

    suffixe = os.path.splitext(fichier.filename)[1]
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffixe) as tmp:
        shutil.copyfileobj(fichier.file, tmp)
        chemin_tmp = tmp.name

    try:
        extension = suffixe.lower().strip(".")
        hash_fichier = hash_contenu_dataframe(chemin_tmp, extension) or calculer_hash(chemin_tmp, extension)
        fichier_id_existant = None
        print(f"[ANALYSER] Hash calculé : {hash_fichier}")

        if utilisateur_id:
            res = supabase.table("jeux_de_donnees") \
                .select("id") \
                .eq("utilisateur_id", utilisateur_id) \
                .eq("hash_fichier", hash_fichier) \
                .execute()
            if res.data:
                fichier_id_existant = str(res.data[0]["id"])
                print(f"[ANALYSER] Doublon détecté : jeu_id existant = {fichier_id_existant}")

        print(f"[ANALYSER] Lancement de l'inspection...")
        inspection = inspecter(chemin_tmp, fichier.filename)
        print(f"[ANALYSER] Inspection terminée : lisible={inspection.get('lisible')} | erreur={inspection.get('erreur')}")

        if not inspection.get("lisible"):
            raise HTTPException(status_code=400, detail=inspection.get("erreur", "Fichier illisible."))

        print(f"[ANALYSER] Dimensions : {inspection.get('nb_lignes')} lignes × {inspection.get('nb_colonnes')} colonnes")

        df = lire_fichier(chemin_tmp, fichier.filename)
        print(f"[ANALYSER] DataFrame chargé : {df.shape}")

        nettoyage = nettoyer(df, inspection["colonnes"])
        rapport = generer_rapport(inspection, nettoyage)

        resultats = {
            "inspection": inspection,
            "rapport": rapport,
            "apercu": inspection.get("apercu", []),
        }

        id_a_sauvegarder = fichier_id_existant or fichier_id
        if id_a_sauvegarder:
            print(f"[ANALYSER] Sauvegarde en base pour fichier_id={id_a_sauvegarder}...")
            resultats_propres = _nettoyer_nan(resultats)
            supabase.table("analyses").upsert(
                {"fichier_id": id_a_sauvegarder, "statut": "termine", "resultats": resultats_propres},
                on_conflict="fichier_id"
            ).execute()
            supabase.table("jeux_de_donnees") \
                .update({"hash_fichier": hash_fichier}) \
                .eq("id", id_a_sauvegarder) \
                .execute()
            print(f"[ANALYSER] ✓ Sauvegarde réussie")
        else:
            print(f"[ANALYSER] Aucun id_a_sauvegarder — analyse non persistée")

        print(f"[ANALYSER] ✓ Terminé avec succès\n")
        return _nettoyer_nan({
            **resultats,
            "hash_fichier": hash_fichier,
            "doublon": fichier_id_existant is not None,
            "fichier_id_existant": fichier_id_existant,
        })

    except HTTPException:
        raise
    except Exception as e:
        print(f"[ANALYSER] ✗ ERREUR : {traceback.format_exc()}")
        id_erreur = fichier_id_existant if 'fichier_id_existant' in locals() and fichier_id_existant else fichier_id
        if id_erreur:
            supabase.table("analyses").update(
                {"statut": "erreur", "resultats": {"erreur": str(e)}}
            ).eq("fichier_id", id_erreur).execute()
        raise HTTPException(status_code=500, detail=str(e))

    finally:
        os.unlink(chemin_tmp)


@app.post("/verifier-doublon")
async def verifier_doublon(
    fichier: UploadFile = File(...),
    utilisateur_id: str = Query(...),
):
    print(f"\n[DOUBLON] ── Fichier reçu : {fichier.filename}")

    suffixe = os.path.splitext(fichier.filename)[1]
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffixe) as tmp:
        shutil.copyfileobj(fichier.file, tmp)
        chemin_tmp = tmp.name

    try:
        extension = suffixe.lower().strip(".")
        hash_fichier = hash_contenu_dataframe(chemin_tmp, extension) or calculer_hash(chemin_tmp, extension)

        champs_jeu = "id, titre, description, source, categorie_id, fichiers(format, chemin_stockage)"

        # 1. Même contenu déjà publié par cet utilisateur ?
        res_perso = supabase.table("jeux_de_donnees") \
            .select(champs_jeu) \
            .eq("utilisateur_id", utilisateur_id) \
            .eq("hash_fichier", hash_fichier) \
            .execute()

        jeu_trouve = res_perso.data[0] if res_perso.data else None
        pct_lignes = None

        if jeu_trouve:
            formats = [f["format"] for f in (jeu_trouve.get("fichiers") or [])]
            resultat = "identique_meme_format" if extension in formats else "identique_autre_format"
        else:
            # 2. Nouvelle version d'un de ses jeux ?
            resultat = "nouveau"
            try:
                jeu_trouve, pct_lignes = _chercher_nouvelle_version(chemin_tmp, fichier.filename, utilisateur_id, champs_jeu)
                if jeu_trouve:
                    resultat = "nouvelle_version"
            except Exception:
                print(f"[DOUBLON] ✗ Comparaison impossible : {traceback.format_exc()}")
                jeu_trouve = None

        # 3. Même contenu publié par un autre utilisateur ?
        res_global = supabase.table("jeux_de_donnees") \
            .select("id") \
            .neq("utilisateur_id", utilisateur_id) \
            .eq("hash_fichier", hash_fichier) \
            .execute()

        doublon_global = bool(res_global.data)
        doublon_perso = resultat.startswith("identique")
        print(f"[DOUBLON] resultat={resultat} | pct_lignes={pct_lignes} | doublon_global={doublon_global}")

        jeu = None
        if jeu_trouve:
            jeu = {k: jeu_trouve.get(k) for k in ("id", "titre", "description", "source", "categorie_id")}

        return {
            "resultat": resultat,
            "jeu": jeu,
            "pct_lignes": pct_lignes,
            "hash_fichier": hash_fichier,
            "doublon_global": doublon_global,
            "format_doublon": extension if doublon_global else None,
            # Anciens champs, gardés pour la compatibilité avec l'ancien formulaire
            "doublon": doublon_perso,
            "jeu_id": str(jeu_trouve["id"]) if doublon_perso else None,
        }

    finally:
        os.unlink(chemin_tmp)


def _lire_fichier_stocke(chemin_stockage: str) -> pd.DataFrame:
    """Télécharge un fichier depuis Supabase Storage et le lit avec pandas."""
    suffixe = os.path.splitext(chemin_stockage)[1]
    contenu = supabase.storage.from_("jeux-donnees").download(chemin_stockage)
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffixe) as tmp:
        tmp.write(contenu)
        chemin_tmp = tmp.name
    try:
        return lire_fichier(chemin_tmp, chemin_stockage)
    finally:
        os.unlink(chemin_tmp)


def _chercher_nouvelle_version(chemin_tmp: str, nom_fichier: str, utilisateur_id: str, champs_jeu: str):
    """
    Cherche parmi les jeux de l'utilisateur celui dont ce fichier est une nouvelle version :
    mêmes colonnes et au moins 70 % des anciennes lignes retrouvées.
    Retourne (jeu, pourcentage de lignes) ou (None, None).
    """
    df_nouveau = lire_fichier(chemin_tmp, nom_fichier)

    jeux = supabase.table("jeux_de_donnees") \
        .select(champs_jeu) \
        .eq("utilisateur_id", utilisateur_id) \
        .execute().data or []
    if not jeux:
        return None, None

    # Colonnes de chaque jeu, lues dans les rapports d'analyse (sans ouvrir les fichiers)
    analyses = supabase.table("analyses") \
        .select("fichier_id, colonnes:resultats->inspection->colonnes") \
        .in_("fichier_id", [j["id"] for j in jeux]) \
        .eq("statut", "termine") \
        .execute().data or []
    colonnes_par_jeu = {
        str(a["fichier_id"]): [c["nom"] for c in (a.get("colonnes") or [])]
        for a in analyses
    }

    meilleur_jeu, meilleur_pct = None, None
    for jeu in jeux:
        colonnes = colonnes_par_jeu.get(str(jeu["id"]))
        fichiers = jeu.get("fichiers") or []
        if not colonnes or not fichiers or not memes_colonnes(colonnes, df_nouveau.columns):
            continue
        try:
            df_ancien = _lire_fichier_stocke(fichiers[0]["chemin_stockage"])
        except Exception as e:
            print(f"[DOUBLON] Ancien fichier illisible (jeu {jeu['id']}) : {e}")
            continue
        comparaison = comparer(df_ancien, df_nouveau)
        print(f"[DOUBLON] Jeu {jeu['id']} : {comparaison}")
        if comparaison["nouvelle_version"] and (meilleur_pct is None or comparaison["pct_lignes"] > meilleur_pct):
            meilleur_jeu, meilleur_pct = jeu, comparaison["pct_lignes"]

    return meilleur_jeu, meilleur_pct


@app.post("/suggerer")
async def suggerer(fichier: UploadFile = File(...)):
    print(f"\n[SUGGERER] ── Fichier reçu : {fichier.filename}")

    suffixe = os.path.splitext(fichier.filename)[1]
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffixe) as tmp:
        shutil.copyfileobj(fichier.file, tmp)
        chemin_tmp = tmp.name

    try:
        suggestion = agent_suggerer(chemin_tmp, fichier.filename)
        print(f"[SUGGERER] ✓ Suggestion obtenue : {suggestion}")
        return suggestion
    except HTTPException:
        raise
    except Exception as e:
        print(f"[SUGGERER] ✗ ERREUR : {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        os.unlink(chemin_tmp)


@app.post("/chat")
async def route_chat(requete: RequeteChat):
    try:
        reponse = agent_chat(requete.jeu_id, requete.messages)
        return {"reponse": reponse}
    except Exception as e:
        print("ERREUR /chat :", traceback.format_exc())
        raise HTTPException(status_code=500, detail=str(e))