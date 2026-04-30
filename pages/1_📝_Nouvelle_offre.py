"""Création d'une nouvelle offre commerciale — avec carte, GPS et champs éditables."""
import streamlit as st
from lib import auth, pricer, geo
from lib.db import sb
from lib.pdf import pdf_offre
from streamlit_folium import st_folium

st.set_page_config(page_title="Nouvelle offre — KORI", page_icon="📝", layout="wide")
auth.require_role("commercial", "manager", "admin")

st.title("📝 Nouvelle offre commerciale")

# Chargement des listes
dests = sb().table("destinations").select("localite,distance_ar_km,peages_ar,frais_mission_unitaire,latitude,longitude").order("localite").execute().data or []
vehs = sb().table("vehicules").select("attelage").eq("actif", True).order("attelage").execute().data or []

mode = st.radio(
    "Mode de saisie",
    ["Choisir dans la liste", "Rechercher un lieu", "Coordonnées GPS", "Carte interactive"],
    horizontal=True,
    help=("Liste : vos destinations habituelles. "
          "Recherche : toute localité de Côte d'Ivoire. "
          "GPS : entrez directement les coordonnées du point de livraison. "
          "Carte : cliquez sur la carte pour positionner le point."),
)

destination = None
gps_lat, gps_lon = None, None
dest_data = None

# ------- MODE 1 : choisir dans la liste -------
if mode == "Choisir dans la liste":
    destination = st.selectbox("Destination", [d["localite"] for d in dests])
    dest_data = next((d for d in dests if d["localite"] == destination), None)
    if dest_data:
        gps_lat, gps_lon = dest_data.get("latitude"), dest_data.get("longitude")

# ------- MODE 2 : recherche par nom (Nominatim / OpenStreetMap) -------
elif mode == "Rechercher un lieu":
    st.caption("🔎 Tapez le nom d'un lieu (ville, village, quartier, site industriel…)")
    col_q, col_btn = st.columns([5, 1])
    query = col_q.text_input(
        "Nom du lieu",
        placeholder="Ex : Adzopé, Abobo, Zone industrielle Yopougon…",
        label_visibility="collapsed",
    )
    go = col_btn.button("Rechercher", use_container_width=True)
    if go and query:
        with st.spinner("Recherche en cours…"):
            st.session_state["geo_results"] = geo.chercher_lieu(query, limit=8)
    results = st.session_state.get("geo_results", [])
    if results:
        options = [f"{r['display_name']}  —  ({r['lat']:.4f}, {r['lon']:.4f})" for r in results]
        choix = st.radio("Choisissez le résultat correspondant :", options, index=0)
        idx = options.index(choix)
        r = results[idx]
        gps_lat, gps_lon = r["lat"], r["lon"]
        best, ecart = pricer.ville_la_plus_proche(gps_lat, gps_lon)
        if best:
            if ecart < 15:
                st.success(f"✅ Rattaché à **{best['localite']}** (écart : {ecart:.1f} km)")
            elif ecart < 50:
                st.info(f"📍 Ville de référence la plus proche : **{best['localite']}** (écart : {ecart:.1f} km)")
            else:
                st.warning(f"⚠️ Ville de référence la plus proche : **{best['localite']}** mais à {ecart:.1f} km — prévoyez des frais supplémentaires.")
            destination = best["localite"]
            dest_data = next((d for d in dests if d["localite"] == destination), None)
    elif go:
        st.warning("Aucun résultat. Essayez une autre orthographe ou un lieu plus proche.")

# ------- MODE 3 : Coordonnées GPS directes -------
elif mode == "Coordonnées GPS":
    st.caption("📍 Entrez les coordonnées GPS exactes du point de livraison.")
    st.info("💡 Astuce : vous pouvez trouver les coordonnées sur Google Maps (clic droit → coordonnées).")
    col_lat, col_lon = st.columns(2)
    input_lat = col_lat.number_input("Latitude", value=None, min_value=4.0, max_value=11.0,
                                      format="%.6f", step=0.001,
                                      placeholder="Ex : 6.8276",
                                      help="Latitude en degrés décimaux (entre 4.0 et 11.0 pour la Côte d'Ivoire)")
    input_lon = col_lon.number_input("Longitude", value=None, min_value=-9.0, max_value=-2.0,
                                      format="%.6f", step=0.001,
                                      placeholder="Ex : -5.2893",
                                      help="Longitude en degrés décimaux (entre -9.0 et -2.0 pour la Côte d'Ivoire)")
    if input_lat is not None and input_lon is not None:
        gps_lat, gps_lon = input_lat, input_lon
        # Géocodage inverse pour afficher le nom du lieu
        with st.spinner("Identification du lieu…"):
            adresse = geo.reverse_geocode(gps_lat, gps_lon)
        if adresse:
            st.success(f"📍 Lieu identifié : **{adresse}**")
        else:
            st.info(f"📍 Point GPS : **{gps_lat:.6f}, {gps_lon:.6f}**")
        # Rattachement à la ville de référence la plus proche
        best, ecart = pricer.ville_la_plus_proche(gps_lat, gps_lon)
        if best:
            if ecart < 15:
                st.success(f"✅ Rattaché à **{best['localite']}** (écart : {ecart:.1f} km)")
            elif ecart < 50:
                st.info(f"📍 Ville de référence : **{best['localite']}** (écart : {ecart:.1f} km)")
            else:
                st.warning(f"⚠️ Ville la plus proche : **{best['localite']}** à {ecart:.1f} km.")
            destination = best["localite"]
            dest_data = next((d for d in dests if d["localite"] == destination), None)
    else:
        st.warning("Veuillez renseigner la latitude et la longitude.")

# ------- MODE 4 : carte cliquable -------
elif mode == "Carte interactive":
    st.caption("🗺️ Cliquez sur la carte pour positionner le point de livraison.")
    last = st.session_state.get("map_click")
    has_point = last is not None
    m = geo.carte_folium(
        lat=last["lat"] if has_point else None,
        lon=last["lng"] if has_point else None,
        zoom=9 if has_point else 6,
        route_depuis_garage=has_point,
        marker_label="Point sélectionné",
    )
    out = st_folium(m, width=None, height=500, returned_objects=["last_clicked"])
    if out and out.get("last_clicked"):
        new_click = out["last_clicked"]
        if last is None or new_click != last:
            st.session_state["map_click"] = new_click
            st.rerun()
    if last:
        gps_lat, gps_lon = last["lat"], last["lng"]
        st.info(f"📍 Point sélectionné : **{gps_lat:.4f}, {gps_lon:.4f}**")
        best, ecart = pricer.ville_la_plus_proche(gps_lat, gps_lon)
        if best:
            destination = best["localite"]
            dest_data = next((d for d in dests if d["localite"] == destination), None)
            if ecart < 15:
                st.success(f"✅ Rattaché à **{destination}** (écart : {ecart:.1f} km)")
            elif ecart < 50:
                st.info(f"📍 Ville de référence : **{destination}** (écart : {ecart:.1f} km)")
            else:
                st.warning(f"⚠️ Ville la plus proche : **{destination}** à {ecart:.1f} km.")
        if st.button("🔄 Réinitialiser le point"):
            st.session_state.pop("map_click", None)
            st.rerun()

# ------- Suite du formulaire -------
st.divider()
_attelages = [v["attelage"] for v in vehs]
_default_idx = _attelages.index("739LS01-739LS01") if "739LS01-739LS01" in _attelages else 0
attelage = st.selectbox("Attelage", _attelages, index=_default_idx)
c1, c2 = st.columns(2)
quantite = c1.number_input("Quantité (kg)", value=28000, min_value=1, step=1000)
autres = c2.number_input("Autres dépenses (F CFA)", value=0, min_value=0, step=1000)

if destination and attelage:
    # ---- Points de passage (waypoints) pour corriger l'itinéraire ----
    route_lat = gps_lat if gps_lat is not None else (dest_data.get("latitude") if dest_data else None)
    route_lon = gps_lon if gps_lon is not None else (dest_data.get("longitude") if dest_data else None)

    with st.expander("🛤️ Points de passage (optionnel — pour corriger l'itinéraire)", expanded=False):
        st.caption("Ajoutez des points intermédiaires pour forcer l'itinéraire à passer par "
                   "les bonnes routes. Ex : passer par **Bonoua** au lieu d'Alepe.")

        # Initialiser la liste des waypoints en session
        if "waypoints" not in st.session_state:
            st.session_state["waypoints"] = []

        # Interface d'ajout d'un nouveau waypoint
        wp_mode = st.radio("Ajouter un point via :", ["Ville connue", "Recherche", "Coordonnées GPS"],
                           horizontal=True, key="wp_mode")

        if wp_mode == "Ville connue":
            wp_ville = st.selectbox("Ville de passage", [d["localite"] for d in dests], key="wp_ville")
            wp_data = next((d for d in dests if d["localite"] == wp_ville), None)
            if wp_data and wp_data.get("latitude") and wp_data.get("longitude"):
                if st.button(f"➕ Ajouter **{wp_ville}** comme point de passage", key="wp_add_ville"):
                    st.session_state["waypoints"].append({
                        "label": wp_ville,
                        "lat": float(wp_data["latitude"]),
                        "lon": float(wp_data["longitude"]),
                    })
                    st.rerun()
            elif wp_data:
                st.warning(f"{wp_ville} n'a pas de coordonnées GPS en base.")

        elif wp_mode == "Recherche":
            col_wq, col_wb = st.columns([5, 1])
            wp_query = col_wq.text_input("Nom du lieu de passage", placeholder="Ex : Bonoua",
                                          key="wp_query")
            if col_wb.button("Chercher", key="wp_search", use_container_width=True) and wp_query:
                with st.spinner("Recherche…"):
                    st.session_state["wp_results"] = geo.chercher_lieu(wp_query, limit=5)
            wp_results = st.session_state.get("wp_results", [])
            if wp_results:
                wp_opts = [f"{r['display_name']} — ({r['lat']:.4f}, {r['lon']:.4f})" for r in wp_results]
                wp_choix = st.radio("Résultat :", wp_opts, key="wp_choix")
                wp_r = wp_results[wp_opts.index(wp_choix)]
                if st.button(f"➕ Ajouter comme point de passage", key="wp_add_search"):
                    label = wp_r["display_name"].split(",")[0]
                    st.session_state["waypoints"].append({
                        "label": label,
                        "lat": wp_r["lat"],
                        "lon": wp_r["lon"],
                    })
                    st.session_state.pop("wp_results", None)
                    st.rerun()

        elif wp_mode == "Coordonnées GPS":
            col_wlat, col_wlon = st.columns(2)
            wp_lat = col_wlat.number_input("Latitude", value=None, min_value=4.0, max_value=11.0,
                                            format="%.6f", step=0.001, key="wp_lat")
            wp_lon = col_wlon.number_input("Longitude", value=None, min_value=-9.0, max_value=-2.0,
                                            format="%.6f", step=0.001, key="wp_lon")
            if wp_lat is not None and wp_lon is not None:
                if st.button(f"➕ Ajouter ({wp_lat:.4f}, {wp_lon:.4f}) comme point de passage",
                             key="wp_add_gps"):
                    st.session_state["waypoints"].append({
                        "label": f"GPS ({wp_lat:.4f}, {wp_lon:.4f})",
                        "lat": wp_lat,
                        "lon": wp_lon,
                    })
                    st.rerun()

        # Afficher les waypoints actuels
        wps = st.session_state.get("waypoints", [])
        if wps:
            st.markdown("**Points de passage actuels :**")
            for i, wp in enumerate(wps):
                col_wp, col_del = st.columns([5, 1])
                col_wp.write(f"{i+1}. **{wp['label']}** ({wp['lat']:.4f}, {wp['lon']:.4f})")
                if col_del.button("❌", key=f"wp_del_{i}"):
                    st.session_state["waypoints"].pop(i)
                    st.rerun()
            if st.button("🗑️ Supprimer tous les points de passage", key="wp_clear"):
                st.session_state["waypoints"] = []
                st.rerun()

    # Convertir en tuple pour le cache OSRM
    waypoints_tuple = tuple((wp["lat"], wp["lon"]) for wp in st.session_state.get("waypoints", []))
    if not waypoints_tuple:
        waypoints_tuple = None

    # ---- Calcul de la distance routière via OSRM (indicatif) ----
    trajet_info = None
    distance_osrm_ar = None
    if route_lat is not None and route_lon is not None:
        try:
            _rlat, _rlon = float(route_lat), float(route_lon)
            with st.spinner("Calcul de l'itinéraire routier (indicatif)…"):
                trajet_info = geo.trajet_depuis_garage(_rlat, _rlon, waypoints=waypoints_tuple)
            if trajet_info:
                distance_osrm_ar = trajet_info["distance_km"] * 2
        except (TypeError, ValueError):
            trajet_info = None

    # ---- Affichage distance OSRM (indicatif) ----
    if trajet_info:
        from lib.pricer import load_params
        all_params = load_params()
        vitesse_pl = all_params.get("vitesse_moyenne_pl_kmh", 50)
        duree_max = all_params.get("duree_max_conduite_jour_h", 9)
        marge_temps = all_params.get("marge_securite_temps_pct", 15)

        duree_aller_pratique_min = geo.duree_pratique_pl(
            trajet_info["distance_km"], vitesse_pl, marge_temps)
        jours_mission = geo.nombre_jours_mission(duree_aller_pratique_min, duree_max)

        st.caption("🗺️ **Estimation OSRM** (itinéraire indicatif — peut différer de la route réelle)")
        col_r1, col_r2, col_r3 = st.columns(3)
        col_r1.metric("🛣️ Distance OSRM A/R",
                      f"{distance_osrm_ar:,.1f} km".replace(",", " "))
        col_r2.metric(f"⏱️ Durée aller camion ({vitesse_pl:.0f} km/h)",
                      f"{duree_aller_pratique_min:.0f} min "
                      f"({duree_aller_pratique_min/60:.1f} h)")
        col_r3.metric("📅 Jours de mission estimés",
                      f"{jours_mission} jour{'s' if jours_mission > 1 else ''}")

    # ---- Champs éditables : distance, péages, frais de mission ----
    st.divider()
    st.subheader("📐 Paramètres de la livraison")
    st.caption("⚡ Valeurs pré-remplies depuis la base de données. **Modifiez-les si nécessaire** "
               "pour refléter le trajet réel (itinéraire, péages, hébergement…).")

    # Valeurs par défaut depuis la base
    db_distance = float(dest_data.get("distance_ar_km") or 0) if dest_data else 0
    db_peages = float(dest_data.get("peages_ar") or 0) if dest_data else 0
    db_frais = float(dest_data.get("frais_mission_unitaire") or 0) if dest_data else 0

    # Si hors liste et qu'on a une distance OSRM, la proposer comme défaut
    default_distance = db_distance
    if mode in ("Rechercher un lieu", "Coordonnées GPS", "Carte interactive") and distance_osrm_ar:
        default_distance = round(distance_osrm_ar, 1)

    col_d1, col_d2, col_d3 = st.columns(3)
    input_distance = col_d1.number_input(
        "Distance A/R (km)",
        value=default_distance,
        min_value=0.0, step=10.0, format="%.1f",
        help=f"Base de données : {db_distance:.0f} km" +
             (f" — OSRM : {distance_osrm_ar:.1f} km" if distance_osrm_ar else ""))
    input_peages = col_d2.number_input(
        "Péages A/R (F CFA)",
        value=int(db_peages),
        min_value=0, step=500,
        help=f"Valeur de référence en base : {db_peages:,.0f} F".replace(",", " "))
    input_frais = col_d3.number_input(
        "Frais de mission (F CFA)",
        value=int(db_frais),
        min_value=0, step=1000,
        help=f"Valeur de référence en base : {db_frais:,.0f} F".replace(",", " "))

    # Déterminer les overrides (None = utiliser la valeur DB par défaut)
    dist_override = input_distance if input_distance != db_distance else None
    peages_override = float(input_peages) if input_peages != db_peages else None
    frais_override = float(input_frais) if input_frais != db_frais else None

    # Toujours overrider la distance si hors mode liste
    if mode != "Choisir dans la liste":
        dist_override = input_distance

    # ---- Carte du trajet (indicative) ----
    if route_lat is not None and route_lon is not None:
        with st.expander("🗺️ Visualiser l'itinéraire (indicatif — OpenStreetMap)",
                         expanded=(mode != "Carte interactive")):
            st.caption("⚠️ L'itinéraire affiché est généré automatiquement et peut "
                       "ne pas correspondre au trajet réellement emprunté par les camions. "
                       "Les distances et péages officiels sont ceux saisis ci-dessus.")
            if waypoints_tuple:
                st.caption(f"🛤️ Itinéraire passant par {len(waypoints_tuple)} point(s) de passage.")
            m_view = geo.carte_folium(
                lat=float(route_lat), lon=float(route_lon),
                route_depuis_garage=True,
                marker_label=destination,
                vrai_itineraire=True,
                waypoints=waypoints_tuple,
            )
            st_folium(m_view, width=None, height=400, returned_objects=[], key="map_view")

    # ---- Calcul de l'offre ----
    calc = pricer.calculer(
        destination, attelage, quantite, autres,
        distance_ar_override=dist_override,
        peages_ar_override=peages_override,
        frais_mission_override=frais_override,
    )

    st.subheader("📊 Détail des charges")
    d1, d2, d3 = st.columns(3)
    d1.metric("Distance A/R utilisée", f"{calc.distance_ar:,.0f} km".replace(",", " "))
    d2.metric("Péages A/R", f"{calc.peages_ar:,.0f} F".replace(",", " "))
    d3.metric("Frais mission", f"{calc.frais_mission:,.0f} F".replace(",", " "))

    charges = {
        "Carburant": calc.carburant,
        "Maintenance": calc.maintenance,
        "Péages A/R": calc.peages_ar,
        "Frais de mission": calc.frais_mission,
        "Prime voyage": calc.prime_voyage,
        "Lettre de voiture": calc.lettre_voiture,
        "Autres dépenses": calc.autres_depenses,
        "Charges fixes attelage": calc.charges_fixes_attelage,
        "VT/km × distance": calc.vt_km_distance,
    }
    import pandas as pd
    df = pd.DataFrame([{"Poste": k, "Montant (F CFA)": round(v)} for k, v in charges.items()])
    st.dataframe(df, use_container_width=True, hide_index=True)

    st.divider()
    st.subheader("💰 Prix & marge")
    prix_offert = st.number_input(
        "Prix offert client (F/kg) — laissez 0 pour utiliser le prix plancher",
        value=round(calc.prix_plancher_kg), min_value=0, step=1)
    calc = pricer.calculer(
        destination, attelage, quantite, autres,
        prix_offert_kg=prix_offert if prix_offert > 0 else None,
        distance_ar_override=dist_override,
        peages_ar_override=peages_override,
        frais_mission_override=frais_override,
    )

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Total charges", f"{calc.total_charges:,.0f} F".replace(",", " "))
    m2.metric("Prix plancher", f"{calc.prix_plancher_kg:,.0f} F/kg".replace(",", " "))
    m3.metric("CA total", f"{calc.ca_total:,.0f} F".replace(",", " "))
    m4.metric("Taux de marge", f"{calc.taux_marge*100:.1f} %")

    from lib.pricer import load_params
    params = load_params()
    cible = params.get("marge_cible", 0.75)
    seuil_bas = params.get("seuil_marge_basse", 0.60)
    seuil_crit = params.get("seuil_marge_critique", 0.375)
    if calc.taux_marge >= cible:
        st.success(f"✅ Marge supérieure ou égale à la cible ({cible*100:.0f} %)")
    elif calc.taux_marge >= seuil_bas:
        st.warning(f"⚠️ Marge faible — en dessous de la cible ({cible*100:.0f} %)")
    elif calc.taux_marge >= seuil_crit:
        st.error(f"🚨 Marge critique — seuil bas : {seuil_bas*100:.0f} %")
    else:
        st.error(f"🛑 Marge insuffisante — sous le seuil critique : {seuil_crit*100:.0f} %")

    st.divider()
    notes = st.text_area("Notes (optionnel)")
    statut = st.selectbox("Statut", ["brouillon", "valide", "envoye"])
    col_save, col_pdf = st.columns(2)

    if col_save.button("💾 Enregistrer l'offre", type="primary", use_container_width=True):
        user = auth.current_user()
        rec = pricer.enregistrer_offre(calc, user_id=user["id"], user_email=user["email"],
                                       statut=statut, notes=notes)
        st.success(f"Offre enregistrée : **{rec['numero']}**")
        st.session_state["last_offre"] = rec

    if "last_offre" in st.session_state:
        pdf_bytes = pdf_offre(st.session_state["last_offre"])
        col_pdf.download_button(
            "📄 Télécharger le PDF", data=pdf_bytes,
            file_name=f"{st.session_state['last_offre']['numero']}.pdf",
            mime="application/pdf", use_container_width=True)
