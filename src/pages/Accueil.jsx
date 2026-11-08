import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { Search, Users, Database, Download } from 'lucide-react'
import { supabase } from '../supabase'
import { IconeCategorie } from '../utilitaires/iconeCategorie'

const CATEGORIES_ACCUEIL = ['Économie', 'Santé', 'Éducation', 'Agriculture', 'Transport', 'Environnement', 'Démographie', 'Sport']

export default function Accueil() {
  const [stats, setStats] = useState({ jeux: 0, utilisateurs: 0, telechargements: 0 })
  const [categories, setCategories] = useState([])

  useEffect(() => {
    async function charger() {
      const { count: jeux } = await supabase
        .from('jeux_de_donnees')
        .select('*', { count: 'exact', head: true })
        .eq('visible', true)

      const { count: utilisateurs } = await supabase
        .from('profiles')
        .select('*', { count: 'exact', head: true })

      const { data: fichiers } = await supabase
        .from('fichiers')
        .select('telechargements')
      const telechargements = fichiers?.reduce((acc, f) => acc + (f.telechargements ?? 0), 0) ?? 0

      const { data: cats } = await supabase
        .from('categories')
        .select('*')
        .order('nom', { ascending: true })

      const { data: comptages } = await supabase
        .from('jeux_de_donnees')
        .select('categorie_id')
        .eq('visible', true)

      const compteParCategorie = {}
      comptages?.forEach(j => {
        if (j.categorie_id) compteParCategorie[j.categorie_id] = (compteParCategorie[j.categorie_id] ?? 0) + 1
      })

      const catsAvecCompte = (cats ?? [])
        .map(c => ({ ...c, nb_jeux: compteParCategorie[c.id] ?? 0 }))
        .filter(c => CATEGORIES_ACCUEIL.includes(c.nom))
        .sort((a,b) => CATEGORIES_ACCUEIL.indexOf(a.nom) - CATEGORIES_ACCUEIL.indexOf(b.nom))

      setStats({ jeux: jeux ?? 0, utilisateurs: utilisateurs ?? 0, telechargements })
      setCategories(catsAvecCompte)
    }
    charger()
  }, [])

  const categoriesAffichees = categories
  const plusDeCategories = false

  return (
    <div>
      <section className="bg-gradient-to-b from-blue-50 to-white py-20 px-4 text-center">
        <p className="text-blue-600 font-medium mb-3">Des données ouvertes et gratuites, partagées par tous</p>
        <h1 className="text-4xl md:text-5xl font-extrabold text-gray-900 mb-4">
          Vous cherchez un jeu de données ?<br />Trouvez-le, ou partagez le vôtre.
        </h1>
        <p className="text-gray-500 mb-8 max-w-xl mx-auto">
          Déposez, explorez et téléchargez gratuitement des jeux de données aux formats CSV, Excel et JSON.
        </p>
        <div className="flex justify-center">
          <Link to="/donnees" className="flex items-center justify-center gap-2 bg-blue-600 hover:bg-blue-700 text-white px-6 py-3 rounded-lg font-medium">
            <Search size={18} /> Explorer les données
          </Link>
        </div>
      </section>

      <section className="py-16 px-4 bg-white text-center">
        <h2 className="text-2xl font-bold text-gray-900 mb-2">Un écosystème de données en construction</h2>
        <p className="text-gray-500 mb-10">Découvrez les statistiques de notre portail communautaire</p>
        <div className="max-w-4xl mx-auto grid grid-cols-1 sm:grid-cols-3 gap-6">
          <div className="border border-gray-100 rounded-2xl p-6 shadow-sm">
            <div className="flex justify-center mb-2 text-blue-600"><Database size={28} /></div>
            <p className="text-3xl font-bold text-blue-600">{stats.jeux}</p>
            <p className="text-gray-500 text-sm mt-1">Jeux de données</p>
          </div>
          <div className="border border-gray-100 rounded-2xl p-6 shadow-sm">
            <div className="flex justify-center mb-2 text-blue-600"><Download size={28} /></div>
            <p className="text-3xl font-bold text-blue-600">{stats.telechargements}</p>
            <p className="text-gray-500 text-sm mt-1">Téléchargements</p>
          </div>
          <div className="border border-gray-100 rounded-2xl p-6 shadow-sm">
            <div className="flex justify-center mb-2 text-blue-600"><Users size={28} /></div>
            <p className="text-3xl font-bold text-blue-600">{stats.utilisateurs}</p>
            <p className="text-gray-500 text-sm mt-1">Utilisateurs inscrits</p>
          </div>
        </div>
      </section>

      <section className="py-16 px-4 bg-gray-50 text-center">
        <h2 className="text-2xl font-bold text-gray-900 mb-2">Explorez nos catégories de données</h2>
        <p className="text-gray-500 mb-10">Des données structurées par domaine pour faciliter vos recherches</p>
        <div className="max-w-5xl mx-auto grid grid-cols-2 sm:grid-cols-4 gap-4">
          {categoriesAffichees.map((cat) => (
            <Link
              key={cat.id}
              to={`/donnees?categorie=${cat.id}`}
              className="bg-white border border-gray-100 rounded-2xl p-5 hover:border-blue-300 hover:shadow-sm transition text-center"
            >
              <div className="flex justify-center mb-3">
                <div className="bg-blue-50 p-3 rounded-full">
                  <IconeCategorie nom={cat.nom} size={22} className="text-blue-600" />
                </div>
              </div>
              <p className="font-semibold text-gray-800 text-sm">{cat.nom}</p>
              {cat.description && (
                <p className="text-xs text-gray-400 mt-1 line-clamp-2">{cat.description}</p>
              )}
              <p className="text-blue-600 font-bold text-lg mt-2">{cat.nb_jeux}</p>
              <p className="text-xs text-gray-400">jeux de données</p>
            </Link>
          ))}
        </div>

        {plusDeCategories && (
          <div className="mt-8">
            <Link
              to="/donnees"
              className="inline-flex items-center gap-2 border border-blue-600 text-blue-600 hover:bg-blue-50 px-6 py-2.5 rounded-lg text-sm font-medium transition"
            >
              Voir toutes les catégories
            </Link>
          </div>
        )}
      </section>
    </div>
  )
}