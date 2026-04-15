"""Géocodage (Nominatim/OpenStreetMap) + helpers cartographiques."""
from __future__ import annotations
import time
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


@st.cache_resource
def _geocoder():
    return Nominatim(user_agent="kori-pricer-ci/1.0 (contact: kori-transport)", timeout=10)


def _search_raw(query: str, limit: int = 5):
    """Appel brut Nominatim avec limitation de débit (1 req/s)."""
    geolocator = _geocoder()
    search = RateLimiter(geolocator.geocode, min_delay_seconds=1, max_retries=2)
    # Priorité à la Côte d'Ivoire, mais pas de restriction stricte (pays voisins possibles)
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
    except Exception as e:
        return []
    if not results:
        # Fallback sans restriction de pays (utile pour les villes frontalières)
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
    """À partir de coordonnées, renvoie une adresse lisible."""
    try:
        geolocator = _geocoder()
        rev = RateLimiter(geolocator.reverse, min_delay_seconds=1)
        r = rev((lat, lon), language="fr")
        return r.address if r else None
    except Exception:
        return None


def carte_folium(lat: float | None = None, lon: float | None = None,
                 zoom: int = 7, route_depuis_garage: bool = False,
                 marker_label: str | None = None):
    """Crée une carte Folium centrée sur la Côte d'Ivoire (ou sur le point donné)."""
    import folium
    center = (lat, lon) if (lat is not None and lon is not None) else (7.5, -5.5)
    m = folium.Map(location=center, zoom_start=zoom, tiles="OpenStreetMap",
                   control_scale=True)
    # Marqueur du garage KORI (toujours affiché)
    folium.Marker(GARAGE_KORI, tooltip="Garage KORI — Abidjan",
                  icon=folium.Icon(color="red", icon="home", prefix="fa")).add_to(m)
    # Marqueur de destination
    if lat is not None and lon is not None:
        folium.Marker((lat, lon), tooltip=marker_label or "Destination",
                      icon=folium.Icon(color="blue", icon="flag", prefix="fa")).add_to(m)
        if route_depuis_garage:
            folium.PolyLine([GARAGE_KORI, (lat, lon)],
                            color="#E30613", weight=3, opacity=0.8,
                            tooltip="Trajet (vol d'oiseau)").add_to(m)
            # Ajuster le zoom pour voir les 2 points
            m.fit_bounds([GARAGE_KORI, (lat, lon)], padding=(30, 30))
    return m
