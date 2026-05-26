import hashlib
import time
from typing import Any, Dict, cast

import streamlit as st

from src.config import APP_TITLE
from src.database import get_supabase
from src.lang import t
from src.logger import log_event_sync
from src.utils import format_swedish_date, get_now, to_local_time


def show_login(controller: Any):
    """Entry point for the Coach Engine authentication gatekeeper."""

    if "use_lang" not in st.session_state:
        st.session_state.use_lang = "sv"

    def update_lang():
        current = st.session_state.lang_toggle
        st.session_state.use_lang = "en" if current else "sv"

    cols = st.columns([0.8, 0.2])
    with cols[1]:
        st.toggle(
            f"🌐 {st.session_state.use_lang.upper()}",
            value=(st.session_state.use_lang == "en"),
            key="lang_toggle",
            on_change=update_lang,
        )

    lang = st.session_state.use_lang
    st.title(APP_TITLE)

    # 1. PUBLIC SESSION PREVIEW
    _render_public_next_session(lang)

    st.success(t("msg_landing_welcome", lang))
    st.warning(t("msg_landing_details", lang))
    st.error(t("lbl_schedule", lang))

    # 2. AUTHENTICATION FORM
    col1, _ = st.columns([1, 1])
    with col1:
        st.subheader(t("lbl_login", lang))
        email = st.text_input(t("lbl_email", lang), key="login_input_email")
        password = st.text_input(
            t("lbl_password", lang), type="password", key="login_input_pwd"
        )
        remember_me = st.checkbox(
            t("lbl_remember_me", lang), value=True, key="login_check_remember"
        )

        if st.button(
            t("btn_start_engine", lang),
            use_container_width=True,
            type="primary",
            key="login_btn_submit",
        ):
            # Normalizing email string to lowercase to enforce case-insensitivity
            email_clean = str(email).strip().lower()
            login_success = False
            user_data_row = None

            # Phase 1: Authentication against Auth Provider
            try:
                client = get_supabase()
                response = client.auth.sign_in_with_password(
                    {"email": email_clean, "password": password}
                )

                if response.user:
                    user_query = (
                        client.table("users")
                        .select("*")
                        .eq("use_uuid", response.user.id)
                        .execute()
                    )
                    if user_query.data and len(user_query.data) > 0:
                        user_data_row = cast(Dict[str, Any], user_query.data[0])
                        login_success = True
                    else:
                        client.auth.sign_out()
                        log_event_sync(
                            15,
                            0,
                            "Login rejected: Missing user profile record",
                            target_table="auth",
                        )
                        st.error(t("err_profile_missing", lang))
                else:
                    log_event_sync(
                        15,
                        0,
                        "Failed login attempt (Invalid credentials)",
                        target_table="auth",
                    )
                    st.error(t("err_invalid_credentials", lang))
            except Exception as e:
                log_event_sync(
                    15,
                    0,
                    f"System exception during auth loop: {e}",
                    target_table="auth",
                )
                st.error(t("err_invalid_credentials", lang))

            # Phase 2: Session state population
            if login_success and user_data_row:
                try:
                    st.session_state.user_id = int(user_data_row["use_id"])
                    st.session_state.user_name = str(user_data_row["use_first_name"])
                    st.session_state.user_rol_id = int(user_data_row["use_rol_id"])
                    st.session_state.authenticated = True
                    st.session_state.use_lang = str(user_data_row.get("use_lang", "sv"))

                    log_event_sync(
                        2,
                        st.session_state.user_id,
                        "Manual login success",
                        target_table="auth",
                    )

                    if remember_me:
                        try:
                            salt = st.secrets.get("SESSION_SALT", "fallback_secret")
                            token = hashlib.sha256(
                                f"{user_data_row['use_uuid']}{salt}".encode()
                            ).hexdigest()
                            controller.set("ce_session_token", token, max_age=2592000)
                            controller.set(
                                "ce_user_id",
                                str(st.session_state.user_id),
                                max_age=2592000,
                            )
                        except Exception as ce_err:
                            log_event_sync(
                                1,
                                st.session_state.user_id,
                                f"Cookie storage warning: {ce_err}",
                                target_table="auth",
                            )

                    st.success(t("msg_login_success", lang))
                    time.sleep(0.5)
                    st.rerun()
                except Exception as e:
                    log_event_sync(
                        15,
                        0,
                        f"Critical state assignment failure: {e}",
                        target_table="auth",
                    )
                    st.error(t("err_invalid_credentials", lang))

    st.caption("© 2026 Zebricorn Consulting AB")


def _render_public_next_session(lang: str):
    """Displays upcoming public training event data."""
    try:
        client = get_supabase()
        res = (
            client.table("workout_sessions")
            .select("*, locations(*)")
            .gte("ses_timestamp", get_now().isoformat())
            .order("ses_timestamp")
            .limit(1)
            .execute()
        )

        if res and res.data:
            session = cast(Dict[str, Any], res.data[0])
            loc = session.get("locations", {})
            loc_name = loc.get(f"loc_name_{'en' if lang == 'en' else 'swe'}", "Unknown")
            dt = to_local_time(str(session.get("ses_timestamp", "")))

            with st.container(border=True):
                st.markdown(f"### 🏠 {t('lbl_next_training', lang)}")
                st.write(f"**{loc_name}** | ⏰ {format_swedish_date(dt)}")
    except Exception:
        pass
