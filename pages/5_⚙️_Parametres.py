"""Paramètres globaux — Admin uniquement."""
import streamlit as st
import pandas as pd
from lib import auth
from lib.db import sb

st.set_page_config(page_title="Paramètres — KORI", page_icon="⚙️", layout="wide")
auth.require_auth()
is_admin = auth.current_role() == "admin"

st.title("⚙️ Paramètres de tarification")

rows = sb().table("parametres").select("*").order("cle").execute().data or []
df = pd.DataFrame(rows)

if is_admin:
    st.warning("Ces valeurs impactent TOUTES les offres futures. Modifiez avec précaution.")
    edited = st.data_editor(df, use_container_width=True, hide_index=True,
                            disabled=["cle","maj_le"])
    if st.button("💾 Sauvegarder", type="primary"):
        for _, row in edited.iterrows():
            sb().table("parametres").update({
                "valeur": float(row["valeur"]),
                "unite": row.get("unite"),
                "description": row.get("description"),
            }).eq("cle", row["cle"]).execute()
        st.success("Paramètres mis à jour.")
        st.rerun()
else:
    st.dataframe(df, use_container_width=True, hide_index=True)
