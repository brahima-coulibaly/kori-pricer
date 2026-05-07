-- ============================================================
-- Script SQL — Nouveaux paramètres et colonnes (alignement TB Simulation livraison)
-- À exécuter dans l'éditeur SQL de Supabase
-- ============================================================

-- 1. Nouveaux paramètres dans la table `parametres`
INSERT INTO public.parametres (cle, valeur, unite, description) VALUES
    ('pesage', 2000, 'F CFA', 'Frais de pesage au pont-bascule'),
    ('frais_voyage', 5000, 'F CFA', 'Per diem / indemnité de déplacement chauffeur'),
    ('frais_route', 0, 'F CFA', 'Frais divers route (lavage, stationnement…)'),
    ('hebergement_nuit', 10000, 'F CFA/nuit', 'Coût hébergement par nuit pour le chauffeur'),
    ('maintenance_pct_ca', 0.0385, '%', 'Taux de maintenance en % du CA (3.85%)')
ON CONFLICT (cle) DO UPDATE SET
    valeur = EXCLUDED.valeur,
    unite = EXCLUDED.unite,
    description = EXCLUDED.description;


-- 2. Nouvelles colonnes dans la table `offres` (si elles n'existent pas)
DO $$
BEGIN
    -- Pesage
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_schema = 'public' AND table_name = 'offres' AND column_name = 'pesage') THEN
        ALTER TABLE public.offres ADD COLUMN pesage numeric DEFAULT 0;
    END IF;

    -- Frais de voyage
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_schema = 'public' AND table_name = 'offres' AND column_name = 'frais_voyage') THEN
        ALTER TABLE public.offres ADD COLUMN frais_voyage numeric DEFAULT 0;
    END IF;

    -- Frais de route
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_schema = 'public' AND table_name = 'offres' AND column_name = 'frais_route') THEN
        ALTER TABLE public.offres ADD COLUMN frais_route numeric DEFAULT 0;
    END IF;

    -- Frais d'hébergement
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_schema = 'public' AND table_name = 'offres' AND column_name = 'frais_hebergement') THEN
        ALTER TABLE public.offres ADD COLUMN frais_hebergement numeric DEFAULT 0;
    END IF;

    -- KPI : F CFA par km
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_schema = 'public' AND table_name = 'offres' AND column_name = 'fcfa_par_km') THEN
        ALTER TABLE public.offres ADD COLUMN fcfa_par_km numeric DEFAULT 0;
    END IF;

    -- KPI : Taux carburant / CA
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_schema = 'public' AND table_name = 'offres' AND column_name = 'taux_carburant_ca') THEN
        ALTER TABLE public.offres ADD COLUMN taux_carburant_ca numeric DEFAULT 0;
    END IF;

    -- KPI : Coût par kg
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_schema = 'public' AND table_name = 'offres' AND column_name = 'cout_par_kg') THEN
        ALTER TABLE public.offres ADD COLUMN cout_par_kg numeric DEFAULT 0;
    END IF;
END $$;
