import { MapPin, Phone, Mail } from 'lucide-react'
import { Link } from 'react-router-dom'
import LogOpenData from './LogOpenData'

export default function PiedDePage() {
  return (
    <footer className="bg-gray-900 text-gray-300 mt-16">
      <div className="max-w-7xl mx-auto px-4 py-12 grid grid-cols-1 md:grid-cols-4 gap-8">

        {/* Contact */}
        <div>
          <h3 className="text-white font-semibold mb-3">Contact</h3>
          <ul className="space-y-2 text-sm">
            <li className="flex items-center gap-2">
              <MapPin size={14} className="text-blue-400 shrink-0" />
              Abidjan, Côte d'Ivoire
            </li>
            <li className="flex items-center gap-2">
              <Phone size={14} className="text-blue-400 shrink-0" />
              +225 07 483 365 67 / +225 05 554 894 83
            </li>
            <li className="flex items-center gap-2">
              <Mail size={14} className="text-blue-400 shrink-0" />
              urielakpa777@gmail.com
            </li>
          </ul>
          <div className="flex items-center gap-3 mt-4">
            <a href="https://www.linkedin.com/in/uriel-akpa-748aa5377?utm_source=share_via&utm_content=profile&utm_medium=member_ios" target="_blank" rel="noreferrer" className="hover:opacity-80 transition-opacity">
              <svg width="24" height="24" viewBox="0 0 24 24" fill="none">
                <rect width="24" height="24" rx="4" fill="#0A66C2" />
                <path d="M7.5 9.5H5V19H7.5V9.5ZM6.25 8.5C7.08 8.5 7.75 7.83 7.75 7C7.75 6.17 7.08 5.5 6.25 5.5C5.42 5.5 4.75 6.17 4.75 7C4.75 7.83 5.42 8.5 6.25 8.5ZM19 19H16.5V14.25C16.5 12.5 15.5 12 14.75 12C14 12 12.5 12.5 12.5 14.25V19H10V9.5H12.5V10.75C12.92 9.92 14.08 9.25 15.25 9.25C17.5 9.25 19 10.75 19 13.5V19Z" fill="white" />
              </svg>
            </a>
            <a href="#" target="_blank" rel="noreferrer" className="hover:opacity-80 transition-opacity">
              <svg width="24" height="24" viewBox="0 0 24 24" fill="none">
                <rect width="24" height="24" rx="4" fill="#1877F2" />
                <path d="M16 8H13.5C13 8 12.5 8.5 12.5 9V11H16L15.5 13.5H12.5V20H10V13.5H8V11H10V9C10 7 11.5 5.5 13.5 5.5H16V8Z" fill="white" />
              </svg>
            </a>
          </div>
        </div>

        {/* Logo + description */}
        <div>
          <div className="mb-3">
            <LogOpenData tailleIcone={23} tailleTexte="1.1rem" couleurTexte="white" mode="sombre" />
          </div>
          <p className="text-sm text-gray-400">
            Une plateforme communautaire pour partager et explorer des données ouvertes aux formats CSV, Excel et JSON.
          </p>
        </div>

        {/* Navigation */}
        <div>
          <h3 className="text-white font-semibold mb-3">Navigation</h3>
          <ul className="space-y-2 text-sm">
            <li><Link to="/" className="hover:text-white">Accueil</Link></li>
            <li><Link to="/donnees" className="hover:text-white">Données</Link></li>
            <li><Link to="/visualisation" className="hover:text-white">Visualisation</Link></li>
          </ul>
        </div>

        {/* Catégories */}
        <div>
          <h3 className="text-white font-semibold mb-3">Catégories</h3>
          <ul className="space-y-2 text-sm">
            <li><Link to="/donnees?categorie=Économie" className="hover:text-white">Économie</Link></li>
            <li><Link to="/donnees?categorie=Environnement" className="hover:text-white">Environnement</Link></li>
            <li><Link to="/donnees?categorie=Santé" className="hover:text-white">Santé</Link></li>
            <li><Link to="/donnees?categorie=Éducation" className="hover:text-white">Éducation</Link></li>
            <li><Link to="/donnees?categorie=Démographie" className="hover:text-white">Démographie</Link></li>
            <li><Link to="/donnees?categorie=Sport" className="hover:text-white">Sport</Link></li>
            <li><Link to="/donnees?categorie=Sécurité & Justice" className="hover:text-white">Sécurité & Justice</Link></li>
          </ul>
        </div>

      </div>

      <div className="border-t border-gray-800 text-center py-4 text-xs text-gray-500">
        © {new Date().getFullYear()} OpenData. Tous droits réservés.
      </div>
    </footer>
  )
}