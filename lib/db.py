"""Couche d'accès Supabase — un client par session utilisateur pour éviter les fuites de token."""
from __future__ import annotations
import os
import streamlit as st
from supabase import create_client, Client


def _get_cfg(key: str) -> str:
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


def _new_client() -> Client:
    return create_client(_get_cfg("SUPABASE_URL"), _get_cfg("SUPABASE_ANON_KEY"))


def get_client() -> Client:
    """Client non-authentifié (utilisé pour login/signup).
    Un client par session Streamlit pour éviter de partager l'état entre utilisateurs."""
    if "sb_client" not in st.session_state:
        st.session_state["sb_client"] = _new_client()
    return st.session_state["sb_client"]


def sb() -> Client:
    """Retourne le client Supabase avec la session utilisateur courante attachée.
    Rafraîchit la session depuis st.session_state à chaque appel pour garantir
    la fraîcheur du token et éviter les erreurs RLS."""
    client = get_client()
    sess = st.session_state.get("sb_session")
    if sess:
        token = sess.get("access_token")
        refresh = sess.get("refresh_token")
        # 1) Attacher le token au client d'auth (pour que sign_out fonctionne et
        #    pour que les policies voient bien auth.uid())
        try:
            client.auth.set_session(token, refresh)
        except Exception:
            pass
        # 2) Attacher explicitement le token au client PostgREST (data API)
        try:
            client.postgrest.auth(token)
        except Exception:
            pass
    return client
