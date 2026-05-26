import logging
from typing import Any, Dict, List, cast

import streamlit as st

from src.database import (  # Central JIT factory utilities
    get_recent_access_logs,
    get_supabase,
)
from src.lang import t
from src.logger import log_event_sync
from src.utils import to_local_time


@st.cache_data(ttl=300)
def _get_cached_admin_users_directory() -> List[Dict[str, Any]]:
    """Retrieves and caches user baseline directories securely using a resilient connection factory."""
    try:
        client = get_supabase()
        res = (
            client.table("users")
            .select("use_id, use_uuid, use_first_name, use_display_name")
            .execute()
        )
        return cast(List[Dict[str, Any]], res.data) if res and res.data else []
    except Exception as e:
        logging.error(
            f"Operational error caching user mapping directory inside system settings view: {e}"
        )
        return []


def render_system_settings():
    """Renders administrative dashboards including security access logs and identity provisioning controls."""
    lang = st.session_state.get("use_lang", "sv")
    admin_tabs = st.tabs([t("tab_access_logs", lang), t("tab_user_management", lang)])

    # --- TAB 1: ACCESS LOGS (V4.5 CLEAN ARCHITECTURE) ---
    with admin_tabs[0]:
        st.markdown(f"### 📋 {t('tab_access_logs', lang)}")

        # Centralized retrieval layer avoids N+1 queries by leveraging unified adapter functions
        res = get_recent_access_logs(limit=30)

        if res and res.data and len(res.data) > 0:
            logs = cast(List[Dict[str, Any]], res.data)
            cached_users = _get_cached_admin_users_directory()

            # Establish clean hash-maps for display labels, addressing system/anon background tasks safely
            user_map = {0: t("lbl_system_anon", lang)}
            for u in cached_users:
                if u.get("use_id"):
                    user_map[int(u["use_id"])] = str(u["use_first_name"])

            for log in logs:
                log_time = to_local_time(str(log.get("al_timestamp", ""))).strftime(
                    "%d/%m %H:%M:%S"
                )
                target_table = log.get("al_target_table", "-")
                target_id = log.get("al_target_id") or "-"
                action_type_id = log.get("al_action_type_id")

                # Safely extract audit log relation parameters to protect view layers from missing indexes
                type_relation = log.get("audit_log_type", {})
                alt_code = (
                    type_relation.get("alt_code", "UNKNOWN")
                    if isinstance(type_relation, dict)
                    else "UNKNOWN"
                )

                # Unpack dynamic JSONB layout content layers defensively
                payload = log.get("al_new_payload", {})
                payload_msg = ""
                client_ip = "Unknown IP"

                if isinstance(payload, dict):
                    payload_msg = payload.get("message", "")
                    client_ip = payload.get("client_ip", "Unknown IP")
                    # If an auth failure occurred, append diagnostic info straight to display layers
                    if "attempted_email" in payload:
                        payload_msg += f" ({t('lbl_attempt_col', lang)}: {payload.get('attempted_email')})"

                # 🚥 SECURITY MAPPING MATRIX: Dictate layout iconography based on core identity classifications
                if action_type_id == 15:  # AUTH_FAILURE
                    emoji = "🔴"
                    display_code = f"{t('lbl_security_deviation', lang)} ({alt_code})"
                elif action_type_id in [1, 5]:  # SYSTEM_EVENT (Crash) or DATA_DELETED
                    emoji = "🟠"
                    display_code = alt_code
                elif action_type_id in [2, 12]:  # USER_LOGIN or SESSION_CREATED
                    emoji = "🟢"
                    display_code = alt_code
                elif action_type_id in [4, 7]:  # USER_ROLE_UPDATED / RESET PWD
                    emoji = "🔵"
                    display_code = alt_code
                else:
                    emoji = "🟡"
                    display_code = alt_code

                # Resolve actor name records
                raw_actor_id = log.get("al_actor_user_id")
                actor_id = int(raw_actor_id) if raw_actor_id is not None else 0
                actor_name = user_map.get(actor_id, t("lbl_system_anon", lang))

                # Build highly scannable, mobile-responsive layout blocks for the dashboard feed
                with st.container(border=True):
                    col_meta, col_desc = st.columns([0.35, 0.65])

                    with col_meta:
                        st.markdown(f"{emoji} **{log_time}**")
                        st.caption(
                            f"**IP:** `{client_ip}` | **{t('lbl_actor_col', lang)}:** {actor_name}"
                        )

                    with col_desc:
                        st.markdown(f"`{display_code}`")
                        if payload_msg:
                            st.markdown(f"*{payload_msg}*")
                        else:
                            # Apply dynamic localization formatting rules cleanly without raw leak loops
                            modified_lbl = t("lbl_modified_action", lang)
                            st.caption(
                                f"{modified_lbl} `{target_table}` (ID: {target_id})"
                            )

        else:
            st.info(t("msg_no_logs", lang))

    # --- TAB 2: USER MANAGEMENT ---
    with admin_tabs[1]:
        cached_users = _get_cached_admin_users_directory()

        # SECTION A: CREATE NEW USER IDENTITY PROVISIONS
        with st.expander(t("btn_create_user", lang)):
            with st.form("create_user_form", clear_on_submit=True):
                new_email = st.text_input(t("lbl_email", lang))
                new_password = st.text_input(t("lbl_temp_pwd", lang), type="password")
                new_first_name = st.text_input(t("lbl_first_name", lang))
                new_display_name = st.text_input(t("lbl_full_name", lang))

                role_options = {
                    t("role_member", lang): 3,
                    t("role_coach", lang): 2,
                    t("role_admin", lang): 1,
                }
                selected_role = st.selectbox(
                    t("lbl_system_role", lang), options=list(role_options.keys())
                )

                if st.form_submit_button(t("btn_invite_user", lang)):
                    try:
                        client = get_supabase()
                        # Identity provisioning operations run cleanly via protected admin clients
                        auth_res = client.auth.admin.create_user(
                            {
                                "email": new_email,
                                "password": new_password,
                                "email_confirm": True,
                            }
                        )
                        if auth_res and auth_res.user:
                            client.table("users").insert(
                                {
                                    "use_uuid": auth_res.user.id,
                                    "use_first_name": new_first_name,
                                    "use_display_name": new_display_name,
                                    "use_rol_id": role_options[selected_role],
                                }
                            ).execute()

                            log_event_sync(
                                3,
                                st.session_state.user_id,
                                f"Created user: {new_email}",
                                target_table="users",
                            )
                            st.success(t("msg_account_created", lang))
                            st.rerun()
                    except Exception as e:
                        st.error(t("err_user_creation_failed", lang))
                        logging.error(
                            f"Exception encountered during administrative account provisioning: {e}"
                        )

        # SECTION B: ADMINISTRATIVE RESET CONTROL MATRICES
        with st.expander(t("btn_reset_pwd", lang)):
            user_opts = {
                u["use_display_name"]: u["use_uuid"]
                for u in cached_users
                if u.get("use_display_name")
            }

            selected_name = st.selectbox(
                t("lbl_select_user", lang), options=list(user_opts.keys())
            )
            new_pwd = st.text_input(t("lbl_new_temp_pwd", lang), type="password")

            if st.button(t("btn_forced_reset", lang)):
                try:
                    client = get_supabase()
                    client.auth.admin.update_user_by_id(
                        user_opts[selected_name], {"password": new_pwd}
                    )
                    log_event_sync(
                        7,
                        st.session_state.user_id,
                        f"Admin reset pwd: {selected_name}",
                        target_table="users",
                    )
                    st.success(t("msg_pwd_updated_admin", lang))
                    st.rerun()
                except Exception as e:
                    st.error(t("err_pwd_reset_failed", lang))
                    logging.error(
                        f"Exception raised during forced administrator pass reset sequence: {e}"
                    )
