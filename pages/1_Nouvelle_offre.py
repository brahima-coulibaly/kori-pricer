"""Création d'une nouvelle offre commerciale."""
import streamlit as st
from lib import auth, pricer
from lib.db import sb
from lib.pdf import pdf_offre

st.set_page_config(page_title="Nouvelle offre — KORI", page_icon="📝", layout="wide")
auth.require_role("commercial", "manager", "admin")

st.title("📝 Nouvelle offre commerciale")

# Chargement des listes
dests = sb().table("destinations").select("localite,distance_ar_km,latitude,longitude").order("localite").execute().data or []
vehs = sb().table("vehicules").select("attelage").eq("actif", True).order("attelage").execute().data or []

mode = st.radio("Mode de saisie", ["Choisir une destination", "Coordonnées GPS"], horizontal=True)

destination = None
if mode == "Choisir une destination":
    destination = st.selectbox("Destination", [d["localite"] for d in dests])
else:
    st.caption("📍 Saisissez les coordonnées GPS du point de livraison. "
               "Côte d'Ivoire : latitude entre 4° et 11° (Nord), longitude entre -8° et -2° (Ouest).")
    c1, c2 = st.columns(2)
    lat = c1.number_input("Latitude (ex: 7.6900)", value=0.0, min_value=-90.0, max_value=90.0, format="%.4f")
    lon = c2.number_input("Longitude (ex: -5.0300)", value=0.0, min_value=-180.0, max_value=180.0, format="%.4f")
    if lat != 0.0 and lon != 0.0:
        # Validation : coordonnées plausibles pour la Côte d'Ivoire
        if not (4.0 <= lat <= 11.0 and -9.0 <= lon <= -2.0):
            st.error("⚠️ Ces coordonnées semblent être hors de la Côte d'Ivoire. "
                     "Vérifiez que la latitude est positive (Nord) et la longitude négative (Ouest).")
        best, d = pricer.ville_la_plus_proche(lat, lon)
        if best:
            if d < 10:
                st.success(f"✅ Ville la plus proche : **{best['localite']}** (écart : {d:.1f} km)")
            elif d < 50:
                st.info(f"📍 Ville la plus proche : **{best['localite']}** (écart : {d:.1f} km)")
            else:
                st.warning(f"⚠️ Ville la plus proche : **{best['localite']}** mais l'écart est de **{d:.1f} km** — "
                           "vérifiez vos coordonnées ou prévoyez des frais supplémentaires.")
            destination = best["localite"]

attelage = st.selectbox("Attelage", [v["attelage"] for v in vehs])
c1, c2 = st.columns(2)
quantite = c1.number_input("Quantité (kg)", value=28000, min_value=1, step=1000)
autres = c2.number_input("Autres dépenses (F CFA)", value=0, min_value=0, step=1000)

if destination and attelage:
    calc = pricer.calculer(destination, attelage, quantite, autres)

    st.divider()
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
    prix_offert = st.number_input("Prix offert client (F/kg) — laissez 0 pour utiliser le prix plancher",
                                  value=round(calc.prix_plancher_kg), min_value=0, step=1)
    calc = pricer.calculer(destination, attelage, quantite, autres,
                           prix_offert_kg=prix_offert if prix_offert > 0 else None)

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Total charges", f"{calc.total_charges:,.0f} F".replace(",", " "))
    m2.metric("Prix plancher", f"{calc.prix_plancher_kg:,.0f} F/kg".replace(",", " "))
    m3.metric("CA total", f"{calc.ca_total:,.0f} F".replace(",", " "))
    m4.metric("Taux de marge", f"{calc.taux_marge*100:.1f} %")

    # Alertes marge
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
        col_pdf.download_button("📄 Télécharger le PDF", data=pdf_bytes,
                                file_name=f"{st.session_state['last_offre']['numero']}.pdf",
                                mime="application/pdf", use_container_width=True)
