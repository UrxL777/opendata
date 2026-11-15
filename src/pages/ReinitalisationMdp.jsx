import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { supabase } from '../supabase'
import { traduireErreurAuth } from '../utilitaires/erreursAuth'

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

export default function ReinitalisationMdp() {
  const navigate = useNavigate()
  const [mdp, setMdp] = useState('')
  const [confirmation, setConfirmation] = useState('')
  const [erreur, setErreur] = useState('')
  const [chargement, setChargement] = useState(false)
  const [succes, setSucces] = useState(false)
  const [sessionValide, setSessionValide] = useState(false)
  const [mdpVisible, setMdpVisible] = useState(false)
  const [confirmationVisible, setConfirmationVisible] = useState(false)

  useEffect(() => {
    supabase.auth.getSession().then(({ data }) => {
      if (data.session) setSessionValide(true)
      else setErreur('Lien invalide ou expiré. Demandez un nouveau lien.')
    })
  }, [])

  async function reinitialiser(e) {
    e.preventDefault()
    if (mdp !== confirmation) { setErreur('Les mots de passe ne correspondent pas.'); return }
    if (mdp.length < 6) { setErreur('Le mot de passe doit contenir au moins 6 caractères.'); return }
    setErreur('')
    setChargement(true)
    const { error } = await supabase.auth.updateUser({ password: mdp })
    setChargement(false)
    if (error) { setErreur(traduireErreurAuth(error.message)); return }
    setSucces(true)
    setTimeout(() => navigate('/'), 2000)
  }

  return (
    <div className="min-h-screen flex items-center justify-center p-4 bg-fond-doux">
      <div className="bg-fond rounded-2xl w-full max-w-md p-8 shadow-sm">
        <h1 className="font-bold text-xl mb-6">Nouveau mot de passe</h1>

        {succes ? (
          <div className="text-center py-4">
            <p className="font-semibold text-texte mb-2">Mot de passe mis à jour !</p>
            <p className="text-sm text-texte-doux">Vous allez être redirigé vers l'accueil...</p>
          </div>
        ) : !sessionValide ? (
          <p className="text-texte-erreur text-sm">{erreur}</p>
        ) : (
          <form onSubmit={reinitialiser} className="space-y-4">
            <div>
              <label className="block text-sm font-medium mb-1">Nouveau mot de passe</label>
              <div className="relative">
                <input
                  type={mdpVisible ? 'text' : 'password'}
                  placeholder="6 caractères minimum"
                  value={mdp}
                  onChange={e => setMdp(e.target.value)}
                  required
                  className="w-full border border-bordure-champ rounded-lg px-4 py-3 pr-11 focus:outline-none focus:border-bordure-focus"
                />
                <button
                  type="button"
                  onClick={() => setMdpVisible(v => !v)}
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-texte-discret hover:text-texte-secondaire"
                >
                  <IcôneOeil visible={mdpVisible} />
                </button>
              </div>
            </div>
            <div>
              <label className="block text-sm font-medium mb-1">Confirmer le mot de passe</label>
              <div className="relative">
                <input
                  type={confirmationVisible ? 'text' : 'password'}
                  placeholder="Retapez le mot de passe"
                  value={confirmation}
                  onChange={e => setConfirmation(e.target.value)}
                  required
                  className="w-full border border-bordure-champ rounded-lg px-4 py-3 pr-11 focus:outline-none focus:border-bordure-focus"
                />
                <button
                  type="button"
                  onClick={() => setConfirmationVisible(v => !v)}
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-texte-discret hover:text-texte-secondaire"
                >
                  <IcôneOeil visible={confirmationVisible} />
                </button>
              </div>
            </div>
            {erreur && <p className="text-texte-erreur text-sm">{erreur}</p>}
            <button
              type="submit"
              disabled={chargement}
              className="w-full bg-principal hover:bg-principal-survol disabled:opacity-60 text-texte-inverse py-3 rounded-lg font-medium"
            >
              {chargement ? 'Mise à jour...' : 'Mettre à jour'}
            </button>
          </form>
        )}
      </div>
    </div>
  )
}