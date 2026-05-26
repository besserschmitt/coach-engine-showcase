import hashlib
import time

import streamlit as st
from streamlit_cookies_controller import CookieController

from src.config import PAGE_TITLE
from src.lang import t
from src.logger import log_event
from src.styles import apply_styles
from views.admin import render_admin_tab
from views.coach import show_coach

# Import views
from views.home import show_home
from views.sessions import render_sessions_tab

# --- 1. CONFIGURATION ---
st.set_page_config(
    page_title=PAGE_TITLE,
    page_icon="🏋️‍♂️",
    layout="wide",
    initial_sidebar_state="expanded",
)
apply_styles()

controller = CookieController(key="ce_cookie_controller")

# --- 2. AUTHENTICATION GATE ---
if "authenticated" not in st.session_state:
    st.session_state.authenticated = False

if st.session_state.get("logout_triggered", False):
    # Aggressive cookie and state wipe
    try:
        controller.remove("ce_session_token")
        controller.remove("ce_user_id")
    except Exception:
        pass

    st.session_state.authenticated = False
    st.session_state.logout_triggered = False
    st.session_state.cookie_logged = False
    st.session_state.user_id = None

    from views.login import show_login

    show_login(controller)
    st.stop()

if not st.session_state.authenticated or st.session_state.get("user_id") is None:
    time.sleep(0.3)

    saved_token = None
    saved_user_id = None

    # Defensive access to prevent NoneType TypeError
    if controller:
        try:
            saved_token = controller.get("ce_session_token")
            saved_user_id = controller.get("ce_user_id")
        except Exception:
            pass

    if saved_token and saved_user_id:
        from typing import Any, Dict, cast

        from src.database import supabase

        try:
            res = (
                supabase.table("users")
                .select(
                    "use_id, use_first_name, use_display_name, use_rol_id, use_uuid, use_lang"
                )
                .eq("use_id", str(saved_user_id))
                .execute()
            )
        except Exception:
            res = None

        if res and res.data:
            user_row = cast(Dict[str, Any], res.data[0])
            user_uuid = str(user_row["use_uuid"])

            salt = st.secrets.get("SESSION_SALT", "default_secret_fallback")
            expected_token = hashlib.sha256(f"{user_uuid}{salt}".encode()).hexdigest()

            if saved_token == expected_token:
                st.session_state.user_id = int(user_row["use_id"])
                st.session_state.user_name = str(user_row["use_first_name"])
                st.session_state.user_display_name = str(user_row["use_display_name"])
                st.session_state.user_rol_id = int(user_row["use_rol_id"])
                st.session_state.user_uuid = user_uuid
                st.session_state.use_lang = str(user_row.get("use_lang", "sv"))
                st.session_state.authenticated = True

                if not st.session_state.get("cookie_logged", False):
                    log_event(
                        2,
                        st.session_state.user_id,
                        "Auto-login via cookie",
                        target_table="auth",
                    )
                    st.session_state.cookie_logged = True
                st.rerun()
            else:
                # Token mismatch: clean up
                try:
                    controller.remove("ce_session_token")
                    controller.remove("ce_user_id")
                except Exception:
                    pass

    from views.login import show_login

    show_login(controller)
    st.stop()

# --- 3. MAIN NAVIGATION ---
current_role = st.session_state.get("user_rol_id", 3)
lang = st.session_state.get("use_lang", "sv")

tabs = st.tabs(
    [
        t("nav_home", lang),
        t("nav_coach", lang),
        t("nav_sessions", lang),
        t("nav_admin", lang),
    ]
)

with tabs[0]:
    show_home()
with tabs[1]:
    if current_role in [1, 2]:
        show_coach()
    else:
        st.error(t("msg_access_denied", lang))
with tabs[2]:
    render_sessions_tab()
with tabs[3]:
    render_admin_tab()
