"""Table des véhicules — édition réservée Admin."""
import streamlit as st
import pandas as pd
from lib import auth
from lib.db import sb

st.set_page_config(page_title="Véhicules — KORI", page_icon="🚛", layout="wide")
auth.require_auth()
is_admin = auth.current_role() == "admin"

st.title("🚛 Parc de véhicules (attelages)")

rows = sb().table("vehicules").select("*").order("attelage").execute().data or []
df = pd.DataFrame(rows)

if is_admin:
    st.info("Mode administrateur : vous pouvez éditer les lignes ci-dessous.")
    edited = st.data_editor(df, use_container_width=True, num_rows="dynamic", hide_index=True,
                            disabled=["id","maj_le"])
    if st.button("💾 Sauvegarder", type="primary"):
        for _, row in edited.iterrows():
            payload = row.dropna().to_dict()
            payload.pop("maj_le", None)
            rid = payload.pop("id", None)
            if rid:
                sb().table("vehicules").update(payload).eq("id", int(rid)).execute()
            else:
                sb().table("vehicules").insert(payload).execute()
        st.success("Véhicules mis à jour.")
        st.rerun()
else:
    st.dataframe(df, use_container_width=True, hide_index=True)
