-- Ajout des colonnes frais_voyage et frais_hebergement à la table destinations
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_schema = 'public' AND table_name = 'destinations' AND column_name = 'frais_voyage') THEN
        ALTER TABLE public.destinations ADD COLUMN frais_voyage numeric DEFAULT 0;
    END IF;

    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_schema = 'public' AND table_name = 'destinations' AND column_name = 'frais_hebergement') THEN
        ALTER TABLE public.destinations ADD COLUMN frais_hebergement numeric DEFAULT 0;
    END IF;
END $$;
