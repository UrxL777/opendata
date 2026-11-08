import { useEffect, useState, useRef, useCallback } from 'react'
import { useParams, Link } from 'react-router-dom'
import { Download, ArrowLeft, PanelLeftOpen, Send, MessageCircle, X, Maximize2, Minimize2 } from 'lucide-react'
import { supabase } from '../supabase'
import { IconeCategorie } from '../utilitaires/iconeCategorie'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'

function formaterTaille(octets) {
  if (!octets) return '—'
  if (octets < 1024) return `${octets} o`
  if (octets < 1024 * 1024) return `${(octets / 1024).toFixed(1)} Ko`
  return `${(octets / 1024 / 1024).toFixed(1)} Mo`
}

function RapportEnAttente() {
  useEffect(() => {
    const minuterie = setTimeout(() => {
      window.location.reload()
    }, 30000)
    return () => clearTimeout(minuterie)
  }, [])

  return (
    <div className="bg-blue-50 border border-blue-200 rounded-2xl p-5 mb-6">
      <div className="flex items-center gap-3 mb-2">
        <div className="w-2 h-2 bg-blue-400 rounded-full animate-pulse" />
        <h2 className="font-semibold text-blue-800">Analyse en préparation</h2>
      </div>
      <p className="text-sm text-blue-700">
        Ce jeu de données est en cours de traitement. Le rapport sera disponible dans quelques instants — cette page se met à jour automatiquement.
      </p>
    </div>
  )
}

function RapportNettoyage({ jeuId }) {
  const [rapport, setRapport] = useState(null)
  const [charge, setCharge] = useState(true)

  useEffect(() => {
    async function charger() {
      if (!jeuId) { setCharge(false); return }
      const { data } = await supabase
        .from('analyses')
        .select('resultats')
        .eq('fichier_id', jeuId)
        .eq('statut', 'termine')
        .maybeSingle()
      if (data?.resultats?.rapport) setRapport(data.resultats.rapport)
      setCharge(false)
    }
    charger()
  }, [jeuId])

  if (charge) return null
  if (!rapport) return <RapportEnAttente />

  const { lignes_avant, lignes_apres, lignes_supprimees, nb_colonnes, operations } = rapport

  return (
    <div className="bg-amber-50 border border-amber-200 rounded-2xl p-5 mb-6">
      <h2 className="font-semibold text-amber-800 mb-3">Rapport de nettoyage</h2>
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 mb-4 text-center">
        <div className="bg-white rounded-xl p-3">
          <p className="text-lg font-bold text-gray-800">{lignes_avant}</p>
          <p className="text-xs text-gray-400 mt-0.5">lignes au départ</p>
        </div>
        <div className="bg-white rounded-xl p-3">
          <p className="text-lg font-bold text-green-700">{lignes_apres}</p>
          <p className="text-xs text-gray-400 mt-0.5">lignes conservées</p>
        </div>
        <div className="bg-white rounded-xl p-3">
          <p className="text-lg font-bold text-red-500">{lignes_supprimees}</p>
          <p className="text-xs text-gray-400 mt-0.5">lignes supprimées</p>
        </div>
        {nb_colonnes != null && (
          <div className="bg-white rounded-xl p-3">
            <p className="text-lg font-bold text-blue-600">{nb_colonnes}</p>
            <p className="text-xs text-gray-400 mt-0.5">colonnes</p>
          </div>
        )}
      </div>
      {operations?.length > 0 && (
        <div>
          <p className="text-sm font-medium text-amber-800 mb-2">Ce qui a été nettoyé :</p>
          <ul className="space-y-1">
            {operations.map((op, i) => (
              <li key={i} className="text-sm text-amber-700 flex gap-2">
                <span className="text-amber-400 mt-0.5">•</span>
                <span>{op}</span>
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  )
}

function PanneauChat({ jeuId, estMobile, afficherHeader = true }) {
  const cleStockage = `chat_${jeuId}`

  const [messages, setMessages] = useState(() => {
    try {
      const sauvegardes = sessionStorage.getItem(`chat_${jeuId}`)
      if (sauvegardes) return JSON.parse(sauvegardes)
    } catch {}
    return []
  })
  const [saisie, setSaisie] = useState('')
  const [chargement, setChargement] = useState(false)
  const basMessages = useRef(null)

  useEffect(() => {
    try {
      sessionStorage.setItem(cleStockage, JSON.stringify(messages))
    } catch {}
  }, [messages, cleStockage])

  useEffect(() => {
    if (basMessages.current) {
      basMessages.current.scrollTop = basMessages.current.scrollHeight
    }
  }, [messages])

  async function envoyerMessage() {
    const texte = saisie.trim()
    if (!texte || chargement) return
    const nouveauxMessages = [...messages, { role: 'user', contenu: texte }]
    setMessages(nouveauxMessages)
    setSaisie('')
    setChargement(true)
    try {
      const res = await fetch(`${import.meta.env.VITE_API_URL}/chat`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          jeu_id: jeuId,
          messages: nouveauxMessages.map(m => ({ role: m.role, content: m.contenu }))
        })
      })
      const donnees = await res.json()
      setMessages(prev => [...prev, { role: 'assistant', contenu: donnees.reponse }])
    } catch {
      setMessages(prev => [...prev, { role: 'assistant', contenu: 'Erreur de connexion au serveur.' }])
    } finally {
      setChargement(false)
    }
  }

  function gererTouche(e) {
    if (e.key === 'Enter' && !e.shiftKey && !estMobile) {
      e.preventDefault()
      envoyerMessage()
    }
  }

  return (
    <div className="flex flex-col h-full">
      {afficherHeader && (
        <div className="p-3 border-b border-gray-200 shrink-0">
          <p className="font-semibold text-gray-800 text-sm">Atlas</p>
          <p className="text-xs text-gray-400">Questions sur ce jeu de données</p>
        </div>
      )}

      <div
        ref={basMessages}
        className="flex-1 overflow-y-auto p-3 space-y-2 min-h-0"
        style={{ overflowAnchor: 'none', overscrollBehaviorY: 'contain' }}
      >
        {messages.map((msg, i) => (
          <div key={i} className={`flex flex-col ${msg.role === 'user' ? 'items-end' : 'items-start'}`}>
            {msg.role === 'user' ? (
              <p className="text-sm text-gray-800 bg-gray-100 rounded-2xl px-3 py-2 max-w-[85%] whitespace-pre-wrap">
                {msg.contenu}
              </p>
            ) : (
              <div className="text-sm text-gray-800 max-w-[95%]">
                <ReactMarkdown
                  remarkPlugins={[remarkGfm]}
                  components={{
                    hr: () => null,
                    h2: ({ children }) => <p className="font-bold mt-3 mb-1">{children}</p>,
                    h3: ({ children }) => <p className="font-semibold mt-2 mb-1">{children}</p>,
                    strong: ({ children }) => <strong className="font-semibold">{children}</strong>,
                    ul: ({ children }) => <ul className="list-disc ml-4 space-y-0.5 my-1">{children}</ul>,
                    ol: ({ children }) => <ol className="list-decimal ml-4 space-y-0.5 my-1">{children}</ol>,
                    li: ({ children }) => <li>{children}</li>,
                    code: ({ inline, children }) => inline
                      ? <code className="bg-gray-100 px-1 rounded text-xs font-mono">{children}</code>
                      : <pre className="bg-gray-100 rounded p-2 text-xs font-mono overflow-x-auto my-1 whitespace-pre-wrap">{children}</pre>,
                    p: ({ children }) => <p className="mb-1 last:mb-0">{children}</p>,
                    table: ({ children }) => (
                      <div className="overflow-x-auto my-2">
                        <table className="text-xs border-collapse w-full">{children}</table>
                      </div>
                    ),
                    th: ({ children }) => <th className="border border-gray-200 px-2 py-1 bg-gray-100 font-semibold text-left">{children}</th>,
                    td: ({ children }) => <td className="border border-gray-200 px-2 py-1">{children}</td>,
                  }}
                >
                  {msg.contenu}
                </ReactMarkdown>
              </div>
            )}
          </div>
        ))}
        {chargement && (
          <div className="flex justify-start">
            <div className="bg-gray-100 rounded-2xl rounded-bl-sm px-3 py-2">
              <div className="flex gap-1 items-center h-4">
                <span className="w-1.5 h-1.5 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: '0ms' }} />
                <span className="w-1.5 h-1.5 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: '150ms' }} />
                <span className="w-1.5 h-1.5 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: '300ms' }} />
              </div>
            </div>
          </div>
        )}
      </div>

      <div className="p-3 border-t border-gray-200 shrink-0">
        <div className="flex gap-2 items-end">
          <textarea
            value={saisie}
            onChange={e => setSaisie(e.target.value)}
            onKeyDown={gererTouche}
            placeholder="Posez une question..."
            rows={1}
            className="flex-1 resize-none border border-gray-200 rounded-xl px-3 py-2 text-sm focus:outline-none focus:border-blue-400"
            style={{ maxHeight: '96px', overflowY: 'auto', fontSize: '16px' }}
            onInput={e => {
              e.target.style.height = '36px'
              e.target.style.height = Math.min(e.target.scrollHeight, 96) + 'px'
            }}
          />
          <button
            onClick={envoyerMessage}
            disabled={!saisie.trim() || chargement}
            className="bg-blue-600 hover:bg-blue-700 disabled:bg-gray-200 text-white disabled:text-gray-400 p-2 rounded-xl shrink-0 transition-colors"
          >
            <Send size={16} />
          </button>
        </div>
        <p className="text-xs text-gray-400 mt-2 text-center">
          Atlas est une IA et peut commettre des erreurs !
        </p>
      </div>
    </div>
  )
}

export default function Detail() {
  const { id } = useParams()
  const [jeu, setJeu] = useState(null)
  const [chargement, setChargement] = useState(true)
  const [panneauOuvert, setPanneauOuvert] = useState(true)
  const [pleinEcran, setPleinEcran] = useState(false)
  const [largeurPanneau, setLargeurPanneau] = useState(340)
  const [estMobile, setEstMobile] = useState(window.innerWidth < 768)
  const [sheetOuverte, setSheetOuverte] = useState(false)
  const [sheetPleinEcran, setSheetPleinEcran] = useState(false)
  const enRedimensionnement = useRef(false)
  const largeurDepart = useRef(0)
  const xDepart = useRef(0)

  useEffect(() => {
    const gerer = () => setEstMobile(window.innerWidth < 768)
    window.addEventListener('resize', gerer)
    return () => window.removeEventListener('resize', gerer)
  }, [])

  useEffect(() => {
    async function charger() {
      const { data } = await supabase
        .from('jeux_de_donnees')
        .select('*, categories(nom, description), fichiers(*)')
        .eq('id', id)
        .single()
      setJeu(data)
      setChargement(false)
    }
    charger()
  }, [id])

  const demarrerRedimensionnement = useCallback((e) => {
    enRedimensionnement.current = true
    xDepart.current = e.clientX
    largeurDepart.current = largeurPanneau
    e.preventDefault()
  }, [largeurPanneau])

  useEffect(() => {
    function deplacerSouris(e) {
      if (!enRedimensionnement.current) return
      const delta = e.clientX - xDepart.current
      const nouvelleLargeur = Math.min(600, Math.max(240, largeurDepart.current + delta))
      setLargeurPanneau(nouvelleLargeur)
    }
    function relacherSouris() {
      enRedimensionnement.current = false
    }
    window.addEventListener('mousemove', deplacerSouris)
    window.addEventListener('mouseup', relacherSouris)
    return () => {
      window.removeEventListener('mousemove', deplacerSouris)
      window.removeEventListener('mouseup', relacherSouris)
    }
  }, [])

  async function telecharger(fichier) {
    const { data } = supabase.storage.from('jeux-donnees').getPublicUrl(fichier.chemin_stockage)
    window.open(data.publicUrl, '_blank')
    await supabase.from('fichiers').update({ telechargements: (fichier.telechargements ?? 0) + 1 }).eq('id', fichier.id)
  }

  if (chargement) return <p className="text-center py-16 text-gray-400">Chargement...</p>
  if (!jeu) return <p className="text-center py-16 text-gray-400">Jeu de données introuvable.</p>

  const hauteurContenu = 'calc(100vh - 64px)'

  const contenuPrincipal = (
    <main className="max-w-4xl mx-auto px-4 py-10">
      <Link to="/donnees" className="flex items-center gap-1 text-sm text-gray-500 hover:text-blue-600 mb-6">
        <ArrowLeft size={16} /> Retour au catalogue
      </Link>

      <div className="flex gap-4 mb-6">
        <div className="bg-blue-50 p-3 rounded-xl shrink-0 h-fit">
          <IconeCategorie taille={28} className="text-blue-600" />
        </div>
        <div>
          <h1 className="text-2xl font-extrabold text-gray-900">{jeu.titre}</h1>
          {jeu.categories && (
            <span className="text-xs bg-gray-100 text-gray-600 px-2 py-0.5 rounded-full">{jeu.categories.nom}</span>
          )}
        </div>
      </div>

      {jeu.description && (
        <div className="bg-gray-50 rounded-2xl p-5 mb-6">
          <h2 className="font-semibold text-gray-700 mb-1">Description</h2>
          <p className="text-gray-600 text-sm">{jeu.description}</p>
        </div>
      )}

      <RapportNettoyage jeuId={jeu.id} />

      <div className="grid grid-cols-2 sm:grid-cols-3 gap-4 mb-8 text-sm">
        {jeu.source && (
          <div className="bg-white border border-gray-100 rounded-xl p-4">
            <p className="text-gray-400 text-xs mb-1">Source</p>
            <p className="font-medium">{jeu.source}</p>
          </div>
        )}
        <div className="bg-white border border-gray-100 rounded-xl p-4">
          <p className="text-gray-400 text-xs mb-1">Mis à jour le</p>
          <p className="font-medium">{new Date(jeu.mis_a_jour_le ?? jeu.cree_le).toLocaleDateString('fr-FR')}</p>
        </div>
        {jeu.categories && (
          <div className="bg-white border border-gray-100 rounded-xl p-4">
            <p className="text-gray-400 text-xs mb-1">Catégorie</p>
            <p className="font-medium">{jeu.categories.nom}</p>
          </div>
        )}
      </div>

      <h2 className="font-bold text-gray-900 mb-3">Fichiers disponibles</h2>
      <div className="space-y-3 mb-8">
        {jeu.fichiers?.map((fichier) => (
          <div key={fichier.id} className="bg-white border border-gray-100 rounded-2xl p-4 flex items-center justify-between gap-4">
            <div>
              <p className="font-medium text-gray-900 text-sm">{fichier.nom_fichier}</p>
              <div className="flex gap-3 text-xs text-gray-400 mt-1">
                <span className="bg-blue-50 text-blue-600 px-2 py-0.5 rounded uppercase font-medium">{fichier.format}</span>
                <span>{formaterTaille(fichier.taille)}</span>
                <span>{fichier.telechargements ?? 0} téléchargements</span>
              </div>
            </div>
            <button
              onClick={() => telecharger(fichier)}
              className="flex items-center gap-1 bg-blue-600 hover:bg-blue-700 text-white text-sm px-4 py-2 rounded-lg shrink-0"
            >
              <Download size={16} /> Télécharger
            </button>
          </div>
        ))}
      </div>
    </main>
  )

  if (estMobile) {
    return (
      <div className="relative" style={{ minHeight: hauteurContenu }}>
        <div className="overflow-y-auto" style={{ height: hauteurContenu, paddingBottom: '80px' }}>
          {contenuPrincipal}
        </div>

        {!sheetOuverte && (
          <button
            onClick={() => setSheetOuverte(true)}
            className="fixed bottom-6 right-4 flex items-center gap-2 bg-blue-600 text-white px-4 py-3 rounded-full shadow-lg text-sm font-semibold z-40"
          >
            <MessageCircle size={16} />
            Atlas
          </button>
        )}

        {sheetOuverte && !sheetPleinEcran && (
          <div className="fixed inset-0 bg-black/30 z-40" onClick={() => setSheetOuverte(false)} />
        )}

        {sheetOuverte && (
          <div
            className="fixed left-0 right-0 bg-white z-50 flex flex-col transition-all duration-300"
            style={{
              bottom: 0,
              height: sheetPleinEcran ? '100%' : '72%',
              borderRadius: sheetPleinEcran ? '0' : '16px 16px 0 0',
            }}
          >
            {!sheetPleinEcran && (
              <div className="flex justify-center pt-2 pb-1 shrink-0">
                <div className="w-9 h-1 bg-gray-300 rounded-full" />
              </div>
            )}
            <div className="flex items-center gap-3 px-4 py-3 border-b border-gray-200 shrink-0">
              <div className="bg-blue-600 rounded-xl p-2">
                <MessageCircle size={16} className="text-white" />
              </div>
              <div className="flex-1">
                <p className="font-semibold text-gray-800 text-sm">Atlas</p>
                <p className="text-xs text-gray-400">Questions sur ce jeu de données</p>
              </div>
              <button
                onClick={() => setSheetPleinEcran(!sheetPleinEcran)}
                className="p-1.5 rounded-lg hover:bg-gray-100 transition-colors mr-1"
              >
                {sheetPleinEcran
                  ? <Minimize2 size={16} className="text-gray-500" />
                  : <Maximize2 size={16} className="text-gray-500" />
                }
              </button>
              <button
                onClick={() => { setSheetOuverte(false); setSheetPleinEcran(false) }}
                className="p-1.5 rounded-lg hover:bg-gray-100 transition-colors"
              >
                <X size={16} className="text-gray-500" />
              </button>
            </div>
            <div className="flex-1 min-h-0">
              <PanneauChat jeuId={id} estMobile={true} afficherHeader={false} />
            </div>
          </div>
        )}
      </div>
    )
  }

  return (
    <div className="flex" style={{ height: hauteurContenu }}>
      {panneauOuvert && (
        <div
          className="flex flex-col border-r border-gray-200 bg-white shrink-0 overflow-hidden transition-all duration-200"
          style={{ width: pleinEcran ? '100%' : largeurPanneau, height: '100%' }}
        >
          <div className="flex items-center justify-end gap-1 px-2 pt-2 shrink-0">
            <button
              onClick={() => setPleinEcran(!pleinEcran)}
              className="p-1.5 rounded-lg hover:bg-gray-100 transition-colors"
            >
              {pleinEcran
                ? <Minimize2 size={15} className="text-gray-400" />
                : <Maximize2 size={15} className="text-gray-400" />
              }
            </button>
            <button
              onClick={() => { setPanneauOuvert(false); setPleinEcran(false) }}
              className="p-1.5 rounded-lg hover:bg-gray-100 transition-colors"
            >
              <X size={15} className="text-gray-400" />
            </button>
          </div>
          <div className="flex-1 min-h-0">
            <PanneauChat jeuId={id} estMobile={false} />
          </div>
        </div>
      )}

      {panneauOuvert && !pleinEcran && (
        <div
          onMouseDown={demarrerRedimensionnement}
          className="w-1 cursor-col-resize bg-gray-200 hover:bg-blue-400 transition-colors shrink-0"
          style={{ height: '100%' }}
        />
      )}

      {!pleinEcran && (
        <div className="flex-1 overflow-y-auto">
          {!panneauOuvert && (
            <div className="px-4 pt-4">
              <button
                onClick={() => setPanneauOuvert(true)}
                className="flex items-center gap-1.5 text-xs text-gray-500 hover:text-gray-800 border border-gray-200 rounded-lg px-2 py-1.5 transition-colors"
              >
                <PanelLeftOpen size={14} />
                Ouvrir Atlas
              </button>
            </div>
          )}
          {contenuPrincipal}
        </div>
      )}
    </div>
  )
}