"""Création d'une nouvelle offre commerciale — avec carte interactive OpenStreetMap."""
import streamlit as st
from lib import auth, pricer, geo
from lib.db import sb
from lib.pdf import pdf_offre
from streamlit_folium import st_folium

st.set_page_config(page_title="Nouvelle offre — KORI", page_icon="📝", layout="wide")
auth.require_role("commercial", "manager", "admin")

st.title("📝 Nouvelle offre commerciale")

# Chargement des listes
dests = sb().table("destinations").select("localite,distance_ar_km,latitude,longitude").order("localite").execute().data or []
vehs = sb().table("vehicules").select("attelage").eq("actif", True).order("attelage").execute().data or []

mode = st.radio(
    "Mode de saisie",
    ["Choisir dans la liste", "Rechercher une ville", "Carte interactive"],
    horizontal=True,
    help="Liste : vos 74 destinations habituelles. Recherche : toute ville de Côte d'Ivoire. Carte : cliquez n'importe où.",
)

destination = None
gps_lat, gps_lon = None, None

# ------- MODE 1 : choisir dans la liste -------
if mode == "Choisir dans la liste":
    destination = st.selectbox("Destination", [d["localite"] for d in dests])
    dest_data = next((d for d in dests if d["localite"] == destination), None)
    if dest_data:
        gps_lat, gps_lon = dest_data.get("latitude"), dest_data.get("longitude")

# ------- MODE 2 : recherche par nom (Nominatim / OpenStreetMap) -------
elif mode == "Rechercher une ville":
    st.caption("🔎 Tapez le nom d'une ville, d'un village ou d'un quartier puis cliquez sur Rechercher.")
    col_q, col_btn = st.columns([5, 1])
    query = col_q.text_input(
        "Nom de la ville ou du lieu",
        placeholder="Ex : Adzopé, Abobo, Vitré 2…",
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
    elif go:
        st.warning("Aucun résultat. Essayez une autre orthographe ou une ville plus proche.")

# ------- MODE 3 : carte cliquable -------
elif mode == "Carte interactive":
    st.caption("🗺️ Cliquez n'importe où sur la carte pour positionner le point de livraison.")
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
        # Éviter la boucle infinie : ne rerun que si c'est un nouveau clic
        if last is None or new_click != last:
            st.session_state["map_click"] = new_click
            st.rerun()
    if last:
        gps_lat, gps_lon = last["lat"], last["lng"]
        st.info(f"📍 Point sélectionné : **{gps_lat:.4f}, {gps_lon:.4f}**")
        best, ecart = pricer.ville_la_plus_proche(gps_lat, gps_lon)
        if best:
            destination = best["localite"]
            if ecart < 15:
                st.success(f"✅ Rattaché à **{destination}** (écart : {ecart:.1f} km)")
            elif ecart < 50:
                st.info(f"📍 Ville de référence la plus proche : **{destination}** (écart : {ecart:.1f} km)")
            else:
                st.warning(f"⚠️ Ville de référence la plus proche : **{destination}** à {ecart:.1f} km.")
        if st.button("🔄 Réinitialiser le point"):
            st.session_state.pop("map_click", None)
            st.rerun()

# ------- Suite du formulaire -------
st.divider()
attelage = st.selectbox("Attelage", [v["attelage"] for v in vehs])
c1, c2 = st.columns(2)
quantite = c1.number_input("Quantité (kg)", value=28000, min_value=1, step=1000)
autres = c2.number_input("Autres dépenses (F CFA)", value=0, min_value=0, step=1000)

if destination and attelage:
    dest_data = next((d for d in dests if d["localite"] == destination), None)

    # ---- Calcul de la distance routière réelle via OSRM ----
    # Si l'utilisateur est en mode recherche/carte, on utilise les coords GPS sélectionnées.
    # Sinon, on utilise les coords de la destination de la liste.
    route_lat = gps_lat if gps_lat is not None else (dest_data.get("latitude") if dest_data else None)
    route_lon = gps_lon if gps_lon is not None else (dest_data.get("longitude") if dest_data else None)

    trajet_info = None
    distance_ar_reelle = None
    if route_lat is not None and route_lon is not None:
        with st.spinner("Calcul de l'itinéraire routier…"):
            trajet_info = geo.trajet_depuis_garage(float(route_lat), float(route_lon))
        if trajet_info:
            distance_ar_reelle = trajet_info["distance_km"] * 2  # aller-retour

    # ---- Affichage des distances (DB vs routière) ----
    if trajet_info:
        col_r1, col_r2, col_r3 = st.columns(3)
        col_r1.metric("🛣️ Distance routière A/R",
                      f"{distance_ar_reelle:,.1f} km".replace(",", " "))
        col_r2.metric("⏱️ Durée estimée (aller)",
                      f"{trajet_info['duration_min']:.0f} min "
                      f"({trajet_info['duration_min']/60:.1f} h)")
        if dest_data and dest_data.get("distance_ar_km"):
            diff = distance_ar_reelle - float(dest_data["distance_ar_km"])
            col_r3.metric("Écart vs base", f"{diff:+.1f} km",
                          help="Différence entre la distance routière calculée et celle stockée en base.")

    # ---- Choix de la distance utilisée pour la tarification ----
    distance_override = None
    if mode in ("Rechercher une ville", "Carte interactive") and distance_ar_reelle:
        # Hors liste : on utilise systématiquement la distance routière réelle
        distance_override = distance_ar_reelle
        st.info(f"ℹ️ La tarification utilise la **distance routière réelle** "
                f"({distance_ar_reelle:.1f} km A/R) calculée via OpenStreetMap.")
    elif mode == "Choisir dans la liste" and distance_ar_reelle and dest_data:
        # En mode liste : par défaut distance DB, mais l'utilisateur peut choisir
        db_dist = float(dest_data.get("distance_ar_km") or 0)
        use_real = st.toggle(
            f"Utiliser la distance routière calculée ({distance_ar_reelle:.1f} km) "
            f"au lieu de la distance de référence ({db_dist:.0f} km) ?",
            value=False,
            help="La distance de référence (base de données) est généralement plus fiable "
                 "car validée historiquement. Activez cette option pour un point de livraison "
                 "différent ou pour une mise à jour ponctuelle.")
        if use_real:
            distance_override = distance_ar_reelle

    # ---- Carte du trajet ----
    if route_lat is not None and route_lon is not None:
        with st.expander("🗺️ Visualiser l'itinéraire routier",
                         expanded=(mode != "Carte interactive")):
            m_view = geo.carte_folium(
                lat=float(route_lat), lon=float(route_lon),
                route_depuis_garage=True,
                marker_label=destination,
                vrai_itineraire=True,
            )
            st_folium(m_view, width=None, height=400, returned_objects=[], key="map_view")

    calc = pricer.calculer(destination, attelage, quantite, autres,
                           distance_ar_override=distance_override)

    st.subheader("📊 Détail des charges")
    d1, d2, d3 = st.columns(3)
    d1.metric("Distance A/R", f"{calc.distance_ar:,.0f} km".replace(",", " "))
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
    calc = pricer.calculer(destination, attelage, quantite, autres,
                           prix_offert_kg=prix_offert if prix_offert > 0 else None,
                           distance_ar_override=distance_override)

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
