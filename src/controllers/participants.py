import logging
from typing import Any, Dict, List, Optional, cast

import streamlit as st

from src.database import get_supabase  # JIT client factory to mitigate stale sockets
from src.lang import t


def render_participant_list(
    ses_id: int, preloaded_participants: Optional[List[Dict[str, Any]]] = None
):
    """
    Renders the participant list using use_first_name with full i18n support.
    Strategy: Uses preloaded data if available, otherwise performs a live lookup.
    Status: 1=Registered, 2=Checked-in, 0=Not attending.
    """
    lang = st.session_state.get("use_lang", "sv")

    # [OPTIMIZATION]: If the view has already fetched participants, avoid network lag
    if preloaded_participants is not None:
        parts = preloaded_participants
    else:
        # Fallback: Safe live lookup wrapped in a try-except block to prevent UI crashes
        try:
            client = get_supabase()
            res = (
                client.table("session_participants")
                .select("sep_status, sep_is_leader, users(use_first_name)")
                .eq("sep_session_id", ses_id)
                .execute()
            )
            parts = cast(List[Dict[str, Any]], res.data) if res.data else []
        except Exception as e:
            st.error(t("err_failed_to_fetch_participants", lang))
            logging.error(f"Database error in render_participant_list: {e}")
            return

    if not parts:
        st.caption(t("msg_no_registrations", lang))
        return

    attending: List[str] = []
    not_coming: List[str] = []

    for p in parts:
        user_info = p.get("users")
        if not isinstance(user_info, dict):
            continue

        # Use use_first_name for the 'Elittruppen' feel
        name = str(user_info.get("use_first_name", t("lbl_member", lang)))

        status = int(p.get("sep_status", 0))
        is_leader = bool(p.get("sep_is_leader", False))

        # Format name with leader crown
        display_name = f"👑 {name}" if is_leader else name

        if status in [1, 2]:
            if status == 2:
                attending.append(
                    f"✅ {display_name}"
                )  # Checkmark for checked-in status
            else:
                attending.append(display_name)
        elif status == 0:
            not_coming.append(f"❌ {display_name}")

    # --- RENDERING ---
    if attending:
        label_attending = t("lbl_attending", lang)
        st.markdown(f"**{label_attending}**: {', '.join(attending)}")

    if not_coming:
        label_not_coming = t("lbl_not_coming", lang)
        st.caption(f"**{label_not_coming}**: {', '.join(not_coming)}")
