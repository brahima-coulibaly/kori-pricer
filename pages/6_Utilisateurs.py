"""Gestion des utilisateurs et des rôles — Admin uniquement."""
import streamlit as st
import pandas as pd
from lib import auth
from lib.db import sb

st.set_page_config(page_title="Utilisateurs — KORI", page_icon="👥", layout="wide")
auth.require_role("admin")

st.title("👥 Gestion des utilisateurs")

rows = sb().table("profiles").select("*").order("email").execute().data or []
df = pd.DataFrame(rows)

st.caption("Les comptes sont créés via l'inscription. Vous attribuez ensuite le rôle approprié.")

edited = st.data_editor(df, use_container_width=True, hide_index=True,
                        disabled=["id","email","cree_le"],
                        column_config={
                            "role": st.column_config.SelectboxColumn(
                                "Rôle", options=auth.ROLES, required=True),
                            "actif": st.column_config.CheckboxColumn("Actif"),
                        })

if st.button("💾 Sauvegarder les rôles", type="primary"):
    for _, row in edited.iterrows():
        sb().table("profiles").update({
            "role": row["role"],
            "actif": bool(row["actif"]),
            "nom_complet": row.get("nom_complet"),
        }).eq("id", row["id"]).execute()
    st.success("Profils mis à jour.")
    st.rerun()

st.divider()
st.subheader("Rôles disponibles")
st.markdown("""
- **Commercial** — peut créer des offres et consulter l'historique
- **Manager** — création + validation des offres + changement de statut
- **Administrateur** — accès complet (destinations, véhicules, paramètres, utilisateurs)
- **Consultation** — lecture seule de l'historique et des tables de référence
""")
