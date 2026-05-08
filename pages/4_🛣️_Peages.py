"""Gestion des postes de péage — Admin uniquement."""
import streamlit as st
import pandas as pd
from lib import auth
from lib.db import sb

st.set_page_config(page_title="Péages — KORI", page_icon="🛣️", layout="wide")
auth.require_auth()
is_admin = auth.current_role() == "admin"

st.title("🛣️ Postes de péage")
st.caption("Postes de péage en Côte d'Ivoire — tarifs classe 4 (3 essieux et plus)")

rows = sb().table("peages").select("*").order("axe,nom").execute().data or []
df = pd.DataFrame(rows)

if df.empty:
    st.warning("Aucun poste de péage en base. Exécutez le script SQL `supabase_peages.sql`.")
    st.stop()

# Vue résumé par axe
st.subheader("Résumé par axe")
if not df.empty:
    resume = df.groupby("axe").agg(
        nb_postes=("id", "count"),
        tarif_total=("tarif_classe4", "sum"),
    ).reset_index()
    resume.columns = ["Axe", "Nb postes", "Total péages aller (F CFA)"]
    resume["Total A/R (F CFA)"] = resume["Total péages aller (F CFA)"] * 2
    st.dataframe(resume, use_container_width=True, hide_index=True)

st.divider()

if is_admin:
    st.subheader("📋 Éditer les postes de péage")
    st.info("Modifiez les tarifs, coordonnées GPS ou désactivez un poste. "
            "Les coordonnées GPS doivent être précises pour la détection automatique sur les itinéraires.")

    edited = st.data_editor(
        df, use_container_width=True, num_rows="dynamic", hide_index=True,
        disabled=["id", "maj_le"],
        column_config={
            "tarif_classe4": st.column_config.NumberColumn("Tarif Classe 4 (F CFA)", min_value=0, step=500),
            "latitude": st.column_config.NumberColumn("Latitude", format="%.6f"),
            "longitude": st.column_config.NumberColumn("Longitude", format="%.6f"),
            "actif": st.column_config.CheckboxColumn("Actif"),
            "rayon_detection_km": st.column_config.NumberColumn(
                "Rayon détection (km)", min_value=0.5, max_value=10.0, step=0.5,
                help="Rayon de détection personnalisé. Vide = 5 km par défaut. Réduit pour les ponts urbains (ex: 1 km)."),
        },
    )

    if st.button("💾 Sauvegarder", type="primary"):
        for _, row in edited.iterrows():
            payload = row.dropna().to_dict()
            payload.pop("maj_le", None)
            rid = payload.pop("id", None)
            if rid:
                sb().table("peages").update(payload).eq("id", int(rid)).execute()
            else:
                sb().table("peages").insert(payload).execute()
        st.success("Péages mis à jour.")
        st.rerun()
    # --- Outil de calibrage GPS ---
    st.divider()
    st.subheader("📍 Calibrage GPS des péages")
    st.info("**Comment corriger les coordonnées GPS d'un péage :**\n\n"
            "1. Ouvrez [Google Maps](https://maps.google.com) ou [OpenStreetMap](https://www.openstreetmap.org)\n"
            "2. Trouvez le poste de péage sur la carte (cherchez le nom)\n"
            "3. Faites un clic droit sur le péage → Copiez les coordonnées\n"
            "4. Collez latitude et longitude dans le tableau ci-dessus\n"
            "5. Sauvegardez\n\n"
            "**Important** : le point GPS doit être **sur la chaussée** (pas à côté), "
            "sinon la détection automatique ne fonctionnera pas correctement.")

    # Test rapide : vérifier un trajet
    st.markdown("#### 🧪 Test rapide de détection")
    st.caption("Testez la détection des péages sur un trajet donné.")
    from lib import geo
    test_col1, test_col2 = st.columns(2)
    test_lat = test_col1.number_input("Lat. destination test", value=6.5167,
                                       format="%.4f", key="test_plat")
    test_lon = test_col2.number_input("Lon. destination test", value=-7.3500,
                                       format="%.4f", key="test_plon")
    if st.button("🔍 Tester la détection", key="test_peages_btn"):
        with st.spinner("Calcul du trajet OSRM…"):
            trajet = geo.trajet_depuis_garage(test_lat, test_lon)
        if trajet and trajet.get("geometry"):
            st.success(f"Trajet : {trajet['distance_km']:.0f} km — {len(trajet['geometry'])} points")
            detectes, tous = geo.detecter_peages_sur_trajet(trajet["geometry"], diagnostic=True)
            st.markdown(f"**{len(detectes)} péage(s) détecté(s)** sur {len(tous)} actifs")
            for p in tous:
                icon = "✅" if p["detecte"] else "❌"
                st.markdown(f"{icon} **{p['nom']}** ({p['axe']}) — "
                            f"dist. route : **{p['distance_route_km']:.1f} km** "
                            f"(rayon : {p['rayon']:.1f} km) — "
                            f"GPS : ({p['lat_peage']:.4f}, {p['lon_peage']:.4f})")
        else:
            st.error("Impossible de calculer le trajet OSRM.")

else:
    st.dataframe(df[["nom", "axe", "tarif_classe4", "actif"]], use_container_width=True, hide_index=True)
