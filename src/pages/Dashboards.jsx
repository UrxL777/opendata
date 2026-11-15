import { useEffect, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { Search, ChartColumnBig, Loader2, Clock, CircleAlert } from 'lucide-react'
import { supabase } from '../supabase'
import Pagination from '../composants/Pagination'
import { formaterKpi, MESSAGES_STATUT } from '../utilitaires/formatDashboard'

const DASHBOARDS_PAR_PAGE = 10

// Une carte de la galerie : la question centrale et les 3 premiers KPI du dashboard
function CarteDashboard({ jeu, dashboard }) {
  const pret = dashboard.statut === 'termine'
  const IconeStatut = { en_attente: Clock, en_cours: Loader2, erreur: CircleAlert }[dashboard.statut] ?? Clock

  return (
    <Link
      to={`/dashboards/${jeu.id}`}
      className="bg-fond border border-bordure-legere rounded-2xl p-5 flex flex-col gap-3 shadow-sm hover:border-bordure-bleu hover:shadow-md transition"
    >
      <div className="flex gap-3">
        <div className="bg-fond-bleu-clair p-2 rounded-xl shrink-0 h-fit">
          <ChartColumnBig size={20} className="text-principal" />
        </div>
        <div>
          <h3 className="font-bold text-texte-titre">{jeu.titre}</h3>
          <div className="flex items-center gap-2 flex-wrap">
            {jeu.categories && (
              <span className="text-xs bg-fond-gris text-texte-secondaire px-2 py-0.5 rounded-full">{jeu.categories.nom}</span>
            )}
            {jeu.pseudo && (
              <span className="text-xs text-texte-discret">par <span className="font-medium text-texte-secondaire">{jeu.pseudo}</span></span>
            )}
          </div>
          {pret && dashboard.question && (
            <p className="text-sm text-texte-doux mt-1">{dashboard.question}</p>
          )}
        </div>
      </div>

      {pret ? (
        <div className="grid grid-cols-3 gap-2">
          {(dashboard.kpi ?? []).slice(0, 3).map(k => (
            <div key={k.id} className="bg-fond-bleu-clair rounded-xl px-3 py-2">
              <p className="font-bold text-principal">{formaterKpi(k)}</p>
              <p className="text-xs text-texte-doux line-clamp-2">{k.titre}</p>
            </div>
          ))}
        </div>
      ) : (
        <div className="flex items-center gap-2 bg-fond-doux rounded-xl px-4 py-3 text-sm text-texte-secondaire">
          <IconeStatut size={16} className={`text-principal shrink-0 ${dashboard.statut === 'en_cours' ? 'animate-spin' : ''}`} />
          {MESSAGES_STATUT[dashboard.statut] ?? MESSAGES_STATUT.en_attente}
        </div>
      )}
    </Link>
  )
}

export default function Dashboards() {
  const [searchParams, setSearchParams] = useSearchParams()
  const [categories, setCategories] = useState([])
  const [cartes, setCartes] = useState([])
  const [chargement, setChargement] = useState(true)
  const [recherche, setRecherche] = useState('')
  const [pageCourante, setPageCourante] = useState(1)

  const categorieActive = searchParams.get('categorie') ?? ''

  useEffect(() => {
    supabase.from('categories').select('*').then(({ data }) => setCategories(data ?? []))
  }, [])

  useEffect(() => {
    async function charger() {
      let requete = supabase
        .from('vue_jeux_avec_pseudo')
        .select('id, titre, pseudo, cree_le, categorie_id, categories(nom)')
        .order('cree_le', { ascending: false })
        .eq('visible', true)
      if (categorieActive) requete = requete.eq('categorie_id', categorieActive)
      if (recherche) requete = requete.ilike('titre', `%${recherche}%`)

      // Seulement la question centrale et les KPI de chaque dashboard (pas les graphiques : la galerie reste légère)
      const [{ data: jeux }, { data: dashboards }] = await Promise.all([
        requete,
        supabase.from('dashboards').select('jeu_de_donnees_id, statut, question:contenu->comprehension->>question_centrale, kpi:contenu->kpi'),
      ])
      const parJeu = Object.fromEntries((dashboards ?? []).map(d => [String(d.jeu_de_donnees_id), d]))
      setCartes((jeux ?? []).filter(j => parJeu[String(j.id)]).map(j => ({ jeu: j, dashboard: parJeu[String(j.id)] })))
      setPageCourante(1)
      setChargement(false)
    }
    charger()
  }, [categorieActive, recherche])

  function changerCategorie(id) {
    if (id === '') setSearchParams({})
    else setSearchParams({ categorie: id })
    setPageCourante(1)
  }

  const totalPages = Math.ceil(cartes.length / DASHBOARDS_PAR_PAGE)
  const cartesPage = cartes.slice((pageCourante - 1) * DASHBOARDS_PAR_PAGE, pageCourante * DASHBOARDS_PAR_PAGE)

  return (
    <main className="max-w-6xl mx-auto px-4 py-10">
      <h1 className="text-3xl font-extrabold text-texte-titre mb-1">Dashboards</h1>
      <p className="text-texte-doux mb-8">Les dashboards créés automatiquement par Atlas pour chaque jeu de données publié.</p>

      <div className="flex items-center gap-2 border border-bordure rounded-lg px-4 py-2 bg-fond mb-4">
        <Search size={18} className="text-texte-discret" />
        <input
          value={recherche}
          onChange={e => { setRecherche(e.target.value); setPageCourante(1) }}
          placeholder="Rechercher dans les dashboards..."
          className="flex-1 outline-none text-sm"
        />
      </div>

      <div className="mb-8">
        <select
          value={categorieActive}
          onChange={e => changerCategorie(e.target.value)}
          className="border border-bordure-champ rounded-lg px-4 py-2 text-sm focus:outline-none focus:border-bordure-focus bg-fond"
        >
          <option value="">Toutes les catégories</option>
          {categories.map(cat => (
            <option key={cat.id} value={String(cat.id)}>{cat.nom}</option>
          ))}
        </select>
      </div>

      {chargement ? null : cartes.length === 0 ? (
        <p className="text-center text-texte-discret py-16">Aucun dashboard trouvé.</p>
      ) : (
        <>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {cartesPage.map(({ jeu, dashboard }) => <CarteDashboard key={jeu.id} jeu={jeu} dashboard={dashboard} />)}
          </div>
          <Pagination pageCourante={pageCourante} totalPages={totalPages} onChanger={setPageCourante} />
        </>
      )}
    </main>
  )
}
