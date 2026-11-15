import { useCallback, useEffect, useRef, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { ArrowLeft, ChartColumnBig, MessageCircle, X, Maximize2, Minimize2, Loader2, Clock, CircleAlert, FolderOpen } from 'lucide-react'
import { supabase } from '../supabase'
import PanneauChat from '../composants/PanneauChat'
import FiltresDashboard from '../composants/dashboard/FiltresDashboard'
import GraphiqueDashboard from '../composants/dashboard/GraphiqueDashboard'
import { formaterKpi, formaterNombre, MESSAGES_STATUT } from '../utilitaires/formatDashboard'

const SOUS_TITRE_ATLAS = 'Questions sur ce dashboard'

// Vrai sur un écran de téléphone (moins de 768 pixels de large)
function useEstMobile() {
  const [estMobile, setEstMobile] = useState(() => window.innerWidth < 768)
  useEffect(() => {
    const gerer = () => setEstMobile(window.innerWidth < 768)
    window.addEventListener('resize', gerer)
    return () => window.removeEventListener('resize', gerer)
  }, [])
  return estMobile
}

// Hauteur de la barre de navigation : la zone du dashboard prend exactement le reste de l'écran
function useHauteurNavigation() {
  const [hauteur, setHauteur] = useState(101)
  useEffect(() => {
    const mesurer = () => setHauteur(document.querySelector('header')?.offsetHeight ?? 101)
    mesurer()
    window.addEventListener('resize', mesurer)
    return () => window.removeEventListener('resize', mesurer)
  }, [])
  return hauteur
}

// Carte d'un indicateur clé, avec « calculé sur N lignes » en gris
function CarteKpi({ kpi }) {
  return (
    <div className="bg-fond border border-bordure-legere rounded-xl p-3 shadow-sm">
      <p className="text-2xl font-bold text-principal">{formaterKpi(kpi)}</p>
      <p className="text-xs text-texte-doux mt-0.5">{kpi.titre}</p>
      {kpi.nb != null && (
        <p className="text-xs text-texte-discret mt-1">
          calculé sur {formaterNombre(kpi.nb)} ligne{kpi.nb > 1 ? 's' : ''}
          {kpi.nb_sans_valeur > 0 ? ` (${formaterNombre(kpi.nb_sans_valeur)} sans valeur)` : ''}
        </p>
      )}
    </div>
  )
}

// Message court quand le dashboard n'est pas encore prêt
function StatutDashboard({ statut }) {
  const Icone = { en_attente: Clock, en_cours: Loader2, erreur: CircleAlert }[statut] ?? Clock
  return (
    <div className="bg-fond border border-bordure-legere rounded-2xl p-10 shadow-sm flex flex-col items-center text-center gap-3 mt-6">
      <Icone size={28} className={`text-principal ${statut === 'en_cours' ? 'animate-spin' : ''}`} />
      <p className="font-semibold text-texte">{MESSAGES_STATUT[statut] ?? MESSAGES_STATUT.en_attente}</p>
      {statut !== 'erreur' && <p className="text-xs text-texte-discret">Cette page se met à jour toute seule.</p>}
    </div>
  )
}

export default function Dashboard() {
  const { id } = useParams()
  const estMobile = useEstMobile()
  const hauteurNavigation = useHauteurNavigation()

  const [jeu, setJeu] = useState(null)
  const [ligne, setLigne] = useState(null)          // { statut, contenu } de la table dashboards
  const [chargement, setChargement] = useState(true)
  const [choix, setChoix] = useState({})            // filtres choisis : { colonne: [valeurs] }
  const [recalcul, setRecalcul] = useState(null)    // KPI et graphiques recalculés pour ces filtres
  const [enCalcul, setEnCalcul] = useState(false)
  const [erreurFiltre, setErreurFiltre] = useState('')
  const [atlasOuvert, setAtlasOuvert] = useState(true)
  const [atlasPleinEcran, setAtlasPleinEcran] = useState(false)
  const [atlasMobile, setAtlasMobile] = useState(false)
  const numeroRequete = useRef(0)

  // Chargement du jeu et de son dashboard ; si le dashboard n'est pas prêt, on revérifie toutes les 15 secondes
  useEffect(() => {
    let annule = false, minuterie = null
    async function charger() {
      const [{ data: j }, { data: d }] = await Promise.all([
        supabase.from('jeux_de_donnees').select('id, titre, categories(nom)').eq('id', id).maybeSingle(),
        supabase.from('dashboards').select('statut, contenu').eq('jeu_de_donnees_id', id).maybeSingle(),
      ])
      if (annule) return
      setJeu(j); setLigne(d); setChargement(false)
      if (d && ['en_attente', 'en_cours'].includes(d.statut)) minuterie = setTimeout(charger, 15000)
    }
    charger()
    return () => { annule = true; clearTimeout(minuterie) }
  }, [id])

  // Atlas en plein écran sur mobile : la page derrière ne bouge plus
  useEffect(() => {
    if (!atlasMobile) return
    const avant = document.body.style.overflow
    document.body.style.overflow = 'hidden'
    return () => { document.body.style.overflow = avant }
  }, [atlasMobile])

  // Les filtres : le serveur relance les calculs déjà écrits par Atlas (aucun appel à l'IA)
  const appliquerFiltres = useCallback(async (nouveauChoix) => {
    setChoix(nouveauChoix)
    const actifs = Object.fromEntries(Object.entries(nouveauChoix).filter(([, v]) => v.length))
    if (!Object.keys(actifs).length) { setRecalcul(null); setErreurFiltre(''); return }
    const numero = ++numeroRequete.current
    setEnCalcul(true)
    try {
      const rep = await fetch(`${import.meta.env.VITE_API_URL}/dashboard/filtrer`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ jeu_id: String(id), filtres: actifs }),
      })
      if (!rep.ok) throw new Error()
      const donnees = await rep.json()
      if (numero !== numeroRequete.current) return   // une réponse plus récente est déjà demandée
      setRecalcul(donnees); setErreurFiltre('')
    } catch {
      if (numero === numeroRequete.current) setErreurFiltre('Les filtres n’ont pas pu être appliqués. Réessaie dans un instant.')
    } finally {
      if (numero === numeroRequete.current) setEnCalcul(false)
    }
  }, [id])

  if (chargement) return <p className="text-center py-16 text-texte-discret">Chargement...</p>
  if (!jeu) return <p className="text-center py-16 text-texte-discret">Dashboard introuvable.</p>

  const contenu = ligne?.statut === 'termine' ? ligne.contenu : null
  const filtres = contenu?.filtres ?? []
  const effectifMin = contenu?.effectif_min ?? 30

  // Valeurs affichées : celles d'origine, ou celles recalculées pour les filtres
  const kpiAffiches = (contenu?.kpi ?? []).map(k => {
    const r = recalcul?.kpi?.find(x => x.id === k.id)
    return r ? { ...k, valeur: r.valeur, nb: r.nb, nb_sans_valeur: r.nb_sans_valeur } : k
  })
  const resultatDe = g => {
    if (!recalcul) return g.resultat
    return recalcul.graphiques?.find(x => x.id === g.id)?.resultat ?? { colonnes: [], lignes: [] }
  }
  const cliquerValeur = (colonne, valeur) => {
    const actuel = choix[colonne] ?? []
    appliquerFiltres({ ...choix, [colonne]: actuel.length === 1 && actuel[0] === valeur ? [] : [valeur] })
  }
  const resumeFiltres = Object.entries(choix).filter(([, v]) => v.length)
    .map(([c, v]) => `${filtres.find(f => f.colonne === c)?.libelle ?? c} = ${v.join(', ')}`).join(' ; ')

  const page = (
    <div className={estMobile ? 'px-4 py-5' : 'max-w-6xl mx-auto px-6 py-6'}>
      <Link to="/dashboards" className="flex items-center gap-1.5 text-sm text-texte-doux hover:text-principal mb-5">
        <ArrowLeft size={16} /> Retour aux dashboards
      </Link>

      <div className="flex items-start justify-between gap-3">
        <div className="flex gap-4">
          <div className="bg-fond-bleu-clair p-3 rounded-xl shrink-0 h-fit">
            <ChartColumnBig size={28} className="text-principal" />
          </div>
          <div>
            <h1 className={`${estMobile ? 'text-xl' : 'text-2xl'} font-extrabold text-texte-titre`}>{jeu.titre}</h1>
            <div className="flex items-center gap-2 mt-1 flex-wrap">
              {jeu.categories && <span className="text-xs bg-fond-gris text-texte-secondaire px-2 py-0.5 rounded-full">{jeu.categories.nom}</span>}
              <span className="text-xs text-texte-discret">Dashboard créé par Atlas</span>
              <Link to={`/donnees/${jeu.id}`} className="flex items-center gap-1 text-xs text-principal hover:underline">
                <FolderOpen size={12} /> Voir le jeu de données
              </Link>
            </div>
          </div>
        </div>
        {!estMobile && !atlasOuvert && contenu && (
          <button onClick={() => setAtlasOuvert(true)}
            className="flex items-center gap-2 bg-principal hover:bg-principal-survol text-texte-inverse px-3 py-2 rounded-lg text-sm font-medium shrink-0">
            <MessageCircle size={16} /> Ouvrir Atlas
          </button>
        )}
      </div>

      {!contenu ? <StatutDashboard statut={ligne?.statut ?? 'en_attente'} /> : (
        <>
          <p className="text-texte-bleu-nuit font-semibold mt-4 mb-3">{contenu.comprehension?.question_centrale}</p>

          <FiltresDashboard filtres={filtres} choix={choix}
            onChanger={(colonne, valeurs) => appliquerFiltres({ ...choix, [colonne]: valeurs })}
            onReinitialiser={() => appliquerFiltres({})} />
          {resumeFiltres && (
            <p className="text-xs text-texte-principal-fonce mt-2 flex items-center gap-2">
              {enCalcul && <Loader2 size={12} className="animate-spin" />}
              Filtre actif : {resumeFiltres}. Tous les indicateurs et graphiques sont recalculés.
            </p>
          )}
          {erreurFiltre && <p className="text-xs text-texte-erreur mt-2">{erreurFiltre}</p>}

          <div className={`transition-opacity ${enCalcul ? 'opacity-60' : ''}`}>
            {kpiAffiches.length > 0 && (
              <div className={`grid gap-3 my-4 ${estMobile ? 'grid-cols-2' : ['grid-cols-1', 'grid-cols-2', 'grid-cols-3', 'grid-cols-4'][Math.min(kpiAffiches.length, 4) - 1]}`}>
                {kpiAffiches.map(k => <CarteKpi key={k.id} kpi={k} />)}
              </div>
            )}

            {/* Deux graphiques par ligne quand il y a la place ; un seul quand Atlas est ouvert */}
            <div className={`grid grid-cols-1 gap-4 ${atlasOuvert && !estMobile ? '2xl:grid-cols-2' : 'lg:grid-cols-2'}`}>
              {(contenu.graphiques ?? []).map((g, i) => (
                <GraphiqueDashboard key={g.id} graphique={g} resultat={resultatDe(g)} numero={i + 1} effectifMin={effectifMin}
                  filtres={filtres} onCliquerValeur={cliquerValeur} compact={estMobile} />
              ))}
            </div>
          </div>

          {contenu.conclusion && !resumeFiltres && (
            <div className="bg-fond-bleu-clair border border-bordure-bleu-pale rounded-2xl p-4 mt-4">
              <p className="text-sm text-texte-bleu-nuit"><span className="font-semibold">Conclusion d’Atlas :</span> {contenu.conclusion}</p>
            </div>
          )}
        </>
      )}
    </div>
  )

  // ─── Mobile : le dashboard, et Atlas en plein écran par-dessus ───
  if (estMobile) {
    return (
      <>
        <div className="pb-20">{page}</div>
        {contenu && !atlasMobile && (
          <button onClick={() => setAtlasMobile(true)}
            className="fixed bottom-6 right-4 flex items-center gap-2 bg-principal text-texte-inverse px-4 py-3 rounded-full shadow-lg text-sm font-semibold z-40">
            <MessageCircle size={16} /> Atlas
          </button>
        )}
        {atlasMobile && (
          <div className="fixed inset-0 z-50 bg-fond flex flex-col" style={{ height: '100dvh' }}>
            <div className="flex items-center gap-3 px-4 py-3 border-b border-bordure shrink-0">
              <div className="bg-principal rounded-xl p-2"><MessageCircle size={16} className="text-texte-inverse" /></div>
              <div className="flex-1">
                <p className="font-semibold text-texte text-sm">Atlas</p>
                <p className="text-xs text-texte-discret">{SOUS_TITRE_ATLAS}</p>
              </div>
              <button onClick={() => setAtlasMobile(false)} aria-label="Fermer Atlas" className="p-2 rounded-lg hover:bg-fond-gris">
                <X size={18} className="text-texte-doux" />
              </button>
            </div>
            <div className="flex-1 min-h-0" style={{ paddingBottom: 'env(safe-area-inset-bottom)' }}>
              <PanneauChat jeuId={id} estMobile={true} afficherHeader={false} />
            </div>
          </div>
        )}
      </>
    )
  }

  // ─── Ordinateur : Atlas à gauche, fixé à la hauteur de l'écran ; le dashboard défile à droite ───
  return (
    <div className="flex" style={{ height: `calc(100dvh - ${hauteurNavigation}px)` }}>
      {contenu && atlasOuvert && (
        <aside className="flex flex-col bg-fond border-r border-bordure shrink-0 h-full"
          style={{ width: atlasPleinEcran ? '100%' : 340 }}>
          <div className="flex items-center justify-between px-3 pt-3 pb-3 border-b border-bordure shrink-0">
            <div>
              <p className="font-semibold text-texte text-sm">Atlas</p>
              <p className="text-xs text-texte-discret">{SOUS_TITRE_ATLAS}</p>
            </div>
            <div className="flex items-center gap-1">
              <button onClick={() => setAtlasPleinEcran(p => !p)} aria-label="Agrandir Atlas" className="p-1.5 rounded-lg hover:bg-fond-gris">
                {atlasPleinEcran ? <Minimize2 size={15} className="text-texte-discret" /> : <Maximize2 size={15} className="text-texte-discret" />}
              </button>
              <button onClick={() => { setAtlasOuvert(false); setAtlasPleinEcran(false) }} aria-label="Fermer Atlas" className="p-1.5 rounded-lg hover:bg-fond-gris">
                <X size={15} className="text-texte-discret" />
              </button>
            </div>
          </div>
          <div className="flex-1 min-h-0">
            <PanneauChat jeuId={id} estMobile={false} afficherHeader={false} />
          </div>
        </aside>
      )}
      {!(contenu && atlasOuvert && atlasPleinEcran) && (
        <main className="flex-1 overflow-y-auto">{page}</main>
      )}
    </div>
  )
}
