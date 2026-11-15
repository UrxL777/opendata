import {
  ResponsiveContainer, BarChart, Bar, LineChart, Line, PieChart, Pie, Cell,
  XAxis, YAxis, CartesianGrid, Tooltip, Legend,
} from 'recharts'
import { formaterNombre } from '../../utilitaires/formatDashboard'

// Les couleurs viennent de index.css (uniquement des bleus)
const COULEURS = [1, 2, 3, 4, 5, 6].map(i => `var(--color-graphique-${i})`)
const COULEUR_PETIT_GROUPE = 'var(--color-graphique-petit-groupe)'
const COULEUR_GRILLE = 'var(--color-graphique-grille)'
const COULEUR_TEXTE_AXE = 'var(--color-texte-doux)'

// Axe : 12 500 → « 12,5 k » ; 2 300 000 → « 2,3 M »
function formaterAxe(v) {
  const n = Number(v)
  if (Math.abs(n) >= 1e6) return `${(n / 1e6).toLocaleString('fr-FR', { maximumFractionDigits: 1 })} M`
  if (Math.abs(n) >= 1e3) return `${(n / 1e3).toLocaleString('fr-FR', { maximumFractionDigits: 1 })} k`
  return n.toLocaleString('fr-FR', { maximumFractionDigits: 1 })
}

const raccourcir = (texte, max) => {
  const t = String(texte ?? '')
  return t.length > max ? t.slice(0, max - 1) + '…' : t
}

// Transforme le résultat SQL (colonnes + lignes) en données pour Recharts
function preparerDonnees(graphique, resultat) {
  const { colonnes = [], lignes = [] } = resultat ?? {}
  const ix = colonnes.indexOf(graphique.x)
  const iy = colonnes.indexOf(graphique.y)
  const inb = graphique.effectif ? colonnes.indexOf(graphique.effectif) : -1
  const iserie = graphique.serie ? colonnes.indexOf(graphique.serie) : -1
  if (ix < 0 || iy < 0) return { donnees: [], series: [] }

  if (iserie < 0) {
    return {
      donnees: lignes.map(l => ({ x: String(l[ix]), y: l[iy], nb: inb >= 0 ? l[inb] : null })),
      series: [],
    }
  }
  // Croisement : une ligne par catégorie, une colonne par série (format « large »)
  const parX = new Map(), series = []
  for (const l of lignes) {
    const x = String(l[ix]), s = String(l[iserie])
    if (!series.includes(s)) series.push(s)
    if (!parX.has(x)) parX.set(x, { x })
    parX.get(x)[`v_${s}`] = l[iy]
    parX.get(x)[`nb_${s}`] = inb >= 0 ? l[inb] : null
  }
  return { donnees: [...parX.values()], series }
}

// La bulle qui s'affiche au survol : valeur et nombre de lignes
function Bulle({ active, payload, label, graphique, effectifMin }) {
  if (!active || !payload?.length) return null
  return (
    <div className="bg-fond border border-bordure rounded-lg shadow-sm px-3 py-2 text-xs">
      <p className="font-semibold text-texte mb-1">{label ?? payload[0]?.payload?.x}</p>
      {payload.map((p, i) => {
        const nb = graphique.serie ? p.payload[`nb_${p.name}`] : p.payload.nb
        return (
          <p key={i} className="text-texte-secondaire">
            {graphique.serie && <span className="font-medium">{p.name} : </span>}
            {graphique.libelle_y} : <span className="font-semibold text-texte">{formaterNombre(p.value)}</span>
            {nb != null && (
              <span className={nb < effectifMin ? 'text-texte-erreur' : 'text-texte-discret'}>
                {' '}· {formaterNombre(nb)} ligne{nb > 1 ? 's' : ''}{nb < effectifMin ? ' (peu fiable)' : ''}
              </span>
            )}
          </p>
        )
      })}
    </div>
  )
}

export default function GraphiqueDashboard({ graphique, resultat, numero, effectifMin = 30, colonnesFiltres = [], onCliquerValeur, compact = false }) {
  const { donnees, series } = preparerDonnees(graphique, resultat)
  // Sur un petit écran, des barres avec beaucoup de catégories deviennent horizontales (noms lisibles à gauche)
  const type = compact && graphique.type === 'barres' && donnees.length > 5 ? 'barres_horizontales' : graphique.type
  const petit = nb => nb != null && nb < effectifMin
  const cliquable = colonnesFiltres.includes(graphique.x) && onCliquerValeur
  const cliquer = d => { if (cliquable && d?.x != null) onCliquerValeur(graphique.x, d.x) }

  // Base du graphique : nombre de lignes utilisées (sauf croisement : chaque ligne compte une fois par série)
  const total = graphique.effectif && donnees.length
    ? (series.length ? donnees.reduce((a, d) => a + series.reduce((b, s) => b + (d[`nb_${s}`] ?? 0), 0), 0)
      : donnees.reduce((a, d) => a + (d.nb ?? 0), 0))
    : null
  const aPetitsGroupes = series.length
    ? donnees.some(d => series.some(s => petit(d[`nb_${s}`])))
    : donnees.some(d => petit(d.nb))

  const bulle = <Tooltip content={<Bulle graphique={graphique} effectifMin={effectifMin} />} cursor={{ fill: 'var(--color-fond-bleu-clair)' }} />
  const axeTexte = { fontSize: 12, fill: COULEUR_TEXTE_AXE }
  const labelY = { value: graphique.libelle_y, angle: -90, position: 'insideLeft', style: { ...axeTexte, textAnchor: 'middle' } }
  const labelX = { value: graphique.libelle_x, position: 'insideBottom', offset: -12, style: axeTexte }
  const marges = { top: 8, right: 12, bottom: 28, left: 8 }

  let rendu
  if (!donnees.length) {
    rendu = <p className="text-sm text-texte-discret py-16 text-center">Aucune donnée pour ces filtres.</p>
  } else if (type === 'camembert') {
    rendu = (
      <PieChart>
        <Pie data={donnees} dataKey="y" nameKey="x" outerRadius="75%" onClick={cliquer} cursor={cliquable ? 'pointer' : undefined}>
          {donnees.map((d, i) => <Cell key={i} fill={petit(d.nb) ? COULEUR_PETIT_GROUPE : COULEURS[i % COULEURS.length]} />)}
        </Pie>
        {bulle}
        <Legend wrapperStyle={{ fontSize: 12 }} />
      </PieChart>
    )
  } else if (type === 'courbe') {
    rendu = (
      <LineChart data={donnees} margin={marges}>
        <CartesianGrid stroke={COULEUR_GRILLE} vertical={false} />
        <XAxis dataKey="x" tick={axeTexte} tickFormatter={v => raccourcir(v, 12)} label={labelX} padding={{ left: 24, right: 24 }} />
        <YAxis tick={axeTexte} tickFormatter={formaterAxe} label={labelY} width={64} />
        {bulle}
        {series.length ? (
          <>
            <Legend verticalAlign="top" wrapperStyle={{ fontSize: 12 }} />
            {series.map((s, i) => <Line key={s} name={s} dataKey={`v_${s}`} stroke={COULEURS[i % COULEURS.length]} strokeWidth={2} dot={{ r: 3 }} />)}
          </>
        ) : (
          <Line dataKey="y" name={graphique.libelle_y} stroke={COULEURS[1]} strokeWidth={2} dot={{ r: 3 }} />
        )}
      </LineChart>
    )
  } else if (type === 'barres_horizontales') {
    rendu = (
      <BarChart data={donnees} layout="vertical" margin={{ ...marges, left: 4 }}>
        <CartesianGrid stroke={COULEUR_GRILLE} horizontal={false} />
        <XAxis type="number" tick={axeTexte} tickFormatter={formaterAxe} label={{ ...labelX, value: graphique.libelle_y }} />
        <YAxis type="category" dataKey="x" tick={axeTexte} tickFormatter={v => raccourcir(v, compact ? 12 : 16)} width={compact ? 92 : 120} interval={0} />
        {bulle}
        <Bar dataKey="y" name={graphique.libelle_y} onClick={cliquer} cursor={cliquable ? 'pointer' : undefined} radius={[0, 4, 4, 0]}>
          {donnees.map((d, i) => <Cell key={i} fill={petit(d.nb) ? COULEUR_PETIT_GROUPE : COULEURS[1]} />)}
        </Bar>
      </BarChart>
    )
  } else {
    // barres et barres_groupees
    rendu = (
      <BarChart data={donnees} margin={marges}>
        <CartesianGrid stroke={COULEUR_GRILLE} vertical={false} />
        <XAxis dataKey="x" tick={axeTexte} tickFormatter={v => raccourcir(v, donnees.length > 6 ? 8 : 14)} interval={0} label={labelX} />
        <YAxis tick={axeTexte} tickFormatter={formaterAxe} label={labelY} width={64} />
        {bulle}
        {series.length ? (
          <>
            <Legend verticalAlign="top" wrapperStyle={{ fontSize: 12 }} />
            {series.map((s, i) => (
              <Bar key={s} name={s} dataKey={`v_${s}`} onClick={cliquer} cursor={cliquable ? 'pointer' : undefined} radius={[4, 4, 0, 0]}>
                {donnees.map((d, j) => <Cell key={j} fill={petit(d[`nb_${s}`]) ? COULEUR_PETIT_GROUPE : COULEURS[i % COULEURS.length]} />)}
              </Bar>
            ))}
          </>
        ) : (
          <Bar dataKey="y" name={graphique.libelle_y} onClick={cliquer} cursor={cliquable ? 'pointer' : undefined} radius={[4, 4, 0, 0]}>
            {donnees.map((d, i) => <Cell key={i} fill={petit(d.nb) ? COULEUR_PETIT_GROUPE : COULEURS[1]} />)}
          </Bar>
        )}
      </BarChart>
    )
  }

  return (
    <div className="bg-fond border border-bordure-legere rounded-2xl p-4 shadow-sm flex flex-col">
      <h3 className="font-semibold text-texte-titre text-sm mb-3">
        <span className="text-texte-discret font-normal">{numero}. </span>{graphique.titre}
      </h3>
      <div className={type === 'barres_horizontales' && donnees.length > 8 ? 'h-96' : 'h-72'}>
        {donnees.length ? <ResponsiveContainer width="100%" height="100%">{rendu}</ResponsiveContainer> : rendu}
      </div>
      {graphique.phrase && <p className="text-sm text-texte-secondaire mt-3">{graphique.phrase}</p>}
      <p className="text-xs text-texte-discret mt-2">
        {total ? `Basé sur ${formaterNombre(total)} lignes` : ''}
        {total && aPetitsGroupes ? ' · ' : ''}
        {aPetitsGroupes ? `barre pâle : groupe de moins de ${effectifMin} lignes` : ''}
        {cliquable ? `${total || aPetitsGroupes ? ' · ' : ''}clique sur une barre pour filtrer` : ''}
      </p>
    </div>
  )
}
