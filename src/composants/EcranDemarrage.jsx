import { useEffect, useState } from 'react'

export default function EcranDemarrage({ onTermine }) {
  const [sortie, setSortie] = useState(false)

  useEffect(() => {
    const minuterieSortie = setTimeout(() => setSortie(true), 2000)
    const minuterieTermine = setTimeout(() => onTermine(), 2600)
    return () => {
      clearTimeout(minuterieSortie)
      clearTimeout(minuterieTermine)
    }
  }, [onTermine])

  return (
    <>
      <style>{`
        @keyframes entree {
          from { opacity: 0; transform: scale(0.85); }
          to   { opacity: 1; transform: scale(1); }
        }
        @keyframes sortieAnim {
          from { opacity: 1; }
          to   { opacity: 0; }
        }
        .splash-entree  { animation: entree     0.6s ease-out forwards; }
        .splash-sortie  { animation: sortieAnim 0.5s ease-in  forwards; }
      `}</style>

      <div
        className={sortie ? 'splash-sortie' : 'splash-entree'}
        style={{
          position: 'fixed', inset: 0, zIndex: 9999,
          backgroundColor: '#2563EB',
          display: 'flex', flexDirection: 'column',
          alignItems: 'center', justifyContent: 'center',
        }}
      >
        <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '16px' }}>
          <svg xmlns="http://www.w3.org/2000/svg" width="72" height="72" viewBox="0 0 32 32" fill="none">
            <circle cx="16" cy="16" r="13" stroke="white" strokeWidth="2.5" fill="none" />
            <rect x="9"    y="18"   width="3.5" height="6"   rx="1" fill="rgba(255,255,255,0.55)" />
            <rect x="14.25" y="12" width="3.5" height="12"  rx="1" fill="white" />
            <rect x="19.5" y="14.5" width="3.5" height="9.5" rx="1" fill="rgba(255,255,255,0.8)" />
          </svg>

          <p style={{ color: 'white', fontSize: '24px', fontWeight: '700', letterSpacing: '0.02em', margin: 0 }}>
            OpenData
          </p>
        </div>

        <p style={{
          position: 'absolute', bottom: '40px',
          color: 'rgba(255,255,255,0.7)', fontSize: '13px', margin: 0
        }}>
          Plateforme de données ouvertes
        </p>
      </div>
    </>
  )
}