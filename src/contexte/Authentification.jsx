// ═══ L'UTILISATEUR CONNECTÉ, PARTAGÉ AVEC TOUT LE SITE ═══
// Démarche :
//   1. au chargement, getSession() demande à Supabase Auth si quelqu'un est déjà connecté
//   2. onAuthStateChange() prévient à chaque connexion ou déconnexion
//   3. l'utilisateur est rangé dans un « contexte » React : toute page le lit avec useAuthentification()
// Le mot de passe est géré par Supabase, jamais par notre code.

import { createContext, useContext, useEffect, useState } from 'react'
import { supabase } from '../supabase'

// Supabase refuse d'écrire le profil tant que le mail n'est pas validé :
// le pseudo est gardé avec le compte et enregistré à la première connexion.
async function enregistrerPseudoEnAttente(utilisateur) {
  const pseudo = utilisateur.user_metadata?.pseudo
  if (!pseudo) return
  const { data } = await supabase.from('profiles').select('pseudo').eq('id', utilisateur.id).maybeSingle()
  if (!data?.pseudo) {
    await supabase.from('profiles').upsert({ id: utilisateur.id, pseudo })
  }
}

const ContexteAuth = createContext(null)

export function FournisseurAuth({ children }) {
  const [utilisateur, setUtilisateur] = useState(null)
  const [chargement, setChargement] = useState(true)

  useEffect(() => {
    // 1. Quelqu'un est-il déjà connecté ? (session gardée par le navigateur)
    supabase.auth.getSession().then(({ data }) => {
      setUtilisateur(data.session?.user ?? null)
      setChargement(false)
    })

    // 2. Être prévenu à chaque connexion ou déconnexion
    const { data: ecouteur } = supabase.auth.onAuthStateChange((_evenement, session) => {
      setUtilisateur(session?.user ?? null)
    })

    return () => ecouteur.subscription.unsubscribe()
  }, [])

  useEffect(() => {
    if (utilisateur) enregistrerPseudoEnAttente(utilisateur)
  }, [utilisateur])

  return (
    <ContexteAuth.Provider value={{ utilisateur, chargement }}>
      {children}
    </ContexteAuth.Provider>
  )
}

export function useAuthentification() {
  return useContext(ContexteAuth)
}