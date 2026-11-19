// L'icône des catégories (bibliothèque lucide-react), au même format partout sur le site.

import { FolderOpen } from 'lucide-react'

export function IconeCategorie({ taille = 24, className = '' }) {
  return <FolderOpen size={taille} className={className} />
}