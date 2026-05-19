"""Nouvelle offre commerciale — KORI TRANSPORT."""
import streamlit as st
import pandas as pd
from lib import auth, pricer, geo
from lib.db import sb
from lib.pdf import pdf_offre
from lib.pricer import load_params

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

destination = None
gps_lat, gps_lon = None, None
dest_data = None
lieu_recherche = None

st.caption("🔎 Tapez le nom du lieu de livraison puis appuyez sur Entrée")
query = st.text_input("Nom du lieu", placeholder="Ex : Adzopé, Mine d'Ity, Zone industrielle Yopougon…",
                       label_visibility="collapsed")
if query:
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

# =====================================================================
# 2. QUANTITÉ
# =====================================================================
st.divider()
c1, c2 = st.columns(2)
quantite = c1.number_input("Qté à livrer (kg)", value=None, min_value=1, step=1000,
                            placeholder="Ex : 28000")
autres = c2.number_input("Autres dépenses (F CFA)", value=0, min_value=0, step=1000)

if not quantite or quantite <= 0:
    if destination:
        st.warning("⚠️ Veuillez renseigner la quantité à livrer (kg) pour lancer la simulation.")
    st.stop()

if destination:
    attelage = "739LS01-739LS01"
    route_lat = gps_lat if gps_lat is not None else (dest_data.get("latitude") if dest_data else None)
    route_lon = gps_lon if gps_lon is not None else (dest_data.get("longitude") if dest_data else None)

    # ---- Distance OSRM ----
    trajet_info = None
    distance_osrm_ar = None
    if route_lat is not None and route_lon is not None:
        try:
            _rlat, _rlon = float(route_lat), float(route_lon)
            with st.spinner("Calcul de l'itinéraire…"):
                trajet_info = geo.trajet_depuis_garage(_rlat, _rlon)
            if trajet_info:
                distance_osrm_ar = trajet_info["distance_km"] * 2
        except (TypeError, ValueError):
            trajet_info = None

    # =====================================================================
    # 3. PARAMÈTRES & VALEURS PAR DÉFAUT
    # =====================================================================
    params = load_params()

    db_distance = float(dest_data.get("distance_ar_km") or 0) if dest_data else 0
    db_peages = float(dest_data.get("peages_ar") or 0) if dest_data else 0
    db_frais_mission = float(dest_data.get("frais_mission_unitaire") or 0) if dest_data else 0
    db_frais_voyage = float(dest_data.get("frais_voyage") or 0) if dest_data else 0
    db_frais_hebergement = float(dest_data.get("frais_hebergement") or 0) if dest_data else 0

    if distance_osrm_ar and distance_osrm_ar > 0:
        default_distance = round(distance_osrm_ar, 1)
    else:
        default_distance = db_distance

    # Forcer la mise à jour quand la destination ou le point GPS change
    _dest_key = f"{destination}_{gps_lat}_{gps_lon}"
    if st.session_state.get("_last_dest_key") != _dest_key:
        st.session_state["_last_dest_key"] = _dest_key
        for _k in ("sim_dist", "sim_peages", "sim_fmission", "sim_fvoyage",
                    "sim_heberg", "sim_froute", "sim_prime", "sim_pesage",
                    "sim_carb_pu", "sim_prix_kg", "sim_lv",
                    "_auto_dist", "_auto_peages"):
            st.session_state.pop(_k, None)

    # =====================================================================
    # 4. TABLEAU DE SIMULATION
    # =====================================================================
    _nom_affiche = destination
    if lieu_recherche and lieu_recherche.upper() != destination.upper():
        _nom_affiche = f"{lieu_recherche} (réf: {destination})"

    st.markdown(f"### ESTIMATION COUT DE VOYAGE — {_nom_affiche}")

    col_info1, col_info2 = st.columns(2)
    with col_info1:
        st.markdown(f"**SITE DE LIVRAISON** : {_nom_affiche}")
        # Forcer la mise à jour si la valeur auto-calculée a changé
        if st.session_state.get("_auto_dist") != default_distance:
            st.session_state["_auto_dist"] = default_distance
            st.session_state["sim_dist"] = default_distance
        input_distance = st.number_input(
            "Distance A/R (km)", value=default_distance,
            min_value=0.0, step=10.0, format="%.1f", key="sim_dist")
        consommation = params.get("consommation_l_km", 0.5)
        carburant_litres = input_distance * consommation
        st.markdown(f"**CARBURANT** : {carburant_litres:,.0f} L  —  **Qté** : {quantite:,} kg".replace(",", " "))

    with col_info2:
        taux_maint = params.get("maintenance_pct_ca", 0.0385)
        st.markdown(f"**Coût maintenance / CA** : {taux_maint*100:.2f} %")

    st.divider()

    # ---- Détail des charges ----
    st.markdown("#### Détail des charges")

    col_el, col_qty, col_pu, col_mt = st.columns([3, 1.5, 1.5, 2])
    col_el.markdown("**Eléments**")
    col_qty.markdown("**Qté**")
    col_pu.markdown("**Prix U.**")
    col_mt.markdown("**Montant**")

    prix_carburant = params.get("prix_carburant", 700)

    # --- Carburant ---
    col_el, col_qty, col_pu, col_mt = st.columns([3, 1.5, 1.5, 2])
    col_el.markdown("Carburant")
    col_qty.markdown(f"{carburant_litres:,.0f}".replace(",", " "))
    input_prix_carb = col_pu.number_input("Prix/L", value=int(prix_carburant), min_value=0,
                                           step=25, label_visibility="collapsed", key="sim_carb_pu")
    mt_carburant = carburant_litres * input_prix_carb
    col_mt.markdown(f"**{mt_carburant:,.0f}**".replace(",", " "))

    # --- Péages ---
    peages_detectes = []
    peages_total_aller = 0
    if trajet_info and trajet_info.get("geometry"):
        peages_detectes, _diag = geo.detecter_peages_sur_trajet(
            trajet_info["geometry"], diagnostic=True)
        peages_total_aller = sum(p["tarif"] for p in peages_detectes)
    peages_total_ar = peages_total_aller * 2

    col_el, col_qty, col_pu, col_mt = st.columns([3, 1.5, 1.5, 2])
    col_el.markdown("Péages A/R")
    if peages_detectes:
        col_qty.markdown(f"{len(peages_detectes)} poste(s) × 2")
        col_pu.markdown(f"{peages_total_aller:,} /trajet".replace(",", " "))
    else:
        col_qty.markdown("—")
        col_pu.markdown("—")

    _peages_default = int(peages_total_ar) if trajet_info else int(db_peages)
    if st.session_state.get("_auto_peages") != _peages_default:
        st.session_state["_auto_peages"] = _peages_default
        st.session_state["sim_peages"] = _peages_default
    input_peages = col_mt.number_input(
        "Péages", value=_peages_default,
        min_value=0, step=500, label_visibility="collapsed", key="sim_peages")

    # Détail péages (expander)
    if peages_detectes:
        with st.expander(f"Détail des {len(peages_detectes)} péage(s)", expanded=False):
            for p in peages_detectes:
                st.markdown(f"- **{p['nom']}** ({p['axe']}) — {p['tarif']:,.0f} F".replace(",", " "))
            st.caption(f"Total A/R : {peages_total_ar:,.0f} F".replace(",", " "))

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
    col_el.markdown("Lettre de voiture")
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
    calc = pricer.calculer(
        destination, attelage, quantite, autres,
        distance_ar_override=input_distance,
        peages_ar_override=float(input_peages),
        frais_mission_override=float(input_frais_mission),
        pesage_override=float(input_pesage),
        frais_voyage_override=float(input_frais_voyage),
        frais_route_override=float(input_frais_route),
        cout_hebergement_nuit=float(input_hebergement),
    )

    # --- Coût de maintenance ---
    col_el, col_qty, col_pu, col_mt = st.columns([3, 1.5, 1.5, 2])
    col_el.markdown("Coût de maintenance")
    col_qty.markdown(f"{calc.ca_total:,.0f}".replace(",", " "))
    col_pu.markdown(f"{taux_maint*100:.2f} %")
    col_mt.markdown(f"**{calc.maintenance:,.0f}**".replace(",", " "))

    # --- Total Charges ---
    st.markdown("---")
    col_el, col_qty, col_pu, col_mt = st.columns([3, 1.5, 1.5, 2])
    col_el.markdown("### Total Charges")
    col_mt.markdown(f"### {calc.total_charges:,.0f}".replace(",", " "))

    # =====================================================================
    # 5. RÉSULTATS
    # =====================================================================
    st.divider()

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

    # Prix de vente recommandé
    st.markdown("---")
    col_pv1, col_pv2 = st.columns(2)
    col_pv1.markdown(f"**Coût total / kg** : {calc.cout_par_kg:,.0f} F/kg".replace(",", " "))
    col_pv1.markdown(f"**Marge espérée** : {cible*100:.0f} %")
    prix_vente_cible = (calc.total_charges / max(1 - cible, 0.01)) / max(quantite, 1)
    col_pv2.metric("Prix de vente recommandé", f"{prix_vente_cible:,.0f} F/kg".replace(",", " "))

    # =====================================================================
    # 6. ENREGISTREMENT
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
