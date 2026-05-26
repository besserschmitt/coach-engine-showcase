import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, cast

import pytz
import streamlit as st

from src.controllers.rsvp import handle_rsvp, toggle_leadership
from src.controllers.rsvp_buddy import render_buddy_signup

# Import cards with specific functional aliases
from src.controllers.session_card import render_session_card as render_upcoming_card
from src.controllers.session_card_hist import render_session_card as render_history_card
from src.database import fetch_all_locations, get_supabase
from src.lang import t
from src.utils import STOCKHOLM_TZ, format_swedish_date, get_now, sync_session_weather
from views.components.workout_view import render_workout_blob


@st.cache_data(ttl=3600)
def get_cached_session_history(t_now_str: str, limit: int = 20) -> List[Dict[str, Any]]:
    """Retrieves architectural history records from the databank cached by hour."""
    try:
        client = get_supabase()
        res = (
            client.table("workout_sessions")
            .select(
                "*, locations(*), weather_conditions(*), session_participants(sep_status, sep_is_leader, users(use_first_name))"
            )
            .lt("ses_timestamp", t_now_str)
            .order("ses_timestamp", desc=True)
            .limit(limit)
            .execute()
        )
        return cast(List[Dict[str, Any]], res.data) if res and res.data else []
    except Exception as e:
        logging.error(f"Failed to retrieve historical session records: {e}")
        return []


def render_sessions_tab():
    """Main rendering orchestrator for the Session Management System."""
    lang = st.session_state.get("use_lang", "sv")
    st.info(t("msg_session_admin_info", lang))

    raw_uid = st.session_state.get("user_id")
    if raw_uid is None:
        st.warning(t("msg_session_expired", lang))
        st.stop()

    current_user_id = int(raw_uid)
    current_role = int(st.session_state.get("user_rol_id", 3))

    tab_titles = [t("tab_upcoming", lang), t("tab_history", lang)]
    is_privileged = current_role in [1, 2]

    if is_privileged:
        tab_titles.append(t("tab_create_session", lang))

    tabs = st.tabs(tab_titles)

    with tabs[0]:
        _render_upcoming_fragment(current_user_id, lang)
    with tabs[1]:
        _render_history(lang)
    if is_privileged:
        with tabs[2]:
            _render_create_form(lang)


@st.fragment(run_every=30)
def _render_upcoming_fragment(current_user_id: int, lang: str):
    """Asynchronous fragment managing live session RSVP workflows."""
    try:
        client = get_supabase()
        t_limit = (get_now() - timedelta(hours=12)).isoformat()

        res = (
            client.table("workout_sessions")
            .select(
                "*, locations(*), weather_conditions(*), session_participants(sep_id, sep_user_id, sep_is_leader, sep_status, users(use_first_name))"
            )
            .gt("ses_timestamp", t_limit)
            .order("ses_timestamp")
            .execute()
        )

        if not res or not res.data:
            st.info(t("msg_no_upcoming", lang))
            return

        for s in cast(List[Dict[str, Any]], res.data):
            sid = int(s.get("ses_id", 0))
            ts_raw = str(s.get("ses_timestamp", "")).replace("Z", "+00:00")
            dt = datetime.fromisoformat(ts_raw).astimezone(STOCKHOLM_TZ)
            p_data = cast(List[Dict[str, Any]], s.get("session_participants", []))

            coming_p = [p for p in p_data if int(p.get("sep_status", 0)) in [1, 2]]
            not_coming = [p for p in p_data if int(p.get("sep_status", -1)) == 0]

            weather = sync_session_weather(s)
            label = f"📅 {format_swedish_date(dt)} ({len(coming_p)} {t('lbl_registered', lang)})"

            with st.expander(label, expanded=False):
                render_upcoming_card(s, weather)

                if coming_p:
                    st.write("---")
                    names = [
                        f"👑 {p['users']['use_first_name']}"
                        if p.get("sep_is_leader")
                        else p["users"]["use_first_name"]
                        for p in coming_p
                    ]
                    st.write(f"**{t('lbl_participants', lang)}:** " + ", ".join(names))

                if not_coming:
                    st.caption(
                        f"❌ **{t('lbl_cant_make_it', lang)}:** "
                        + ", ".join([p["users"]["use_first_name"] for p in not_coming])
                    )

                st.divider()

                my_p = next(
                    (
                        p
                        for p in p_data
                        if int(p.get("sep_user_id", 0)) == current_user_id
                    ),
                    None,
                )

                has_record = my_p is not None
                my_p_dict = my_p if has_record else {}

                current_status = int(my_p_dict.get("sep_status", 0))
                is_leader = bool(my_p_dict.get("sep_is_leader", False))
                is_attending = current_status in [1, 2]

                c_act, c_buddy = st.columns(2)
                with c_act:
                    if not has_record:
                        col_y, col_n, col_l = st.columns(3)
                        if col_y.button(
                            t("btn_attending", lang),
                            key=f"y_init_{sid}",
                            use_container_width=True,
                            type="primary",
                        ):
                            # ✅ Pylance-säkrad: current_user_id borttagen ur anropet
                            handle_rsvp(sid, status=1, is_leader=is_leader)
                        if col_n.button(
                            t("btn_cant_make_it", lang),
                            key=f"n_init_{sid}",
                            use_container_width=True,
                        ):
                            handle_rsvp(sid, status=0, is_leader=False)
                        if col_l.button(
                            t("btn_take_crown", lang),
                            key=f"l_init_{sid}",
                            use_container_width=True,
                        ):
                            handle_rsvp(sid, status=1, is_leader=True)

                    else:
                        if not is_attending:
                            col_y, col_l = st.columns(2)
                            if col_y.button(
                                t("btn_attending", lang),
                                key=f"y_{sid}",
                                use_container_width=True,
                                type="primary",
                            ):
                                handle_rsvp(sid, status=1, is_leader=is_leader)
                            if col_l.button(
                                t("btn_take_crown", lang),
                                key=f"bl_{sid}",
                                use_container_width=True,
                            ):
                                handle_rsvp(sid, status=1, is_leader=True)
                        else:
                            col_n, col_lt = st.columns(2)
                            if col_n.button(
                                t("btn_cant_make_it", lang),
                                key=f"n_{sid}",
                                use_container_width=True,
                            ):
                                handle_rsvp(sid, status=0, is_leader=False)
                            lbl = (
                                t("btn_step_down", lang)
                                if is_leader
                                else t("btn_take_crown", lang)
                            )
                            if col_lt.button(
                                lbl, key=f"lt_{sid}", use_container_width=True
                            ):
                                # ✅ Pylance-säkrad: current_user_id borttagen ur anropet
                                toggle_leadership(
                                    sid,
                                    current_status=current_status,
                                    current_leader_bool=is_leader,
                                )

                with c_buddy:
                    render_buddy_signup(sid, context="list")
                render_workout_blob(s)
    except Exception as e:
        logging.error(f"Error during upcoming session render: {e}")


def _render_history(lang: str):
    """Displays chronological historical session archives."""
    t_now_cached_string = (
        get_now().replace(minute=0, second=0, microsecond=0).isoformat()
    )
    history_data = get_cached_session_history(t_now_cached_string, limit=20)

    if not history_data:
        st.info(t("msg_no_history", lang))
        return

    for h in history_data:
        ts = str(h.get("ses_timestamp", ""))
        dt = datetime.fromisoformat(ts.replace("Z", "+00:00")).astimezone(STOCKHOLM_TZ)
        parts = cast(List[Dict[str, Any]], h.get("session_participants", []))
        coming = [p for p in parts if int(p.get("sep_status", 0)) in [1, 2]]

        weather = sync_session_weather(h)
        with st.expander(
            f"📜 {format_swedish_date(dt)} - {len(coming)} {t('lbl_participants', lang)}"
        ):
            render_history_card(h, weather)
            if coming:
                st.write("---")
                names = [
                    f"👑 {p['users']['use_first_name']}"
                    if p.get("sep_is_leader")
                    else p["users"]["use_first_name"]
                    for p in coming
                ]
                st.write(f"**{t('lbl_who_was_there', lang)}:** " + ", ".join(names))
            st.divider()
            render_workout_blob(h)


def _render_create_form(lang: str):
    """Admin-only entry point for new session creation."""
    st.subheader(t("tab_create_session", lang))
    loc_data = fetch_all_locations(lang)

    if loc_data:
        sorted_loc = sorted(loc_data, key=lambda x: x.get("loc_id", 0))
        loc_opts = {
            str(l1.get(f"loc_name_{'en' if lang == 'en' else 'swe'}")): int(
                l1.get("loc_id", 0)
            )
            for l1 in sorted_loc
        }

        with st.form("new_session_form"):
            c1, c2 = st.columns(2)
            d = c1.date_input(t("lbl_date", lang), value=datetime.now())
            t_input = c2.time_input(
                t("lbl_time", lang), value=datetime.strptime("18:00", "%H:%M").time()
            )
            sel_l = st.selectbox(t("lbl_location", lang), options=list(loc_opts.keys()))

            if st.form_submit_button(
                t("btn_save_session", lang), use_container_width=True, type="primary"
            ):
                try:
                    dt_u = (
                        pytz.timezone("Europe/Stockholm")
                        .localize(datetime.combine(d, t_input))
                        .astimezone(pytz.utc)
                        .isoformat()
                    )
                    client = get_supabase()
                    client.table("workout_sessions").insert(
                        {
                            "ses_timestamp": dt_u,
                            "ses_loc_id": loc_opts[str(sel_l)],
                            "ses_is_canceled": False,
                        }
                    ).execute()
                    st.cache_data.clear()
                    st.success(t("msg_session_created", lang))
                    st.rerun()
                except Exception as e:
                    st.error(t("err_session_save_failed", lang))
                    logging.error(f"Failed to create new session record: {e}")
