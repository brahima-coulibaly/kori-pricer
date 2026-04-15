"""Historique des offres — visible par tous les utilisateurs authentifiés."""
import streamlit as st
import pandas as pd
from lib import auth
from lib.db import sb
from lib.pdf import pdf_offre

st.set_page_config(page_title="Historique — KORI", page_icon="📋", layout="wide")
auth.require_auth()

st.title("📋 Historique des offres")

res = sb().table("offres").select("*").order("cree_le", desc=True).execute()
offres = res.data or []
if not offres:
    st.info("Aucune offre enregistrée pour le moment.")
    st.stop()

df = pd.DataFrame(offres)

# Filtres
with st.expander("🔍 Filtres"):
    c1, c2, c3 = st.columns(3)
    dest_filter = c1.multiselect("Destination", sorted(df["destination"].dropna().unique()))
    statut_filter = c2.multiselect("Statut", sorted(df["statut"].dropna().unique()))
    auteur_filter = c3.multiselect("Auteur", sorted(df["user_email"].dropna().unique()))

view = df.copy()
if dest_filter: view = view[view["destination"].isin(dest_filter)]
if statut_filter: view = view[view["statut"].isin(statut_filter)]
if auteur_filter: view = view[view["user_email"].isin(auteur_filter)]

# KPIs
c1, c2, c3, c4 = st.columns(4)
c1.metric("Nombre d'offres", len(view))
c2.metric("CA cumulé", f"{view['ca_total'].sum():,.0f} F".replace(",", " "))
c3.metric("Marge cumulée", f"{view['marge_brute'].sum():,.0f} F".replace(",", " "))
tx = (view["marge_brute"].sum() / view["ca_total"].sum() * 100) if view["ca_total"].sum() else 0
c4.metric("Taux marge moyen", f"{tx:.1f} %")

st.divider()

cols_affich = ["numero","date_offre","destination","attelage","quantite_kg",
               "total_charges","prix_offert_kg","ca_total","marge_brute","taux_marge",
               "statut","user_email"]
cols_affich = [c for c in cols_affich if c in view.columns]
st.dataframe(view[cols_affich], use_container_width=True, hide_index=True,
             column_config={
                 "taux_marge": st.column_config.NumberColumn("Tx marge", format="%.1f%%"),
                 "ca_total": st.column_config.NumberColumn("CA", format="%d"),
                 "marge_brute": st.column_config.NumberColumn("Marge", format="%d"),
             })

# Export CSV
st.download_button("📥 Exporter CSV", data=view.to_csv(index=False).encode("utf-8"),
                   file_name="historique_offres.csv", mime="text/csv")

# Détail + PDF d'une offre
st.divider()
st.subheader("Détail d'une offre")
num = st.selectbox("Sélectionnez un numéro d'offre", [""] + view["numero"].tolist())
if num:
    off = next(o for o in offres if o["numero"] == num)
    st.json(off)
    st.download_button("📄 Télécharger PDF", data=pdf_offre(off),
                       file_name=f"{num}.pdf", mime="application/pdf")

    role = auth.current_role()
    if role in ("manager", "admin"):
        new_statut = st.selectbox("Changer statut",
                                   ["brouillon","valide","envoye","accepte","refuse"],
                                   index=["brouillon","valide","envoye","accepte","refuse"].index(off["statut"]))
        if st.button("Mettre à jour le statut"):
            sb().table("offres").update({"statut": new_statut}).eq("id", off["id"]).execute()
            st.success("Statut mis à jour.")
            st.rerun()
