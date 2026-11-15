import { useEffect, useState, useRef } from 'react'
import { Send } from 'lucide-react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'

// Conversation avec Atlas (utilisée sur la page d'un dashboard)
export default function PanneauChat({ jeuId, estMobile, afficherHeader = true, sousTitre = 'Questions sur ce jeu de données' }) {
  const cleStockage = `chat_${jeuId}`

  const [messages, setMessages] = useState(() => {
    try {
      const sauvegardes = sessionStorage.getItem(`chat_${jeuId}`)
      if (sauvegardes) return JSON.parse(sauvegardes)
    } catch { /* stockage du navigateur indisponible : la conversation n'est simplement pas gardée */ }
    return []
  })
  const [saisie, setSaisie] = useState('')
  const [chargement, setChargement] = useState(false)
  const basMessages = useRef(null)

  useEffect(() => {
    try {
      sessionStorage.setItem(cleStockage, JSON.stringify(messages))
    } catch { /* stockage du navigateur indisponible : la conversation n'est simplement pas gardée */ }
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
        <div className="p-3 border-b border-bordure shrink-0">
          <p className="font-semibold text-texte text-sm">Atlas</p>
          <p className="text-xs text-texte-discret">{sousTitre}</p>
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
              <p className="text-sm text-texte bg-fond-gris rounded-2xl px-3 py-2 max-w-[85%] whitespace-pre-wrap">
                {msg.contenu}
              </p>
            ) : (
              <div className="text-sm text-texte max-w-[95%]">
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
                    // Bloc de code (plusieurs lignes) : grand cadre ; petit morceau dans une phrase : reste dans la phrase
                    pre: ({ children }) => <pre className="bg-fond-gris rounded p-2 text-xs font-mono overflow-x-auto my-1 whitespace-pre-wrap">{children}</pre>,
                    code: ({ className, children }) => (className || String(children).includes('\n'))
                      ? <code className="font-mono">{children}</code>
                      : <code className="bg-fond-gris px-1 py-0.5 rounded text-[0.85em] font-mono">{children}</code>,
                    p: ({ children }) => <p className="mb-1 last:mb-0">{children}</p>,
                    table: ({ children }) => (
                      <div className="overflow-x-auto my-2">
                        <table className="text-xs border-collapse w-full">{children}</table>
                      </div>
                    ),
                    th: ({ children }) => <th className="border border-bordure px-2 py-1 bg-fond-gris font-semibold text-left">{children}</th>,
                    td: ({ children }) => <td className="border border-bordure px-2 py-1">{children}</td>,
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
            <div className="bg-fond-gris rounded-2xl rounded-bl-sm px-3 py-2">
              <div className="flex gap-1 items-center h-4">
                <span className="w-1.5 h-1.5 bg-indicateur-saisie rounded-full animate-bounce" style={{ animationDelay: '0ms' }} />
                <span className="w-1.5 h-1.5 bg-indicateur-saisie rounded-full animate-bounce" style={{ animationDelay: '150ms' }} />
                <span className="w-1.5 h-1.5 bg-indicateur-saisie rounded-full animate-bounce" style={{ animationDelay: '300ms' }} />
              </div>
            </div>
          </div>
        )}
      </div>

      <div className="p-3 border-t border-bordure shrink-0">
        <div className="flex gap-2 items-end">
          <textarea
            value={saisie}
            onChange={e => setSaisie(e.target.value)}
            onKeyDown={gererTouche}
            placeholder="Posez une question..."
            rows={1}
            className="flex-1 resize-none border border-bordure rounded-xl px-3 py-2 text-sm focus:outline-none focus:border-bordure-bleu-doux"
            style={{ maxHeight: '96px', overflowY: 'auto', fontSize: '16px' }}
            onInput={e => {
              e.target.style.height = '36px'
              e.target.style.height = Math.min(e.target.scrollHeight, 96) + 'px'
            }}
          />
          <button
            onClick={envoyerMessage}
            disabled={!saisie.trim() || chargement}
            className="bg-principal hover:bg-principal-survol disabled:bg-fond-gris-moyen text-texte-inverse disabled:text-texte-discret p-2 rounded-xl shrink-0 transition-colors"
          >
            <Send size={16} />
          </button>
        </div>
        <p className="text-xs text-texte-discret mt-2 text-center">
          Atlas est une IA et peut commettre des erreurs !
        </p>
      </div>
    </div>
  )
}
