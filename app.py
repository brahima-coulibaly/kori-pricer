"""KORI TRANSPORT — Pricer web (page d'accueil et connexion)."""
import streamlit as st
from lib import auth

st.set_page_config(page_title="KORI Pricer", page_icon="🚛", layout="wide")


def sidebar():
    with st.sidebar:
        st.markdown(
            """
            <div style="background:#003B7A;color:#fff;padding:14px 10px;border-radius:8px;
                        text-align:center;font-weight:700;letter-spacing:1px;margin-bottom:10px;
                        font-family:'Arial Black',Arial,sans-serif;">
              🚛 KORI TRANSPORT
              <div style="font-size:0.7em;font-weight:400;opacity:0.9;margin-top:2px;">
                Pricer Gaz Butane
              </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        user = auth.current_user()
        profile = auth.current_profile()
        if user:
            role = auth.current_role()
            st.success(f"Connecté : **{user['email']}**")
            st.caption(f"Rôle : {auth.ROLE_LABELS.get(role, role)}")
            if st.button("Déconnexion", use_container_width=True):
                auth.sign_out()
                st.rerun()
        st.divider()
        st.caption("© 2026 KORI TRANSPORT SA")


def login_ui():
    st.title("🚛 KORI TRANSPORT — Pricer")
    st.subheader("Connexion")

    tab1, tab2 = st.tabs(["Se connecter", "Créer un compte"])

    with tab1:
        with st.form("login"):
            email = st.text_input("Email")
            pwd = st.text_input("Mot de passe", type="password")
            if st.form_submit_button("Se connecter", type="primary", use_container_width=True):
                ok, msg = auth.sign_in(email, pwd)
                if ok:
                    st.rerun()
                else:
                    st.error(msg)

    with tab2:
        with st.form("signup"):
            nom = st.text_input("Nom complet")
            email2 = st.text_input("Email ", key="su_email")
            pwd2 = st.text_input("Mot de passe (min. 8 caractères)", type="password", key="su_pwd")
            if st.form_submit_button("Créer mon compte", use_container_width=True):
                if len(pwd2) < 8:
                    st.error("Mot de passe trop court.")
                else:
                    ok, msg = auth.sign_up(email2, pwd2, nom)
                    (st.success if ok else st.error)(msg)


def home():
    profile = auth.current_profile() or {}
    role = auth.current_role()
    st.title(f"Bienvenue, {profile.get('nom_complet') or profile.get('email','')}")
    st.caption(f"Rôle : **{auth.ROLE_LABELS.get(role, role)}**")

    st.markdown("""
### Navigation
Utilisez le menu latéral pour accéder aux différents modules :

- **Nouvelle offre** — Créer une offre commerciale (Commercial, Manager, Admin)
- **Historique** — Consulter toutes les offres (tous rôles)
- **Destinations** — Table des 74 localités (lecture pour tous, édition Admin)
- **Véhicules** — Parc d'attelages (lecture pour tous, édition Admin)
- **Paramètres** — Hypothèses de tarification (Admin)
- **Utilisateurs** — Gestion des comptes (Admin)
""")

    # Tableau de bord mini
    try:
        from lib.db import sb
        offres = sb().table("offres").select("id,marge_brute,ca_total,taux_marge").execute().data or []
        c1, c2, c3 = st.columns(3)
        c1.metric("Offres totales", len(offres))
        ca = sum((o.get("ca_total") or 0) for o in offres)
        mb = sum((o.get("marge_brute") or 0) for o in offres)
        c2.metric("CA cumulé", f"{ca:,.0f} F".replace(",", " "))
        c3.metric("Marge brute cumulée", f"{mb:,.0f} F".replace(",", " "))
    except Exception as e:
        st.info(f"(Tableau de bord indisponible : {e})")


sidebar()
if not auth.current_user():
    login_ui()
else:
    home()
