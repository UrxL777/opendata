import { useEffect } from 'react'
import { Routes, Route, useLocation } from 'react-router-dom'
import Navigation from './composants/Navigation'
import PiedDePage from './composants/PiedDePage'
import Accueil from './pages/Accueil'
import Donnees from './pages/Donnees'
import Detail from './pages/Detail'
import Visualisation from './pages/Visualisation'
import ReinitalisationMdp from './pages/ReinitalisationMdp'

// Affiche chaque nouvelle page depuis le haut
function RemonterEnHaut() {
  const { pathname, search } = useLocation()
  useEffect(() => { window.scrollTo(0, 0) }, [pathname, search])
  return null
}

export default function App() {

  return (
      <div className="min-h-screen bg-gray-50 flex flex-col">
        <RemonterEnHaut />
        <Navigation />
        <div className="flex-1">
          <Routes>
            <Route path="/" element={<Accueil />} />
            <Route path="/donnees" element={<Donnees />} />
            <Route path="/donnees/:id" element={<Detail />} />
            <Route path="/visualisation" element={<Visualisation />} />
            <Route path="/reinitialisation-mdp" element={<ReinitalisationMdp />} />
          </Routes>
        </div>
        <PiedDePage />
      </div>
  )
}