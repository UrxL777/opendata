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

// Coupe un nom en lignes d'environ « max » caractères, aux espaces : le nom est affiché EN ENTIER
function couperEnLignes(texte, max) {
  const lignes = []
  for (const mot of String(texte ?? '').split(' ')) {
    const derniere = lignes[lignes.length - 1]
    if (derniere !== undefined && (derniere + ' ' + mot).length <= max) lignes[lignes.length - 1] = derniere + ' ' + mot
    else lignes.push(mot)
  }
  return lignes
}

// Graduation sous l'axe horizontal : le nom sur plusieurs lignes, centré sous la barre
function GraduationBas({ x, y, payload, max }) {
  const lignes = couperEnLignes(payload.value, max)
  return (
    <text x={x} y={y + 12} textAnchor="middle" fontSize={12} fill={COULEUR_TEXTE_AXE}>
      {lignes.map((l, i) => <tspan key={i} x={x} dy={i === 0 ? 0 : 14}>{l}</tspan>)}
    </text>
  )
}

// Graduation à gauche (barres horizontales) : le nom sur plusieurs lignes, centré sur la barre
function GraduationGauche({ x, y, payload, max }) {
  const lignes = couperEnLignes(payload.value, max)
  return (
    <text x={x - 6} y={y - ((lignes.length - 1) * 14) / 2 + 4} textAnchor="end" fontSize={12} fill={COULEUR_TEXTE_AXE}>
      {lignes.map((l, i) => <tspan key={i} x={x - 6} dy={i === 0 ? 0 : 14}>{l}</tspan>)}
    </text>
  )
}

// Quel filtre correspond aux catégories d'un graphique ? On compare les VALEURS (pas le nom de la colonne,
// qu'Atlas a pu renommer dans son calcul) : les barres « Jet Airways, IndiGo… » sont les valeurs du filtre « Compagnie ».
function filtreDuGraphique(filtres, valeursX, nomX) {
  const valeurs = valeursX.filter(v => v != null).map(String)
  if (valeurs.length < 2) return null
  let meilleur = null
  for (const f of filtres ?? []) {
    const connues = new Set(f.valeurs.map(v => String(v.valeur)))
    const trouvees = valeurs.filter(v => connues.has(v)).length
    const inconnues = valeurs.filter(v => !connues.has(v))
    // Toutes les barres doivent être des valeurs du filtre (sauf un éventuel regroupement « Autres »)
    if (trouvees < 2 || inconnues.some(v => !/^autres?$/i.test(v.trim()))) continue
    const score = (f.colonne === nomX ? 1000 : 0) + trouvees - connues.size / 1000
    if (!meilleur || score > meilleur.score) meilleur = { score, filtre: f, connues }
  }
  return meilleur
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

export default function GraphiqueDashboard({ graphique, resultat, numero, effectifMin = 30, filtres = [], onCliquerValeur, compact = false }) {
  const { donnees, series } = preparerDonnees(graphique, resultat)
  const plusLongNom = Math.max(0, ...donnees.map(d => String(d.x).length))
  // Des barres avec beaucoup de catégories ou des noms longs deviennent horizontales : les noms ont la place à gauche
  const type = graphique.type === 'barres' && (donnees.length > (compact ? 5 : 8) || plusLongNom > (compact ? 10 : 16))
    ? 'barres_horizontales' : graphique.type
  const petit = nb => nb != null && nb < effectifMin

  // Clic sur une barre = filtrer par cette valeur (si les barres sont les valeurs d'un filtre)
  const lien = onCliquerValeur ? filtreDuGraphique(filtres, donnees.map(d => d.x), graphique.x) : null
  const cliquable = !!lien
  // Recharts donne la barre cliquée : son nom est dans payload (d.x est sa position en pixels)
  const cliquer = d => {
    const valeur = d?.payload?.x
    if (lien && valeur != null && lien.connues.has(String(valeur))) onCliquerValeur(lien.filtre.colonne, String(valeur))
  }

  // Place pour les noms écrits sur plusieurs lignes
  const maxGauche = compact ? 13 : 20
  const lignesGauche = Math.max(1, ...donnees.map(d => couperEnLignes(d.x, maxGauche).length))
  const largeurGauche = Math.min(compact ? 100 : 150, 14 + 7 * Math.max(...donnees.map(d => Math.max(...couperEnLignes(d.x, maxGauche).map(l => l.length))), 4))
  const maxBas = Math.max(6, Math.floor((compact ? 300 : 520) / Math.max(1, donnees.length) / 7))
  const lignesBas = Math.max(1, ...donnees.map(d => couperEnLignes(d.x, maxBas).length))

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
  const labelX = { value: graphique.libelle_x, position: 'insideBottom', offset: -18, style: axeTexte }
  const marges = { top: 8, right: 12, bottom: 34, left: 8 }
  const hauteurAxeBas = 22 + (lignesBas - 1) * 14

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
        <YAxis type="category" dataKey="x" tick={<GraduationGauche max={maxGauche} />} width={largeurGauche} interval={0} />
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
        <XAxis dataKey="x" tick={<GraduationBas max={maxBas} />} interval={0} height={hauteurAxeBas} label={labelX} />
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
      <div style={{ height: type === 'barres_horizontales' ? Math.max(288, donnees.length * (lignesGauche * 14 + 16) + 70) : 288 + (lignesBas - 1) * 14 }}>
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
