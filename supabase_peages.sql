-- ============================================================
-- Table des postes de péage en Côte d'Ivoire
-- Classe 4 (3 essieux et plus) = tarif utilisé par KORI
-- ============================================================

CREATE TABLE IF NOT EXISTS public.peages (
    id serial PRIMARY KEY,
    nom text NOT NULL,
    axe text NOT NULL,
    latitude numeric,
    longitude numeric,
    tarif_classe4 numeric NOT NULL DEFAULT 0,
    actif boolean DEFAULT true,
    maj_le timestamptz DEFAULT now()
);

-- RLS
ALTER TABLE public.peages ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "Lecture peages pour authenticated" ON public.peages;
CREATE POLICY "Lecture peages pour authenticated" ON public.peages
    FOR SELECT TO authenticated USING (true);

DROP POLICY IF EXISTS "Modification peages pour authenticated" ON public.peages;
CREATE POLICY "Modification peages pour authenticated" ON public.peages
    FOR ALL TO authenticated USING (true) WITH CHECK (true);

-- ============================================================
-- Données : postes de péage (coordonnées GPS approximatives)
-- ============================================================
INSERT INTO public.peages (nom, axe, latitude, longitude, tarif_classe4) VALUES
    -- Autoroute du Nord (Abidjan - Yamoussoukro - Bouaké)
    ('Attinguié',       'Autoroute du Nord',           5.9000, -4.0700, 5000),
    ('Singrobo',        'Autoroute du Nord',           6.5000, -5.1800, 5000),
    ('Tiébissou',       'Autoroute du Nord',           7.1200, -5.2200, 5000),
    ('Djébounoua',      'Autoroute du Nord',           7.3200, -5.1800, 5000),

    -- Route de l'Est (vers Abengourou / Bondoukou)
    ('Thomasset',       'Route de l''Est',             6.0800, -3.8900, 3500),
    ('Moapé',           'Route de l''Est',             6.2500, -3.6500, 3500),
    ('Ebouassué',       'Route de l''Est',             6.9800, -3.2800, 3500),

    -- Autoroute Grand-Bassam / Sud-Comoé
    ('Grand-Bassam (Moossou)', 'Autoroute Grand-Bassam', 5.2200, -3.7300, 2500),
    ('Mondoukou',       'Autoroute Grand-Bassam',      5.2600, -3.5800, 2500),

    -- Ponts à péage d'Abidjan
    ('Pont HKB (3e Pont)',  'Pont Abidjan',            5.3200, -3.9800, 3000),
    ('4e Pont',             'Pont Abidjan',            5.3500, -4.0600, 3000),

    -- Autres axes intérieurs
    ('Lakota',          'N''Douci - Gagnoa',           5.8500, -5.7000, 3500),
    ('Diabo',           'Yamoussoukro - Daloa',        6.7800, -5.9200, 3500),
    ('Katiola',         'Bouaké - Ferkessédougou',     8.1400, -5.1000, 3500);
