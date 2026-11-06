export default function LogOpenData({ tailleIcone = 26, tailleTexte = '1.25rem', couleurTexte = '#111827', mode = 'clair', afficherTexte = true }) {
  const c = mode === 'sombre'
    ? { anneau: '#60A5FA', barre1: '#93C5FD', barre2: '#BFDBFE', barre3: '#93C5FD' }
    : { anneau: '#2563EB', barre1: '#BFDBFE', barre2: '#2563EB', barre3: '#60A5FA' }

  return (
    <span style={{ display: 'inline-flex', alignItems: 'baseline' }}>
      <svg xmlns="http://www.w3.org/2000/svg" width={tailleIcone} height={tailleIcone} viewBox="0 0 32 32" fill="none" style={{ flexShrink: 0 }}>
        <circle cx="16" cy="16" r="13" stroke={c.anneau} strokeWidth="2.5" fill="none" />
        <rect x="9" y="18" width="3.5" height="6" rx="1" fill={c.barre1} />
        <rect x="14.25" y="12" width="3.5" height="12" rx="1" fill={c.barre2} />
        <rect x="19.5" y="14.5" width="3.5" height="9.5" rx="1" fill={c.barre3} />
      </svg>
      {afficherTexte && (
        <span style={{ fontWeight: 700, fontSize: tailleTexte, letterSpacing: '-0.02em', color: couleurTexte, lineHeight: 1 }}>
          penData
        </span>
      )}
    </span>
  )
}