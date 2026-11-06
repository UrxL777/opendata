import { Link, useLocation } from 'react-router-dom'
import BoutonPublier from './BoutonPublier'
import BoutonConnexion from './BoutonConnexion'
import LogOpenData from './LogOpenData'

export default function Navigation() {
  const location = useLocation()

  const lienActif = (chemin) =>
    location.pathname === chemin
      ? 'text-blue-600 border-b-2 border-blue-600 pb-1'
      : 'text-gray-600 hover:text-blue-600'

  return (
    <header className="bg-white border-b border-gray-100">
      <div className="max-w-7xl mx-auto px-4 flex items-center justify-between h-14">
        <Link to="/">
          <LogOpenData tailleIcone={26} tailleTexte="1.25rem" couleurTexte="#111827" />
        </Link>
        <div className="flex items-center gap-3">
          <BoutonConnexion />
        </div>
      </div>

      <div className="border-t border-gray-100">
        <div className="max-w-7xl mx-auto px-4 flex items-center justify-between h-11">
          <nav className="flex items-center gap-8">
            <Link to="/" className={`text-sm font-medium ${lienActif('/')}`}>Accueil</Link>
            <Link to="/donnees" className={`text-sm font-medium ${lienActif('/donnees')}`}>Données</Link>
            <Link to="/visualisation" className={`text-sm font-medium ${lienActif('/visualisation')}`}>Visualisation</Link>
          </nav>
          <BoutonPublier />
        </div>
      </div>
    </header>
  )
}