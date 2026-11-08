// Traduit en français les messages d'erreur renvoyés par Supabase Auth
const TRADUCTIONS = [
  [/invalid login credentials/i, 'Email ou mot de passe incorrect.'],
  [/email not confirmed/i, 'Veuillez confirmer votre adresse email avant de vous connecter (vérifiez vos spams).'],
  [/user already registered|already been registered/i, 'Un compte existe déjà avec cette adresse email.'],
  [/password should be at least/i, 'Le mot de passe doit contenir au moins 6 caractères.'],
  [/unable to validate email|invalid email|email address .* is invalid/i, 'Adresse email invalide.'],
  [/rate limit|too many requests|security purposes/i, 'Trop de tentatives. Patientez quelques minutes avant de réessayer.'],
  [/new password should be different/i, 'Le nouveau mot de passe doit être différent de l’ancien.'],
  [/failed to fetch|network/i, 'Connexion impossible. Vérifiez votre accès à internet.'],
]

export function traduireErreurAuth(message = '') {
  const trouve = TRADUCTIONS.find(([motif]) => motif.test(message))
  return trouve ? trouve[1] : 'Une erreur est survenue. Veuillez réessayer.'
}
