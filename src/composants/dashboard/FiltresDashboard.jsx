import { useEffect, useRef, useState } from 'react'
import { SlidersHorizontal, ChevronDown, Check } from 'lucide-react'
import { formaterNombre } from '../../utilitaires/formatDashboard'

// Un filtre : bouton « Nom : Tous » qui ouvre la liste des valeurs (plusieurs choix possibles)
function Filtre({ filtre, choisies, onChanger }) {
  const [ouvert, setOuvert] = useState(false)
  const zone = useRef(null)

  useEffect(() => {
    if (!ouvert) return
    const fermer = e => { if (zone.current && !zone.current.contains(e.target)) setOuvert(false) }
    document.addEventListener('mousedown', fermer)
    return () => document.removeEventListener('mousedown', fermer)
  }, [ouvert])

  const resume = choisies.length === 0 ? 'Tous' : choisies.length === 1 ? choisies[0] : `${choisies.length} choisis`
  const basculer = v => onChanger(choisies.includes(v) ? choisies.filter(c => c !== v) : [...choisies, v])

  return (
    <div className="relative" ref={zone}>
      <button
        onClick={() => setOuvert(o => !o)}
        className={`flex items-center gap-1.5 border rounded-full px-3 py-1.5 text-sm transition-colors ${
          choisies.length ? 'border-principal bg-fond-bleu-clair text-principal' : 'border-bordure bg-fond text-texte-moyen hover:border-bordure-bleu'
        }`}
      >
        <span className="font-medium">{filtre.libelle || filtre.colonne}</span> : <span className="max-w-32 truncate">{resume}</span>
        <ChevronDown size={14} />
      </button>
      {ouvert && (
        <div className="absolute z-30 mt-1 left-0 min-w-56 max-h-72 overflow-y-auto bg-fond border border-bordure rounded-xl shadow-lg py-1">
          <button onClick={() => onChanger([])} className="w-full flex items-center gap-2 px-3 py-2 text-sm hover:bg-fond-doux text-left">
            <span className="w-4">{choisies.length === 0 && <Check size={14} className="text-principal" />}</span>Tous
          </button>
          {filtre.valeurs.map(({ valeur, nb }) => {
            const v = String(valeur)
            return (
              <button key={v} onClick={() => basculer(v)} className="w-full flex items-center gap-2 px-3 py-2 text-sm hover:bg-fond-doux text-left">
                <span className="w-4">{choisies.includes(v) && <Check size={14} className="text-principal" />}</span>
                <span className="flex-1">{v}</span>
                <span className="text-xs text-texte-discret">{formaterNombre(nb)}</span>
              </button>
            )
          })}
        </div>
      )}
    </div>
  )
}

export default function FiltresDashboard({ filtres, choix, onChanger, onReinitialiser }) {
  if (!filtres?.length) return null
  const actifs = Object.values(choix).some(v => v.length)
  return (
    <div className="flex flex-wrap items-center gap-2">
      <span className="flex items-center gap-1.5 text-sm text-texte-doux"><SlidersHorizontal size={16} /> Filtres</span>
      {filtres.map(f => (
        <Filtre key={f.colonne} filtre={f} choisies={choix[f.colonne] ?? []} onChanger={v => onChanger(f.colonne, v)} />
      ))}
      {actifs && (
        <button onClick={onReinitialiser} className="text-sm text-principal hover:underline ml-1">Réinitialiser</button>
      )}
    </div>
  )
}
