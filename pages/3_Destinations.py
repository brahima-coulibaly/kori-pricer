"""Table des destinations — édition réservée Admin."""
import streamlit as st
import pandas as pd
from lib import auth
from lib.db import sb

st.set_page_config(page_title="Destinations — KORI", page_icon="🗺️", layout="wide")
auth.require_auth()
is_admin = auth.current_role() == "admin"

st.title("🗺️ Destinations")
st.caption("74 localités — distances et péages depuis le garage KORI (Ancienne voie de Bassam)")

rows = sb().table("destinations").select("*").order("localite").execute().data or []
df = pd.DataFrame(rows)

if is_admin:
    st.info("Mode administrateur : vous pouvez éditer les lignes ci-dessous.")
    edited = st.data_editor(df, use_container_width=True, num_rows="dynamic", hide_index=True,
                            disabled=["id","maj_le"])
    if st.button("💾 Sauvegarder les modifications", type="primary"):
        # Upsert par localité (upsert ignoré si RLS bloque)
        for _, row in edited.iterrows():
            payload = row.dropna().to_dict()
            payload.pop("maj_le", None)
            rid = payload.pop("id", None)
            if rid:
                sb().table("destinations").update(payload).eq("id", int(rid)).execute()
            else:
                sb().table("destinations").insert(payload).execute()
        st.success("Destinations mises à jour.")
        st.rerun()
else:
    st.dataframe(df, use_container_width=True, hide_index=True)
