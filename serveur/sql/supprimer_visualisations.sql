-- ─── Suppression de l'ancienne table « visualisations » ─────────────────────────
-- Elle contenait les dashboards que les utilisateurs publiaient eux-mêmes (code iframe Power BI, Tableau...).
-- Cette fonction a été retirée : les dashboards sont maintenant créés par Atlas (table « dashboards »).
-- À exécuter une seule fois dans Supabase (SQL Editor), APRÈS la mise en ligne du nouveau code.
-- Attention : la suppression est définitive.

drop table if exists public.visualisations;
