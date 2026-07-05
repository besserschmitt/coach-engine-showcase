import logging
from typing import Any, Dict, List, cast

import streamlit as st

from src.database import (
    get_supabase,  # Central JIT factory to mitigate stale connections
)
from src.lang import t


def _get_current_user_id() -> int:
    """Helper function to get the correct user id from the active login session."""
    return int(st.session_state.get("user_id", 0))


def handle_rsvp(ses_id: int, status: int, is_leader: bool = False):
    """
    Handles RSVP centrally and clears the app cache immediately to prevent ghost states.
    Status: 1=Registered, 0=Not attending.

    Note: The user_id is fetched strictly from the session context to prevent parameter tampering.
    """
    lang = st.session_state.get("use_lang", "sv")

    # 🔒 SAFEGUARD: Force user_id execution from session state boundaries.
    safe_user_id = _get_current_user_id()
    if safe_user_id == 0:
        st.error(t("msg_session_expired", lang))
        return

    try:
        client = get_supabase()

        res = (
            client.table("session_participants")
            .select("sep_id, sep_status, sep_is_leader")
            .eq("sep_session_id", ses_id)
            .eq("sep_user_id", safe_user_id)  # ALWAYS use secure safe_user_id
            .execute()
        )

        data = {
            "sep_session_id": ses_id,
            "sep_user_id": safe_user_id,
            "sep_status": status,
            "sep_role_id": 3,
            "sep_is_leader": is_leader,
        }

        if res and res.data:
            participants = cast(List[Dict[str, Any]], res.data)
            if len(participants) > 0:
                first_row = cast(Dict[str, Any], participants[0])
                sep_id = first_row.get("sep_id")

                if sep_id:
                    client.table("session_participants").update(data).eq(
                        "sep_id", sep_id
                    ).execute()
        else:
            client.table("session_participants").insert(data).execute()

        st.cache_data.clear()
        st.toast(t("msg_status_synced", lang), icon="📡")
        st.rerun()

    except Exception as e:
        st.error(t("err_rsvp_failed", lang))
        logging.error(f"Database error in handle_rsvp controller: {e}")


def toggle_leadership(ses_id: int, current_status: int, current_leader_bool: bool):
    """Toggles leadership parameters for the currently authenticated profile context."""
    try:
        handle_rsvp(ses_id, status=current_status, is_leader=not current_leader_bool)
    except Exception as e:
        lang = st.session_state.get("use_lang", "sv")
        st.error(t("err_leadership_toggle_failed", lang))
        logging.error(f"Error in toggle_leadership wrapper: {e}")


def handle_buddy_rsvp(ses_id: int, target_user_id: int):
    """
    Dedicated handler for booking a buddy target profile.
    This accepts an explicit target_user_id, bypassing the session user state lock.
    Forces an INSERT or verification action with status=1 (attending) and is_leader=False.
    """
    lang = st.session_state.get("use_lang", "sv")

    if not target_user_id or target_user_id == 0:
        st.error(t("err_rsvp_failed", lang))
        return

    try:
        client = get_supabase()

        # Verify if the target buddy has already signed up via a concurrent runtime flow
        res = (
            client.table("session_participants")
            .select("sep_id")
            .eq("sep_session_id", ses_id)
            .eq("sep_user_id", target_user_id)
            .execute()
        )

        if res and res.data and len(cast(List[Dict[str, Any]], res.data)) > 0:
            st.warning(t("msg_buddy_already_registered", lang))
            return

        # Construct the execution payload
        data = {
            "sep_session_id": ses_id,
            "sep_user_id": target_user_id,
            "sep_status": 1,  # Force state validation to registered
            "sep_role_id": 3,
            "sep_is_leader": False,
        }

        client.table("session_participants").insert(data).execute()

        # Reset query cache parameters and force UI thread refreshes
        st.cache_data.clear()
        st.toast(t("msg_status_synced", lang), icon="📡")
        st.rerun()

    except Exception as e:
        st.error(t("err_rsvp_failed", lang))
        logging.error(f"Database error in handle_buddy_rsvp controller: {e}")
