-- ─── Création du profil à l'inscription ─────────────────────────────────────────
-- L'automatisme « trigger_creer_profil » (sur auth.users) appelle cette fonction à chaque inscription.
-- Le pseudo tapé dans le formulaire est enregistré tout de suite dans « profiles ».
-- Sans pseudo, l'inscription est refusée : un compte ne peut pas exister sans pseudo.
-- À exécuter dans Supabase (SQL Editor). Peut être relancé sans risque.

create or replace function public.creer_profil()
returns trigger
language plpgsql
security definer
set search_path to 'public'
as $function$
declare
  pseudo_saisi text := nullif(trim(new.raw_user_meta_data->>'pseudo'), '');
begin
  if pseudo_saisi is null then
    raise exception 'Le pseudo est obligatoire pour créer un compte.';
  end if;
  insert into public.profiles (id, pseudo) values (new.id, pseudo_saisi);
  return new;
end;
$function$;

-- Réparation des anciens comptes : recopie le pseudo tapé à l'inscription dans les profils qui n'en ont pas
update public.profiles p
set pseudo = u.raw_user_meta_data->>'pseudo'
from auth.users u
where p.id = u.id
  and (p.pseudo is null or p.pseudo = '')
  and coalesce(u.raw_user_meta_data->>'pseudo', '') <> '';
