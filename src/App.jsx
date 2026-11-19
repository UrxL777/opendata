// ═══ LE PLAN DU SITE ═══
// App déclare chaque adresse et la page qui s'affiche (React Router).
// Le menu (Navigation) et le pied de page sont présents sur toutes les pages.

import { useEffect } from 'react'
import { Routes, Route, useLocation } from 'react-router-dom'
import Navigation from './composants/Navigation'
import PiedDePage from './composants/PiedDePage'
import Accueil from './pages/Accueil'
import Donnees from './pages/Donnees'
import Detail from './pages/Detail'
import Dashboards from './pages/Dashboards'
import Dashboard from './pages/Dashboard'
import ReinitalisationMdp from './pages/ReinitalisationMdp'

// Affiche chaque nouvelle page depuis le haut
function RemonterEnHaut() {
  const { pathname, search } = useLocation()
  useEffect(() => { window.scrollTo(0, 0) }, [pathname, search])
  return null
}

export default function App() {

  return (
      <div className="min-h-screen bg-fond-doux flex flex-col">
        <RemonterEnHaut />
        <Navigation />
        <div className="flex-1">
          <Routes>
            {/* Une ligne = une adresse → une page */}
            <Route path="/" element={<Accueil />} />
            <Route path="/donnees" element={<Donnees />} />
            <Route path="/donnees/:id" element={<Detail />} />
            <Route path="/dashboards" element={<Dashboards />} />
            <Route path="/dashboards/:id" element={<Dashboard />} />
            <Route path="/reinitialisation-mdp" element={<ReinitalisationMdp />} />
          </Routes>
        </div>
        <PiedDePage />
      </div>
  )
}