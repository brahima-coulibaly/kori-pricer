-- =========================================================================
-- KORI TRANSPORT — Pricer Web App — Schéma Supabase (PostgreSQL)
-- À exécuter dans Supabase → SQL Editor après création du projet
-- =========================================================================

-- 1) Table des profils utilisateurs (liée à auth.users de Supabase)
create table if not exists public.profiles (
    id uuid references auth.users on delete cascade primary key,
    email text unique not null,
    nom_complet text,
    role text not null default 'consultation'
        check (role in ('commercial','manager','admin','consultation')),
    actif boolean default true,
    cree_le timestamptz default now()
);

-- 2) Destinations
create table if not exists public.destinations (
    id serial primary key,
    localite text unique not null,
    distance_ar_km numeric default 0,
    peages_aller numeric default 0,
    peages_ar numeric default 0,
    frais_route numeric default 0,
    prime_voyage numeric default 0,
    frais_mission_unitaire numeric default 0,
    source text,
    prix_cible_kg numeric default 0,
    dist_gps_km numeric default 0,
    latitude numeric,
    longitude numeric,
    maj_le timestamptz default now()
);

-- 3) Véhicules (attelages)
create table if not exists public.vehicules (
    id serial primary key,
    attelage text unique not null,
    tracteur text,
    citerne text,
    nb_livraisons_an int default 30,
    km_annuel int default 50000,
    autorisation numeric default 0,
    carte_transport numeric default 0,
    carte_stationnement numeric default 0,
    patente numeric default 0,
    cert_epreuve_citerne numeric default 0,
    cert_epreuve_flexible numeric default 0,
    cert_etalonnage numeric default 0,
    cert_jaugeage numeric default 0,
    cert_sgs_temci numeric default 0,
    vt_citerne numeric default 0,
    vt_tracteur numeric default 0,
    charges_admin_livraison numeric default 0,
    charges_admin_km numeric default 0,
    actif boolean default true,
    maj_le timestamptz default now()
);

-- 4) Paramètres globaux (clé/valeur)
create table if not exists public.parametres (
    cle text primary key,
    valeur numeric not null,
    unite text,
    description text,
    maj_le timestamptz default now()
);

-- 5) Offres (historique)
create table if not exists public.offres (
    id serial primary key,
    numero text unique not null,
    date_offre date default current_date,
    user_id uuid references auth.users on delete set null,
    user_email text,
    destination text not null,
    attelage text not null,
    quantite_kg numeric not null,
    autres_depenses numeric default 0,
    mode text default 'liste', -- 'liste' ou 'gps'
    distance_ar numeric,
    peages_ar numeric,
    frais_mission numeric,
    carburant numeric,
    maintenance numeric,
    prime_voyage numeric,
    lettre_voiture numeric,
    charges_fixes_attelage numeric,
    vt_km_distance numeric,
    total_charges numeric,
    prix_plancher_kg numeric,
    prix_offert_kg numeric,
    ca_total numeric,
    marge_brute numeric,
    taux_marge numeric,
    statut text default 'brouillon' check (statut in ('brouillon','valide','envoye','accepte','refuse')),
    notes text,
    cree_le timestamptz default now(),
    maj_le timestamptz default now()
);

-- 6) Row Level Security
alter table public.profiles enable row level security;
alter table public.destinations enable row level security;
alter table public.vehicules enable row level security;
alter table public.parametres enable row level security;
alter table public.offres enable row level security;

-- Helper: fonction pour récupérer le rôle courant
create or replace function public.current_user_role() returns text
language sql stable security definer as $$
    select role from public.profiles where id = auth.uid();
$$;

-- Policies — profiles
drop policy if exists "profile read self" on public.profiles;
create policy "profile read self" on public.profiles for select
    using (auth.uid() = id or public.current_user_role() = 'admin');
drop policy if exists "profile admin all" on public.profiles;
create policy "profile admin all" on public.profiles for all
    using (public.current_user_role() = 'admin');

-- Policies — tables de référence (destinations, vehicules, parametres) :
-- lecture pour tous les utilisateurs authentifiés, écriture admin uniquement
drop policy if exists "ref read" on public.destinations;
create policy "ref read" on public.destinations for select using (auth.role() = 'authenticated');
drop policy if exists "ref admin write" on public.destinations;
create policy "ref admin write" on public.destinations for all using (public.current_user_role() = 'admin');

drop policy if exists "ref read" on public.vehicules;
create policy "ref read" on public.vehicules for select using (auth.role() = 'authenticated');
drop policy if exists "ref admin write" on public.vehicules;
create policy "ref admin write" on public.vehicules for all using (public.current_user_role() = 'admin');

drop policy if exists "ref read" on public.parametres;
create policy "ref read" on public.parametres for select using (auth.role() = 'authenticated');
drop policy if exists "ref admin write" on public.parametres;
create policy "ref admin write" on public.parametres for all using (public.current_user_role() = 'admin');

-- Policies — offres
-- Lecture : tous les authentifiés (commercial voit tout, c'est voulu pour le MVP)
drop policy if exists "offre read all auth" on public.offres;
create policy "offre read all auth" on public.offres for select using (auth.role() = 'authenticated');

-- Création : commercial, manager, admin
drop policy if exists "offre insert" on public.offres;
create policy "offre insert" on public.offres for insert
    with check (public.current_user_role() in ('commercial','manager','admin'));

-- Modification : l'auteur OU manager/admin
drop policy if exists "offre update" on public.offres;
create policy "offre update" on public.offres for update
    using (user_id = auth.uid() or public.current_user_role() in ('manager','admin'));

-- Suppression : manager/admin uniquement
drop policy if exists "offre delete" on public.offres;
create policy "offre delete" on public.offres for delete
    using (public.current_user_role() in ('manager','admin'));

-- Trigger : créer un profil auto à l'inscription (rôle consultation par défaut)
create or replace function public.handle_new_user() returns trigger
language plpgsql security definer as $$
begin
    insert into public.profiles (id, email, role)
    values (new.id, new.email, 'consultation')
    on conflict (id) do nothing;
    return new;
end;
$$;

drop trigger if exists on_auth_user_created on auth.users;
create trigger on_auth_user_created
    after insert on auth.users
    for each row execute function public.handle_new_user();
