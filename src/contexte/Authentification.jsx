import { createContext, useContext, useEffect, useState } from 'react'
import { supabase } from '../supabase'

const ContexteAuth = createContext(null)

export function FournisseurAuth({ children }) {
  const [utilisateur, setUtilisateur] = useState(null)
  const [chargement, setChargement] = useState(true)

  useEffect(() => {
    supabase.auth.getSession().then(({ data }) => {
      setUtilisateur(data.session?.user ?? null)
      setChargement(false)
    })

    const { data: ecouteur } = supabase.auth.onAuthStateChange((_evenement, session) => {
      setUtilisateur(session?.user ?? null)
    })

    return () => ecouteur.subscription.unsubscribe()
  }, [])

  return (
    <ContexteAuth.Provider value={{ utilisateur, chargement }}>
      {children}
    </ContexteAuth.Provider>
  )
}

export function useAuthentification() {
  return useContext(ContexteAuth)
}