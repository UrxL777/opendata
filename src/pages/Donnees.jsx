// ═══ LE CATALOGUE DES JEUX DE DONNÉES (adresse /donnees) ═══
// Démarche :
//   1. charger les catégories (pour le filtre)
//   2. lire la vue SQL vue_jeux_avec_pseudo : chaque jeu avec le pseudo de son auteur, du plus récent au plus ancien
//   3. filtrer dans la base par catégorie (eq) et par titre (ilike), puis afficher 10 jeux par page (Pagination)

import { useEffect, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { Search } from 'lucide-react'
import { supabase } from '../supabase'
import { IconeCategorie } from '../utilitaires/iconeCategorie'
import Pagination from '../composants/Pagination'

const DATASETS_PAR_PAGE = 10

function formaterTaille(octets) {
  if (!octets) return '—'
  if (octets < 1024) return `${octets} o`
  if (octets < 1024 * 1024) return `${(octets / 1024).toFixed(1)} Ko`
  return `${(octets / 1024 / 1024).toFixed(1)} Mo`
}

export default function Donnees() {
  const [searchParams, setSearchParams] = useSearchParams()
  const [categories, setCategories] = useState([])
  const [jeux, setJeux] = useState([])
  const [recherche, setRecherche] = useState('')
  const [pageCourante, setPageCourante] = useState(1)

  const categorieActive = searchParams.get('categorie') ?? ''

  useEffect(() => {
    // 1. Les catégories, pour le menu de filtre
    supabase.from('categories').select('*').then(({ data }) => setCategories(data ?? []))
  }, [])

  useEffect(() => {
    async function charger() {
      // 2. Les jeux visibles avec le pseudo de leur auteur (vue SQL)
      let requete = supabase
        .from('vue_jeux_avec_pseudo')
        .select('*, categories(nom), fichiers(format, taille, telechargements, nom_fichier)')
        .order('cree_le', { ascending: false })
        .eq('visible', true)

      // 3. Filtres faits par la base : catégorie choisie, et titre qui contient la recherche
      if (categorieActive) requete = requete.eq('categorie_id', categorieActive)
      if (recherche) requete = requete.ilike('titre', `%${recherche}%`)

      const { data } = await requete
      setJeux(data ?? [])
      setPageCourante(1)
    }
    charger()
  }, [categorieActive, recherche])

  function changerCategorie(id) {
    if (id === '') setSearchParams({})
    else setSearchParams({ categorie: id })
    setPageCourante(1)
  }

  // Découpage en pages : seuls les jeux de la page courante sont affichés
  const totalPages = Math.ceil(jeux.length / DATASETS_PAR_PAGE)
  const jeuxPage = jeux.slice(
    (pageCourante - 1) * DATASETS_PAR_PAGE,
    pageCourante * DATASETS_PAR_PAGE
  )

  return (
    <div>
      <main className="max-w-6xl mx-auto px-4 py-10">
        <h1 className="text-3xl font-extrabold text-texte-titre mb-1">Catalogue de données</h1>
        <p className="text-texte-doux mb-8">Explorez et téléchargez gratuitement des jeux de données aux formats CSV, Excel et JSON, sans créer de compte.</p>

        <div className="flex items-center gap-2 border border-bordure rounded-lg px-4 py-2 bg-fond mb-4">
          <Search size={18} className="text-texte-discret" />
          <input
            value={recherche}
            onChange={e => { setRecherche(e.target.value); setPageCourante(1) }}
            placeholder="Rechercher dans les jeux de données..."
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

        {jeux.length === 0 ? (
          <p className="text-center text-texte-discret py-16">Aucun jeu de données trouvé.</p>
        ) : (
          <>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {jeuxPage.map((jeu) => {
                const fichiers = jeu.fichiers ?? []
                const tailleTotale = fichiers.reduce((acc, f) => acc + (f.taille ?? 0), 0)
                const telechargementsTotaux = fichiers.reduce((acc, f) => acc + (f.telechargements ?? 0), 0)
                const pseudo = jeu.pseudo ?? null
                return (
                  <div key={jeu.id} className="bg-fond border border-bordure-legere rounded-2xl p-5 flex flex-col gap-3 shadow-sm">
                    <div className="flex gap-3">
                      <div className="bg-fond-bleu-clair p-2 rounded-xl shrink-0 h-fit">
                        <IconeCategorie taille={20} className="text-principal" />
                      </div>
                      <div>
                        <h3 className="font-bold text-texte-titre">{jeu.titre}</h3>
                        <div className="flex items-center gap-2 flex-wrap">
                          {jeu.categories && (
                            <span className="text-xs bg-fond-gris text-texte-secondaire px-2 py-0.5 rounded-full">{jeu.categories.nom}</span>
                          )}
                          {pseudo && (
                            <span className="text-xs text-texte-discret">par <span className="font-medium text-texte-secondaire">{pseudo}</span></span>
                          )}
                        </div>
                        {jeu.description && (
                          <p className="text-sm text-texte-doux mt-1 line-clamp-2">{jeu.description}</p>
                        )}
                      </div>
                    </div>
                    {jeu.source && (
                      <p className="text-sm text-texte-doux"><span className="font-medium">Source :</span> {jeu.source}</p>
                    )}
                    {fichiers.length > 0 && (
                      <div className="flex flex-wrap gap-1">
                        {fichiers.map((f, i) => (
                          <span key={i} className="text-xs bg-fond-bleu-clair text-principal px-2 py-0.5 rounded font-medium uppercase">
                            {f.format}
                          </span>
                        ))}
                      </div>
                    )}
                    {fichiers.length > 0 && (
                      <div className="grid grid-cols-3 text-xs text-texte-doux gap-2">
                        <div><p className="font-medium text-texte-moyen">Taille</p><p>{formaterTaille(tailleTotale)}</p></div>
                        <div><p className="font-medium text-texte-moyen">Mis à jour le</p><p>{new Date(jeu.mis_a_jour_le ?? jeu.cree_le).toLocaleDateString('fr-FR')}</p></div>
                        <div><p className="font-medium text-texte-moyen">Téléchargements</p><p>{telechargementsTotaux}</p></div>
                      </div>
                    )}
                    <Link
                      to={`/donnees/${jeu.id}`}
                      className="block w-full text-center bg-principal hover:bg-principal-survol text-texte-inverse py-2.5 rounded-lg text-sm font-medium mt-auto"
                    >
                      Voir le détail
                    </Link>
                  </div>
                )
              })}
            </div>
            <Pagination
              pageCourante={pageCourante}
              totalPages={totalPages}
              onChanger={setPageCourante}
            />
          </>
        )}
      </main>
    </div>
  )
}