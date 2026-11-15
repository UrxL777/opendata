import { useEffect, useState, useRef, useCallback } from 'react'
import { useParams, Link } from 'react-router-dom'
import { Download, ArrowLeft, PanelLeftOpen, MessageCircle, X, Maximize2, Minimize2 } from 'lucide-react'
import { supabase } from '../supabase'
import { IconeCategorie } from '../utilitaires/iconeCategorie'
import PanneauChat from '../composants/PanneauChat'

function formaterTaille(octets) {
  if (!octets) return '—'
  if (octets < 1024) return `${octets} o`
  if (octets < 1024 * 1024) return `${(octets / 1024).toFixed(1)} Ko`
  return `${(octets / 1024 / 1024).toFixed(1)} Mo`
}

function RapportEnAttente() {
  useEffect(() => {
    const minuterie = setTimeout(() => {
      window.location.reload()
    }, 30000)
    return () => clearTimeout(minuterie)
  }, [])

  return (
    <div className="bg-fond-bleu-clair border border-bordure-bleu-clair rounded-2xl p-5 mb-6">
      <div className="flex items-center gap-3 mb-2">
        <div className="w-2 h-2 bg-accent-doux rounded-full animate-pulse" />
        <h2 className="font-semibold text-texte-bleu-fonce">Analyse en préparation</h2>
      </div>
      <p className="text-sm text-texte-principal-fonce">
        Ce jeu de données est en cours de traitement. Le rapport sera disponible dans quelques instants — cette page se met à jour automatiquement.
      </p>
    </div>
  )
}

function RapportNettoyage({ jeuId }) {
  const [rapport, setRapport] = useState(null)
  const [charge, setCharge] = useState(true)

  useEffect(() => {
    async function charger() {
      if (!jeuId) { setCharge(false); return }
      const { data } = await supabase
        .from('analyses')
        .select('resultats')
        .eq('fichier_id', jeuId)
        .eq('statut', 'termine')
        .maybeSingle()
      if (data?.resultats?.rapport) setRapport(data.resultats.rapport)
      setCharge(false)
    }
    charger()
  }, [jeuId])

  if (charge) return null
  if (!rapport) return <RapportEnAttente />

  const { lignes_avant, lignes_apres, lignes_supprimees, nb_colonnes, operations } = rapport

  return (
    <div className="bg-fond-bleu-clair border border-bordure-bleu-pale rounded-2xl p-5 mb-6">
      <h2 className="font-semibold text-texte-bleu-nuit mb-3">Rapport de nettoyage</h2>
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 mb-4 text-center">
        <div className="bg-fond rounded-xl p-3">
          <p className="text-lg font-bold text-texte">{lignes_avant}</p>
          <p className="text-xs text-texte-discret mt-0.5">lignes au départ</p>
        </div>
        <div className="bg-fond rounded-xl p-3">
          <p className="text-lg font-bold text-principal">{lignes_apres}</p>
          <p className="text-xs text-texte-discret mt-0.5">lignes conservées</p>
        </div>
        <div className="bg-fond rounded-xl p-3">
          <p className="text-lg font-bold text-texte-bleu-nuit">{lignes_supprimees}</p>
          <p className="text-xs text-texte-discret mt-0.5">lignes supprimées</p>
        </div>
        {nb_colonnes != null && (
          <div className="bg-fond rounded-xl p-3">
            <p className="text-lg font-bold text-principal">{nb_colonnes}</p>
            <p className="text-xs text-texte-discret mt-0.5">colonnes</p>
          </div>
        )}
      </div>
      {operations?.length > 0 && (
        <div>
          <p className="text-sm font-medium text-texte-bleu-nuit mb-2">Ce qui a été nettoyé :</p>
          <ul className="space-y-1">
            {operations.map((op, i) => (
              <li key={i} className="text-sm text-texte-principal-fonce flex gap-2">
                <span className="text-texte-puce mt-0.5">•</span>
                <span>{op}</span>
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  )
}

export default function Detail() {
  const { id } = useParams()
  const [jeu, setJeu] = useState(null)
  const [chargement, setChargement] = useState(true)
  const [panneauOuvert, setPanneauOuvert] = useState(true)
  const [pleinEcran, setPleinEcran] = useState(false)
  const [largeurPanneau, setLargeurPanneau] = useState(340)
  const [estMobile, setEstMobile] = useState(window.innerWidth < 768)
  const [sheetOuverte, setSheetOuverte] = useState(false)
  const [sheetPleinEcran, setSheetPleinEcran] = useState(false)
  const enRedimensionnement = useRef(false)
  const largeurDepart = useRef(0)
  const xDepart = useRef(0)

  useEffect(() => {
    const gerer = () => setEstMobile(window.innerWidth < 768)
    window.addEventListener('resize', gerer)
    return () => window.removeEventListener('resize', gerer)
  }, [])

  useEffect(() => {
    async function charger() {
      const { data } = await supabase
        .from('jeux_de_donnees')
        .select('*, categories(nom, description), fichiers(*)')
        .eq('id', id)
        .single()
      setJeu(data)
      setChargement(false)
    }
    charger()
  }, [id])

  const demarrerRedimensionnement = useCallback((e) => {
    enRedimensionnement.current = true
    xDepart.current = e.clientX
    largeurDepart.current = largeurPanneau
    e.preventDefault()
  }, [largeurPanneau])

  useEffect(() => {
    function deplacerSouris(e) {
      if (!enRedimensionnement.current) return
      const delta = e.clientX - xDepart.current
      const nouvelleLargeur = Math.min(600, Math.max(240, largeurDepart.current + delta))
      setLargeurPanneau(nouvelleLargeur)
    }
    function relacherSouris() {
      enRedimensionnement.current = false
    }
    window.addEventListener('mousemove', deplacerSouris)
    window.addEventListener('mouseup', relacherSouris)
    return () => {
      window.removeEventListener('mousemove', deplacerSouris)
      window.removeEventListener('mouseup', relacherSouris)
    }
  }, [])

  async function telecharger(fichier) {
    const { data } = supabase.storage.from('jeux-donnees').getPublicUrl(fichier.chemin_stockage)
    window.open(data.publicUrl, '_blank')
    await supabase.rpc('compt_tel', { id_fichier: fichier.id })
  }

  if (chargement) return <p className="text-center py-16 text-texte-discret">Chargement...</p>
  if (!jeu) return <p className="text-center py-16 text-texte-discret">Jeu de données introuvable.</p>

  const hauteurContenu = 'calc(100vh - 64px)'

  const contenuPrincipal = (
    <main className="max-w-4xl mx-auto px-4 py-10">
      <Link to="/donnees" className="flex items-center gap-1 text-sm text-texte-doux hover:text-principal mb-6">
        <ArrowLeft size={16} /> Retour au catalogue
      </Link>

      <div className="flex gap-4 mb-6">
        <div className="bg-fond-bleu-clair p-3 rounded-xl shrink-0 h-fit">
          <IconeCategorie taille={28} className="text-principal" />
        </div>
        <div>
          <h1 className="text-2xl font-extrabold text-texte-titre">{jeu.titre}</h1>
          {jeu.categories && (
            <span className="text-xs bg-fond-gris text-texte-secondaire px-2 py-0.5 rounded-full">{jeu.categories.nom}</span>
          )}
        </div>
      </div>

      {jeu.description && (
        <div className="bg-fond-doux rounded-2xl p-5 mb-6">
          <h2 className="font-semibold text-texte-moyen mb-1">Description</h2>
          <p className="text-texte-secondaire text-sm">{jeu.description}</p>
        </div>
      )}

      <RapportNettoyage jeuId={jeu.id} />

      <div className="grid grid-cols-2 sm:grid-cols-3 gap-4 mb-8 text-sm">
        {jeu.source && (
          <div className="bg-fond border border-bordure-legere rounded-xl p-4">
            <p className="text-texte-discret text-xs mb-1">Source</p>
            <p className="font-medium">{jeu.source}</p>
          </div>
        )}
        <div className="bg-fond border border-bordure-legere rounded-xl p-4">
          <p className="text-texte-discret text-xs mb-1">Mis à jour le</p>
          <p className="font-medium">{new Date(jeu.mis_a_jour_le ?? jeu.cree_le).toLocaleDateString('fr-FR')}</p>
        </div>
        {jeu.categories && (
          <div className="bg-fond border border-bordure-legere rounded-xl p-4">
            <p className="text-texte-discret text-xs mb-1">Catégorie</p>
            <p className="font-medium">{jeu.categories.nom}</p>
          </div>
        )}
      </div>

      <h2 className="font-bold text-texte-titre mb-3">Fichiers disponibles</h2>
      <div className="space-y-3 mb-8">
        {jeu.fichiers?.map((fichier) => (
          <div key={fichier.id} className="bg-fond border border-bordure-legere rounded-2xl p-4 flex items-center justify-between gap-4">
            <div>
              <p className="font-medium text-texte-titre text-sm">{fichier.nom_fichier}</p>
              <div className="flex gap-3 text-xs text-texte-discret mt-1">
                <span className="bg-fond-bleu-clair text-principal px-2 py-0.5 rounded uppercase font-medium">{fichier.format}</span>
                <span>{formaterTaille(fichier.taille)}</span>
                <span>{fichier.telechargements ?? 0} téléchargements</span>
              </div>
            </div>
            <button
              onClick={() => telecharger(fichier)}
              className="flex items-center gap-1 bg-principal hover:bg-principal-survol text-texte-inverse text-sm px-4 py-2 rounded-lg shrink-0"
            >
              <Download size={16} /> Télécharger
            </button>
          </div>
        ))}
      </div>
    </main>
  )

  if (estMobile) {
    return (
      <div className="relative" style={{ minHeight: hauteurContenu }}>
        <div className="overflow-y-auto" style={{ height: hauteurContenu, paddingBottom: '80px' }}>
          {contenuPrincipal}
        </div>

        {!sheetOuverte && (
          <button
            onClick={() => setSheetOuverte(true)}
            className="fixed bottom-6 right-4 flex items-center gap-2 bg-principal text-texte-inverse px-4 py-3 rounded-full shadow-lg text-sm font-semibold z-40"
          >
            <MessageCircle size={16} />
            Atlas
          </button>
        )}

        {sheetOuverte && !sheetPleinEcran && (
          <div className="fixed inset-0 bg-voile/30 z-40" onClick={() => setSheetOuverte(false)} />
        )}

        {sheetOuverte && (
          <div
            className="fixed left-0 right-0 bg-fond z-50 flex flex-col transition-all duration-300"
            style={{
              bottom: 0,
              height: sheetPleinEcran ? '100%' : '72%',
              borderRadius: sheetPleinEcran ? '0' : '16px 16px 0 0',
            }}
          >
            {!sheetPleinEcran && (
              <div className="flex justify-center pt-2 pb-1 shrink-0">
                <div className="w-9 h-1 bg-poignee rounded-full" />
              </div>
            )}
            <div className="flex items-center gap-3 px-4 py-3 border-b border-bordure shrink-0">
              <div className="bg-principal rounded-xl p-2">
                <MessageCircle size={16} className="text-texte-inverse" />
              </div>
              <div className="flex-1">
                <p className="font-semibold text-texte text-sm">Atlas</p>
                <p className="text-xs text-texte-discret">Questions sur ce jeu de données</p>
              </div>
              <button
                onClick={() => setSheetPleinEcran(!sheetPleinEcran)}
                className="p-1.5 rounded-lg hover:bg-fond-gris transition-colors mr-1"
              >
                {sheetPleinEcran
                  ? <Minimize2 size={16} className="text-texte-doux" />
                  : <Maximize2 size={16} className="text-texte-doux" />
                }
              </button>
              <button
                onClick={() => { setSheetOuverte(false); setSheetPleinEcran(false) }}
                className="p-1.5 rounded-lg hover:bg-fond-gris transition-colors"
              >
                <X size={16} className="text-texte-doux" />
              </button>
            </div>
            <div className="flex-1 min-h-0">
              <PanneauChat jeuId={id} estMobile={true} afficherHeader={false} />
            </div>
          </div>
        )}
      </div>
    )
  }

  return (
    <div className="flex" style={{ height: hauteurContenu }}>
      {panneauOuvert && (
        <div
          className="flex flex-col border-r border-bordure bg-fond shrink-0 overflow-hidden transition-all duration-200"
          style={{ width: pleinEcran ? '100%' : largeurPanneau, height: '100%' }}
        >
          <div className="flex items-center justify-end gap-1 px-2 pt-2 shrink-0">
            <button
              onClick={() => setPleinEcran(!pleinEcran)}
              className="p-1.5 rounded-lg hover:bg-fond-gris transition-colors"
            >
              {pleinEcran
                ? <Minimize2 size={15} className="text-texte-discret" />
                : <Maximize2 size={15} className="text-texte-discret" />
              }
            </button>
            <button
              onClick={() => { setPanneauOuvert(false); setPleinEcran(false) }}
              className="p-1.5 rounded-lg hover:bg-fond-gris transition-colors"
            >
              <X size={15} className="text-texte-discret" />
            </button>
          </div>
          <div className="flex-1 min-h-0">
            <PanneauChat jeuId={id} estMobile={false} />
          </div>
        </div>
      )}

      {panneauOuvert && !pleinEcran && (
        <div
          onMouseDown={demarrerRedimensionnement}
          className="w-1 cursor-col-resize bg-fond-gris-moyen hover:bg-accent-doux transition-colors shrink-0"
          style={{ height: '100%' }}
        />
      )}

      {!pleinEcran && (
        <div className="flex-1 overflow-y-auto">
          {!panneauOuvert && (
            <div className="px-4 pt-4">
              <button
                onClick={() => setPanneauOuvert(true)}
                className="flex items-center gap-1.5 text-xs text-texte-doux hover:text-texte border border-bordure rounded-lg px-2 py-1.5 transition-colors"
              >
                <PanelLeftOpen size={14} />
                Ouvrir Atlas
              </button>
            </div>
          )}
          {contenuPrincipal}
        </div>
      )}
    </div>
  )
}