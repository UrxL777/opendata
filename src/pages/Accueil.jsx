// ═══ PAGE D'ACCUEIL (adresse /) ═══
// Démarche : au chargement, la page COMPTE dans Supabase (supabase-js) :
//   1. les jeux visibles, 2. les inscrits, 3. les dashboards terminés, 4. les téléchargements,
//   5. les jeux de chaque catégorie (pour les cartes).
// Les chiffres ne sont jamais écrits à la main : ils sont recalculés à chaque visite.

import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { Search, Users, Database, Download, ChartColumnBig } from 'lucide-react'
import { supabase } from '../supabase'
import { IconeCategorie } from '../utilitaires/iconeCategorie'

const CATEGORIES_ACCUEIL = ['Économie', 'Santé', 'Éducation', 'Agriculture', 'Transport', 'Environnement', 'Démographie', 'Sport']

const ETAPES = [
  { titre: 'Déposez votre fichier', texte: "CSV, Excel ou JSON, jusqu'à 50 Mo." },
  { titre: "L'IA le décrit pour vous", texte: 'Titre, description et catégorie proposés automatiquement. Vous pouvez les modifier.' },
  { titre: 'Rapport de qualité automatique', texte: 'Valeurs manquantes, doublons et nettoyage des données, détectés dès la publication.' },
  { titre: 'Un dashboard créé par Atlas', texte: "Atlas analyse vos données comme un data analyst, construit un dashboard interactif et vous l'explique." },
]

export default function Accueil() {
  const [stats, setStats] = useState({ jeux: 0, utilisateurs: 0, telechargements: 0, dashboards: 0 })
  const [categories, setCategories] = useState([])

  useEffect(() => {
    async function charger() {
      // 1. Nombre de jeux visibles (count : Supabase compte sans renvoyer les lignes)
      const { count: jeux } = await supabase
        .from('jeux_de_donnees')
        .select('*', { count: 'exact', head: true })
        .eq('visible', true)

      // 2. Nombre d'inscrits (table profiles)
      const { count: utilisateurs } = await supabase
        .from('profiles')
        .select('*', { count: 'exact', head: true })

      // Les dashboards créés par Atlas (seulement ceux qui sont prêts)
      const { count: dashboards } = await supabase
        .from('dashboards')
        .select('*', { count: 'exact', head: true })
        .eq('statut', 'termine')

      // 4. Total des téléchargements : on additionne le compteur de chaque fichier
      const { data: fichiers } = await supabase
        .from('fichiers')
        .select('telechargements')
      const telechargements = fichiers?.reduce((acc, f) => acc + (f.telechargements ?? 0), 0) ?? 0

      // 5. Les catégories, puis le nombre de jeux dans chacune
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

      // Les chiffres sont rangés dans l'état (stats) : React met la page à jour
      setStats({ jeux: jeux ?? 0, utilisateurs: utilisateurs ?? 0, telechargements, dashboards: dashboards ?? 0 })
      setCategories(catsAvecCompte)
    }
    charger()
  }, [])

  return (
    <div>
      <section className="bg-gradient-to-b from-degrade-debut to-degrade-fin py-20 px-4 text-center">
        <p className="text-principal font-medium mb-3">Des données ouvertes et gratuites, partagées par tous</p>
        <h1 className="text-4xl md:text-5xl font-extrabold text-texte-titre mb-4 max-w-4xl mx-auto">
          La plateforme où les données se partagent et se comprennent
        </h1>
        <p className="text-texte-doux mb-8 max-w-2xl mx-auto">
          Publiez vos jeux de données, explorez ceux des autres et analysez-les avec l'aide d'une IA. Pensée pour les étudiants et les analystes qui construisent leur portfolio.
        </p>
        <div className="flex justify-center">
          <Link to="/donnees" className="flex items-center justify-center gap-2 bg-principal hover:bg-principal-survol text-texte-inverse px-6 py-3 rounded-lg font-medium">
            <Search size={18} /> Explorer les données
          </Link>
        </div>
        <p className="text-xs text-texte-discret mt-6 max-w-md mx-auto">
          Vous avez modifié un jeu de données déjà publié ? Redéposez simplement la nouvelle version : elle sera reconnue automatiquement.
        </p>
      </section>

      <section className="py-16 px-4 bg-fond text-center">
        <h2 className="text-2xl font-bold text-texte-titre mb-2">Comment ça marche ?</h2>
        <p className="text-texte-doux mb-10">De votre fichier brut à un jeu de données prêt à être analysé, en quelques secondes</p>
        <div className="max-w-5xl mx-auto grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-5 text-left">
          {ETAPES.map((etape, i) => (
            <div key={etape.titre} className="border border-bordure-bleu-pale rounded-2xl p-6">
              <div className="w-11 h-11 rounded-full bg-fond-bleu-clair text-principal font-bold text-lg flex items-center justify-center mb-4">{i + 1}</div>
              <h3 className="font-semibold text-texte-bleu-nuit mb-2">{etape.titre}</h3>
              <p className="text-sm text-texte-doux">{etape.texte}</p>
            </div>
          ))}
        </div>
      </section>

      <section className="py-16 px-4 bg-fond text-center">
        <h2 className="text-2xl font-bold text-texte-titre mb-2">Un écosystème de données en construction</h2>
        <p className="text-texte-doux mb-10">Découvrez les statistiques de notre portail communautaire</p>
        <div className="max-w-5xl mx-auto grid grid-cols-2 lg:grid-cols-4 gap-6">
          <div className="border border-bordure-legere rounded-2xl p-6 shadow-sm">
            <div className="flex justify-center mb-2 text-principal"><Database size={28} /></div>
            <p className="text-3xl font-bold text-principal">{stats.jeux}</p>
            <p className="text-texte-doux text-sm mt-1">Jeux de données</p>
          </div>
          <div className="border border-bordure-legere rounded-2xl p-6 shadow-sm">
            <div className="flex justify-center mb-2 text-principal"><ChartColumnBig size={28} /></div>
            <p className="text-3xl font-bold text-principal">{stats.dashboards}</p>
            <p className="text-texte-doux text-sm mt-1">Dashboards</p>
          </div>
          <div className="border border-bordure-legere rounded-2xl p-6 shadow-sm">
            <div className="flex justify-center mb-2 text-principal"><Download size={28} /></div>
            <p className="text-3xl font-bold text-principal">{stats.telechargements}</p>
            <p className="text-texte-doux text-sm mt-1">Téléchargements</p>
          </div>
          <div className="border border-bordure-legere rounded-2xl p-6 shadow-sm">
            <div className="flex justify-center mb-2 text-principal"><Users size={28} /></div>
            <p className="text-3xl font-bold text-principal">{stats.utilisateurs}</p>
            <p className="text-texte-doux text-sm mt-1">Utilisateurs inscrits</p>
          </div>
        </div>
      </section>

      <section className="py-16 px-4 bg-fond-doux text-center">
        <h2 className="text-2xl font-bold text-texte-titre mb-2">Explorez nos catégories de données</h2>
        <p className="text-texte-doux mb-10">Des données structurées par domaine pour faciliter vos recherches</p>
        <div className="max-w-5xl mx-auto grid grid-cols-2 sm:grid-cols-4 gap-4">
          {categories.map((cat) => (
            <Link
              key={cat.id}
              to={`/donnees?categorie=${cat.id}`}
              className="bg-fond border border-bordure-legere rounded-2xl p-5 hover:border-bordure-bleu hover:shadow-sm transition text-center"
            >
              <div className="flex justify-center mb-3">
                <div className="bg-fond-bleu-clair p-3 rounded-full">
                  <IconeCategorie taille={22} className="text-principal" />
                </div>
              </div>
              <p className="font-semibold text-texte text-sm">{cat.nom}</p>
              {cat.description && (
                <p className="text-xs text-texte-discret mt-1 line-clamp-2">{cat.description}</p>
              )}
              <p className="text-principal font-bold text-lg mt-2">{cat.nb_jeux}</p>
              <p className="text-xs text-texte-discret">jeux de données</p>
            </Link>
          ))}
        </div>
      </section>
    </div>
  )
}