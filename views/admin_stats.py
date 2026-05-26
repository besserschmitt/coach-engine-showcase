import logging
from typing import Any, Dict, List, cast

import streamlit as st

from src.database import (
    get_supabase,  # Central JIT factory to mitigate stale connections
)
from src.lang import t
from src.utils import to_local_time


# [OPTIMIZATION]: Caching hero stats for 24h to protect Supabase from heavy historical queries.
@st.cache_data(ttl=86400)
def get_cached_weather_heroes() -> List[Dict[str, Any]]:
    """Fetches and aggregates historical attendance data for weather statistics using a JIT client."""
    try:
        client = get_supabase()

        user_res = (
            client.table("users")
            .select("use_id, use_first_name, use_display_name, use_is_locked")
            .gte("use_id", 10)
            .execute()
        )

        if not user_res or not user_res.data:
            return []

        raw_users = cast(List[Dict[str, Any]], user_res.data)
        users = [
            u
            for u in raw_users
            if not u.get("use_is_locked", False) and not u.get("locked", False)
        ]

        part_res = (
            client.table("session_participants")
            .select(
                "sep_user_id, sep_status, sep_is_leader, workout_sessions(ses_timestamp, ses_temp, ses_wind_speed, ses_weather_swe, ses_wea_id)"
            )
            .in_("sep_status", [1, 2])
            .execute()
        )

        raw_participations = (
            cast(List[Dict[str, Any]], part_res.data)
            if part_res and part_res.data
            else []
        )

        user_stats: Dict[int, Dict[str, Any]] = {}
        for u in users:
            if not isinstance(u, dict) or "use_id" not in u:
                continue
            u_id = int(u["use_id"])
            # Normalized all mapping keys to explicit English architectural attributes
            user_stats[u_id] = {
                "use_id": u_id,
                "first_name": str(u["use_first_name"]),
                "total_pass": 0,
                "under_10": 0,
                "bad_weather": 0,
                "over_20": 0,
                "windy": 0,
                "total_leader": 0,
                "min_temp": None,
                "max_temp": None,
                "dark_pass": 0,
            }

        BAD_WEATHER_IDS = [3, 4, 6, 7]
        WINDY_WEATHER_IDS = [5]

        for p in raw_participations:
            if not isinstance(p, dict):
                continue
            uid = p.get("sep_user_id")
            if uid is None or int(uid) not in user_stats:
                continue

            u_id = int(uid)
            user_stats[u_id]["total_pass"] += 1

            if bool(p.get("sep_is_leader", False)):
                user_stats[u_id]["total_leader"] += 1

            ws = p.get("workout_sessions")
            if isinstance(ws, dict):
                temp = ws.get("ses_temp")
                wind = ws.get("ses_wind_speed")
                ts_str = ws.get("ses_timestamp")
                desc = str(ws.get("ses_weather_swe") or "").lower()
                wea_id = (
                    int(ws["ses_wea_id"]) if ws.get("ses_wea_id") is not None else None
                )

                if temp is not None:
                    try:
                        t_float = float(temp)
                        if t_float < -10:
                            user_stats[u_id]["under_10"] += 1
                        if t_float > 20:
                            user_stats[u_id]["over_20"] += 1
                        if (
                            user_stats[u_id]["min_temp"] is None
                            or t_float < user_stats[u_id]["min_temp"]
                        ):
                            user_stats[u_id]["min_temp"] = t_float
                        if (
                            user_stats[u_id]["max_temp"] is None
                            or t_float > user_stats[u_id]["max_temp"]
                        ):
                            user_stats[u_id]["max_temp"] = t_float
                    except (ValueError, TypeError):
                        pass

                if ts_str:
                    try:
                        dt_local = to_local_time(ts_str)
                        # Dark sessions classification: Nov to Feb at or later than 17:00
                        if dt_local.month in [11, 12, 1, 2] and dt_local.hour >= 17:
                            user_stats[u_id]["dark_pass"] += 1
                    except Exception:
                        pass

                is_windy_id = (
                    wea_id in WINDY_WEATHER_IDS if wea_id is not None else False
                )
                is_windy_wind = False
                if wind is not None:
                    try:
                        if float(wind) >= 20.0:
                            is_windy_wind = True
                    except (ValueError, TypeError):
                        pass

                if is_windy_id or is_windy_wind:
                    user_stats[u_id]["windy"] += 1

                if wea_id is not None:
                    if wea_id in BAD_WEATHER_IDS:
                        user_stats[u_id]["bad_weather"] += 1
                else:
                    bad_weather_keywords = [
                        "regn",
                        "snö",
                        "duggregn",
                        "åska",
                        "slask",
                        "rain",
                        "snow",
                        "thunder",
                        "drizzle",
                    ]
                    if any(keyword in desc for keyword in bad_weather_keywords):
                        user_stats[u_id]["bad_weather"] += 1

        return list(user_stats.values())

    except Exception as e:
        logging.error(
            f"Error compiling historical analytics within get_cached_weather_heroes: {e}"
        )
        return []


def render_stats():
    """Main renderer for Weather Heroes (v3.0)."""
    lang = st.session_state.get("use_lang", "sv")

    st.info(t("msg_stats_intro", lang))

    current_user_id = st.session_state.get("user_id")
    if current_user_id is None:
        st.warning(t("msg_session_expired", lang))
        st.stop()

    all_users_stats = get_cached_weather_heroes()
    if not all_users_stats:
        st.info(t("msg_no_stats", lang))
        return

    my_id = int(current_user_id)
    my_card = next(
        (
            u
            for u in all_users_stats
            if isinstance(u, dict) and u.get("use_id") == my_id
        ),
        None,
    )
    remaining_users = sorted(
        [
            u
            for u in all_users_stats
            if isinstance(u, dict) and u.get("use_id") != my_id
        ],
        key=lambda x: str(x.get("first_name", "")).lower(),
    )

    if my_card:
        st.markdown(f"### 👤 {t('lbl_my_status', lang)}")
        _render_compact_stat_card(my_card, is_current_user=True, lang=lang)
        st.write("---")

    st.markdown(f"### 👥 {t('lbl_entire_squad', lang)}")
    for u_data in remaining_users:
        if isinstance(u_data, dict):
            _render_compact_stat_card(u_data, is_current_user=False, lang=lang)


def _render_compact_stat_card(
    u_data: Dict[str, Any], is_current_user: bool, lang: str = "sv"
):
    """Renders a compact, scannable leaderboard metric card with full internationalization."""
    first_name = str(u_data.get("first_name", "Unknown"))
    total_pass = int(u_data.get("total_pass", 0))
    total_leader = int(u_data.get("total_leader", 0))

    pass_suffix = "st" if lang == "sv" else "sessions"
    pass_style = (
        f":red[{total_pass} {pass_suffix}]"
        if total_pass == 0
        else f"**{total_pass} {pass_suffix}**"
    )
    leader_suffix = (
        f"  •  👑 {total_leader} {t('lbl_leader_small', lang)}"
        if total_leader > 0
        else ""
    )

    min_t = u_data.get("min_temp")
    max_t = u_data.get("max_temp")

    # [FIXED]: Resolved sign mismatch anomalies when printing sub-zero maximum temperature records
    if min_t is not None and max_t is not None:
        try:
            max_float = float(max_t)
            min_float = float(min_t)
            max_prefix = "+" if max_float > 0 else ""
            range_str = f"{round(min_float, 1)}°C {t('lbl_to', lang)} {max_prefix}{round(max_float, 1)}°C"
        except (ValueError, TypeError):
            range_str = "0.0°C"
    else:
        range_str = "0.0°C"

    with st.container(border=True):
        c1, c2 = st.columns([1.2, 0.8])
        with c1:
            me_badge = " 😎" if is_current_user else ""
            st.markdown(f"### **{first_name}**{me_badge}")
        with c2:
            st.markdown(f"🏃‍♂️ {t('lbl_total', lang)}: {pass_style}{leader_suffix}")

        st.markdown(
            f"""
            <div style="display: flex; justify-content: space-between; color: #808495; font-size: 0.8rem; margin-bottom: 4px;">
                <span>❄️ {t("lbl_under_10", lang)}: <b>{u_data.get("under_10", 0)}</b></span>
                <span>☀️ {t("lbl_over_20", lang)}: <b>{u_data.get("over_20", 0)}</b></span>
            </div>
            <div style="display: flex; justify-content: space-between; color: #808495; font-size: 0.8rem; margin-bottom: 4px;">
                <span>🌧️ {t("lbl_bad", lang)}: <b>{u_data.get("bad_weather", 0)}</b></span>
                <span>💨 {t("lbl_windy", lang)}: <span style="color: #FF4B4B;"><b>{u_data.get("windy", 0)}</b></span></span>
            </div>
            <div style="display: flex; justify-content: space-between; color: #808495; font-size: 0.8rem;">
                <span>🌌 {t("lbl_dark", lang)}: <b>{u_data.get("dark_pass", 0)}</b></span>
                <span>🌡️ {t("lbl_climate_range", lang)}: <b>{range_str}</b></span>
            </div>
        """,
            unsafe_allow_html=True,
        )
