# Point d'entrée FastAPI — pipeline d'analyse des jeux de données
import os, tempfile, shutil, traceback, hashlib, math, asyncio, queue, threading
from datetime import datetime, timezone
import pandas as pd
import httpx
from fastapi import FastAPI, UploadFile, File, Query, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from supabase import create_client
from dotenv import load_dotenv
from contextlib import asynccontextmanager

from modules.inspecteur import inspecter, lire_fichier, fiche_identite
from modules.nettoyeur import nettoyer
from modules.rapport import generer_rapport
from modules.comparateur import comparer, memes_colonnes
from modules.requetes import executer_requete
from agent import suggerer as agent_suggerer, chat as agent_chat, analyser_dataset, mettre_en_forme_resultat, \
    choisir_traitement_manquants, base_du_kpi

load_dotenv()

supabase = create_client(
    os.getenv("SUPABASE_URL"),
    os.getenv("SUPABASE_SERVICE_KEY"),
)


# ═══════════════════════════════════════════════════════════════════════════════
#  DASHBOARD AUTOMATIQUE : Atlas, dans son rôle d'analyste
#  Après le rapport de nettoyage, le jeu de données propre est rangé (Parquet) puis mis
#  dans une FILE D'ATTENTE. Un fil de travail séparé crée les dashboards un par un, en
#  arrière-plan, pour ne jamais bloquer le serveur et respecter les limites de l'IA.
# ═══════════════════════════════════════════════════════════════════════════════

DOSSIER_PROPRES = os.path.join(tempfile.gettempdir(), "opendata_propres")  # copies locales (cache)
os.makedirs(DOSSIER_PROPRES, exist_ok=True)
_file_dashboards: "queue.Queue[str]" = queue.Queue()
_dans_la_file: set[str] = set()
_verrou_file = threading.Lock()


def _chemin_local(jeu_id: str) -> str:
    return os.path.join(DOSSIER_PROPRES, f"{jeu_id}.parquet")


def _chemin_stockage_propre(jeu_id: str) -> str:
    return f"propres/{jeu_id}.parquet"


def enregistrer_fichier_propre(df: pd.DataFrame, jeu_id: str) -> str:
    """Range le jeu de données propre (format Parquet) dans le stockage Supabase et en garde une copie locale."""
    df_ecrit = df.copy()
    df_ecrit.columns = [str(c) for c in df_ecrit.columns]
    # Parquet refuse une colonne qui mélange des types (ex. nombres et textes) : on l'écrit en texte
    for col in df_ecrit.columns:
        if df_ecrit[col].dtype == object:
            df_ecrit[col] = df_ecrit[col].map(lambda v: None if v is None or (isinstance(v, float) and math.isnan(v)) else str(v))
    chemin_local = _chemin_local(jeu_id)
    df_ecrit.to_parquet(chemin_local, index=False)
    with open(chemin_local, "rb") as f:
        supabase.storage.from_("jeux-donnees").upload(
            _chemin_stockage_propre(jeu_id), f.read(),
            {"content-type": "application/octet-stream", "upsert": "true"},
        )
    return _chemin_stockage_propre(jeu_id)


def _fichier_propre_local(jeu_id: str, chemin_stockage: str) -> str:
    """Rend le chemin local du jeu propre ; le télécharge depuis le stockage s'il n'est pas déjà sur le serveur."""
    chemin_local = _chemin_local(jeu_id)
    if not os.path.exists(chemin_local):
        contenu = supabase.storage.from_("jeux-donnees").download(chemin_stockage)
        with open(chemin_local, "wb") as f:
            f.write(contenu)
    return chemin_local


def _maj_dashboard(jeu_id: str, **champs) -> None:
    """Crée ou met à jour la ligne du dashboard (seuls les champs donnés changent)."""
    supabase.table("dashboards").upsert(
        {"jeu_de_donnees_id": int(jeu_id), **champs, "mis_a_jour_le": datetime.now(timezone.utc).isoformat()},
        on_conflict="jeu_de_donnees_id",
    ).execute()


def _dashboard_meme_contenu(jeu_id: str, hash_fichier: str | None) -> dict | None:
    """Un autre jeu a exactement le même contenu et déjà un dashboard ? On le réutilise (0 token)."""
    if not hash_fichier:
        return None
    jeux = supabase.table("jeux_de_donnees").select("id").eq("hash_fichier", hash_fichier).neq("id", jeu_id).execute()
    ids = [j["id"] for j in (jeux.data or [])]
    if not ids:
        return None
    res = supabase.table("dashboards").select("fiche, contenu").in_("jeu_de_donnees_id", ids) \
        .eq("statut", "termine").limit(1).execute()
    return res.data[0] if res.data else None


def mettre_en_file(jeu_id: str) -> None:
    """Ajoute un jeu à la file d'attente des dashboards (une seule fois)."""
    with _verrou_file:
        if jeu_id in _dans_la_file:
            return
        _dans_la_file.add(jeu_id)
    _file_dashboards.put(jeu_id)


def preparer_dashboard(jeu_id: str, df_propre: pd.DataFrame, hash_fichier: str | None) -> None:
    """Appelée par /analyser après le rapport : range le jeu propre, puis réutilise ou met en file."""
    jeu_id = str(jeu_id)
    chemin = enregistrer_fichier_propre(df_propre, jeu_id)
    existant = _dashboard_meme_contenu(jeu_id, hash_fichier)
    if existant:
        _maj_dashboard(jeu_id, statut="termine", fiche=existant["fiche"], contenu=existant["contenu"],
                       chemin_propre=chemin, erreur=None)
        print(f"[DASHBOARD] Jeu {jeu_id} : même contenu qu'un jeu existant, dashboard réutilisé (0 token)")
        return
    _maj_dashboard(jeu_id, statut="en_attente", chemin_propre=chemin, erreur=None)
    mettre_en_file(jeu_id)
    print(f"[DASHBOARD] Jeu {jeu_id} mis en file d'attente ({_file_dashboards.qsize()} en attente)")


def _creer_dashboard(jeu_id: str) -> None:
    """Le vrai travail : fiche d'identité, puis Atlas (rôle d'analyste), puis enregistrement."""
    _maj_dashboard(jeu_id, statut="en_cours")
    ligne = supabase.table("dashboards").select("chemin_propre").eq("jeu_de_donnees_id", jeu_id).maybe_single().execute()
    jeu = supabase.table("jeux_de_donnees").select("titre, description").eq("id", jeu_id).maybe_single().execute()
    if not ligne or not ligne.data or not ligne.data.get("chemin_propre"):
        raise ValueError("Jeu de données propre introuvable.")
    infos = (jeu.data if jeu and jeu.data else {}) or {}
    chemin_local = _fichier_propre_local(jeu_id, ligne.data["chemin_propre"])
    # Les rôles corrigés par Atlas au nettoyage sont repris ici (enregistrés avec le rapport)
    roles_atlas = {}
    try:
        analyse = supabase.table("analyses").select("resultats").eq("fichier_id", jeu_id).maybe_single().execute()
        roles_atlas = ((((analyse.data if analyse else None) or {}).get("resultats") or {}).get("rapport") or {}).get("roles_atlas") or {}
    except Exception:
        pass
    fiche = fiche_identite(pd.read_parquet(chemin_local), infos.get("titre") or "", infos.get("description") or "", roles_atlas)
    dashboard = analyser_dataset(fiche, chemin_local)
    _maj_dashboard(jeu_id, statut="termine", fiche=_nettoyer_nan(fiche), contenu=_nettoyer_nan(dashboard), erreur=None)
    print(f"[DASHBOARD] ✓ Jeu {jeu_id} : dashboard enregistré")


def _travailleur_dashboards() -> None:
    """Fil de travail séparé : prend les jeux dans la file, un par un, pour toujours."""
    while True:
        jeu_id = _file_dashboards.get()
        try:
            _creer_dashboard(jeu_id)
        except Exception as e:
            print(f"[DASHBOARD] ✗ Jeu {jeu_id} : {traceback.format_exc()}")
            try:
                _maj_dashboard(jeu_id, statut="erreur", erreur=str(e)[:500])
            except Exception:
                pass
        finally:
            with _verrou_file:
                _dans_la_file.discard(jeu_id)


def _relancer_dashboards(tous_jeux: list, ids_avec_rapport: set) -> dict | None:
    """
    Remet en file les dashboards en erreur (après 30 min) ou bloqués après un redémarrage (après 10 min).
    Rend aussi UN jeu publié avant l'arrivée des dashboards (s'il y en a), pour lui en créer un.
    """
    lignes = supabase.table("dashboards").select("jeu_de_donnees_id, statut, mis_a_jour_le").execute().data or []
    maintenant = datetime.now(timezone.utc)
    for d in lignes:
        jeu_id = str(d["jeu_de_donnees_id"])
        if d["statut"] == "termine" or jeu_id in _dans_la_file:
            continue
        mis_a_jour = datetime.fromisoformat(str(d["mis_a_jour_le"]).replace("Z", "+00:00"))
        if (maintenant - mis_a_jour).total_seconds() >= (1800 if d["statut"] == "erreur" else 600):
            print(f"[DASHBOARD] Nouvel essai pour le jeu {jeu_id} (statut {d['statut']})")
            mettre_en_file(jeu_id)
    if not _file_dashboards.empty():
        return None
    avec_dashboard = {d["jeu_de_donnees_id"] for d in lignes}
    anciens = [j for j in tous_jeux if j["id"] in ids_avec_rapport and j["id"] not in avec_dashboard and j.get("fichiers")]
    return anciens[0] if anciens else None


async def _tache_reanalyse():
    """Vérifie toutes les 5 minutes les fichiers sans analyse terminée."""
    await asyncio.sleep(30)
    while True:
        try:
            print("[REANALYSE] Vérification des fichiers non analysés...")
            # Le rapport d'analyse est rangé sous le numéro du JEU de données (comme le fait le site),
            # jamais sous le numéro d'un fichier : sinon il pourrait écraser le rapport d'un autre jeu.
            res_jeux = supabase.table("jeux_de_donnees").select("id, fichiers(id, nom_fichier, chemin_stockage)").execute()
            tous_jeux = res_jeux.data or []

            res_analyses = supabase.table("analyses").select("fichier_id").eq("statut", "termine").execute()
            ids_termines = {row["fichier_id"] for row in (res_analyses.data or [])}

            a_reanalyser = [j for j in tous_jeux if j["id"] not in ids_termines and j.get("fichiers")]
            print(f"[REANALYSE] {len(a_reanalyser)} jeu(x) à traiter")

            for jeu in a_reanalyser:
                fichier = jeu["fichiers"][0]
                try:
                    contenu = supabase.storage.from_("jeux-donnees").download(fichier["chemin_stockage"])
                    async with httpx.AsyncClient(timeout=120) as client:
                        await client.post(
                            f"{os.getenv('API_URL', 'http://localhost:8000')}/analyser",
                            params={"fichier_id": jeu["id"]},
                            files={"fichier": (fichier["nom_fichier"], contenu)},
                        )
                    print(f"[REANALYSE] ✓ jeu {jeu['id']} ({fichier['nom_fichier']})")
                except Exception as e:
                    print(f"[REANALYSE] ✗ jeu {jeu['id']} ({fichier['nom_fichier']}) : {e}")

            # Dashboards : relancer ceux en erreur ou bloqués, et en créer pour les jeux publiés avant
            jeu_sans_dashboard = _relancer_dashboards(tous_jeux, ids_termines)
            if jeu_sans_dashboard:
                # Un seul jeu à la fois, pour ne pas épuiser le quota de l'IA d'un coup
                fichier = jeu_sans_dashboard["fichiers"][0]
                try:
                    contenu = supabase.storage.from_("jeux-donnees").download(fichier["chemin_stockage"])
                    async with httpx.AsyncClient(timeout=180) as client:
                        await client.post(
                            f"{os.getenv('API_URL', 'http://localhost:8000')}/analyser",
                            params={"fichier_id": jeu_sans_dashboard["id"]},
                            files={"fichier": (fichier["nom_fichier"], contenu)},
                        )
                    print(f"[DASHBOARD] Dashboard demandé pour l'ancien jeu {jeu_sans_dashboard['id']}")
                except Exception as e:
                    print(f"[DASHBOARD] ✗ Ancien jeu {jeu_sans_dashboard['id']} : {e}")

        except Exception as e:
            print(f"[REANALYSE] Erreur générale : {e}")

        await asyncio.sleep(300)


@asynccontextmanager
async def lifespan(app: FastAPI):
    tache = asyncio.create_task(_tache_reanalyse())
    threading.Thread(target=_travailleur_dashboards, daemon=True).start()
    yield
    tache.cancel()  # arrêt propre de la relance automatique quand le serveur s'arrête


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


class RequeteFiltre(BaseModel):
    jeu_id: str
    filtres: dict[str, list] = {}   # ex. {"smoker": ["yes"], "age_group": ["18-25", "26-35"]}


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

        # Atlas décide du traitement des cases vides à partir de la fiche d'identité (titre et description aident)
        infos_jeu = {}
        if fichier_id_existant or fichier_id:
            try:
                rep = supabase.table("jeux_de_donnees").select("titre, description") \
                    .eq("id", fichier_id_existant or fichier_id).maybe_single().execute()
                infos_jeu = (rep.data if rep else None) or {}
            except Exception:
                pass

        def decision_atlas(df_presque_propre):
            fiche = fiche_identite(df_presque_propre, infos_jeu.get("titre") or fichier.filename, infos_jeu.get("description") or "")
            return choisir_traitement_manquants(fiche)

        nettoyage = nettoyer(df, inspection["colonnes"], decision_atlas)
        rapport = generer_rapport(inspection, nettoyage)
        rapport["roles_atlas"] = nettoyage.get("roles_atlas") or {}  # repris par le dashboard

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

            # Dashboard automatique : jamais bloquant pour le rapport, qui est déjà enregistré
            try:
                preparer_dashboard(id_a_sauvegarder, nettoyage["df_nettoye"], hash_fichier)
            except Exception:
                print(f"[DASHBOARD] ✗ Préparation impossible : {traceback.format_exc()}")
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
                jeu_trouve, pct_lignes, identique = _chercher_nouvelle_version(chemin_tmp, fichier.filename, utilisateur_id, champs_jeu)
                if jeu_trouve and identique:
                    # Même contenu, même si l'empreinte enregistrée a été calculée autrement
                    formats = [f["format"] for f in (jeu_trouve.get("fichiers") or [])]
                    resultat = "identique_meme_format" if extension in formats else "identique_autre_format"
                    pct_lignes = None
                elif jeu_trouve:
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
    Retourne (jeu, pourcentage de lignes, contenu identique ?) ou (None, None, False).
    """
    df_nouveau = lire_fichier(chemin_tmp, nom_fichier)

    jeux = supabase.table("jeux_de_donnees") \
        .select(champs_jeu) \
        .eq("utilisateur_id", utilisateur_id) \
        .execute().data or []
    if not jeux:
        return None, None, False

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

    meilleur_jeu, meilleur_pct, identique = None, None, False
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
        if comparaison["identique"]:
            return jeu, comparaison["pct_lignes"], True
        if comparaison["nouvelle_version"] and (meilleur_pct is None or comparaison["pct_lignes"] > meilleur_pct):
            meilleur_jeu, meilleur_pct = jeu, comparaison["pct_lignes"]

    return meilleur_jeu, meilleur_pct, False


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


@app.post("/dashboard/filtrer")
def filtrer_dashboard(requete: RequeteFiltre):
    """
    Recalcule les KPI et les graphiques du dashboard pour les filtres choisis par le visiteur.
    On relance les requêtes déjà écrites par Atlas : l'IA n'est PAS appelée, donc aucun token.
    (Fonction non async : FastAPI l'exécute à part, sans bloquer le reste du serveur.)
    """
    res = supabase.table("dashboards").select("statut, contenu, chemin_propre") \
        .eq("jeu_de_donnees_id", requete.jeu_id).maybe_single().execute()
    if not res or not res.data or res.data.get("statut") != "termine" or not res.data.get("contenu"):
        raise HTTPException(status_code=404, detail="Dashboard indisponible.")
    contenu = res.data["contenu"]

    # Seuls les filtres prévus par le dashboard sont acceptés
    autorises = {f["colonne"] for f in contenu.get("filtres") or []}
    filtres = {col: valeurs for col, valeurs in requete.filtres.items() if col in autorises and valeurs}
    chemin = _fichier_propre_local(requete.jeu_id, res.data["chemin_propre"])
    colonnes_calculees = contenu.get("colonnes_calculees") or []

    kpi = []
    for k in contenu.get("kpi") or []:
        r = executer_requete(chemin, k["sql"], filtres, colonnes_calculees)
        kpi.append({"id": k["id"], "valeur": r["lignes"][0][0] if r["ok"] and r["lignes"] else None,
                    **base_du_kpi(chemin, k.get("colonne"), filtres, colonnes_calculees)})

    graphiques = []
    for g in contenu.get("graphiques") or []:
        r = executer_requete(chemin, g["sql"], filtres, colonnes_calculees)
        resultat = mettre_en_forme_resultat(r, g["x"], g.get("serie")) if r["ok"] else None
        graphiques.append({"id": g["id"], "resultat": _nettoyer_nan(resultat) if resultat else None})

    return {"filtres": filtres, "kpi": _nettoyer_nan(kpi), "graphiques": graphiques}


@app.post("/chat")
async def route_chat(requete: RequeteChat):
    try:
        reponse = agent_chat(requete.jeu_id, requete.messages)
        return {"reponse": reponse}
    except Exception as e:
        print("ERREUR /chat :", traceback.format_exc())
        raise HTTPException(status_code=500, detail=str(e))