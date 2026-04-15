"""Couche d'accès Supabase — client unique partagé via st.cache_resource."""
from __future__ import annotations
import os
import streamlit as st
from supabase import create_client, Client


def _get_cfg(key: str) -> str:
    # Priorité : st.secrets > variables d'environnement
    try:
        if key in st.secrets:
            return st.secrets[key]
    except Exception:
        pass
    v = os.environ.get(key)
    if not v:
        st.error(f"Configuration manquante : {key}. Renseignez-le dans .streamlit/secrets.toml")
        st.stop()
    return v


@st.cache_resource
def get_client() -> Client:
    url = _get_cfg("SUPABASE_URL")
    key = _get_cfg("SUPABASE_ANON_KEY")
    return create_client(url, key)


def sb() -> Client:
    """Retourne le client Supabase avec la session utilisateur courante si dispo."""
    client = get_client()
    sess = st.session_state.get("sb_session")
    if sess:
        # Attache le token d'accès pour que RLS s'applique correctement
        try:
            client.postgrest.auth(sess["access_token"])
        except Exception:
            pass
    return client
