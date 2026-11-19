// ═══ LE POINT DE DÉPART DU SITE ═══
// C'est le premier fichier lu par le navigateur. Il « monte » l'application React dans la page (index.html, balise #root).
// Démarche, de l'extérieur vers l'intérieur :
//   1. BrowserRouter (React Router) : gère les adresses des pages (/, /donnees, /dashboards…)
//   2. FournisseurAuth : partage l'utilisateur connecté avec toutes les pages
//   3. App : choisit la page à afficher selon l'adresse
// index.css (les couleurs et Tailwind) est chargé ici, une seule fois pour tout le site.

import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { BrowserRouter } from 'react-router-dom'
import { FournisseurAuth } from './contexte/Authentification'
import './index.css'
import App from './App.jsx'

createRoot(document.getElementById('root')).render(
  <StrictMode>
    <BrowserRouter>
      <FournisseurAuth>
        <App />
      </FournisseurAuth>
    </BrowserRouter>
  </StrictMode>
)