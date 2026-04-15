-- ============================================================================
-- Ajout des paramètres TMD (Transport de Matières Dangereuses) pour KORI Pricer
-- À exécuter dans Supabase → SQL Editor (nouvelle requête)
-- ============================================================================
-- Ces paramètres permettent de calculer la durée réelle et le nombre de jours
-- de mission d'un camion-citerne gaz (poids lourd TMD) en Côte d'Ivoire,
-- selon la réglementation locale et les pratiques opérationnelles.

insert into public.parametres (cle, valeur, unite, description) values
    ('vitesse_moyenne_pl_kmh', 50, 'km/h',
     'Vitesse moyenne effective d''un camion-citerne gaz (incluant pauses, contrôles, agglos)'),
    ('duree_max_conduite_jour_h', 9, 'h',
     'Durée maximale de conduite autorisée par chauffeur et par jour (réglementation TMD)'),
    ('marge_securite_temps_pct', 15, '%',
     'Marge de sécurité ajoutée au temps de conduite (imprévus, contrôles renforcés)')
on conflict (cle) do update
    set valeur = excluded.valeur,
        unite = excluded.unite,
        description = excluded.description;
