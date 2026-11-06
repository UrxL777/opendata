import { useState } from 'react'
import { Link, useLocation } from 'react-router-dom'
import BoutonPublier from './BoutonPublier'
import BoutonConnexion from './BoutonConnexion'
import LogOpenData from './LogOpenData'

function IcôneMenu() {
  return (
    <svg xmlns="http://www.w3.org/2000/svg" width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <line x1="3" y1="6" x2="21" y2="6"/>
      <line x1="3" y1="12" x2="21" y2="12"/>
      <line x1="3" y1="18" x2="21" y2="18"/>
    </svg>
  )
}

function IcôneFermer() {
  return (
    <svg xmlns="http://www.w3.org/2000/svg" width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <line x1="18" y1="6" x2="6" y2="18"/>
      <line x1="6" y1="6" x2="18" y2="18"/>
    </svg>
  )
}

export default function Navigation() {
  const location = useLocation()
  const [menuOuvert, setMenuOuvert] = useState(false)

  const lienActif = (chemin) =>
    location.pathname === chemin
      ? 'text-blue-600 border-b-2 border-blue-600 pb-1'
      : 'text-gray-600 hover:text-blue-600'

  const lienActifMobile = (chemin) =>
    location.pathname === chemin
      ? 'text-blue-600 font-semibold'
      : 'text-gray-700'

  function fermerMenu() { setMenuOuvert(false) }

  return (
    <header className="bg-white border-b border-gray-100">

      {/* ── Barre principale ── */}
      <div className="max-w-7xl mx-auto px-4 flex items-center justify-between h-14">
        <Link to="/" onClick={fermerMenu}>
          {/* Desktop : icône + texte */}
          <span className="hidden md:inline-flex">
            <LogOpenData tailleIcone={26} tailleTexte="1.25rem" couleurTexte="#111827" />
          </span>
          {/* Mobile : icône seulement */}
          <span className="inline-flex md:hidden">
            <LogOpenData tailleIcone={26} afficherTexte={false} />
          </span>
        </Link>

        <div className="flex items-center gap-3">
          <BoutonConnexion />
          {/* Hamburger — visible seulement sur mobile */}
          <button
            className="md:hidden text-gray-600 hover:text-blue-600 p-1"
            onClick={() => setMenuOuvert(v => !v)}
          >
            {menuOuvert ? <IcôneFermer /> : <IcôneMenu />}
          </button>
        </div>
      </div>

      {/* ── Sous-barre desktop : liens + Publier — cachée sur mobile ── */}
      <div className="hidden md:block border-t border-gray-100">
        <div className="max-w-7xl mx-auto px-4 flex items-center justify-between h-11">
          <nav className="flex items-center gap-8">
            <Link to="/" className={`text-sm font-medium ${lienActif('/')}`}>Accueil</Link>
            <Link to="/donnees" className={`text-sm font-medium ${lienActif('/donnees')}`}>Données</Link>
            <Link to="/visualisation" className={`text-sm font-medium ${lienActif('/visualisation')}`}>Visualisation</Link>
          </nav>
          <BoutonPublier />
        </div>
      </div>

      {/* ── Menu mobile déroulant ── */}
      {menuOuvert && (
        <div className="md:hidden border-t border-gray-100 bg-white shadow-sm">
          <nav className="px-4 py-2 flex flex-col">
            <Link to="/" onClick={fermerMenu}
              className={`text-sm font-medium py-3 border-b border-gray-100 ${lienActifMobile('/')}`}>
              Accueil
            </Link>
            <Link to="/donnees" onClick={fermerMenu}
              className={`text-sm font-medium py-3 border-b border-gray-100 ${lienActifMobile('/donnees')}`}>
              Données
            </Link>
            <Link to="/visualisation" onClick={fermerMenu}
              className={`text-sm font-medium py-3 border-b border-gray-100 ${lienActifMobile('/visualisation')}`}>
              Visualisation
            </Link>
            <div className="pt-3 pb-2">
              <BoutonPublier onVisualisationPubliee={fermerMenu} />
            </div>
          </nav>
        </div>
      )}

    </header>
  )
}