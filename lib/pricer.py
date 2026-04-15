"""Logique de calcul du pricer — portage des formules Excel."""
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
    # Règle Excel : 0–300 / 301–600 / 601+ sur la distance A/R
    d = distance_ar_km or 0
    if d <= 300:
        return params.get("prime_0_300", 5000)
    if d <= 600:
        return params.get("prime_301_600", 10000)
    return params.get("prime_601_plus", 15000)


def calculer(destination: str, attelage: str, quantite_kg: float,
             autres_depenses: float = 0.0, prix_offert_kg: float | None = None,
             mode: str = "liste",
             distance_ar_override: float | None = None) -> OffreCalcul:
    """Calcule une offre.

    Si distance_ar_override est fourni (ex : calculé via OSRM pour un point hors
    liste), il remplace la distance stockée en base pour tous les calculs
    dépendant du kilométrage (carburant, maintenance, prime voyage, VT/km).
    Les péages et frais de mission restent ceux de la ville de référence.
    """
    params = load_params()
    dest = get_destination(destination) or {}
    veh = get_vehicule(attelage) or {}

    distance_ar = (float(distance_ar_override)
                   if distance_ar_override is not None and distance_ar_override > 0
                   else float(dest.get("distance_ar_km") or 0))
    peages_ar = float(dest.get("peages_ar") or 0)
    frais_mission = float(dest.get("frais_mission_unitaire") or 0)

    carburant = distance_ar * float(params.get("consommation_l_km", 0.5)) * float(params.get("prix_carburant", 675))
    maintenance = distance_ar * float(params.get("maintenance_km", 346))
    prime_voyage = prime_par_distance(distance_ar, params)
    lettre_voiture = float(params.get("lettre_voiture", 2500))
    charges_fixes_attelage = float(veh.get("charges_admin_livraison") or 0)
    vt_km_distance = distance_ar * float(veh.get("charges_admin_km") or 0)

    total_charges = (carburant + maintenance + peages_ar + frais_mission +
                     prime_voyage + lettre_voiture + autres_depenses +
                     charges_fixes_attelage + vt_km_distance)

    # Prix plancher : interpretation — marge cible 75% signifie couverture charges = 25% du CA
    # donc prix plancher = total_charges / (1 - marge_cible) / quantite
    marge_cible = float(params.get("marge_cible", 0.75))
    ratio = max(1 - marge_cible, 0.0001)
    prix_plancher_kg = (total_charges / ratio) / max(quantite_kg, 1)

    if prix_offert_kg is None or prix_offert_kg <= 0:
        prix_offert_kg = prix_plancher_kg

    ca_total = prix_offert_kg * quantite_kg
    marge_brute = ca_total - total_charges
    taux_marge = (marge_brute / ca_total) if ca_total else 0

    return OffreCalcul(
        destination=destination, attelage=attelage, quantite_kg=quantite_kg,
        autres_depenses=autres_depenses, mode=mode,
        distance_ar=distance_ar, peages_ar=peages_ar, frais_mission=frais_mission,
        carburant=carburant, maintenance=maintenance, prime_voyage=prime_voyage,
        lettre_voiture=lettre_voiture, charges_fixes_attelage=charges_fixes_attelage,
        vt_km_distance=vt_km_distance, total_charges=total_charges,
        prix_plancher_kg=prix_plancher_kg, prix_offert_kg=prix_offert_kg,
        ca_total=ca_total, marge_brute=marge_brute, taux_marge=taux_marge,
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
    # Format : KT-AAAAMMJJ-NNNN
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
