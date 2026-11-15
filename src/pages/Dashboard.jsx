import { Link, useParams } from 'react-router-dom'
import { ArrowLeft } from 'lucide-react'

// Page d'un dashboard : complétée à l'étape suivante (KPI, filtres, graphiques, Atlas)
export default function Dashboard() {
  const { id } = useParams()
  return (
    <main className="max-w-6xl mx-auto px-4 py-10">
      <Link to="/dashboards" className="flex items-center gap-1.5 text-sm text-texte-doux hover:text-principal mb-5">
        <ArrowLeft size={16} /> Retour aux dashboards
      </Link>
      <p className="text-texte-doux">Dashboard du jeu de données {id}.</p>
    </main>
  )
}
