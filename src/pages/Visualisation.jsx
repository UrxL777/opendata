import { useEffect, useState } from 'react'
import { supabase } from '../supabase'
import { Search, FileImage } from 'lucide-react'

const CATEGORIES = [
  'Économie', 'Santé', 'Éducation', 'Agriculture', 'Transport',
  'Environnement', 'Démographie', 'Sport', 'Culture', 'Sécurité & Justice'
]

function PanneauAffichage({ visu }) {
  if (!visu) {
    return (
      <div className="flex-1 flex flex-col items-center justify-center bg-gray-50 rounded-xl border border-gray-200 min-h-[300px] md:min-h-[500px]">
        <FileImage size={48} className="text-gray-200 mb-3" />
        <p className="text-gray-400 text-sm">Sélectionnez une visualisation</p>
      </div>
    )
  }

  const estEmbed = !!visu.code_embed
  const estImage = visu.url_fichier && /\.(png|jpg|jpeg|svg)$/i.test(visu.nom_fichier ?? '')
  const estLien  = !!visu.lien_url

  return (
    <div className="flex-1 flex flex-col bg-white rounded-xl border border-gray-200 overflow-hidden min-h-[300px] md:min-h-[500px]">
      {/* En-tête du panneau */}
      <div className="px-4 py-3 border-b border-gray-100">
        <h2 className="font-semibold text-gray-800 text-base">{visu.titre}</h2>
        {visu.categorie && (
          <span className="text-xs text-blue-600 bg-blue-50 px-2 py-0.5 rounded-full mt-1 inline-block">
            {visu.categorie}
          </span>
        )}
      </div>

      {/* Zone graphique */}
      <div className="flex-1 overflow-hidden">
        {estEmbed ? (
          <div
            className="w-full h-full"
            style={{ minHeight: '300px' }}
            dangerouslySetInnerHTML={{ __html: visu.code_embed }}
          />
        ) : estImage ? (
          <img src={visu.url_fichier} alt={visu.titre} className="w-full h-full object-contain p-4" />
        ) : estLien ? (
          <iframe
            src={visu.lien_url}
            title={visu.titre}
            className="w-full h-full border-0"
            style={{ minHeight: '300px' }}
            allowFullScreen
          />
        ) : (
          <div className="flex items-center justify-center h-full text-gray-300 py-10">
            <p className="text-sm">Aucun contenu à afficher</p>
          </div>
        )}
      </div>

      {/* Description */}
      {visu.description && (
        <div className="px-4 py-3 border-t border-gray-100 bg-gray-50">
          <p className="text-xs text-gray-500">{visu.description}</p>
        </div>
      )}
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
    const resultats = data ?? []
    setVisualisations(resultats)
    if (resultats.length > 0) setVisuSelectionnee(resultats[0])
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
      setVisuSelectionnee(visuFiltrees[0] ?? null)
    }
  }, [visuFiltrees])

  return (
    <main className="max-w-7xl mx-auto px-4 py-8">
      <h1 className="text-2xl font-bold mb-6">Visualisations</h1>

      {/* Filtres — empilés sur mobile */}
      <div className="flex flex-col sm:flex-row gap-3 mb-6">
        <div className="relative flex-1">
          <Search size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" />
          <input
            value={recherche}
            onChange={e => setRecherche(e.target.value)}
            placeholder="Rechercher une visualisation..."
            className="w-full pl-9 pr-4 py-2 border border-gray-200 rounded-lg text-sm focus:outline-none focus:border-blue-500"
          />
        </div>
        <select
          value={categorieFiltree}
          onChange={e => setCategorieFiltree(e.target.value)}
          className="border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-blue-500 bg-white"
        >
          <option value="">Toutes les catégories</option>
          {CATEGORIES.map(c => <option key={c} value={c}>{c}</option>)}
        </select>
      </div>

      {chargement ? (
        <p className="text-center text-gray-400 py-16">Chargement...</p>
      ) : visualisations.length === 0 ? (
        <div className="text-center py-16">
          <FileImage size={40} className="mx-auto mb-3 text-gray-200" />
          <p className="text-gray-400 text-sm">Aucune visualisation disponible.</p>
        </div>
      ) : (
        /* Sur mobile : colonne (liste puis viz). Sur desktop : côte à côte */
        <div className="flex flex-col md:flex-row gap-4 items-start">

          {/* Liste — pleine largeur sur mobile, 288px sur desktop */}
          <div className="w-full md:w-72 md:flex-shrink-0 bg-white border border-gray-200 rounded-xl overflow-hidden">
            <div className="px-4 py-3 border-b border-gray-100">
              <p className="text-xs font-medium text-gray-500 uppercase tracking-wide">
                {visuFiltrees.length} visualisation{visuFiltrees.length > 1 ? 's' : ''}
              </p>
            </div>
            {/* Scroll horizontal sur mobile, vertical sur desktop */}
            <ul
              className="overflow-x-auto md:overflow-x-hidden overflow-y-hidden md:overflow-y-auto flex md:flex-col"
              style={{ maxHeight: 'none' }}
            >
              {visuFiltrees.length === 0 ? (
                <li className="px-4 py-8 text-center text-sm text-gray-400 w-full">Aucun résultat</li>
              ) : (
                visuFiltrees.map(v => (
                  <li key={v.id} className="flex-shrink-0 md:flex-shrink w-48 md:w-auto">
                    <button
                      onClick={() => setVisuSelectionnee(v)}
                      className={`w-full text-left px-4 py-3 border-b border-gray-50 transition-colors hover:bg-blue-50 ${
                        visuSelectionnee?.id === v.id
                          ? 'bg-blue-50 border-l-4 border-l-blue-500'
                          : 'border-l-4 border-l-transparent'
                      }`}
                    >
                      <p className="text-sm font-medium text-gray-800 line-clamp-1">{v.titre}</p>
                      {v.categorie && (
                        <p className="text-xs text-blue-500 mt-0.5">{v.categorie}</p>
                      )}
                    </button>
                  </li>
                ))
              )}
            </ul>
          </div>

          {/* Panneau d'affichage */}
          <PanneauAffichage visu={visuSelectionnee} />

        </div>
      )}
    </main>
  )
}