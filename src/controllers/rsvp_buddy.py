import logging
from typing import Any, Dict, List, Optional, cast

import streamlit as st

from src.controllers.rsvp import handle_buddy_rsvp
from src.database import (
    get_supabase,  # Central JIT factory to prevent stale connections
)
from src.lang import t


# [OPTIMIZATION]: Cache the member directory for 24 hours.
# Automatically cleared when st.cache_data.clear() is triggered upon saving/RSVP.
@st.cache_data(ttl=86400)
def _get_cached_active_buddies_list() -> List[Dict[str, Any]]:
    """Fetches all active and unlocked members from the database once per day."""
    try:
        # Fetch fresh client within the cached loop to secure connection context
        client = get_supabase()
        res = (
            client.table("users")
            .select("use_id, use_display_name")
            .eq("use_is_locked", False)
            .execute()
        )
        return cast(List[Dict[str, Any]], res.data) if res.data else []
    except Exception as e:
        logging.error(f"Database error in _get_cached_active_buddies_list: {e}")
        return []


def render_buddy_signup(
    ses_id: int,
    context: str = "upc",
    preloaded_participants: Optional[List[Dict[str, Any]]] = None,
):
    """
    Renders the 'Register a Buddy' UI with unique keys per context and full i18n support.
    Performance optimized: Reuses preloaded data to eliminate network lag.
    """
    lang = st.session_state.get("use_lang", "sv")
    unique_prefix = f"buddy_{context}_{ses_id}"

    with st.expander(t("btn_register_buddy", lang), expanded=False):
        # 1. FETCH ACTIVE MEMBERS FROM 24H CACHE
        all_users = _get_cached_active_buddies_list()
        if not all_users:
            st.info(t("msg_no_buddies", lang))
            return

        # 2. DICTATE REGISTERED IDS (Use preloaded data if passed, otherwise safe live query)
        if preloaded_participants is not None:
            registered_ids = [
                int(p.get("sep_user_id", 0)) for p in preloaded_participants
            ]
        else:
            try:
                client = get_supabase()
                part_res = (
                    client.table("session_participants")
                    .select("sep_user_id")
                    .eq("sep_session_id", ses_id)
                    .execute()
                )
                raw_parts = (
                    cast(List[Dict[str, Any]], part_res.data) if part_res.data else []
                )
                registered_ids = [int(p.get("sep_user_id", 0)) for p in raw_parts]
            except Exception as e:
                st.error(t("err_failed_to_fetch_buddies", lang))
                logging.error(
                    f"Database error in fallback lookup inside render_buddy_signup: {e}"
                )
                return

        # 3. FILTER AVAILABLE MEMBERS IN MEMORY
        available_buddies = [
            u for u in all_users if int(u.get("use_id", 0)) not in registered_ids
        ]

        if not available_buddies:
            st.info(t("msg_no_buddies", lang))
            return

        user_options = {
            str(u.get("use_display_name", "Unknown")): int(u.get("use_id", 0))
            for u in available_buddies
        }

        # Sort names alphabetically in memory for a better UX
        sorted_names = sorted(list(user_options.keys()))

        selected_name = st.selectbox(
            t("lbl_buddy_selector", lang),
            options=sorted_names,
            key=f"{unique_prefix}_select",
            label_visibility="collapsed",
            index=None,
            placeholder=t("placeholder_select_member", lang),
        )

        if selected_name:
            buddy_id = user_options[selected_name]

            if st.button(
                t("btn_book_buddy", lang),
                key=f"{unique_prefix}_btn",
                use_container_width=True,
                type="primary",
            ):
                handle_buddy_rsvp(ses_id, buddy_id)
