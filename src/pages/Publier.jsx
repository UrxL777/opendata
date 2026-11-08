import { useState, useEffect, useRef } from 'react'
import { useNavigate } from 'react-router-dom'
import { Upload, CheckCircle, AlertTriangle } from 'lucide-react'
import { supabase } from '../supabase'
import { useAuthentification } from '../contexte/Authentification'

// Convertit le titre en nom de fichier propre
function titreVersNomFichier(titre, ext) {
  const base = titre
    .toLowerCase()
    .normalize('NFD').replace(/[\u0300-\u036f]/g, '')
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-+|-+$/g, '')
    .slice(0, 60)
  return `${base}.${ext}`
}

export default function Publier() {
  const { utilisateur } = useAuthentification()
  const navigate = useNavigate()
  const inputRef = useRef()
  const controleurRef = useRef(null)

  const [categories, setCategories] = useState([])
  const [titre, setTitre] = useState('')
  const [description, setDescription] = useState('')
  const [source, setSource] = useState('')
  const [categorieId, setCategorieId] = useState('')
  const [fichier, setFichier] = useState(null)
  const [chargement, setChargement] = useState(false)
  const [analyse, setAnalyse] = useState(false)
  const [erreur, setErreur] = useState('')
  const [avertissementGlobal, setAvertissementGlobal] = useState('')

  useEffect(() => {
    if (!utilisateur) navigate('/connexion')
    supabase.from('categories').select('*').then(({ data }) => setCategories(data ?? []))
  }, [utilisateur])

  async function choisirFichier(f) {
    if (!f) return
    if (controleurRef.current) controleurRef.current.abort()
    setFichier(f)
    setTitre('')
    setDescription('')
    setCategorieId('')
    setErreur('')
    setAvertissementGlobal('')
    setAnalyse(true)
    const controleur = new AbortController()
    controleurRef.current = controleur
    try {
      const form = new FormData()
      form.append('fichier', f)
      const rep = await fetch(`${import.meta.env.VITE_API_URL}/suggerer`, {
        method: 'POST',
        body: form,
        signal: controleur.signal,
      })
      if (rep.ok) {
        const s = await rep.json()
        setTitre(s.titre || '')
        setDescription(s.description || '')
        // Forcer en String pour correspondre aux valeurs du <select>
        if (s.categorie_id) setCategorieId(String(s.categorie_id))
      }
    } catch (err) {
      if (err.name !== 'AbortError') { /* backend pas démarré */ }
    } finally {
      setAnalyse(false)
    }
  }

  async function publier(e) {
    e.preventDefault()
    if (!fichier) { setErreur('Veuillez sélectionner un fichier.'); return }
    if (!description.trim()) { setErreur('La description est obligatoire.'); return}
    setAvertissementGlobal('')
    setChargement(true)

    try {
      // 1. Vérifier doublon
      const formDoublon = new FormData()
      formDoublon.append('fichier', fichier)
      const repDoublon = await fetch(
        `${import.meta.env.VITE_API_URL}/verifier-doublon?utilisateur_id=${utilisateur.id}`,
        { method: 'POST', body: formDoublon }
      )
      const {
        doublon,
        jeu_id: jeuIdExistant,
        hash_fichier,
        doublon_global,
        format_doublon
      } = await repDoublon.json()

      if (doublon_global && format_doublon) {
        setAvertissementGlobal(
          `Un jeu de données similaire existe déjà sur la plateforme en ${format_doublon.toUpperCase()}. Vous pouvez quand même publier le vôtre.`
        )
      }

      const ext = fichier.name.split('.').pop().toLowerCase()
      const nomFichier = titre ? titreVersNomFichier(titre, ext) : fichier.name

      // 2. Si doublon → supprimer l'ancien fichier du storage (même format)
      if (doublon && jeuIdExistant) {
        const { data: ancienFichiers } = await supabase
          .from('fichiers')
          .select('id, chemin_stockage, format')
          .eq('jeu_de_donnees_id', jeuIdExistant)

        const ancienMemFormat = ancienFichiers?.find(f => f.format === ext)
        if (ancienMemFormat?.chemin_stockage) {
          await supabase.storage.from('jeux-donnees').remove([ancienMemFormat.chemin_stockage])
        }
      }

      // 3. Upload avec le nom basé sur le titre
      const cheminFichier = `${utilisateur.id}/${Date.now()}_${nomFichier}`
      const { error: erreurUpload } = await supabase.storage
        .from('jeux-donnees')
        .upload(cheminFichier, fichier)
      if (erreurUpload) { setErreur(erreurUpload.message); setChargement(false); return }

      let jeuId

      if (doublon && jeuIdExistant) {
        jeuId = jeuIdExistant
        await supabase.from('jeux_de_donnees')
          .update({ titre, description, source, categorie_id: categorieId || null, hash_fichier, mis_a_jour_le: new Date().toISOString() })
          .eq('id', jeuId)

        const { data: ancienFichiers } = await supabase
          .from('fichiers')
          .select('id, format')
          .eq('jeu_de_donnees_id', jeuId)

        const ancienMemFormat = ancienFichiers?.find(f => f.format === ext)

        if (ancienMemFormat) {
          await supabase.from('fichiers')
            .update({ nom_fichier: nomFichier, chemin_stockage: cheminFichier, taille: fichier.size })
            .eq('id', ancienMemFormat.id)
        } else {
          await supabase.from('fichiers').insert({
            nom_fichier: nomFichier,
            chemin_stockage: cheminFichier,
            format: ext,
            taille: fichier.size,
            jeu_de_donnees_id: jeuId
          })
        }

      } else {
        const { data: jeu, error: erreurJeu } = await supabase
          .from('jeux_de_donnees')
          .insert({
            titre,
            description,
            source,
            categorie_id: categorieId || null,
            utilisateur_id: utilisateur.id,
            hash_fichier,
            // masqué si un autre utilisateur a déjà publié ce fichier
            visible: true
          })
          .select().single()
        if (erreurJeu) { setErreur(erreurJeu.message); setChargement(false); return }
        jeuId = jeu.id

        await supabase.from('fichiers').insert({
          nom_fichier: nomFichier,
          chemin_stockage: cheminFichier,
          format: ext,
          taille: fichier.size,
          jeu_de_donnees_id: jeuId
        })
      }

      // 4. Lancer l'analyse en arrière-plan
      await supabase.from('analyses').upsert(
        { fichier_id: jeuId, statut: 'en_attente' },
        { onConflict: 'fichier_id' }
      )

      const formAnalyse = new FormData()
      formAnalyse.append('fichier', fichier)
      fetch(`${import.meta.env.VITE_API_URL}/analyser?fichier_id=${jeuId}`, {
        method: 'POST',
        body: formAnalyse,
      }).catch(() => {})

      // 5. Réinitialiser la discussion du jeu republié
      sessionStorage.removeItem(`chat_${jeuId}`)

      navigate(`/donnees/${jeuId}`)

    } catch {
      setErreur('Une erreur est survenue.')
      setChargement(false)
    }
  }

  return (
    <main className="max-w-2xl mx-auto px-4 py-10">
      <h1 className="text-2xl font-bold mb-6">Publier un jeu de données</h1>
      <form onSubmit={publier} className="bg-white border border-gray-200 rounded-2xl p-6 space-y-5">

        <div
          onClick={() => inputRef.current.click()}
          onDragOver={e => e.preventDefault()}
          onDrop={e => { e.preventDefault(); choisirFichier(e.dataTransfer.files[0]) }}
          className="border-2 border-dashed border-blue-300 rounded-xl p-8 text-center cursor-pointer hover:bg-blue-50 transition-colors"
        >
          <input
            ref={inputRef}
            type="file"
            accept=".csv,.xlsx,.xls,.json"
            className="hidden"
            onClick={e => { e.target.value = '' }}
            onChange={e => choisirFichier(e.target.files[0])}
          />
          {fichier ? (
            <div className="flex items-center justify-center gap-2 text-blue-700 font-medium">
              <CheckCircle size={20} />
              {fichier.name}
            </div>
          ) : (
            <div className="text-gray-400">
              <Upload size={32} className="mx-auto mb-2" />
              <p className="text-sm">Glissez un fichier ici ou cliquez pour choisir</p>
              <p className="text-xs mt-1">CSV, Excel, JSON</p>
            </div>
          )}
        </div>

        {analyse && <p className="text-sm text-blue-600 text-center">Analyse en cours...</p>}

        {avertissementGlobal && (
          <div className="flex gap-3 bg-amber-50 border border-amber-200 rounded-xl px-4 py-3">
            <AlertTriangle size={18} className="text-amber-500 shrink-0 mt-0.5" />
            <p className="text-sm text-amber-800">{avertissementGlobal}</p>
          </div>
        )}

        <div>
          <label className="block text-sm font-medium mb-1">Titre *</label>
          <input
            value={titre}
            onChange={e => setTitre(e.target.value)}
            required
            className="w-full border border-gray-300 rounded-lg px-4 py-2 focus:outline-none focus:border-blue-500"
          />
          {titre && (
            <p className="text-xs text-gray-400 mt-1">
              Ce titre sera utilisé comme nom du fichier sur la plateforme. Modifiez-le si nécessaire.
            </p>
          )}
        </div>

        <div>
          <label className="block text-sm font-medium mb-1">Description *</label>
          <textarea value={description} onChange={e => setDescription(e.target.value)} rows={3} className="w-full border border-gray-300 rounded-lg px-4 py-2 focus:outline-none focus:border-blue-500" />
        </div>

        <div className="grid grid-cols-2 gap-4">
          <div>
            <label className="block text-sm font-medium mb-1">Source</label>
            <input value={source} onChange={e => setSource(e.target.value)} className="w-full border border-gray-300 rounded-lg px-4 py-2 focus:outline-none focus:border-blue-500" />
          </div>
          <div>
            <label className="block text-sm font-medium mb-1">Catégorie</label>
            <select value={categorieId} onChange={e => setCategorieId(e.target.value)} className="w-full border border-gray-300 rounded-lg px-4 py-2 focus:outline-none focus:border-blue-500">
              <option value="">-- Choisir --</option>
              {/* String() pour correspondre au categorieId reçu du backend */}
              {categories.map(c => <option key={c.id} value={String(c.id)}>{c.nom}</option>)}
            </select>
          </div>
        </div>

        {erreur && <p className="text-red-600 text-sm">{erreur}</p>}

        <button type="submit" disabled={chargement || !fichier} className="w-full bg-blue-600 hover:bg-blue-700 disabled:opacity-50 text-white py-3 rounded-lg font-medium">
          {chargement ? 'Publication...' : 'Publier'}
        </button>
      </form>
    </main>
  )
}