// Mise en forme des chiffres des dashboards (KPI, axes, bulles d'information)

// 1234567.8 → « 1 234 568 » ; 12.34 → « 12,3 »
export function formaterNombre(valeur) {
  if (valeur === null || valeur === undefined || Number.isNaN(Number(valeur))) return '—'
  const n = Number(valeur)
  const decimales = Math.abs(n) >= 100 ? 0 : 1
  return n.toLocaleString('fr-FR', { maximumFractionDigits: decimales })
}

// Valeur d'un KPI selon son format (nombre, monnaie, pourcentage) et son unité
export function formaterKpi(kpi, valeur = kpi.valeur) {
  if (valeur === null || valeur === undefined) return '—'
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
