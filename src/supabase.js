// ═══ LA CONNEXION À LA BASE SUPABASE ═══
// Crée UNE connexion (supabase-js), réutilisée par toutes les pages : import { supabase } from '../supabase'.
// L'adresse et la clé publique viennent des variables d'environnement (VITE_...), jamais écrites dans le code.
// La clé publique ne donne que les droits prévus par les règles de sécurité (RLS) de la base.

import { createClient } from '@supabase/supabase-js'

const SUPABASE_URL = import.meta.env.VITE_SUPABASE_URL
const SUPABASE_ANON_KEY = import.meta.env.VITE_SUPABASE_ANON_KEY
export const supabase = createClient(SUPABASE_URL, SUPABASE_ANON_KEY)