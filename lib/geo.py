"""Géocodage (Nominatim/OpenStreetMap) + routing (OSRM) + helpers cartographiques."""
from __future__ import annotations
import time
import urllib.request
import json
import streamlit as st
from geopy.geocoders import Nominatim
from geopy.extra.rate_limiter import RateLimiter

# Point de départ : garage KORI à Abidjan (Ancienne voie de Bassam)
GARAGE_KORI = (5.345, -4.024)

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
def calculer_trajet(lat1: float, lon1: float, lat2: float, lon2: float) -> dict | None:
    """Calcule le trajet routier réel entre deux points via OSRM.

    Retourne un dict {distance_km, duration_min, geometry} où geometry est une
    liste de [lat, lon] du tracé exact de la route, ou None en cas d'échec.
    """
    try:
        url = (f"{OSRM_BASE}/route/v1/driving/"
               f"{lon1},{lat1};{lon2},{lat2}"
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


def trajet_depuis_garage(lat: float, lon: float) -> dict | None:
    """Raccourci : trajet aller depuis le garage KORI vers un point."""
    return calculer_trajet(GARAGE_KORI[0], GARAGE_KORI[1], lat, lon)


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


# ---------- Cartes Folium ----------

def carte_folium(lat: float | None = None, lon: float | None = None,
                 zoom: int = 7, route_depuis_garage: bool = False,
                 marker_label: str | None = None,
                 vrai_itineraire: bool = True):
    """Crée une carte Folium.

    Si route_depuis_garage et vrai_itineraire sont True, on trace le vrai
    itinéraire routier OSRM. Sinon, on trace une simple ligne droite (vol d'oiseau).
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
        if route_depuis_garage:
            trajet = trajet_depuis_garage(lat, lon) if vrai_itineraire else None
            if trajet and trajet.get("geometry"):
                folium.PolyLine(trajet["geometry"],
                                color="#E30613", weight=4, opacity=0.85,
                                tooltip=(f"Route : {trajet['distance_km']:.1f} km • "
                                         f"≈ {trajet['duration_min']:.0f} min")
                                ).add_to(m)
                m.fit_bounds([[min(GARAGE_KORI[0], lat), min(GARAGE_KORI[1], lon)],
                              [max(GARAGE_KORI[0], lat), max(GARAGE_KORI[1], lon)]],
                             padding=(30, 30))
            else:
                # Fallback : ligne droite
                folium.PolyLine([GARAGE_KORI, (lat, lon)],
                                color="#888", weight=2, opacity=0.6, dash_array="5,5",
                                tooltip="Trajet indicatif (vol d'oiseau)").add_to(m)
                m.fit_bounds([GARAGE_KORI, (lat, lon)], padding=(30, 30))
    return m
