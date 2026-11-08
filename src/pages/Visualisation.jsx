import { useEffect, useRef, useState } from 'react'
import { supabase } from '../supabase'
import { Search, FileImage, Maximize2, ExternalLink } from 'lucide-react'

const CATEGORIES = [
  'Économie', 'Santé', 'Éducation', 'Agriculture', 'Transport',
  'Environnement', 'Démographie', 'Sport', 'Culture', 'Sécurité & Justice'
]

const RATIO_PAR_DEFAUT = 16 / 9

// Lit l'adresse et les proportions d'un code d'intégration <iframe ...>
function lireIframe(code) {
  if (!code) return null
  const doc = new DOMParser().parseFromString(code, 'text/html')
  const iframe = doc.querySelector('iframe')
  const src = iframe?.getAttribute('src')
  if (!src || !/^https:\/\//i.test(src)) return null
  const largeur = parseFloat(iframe.getAttribute('width'))
  const hauteur = parseFloat(iframe.getAttribute('height'))
  const ratio = largeur > 0 && hauteur > 0 ? largeur / hauteur : RATIO_PAR_DEFAUT
  return { src, ratio }
}

// Calcule la plus grande taille qui tient dans l'écran sans défilement, en gardant les proportions
function useTailleAjustee(zoneRef, ratio) {
  const [taille, setTaille] = useState({ largeur: 0, hauteur: 0 })

  useEffect(() => {
    function calculer() {
      const zone = zoneRef.current
      if (!zone) return
      const largeurDispo = zone.clientWidth
      const hauteurDispo = Math.max(200, window.innerHeight - zone.getBoundingClientRect().top - 16)
      let largeur = largeurDispo
      let hauteur = largeur / ratio
      if (hauteur > hauteurDispo) {
        hauteur = hauteurDispo
        largeur = hauteur * ratio
      }
      setTaille({ largeur: Math.floor(largeur), hauteur: Math.floor(hauteur) })
    }
    calculer()
    window.addEventListener('resize', calculer)
    return () => window.removeEventListener('resize', calculer)
  }, [zoneRef, ratio])

  return taille
}

function PanneauAffichage({ visu }) {
  const zoneRef = useRef(null)
  const cadreRef = useRef(null)
  const [ratioImage, setRatioImage] = useState(null)
  const [pleinEcran, setPleinEcran] = useState(false)

  const iframe = lireIframe(visu?.code_embed)
  const estImage = !!visu?.url_fichier && /\.(png|jpg|jpeg|svg)$/i.test(visu.nom_fichier ?? '')
  const estLien = !!visu?.lien_url
  const adresse = iframe?.src ?? (estLien ? visu.lien_url : estImage ? visu.url_fichier : null)
  const ratio = estImage ? (ratioImage ?? RATIO_PAR_DEFAUT) : (iframe?.ratio ?? RATIO_PAR_DEFAUT)
  const taille = useTailleAjustee(zoneRef, ratio)
  const pleinEcranPossible = typeof document !== 'undefined' && document.fullscreenEnabled

  useEffect(() => {
    const suivre = () => setPleinEcran(document.fullscreenElement === cadreRef.current)
    document.addEventListener('fullscreenchange', suivre)
    return () => document.removeEventListener('fullscreenchange', suivre)
  }, [])

  function basculerPleinEcran() {
    if (document.fullscreenElement) document.exitFullscreen()
    else cadreRef.current?.requestFullscreen()
  }

  if (!visu) {
    return (
      <div className="flex flex-col items-center justify-center bg-gray-50 rounded-xl border border-gray-200 min-h-[400px]">
        <FileImage size={48} className="text-gray-200 mb-3" />
        <p className="text-gray-400 text-sm">Sélectionnez un dashboard</p>
      </div>
    )
  }

  const styleCadre = pleinEcran
    ? { width: '100%', height: '100%' }
    : { width: taille.largeur, height: taille.hauteur }

  return (
    <div className="flex flex-col bg-white rounded-xl border border-gray-200 overflow-hidden">
      <div className="px-3 py-2 sm:px-4 sm:py-3 border-b border-gray-100 flex items-start justify-between gap-3">
        <div className="min-w-0">
          <h2 className="font-semibold text-gray-800 text-sm sm:text-base">{visu.titre}</h2>
          <div className="flex flex-wrap items-center gap-2 mt-1">
            {visu.categorie && (
              <span className="text-xs text-blue-600 bg-blue-50 px-2 py-0.5 rounded-full">{visu.categorie}</span>
            )}
            {visu.description && <p className="hidden sm:block text-xs text-gray-500">{visu.description}</p>}
          </div>
        </div>
        <div className="flex items-center gap-2 shrink-0">
          {pleinEcranPossible && (iframe || estLien || estImage) && (
            <button type="button" onClick={basculerPleinEcran}
              title="Plein écran" aria-label="Plein écran"
              className="flex items-center gap-1.5 text-xs text-gray-600 hover:text-blue-600 border border-gray-200 rounded-lg px-2.5 py-1.5">
              <Maximize2 size={14} /> <span className="hidden sm:inline">Plein écran</span>
            </button>
          )}
          {adresse && (
            <a href={adresse} target="_blank" rel="noreferrer"
              title="Ouvrir dans un nouvel onglet" aria-label="Ouvrir dans un nouvel onglet"
              className="flex items-center gap-1.5 text-xs text-gray-600 hover:text-blue-600 border border-gray-200 rounded-lg px-2.5 py-1.5">
              <ExternalLink size={14} /> <span className="hidden sm:inline">Ouvrir</span>
            </a>
          )}
        </div>
      </div>

      <div ref={zoneRef} className="w-full flex justify-center bg-gray-50 p-1 sm:p-2">
        <div ref={cadreRef} style={styleCadre} className="bg-white">
          {iframe || estLien ? (
            <iframe
              src={iframe?.src ?? visu.lien_url}
              title={visu.titre}
              className="w-full h-full border-0"
              allowFullScreen
              sandbox="allow-storage-access-by-user-activation allow-scripts allow-same-origin allow-popups allow-popups-to-escape-sandbox"
            />
          ) : estImage ? (
            <img src={visu.url_fichier} alt={visu.titre} className="w-full h-full object-contain"
              onLoad={e => setRatioImage(e.currentTarget.naturalWidth / e.currentTarget.naturalHeight)} />
          ) : (
            <div className="flex items-center justify-center h-full text-gray-300">
              <p className="text-sm">Aucun contenu à afficher</p>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

export default function Visualisation() {
  const [visualisations, setVisualisations]     = useState([])
  const [recherche, setRecherche]               = useState('')
  const [categorieFiltree, setCategorieFiltree] = useState('')
  const [chargement, setChargement]             = useState(true)
  const [visuSelectionnee, setVisuSelectionnee] = useState(null)

  async function charger() {
    const { data } = await supabase
      .from('visualisations')
      .select('*')
      .order('cree_le', { ascending: false })
    setVisualisations(data ?? [])
    setVisuSelectionnee(null)
    setChargement(false)
  }

  useEffect(() => { charger() }, [])

  const visuFiltrees = visualisations.filter(v => {
    const motCorrespond = v.titre?.toLowerCase().includes(recherche.toLowerCase())
    const catCorrespond = !categorieFiltree || v.categorie === categorieFiltree
    return motCorrespond && catCorrespond
  })

  useEffect(() => {
    if (visuSelectionnee && !visuFiltrees.find(v => v.id === visuSelectionnee.id)) {
      setVisuSelectionnee(null)
    }
  }, [visuFiltrees])

  return (
    <main className="max-w-7xl mx-auto px-4 py-4 sm:py-6">
      <h1 className="text-xl sm:text-2xl font-bold mb-3 sm:mb-4">Dashboards</h1>

      <div className="grid grid-cols-2 gap-2 sm:flex sm:flex-row sm:gap-3 mb-4">
        <div className="relative col-span-2 sm:flex-1">
          <Search size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" />
          <input
            value={recherche}
            onChange={e => setRecherche(e.target.value)}
            placeholder="Rechercher un dashboard..."
            className="w-full pl-9 pr-4 py-2 border border-gray-200 rounded-lg text-sm focus:outline-none focus:border-blue-500"
          />
        </div>
        <select
          value={categorieFiltree}
          onChange={e => setCategorieFiltree(e.target.value)}
          className="min-w-0 border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-blue-500 bg-white"
        >
          <option value="">Toutes les catégories</option>
          {CATEGORIES.map(c => <option key={c} value={c}>{c}</option>)}
        </select>
        <select
          value={visuSelectionnee?.id ?? ''}
          onChange={e => setVisuSelectionnee(visuFiltrees.find(v => String(v.id) === e.target.value) ?? null)}
          className="min-w-0 border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-blue-500 bg-white"
          disabled={visuFiltrees.length === 0}
        >
          <option value="">— Choisir un visuel —</option>
          {visuFiltrees.map(v => <option key={v.id} value={v.id}>{v.titre}</option>)}
        </select>
      </div>

      {chargement ? (
        <p className="text-center text-gray-400 py-16">Chargement...</p>
      ) : visualisations.length === 0 ? (
        <div className="text-center py-16">
          <FileImage size={40} className="mx-auto mb-3 text-gray-200" />
          <p className="text-gray-400 text-sm">Aucun dashboard disponible.</p>
        </div>
      ) : (
        <PanneauAffichage key={visuSelectionnee?.id ?? 'aucun'} visu={visuSelectionnee} />
      )}
    </main>
  )
}