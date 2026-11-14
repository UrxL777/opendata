-- ════════════════════════════════════════════════════════════════════
-- Table « dashboards » : le dashboard automatique créé par l'Analyste
-- À copier dans Supabase → SQL Editor → Run (une seule fois)
-- ════════════════════════════════════════════════════════════════════

create table if not exists public.dashboards (
  -- Un dashboard par jeu de données ; il est supprimé avec le jeu
  jeu_de_donnees_id bigint primary key
    references public.jeux_de_donnees (id) on delete cascade,

  -- en_cours : l'Analyste travaille · termine : prêt · erreur : échec
  statut text not null default 'en_cours'
    check (statut in ('en_cours', 'termine', 'erreur')),

  -- La fiche d'identité du jeu de données propre (colonnes, rôles, statistiques…)
  fiche jsonb,

  -- Le dashboard : chiffres clés, graphiques (avec leur requête SQL et leurs résultats), filtres
  contenu jsonb,

  -- Emplacement du jeu de données nettoyé dans le stockage (format Parquet)
  chemin_propre text,

  -- Message d'erreur éventuel (pour comprendre un échec)
  erreur text,

  cree_le timestamptz not null default now(),
  mis_a_jour_le timestamptz not null default now()
);

-- Sécurité : tout le monde peut LIRE les dashboards (comme les jeux de données).
-- Personne ne peut écrire depuis le site : seul le serveur, avec la clé de service, écrit.
alter table public.dashboards enable row level security;

drop policy if exists "Lecture publique des dashboards" on public.dashboards;
create policy "Lecture publique des dashboards"
  on public.dashboards
  for select
  using (true);
