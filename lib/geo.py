"""Géocodage (Nominatim/OpenStreetMap) + routing (OSRM) + helpers cartographiques."""
from __future__ import annotations
import time
import urllib.request
import json
import streamlit as st
from geopy.geocoders import Nominatim
from geopy.extra.rate_limiter import RateLimiter

# Point de départ : garage KORI à Abidjan (Ancienne voie de Bassam)
GARAGE_KORI = (5.226602842285156, -3.8468095585081135)

# Bounding box Côte d'Ivoire pour restreindre les recherches
CI_BBOX = {
    "south": 4.0, "north": 10.8,
    "west": -8.7, "east": -2.4,
}

# Serveur OSRM public (démo officielle project-osrm.org)
OSRM_BASE = "https://router.project-osrm.org"


@st.cache_resource
def _geocoder():
    return Nominatim(user_agent="kori-pricer-ci/1.0 (contact: kori-transport)", timeout=10)


def _search_raw(query: str, limit: int = 5):
    """Appel brut Nominatim avec limitation de débit (1 req/s)."""
    geolocator = _geocoder()
    search = RateLimiter(geolocator.geocode, min_delay_seconds=1, max_retries=2)
    viewbox = [(CI_BBOX["north"], CI_BBOX["west"]), (CI_BBOX["south"], CI_BBOX["east"])]
    return search(query, exactly_one=False, limit=limit, viewbox=viewbox,
                  bounded=False, country_codes="ci", language="fr")


@st.cache_data(ttl=3600, show_spinner=False)
def chercher_lieu(query: str, limit: int = 5) -> list[dict]:
    """Renvoie une liste de candidats [{display_name, lat, lon, address}] pour un texte."""
    if not query or len(query.strip()) < 2:
        return []
    try:
        results = _search_raw(query.strip(), limit=limit)
    except Exception:
        return []
    if not results:
        try:
            geolocator = _geocoder()
            search = RateLimiter(geolocator.geocode, min_delay_seconds=1)
            results = search(query.strip(), exactly_one=False, limit=limit, language="fr")
        except Exception:
            results = None
    if not results:
        return []
    return [{
        "display_name": r.address,
        "lat": r.latitude,
        "lon": r.longitude,
        "raw": r.raw,
    } for r in results]


@st.cache_data(ttl=3600, show_spinner=False)
def reverse_geocode(lat: float, lon: float) -> str | None:
    try:
        geolocator = _geocoder()
        rev = RateLimiter(geolocator.reverse, min_delay_seconds=1)
        r = rev((lat, lon), language="fr")
        return r.address if r else None
    except Exception:
        return None


# ---------- Routing OSRM (distance routière réelle + itinéraire) ----------

@st.cache_data(ttl=86400, show_spinner=False)
def calculer_trajet(lat1: float, lon1: float, lat2: float, lon2: float,
                    waypoints: tuple | None = None) -> dict | None:
    """Calcule le trajet routier entre deux points via OSRM, avec waypoints optionnels.

    waypoints : tuple de (lat, lon) intermédiaires pour forcer le passage par
    des points précis (ex : passer par Bonoua plutôt que par Alepe).
    Utilise un tuple (et non une liste) pour être compatible avec st.cache_data.

    Retourne un dict {distance_km, duration_min, geometry} ou None en cas d'échec.
    """
    try:
        # Construction des coordonnées : départ ; waypoint1 ; waypoint2 ; … ; arrivée
        points = [f"{lon1},{lat1}"]
        if waypoints:
            for wlat, wlon in waypoints:
                points.append(f"{wlon},{wlat}")
        points.append(f"{lon2},{lat2}")
        coords_str = ";".join(points)

        url = (f"{OSRM_BASE}/route/v1/driving/{coords_str}"
               f"?overview=full&geometries=geojson&alternatives=false&steps=false")
        req = urllib.request.Request(url, headers={"User-Agent": "kori-pricer-ci/1.0"})
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        if data.get("code") != "Ok" or not data.get("routes"):
            return None
        route = data["routes"][0]
        # GeoJSON coordinates are [lon, lat] → Folium attend [lat, lon]
        coords = [[c[1], c[0]] for c in route["geometry"]["coordinates"]]
        return {
            "distance_km": route["distance"] / 1000.0,
            "duration_min": route["duration"] / 60.0,
            "geometry": coords,
        }
    except Exception:
        return None


def trajet_depuis_garage(lat: float, lon: float,
                         waypoints: tuple | None = None) -> dict | None:
    """Raccourci : trajet aller depuis le garage KORI vers un point, avec waypoints."""
    try:
        return calculer_trajet(GARAGE_KORI[0], GARAGE_KORI[1], lat, lon, waypoints=waypoints)
    except TypeError:
        # Fallback sans cache si erreur de type (ex: problème de hash)
        return _calculer_trajet_no_cache(GARAGE_KORI[0], GARAGE_KORI[1], lat, lon, waypoints)


def _calculer_trajet_no_cache(lat1, lon1, lat2, lon2, waypoints=None):
    """Version sans cache de calculer_trajet (fallback)."""
    try:
        points = [f"{lon1},{lat1}"]
        if waypoints:
            for wlat, wlon in waypoints:
                points.append(f"{wlon},{wlat}")
        points.append(f"{lon2},{lat2}")
        coords_str = ";".join(points)
        url = (f"{OSRM_BASE}/route/v1/driving/{coords_str}"
               f"?overview=full&geometries=geojson&alternatives=false&steps=false")
        req = urllib.request.Request(url, headers={"User-Agent": "kori-pricer-ci/1.0"})
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        if data.get("code") != "Ok" or not data.get("routes"):
            return None
        route = data["routes"][0]
        coords = [[c[1], c[0]] for c in route["geometry"]["coordinates"]]
        return {
            "distance_km": route["distance"] / 1000.0,
            "duration_min": route["duration"] / 60.0,
            "geometry": coords,
        }
    except Exception:
        return None


def duree_pratique_pl(distance_km: float, vitesse_moyenne_kmh: float = 50,
                       marge_securite_pct: float = 15) -> float:
    """Calcule la durée pratique (en minutes) d'un trajet pour un camion-citerne TMD.

    Bien plus réaliste que la durée OSRM qui est calibrée sur des voitures légères.
    Prend en compte la vitesse moyenne effective (incluant pauses, contrôles,
    agglomérations) et ajoute une marge de sécurité pour les imprévus.
    """
    if not distance_km or vitesse_moyenne_kmh <= 0:
        return 0
    heures = distance_km / vitesse_moyenne_kmh
    heures *= (1 + marge_securite_pct / 100.0)
    return heures * 60


def nombre_jours_mission(duree_aller_min: float, duree_max_jour_h: float = 9) -> int:
    """Nombre de jours de mission nécessaires pour un aller-retour, selon la
    réglementation TMD (9h de conduite max par jour + nuit sur place si long).
    """
    if not duree_aller_min:
        return 1
    heures_ar = (duree_aller_min / 60) * 2  # aller + retour
    import math
    return max(1, math.ceil(heures_ar / duree_max_jour_h))


# ---------- Détection des péages sur l'itinéraire ----------

def detecter_peages_sur_trajet(geometry: list[list[float]], rayon_km: float = 5.0,
                                diagnostic: bool = False) -> list[dict] | tuple[list[dict], list[dict]]:
    """Détecte quels postes de péage sont traversés par un itinéraire OSRM.

    geometry : liste de [lat, lon] constituant la polyline du trajet.
    rayon_km : distance max entre un point de la route et un péage pour
               considérer qu'il est traversé (défaut 5 km).
    diagnostic : si True, retourne aussi la liste de TOUS les péages avec
                 leur distance min à la route (pour le calibrage GPS).

    Chaque péage peut avoir un rayon_detection_km personnalisé en base
    (ex : rayon réduit pour les ponts urbains). Sinon le rayon par défaut
    est utilisé.

    Retourne la liste des péages détectés (triés par ordre du trajet).
    Si diagnostic=True, retourne (détectés, tous_avec_distances).
    """
    from .db import sb
    import math

    # Charger tous les péages actifs
    rows = sb().table("peages").select("*").eq("actif", True).execute().data or []
    if not rows or not geometry:
        if diagnostic:
            return [], []
        return []

    def _haversine(lat1, lon1, lat2, lon2):
        R = 6371.0
        p1, p2 = math.radians(lat1), math.radians(lat2)
        dp = math.radians(lat2 - lat1)
        dl = math.radians(lon2 - lon1)
        a = math.sin(dp/2)**2 + math.cos(p1)*math.cos(p2)*math.sin(dl/2)**2
        return 2 * R * math.asin(math.sqrt(a))

    # Échantillonner la géométrie densément (1 point sur 2) pour ne rien rater
    sample = geometry[::2]
    if geometry[-1] not in sample:
        sample.append(geometry[-1])

    # Zone de départ : ignorer les péages détectés dans les premiers 15 km
    # du trajet (zone urbaine Abidjan — les péages ici sont des ponts/voies
    # rapides qui ne concernent pas les trajets inter-villes poids lourds).
    # On calcule l'indice sample correspondant à ~15 km depuis le départ.
    seuil_depart_km = 15.0
    idx_seuil_depart = 0
    cumul_km = 0.0
    for i in range(1, len(sample)):
        cumul_km += _haversine(sample[i-1][0], sample[i-1][1],
                               sample[i][0], sample[i][1])
        if cumul_km >= seuil_depart_km:
            idx_seuil_depart = i
            break

    peages_detectes = []
    tous_peages = []  # Pour le diagnostic
    for peage in rows:
        plat = peage.get("latitude")
        plon = peage.get("longitude")
        if plat is None or plon is None:
            continue
        plat, plon = float(plat), float(plon)

        # Rayon personnalisé si défini en base, sinon rayon par défaut
        rayon_peage = float(peage.get("rayon_detection_km") or rayon_km)

        # Trouver le point le plus proche sur le trajet
        min_dist = float("inf")
        min_idx = 0
        best_pt = None
        for i, pt in enumerate(sample):
            d = _haversine(pt[0], pt[1], plat, plon)
            if d < min_dist:
                min_dist = d
                min_idx = i
                best_pt = pt

        # Un péage est détecté s'il est dans le rayon ET en dehors de la zone
        # de départ (sauf s'il a un rayon personnalisé très petit, signe qu'il
        # a été volontairement calibré par l'admin).
        dans_rayon = min_dist <= rayon_peage
        en_zone_depart = min_idx <= idx_seuil_depart
        # Les péages avec rayon personnalisé (ponts, etc.) ne sont détectés
        # que si le trajet passe EXACTEMENT dessus ET hors zone de départ
        est_peage_urbain = peage.get("rayon_detection_km") is not None
        detecte = dans_rayon and not en_zone_depart

        info = {
            "nom": peage["nom"],
            "axe": peage["axe"],
            "tarif": float(peage["tarif_classe4"]),
            "distance_route_km": round(min_dist, 1),
            "ordre": min_idx,
            "lat_peage": plat,
            "lon_peage": plon,
            "lat_route": best_pt[0] if best_pt else None,
            "lon_route": best_pt[1] if best_pt else None,
            "rayon": rayon_peage,
            "detecte": detecte,
            "en_zone_depart": en_zone_depart,
        }

        if detecte:
            peages_detectes.append(info)
        tous_peages.append(info)

    # Trier par ordre d'apparition sur le trajet
    peages_detectes.sort(key=lambda x: x["ordre"])
    tous_peages.sort(key=lambda x: x["distance_route_km"])

    if diagnostic:
        return peages_detectes, tous_peages
    return peages_detectes


# ---------- Cartes Folium ----------

def carte_folium(lat: float | None = None, lon: float | None = None,
                 zoom: int = 7, route_depuis_garage: bool = False,
                 marker_label: str | None = None,
                 vrai_itineraire: bool = True,
                 waypoints: tuple | None = None):
    """Crée une carte Folium avec waypoints optionnels.

    Si route_depuis_garage et vrai_itineraire sont True, on trace le vrai
    itinéraire routier OSRM (en passant par les waypoints si fournis).
    """
    import folium
    center = (lat, lon) if (lat is not None and lon is not None) else (7.5, -5.5)
    m = folium.Map(location=center, zoom_start=zoom, tiles="OpenStreetMap",
                   control_scale=True)
    folium.Marker(GARAGE_KORI, tooltip="Garage KORI — Abidjan",
                  icon=folium.Icon(color="red", icon="home", prefix="fa")).add_to(m)
    if lat is not None and lon is not None:
        folium.Marker((lat, lon), tooltip=marker_label or "Destination",
                      icon=folium.Icon(color="blue", icon="flag", prefix="fa")).add_to(m)
        # Afficher les marqueurs des points de passage
        if waypoints:
            for i, (wlat, wlon) in enumerate(waypoints, 1):
                folium.Marker(
                    (wlat, wlon),
                    tooltip=f"Point de passage {i}",
                    icon=folium.Icon(color="green", icon="arrow-right", prefix="fa"),
                ).add_to(m)
        if route_depuis_garage:
            trajet = trajet_depuis_garage(lat, lon, waypoints=waypoints) if vrai_itineraire else None
            if trajet and trajet.get("geometry"):
                folium.PolyLine(trajet["geometry"],
                                color="#E30613", weight=4, opacity=0.85,
                                tooltip=(f"Route : {trajet['distance_km']:.1f} km • "
                                         f"≈ {trajet['duration_min']:.0f} min")
                                ).add_to(m)
                # Bounds incluant les waypoints
                all_lats = [GARAGE_KORI[0], lat]
                all_lons = [GARAGE_KORI[1], lon]
                if waypoints:
                    for wlat, wlon in waypoints:
                        all_lats.append(wlat)
                        all_lons.append(wlon)
                m.fit_bounds([[min(all_lats), min(all_lons)],
                              [max(all_lats), max(all_lons)]],
                             padding=(30, 30))
            else:
                folium.PolyLine([GARAGE_KORI, (lat, lon)],
                                color="#888", weight=2, opacity=0.6, dash_array="5,5",
                                tooltip="Trajet indicatif (vol d'oiseau)").add_to(m)
                m.fit_bounds([GARAGE_KORI, (lat, lon)], padding=(30, 30))
    return m
