// Mise en forme des chiffres des dashboards (KPI, axes, bulles d'information)

// Au plus 2 décimales, sans zéros inutiles : 11567.56 → « 11 567,56 » ; 3.00 → « 3 » ; 12.5 → « 12,5 »
export function formaterNombre(valeur) {
  if (valeur === null || valeur === undefined || Number.isNaN(Number(valeur))) return '—'
  return Number(valeur).toLocaleString('fr-FR', { maximumFractionDigits: 2 })
}

// « 2019-03 » → « mars 2019 » (les autres valeurs restent telles quelles)
const MOIS = ['janvier', 'février', 'mars', 'avril', 'mai', 'juin', 'juillet', 'août', 'septembre', 'octobre', 'novembre', 'décembre']
export function libelleValeur(valeur) {
  const m = /^(\d{4})-(\d{2})$/.exec(String(valeur ?? ''))
  return m && +m[2] >= 1 && +m[2] <= 12 ? `${MOIS[+m[2] - 1]} ${m[1]}` : String(valeur ?? '')
}

// Valeur d'un KPI selon son format (nombre, monnaie, pourcentage) et son unité
export function formaterKpi(kpi, valeur = kpi.valeur) {
  if (valeur === null || valeur === undefined) return '—'
  if (kpi.texte) return String(valeur)   // chiffre clé écrit par Atlas, déjà mis en forme (« 17,06 litres »)
  const texte = formaterNombre(valeur)
  if (kpi.format === 'pourcentage') return `${texte} %`
  return kpi.unite ? `${texte} ${kpi.unite}` : texte
}

// Les messages courts quand le dashboard n'est pas encore prêt
export const MESSAGES_STATUT = {
  en_attente: 'Dashboard en file d’attente',
  en_cours: 'Création du dashboard en cours',
  erreur: 'Le dashboard n’a pas encore pu être créé',
}
