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
      ? 'text-principal border-b-2 border-principal pb-1'
      : 'text-texte-secondaire hover:text-principal'

  const lienActifMobile = (chemin) =>
    location.pathname === chemin
      ? 'text-principal font-semibold'
      : 'text-texte-moyen'

  function fermerMenu() { setMenuOuvert(false) }

  return (
    <header className="bg-navbar border-b border-bordure-legere">

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
            className="md:hidden text-texte-secondaire hover:text-principal p-1"
            onClick={() => setMenuOuvert(v => !v)}
          >
            {menuOuvert ? <IcôneFermer /> : <IcôneMenu />}
          </button>
        </div>
      </div>

      {/* ── Sous-barre desktop : liens + Publier — cachée sur mobile ── */}
      <div className="hidden md:block border-t border-bordure-legere">
        <div className="max-w-7xl mx-auto px-4 flex items-center justify-between h-11">
          <nav className="flex items-center gap-8">
            <Link to="/" className={`text-sm font-medium ${lienActif('/')}`}>Accueil</Link>
            <Link to="/donnees" className={`text-sm font-medium ${lienActif('/donnees')}`}>Données</Link>
            <Link to="/visualisation" className={`text-sm font-medium ${lienActif('/visualisation')}`}>Dashboards</Link>
          </nav>
          <BoutonPublier />
        </div>
      </div>

      {/* ── Menu mobile déroulant ── */}
      {menuOuvert && (
        <div className="md:hidden border-t border-bordure-legere bg-navbar shadow-sm">
          <nav className="px-4 py-2 flex flex-col">
            <Link to="/" onClick={fermerMenu}
              className={`text-sm font-medium py-3 border-b border-bordure-legere ${lienActifMobile('/')}`}>
              Accueil
            </Link>
            <Link to="/donnees" onClick={fermerMenu}
              className={`text-sm font-medium py-3 border-b border-bordure-legere ${lienActifMobile('/donnees')}`}>
              Données
            </Link>
            <Link to="/visualisation" onClick={fermerMenu}
              className={`text-sm font-medium py-3 border-b border-bordure-legere ${lienActifMobile('/visualisation')}`}>
              Dashboards
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