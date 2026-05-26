import csv
import io
import logging
import time
from datetime import datetime

import streamlit as st

from src.database import get_supabase, get_user_gdpr_data  # Central factory import
from src.lang import t


def render_profile(full_name: str, role_text: str):
    """Renders the personal profile dashboard, language configurations, and security matrices."""

    user_id = st.session_state.get("user_id")
    lang = st.session_state.get("use_lang", "sv")

    st.info(t("lbl_profile_info", lang))
    st.write(f"### {t('lbl_account_details', lang)}")

    with st.container(border=True):
        c1, c2 = st.columns(2)
        c1.text_input(t("lbl_full_name", lang), value=full_name, disabled=True)
        c2.text_input(t("lbl_role", lang), value=role_text, disabled=True)

        # 🌐 CENTRAL LANGUAGE SELECTOR
        lang_opts = {"Svenska": "sv", "English": "en"}
        current_lang_index = 0 if lang == "sv" else 1

        selected_lang_name = st.selectbox(
            t("lbl_lang_selector", lang),
            options=list(lang_opts.keys()),
            index=current_lang_index,
            key=f"profile_lang_selector_{user_id}",
        )
        new_lang_code = lang_opts[selected_lang_name]

        # Trigger live database connection updates upon dynamic changes
        if new_lang_code != lang and user_id:
            try:
                client = get_supabase()
                client.table("users").update({"use_lang": new_lang_code}).eq(
                    "use_id", user_id
                ).execute()
                st.session_state.use_lang = new_lang_code
                st.cache_data.clear()
                st.rerun()
            except Exception as e:
                st.error(t("err_lang_update_failed", lang))
                logging.error(f"Database translation shift error: {e}")

    # --- SESSION DISCONNECTION HANDLING ---
    st.write(f"### {t('lbl_session', lang)}")
    if st.button(
        t("btn_logout", lang),
        type="primary",
        use_container_width=True,
        key=f"btn_logout_{user_id}",
    ):
        st.session_state.clear()
        st.session_state["logout_triggered"] = True
        st.rerun()

    st.write(f"### {t('lbl_security', lang)}")

    # --- EXPANDER 1: PASSWORD MAINTENANCE ---
    with st.expander(t("lbl_pwd_expander", lang), expanded=False):
        with st.form("update_password_form", clear_on_submit=True):
            new_password = st.text_input(
                t("lbl_new_pwd", lang), type="password", help=t("help_pwd_len", lang)
            )
            confirm_password = st.text_input(t("lbl_conf_pwd", lang), type="password")

            if st.form_submit_button(
                t("btn_pwd_update", lang), use_container_width=True, type="primary"
            ):
                if len(new_password) < 6:
                    st.error(t("err_pwd_short", lang))
                elif new_password != confirm_password:
                    st.error(t("err_pwd_mismatch", lang))
                else:
                    try:
                        client = get_supabase()
                        client.auth.update_user({"password": new_password})
                        st.balloons()
                        st.success(t("msg_pwd_updated", lang))
                        time.sleep(1.2)
                    except Exception as e:
                        st.error(t("err_pwd_update_failed", lang))
                        logging.error(f"Auth credential management exception: {e}")

    # --- EXPANDER 2: REGULATORY AUDIT DATA PROTECTION (GDPR) ---
    with st.expander(t("lbl_gdpr_expander", lang), expanded=False):
        st.markdown(f"**{t('lbl_gdpr_header', lang)}**")
        st.caption(t("lbl_gdpr_text", lang))

        # Retrieve personal context cleanly through isolated storage transaction gates
        gdpr_data = (
            get_user_gdpr_data(user_id)
            if user_id
            else {
                "profile": {},
                "history": [],
                "logs": [],
                "error": "Session state index identifier missing context parameters.",
            }
        )

        if gdpr_data and gdpr_data.get("profile"):
            csv_buffer = io.StringIO()
            writer = csv.writer(csv_buffer, delimiter=";")

            # Localized textual variables for CSV formatting arrays
            title_header = (
                "GDPR REGISTERUTDRAG - COACH ENGINE"
                if lang == "sv"
                else "GDPR DATA EXTRACT - COACH ENGINE"
            )
            gen_label = "Genererat:" if lang == "sv" else "Generated:"
            controller_label = "Dataansvarig:" if lang == "sv" else "Data Controller:"
            legal_basis_label = "Rättslig grund:" if lang == "sv" else "Legal Basis:"
            legal_basis_text = (
                "Artikel 15 GDPR - Rätt till tillgång"
                if lang == "sv"
                else "Article 15 GDPR - Right of Access"
            )

            # --- METADATA SECTIONS ---
            writer.writerow(
                [
                    "# =========================================================================="
                ]
            )
            writer.writerow([f"# {title_header}"])
            writer.writerow(
                [f"# {gen_label} {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"]
            )
            writer.writerow([f"# {controller_label} Zebricorn Consulting AB"])
            writer.writerow([f"# {legal_basis_label} {legal_basis_text}"])
            writer.writerow(
                [
                    "# =========================================================================="
                ]
            )
            writer.writerow([])

            # --- PROFILE BLOCK ---
            profile_title = "[ANVÄNDARPROFIL]" if lang == "sv" else "[USER PROFILE]"
            writer.writerow([profile_title])
            writer.writerow(
                [
                    t("lbl_user_id_col", lang),
                    "UUID",
                    t("lbl_display_name_col", lang),
                    t("lbl_role_id_col", lang),
                ]
            )
            p = gdpr_data["profile"]
            writer.writerow(
                [
                    p.get("use_id"),
                    p.get("use_uuid"),
                    p.get("use_display_name"),
                    p.get("use_rol_id"),
                ]
            )
            writer.writerow([])

            # --- ATTENDANCE HISTORY BLOCK ---
            history_title = (
                "[TRÄNINGSHISTORIK & RSVP]"
                if lang == "sv"
                else "[WORKOUT HISTORY & RSVP]"
            )
            writer.writerow([history_title])
            writer.writerow(
                [
                    t("lbl_rsvp_id_col", lang),
                    t("lbl_session_id_col", lang),
                    t("lbl_timestamp_col", lang),
                    t("lbl_location_col", lang),
                    t("lbl_status_col", lang),
                    t("lbl_was_leader_col", lang),
                ]
            )

            yes_str = "Ja" if lang == "sv" else "Yes"
            no_str = "Nej" if lang == "en" else "No"

            for row in gdpr_data.get("history", []):
                session = row.get("workout_sessions", {}) or {}
                location = session.get("locations", {}) or {}
                writer.writerow(
                    [
                        row.get("sep_id"),
                        row.get("sep_session_id"),
                        session.get("ses_timestamp", "N/A"),
                        location.get("loc_name_swe", "N/A"),
                        row.get("sep_status"),
                        yes_str if row.get("sep_is_leader") else no_str,
                    ]
                )
            writer.writerow([])

            # --- LOGS BLOCK ---
            logs_title = (
                "[SÄKERHETSLOGGAR - ACCESS LOGS]"
                if lang == "sv"
                else "[SECURITY AUDIT - ACCESS LOGS]"
            )
            writer.writerow([logs_title])
            writer.writerow(
                [
                    t("lbl_log_id_col", lang),
                    t("lbl_timestamp_col", lang),
                    t("lbl_operation_col", lang),
                    t("lbl_target_table_col", lang),
                    t("lbl_target_row_col", lang),
                ]
            )
            for log in gdpr_data.get("logs", []):
                writer.writerow(
                    [
                        log.get("al_id"),
                        log.get("al_timestamp"),
                        log.get("al_crud_type"),
                        log.get("al_target_table"),
                        log.get("al_target_id"),
                    ]
                )

            csv_data = csv_buffer.getvalue()

            st.download_button(
                label=t("btn_gdpr_export", lang),
                data=csv_data,
                file_name=f"gdpr_extract_user_{user_id}.csv",
                mime="text/csv",
                use_container_width=True,
                key=f"btn_gdpr_active_{user_id}",
            )
        else:
            db_error = gdpr_data.get("error", "Unknown error")
            st.error(t("err_gdpr_fetch_failed", lang))
            logging.error(
                f"GDPR Extraction sequence diagnostic failure details: {db_error}"
            )

    # --- INFRASTRUCTURE DATA ASSURANCE MATRIX ---
    st.write("---")
    st.info(f"**🛡️ {t('lbl_gdpr_info_title', lang)}**")
    st.markdown(
        f"""
        <div style="font-size: 0.85rem; opacity: 0.85; line-height: 1.4;">
            <b>{t("lbl_security_storage", lang)}:</b> {t("txt_security_storage", lang)}<br><br>
            <b>{t("lbl_audit_logs", lang)}:</b> {t("txt_audit_logs", lang)}<br><br>
            <b>{t("lbl_minimization", lang)}:</b> {t("txt_minimization", lang)}
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.write("---")
