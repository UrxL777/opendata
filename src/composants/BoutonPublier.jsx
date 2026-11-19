import { useState, useRef, useEffect } from 'react'
import { Upload, X, Plus, CheckCircle, AlertTriangle, Info, XCircle } from 'lucide-react'
import { supabase } from '../supabase'
import { useAuthentification } from '../contexte/Authentification'
import { traduireErreurAuth, verifierInscription } from '../utilitaires/erreursAuth'
import { useNavigate } from 'react-router-dom'

// Moment de la publication (en millisecondes), pour donner un nom unique au fichier stocké
const horodatage = () => Date.now()

function IcôneOeil({ visible }) {
  if (visible) {
    return (
      <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
        <path d="M17.94 17.94A10.07 10.07 0 0 1 12 20c-7 0-11-8-11-8a18.45 18.45 0 0 1 5.06-5.94"/>
        <path d="M9.9 4.24A9.12 9.12 0 0 1 12 4c7 0 11 8 11 8a18.5 18.5 0 0 1-2.16 3.19"/>
        <line x1="1" y1="1" x2="23" y2="23"/>
      </svg>
    )
  }
  return (
    <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/>
      <circle cx="12" cy="12" r="3"/>
    </svg>
  )
}

// ─── Formulaire jeu de données ────────────────────────────────────────────────

const NOMS_FORMATS = { csv: 'CSV', xlsx: 'Excel', xls: 'Excel', json: 'JSON' }
const FORMATS_ACCEPTES = ['csv', 'xlsx', 'xls', 'json']
const TAILLE_MAX_MO = 50

function FormulaireDataset({ onFermer }) {
  const { utilisateur } = useAuthentification()
  const navigate = useNavigate()
  const inputRef = useRef()
  const controleurRef = useRef(null)
  const suggestionRef = useRef({})
  const choixRef = useRef(null)

  const [categories, setCategories] = useState([])
  const [titre, setTitre] = useState('')
  const [description, setDescription] = useState('')
  const [source, setSource] = useState('')
  const [categorieId, setCategorieId] = useState('')
  const [fichier, setFichier] = useState(null)
  const [chargement, setChargement] = useState(false)
  const [analyse, setAnalyse] = useState(false)
  const [verification, setVerification] = useState(false)
  const [comparaison, setComparaison] = useState(null)
  const [choix, setChoix] = useState(null)
  const [erreur, setErreur] = useState('')
  const [erreurFichier, setErreurFichier] = useState('')
  const [avertissementGlobal, setAvertissementGlobal] = useState('')

  useEffect(() => {
    supabase.from('categories').select('*').then(({ data }) => setCategories(data ?? []))
  }, [])

  function viderFormulaire() {
    setTitre('')
    setDescription('')
    setSource('')
    setCategorieId('')
    setErreur('')
    setErreurFichier('')
    setAvertissementGlobal('')
    setComparaison(null)
    setChoix(null)
    choixRef.current = null
    suggestionRef.current = {}
  }

  function annuler() {
    if (controleurRef.current) controleurRef.current.abort()
    viderFormulaire()
    setFichier(null)
    setAnalyse(false)
    setVerification(false)
  }

  async function choisirFichier(f) {
    if (!f) return
    if (controleurRef.current) controleurRef.current.abort()
    viderFormulaire()

    // Format et taille vérifiés avant tout envoi au serveur
    const ext = f.name.split('.').pop().toLowerCase()
    if (!FORMATS_ACCEPTES.includes(ext)) {
      setFichier(null)
      setErreurFichier(`Format non accepté (.${ext}). Formats acceptés : CSV, Excel (.xlsx, .xls) et JSON.`)
      return
    }
    const tailleMo = f.size / (1024 * 1024)
    if (tailleMo > TAILLE_MAX_MO) {
      setFichier(null)
      setErreurFichier(`Fichier trop volumineux (${Math.round(tailleMo)} Mo). La taille maximale est de ${TAILLE_MAX_MO} Mo.`)
      return
    }

    setFichier(f)
    setAnalyse(true)
    setVerification(true)
    const controleur = new AbortController()
    controleurRef.current = controleur

    // Suggestions de l'IA (titre, description, catégorie)
    const suggestions = (async () => {
      const form = new FormData()
      form.append('fichier', f)
      const rep = await fetch(`${import.meta.env.VITE_API_URL}/suggerer`, { method: 'POST', body: form, signal: controleur.signal })  // Envoi du fichier vers le serveur
      if (!rep.ok) return
      const s = await rep.json()
      suggestionRef.current = { titre: s.titre || '', description: s.description || '', categorieId: s.categorie_id ? String(s.categorie_id) : '' }
      // On ne remplace pas les informations du jeu existant si l'utilisateur a choisi de le mettre à jour.
      // La suggestion ne remplit que les champs encore vides : ce que l'utilisateur a déjà tapé est gardé.
      if (choixRef.current !== 'maj') {
        const s = suggestionRef.current
        setTitre(actuel => actuel.trim() ? actuel : s.titre)
        setDescription(actuel => actuel.trim() ? actuel : s.description)
        setCategorieId(actuel => actuel || s.categorieId)
      }
    })().catch(() => {}).finally(() => {
      if (controleurRef.current === controleur) setAnalyse(false)
    })

    // Comparaison avec les jeux déjà publiés par l'utilisateur
    const verificationDoublon = (async () => {
      const form = new FormData()
      form.append('fichier', f)
      const rep = await fetch(`${import.meta.env.VITE_API_URL}/verifier-doublon?utilisateur_id=${utilisateur.id}`, { method: 'POST', body: form, signal: controleur.signal })
      if (!rep.ok) return
      const resultat = await rep.json()
      setComparaison(resultat)
      if (resultat.doublon_global && resultat.format_doublon) {
        setAvertissementGlobal(`Un jeu de données similaire existe déjà sur la plateforme en ${resultat.format_doublon.toUpperCase()}. Vous pouvez quand même publier le vôtre.`)
      }
    })().catch(() => {}).finally(() => {
      if (controleurRef.current === controleur) setVerification(false)
    })

    await Promise.all([suggestions, verificationDoublon])
  }

  function appliquerValeurs({ titre = '', description = '', source = '', categorieId = '' }) {
    setTitre(titre)
    setDescription(description)
    setSource(source)
    setCategorieId(categorieId)
  }

  function choisir(valeur) {
    setChoix(valeur)
    choixRef.current = valeur
    if (valeur === 'maj') {
      const jeu = comparaison.jeu
      appliquerValeurs({
        titre: jeu.titre || '',
        description: jeu.description || '',
        source: jeu.source || '',
        categorieId: jeu.categorie_id ? String(jeu.categorie_id) : '',
      })
    } else {
      appliquerValeurs(suggestionRef.current)
    }
  }

  function titreVersNomFichier(t, ext) {
    const base = t.toLowerCase().normalize('NFD').replace(/[̀-ͯ]/g, '')
      .replace(/[^a-z0-9]+/g, '-').replace(/^-+|-+$/g, '').slice(0, 60)
    return `${base}.${ext}`
  }

  const resultat = comparaison?.resultat
  const bloque = resultat === 'identique_meme_format'
  const choixRequis = resultat === 'identique_autre_format' || resultat === 'nouvelle_version'
  const peutPublier = !!fichier && !verification && !bloque && (!choixRequis || !!choix) && !chargement
  const extension = fichier?.name.split('.').pop().toLowerCase()

  async function publier(e) {
    e.preventDefault()
    if (!fichier) { setErreur('Veuillez sélectionner un fichier.'); return }
    if (!peutPublier) return
    if (!titre.trim()) { setErreur('Le titre est obligatoire.'); return }
    if (!description.trim()) { setErreur('La description est obligatoire.'); return }
    if (!categorieId) { setErreur('La catégorie est obligatoire.'); return }
    setErreur('')
    setChargement(true)
    try {
      const ext = extension
      const nomFichier = titre ? titreVersNomFichier(titre, ext) : fichier.name
      const hash_fichier = comparaison?.hash_fichier ?? null
      const jeuAMettreAJour = choixRequis && choix === 'maj' ? comparaison.jeu : null

      const cheminFichier = `${utilisateur.id}/${horodatage()}_${nomFichier}`
      const { error: erreurUpload } = await supabase.storage.from('jeux-donnees').upload(cheminFichier, fichier)
      if (erreurUpload) { setErreur(erreurUpload.message); setChargement(false); return }

      let jeuId

      if (jeuAMettreAJour) {
        // Mise à jour : on remplace le fichier du même format, on garde les autres formats
        jeuId = jeuAMettreAJour.id
        await supabase.from('jeux_de_donnees').update({ titre, description, source, categorie_id: categorieId || null, hash_fichier, mis_a_jour_le: new Date().toISOString() }).eq('id', jeuId)
        const { data: anciensFichiers } = await supabase.from('fichiers').select('id, format, chemin_stockage').eq('jeu_de_donnees_id', jeuId)
        const ancienMemeFormat = anciensFichiers?.find(f => f.format === ext)
        if (ancienMemeFormat) {
          await supabase.from('fichiers').update({ nom_fichier: nomFichier, chemin_stockage: cheminFichier, taille: fichier.size }).eq('id', ancienMemeFormat.id)
          if (ancienMemeFormat.chemin_stockage) {
            await supabase.storage.from('jeux-donnees').remove([ancienMemeFormat.chemin_stockage])
          }
        } else {
          await supabase.from('fichiers').insert({ nom_fichier: nomFichier, chemin_stockage: cheminFichier, format: ext, taille: fichier.size, jeu_de_donnees_id: jeuId })
        }
      } else {
        // Nouveau jeu de données
        const { data: jeu, error: erreurJeu } = await supabase.from('jeux_de_donnees').insert({ titre, description, source, categorie_id: categorieId || null, utilisateur_id: utilisateur.id, hash_fichier, visible: true }).select().single()
        if (erreurJeu) { setErreur(erreurJeu.message); setChargement(false); return }
        jeuId = jeu.id
        await supabase.from('fichiers').insert({ nom_fichier: nomFichier, chemin_stockage: cheminFichier, format: ext, taille: fichier.size, jeu_de_donnees_id: jeuId })
      }

      await supabase.from('analyses').upsert({ fichier_id: jeuId, statut: 'en_attente' }, { onConflict: 'fichier_id' })
      const formAnalyse = new FormData()
      formAnalyse.append('fichier', fichier)
      fetch(`${import.meta.env.VITE_API_URL}/analyser?fichier_id=${jeuId}`, { method: 'POST', body: formAnalyse }).catch(() => {})

      onFermer()
      navigate(`/donnees/${jeuId}`)
    } catch {
      setErreur('Une erreur est survenue.')
      setChargement(false)
    }
  }

  const classeBoutonChoix = (actif) =>
    `flex-1 text-xs font-medium px-3 py-2 rounded-lg border transition-colors ${actif
      ? 'bg-principal border-principal text-texte-inverse'
      : 'bg-fond border-bordure-bleu text-texte-principal-fonce hover:bg-fond-bleu-pale'}`

  return (
    <form onSubmit={publier} className="p-5 space-y-4">
      <div onClick={() => inputRef.current.click()} onDragOver={e => e.preventDefault()} onDrop={e => { e.preventDefault(); choisirFichier(e.dataTransfer.files[0]) }}
        className="border-2 border-dashed border-bordure-bleu rounded-xl p-6 text-center cursor-pointer hover:bg-fond-bleu-clair transition-colors">
        <input ref={inputRef} type="file" accept=".csv,.xlsx,.xls,.json" className="hidden"
          onClick={e => { e.target.value = '' }} onChange={e => choisirFichier(e.target.files[0])} />
        {fichier ? (
          <div className="flex items-center justify-center gap-2 text-texte-principal-fonce font-medium text-sm">
            <CheckCircle size={18} />{fichier.name}
          </div>
        ) : (
          <div className="text-texte-discret">
            <Upload size={28} className="mx-auto mb-2" />
            <p className="text-sm">Glissez un fichier ou cliquez pour choisir</p>
            <p className="text-xs mt-1">CSV, Excel, JSON</p>
          </div>
        )}
      </div>

      <p className="text-xs text-texte-discret text-center -mt-2">
        Formats acceptés : CSV, Excel (.xlsx, .xls), JSON · Taille maximale : {TAILLE_MAX_MO} Mo
      </p>

      {erreurFichier && (
        <div className="flex gap-2 bg-fond-erreur border border-bordure-erreur rounded-xl px-3 py-2">
          <XCircle size={16} className="text-texte-erreur-vif shrink-0 mt-0.5" />
          <p className="text-xs text-texte-erreur-tres-fonce">{erreurFichier}</p>
        </div>
      )}

      {!fichier && (
        <p className="text-xs text-texte-doux text-center">
          💡 Vous avez modifié un fichier déjà publié ? Déposez simplement la nouvelle version : nous la reconnaîtrons automatiquement.
        </p>
      )}

      {analyse && <p className="text-sm text-principal text-center">Analyse en cours...</p>}

      {bloque && (
        <div className="bg-fond-erreur border border-bordure-erreur rounded-xl px-3 py-3 space-y-2">
          <div className="flex gap-2">
            <XCircle size={16} className="text-texte-erreur-vif shrink-0 mt-0.5" />
            <p className="text-xs text-texte-erreur-tres-fonce">
              Vous avez déjà publié ce fichier : <strong>« {comparaison.jeu?.titre} »</strong>. Les doublons ne sont pas acceptés.
            </p>
          </div>
          <button type="button" onClick={annuler}
            className="w-full text-xs font-medium px-3 py-2 rounded-lg border border-bordure-erreur-forte text-texte-erreur-fonce bg-fond hover:bg-fond-erreur-survol">
            Annuler
          </button>
        </div>
      )}

      {resultat === 'identique_autre_format' && (
        <div className="bg-fond-bleu-clair border border-bordure-bleu-clair rounded-xl px-3 py-3 space-y-2">
          <div className="flex gap-2">
            <Info size={16} className="text-texte-bleu-vif shrink-0 mt-0.5" />
            <p className="text-xs text-texte-bleu-fonce">
              Ce fichier a le même contenu que votre jeu <strong>« {comparaison.jeu?.titre} »</strong>. Il sera ajouté au format {NOMS_FORMATS[extension] ?? extension?.toUpperCase()}.
            </p>
          </div>
          <div className="flex gap-2">
            <button type="button" onClick={() => choisir('maj')} className={classeBoutonChoix(choix === 'maj')}>Ajouter à ce jeu</button>
            <button type="button" onClick={annuler} className={classeBoutonChoix(false)}>Annuler</button>
          </div>
        </div>
      )}

      {resultat === 'nouvelle_version' && (
        <div className="bg-fond-bleu-clair border border-bordure-bleu-clair rounded-xl px-3 py-3 space-y-2">
          <div className="flex gap-2">
            <Info size={16} className="text-texte-bleu-vif shrink-0 mt-0.5" />
            <p className="text-xs text-texte-bleu-fonce">
              Ce fichier ressemble à votre jeu <strong>« {comparaison.jeu?.titre} »</strong> ({Math.round(comparaison.pct_lignes)} % de lignes identiques).
            </p>
          </div>
          <div className="flex gap-2">
            <button type="button" onClick={() => choisir('maj')} className={classeBoutonChoix(choix === 'maj')}>Mettre à jour ce jeu</button>
            <button type="button" onClick={() => choisir('nouveau')} className={classeBoutonChoix(choix === 'nouveau')}>Publier comme nouveau jeu</button>
          </div>
        </div>
      )}

      {avertissementGlobal && (
        <div className="flex gap-2 bg-fond-bleu-clair border border-bordure-bleu-pale rounded-xl px-3 py-2">
          <AlertTriangle size={16} className="text-principal shrink-0 mt-0.5" />
          <p className="text-xs text-texte-bleu-nuit">{avertissementGlobal}</p>
        </div>
      )}

      <div>
        <label className="block text-sm font-medium mb-1">Titre *</label>
        <input value={titre} onChange={e => setTitre(e.target.value)} required
          className="w-full border border-bordure-champ rounded-lg px-4 py-2 text-sm focus:outline-none focus:border-bordure-focus" />
        {titre && <p className="text-xs text-texte-discret mt-1">Ce titre sera utilisé comme nom du fichier sur la plateforme.</p>}
      </div>

      <div>
        <label className="block text-sm font-medium mb-1">Description *</label>
        <textarea value={description} onChange={e => setDescription(e.target.value)} rows={2} required
          className="w-full border border-bordure-champ rounded-lg px-4 py-2 text-sm focus:outline-none focus:border-bordure-focus" />
      </div>

      <div className="grid grid-cols-2 gap-3">
        <div>
          <label className="block text-sm font-medium mb-1">Source</label>
          <input value={source} onChange={e => setSource(e.target.value)}
            className="w-full border border-bordure-champ rounded-lg px-4 py-2 text-sm focus:outline-none focus:border-bordure-focus" />
        </div>
        <div>
          <label className="block text-sm font-medium mb-1">Catégorie *</label>
          <select value={categorieId} onChange={e => setCategorieId(e.target.value)} required
            className="w-full border border-bordure-champ rounded-lg px-4 py-2 text-sm focus:outline-none focus:border-bordure-focus bg-fond">
            <option value="">-- Choisir --</option>
            {categories.map(c => <option key={c.id} value={String(c.id)}>{c.nom}</option>)}
          </select>
        </div>
      </div>

      {erreur && <p className="text-texte-erreur text-sm">{erreur}</p>}

      <button type="submit" disabled={!peutPublier}
        className="w-full bg-principal hover:bg-principal-survol disabled:opacity-50 text-texte-inverse py-3 rounded-lg font-medium text-sm">
        {chargement ? 'Publication...' : verification ? 'Vérification...' : 'Publier'}
      </button>
    </form>
  )
}

// ─── Modal principal ──────────────────────────────────────────────────────────

export default function BoutonPublier() {
  const { utilisateur } = useAuthentification()
  const [ouvert, setOuvert] = useState(false)
  const [etape, setEtape] = useState('dataset')

  const [vueConnexion, setVueConnexion] = useState('connexion')
  const [emailCo, setEmailCo] = useState('')
  const [mdpCo, setMdpCo] = useState('')
  const [pseudoCo, setPseudoCo] = useState('')
  const [erreurCo, setErreurCo] = useState('')
  const [chargementCo, setChargementCo] = useState(false)
  const [inscriptionReussie, setInscriptionReussie] = useState(false)
  const [reinitReussie, setReinitReussie] = useState(false)
  const [mdpVisible, setMdpVisible] = useState(false)

  function ouvrir() {
    if (!utilisateur) {
      setEtape('non_connecte')
      setVueConnexion('connexion')
      setEmailCo('')
      setMdpCo('')
      setPseudoCo('')
      setErreurCo('')
      setMdpVisible(false)
      setInscriptionReussie(false)
    } else {
      setEtape('dataset')
    }
    setOuvert(true)
  }

  function fermer() {
    setOuvert(false)
    setEtape('dataset')
  }

  function changerVueCo(v) {
    setVueConnexion(v)
    setEmailCo('')
    setMdpCo('')
    setPseudoCo('')
    setErreurCo('')
    setMdpVisible(false)
    setReinitReussie(false)
  }

  async function connecterDepuisPublier(e) {
    e.preventDefault()
    setErreurCo('')
    setChargementCo(true)
    const { error } = await supabase.auth.signInWithPassword({ email: emailCo, password: mdpCo })
    setChargementCo(false)
    if (error) { setErreurCo(traduireErreurAuth(error.message)); return }
    setEtape('dataset')
  }

  async function reinitialiserDepuisPublier(e) {
    e.preventDefault()
    setErreurCo('')
    setChargementCo(true)
    const { error } = await supabase.auth.resetPasswordForEmail(emailCo, {
      redirectTo: `${window.location.origin}/reinitialisation-mdp`,
    })
    setChargementCo(false)
    if (error) { setErreurCo(traduireErreurAuth(error.message)); return }
    setReinitReussie(true)
  }

  async function inscrireDepuisPublier(e) {
    e.preventDefault()
    setErreurCo('')
    const probleme = verifierInscription(pseudoCo, emailCo, mdpCo)
    if (probleme) { setErreurCo(probleme); return }
    setChargementCo(true)
    const { error } = await supabase.auth.signUp({
      email: emailCo.trim(),
      password: mdpCo,
      options: { data: { pseudo: pseudoCo }, emailRedirectTo: window.location.origin },
    })
    if (error) { setChargementCo(false); setErreurCo(traduireErreurAuth(error.message)); return }
    setChargementCo(false)
    setInscriptionReussie(true)
  }

  return (
    <>
      <button onClick={ouvrir}
        className="flex items-center gap-2 bg-bouton-publier hover:bg-bouton-publier-survol text-texte-inverse px-4 py-2 rounded-lg text-sm font-medium">
        <Plus size={16} />
        Publier sur OpenData
      </button>

      {ouvert && (
        <div className="fixed inset-0 bg-voile/50 z-50 flex items-center justify-center p-4" onClick={fermer}>
          <div className="bg-fond rounded-2xl w-full max-w-lg max-h-[90vh] overflow-y-auto"
            onClick={e => e.stopPropagation()}>

            <div className="flex items-center justify-between p-5 border-b border-bordure-legere">
              <div>
                <h2 className="font-bold text-lg">Publier sur OpenData</h2>
              </div>
              <button onClick={fermer} className="text-texte-discret hover:text-texte-secondaire ml-auto">
                <X size={20} />
              </button>
            </div>

            {etape === 'non_connecte' && (
              <div className="p-5">
                {vueConnexion === 'connexion' && (
                  <form onSubmit={connecterDepuisPublier} className="space-y-4">
                    <p className="text-sm text-texte-doux">Connectez-vous pour publier sur OpenData.</p>
                    <div>
                      <label className="block text-sm font-medium mb-1">Email</label>
                      <input type="email" value={emailCo} onChange={e => setEmailCo(e.target.value)} required placeholder="nom@gmail.com"
                        className="w-full border border-bordure-champ rounded-lg px-4 py-3 focus:outline-none focus:border-bordure-focus" />
                    </div>
                    <div>
                      <div className="flex items-center justify-between mb-1">
                        <label className="block text-sm font-medium">Mot de passe</label>
                        <button type="button" onClick={() => changerVueCo('mot_de_passe_oublie')}
                          className="text-xs text-principal hover:underline">Mot de passe oublié ?</button>
                      </div>
                      <div className="relative">
                        <input type={mdpVisible ? 'text' : 'password'} value={mdpCo} onChange={e => setMdpCo(e.target.value)} required placeholder="Votre mot de passe"
                          className="w-full border border-bordure-champ rounded-lg px-4 py-3 pr-11 focus:outline-none focus:border-bordure-focus" />
                        <button type="button" onClick={() => setMdpVisible(v => !v)}
                          className="absolute right-3 top-1/2 -translate-y-1/2 text-texte-discret hover:text-texte-secondaire">
                          <IcôneOeil visible={mdpVisible} />
                        </button>
                      </div>
                    </div>
                    {erreurCo && <p className="text-texte-erreur text-sm">{erreurCo}</p>}
                    <button type="submit" disabled={chargementCo}
                      className="w-full bg-principal hover:bg-principal-survol disabled:opacity-60 text-texte-inverse py-3 rounded-lg font-medium">
                      {chargementCo ? 'Connexion...' : 'Se connecter'}
                    </button>
                    <p className="text-center text-sm text-texte-doux">
                      Pas encore de compte ?{' '}
                      <button type="button" onClick={() => changerVueCo('inscription')}
                        className="text-principal font-medium hover:underline">S'inscrire</button>
                    </p>
                  </form>
                )}

                {vueConnexion === 'mot_de_passe_oublie' && (
                  reinitReussie ? (
                    <div className="text-center py-4">
                      <p className="font-semibold text-texte mb-2">Email envoyé</p>
                      <p className="text-texte-doux text-sm">
                        Un lien de réinitialisation a été envoyé à <strong>{emailCo}</strong>. Vérifiez votre boîte de réception.
                      </p>
                      <button type="button" onClick={() => changerVueCo('connexion')} className="mt-4 text-sm text-principal hover:underline">
                        Retour à la connexion
                      </button>
                    </div>
                  ) : (
                    <form onSubmit={reinitialiserDepuisPublier} className="space-y-4">
                      <p className="text-sm text-texte-doux">Entrez votre adresse email et nous vous enverrons un lien pour réinitialiser votre mot de passe.</p>
                      <div>
                        <label className="block text-sm font-medium mb-1">Email</label>
                        <input type="email" value={emailCo} onChange={e => setEmailCo(e.target.value)} required placeholder="nom@gmail.com"
                          className="w-full border border-bordure-champ rounded-lg px-4 py-3 focus:outline-none focus:border-bordure-focus" />
                      </div>
                      {erreurCo && <p className="text-texte-erreur text-sm">{erreurCo}</p>}
                      <button type="submit" disabled={chargementCo}
                        className="w-full bg-principal hover:bg-principal-survol disabled:opacity-60 text-texte-inverse py-3 rounded-lg font-medium">
                        {chargementCo ? 'Envoi...' : 'Envoyer le lien'}
                      </button>
                      <p className="text-center text-sm text-texte-doux">
                        <button type="button" onClick={() => changerVueCo('connexion')} className="text-principal font-medium hover:underline">
                          Retour à la connexion
                        </button>
                      </p>
                    </form>
                  )
                )}

                {vueConnexion === 'inscription' && (
                  inscriptionReussie ? (
                    <div className="text-center py-4">
                      <p className="font-semibold text-texte mb-2">Vérifiez votre email</p>
                      <p className="text-texte-doux text-sm">
                        Un lien de confirmation a été envoyé à <strong>{emailCo}</strong>.
                      </p>
                      <button onClick={fermer} className="mt-4 text-sm text-principal hover:underline">Fermer</button>
                    </div>
                  ) : (
                    <form onSubmit={inscrireDepuisPublier} className="space-y-4">
                      <p className="text-sm text-texte-doux">Créez un compte pour publier sur OpenData.</p>
                      <div>
                        <label className="block text-sm font-medium mb-1">Pseudo</label>
                        <input type="text" value={pseudoCo} onChange={e => setPseudoCo(e.target.value)} required
                          placeholder="Ex. : data_analyst225"
                          className="w-full border border-bordure-champ rounded-lg px-4 py-3 focus:outline-none focus:border-bordure-focus" />
                      </div>
                      <div>
                        <label className="block text-sm font-medium mb-1">Email</label>
                        <input type="email" value={emailCo} onChange={e => setEmailCo(e.target.value)} required placeholder="nom@gmail.com"
                          className="w-full border border-bordure-champ rounded-lg px-4 py-3 focus:outline-none focus:border-bordure-focus" />
                      </div>
                      <div>
                        <label className="block text-sm font-medium mb-1">Mot de passe</label>
                        <div className="relative">
                          <input type={mdpVisible ? 'text' : 'password'} value={mdpCo} onChange={e => setMdpCo(e.target.value)} required placeholder="6 caractères minimum"
                            className="w-full border border-bordure-champ rounded-lg px-4 py-3 pr-11 focus:outline-none focus:border-bordure-focus" />
                          <button type="button" onClick={() => setMdpVisible(v => !v)}
                            className="absolute right-3 top-1/2 -translate-y-1/2 text-texte-discret hover:text-texte-secondaire">
                            <IcôneOeil visible={mdpVisible} />
                          </button>
                        </div>
                      </div>
                      {erreurCo && <p className="text-texte-erreur text-sm">{erreurCo}</p>}
                      <button type="submit" disabled={chargementCo}
                        className="w-full bg-principal hover:bg-principal-survol disabled:opacity-60 text-texte-inverse py-3 rounded-lg font-medium">
                        {chargementCo ? 'Inscription...' : "S'inscrire"}
                      </button>
                      <p className="text-center text-sm text-texte-doux">
                        Déjà un compte ?{' '}
                        <button type="button" onClick={() => changerVueCo('connexion')}
                          className="text-principal font-medium hover:underline">Se connecter</button>
                      </p>
                    </form>
                  )
                )}
              </div>
            )}

            {etape === 'dataset' && <FormulaireDataset onFermer={fermer} />}
          </div>
        </div>
      )}
    </>
  )
}