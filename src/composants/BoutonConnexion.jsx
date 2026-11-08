import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { supabase } from '../supabase'
import { useAuthentification } from '../contexte/Authentification'

function IcôneDeconnexion() {
  return (
    <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"/>
      <polyline points="16 17 21 12 16 7"/>
      <line x1="21" y1="12" x2="9" y2="12"/>
    </svg>
  )
}

function IcôneConnexion() {
  return (
    <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M15 3h4a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2h-4"/>
      <polyline points="10 17 15 12 10 7"/>
      <line x1="15" y1="12" x2="3" y2="12"/>
    </svg>
  )
}

function IcôneFermer() {
  return (
    <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <line x1="18" y1="6" x2="6" y2="18"/>
      <line x1="6" y1="6" x2="18" y2="18"/>
    </svg>
  )
}

function IcôneOeil({ visible }) {
  if (visible) {
    return (
      <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
        <path d="M17.94 17.94A10.07 10.07 0 0 1 12 20c-7 0-11-8-11-8a18.45 18.45 0 0 1 5.06-5.94"/>
        <path d="M9.9 4.24A9.12 9.12 0 0 1 12 4c7 0 11 8 11 8a18.5 18.5 0 0 1-2.16 3.19"/>
        <line x1="1" y1="1" x2="23" y2="23"/>
      </svg>
    )
  }
  return (
    <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/>
      <circle cx="12" cy="12" r="3"/>
    </svg>
  )
}

function BoutonUtilisateurConnecte({ utilisateur, onDeconnecter }) {
  const [pseudo, setPseudo] = useState('')

  useEffect(() => {
    async function chargerPseudo() {
      const { data } = await supabase
        .from('profiles')
        .select('pseudo')
        .eq('id', utilisateur.id)
        .maybeSingle()
      if (data?.pseudo) setPseudo(data.pseudo)
    }
    chargerPseudo()
  }, [utilisateur.id])

  return (
    <div className="flex items-center gap-2">
      {pseudo && (
        <span className="text-sm text-gray-700 font-medium">
          {pseudo}
        </span>
      )}
      <button
        onClick={onDeconnecter}
        className="flex items-center gap-1 text-sm text-gray-600 hover:text-red-600 border border-gray-200 px-3 py-2 rounded-lg"
      >
        <IcôneDeconnexion /> Déconnexion
      </button>
    </div>
  )
}

export default function BoutonConnexion() {
  const { utilisateur } = useAuthentification()
  const navigate = useNavigate()
  const [ouvert, setOuvert] = useState(false)
  const [vue, setVue] = useState('connexion')
  const [email, setEmail] = useState('')
  const [mdp, setMdp] = useState('')
  const [pseudo, setPseudo] = useState('')
  const [erreur, setErreur] = useState('')
  const [chargement, setChargement] = useState(false)
  const [inscriptionReussie, setInscriptionReussie] = useState(false)
  const [reinitReussie, setReinitReussie] = useState(false)
  const [mdpVisible, setMdpVisible] = useState(false)

  function ouvrir() {
    setOuvert(true)
    setVue('connexion')
    setEmail('')
    setMdp('')
    setPseudo('')
    setErreur('')
    setMdpVisible(false)
    setInscriptionReussie(false)
    setReinitReussie(false)
  }

  function fermer() { setOuvert(false) }

  function changerVue(v) {
    setVue(v)
    setEmail('')
    setMdp('')
    setPseudo('')
    setErreur('')
    setMdpVisible(false)
    setInscriptionReussie(false)
    setReinitReussie(false)
  }

  async function deconnecter() {
    await supabase.auth.signOut()
    navigate('/')
  }

  async function connecter(e) {
    e.preventDefault()
    setErreur('')
    setChargement(true)
    const { error } = await supabase.auth.signInWithPassword({ email, password: mdp })
    setChargement(false)
    if (error) { setErreur(error.message); return }
    fermer()
  }

  async function inscrire(e) {
    e.preventDefault()
    setErreur('')
    setChargement(true)
    const { data, error } = await supabase.auth.signUp({ email, password: mdp })
    if (error) { setChargement(false); setErreur(error.message); return }
    if (data?.user) {
      await supabase.from('profiles').upsert({ id: data.user.id, pseudo })
    }
    setChargement(false)
    setInscriptionReussie(true)
  }

  async function reinitialiserMotDePasse(e) {
    e.preventDefault()
    setErreur('')
    setChargement(true)
    const { error } = await supabase.auth.resetPasswordForEmail(email, {
      redirectTo: `${window.location.origin}/reinitialisation-mdp`,
    })
    setChargement(false)
    if (error) { setErreur(error.message); return }
    setReinitReussie(true)
  }

  if (utilisateur) {
    return <BoutonUtilisateurConnecte utilisateur={utilisateur} onDeconnecter={deconnecter} />
  }

  return (
    <>
      <button
        onClick={ouvrir}
        className="flex items-center gap-1 text-sm text-gray-600 hover:text-blue-600 border border-gray-200 px-4 py-2 rounded-lg"
      >
        <IcôneConnexion /> Se connecter
      </button>

      {ouvert && (
        <div
          className="fixed inset-0 bg-black/50 z-50 flex items-center justify-center p-4"
          onClick={fermer}
        >
          <div
            className="bg-white rounded-2xl w-full max-w-md p-6"
            onClick={e => e.stopPropagation()}
          >
            <div className="flex items-center justify-between mb-5">
              <h2 className="font-bold text-lg">
                {vue === 'connexion' && 'Se connecter'}
                {vue === 'inscription' && 'Créer un compte'}
                {vue === 'mot_de_passe_oublie' && 'Mot de passe oublié'}
              </h2>
              <button onClick={fermer} className="text-gray-400 hover:text-gray-600">
                <IcôneFermer />
              </button>
            </div>

            {vue === 'connexion' && (
              <form onSubmit={connecter} className="space-y-4">
                <div>
                  <label className="block text-sm font-medium mb-1">Email</label>
                  <input
                    type="email"
                    value={email}
                    onChange={e => setEmail(e.target.value)}
                    required
                    className="w-full border border-gray-300 rounded-lg px-4 py-3 focus:outline-none focus:border-blue-500"
                  />
                </div>
                <div>
                  <div className="flex items-center justify-between mb-1">
                    <label className="block text-sm font-medium">Mot de passe</label>
                    <button
                      type="button"
                      onClick={() => changerVue('mot_de_passe_oublie')}
                      className="text-xs text-blue-600 hover:underline"
                    >
                      Mot de passe oublié ?
                    </button>
                  </div>
                  <div className="relative">
                    <input
                      type={mdpVisible ? 'text' : 'password'}
                      value={mdp}
                      onChange={e => setMdp(e.target.value)}
                      required
                      className="w-full border border-gray-300 rounded-lg px-4 py-3 pr-11 focus:outline-none focus:border-blue-500"
                    />
                    <button
                      type="button"
                      onClick={() => setMdpVisible(v => !v)}
                      className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-400 hover:text-gray-600"
                    >
                      <IcôneOeil visible={mdpVisible} />
                    </button>
                  </div>
                </div>
                {erreur && <p className="text-red-600 text-sm">{erreur}</p>}
                <button
                  type="submit"
                  disabled={chargement}
                  className="w-full bg-blue-600 hover:bg-blue-700 disabled:opacity-60 text-white py-3 rounded-lg font-medium"
                >
                  {chargement ? 'Connexion...' : 'Se connecter'}
                </button>
                <p className="text-center text-sm text-gray-500">
                  Pas encore de compte ?{' '}
                  <button
                    type="button"
                    onClick={() => changerVue('inscription')}
                    className="text-blue-600 font-medium hover:underline"
                  >
                    S'inscrire
                  </button>
                </p>
              </form>
            )}

            {vue === 'inscription' && (
              inscriptionReussie ? (
                <div className="text-center py-4">
                  <p className="font-semibold text-gray-800 mb-2">Vérifiez votre email</p>
                  <p className="text-gray-500 text-sm">
                    Un lien de confirmation a été envoyé à <strong>{email}</strong>.
                  </p>
                  <button onClick={fermer} className="mt-4 text-sm text-blue-600 hover:underline">
                    Fermer
                  </button>
                </div>
              ) : (
                <form onSubmit={inscrire} className="space-y-4">
                  <div>
                    <label className="block text-sm font-medium mb-1">Pseudo</label>
                    <input
                      type="text"
                      value={pseudo}
                      onChange={e => setPseudo(e.target.value)}
                      required
                      placeholder="Votre nom d'affichage"
                      className="w-full border border-gray-300 rounded-lg px-4 py-3 focus:outline-none focus:border-blue-500"
                    />
                  </div>
                  <div>
                    <label className="block text-sm font-medium mb-1">Email</label>
                    <input
                      type="email"
                      value={email}
                      onChange={e => setEmail(e.target.value)}
                      required
                      className="w-full border border-gray-300 rounded-lg px-4 py-3 focus:outline-none focus:border-blue-500"
                    />
                  </div>
                  <div>
                    <label className="block text-sm font-medium mb-1">Mot de passe</label>
                    <div className="relative">
                      <input
                        type={mdpVisible ? 'text' : 'password'}
                        value={mdp}
                        onChange={e => setMdp(e.target.value)}
                        required
                        className="w-full border border-gray-300 rounded-lg px-4 py-3 pr-11 focus:outline-none focus:border-blue-500"
                      />
                      <button
                        type="button"
                        onClick={() => setMdpVisible(v => !v)}
                        className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-400 hover:text-gray-600"
                      >
                        <IcôneOeil visible={mdpVisible} />
                      </button>
                    </div>
                  </div>
                  {erreur && <p className="text-red-600 text-sm">{erreur}</p>}
                  <button
                    type="submit"
                    disabled={chargement}
                    className="w-full bg-blue-600 hover:bg-blue-700 disabled:opacity-60 text-white py-3 rounded-lg font-medium"
                  >
                    {chargement ? 'Inscription...' : "S'inscrire"}
                  </button>
                  <p className="text-center text-sm text-gray-500">
                    Déjà un compte ?{' '}
                    <button
                      type="button"
                      onClick={() => changerVue('connexion')}
                      className="text-blue-600 font-medium hover:underline"
                    >
                      Se connecter
                    </button>
                  </p>
                </form>
              )
            )}

            {vue === 'mot_de_passe_oublie' && (
              reinitReussie ? (
                <div className="text-center py-4">
                  <p className="font-semibold text-gray-800 mb-2">Email envoyé</p>
                  <p className="text-gray-500 text-sm">
                    Un lien de réinitialisation a été envoyé à <strong>{email}</strong>.
                    Vérifiez votre boîte de réception.
                  </p>
                  <button
                    onClick={() => changerVue('connexion')}
                    className="mt-4 text-sm text-blue-600 hover:underline"
                  >
                    Retour à la connexion
                  </button>
                </div>
              ) : (
                <form onSubmit={reinitialiserMotDePasse} className="space-y-4">
                  <p className="text-sm text-gray-500">
                    Entrez votre adresse email et nous vous enverrons un lien pour réinitialiser votre mot de passe.
                  </p>
                  <div>
                    <label className="block text-sm font-medium mb-1">Email</label>
                    <input
                      type="email"
                      value={email}
                      onChange={e => setEmail(e.target.value)}
                      required
                      className="w-full border border-gray-300 rounded-lg px-4 py-3 focus:outline-none focus:border-blue-500"
                    />
                  </div>
                  {erreur && <p className="text-red-600 text-sm">{erreur}</p>}
                  <button
                    type="submit"
                    disabled={chargement}
                    className="w-full bg-blue-600 hover:bg-blue-700 disabled:opacity-60 text-white py-3 rounded-lg font-medium"
                  >
                    {chargement ? 'Envoi...' : 'Envoyer le lien'}
                  </button>
                  <p className="text-center text-sm text-gray-500">
                    <button
                      type="button"
                      onClick={() => changerVue('connexion')}
                      className="text-blue-600 font-medium hover:underline"
                    >
                      Retour à la connexion
                    </button>
                  </p>
                </form>
              )
            )}
          </div>
        </div>
      )}
    </>
  )
}