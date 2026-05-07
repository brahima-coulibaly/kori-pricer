"""Logique de calcul du pricer — aligné sur le TB Simulation livraison."""
from __future__ import annotations
import math
from dataclasses import dataclass, asdict
from .db import sb


@dataclass
class OffreCalcul:
    destination: str
    attelage: str
    quantite_kg: float
    autres_depenses: float = 0.0
    mode: str = "liste"
    # Champs calculés
    distance_ar: float = 0.0
    peages_ar: float = 0.0
    pesage: float = 0.0
    frais_voyage: float = 0.0
    frais_route: float = 0.0
    frais_hebergement: float = 0.0
    frais_mission: float = 0.0
    carburant: float = 0.0
    maintenance: float = 0.0
    prime_voyage: float = 0.0
    lettre_voiture: float = 0.0
    charges_fixes_attelage: float = 0.0
    vt_km_distance: float = 0.0
    total_charges: float = 0.0
    prix_plancher_kg: float = 0.0
    prix_offert_kg: float = 0.0
    ca_total: float = 0.0
    marge_brute: float = 0.0
    taux_marge: float = 0.0
    # KPIs
    fcfa_par_km: float = 0.0
    taux_carburant_ca: float = 0.0
    cout_par_kg: float = 0.0

    def to_dict(self):
        return asdict(self)


def load_params() -> dict:
    rows = sb().table("parametres").select("cle,valeur").execute().data or []
    return {r["cle"]: float(r["valeur"]) for r in rows}


def get_destination(localite: str) -> dict | None:
    res = sb().table("destinations").select("*").eq("localite", localite).execute()
    return res.data[0] if res.data else None


def get_vehicule(attelage: str) -> dict | None:
    res = sb().table("vehicules").select("*").eq("attelage", attelage).execute()
    return res.data[0] if res.data else None


def prime_par_distance(distance_ar_km: float, params: dict) -> float:
    d = distance_ar_km or 0
    if d <= 300:
        return params.get("prime_0_300", 5000)
    if d <= 600:
        return params.get("prime_301_600", 10000)
    return params.get("prime_601_plus", 15000)


def calculer(destination: str, attelage: str, quantite_kg: float,
             autres_depenses: float = 0.0, prix_offert_kg: float | None = None,
             mode: str = "liste",
             distance_ar_override: float | None = None,
             peages_ar_override: float | None = None,
             frais_mission_override: float | None = None,
             pesage_override: float | None = None,
             frais_voyage_override: float | None = None,
             frais_route_override: float | None = None,
             nuits_hebergement: int = 0,
             cout_hebergement_nuit: float | None = None) -> OffreCalcul:
    """Calcule une offre — aligné sur le TB Simulation livraison Excel.

    Postes de charges (comme dans le fichier Excel) :
    - Carburant : (distance_ar / 2) litres × prix_carburant
    - Péages A/R
    - Pesage
    - Frais de voyage (per diem chauffeur)
    - Frais de route
    - Prime de voyage (par palier de distance)
    - Frais d'hébergement (nuits × coût/nuit)
    - Frais de mission
    - Lettre de voiture
    - Coût de maintenance (% du CA ou par km)
    - Autres dépenses
    - Charges fixes attelage + VT/km
    """
    params = load_params()
    dest = get_destination(destination) or {}
    veh = get_vehicule(attelage) or {}

    # --- Valeurs de base (overridables) ---
    distance_ar = (float(distance_ar_override)
                   if distance_ar_override is not None and distance_ar_override > 0
                   else float(dest.get("distance_ar_km") or 0))
    peages_ar = (float(peages_ar_override)
                 if peages_ar_override is not None and peages_ar_override >= 0
                 else float(dest.get("peages_ar") or 0))
    frais_mission = (float(frais_mission_override)
                     if frais_mission_override is not None and frais_mission_override >= 0
                     else float(dest.get("frais_mission_unitaire") or 0))

    # --- Nouveaux postes de charges ---
    pesage = (float(pesage_override) if pesage_override is not None and pesage_override >= 0
              else float(params.get("pesage", 2000)))
    frais_voyage = (float(frais_voyage_override) if frais_voyage_override is not None
                    and frais_voyage_override >= 0
                    else float(dest.get("frais_voyage") or 0))
    frais_route = (float(frais_route_override) if frais_route_override is not None
                   and frais_route_override >= 0
                   else float(params.get("frais_route", 0)))

    # Hébergement : valeur depuis la destination (pas les paramètres globaux)
    frais_hebergement = (float(cout_hebergement_nuit) if cout_hebergement_nuit is not None
                         and cout_hebergement_nuit >= 0
                         else float(dest.get("frais_hebergement") or 0))

    # --- Carburant (formule Excel : distance_ar/2 = litres, × prix/litre) ---
    prix_carburant = float(params.get("prix_carburant", 675))
    consommation = float(params.get("consommation_l_km", 0.5))
    carburant = distance_ar * consommation * prix_carburant

    # --- Prime de voyage (par palier) ---
    prime_voyage = prime_par_distance(distance_ar, params)

    # --- Lettre de voiture ---
    lettre_voiture = float(params.get("lettre_voiture", 2500))

    # --- Charges liées à l'attelage ---
    charges_fixes_attelage = float(veh.get("charges_admin_livraison") or 0)
    vt_km_distance = distance_ar * float(veh.get("charges_admin_km") or 0)

    # --- Total charges (hors maintenance sur CA) ---
    total_charges_base = (carburant + peages_ar + pesage + frais_voyage + frais_route +
                          frais_hebergement + frais_mission + prime_voyage +
                          lettre_voiture + autres_depenses +
                          charges_fixes_attelage + vt_km_distance)

    # --- Maintenance : % du CA si paramètre disponible, sinon par km ---
    taux_maintenance_ca = params.get("maintenance_pct_ca", 0.0385)
    maintenance_km = float(params.get("maintenance_km", 0))

    # On calcule d'abord sans maintenance pour déterminer le prix plancher provisoire
    # puis on ajuste avec la maintenance
    # Facteur multiplicateur maintenance (Excel : × 1.1)
    facteur_maintenance = float(params.get("facteur_maintenance", 1.1))

    if taux_maintenance_ca > 0:
        # Maintenance = CA × taux × facteur (formule Excel : =+C23*D23*1.1)
        taux_effectif = taux_maintenance_ca * facteur_maintenance
        marge_cible = float(params.get("marge_cible", 0.75))
        denom = max(1 - taux_effectif - marge_cible, 0.0001)
        ca_plancher = total_charges_base / denom
        prix_plancher_kg = ca_plancher / max(quantite_kg, 1)

        if prix_offert_kg is None or prix_offert_kg <= 0:
            prix_offert_kg = prix_plancher_kg

        ca_total = prix_offert_kg * quantite_kg
        maintenance = ca_total * taux_effectif
    else:
        # Maintenance par km (ancien mode)
        maintenance = distance_ar * maintenance_km
        total_with_maint = total_charges_base + maintenance

        marge_cible = float(params.get("marge_cible", 0.75))
        ratio = max(1 - marge_cible, 0.0001)
        prix_plancher_kg = (total_with_maint / ratio) / max(quantite_kg, 1)

        if prix_offert_kg is None or prix_offert_kg <= 0:
            prix_offert_kg = prix_plancher_kg

        ca_total = prix_offert_kg * quantite_kg

    total_charges = total_charges_base + maintenance
    marge_brute = ca_total - total_charges
    taux_marge = (marge_brute / ca_total) if ca_total else 0

    # --- KPIs ---
    fcfa_par_km = (ca_total / distance_ar) if distance_ar else 0
    taux_carburant_ca = (carburant / ca_total) if ca_total else 0
    cout_par_kg = (total_charges / max(quantite_kg, 1))

    return OffreCalcul(
        destination=destination, attelage=attelage, quantite_kg=quantite_kg,
        autres_depenses=autres_depenses, mode=mode,
        distance_ar=distance_ar, peages_ar=peages_ar, pesage=pesage,
        frais_voyage=frais_voyage, frais_route=frais_route,
        frais_hebergement=frais_hebergement, frais_mission=frais_mission,
        carburant=carburant, maintenance=maintenance, prime_voyage=prime_voyage,
        lettre_voiture=lettre_voiture, charges_fixes_attelage=charges_fixes_attelage,
        vt_km_distance=vt_km_distance, total_charges=total_charges,
        prix_plancher_kg=prix_plancher_kg, prix_offert_kg=prix_offert_kg,
        ca_total=ca_total, marge_brute=marge_brute, taux_marge=taux_marge,
        fcfa_par_km=fcfa_par_km, taux_carburant_ca=taux_carburant_ca,
        cout_par_kg=cout_par_kg,
    )


def haversine_km(lat1, lon1, lat2, lon2) -> float:
    R = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp/2)**2 + math.cos(p1)*math.cos(p2)*math.sin(dl/2)**2
    return 2 * R * math.asin(math.sqrt(a))


def ville_la_plus_proche(lat: float, lon: float) -> tuple[dict | None, float]:
    rows = sb().table("destinations").select("localite,latitude,longitude").execute().data or []
    best, best_d = None, float("inf")
    for r in rows:
        if r["latitude"] is None or r["longitude"] is None:
            continue
        d = haversine_km(lat, lon, float(r["latitude"]), float(r["longitude"]))
        if d < best_d:
            best, best_d = r, d
    return best, best_d


def generer_numero_offre() -> str:
    from datetime import datetime
    today = datetime.now().strftime("%Y%m%d")
    res = sb().table("offres").select("numero").like("numero", f"KT-{today}-%").execute()
    n = len(res.data or []) + 1
    return f"KT-{today}-{n:04d}"


def enregistrer_offre(calc: OffreCalcul, user_id: str | None, user_email: str | None,
                      numero: str | None = None, statut: str = "brouillon",
                      notes: str = "") -> dict:
    numero = numero or generer_numero_offre()
    payload = calc.to_dict()
    payload.update({
        "numero": numero,
        "user_id": user_id,
        "user_email": user_email,
        "statut": statut,
        "notes": notes,
    })
    res = sb().table("offres").insert(payload).execute()
    return res.data[0] if res.data else payload
