import { useEffect, useState } from 'react'
import { useParams, Link } from 'react-router-dom'
import { Download, ArrowLeft, ChartColumnBig } from 'lucide-react'
import { supabase } from '../supabase'
import { IconeCategorie } from '../utilitaires/iconeCategorie'

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

  async function telecharger(fichier) {
    const { data } = supabase.storage.from('jeux-donnees').getPublicUrl(fichier.chemin_stockage)
    window.open(data.publicUrl, '_blank')
    await supabase.rpc('compt_tel', { id_fichier: fichier.id })
  }

  if (chargement) return <p className="text-center py-16 text-texte-discret">Chargement...</p>
  if (!jeu) return <p className="text-center py-16 text-texte-discret">Jeu de données introuvable.</p>

  return (
    <main className="max-w-4xl mx-auto px-4 py-10">
      <Link to="/donnees" className="flex items-center gap-1 text-sm text-texte-doux hover:text-principal mb-6">
        <ArrowLeft size={16} /> Retour au catalogue
      </Link>

      <div className="flex flex-col sm:flex-row sm:items-start sm:justify-between gap-4 mb-6">
        <div className="flex gap-4">
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
        {/* Le dashboard créé par Atlas pour ce jeu de données (Atlas se trouve sur la page du dashboard) */}
        <Link to={`/dashboards/${jeu.id}`}
          className="flex items-center justify-center gap-2 bg-principal hover:bg-principal-survol text-texte-inverse px-4 py-2.5 rounded-lg text-sm font-medium shrink-0">
          <ChartColumnBig size={16} /> Voir le dashboard
        </Link>
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
              <div className="flex flex-wrap gap-x-3 gap-y-1 text-xs text-texte-discret mt-1">
                <span className="bg-fond-bleu-clair text-principal px-2 py-0.5 rounded uppercase font-medium">{fichier.format}</span>
                <span className="whitespace-nowrap">{formaterTaille(fichier.taille)}</span>
                <span className="whitespace-nowrap">{fichier.telechargements ?? 0} téléchargements</span>
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
}
