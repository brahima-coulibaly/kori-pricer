-- ============================================================
-- Migration péages v2 : coordonnées corrigées + Eticoon-Tollakro
-- + rayon de détection personnalisé par péage
-- À exécuter dans l'éditeur SQL de Supabase
-- ============================================================

-- 1. Ajouter la colonne rayon_detection_km si elle n'existe pas
ALTER TABLE public.peages ADD COLUMN IF NOT EXISTS rayon_detection_km numeric DEFAULT NULL;

-- 2. Supprimer toutes les anciennes données et réinsérer
TRUNCATE public.peages RESTART IDENTITY;

INSERT INTO public.peages (nom, axe, latitude, longitude, tarif_classe4, rayon_detection_km) VALUES
    -- Autoroute du Nord (Abidjan - Yamoussoukro - Bouaké)
    ('Attinguié',       'Autoroute du Nord',           5.9392, -4.0741, 5000, NULL),
    ('Singrobo',        'Autoroute du Nord',           6.4500, -5.2000, 5000, NULL),
    ('Tiébissou',       'Autoroute du Nord',           7.1580, -5.2280, 5000, NULL),
    ('Djébounoua',      'Autoroute du Nord',           7.3700, -5.1500, 5000, NULL),

    -- Route de l'Est (vers Abengourou / Bondoukou)
    ('Thomasset',       'Route de l''Est',             6.0750, -3.8850, 3500, NULL),
    ('Moapé',           'Route de l''Est',             6.2400, -3.6400, 3500, NULL),
    ('Ebouassué',       'Route de l''Est',             6.9700, -3.2700, 3500, NULL),

    -- Autoroute Grand-Bassam / Sud-Comoé
    ('Grand-Bassam (Moossou)', 'Autoroute Grand-Bassam', 5.2150, -3.7400, 2500, NULL),
    ('Mondoukou',       'Autoroute Grand-Bassam',      5.2500, -3.5900, 2500, NULL),

    -- Ponts à péage d'Abidjan (rayon réduit : 1 km pour ne détecter que si on passe vraiment dessus)
    ('Pont HKB (3e Pont)',  'Pont Abidjan',            5.3100, -3.9850, 3000, 1.0),
    ('4e Pont',             'Pont Abidjan',            5.3450, -4.0550, 3000, 1.0),

    -- Axe N'Douci - Divo - Gagnoa (NOUVEAU : Eticoon-Tollakro ajouté)
    ('Eticoon-Tollakro',  'N''Douci - Divo - Gagnoa',   6.1000, -5.3600, 3500, NULL),
    ('Lakota',            'N''Douci - Divo - Gagnoa',    5.8500, -5.7000, 3500, NULL),

    -- Yamoussoukro - Daloa
    ('Diabo',           'Yamoussoukro - Daloa',        6.7800, -5.9200, 3500, NULL),

    -- Bouaké - Ferkessédougou
    ('Katiola',         'Bouaké - Ferkessédougou',     8.1400, -5.1000, 3500, NULL);
