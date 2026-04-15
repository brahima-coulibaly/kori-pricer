"""Table des destinations — édition réservée Admin, avec recherche géographique et carte."""
import streamlit as st
import pandas as pd
from lib import auth, geo
from lib.db import sb
from streamlit_folium import st_folium
import folium

st.set_page_config(page_title="Destinations — KORI", page_icon="🗺️", layout="wide")
auth.require_auth()
is_admin = auth.current_role() == "admin"

st.title("🗺️ Destinations")
st.caption("74 localités de référence — distances et péages depuis le garage KORI (Ancienne voie de Bassam)")

rows = sb().table("destinations").select("*").order("localite").execute().data or []
df = pd.DataFrame(rows)

# ---------- Vue carte de toutes les destinations ----------
with st.expander("🗺️ Vue cartographique de toutes les destinations", expanded=False):
    m = folium.Map(location=[7.5, -5.5], zoom_start=6, tiles="OpenStreetMap", control_scale=True)
    folium.Marker(geo.GARAGE_KORI, tooltip="Garage KORI — Abidjan",
                  icon=folium.Icon(color="red", icon="home", prefix="fa")).add_to(m)
    for _, r in df.iterrows():
        if pd.notna(r.get("latitude")) and pd.notna(r.get("longitude")):
            folium.CircleMarker(
                location=[r["latitude"], r["longitude"]],
                radius=5, color="#1f77b4", fill=True, fill_opacity=0.7,
                tooltip=f"{r['localite']} — {r.get('distance_ar_km', 0):.0f} km A/R",
            ).add_to(m)
    st_folium(m, width=None, height=500, returned_objects=[], key="map_all_dests")

# ---------- Mode admin : recherche + édition ----------
if is_admin:
    st.divider()
    st.subheader("➕ Ajouter une destination via recherche géographique")
    st.caption("Tapez le nom d'une ville pour récupérer automatiquement ses coordonnées GPS.")
    col_q, col_btn = st.columns([5, 1])
    query = col_q.text_input("Nom de la ville à ajouter", placeholder="Ex : Odiénné, Duékoué…",
                              label_visibility="collapsed", key="admin_geo_q")
    if col_btn.button("Rechercher", use_container_width=True, key="admin_geo_btn"):
        with st.spinner("Recherche en cours…"):
            st.session_state["admin_geo_results"] = geo.chercher_lieu(query, limit=5)
    results = st.session_state.get("admin_geo_results", [])
    if results:
        opts = [f"{r['display_name']}  —  ({r['lat']:.4f}, {r['lon']:.4f})" for r in results]
        choix = st.radio("Résultat :", opts, key="admin_geo_choice")
        r = results[opts.index(choix)]
        colf1, colf2, colf3 = st.columns(3)
        new_loc = colf1.text_input("Localité (nom à utiliser)",
                                    value=query.strip().upper() if query else "")
        new_dist = colf2.number_input("Distance A/R (km)", min_value=0, step=10,
                                       help="Distance aller-retour estimée. Peut être ajustée ensuite.")
        new_mission = colf3.number_input("Frais mission unitaire (F CFA)", min_value=0, step=1000,
                                          value=5000)
        if st.button("✅ Créer cette destination", type="primary"):
            payload = {
                "localite": new_loc,
                "latitude": r["lat"],
                "longitude": r["lon"],
                "distance_ar_km": new_dist,
                "frais_mission_unitaire": new_mission,
                "source": "Nominatim / OSM",
            }
            try:
                sb().table("destinations").insert(payload).execute()
                st.success(f"Destination **{new_loc}** créée.")
                st.session_state.pop("admin_geo_results", None)
                st.rerun()
            except Exception as e:
                st.error(f"Erreur lors de la création : {e}")

    st.divider()
    st.subheader("📋 Éditer les destinations existantes")
    st.info("Mode administrateur : modifiez les lignes ci-dessous puis sauvegardez.")
    edited = st.data_editor(df, use_container_width=True, num_rows="dynamic", hide_index=True,
                            disabled=["id", "maj_le"])
    if st.button("💾 Sauvegarder les modifications", type="primary"):
        for _, row in edited.iterrows():
            payload = row.dropna().to_dict()
            payload.pop("maj_le", None)
            rid = payload.pop("id", None)
            if rid:
                sb().table("destinations").update(payload).eq("id", int(rid)).execute()
            else:
                sb().table("destinations").insert(payload).execute()
        st.success("Destinations mises à jour.")
        st.rerun()
else:
    st.divider()
    st.dataframe(df, use_container_width=True, hide_index=True)
