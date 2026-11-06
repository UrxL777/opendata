import { Routes, Route } from 'react-router-dom'
import Navigation from './composants/Navigation'
import PiedDePage from './composants/PiedDePage'
import Accueil from './pages/Accueil'
import Donnees from './pages/Donnees'
import Detail from './pages/Detail'
import Visualisation from './pages/Visualisation'
import Publier from './pages/Publier'
import Inscription from './pages/Inscription'
import Connexion from './pages/Connexion'
import ReinitalisationMdp from './pages/ReinitalisationMdp'

export default function App() {

  return (
      <div className="min-h-screen bg-gray-50 flex flex-col">
        <Navigation />
        <div className="flex-1">
          <Routes>
            <Route path="/" element={<Accueil />} />
            <Route path="/donnees" element={<Donnees />} />
            <Route path="/donnees/:id" element={<Detail />} />
            <Route path="/visualisation" element={<Visualisation />} />
            <Route path="/visualisation/:id" element={<Visualisation />} />
            <Route path="/publier" element={<Publier />} />
            <Route path="/inscription" element={<Inscription />} />
            <Route path="/connexion" element={<Connexion />} />
            <Route path="/reinitialisation-mdp" element={<ReinitalisationMdp />} />
          </Routes>
        </div>
        <PiedDePage />
      </div>
  )
}