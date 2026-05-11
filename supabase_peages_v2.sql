-- ============================================================
-- Migration péages v2 : tarifs officiels classe 4 + coordonnées GPS réelles
-- À exécuter dans l'éditeur SQL de Supabase
-- ============================================================

-- 1. Ajouter la colonne rayon_detection_km si elle n'existe pas
ALTER TABLE public.peages ADD COLUMN IF NOT EXISTS rayon_detection_km numeric DEFAULT NULL;

-- 2. Supprimer toutes les anciennes données et réinsérer
TRUNCATE public.peages RESTART IDENTITY;

INSERT INTO public.peages (nom, axe, latitude, longitude, tarif_classe4, actif, rayon_detection_km) VALUES
    -- Autoroute du Nord (2 péages à Attinguié)
    ('Attinguié 1',     'Autoroute du Nord',           5.4614, -4.1873, 5000, true, NULL),
    ('Attinguié 2',     'Autoroute du Nord',           5.4706, -4.2015, 5000, true, NULL),
    ('Singrobo',        'Autoroute du Nord',           6.0704, -4.8923, 5000, true, NULL),
    ('Tiébissou',       'Autoroute du Nord',           7.0487, -5.2467, 2000, true, NULL),
    ('Djébounoua',      'Autoroute du Nord',           7.5416, -5.0850, 4000, true, NULL),

    -- Route de l'Est (vers Abengourou / Bondoukou)
    ('Thomasset',       'Route de l''Est',             6.0750, -3.8850, 3500, true, NULL),
    ('Moapé',           'Route de l''Est',             6.2400, -3.6400, 3500, true, NULL),
    ('Ebouassué',       'Route de l''Est',             6.9700, -3.2700, 3500, true, NULL),

    -- Autoroute Grand-Bassam / Sud-Comoé (rayon réduit)
    ('Grand-Bassam',    'Autoroute Grand-Bassam',      5.2150, -3.7400, 3500, true, 1.0),
    ('Mondoukou',       'Autoroute Grand-Bassam',      5.1939, -3.6339, 3500, true, 1.0),

    -- Ponts à péage d'Abidjan
    ('Pont HKB (3e Pont)',  'Pont Abidjan',            5.3100, -3.9850, 3000, true, 1.0),
    ('4e Pont',             'Pont Abidjan',            5.3450, -4.0550, 3000, false, 1.0),

    -- Axe N'Douci - Divo - Gagnoa
    ('Eticoon-Tollakro',  'N''Douci - Divo - Gagnoa',   5.9149, -4.9490, 3500, true, NULL),
    ('Lakota',            'N''Douci - Divo - Gagnoa',    5.8500, -5.7000, 3500, true, NULL),

    -- Yamoussoukro - Daloa - Man
    ('Bonzi',           'Yamoussoukro - Daloa',        6.9459, -5.5485, 3500, true, NULL),
    ('Diabo',           'Yamoussoukro - Daloa',        7.7704, -5.1403, 3500, true, NULL),
    ('Gonate',          'Daloa - Man',                 6.9072, -6.2841, 3500, true, NULL),

    -- Bouaké - Ferkessédougou
    ('Katiola',         'Bouaké - Ferkessédougou',     8.1400, -5.1000, 3500, true, NULL);
