import logging
from typing import Any, Dict, List, cast

import streamlit as st

from src.database import (
    get_supabase,  # Central JIT factory to mitigate stale connections
)
from src.lang import t


def _get_current_user_id() -> int:
    """Helperfunction to get the correct user id from user logged in."""
    return int(st.session_state.get("user_id", 0))


def handle_rsvp(ses_id: int, status: int, is_leader: bool = False):
    """
    Handles RSVP centrally and clears the app cache immediately to prevent ghost states.
    Status: 1=Registered, 0=Not attending.

    OBS: user_id hämtas nu strikt från sessionen, ej som argument.
    """
    lang = st.session_state.get("use_lang", "sv")

    # 🔒 SAFEGUARD: Force user_id from session.
    safe_user_id = _get_current_user_id()
    if safe_user_id == 0:
        st.error("Ingen användare inloggad.")
        return

    try:
        client = get_supabase()

        res = (
            client.table("session_participants")
            .select("sep_id")
            .eq("sep_session_id", ses_id)
            .eq("sep_user_id", safe_user_id)  # Använd ALLTID safe_user_id
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
                sep_id = participants[0].get("sep_id")
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
    """Toggles leadership for the currently logged in user."""
    try:
        handle_rsvp(ses_id, status=current_status, is_leader=not current_leader_bool)
    except Exception as e:
        lang = st.session_state.get("use_lang", "sv")
        st.error(t("err_leadership_toggle_failed", lang))
        logging.error(f"Error in toggle_leadership wrapper: {e}")


def handle_buddy_rsvp(ses_id: int, target_user_id: int):
    """
    Dedicated handler for booking a buddy.
    This accepts an explicit target_user_id, bypassing the session user lock.
    It forces an INSERT action with status=1 (attending) and is_leader=False.
    """
    lang = st.session_state.get("use_lang", "sv")

    if not target_user_id or target_user_id == 0:
        st.error(t("err_rsvp_failed", lang))
        return

    try:
        client = get_supabase()

        # check, has buddy signed in on another parallell session?
        res = (
            client.table("session_participants")
            .select("sep_id")
            .eq("sep_session_id", ses_id)
            .eq("sep_user_id", target_user_id)
            .execute()
        )

        if res and res.data and len(cast(List[Dict[str, Any]], res.data)) > 0:
            st.warning("Medlemmen är redan anmäld till detta pass.")
            return

        # create entry
        data = {
            "sep_session_id": ses_id,
            "sep_user_id": target_user_id,
            "sep_status": 1,  # Tvinga till anmäld
            "sep_role_id": 3,
            "sep_is_leader": False,
        }

        client.table("session_participants").insert(data).execute()

        # Clear and update
        st.cache_data.clear()
        st.toast(t("msg_status_synced", lang), icon="📡")
        st.rerun()

    except Exception as e:
        st.error(t("err_rsvp_failed", lang))
        logging.error(f"Database error in handle_buddy_rsvp controller: {e}")
