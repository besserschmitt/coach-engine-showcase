import streamlit as st

from src.lang import t
from src.logger import log_event_sync
from views.admin_profile import render_profile
from views.admin_settings import render_system_settings
from views.admin_stats import render_stats


def render_admin_tab():
    """
    Main container for the Admin tab hub (v3.0).
    Logic: RBAC-driven dynamic tab generation with failsafe default restrictions.
    """

    # 1. ROBUST SESSION & SECURITY LAYER CHECK
    raw_uid = st.session_state.get("user_id")
    lang = st.session_state.get("use_lang", "sv")

    if raw_uid is None:
        st.warning(t("msg_session_expired", lang))
        st.stop()

    # Default to standard lowest privilege level (3=Member) - NEVER default to Admin (1)
    user_rol_id = int(st.session_state.get("user_rol_id", 3))

    # 2. ROLE DEFINITION & PROFILE TEXT ASSEMBLY
    user_name = st.session_state.get("user_name", t("lbl_member", lang))
    first_name = user_name.split()[0] if " " in user_name else user_name
    full_name = st.session_state.get("user_display_name", user_name)

    role_map = {
        1: f"🛡️ {t('role_admin', lang)}",
        2: f"👑 {t('role_coach', lang)}",
        3: f"🏃 {t('role_member', lang)}",
    }
    role_text = role_map.get(user_rol_id, f"🏃 {t('role_member', lang)}")

    st.subheader(f"🌤️💪 {t('lbl_hello', lang)} {first_name}!")

    # 3. DYNAMIC TAB GENERATION BASED ON SESSION RBAC PERMISSIONS
    # Build core navigational array matching current privilege profiles
    tab_titles = [t("tab_profile", lang), t("tab_stats", lang)]
    is_admin = user_rol_id == 1

    if is_admin:
        tab_titles.append(t("tab_system_settings", lang))

    tabs = st.tabs(tab_titles)

    # 4. RENDERING & COMPONENT ROUTING LOGIC
    with tabs[0]:
        render_profile(full_name, role_text)

    with tabs[1]:
        render_stats()

    if is_admin:
        with tabs[2]:
            # FIXED: Replaced raw session dictionary query with coerced local integer variable
            if user_rol_id == 1:
                render_system_settings()
            else:
                # Log unauthorized elevation attempts immediately into the access logs tracking ledger
                log_event_sync(
                    1,
                    int(raw_uid),
                    f"RBAC Violation: Unauthorized access attempt to restricted administration layouts by user role {user_rol_id}",
                    target_table="audit_log",
                )
                st.error(t("msg_access_denied", lang))
