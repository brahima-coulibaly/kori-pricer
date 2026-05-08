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
else:
    st.dataframe(df[["nom", "axe", "tarif_classe4", "actif"]], use_container_width=True, hide_index=True)
