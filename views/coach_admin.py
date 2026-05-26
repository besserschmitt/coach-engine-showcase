import logging
import time
from typing import Any, Dict

import streamlit as st

from src.database import (
    get_supabase,  # Central JIT factory to mitigate stale connections
)
from src.lang import t
from src.utils import get_now, to_local_time


def render_coach_admin(session: Dict[str, Any]):
    """Dynamic and internationalized status management control panel view for coaches."""
    lang = st.session_state.get("use_lang", "sv")

    st.warning(t("msg_admin_warning", lang))

    sid = session.get("ses_id")
    is_canceled = session.get("ses_is_canceled", False)
    raw_ts = session.get("ses_timestamp")

    if not sid or not raw_ts:
        st.error(t("err_no_data", lang))
        return

    sess_dt = to_local_time(str(raw_ts))
    has_started = sess_dt < get_now()

    with st.container(border=True):
        c_d, c_s, c_b = st.columns([1.8, 1.2, 1])

        with c_d:
            prefix = "🕒 " if has_started else "🗓️ "
            # Format calendar dates safely using Python standard string formatting rules
            st.markdown(
                f"{prefix}**{sess_dt.strftime('%d %b')}** kl **{sess_dt.strftime('%H:%M')}**"
            )
            st.caption(f"ID: {sid}")

        with c_s:
            status_text = (
                t("lbl_canceled", lang) if is_canceled else t("lbl_active", lang)
            )
            st.markdown(f"**{t('lbl_status', lang)}** {status_text}")

        with c_b:
            with st.popover(
                t("btn_manage", lang), use_container_width=True, key=f"pop_adm_{sid}"
            ):
                btn_label = (
                    t("btn_activate", lang) if is_canceled else t("btn_cancel", lang)
                )
                btn_type = "secondary" if is_canceled else "primary"

                if st.button(
                    btn_label,
                    key=f"adm_toggle_{sid}",
                    use_container_width=True,
                    type=btn_type,
                ):
                    try:
                        # FIXED: Resolve client via JIT factory to defend against stale socket timeouts
                        client = get_supabase()
                        client.table("workout_sessions").update(
                            {"ses_is_canceled": not is_canceled}
                        ).eq("ses_id", sid).execute()

                        # Invalidate caches globally to reflect session status immediately on the Home layout card
                        st.cache_data.clear()
                        st.balloons()
                        time.sleep(1.2)
                        st.rerun()
                    except Exception as err:
                        # FIXED: Isolate raw trace variables from end-user UI layouts
                        st.error(t("err_status_update_failed", lang))
                        logging.error(
                            f"Administrative exception encountered during state modification sequence: {err}"
                        )
