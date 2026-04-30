"""Table des destinations — édition réservée Admin, avec vérification GPS et carte."""
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
st.caption("Localités de référence — distances et péages depuis le garage KORI (Ancienne voie de Bassam)")

rows = sb().table("destinations").select("*").order("localite").execute().data or []
df = pd.DataFrame(rows)

# ---------- Vue carte de toutes les destinations ----------
with st.expander("🗺️ Vue cartographique de toutes les destinations", expanded=False):
    m = folium.Map(location=[7.5, -5.5], zoom_start=6, tiles="OpenStreetMap", control_scale=True)
    folium.Marker(geo.GARAGE_KORI, tooltip="Garage KORI — Abidjan",
                  icon=folium.Icon(color="red", icon="home", prefix="fa")).add_to(m)
    n_ok, n_missing = 0, 0
    for _, r in df.iterrows():
        if pd.notna(r.get("latitude")) and pd.notna(r.get("longitude")):
            folium.CircleMarker(
                location=[r["latitude"], r["longitude"]],
                radius=5, color="#1f77b4", fill=True, fill_opacity=0.7,
                tooltip=f"{r['localite']} — {r.get('distance_ar_km', 0):.0f} km A/R",
            ).add_to(m)
            n_ok += 1
        else:
            n_missing += 1
    st_folium(m, width=None, height=500, returned_objects=[], key="map_all_dests")
    st.caption(f"{n_ok} destinations avec GPS — {n_missing} sans coordonnées")

# ========== OUTIL DE VÉRIFICATION GPS (Admin) ==========
if is_admin:
    st.divider()
    st.subheader("🔍 Vérification des coordonnées GPS")
    st.caption("Parcourez chaque destination pour vérifier que le point GPS correspond bien "
               "à la localité. Corrigez directement celles qui sont mal positionnées.")

    # Sélection de la destination à vérifier
    localites = df["localite"].tolist()
    # Index de navigation
    if "verif_idx" not in st.session_state:
        st.session_state["verif_idx"] = 0

    col_prev, col_select, col_next, col_count = st.columns([1, 4, 1, 2])
    if col_prev.button("⬅️ Préc.", use_container_width=True, key="prev"):
        st.session_state["verif_idx"] = max(0, st.session_state["verif_idx"] - 1)
        st.session_state.pop("verif_search_results", None)
        st.rerun()
    selected = col_select.selectbox(
        "Destination à vérifier",
        localites,
        index=st.session_state["verif_idx"],
        label_visibility="collapsed",
        key="verif_select",
    )
    # Mettre à jour l'index si l'utilisateur change le selectbox
    if selected != localites[st.session_state["verif_idx"]]:
        st.session_state["verif_idx"] = localites.index(selected)
        st.session_state.pop("verif_search_results", None)
    if col_next.button("Suiv. ➡️", use_container_width=True, key="next"):
        st.session_state["verif_idx"] = min(len(localites) - 1, st.session_state["verif_idx"] + 1)
        st.session_state.pop("verif_search_results", None)
        st.rerun()
    col_count.markdown(f"**{st.session_state['verif_idx'] + 1} / {len(localites)}**")

    # Données de la destination sélectionnée
    dest_row = df[df["localite"] == selected].iloc[0] if not df[df["localite"] == selected].empty else None
    if dest_row is not None:
        cur_lat = dest_row.get("latitude")
        cur_lon = dest_row.get("longitude")
        cur_dist = dest_row.get("distance_ar_km", 0)
        dest_id = int(dest_row.get("id"))

        has_gps = pd.notna(cur_lat) and pd.notna(cur_lon)

        # Affichage : carte avec le point actuel
        col_map, col_info = st.columns([3, 2])

        with col_map:
            if has_gps:
                vm = folium.Map(location=[float(cur_lat), float(cur_lon)], zoom_start=10,
                                tiles="OpenStreetMap", control_scale=True)
                folium.Marker(geo.GARAGE_KORI, tooltip="Garage KORI",
                              icon=folium.Icon(color="red", icon="home", prefix="fa")).add_to(vm)
                folium.Marker([float(cur_lat), float(cur_lon)],
                              tooltip=f"{selected} (actuel)",
                              icon=folium.Icon(color="blue", icon="flag", prefix="fa")).add_to(vm)
                # Tracer la route
                trajet = None
                try:
                    trajet = geo.trajet_depuis_garage(float(cur_lat), float(cur_lon))
                except Exception:
                    pass
                if trajet and trajet.get("geometry"):
                    folium.PolyLine(trajet["geometry"], color="#E30613", weight=3, opacity=0.7).add_to(vm)
                st_folium(vm, width=None, height=400, returned_objects=[], key="map_verif")
            else:
                st.warning(f"⚠️ **{selected}** n'a pas de coordonnées GPS.")
                vm = folium.Map(location=[7.5, -5.5], zoom_start=6, tiles="OpenStreetMap")
                folium.Marker(geo.GARAGE_KORI, tooltip="Garage KORI",
                              icon=folium.Icon(color="red", icon="home", prefix="fa")).add_to(vm)
                st_folium(vm, width=None, height=400, returned_objects=[], key="map_verif")

        with col_info:
            st.markdown(f"### {selected}")
            if has_gps:
                st.write(f"📍 Latitude : **{float(cur_lat):.6f}**")
                st.write(f"📍 Longitude : **{float(cur_lon):.6f}**")
            else:
                st.write("📍 Latitude : **—**")
                st.write("📍 Longitude : **—**")
            st.write(f"🛣️ Distance A/R : **{cur_dist} km**")

            # --- Rechercher les bonnes coordonnées ---
            st.markdown("---")
            st.markdown("**🔎 Corriger les coordonnées**")
            corr_mode = st.radio("Méthode :", ["Recherche", "Saisie GPS"],
                                  horizontal=True, key="corr_mode")

            if corr_mode == "Recherche":
                col_sq, col_sb = st.columns([4, 1])
                search_q = col_sq.text_input("Rechercher le lieu",
                                              value=selected,
                                              key="verif_search_q",
                                              label_visibility="collapsed")
                if col_sb.button("🔎", key="verif_search_btn", use_container_width=True):
                    with st.spinner("Recherche…"):
                        st.session_state["verif_search_results"] = geo.chercher_lieu(search_q, limit=6)

                results = st.session_state.get("verif_search_results", [])
                if results:
                    for i, r in enumerate(results):
                        short_name = r["display_name"][:60]
                        if st.button(f"📌 {short_name} ({r['lat']:.4f}, {r['lon']:.4f})",
                                     key=f"verif_pick_{i}", use_container_width=True):
                            sb().table("destinations").update({
                                "latitude": r["lat"],
                                "longitude": r["lon"],
                            }).eq("id", dest_id).execute()
                            st.success(f"✅ Coordonnées de **{selected}** mises à jour !")
                            st.session_state.pop("verif_search_results", None)
                            st.rerun()
                elif "verif_search_results" in st.session_state:
                    st.warning("Aucun résultat trouvé.")

            elif corr_mode == "Saisie GPS":
                new_lat = st.number_input("Nouvelle latitude", value=float(cur_lat) if has_gps else None,
                                           min_value=4.0, max_value=11.0, format="%.6f",
                                           step=0.001, key="verif_new_lat")
                new_lon = st.number_input("Nouvelle longitude", value=float(cur_lon) if has_gps else None,
                                           min_value=-9.0, max_value=-2.0, format="%.6f",
                                           step=0.001, key="verif_new_lon")
                if new_lat is not None and new_lon is not None:
                    if st.button("✅ Enregistrer ces coordonnées", type="primary",
                                 key="verif_save_gps", use_container_width=True):
                        sb().table("destinations").update({
                            "latitude": new_lat,
                            "longitude": new_lon,
                        }).eq("id", dest_id).execute()
                        st.success(f"✅ Coordonnées de **{selected}** mises à jour !")
                        st.rerun()

    st.divider()

    # ---------- Ajouter une destination ----------
    st.subheader("➕ Ajouter une destination")
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

    # ---------- Édition directe du tableau ----------
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
