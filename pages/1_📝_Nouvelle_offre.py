"""Nouvelle offre commerciale — aligné TB Simulation livraison (refonte)."""
import streamlit as st
import pandas as pd
from lib import auth, pricer, geo
from lib.db import sb
from lib.pdf import pdf_offre
from lib.pricer import load_params
from streamlit_folium import st_folium

st.set_page_config(page_title="Nouvelle offre — KORI", page_icon="📝", layout="wide")
auth.require_role("commercial", "manager", "admin")

st.title("📝 Nouvelle offre commerciale")

# =====================================================================
# 1. SAISIE DE LA DESTINATION
# =====================================================================
dests = sb().table("destinations").select(
    "localite,distance_ar_km,peages_ar,frais_mission_unitaire,"
    "frais_voyage,frais_hebergement,latitude,longitude"
).order("localite").execute().data or []

mode = st.radio(
    "Mode de saisie",
    ["Rechercher un lieu", "Coordonnées GPS", "Carte interactive"],
    horizontal=True,
)

destination = None
gps_lat, gps_lon = None, None
dest_data = None
lieu_recherche = None  # Nom du lieu tel que recherché (ex: "Mine d'Ity")

if mode == "Rechercher un lieu":
    st.caption("🔎 Tapez le nom du lieu de livraison puis appuyez sur Entrée")
    query = st.text_input("Nom du lieu", placeholder="Ex : Adzopé, Mine YTI, Zone industrielle Yopougon…",
                           label_visibility="collapsed")
    if query:
        # Recherche déclenchée automatiquement à chaque saisie validée (Entrée)
        if st.session_state.get("_last_geo_query") != query:
            with st.spinner("Recherche en cours…"):
                st.session_state["geo_results"] = geo.chercher_lieu(query, limit=8)
                st.session_state["_last_geo_query"] = query
        results = st.session_state.get("geo_results", [])
        if results:
            options = [f"{r['display_name']}  —  ({r['lat']:.4f}, {r['lon']:.4f})" for r in results]
            choix = st.radio("Choisissez le résultat correspondant :", options, index=0)
            r = results[options.index(choix)]
            gps_lat, gps_lon = r["lat"], r["lon"]
            lieu_recherche = r["display_name"].split(",")[0].strip()
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
            st.warning("Aucun résultat trouvé.")

elif mode == "Coordonnées GPS":
    st.caption("📍 Entrez les coordonnées GPS exactes du point de livraison.")
    col_lat, col_lon = st.columns(2)
    input_lat = col_lat.number_input("Latitude", value=None, min_value=4.0, max_value=11.0,
                                      format="%.6f", step=0.001, placeholder="Ex : 6.8276")
    input_lon = col_lon.number_input("Longitude", value=None, min_value=-9.0, max_value=-2.0,
                                      format="%.6f", step=0.001, placeholder="Ex : -5.2893")
    if input_lat is not None and input_lon is not None:
        gps_lat, gps_lon = input_lat, input_lon
        with st.spinner("Identification du lieu…"):
            adresse = geo.reverse_geocode(gps_lat, gps_lon)
        if adresse:
            st.success(f"📍 Lieu identifié : **{adresse}**")
        best, ecart = pricer.ville_la_plus_proche(gps_lat, gps_lon)
        if best:
            if ecart < 15:
                st.success(f"✅ Rattaché à **{best['localite']}** ({ecart:.1f} km)")
            elif ecart < 50:
                st.info(f"📍 Ville de référence : **{best['localite']}** ({ecart:.1f} km)")
            else:
                st.warning(f"⚠️ Ville la plus proche : **{best['localite']}** à {ecart:.1f} km.")
            destination = best["localite"]
            dest_data = next((d for d in dests if d["localite"] == destination), None)
    else:
        st.warning("Veuillez renseigner la latitude et la longitude.")

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
                st.success(f"✅ Rattaché à **{destination}** ({ecart:.1f} km)")
            elif ecart < 50:
                st.info(f"📍 Ville de référence : **{destination}** ({ecart:.1f} km)")
            else:
                st.warning(f"⚠️ Ville la plus proche : **{destination}** à {ecart:.1f} km.")
        if st.button("🔄 Réinitialiser le point"):
            st.session_state.pop("map_click", None)
            st.rerun()

# =====================================================================
# 2. PARAMÈTRES DE L'OPÉRATION
# =====================================================================
st.divider()
attelage = "739LS01-739LS01"  # Attelage par défaut

c1, c2 = st.columns(2)
quantite = c1.number_input("Qté à livrer (kg)", value=28000, min_value=1, step=1000)
autres = c2.number_input("Autres dépenses (F CFA)", value=0, min_value=0, step=1000)

if destination and attelage:
    # ---- Waypoints ----
    route_lat = gps_lat if gps_lat is not None else (dest_data.get("latitude") if dest_data else None)
    route_lon = gps_lon if gps_lon is not None else (dest_data.get("longitude") if dest_data else None)

    with st.expander("🛤️ Points de passage (optionnel — corriger l'itinéraire)", expanded=False):
        st.caption("Ajoutez des points intermédiaires pour corriger le trajet.")
        if "waypoints" not in st.session_state:
            st.session_state["waypoints"] = []

        wp_mode = st.radio("Ajouter via :", ["Ville connue", "Recherche", "Coordonnées GPS"],
                           horizontal=True, key="wp_mode")
        if wp_mode == "Ville connue":
            wp_ville = st.selectbox("Ville de passage", [d["localite"] for d in dests], key="wp_ville")
            wp_data = next((d for d in dests if d["localite"] == wp_ville), None)
            if wp_data and wp_data.get("latitude") and wp_data.get("longitude"):
                if st.button(f"➕ Ajouter **{wp_ville}**", key="wp_add_ville"):
                    st.session_state["waypoints"].append({"label": wp_ville,
                        "lat": float(wp_data["latitude"]), "lon": float(wp_data["longitude"])})
                    st.rerun()
        elif wp_mode == "Recherche":
            col_wq, col_wb = st.columns([5, 1])
            wp_query = col_wq.text_input("Lieu de passage", placeholder="Ex : Bonoua", key="wp_query")
            if col_wb.button("Chercher", key="wp_search", use_container_width=True) and wp_query:
                with st.spinner("Recherche…"):
                    st.session_state["wp_results"] = geo.chercher_lieu(wp_query, limit=5)
            wp_results = st.session_state.get("wp_results", [])
            if wp_results:
                wp_opts = [f"{r['display_name']} — ({r['lat']:.4f}, {r['lon']:.4f})" for r in wp_results]
                wp_choix = st.radio("Résultat :", wp_opts, key="wp_choix")
                wp_r = wp_results[wp_opts.index(wp_choix)]
                if st.button("➕ Ajouter", key="wp_add_search"):
                    st.session_state["waypoints"].append({"label": wp_r["display_name"].split(",")[0],
                        "lat": wp_r["lat"], "lon": wp_r["lon"]})
                    st.session_state.pop("wp_results", None)
                    st.rerun()
        elif wp_mode == "Coordonnées GPS":
            col_wlat, col_wlon = st.columns(2)
            wp_lat = col_wlat.number_input("Latitude", value=None, min_value=4.0, max_value=11.0,
                                            format="%.6f", step=0.001, key="wp_lat")
            wp_lon = col_wlon.number_input("Longitude", value=None, min_value=-9.0, max_value=-2.0,
                                            format="%.6f", step=0.001, key="wp_lon")
            if wp_lat is not None and wp_lon is not None:
                if st.button(f"➕ Ajouter ({wp_lat:.4f}, {wp_lon:.4f})", key="wp_add_gps"):
                    st.session_state["waypoints"].append({"label": f"GPS ({wp_lat:.4f}, {wp_lon:.4f})",
                        "lat": wp_lat, "lon": wp_lon})
                    st.rerun()

        wps = st.session_state.get("waypoints", [])
        if wps:
            st.markdown("**Points de passage :**")
            for i, wp in enumerate(wps):
                col_wp, col_del = st.columns([5, 1])
                col_wp.write(f"{i+1}. **{wp['label']}** ({wp['lat']:.4f}, {wp['lon']:.4f})")
                if col_del.button("❌", key=f"wp_del_{i}"):
                    st.session_state["waypoints"].pop(i)
                    st.rerun()
            if st.button("🗑️ Tout supprimer", key="wp_clear"):
                st.session_state["waypoints"] = []
                st.rerun()

    waypoints_tuple = tuple((wp["lat"], wp["lon"]) for wp in st.session_state.get("waypoints", []))
    if not waypoints_tuple:
        waypoints_tuple = None

    # ---- Distance OSRM (indicatif) ----
    trajet_info = None
    distance_osrm_ar = None
    if route_lat is not None and route_lon is not None:
        try:
            _rlat, _rlon = float(route_lat), float(route_lon)
            with st.spinner("Calcul de l'itinéraire…"):
                trajet_info = geo.trajet_depuis_garage(_rlat, _rlon, waypoints=waypoints_tuple)
            if trajet_info:
                distance_osrm_ar = trajet_info["distance_km"] * 2
        except (TypeError, ValueError):
            trajet_info = None

    if trajet_info:
        params = load_params()
        vitesse_pl = params.get("vitesse_moyenne_pl_kmh", 50)
        duree_max = params.get("duree_max_conduite_jour_h", 9)
        marge_temps = params.get("marge_securite_temps_pct", 15)
        duree_aller_min = geo.duree_pratique_pl(trajet_info["distance_km"], vitesse_pl, marge_temps)
        jours_mission = geo.nombre_jours_mission(duree_aller_min, duree_max)
        st.caption("🗺️ **Estimation OSRM** (indicatif)")
        cr1, cr2, cr3 = st.columns(3)
        cr1.metric("🛣️ Distance OSRM A/R", f"{distance_osrm_ar:,.0f} km".replace(",", " "))
        cr2.metric(f"⏱️ Durée aller ({vitesse_pl:.0f} km/h)",
                   f"{duree_aller_min:.0f} min ({duree_aller_min/60:.1f} h)")
        cr3.metric("📅 Jours mission", f"{jours_mission}")

    # =====================================================================
    # 3. PARAMÈTRES DE LA LIVRAISON (éditables)
    # =====================================================================
    st.divider()
    params = load_params()

    db_distance = float(dest_data.get("distance_ar_km") or 0) if dest_data else 0
    db_peages = float(dest_data.get("peages_ar") or 0) if dest_data else 0
    db_frais_mission = float(dest_data.get("frais_mission_unitaire") or 0) if dest_data else 0
    db_frais_voyage = float(dest_data.get("frais_voyage") or 0) if dest_data else 0
    db_frais_hebergement = float(dest_data.get("frais_hebergement") or 0) if dest_data else 0

    # Distance par défaut : OSRM (route réelle depuis le garage) si disponible, sinon base de données
    if distance_osrm_ar and distance_osrm_ar > 0:
        default_distance = round(distance_osrm_ar, 1)
    else:
        default_distance = db_distance

    # Forcer la mise à jour des champs quand la destination ou le point GPS change
    _dest_key = f"{destination}_{mode}_{gps_lat}_{gps_lon}_{len(st.session_state.get('waypoints', []))}"
    if st.session_state.get("_last_dest_key") != _dest_key:
        st.session_state["_last_dest_key"] = _dest_key
        st.session_state.pop("sim_dist", None)
        st.session_state.pop("sim_peages", None)

    # =====================================================================
    # 4. TABLEAU DE SIMULATION (style TB Excel)
    # =====================================================================
    # Nom affiché : lieu recherché + ville de référence si différent
    _nom_affiche = destination
    if lieu_recherche and lieu_recherche.upper() != destination.upper():
        _nom_affiche = f"{lieu_recherche} (réf: {destination})"

    st.markdown(f"### ESTIMATION COUT DE VOYAGE — {_nom_affiche}")

    # En-tête info
    col_info1, col_info2 = st.columns(2)
    with col_info1:
        st.markdown(f"**SITE DE LIVRAISON** : {_nom_affiche}")
        if distance_osrm_ar and distance_osrm_ar > 0:
            _dist_label = f"Distance A/R (km) — route OSRM depuis le garage"
            _dist_help = (f"Calculée automatiquement via OSRM. "
                          f"Modifiable si besoin (ex : itinéraire différent).")
        else:
            _dist_label = "Distance A/R (km) — saisie manuelle"
            _dist_help = "Pas de coordonnées GPS. Saisissez la distance manuellement."
        input_distance = st.number_input(
            _dist_label, value=default_distance,
            min_value=0.0, step=10.0, format="%.1f", key="sim_dist",
            help=_dist_help)
        consommation = params.get("consommation_l_km", 0.5)
        carburant_litres = input_distance * consommation
        st.markdown(f"**CARBURANT** : {carburant_litres:,.0f} L".replace(",", " "))
        st.markdown(f"**Qté à livrer** : {quantite:,} kg".replace(",", " "))

    with col_info2:
        taux_maint = params.get("maintenance_pct_ca", 0.0385)
        st.markdown(f"**Coût maintenance / CA** : {taux_maint*100:.2f} %")

    st.divider()

    # ---- Ligne par ligne : Eléments | Qté | Prix U. | Montant ----
    prix_carburant = params.get("prix_carburant", 700)

    # Champs éditables pour chaque poste
    st.markdown("#### Détail des charges")

    # Préparer les données éditables dans un formulaire compact
    col_el, col_qty, col_pu, col_mt = st.columns([3, 1.5, 1.5, 2])
    col_el.markdown("**Eléments**")
    col_qty.markdown("**Qté**")
    col_pu.markdown("**Prix U.**")
    col_mt.markdown("**Montant**")

    # --- Prix offert (ligne CA) ---
    col_el, col_qty, col_pu, col_mt = st.columns([3, 1.5, 1.5, 2])
    col_el.markdown("**Chiffre d'affaire F CFA**")
    col_qty.markdown(f"{quantite:,}".replace(",", " "))
    input_prix_kg = col_pu.number_input("F/kg", value=0, min_value=0, step=1,
                                         label_visibility="collapsed", key="sim_prix_kg",
                                         help="Laissez 0 pour calculer le prix plancher")
    # Le CA sera calculé après

    st.markdown("---")

    # --- Carburant ---
    col_el, col_qty, col_pu, col_mt = st.columns([3, 1.5, 1.5, 2])
    col_el.markdown("Carburant F CFA")
    col_qty.markdown(f"{carburant_litres:,.0f}".replace(",", " "))
    input_prix_carb = col_pu.number_input("Prix/L", value=int(prix_carburant), min_value=0,
                                           step=25, label_visibility="collapsed", key="sim_carb_pu")
    mt_carburant = carburant_litres * input_prix_carb
    col_mt.markdown(f"**{mt_carburant:,.0f}**".replace(",", " "))

    # --- Péages (détection automatique sur l'itinéraire OSRM) ---
    peages_detectes = []
    peages_total_aller = 0
    if trajet_info and trajet_info.get("geometry"):
        peages_detectes = geo.detecter_peages_sur_trajet(trajet_info["geometry"])
        peages_total_aller = sum(p["tarif"] for p in peages_detectes)

    peages_total_ar = peages_total_aller * 2  # Aller + retour

    col_el, col_qty, col_pu, col_mt = st.columns([3, 1.5, 1.5, 2])
    col_el.markdown("**Péages A/R**")
    if peages_detectes:
        col_qty.markdown(f"{len(peages_detectes)} poste(s) × 2")
        col_pu.markdown(f"{peages_total_aller:,} /trajet".replace(",", " "))
    else:
        col_qty.markdown("—")
        col_pu.markdown("—")

    # Champ éditable pré-rempli avec le calcul automatique, modifiable si besoin
    input_peages = col_mt.number_input(
        "Total péages A/R", value=int(peages_total_ar) if peages_total_ar > 0 else int(db_peages),
        min_value=0, step=500, label_visibility="collapsed", key="sim_peages",
        help="Calculé automatiquement depuis l'itinéraire. Modifiable si besoin.")

    # Détail des péages détectés
    if peages_detectes:
        with st.expander(f"🛣️ Détail des {len(peages_detectes)} péage(s) détecté(s) sur le trajet", expanded=False):
            for p in peages_detectes:
                st.markdown(f"- **{p['nom']}** ({p['axe']}) — {p['tarif']:,.0f} F/passage — _{p['distance_route_km']:.1f} km de la route_".replace(",", " "))
            st.caption(f"Total aller : {peages_total_aller:,.0f} F — **Total A/R : {peages_total_ar:,.0f} F**".replace(",", " "))

    # --- Frais de route ---
    col_el, col_qty, col_pu, col_mt = st.columns([3, 1.5, 1.5, 2])
    col_el.markdown("Frais de route")
    col_qty.markdown("1")
    input_frais_route = col_pu.number_input("Fr. route", value=int(params.get("frais_route", 0)),
                                             min_value=0, step=1000, label_visibility="collapsed",
                                             key="sim_froute")
    col_mt.markdown(f"**{input_frais_route:,}**".replace(",", " "))

    # --- Frais de voyage ---
    col_el, col_qty, col_pu, col_mt = st.columns([3, 1.5, 1.5, 2])
    col_el.markdown("Frais de voyage")
    col_qty.markdown("1")
    input_frais_voyage = col_pu.number_input("Fr. voyage", value=int(db_frais_voyage),
                                              min_value=0, step=1000, label_visibility="collapsed",
                                              key="sim_fvoyage")
    col_mt.markdown(f"**{input_frais_voyage:,}**".replace(",", " "))

    # --- Prime de voyage ---
    col_el, col_qty, col_pu, col_mt = st.columns([3, 1.5, 1.5, 2])
    col_el.markdown("Prime de voyage")
    prime_v = pricer.prime_par_distance(input_distance, params)
    col_qty.markdown("1")
    input_prime = col_pu.number_input("Prime", value=int(prime_v), min_value=0, step=5000,
                                       label_visibility="collapsed", key="sim_prime")
    col_mt.markdown(f"**{input_prime:,}**".replace(",", " "))

    # --- Frais d'hébergement ---
    col_el, col_qty, col_pu, col_mt = st.columns([3, 1.5, 1.5, 2])
    col_el.markdown("Frais d'hébergement")
    col_qty.markdown("1")
    input_hebergement = col_pu.number_input("Héberg.", value=int(db_frais_hebergement),
                                             min_value=0, step=5000, label_visibility="collapsed",
                                             key="sim_heberg")
    col_mt.markdown(f"**{input_hebergement:,}**".replace(",", " "))

    # --- Frais de mission ---
    col_el, col_qty, col_pu, col_mt = st.columns([3, 1.5, 1.5, 2])
    col_el.markdown("Frais de mission")
    col_qty.markdown("1")
    input_frais_mission = col_pu.number_input("Fr. mission", value=int(db_frais_mission),
                                               min_value=0, step=1000, label_visibility="collapsed",
                                               key="sim_fmission")
    col_mt.markdown(f"**{input_frais_mission:,}**".replace(",", " "))

    # --- Lettre de voiture ---
    col_el, col_qty, col_pu, col_mt = st.columns([3, 1.5, 1.5, 2])
    col_el.markdown("Lettre de voiture F CFA")
    col_qty.markdown("1")
    lv_default = int(params.get("lettre_voiture", 2500))
    input_lv = col_pu.number_input("LV", value=lv_default, min_value=0, step=500,
                                    label_visibility="collapsed", key="sim_lv")
    col_mt.markdown(f"**{input_lv:,}**".replace(",", " "))

    # --- Pesage ---
    col_el, col_qty, col_pu, col_mt = st.columns([3, 1.5, 1.5, 2])
    col_el.markdown("Pesage")
    col_qty.markdown("1")
    input_pesage = col_pu.number_input("Pesage", value=int(params.get("pesage", 2000)),
                                        min_value=0, step=500, label_visibility="collapsed",
                                        key="sim_pesage")
    col_mt.markdown(f"**{input_pesage:,}**".replace(",", " "))

    # --- Autres dépenses ---
    col_el, col_qty, col_pu, col_mt = st.columns([3, 1.5, 1.5, 2])
    col_el.markdown("Autres dépenses")
    col_qty.markdown("1")
    col_pu.markdown(f"{autres:,}".replace(",", " "))
    col_mt.markdown(f"**{autres:,}**".replace(",", " "))

    # ---- Calcul via pricer ----
    dist_override = input_distance
    peages_override = float(input_peages)
    frais_override = float(input_frais_mission)

    calc = pricer.calculer(
        destination, attelage, quantite, autres,
        prix_offert_kg=input_prix_kg if input_prix_kg > 0 else None,
        distance_ar_override=dist_override,
        peages_ar_override=peages_override,
        frais_mission_override=frais_override,
        pesage_override=float(input_pesage),
        frais_voyage_override=float(input_frais_voyage),
        frais_route_override=float(input_frais_route),
        cout_hebergement_nuit=float(input_hebergement),
    )

    # --- Coût de maintenance ---
    col_el, col_qty, col_pu, col_mt = st.columns([3, 1.5, 1.5, 2])
    col_el.markdown("Coût de maintenance")
    col_qty.markdown(f"{calc.ca_total:,.0f}".replace(",", " "))
    taux_eff = taux_maint
    col_pu.markdown(f"{taux_eff*100:.2f} %")
    col_mt.markdown(f"**{calc.maintenance:,.0f}**".replace(",", " "))

    # --- Total Charges ---
    st.markdown("---")
    col_el, col_qty, col_pu, col_mt = st.columns([3, 1.5, 1.5, 2])
    col_el.markdown("### Total Charges")
    col_mt.markdown(f"### {calc.total_charges:,.0f}".replace(",", " "))

    # =====================================================================
    # 5. RÉSULTATS — MARGE & KPIs
    # =====================================================================
    st.divider()

    # CA
    col_el, col_mt = st.columns([3, 2])
    col_el.markdown(f"**Chiffre d'affaire** ({quantite:,} kg × {calc.prix_offert_kg:,.0f} F/kg)")
    col_mt.markdown(f"### {calc.ca_total:,.0f} F".replace(",", " "))

    r1, r2, r3, r4 = st.columns(4)
    r1.metric("Marge brute", f"{calc.marge_brute:,.0f} F".replace(",", " "))
    r2.metric("Taux de marge", f"{calc.taux_marge*100:.1f} %")
    r3.metric("F CFA / km", f"{calc.fcfa_par_km:,.0f}".replace(",", " "))
    r4.metric("Taux carburant / CA", f"{calc.taux_carburant_ca*100:.1f} %")

    # Indicateur marge
    cible = params.get("marge_cible", 0.75)
    seuil_bas = params.get("seuil_marge_basse", 0.60)
    seuil_crit = params.get("seuil_marge_critique", 0.375)
    if calc.taux_marge >= cible:
        st.success(f"✅ Marge ≥ cible ({cible*100:.0f} %)")
    elif calc.taux_marge >= seuil_bas:
        st.warning(f"⚠️ Marge faible — sous la cible ({cible*100:.0f} %)")
    elif calc.taux_marge >= seuil_crit:
        st.error(f"🚨 Marge critique — seuil bas : {seuil_bas*100:.0f} %")
    else:
        st.error(f"🛑 Marge insuffisante — sous le seuil critique ({seuil_crit*100:.0f} %)")

    # ---- Calcul du prix de vente (méthode Excel) ----
    st.markdown("---")
    col_pv1, col_pv2 = st.columns(2)
    col_pv1.markdown(f"**Coût total / kg** : {calc.cout_par_kg:,.0f} F/kg".replace(",", " "))
    col_pv1.markdown(f"**Marge espérée** : {cible*100:.0f} %")
    prix_vente_cible = (calc.total_charges / max(1 - cible, 0.01)) / max(quantite, 1)
    col_pv2.metric("Prix de vente recommandé", f"{prix_vente_cible:,.0f} F/kg".replace(",", " "))

    # =====================================================================
    # 6. COMPARAISON PAR NIVEAU DE MARGE (style TB Excel)
    # =====================================================================
    st.divider()
    st.subheader("📊 Simulation par niveau de marge")
    st.caption("Tarifs calculés pour atteindre différents niveaux de marge cible.")

    marges_cibles = [0.75, 0.70, 0.65, 0.60]
    rows_comp = []
    for mc in marges_cibles:
        denom = max(1 - (taux_eff if taux_maint > 0 else 0) - mc, 0.0001)
        charges_base = calc.total_charges - calc.maintenance
        ca_sc = charges_base / denom
        tarif_sc = ca_sc / max(quantite, 1)
        maint_sc = ca_sc * taux_eff if taux_maint > 0 else calc.maintenance
        charges_sc = charges_base + maint_sc
        marge_sc = ca_sc - charges_sc
        rows_comp.append({
            "Marge cible": f"{mc*100:.0f} %",
            "Tarif (F/kg)": f"{tarif_sc:,.2f}".replace(",", " "),
            "CA (F CFA)": f"{ca_sc:,.0f}".replace(",", " "),
            "Marge brute (F)": f"{marge_sc:,.0f}".replace(",", " "),
        })

    df_comp = pd.DataFrame(rows_comp)
    st.dataframe(df_comp, use_container_width=True, hide_index=True)

    # =====================================================================
    # 7. CARTE (optionnel)
    # =====================================================================
    if route_lat is not None and route_lon is not None:
        with st.expander("🗺️ Visualiser l'itinéraire (indicatif)", expanded=False):
            st.caption("⚠️ Itinéraire indicatif — peut différer du trajet réel.")
            m_view = geo.carte_folium(
                lat=float(route_lat), lon=float(route_lon),
                route_depuis_garage=True, marker_label=_nom_affiche,
                vrai_itineraire=True, waypoints=waypoints_tuple,
            )
            st_folium(m_view, width=None, height=400, returned_objects=[], key="map_view")

    # =====================================================================
    # 8. ENREGISTREMENT
    # =====================================================================
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
