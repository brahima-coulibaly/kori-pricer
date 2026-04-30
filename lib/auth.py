"""Authentification Supabase + gestion des rôles."""
from __future__ import annotations
import streamlit as st
from .db import get_client, sb

ROLES = ["commercial", "manager", "admin", "consultation"]
ROLE_LABELS = {
    "commercial": "Commercial",
    "manager": "Manager",
    "admin": "Administrateur",
    "consultation": "Consultation",
}


def sign_in(email: str, password: str) -> tuple[bool, str]:
    client = get_client()
    try:
        res = client.auth.sign_in_with_password({"email": email, "password": password})
        if res.session:
            st.session_state["sb_session"] = {
                "access_token": res.session.access_token,
                "refresh_token": res.session.refresh_token,
            }
            st.session_state["sb_user"] = {"id": res.user.id, "email": res.user.email}
            _load_profile()
            return True, "Connecté."
        return False, "Échec de connexion."
    except Exception as e:
        return False, f"Erreur : {e}"


def sign_up(email: str, password: str, nom: str = "") -> tuple[bool, str]:
    client = get_client()
    try:
        res = client.auth.sign_up({"email": email, "password": password})
        if res.user:
            # Met à jour le profil avec le nom (rôle par défaut = consultation via trigger)
            try:
                client.table("profiles").update({"nom_complet": nom}).eq("id", res.user.id).execute()
            except Exception:
                pass
            return True, "Compte créé. Vérifiez votre email si la confirmation est activée, puis contactez un administrateur pour l'attribution de votre rôle."
        return False, "Impossible de créer le compte."
    except Exception as e:
        return False, f"Erreur : {e}"


def sign_out():
    try:
        get_client().auth.sign_out()
    except Exception:
        pass
    for k in ("sb_session", "sb_user", "profile"):
        st.session_state.pop(k, None)


def _load_profile():
    user = st.session_state.get("sb_user")
    if not user:
        return
    try:
        res = sb().table("profiles").select("*").eq("id", user["id"]).single().execute()
        st.session_state["profile"] = res.data
    except Exception:
        st.session_state["profile"] = None


def current_user() -> dict | None:
    return st.session_state.get("sb_user")


def current_profile() -> dict | None:
    if "profile" not in st.session_state and current_user():
        _load_profile()
    return st.session_state.get("profile")


def current_role() -> str:
    p = current_profile()
    return (p or {}).get("role", "consultation")


def _hide_sidebar():
    """Masque complètement la sidebar et la navigation quand l'utilisateur n'est pas connecté."""
    st.markdown(
        """
        <style>
        [data-testid="stSidebar"] { display: none; }
        [data-testid="stSidebarCollapsedControl"] { display: none; }
        </style>
        """,
        unsafe_allow_html=True,
    )


def require_auth():
    if not current_user():
        _hide_sidebar()
        st.warning("Veuillez vous connecter depuis la [page d'accueil](/).")
        st.stop()
    p = current_profile()
    if not p or not p.get("actif", True):
        _hide_sidebar()
        st.error("Votre compte est inactif. Contactez un administrateur.")
        st.stop()


def require_role(*roles: str):
    require_auth()
    if current_role() not in roles:
        st.error(f"Accès refusé — rôle requis : {', '.join(roles)}. Votre rôle : {current_role()}.")
        st.stop()
