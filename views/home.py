import logging
from typing import Any, Dict, cast

import streamlit as st

from src.controllers.participants import render_participant_list
from src.controllers.rsvp import handle_rsvp, toggle_leadership
from src.controllers.rsvp_buddy import render_buddy_signup
from src.controllers.session_card import render_session_card
from src.database import get_supabase
from src.lang import t
from src.utils import (
    ensure_weather_context,
    format_swedish_date,
    get_now,
    sync_session_weather,
    sync_upcoming_weather,
    to_local_time,
)
from views.components.workout_view import render_workout_blob


def show_home():
    """Main dashboard entry point for active member interactions."""
    # 1. SESSION INITIALIZATION
    user_id = st.session_state.get("user_id")
    if user_id is None:
        st.warning(t("msg_session_expired", st.session_state.get("use_lang", "sv")))
        st.stop()

    lang = st.session_state.get("use_lang", "sv")
    user_id = int(user_id)

    # Minimize redundant network synchronization
    if "weather_synced" not in st.session_state:
        sync_upcoming_weather()
        ensure_weather_context()
        st.session_state["weather_synced"] = True

    # 2. DYNAMIC GREETING
    now_local = get_now()
    user_name = st.session_state.get("user_name", t("lbl_member", lang))
    first_name = user_name.split()[0] if " " in user_name else user_name

    if now_local.hour < 10:
        greeting = t("lbl_good_morning", lang)
    elif now_local.hour < 18:
        greeting = t("lbl_hello", lang)
    else:
        greeting = t("lbl_good_evening", lang)

    st.markdown(f"### {greeting}, {first_name}! 👋")
    st.write("---")

    # 3. SESSION DATA RETRIEVAL
    try:
        client = get_supabase()
        res = (
            client.table("workout_sessions")
            .select("*, locations(*), weather_conditions(*)")
            .gte("ses_timestamp", get_now().isoformat())
            .order("ses_timestamp")
            .limit(1)
            .execute()
        )

        if not res or not res.data:
            st.info(t("msg_no_sessions", lang))
            return

        session = cast(Dict[str, Any], res.data[0])
        ses_id = int(session.get("ses_id", 0))

        # 4. STATUS BANNER
        if session.get("ses_is_canceled", False):
            dt = to_local_time(str(session.get("ses_timestamp", "")))
            st.error(
                f"🛑 **{t('lbl_session_canceled', lang)}: {format_swedish_date(dt)}**"
            )

        st.info(t("msg_home_instructions", lang))
        render_session_card(session, sync_session_weather(session))

        # 5. ENGAGEMENT
        _render_live_engagement_section(ses_id, user_id, lang)
        render_workout_blob(session)

    except Exception as e:
        logging.error(f"Error loading home dashboard: {e}")
        st.error(t("err_home_view", lang))


@st.fragment(run_every=30)
def _render_live_engagement_section(ses_id: int, user_id: int, lang: str):
    _render_home_rsvp(ses_id, user_id, lang)
    render_buddy_signup(ses_id, context="home")
    render_participant_list(ses_id)


def _render_home_rsvp(ses_id: int, user_id: int, lang: str):
    client = get_supabase()
    res = (
        client.table("session_participants")
        .select("sep_status, sep_is_leader")
        .eq("sep_session_id", ses_id)
        .eq("sep_user_id", user_id)
        .execute()
    )

    has_record = bool(res and res.data)
    user_part = cast(Dict[str, Any], res.data[0]) if has_record else {}

    status = int(user_part.get("sep_status", 0))
    is_leader = bool(user_part.get("sep_is_leader", False))
    is_attending = status in [1, 2]

    if not has_record:
        c1, c2, c3 = st.columns(3)
        if c1.button(
            t("btn_attending", lang),
            key="home_y_initial",
            use_container_width=True,
            type="primary",
        ):
            # user_id borttaget ur anropet
            handle_rsvp(ses_id, status=1, is_leader=is_leader)
        if c2.button(
            t("btn_cant_make_it", lang),
            key="home_n_initial",
            use_container_width=True,
        ):
            handle_rsvp(ses_id, status=0, is_leader=False)
        if c3.button(
            t("btn_take_crown", lang),
            key="home_l_initial",
            use_container_width=True,
        ):
            handle_rsvp(ses_id, status=1, is_leader=True)

    else:
        c1, c2 = st.columns(2)
        if not is_attending:
            if c1.button(
                t("btn_attending", lang),
                key="home_y",
                use_container_width=True,
                type="primary",
            ):
                handle_rsvp(ses_id, status=1, is_leader=is_leader)
            if c2.button(
                t("btn_take_crown", lang), key="home_l", use_container_width=True
            ):
                handle_rsvp(ses_id, status=1, is_leader=True)
        else:
            if c1.button(
                t("btn_cant_make_it", lang), key="home_n", use_container_width=True
            ):
                handle_rsvp(ses_id, status=0, is_leader=False)

            lbl = t("btn_step_down", lang) if is_leader else t("btn_take_crown", lang)
            if c2.button(lbl, key="home_lt", use_container_width=True):
                # user_id borttaget ur anropet
                toggle_leadership(
                    ses_id, current_status=status, current_leader_bool=is_leader
                )
