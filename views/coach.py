import json
from datetime import timedelta
from typing import Any, Dict, List, Optional, Sequence, cast

import streamlit as st

from src.database import supabase
from src.lang import t
from src.utils import format_swedish_date, get_now, to_local_time
from views.coach_admin import render_coach_admin

# Import sub-views
from views.coach_architect import render_architect
from views.coach_exercise_bank import render_exercise_bank
from views.coach_gear import render_gear


# ⚡ [OPTIMIZATION]: Caches the session list and emoji statuses for 5 minutes.
@st.cache_data(ttl=300)
def _get_cached_future_sessions(t_now_rounded_str: str) -> Dict[str, Any]:
    """Fetches future sessions and calculates status emojis in memory."""
    res = (
        supabase.table("workout_sessions")
        .select("*, locations(*)")
        .gte("ses_timestamp", t_now_rounded_str)
        .order("ses_timestamp")
        .limit(10)
        .execute()
    )

    if not res.data or not isinstance(res.data, list):
        return {}

    options = {}
    data_list = cast(List[Dict[str, Any]], res.data)

    for s in data_list:
        is_canceled = s.get("ses_is_canceled", False)
        status_emoji = "✅"

        if is_canceled:
            status_emoji = "🚫"
        else:
            raw_blob = s.get("ses_json_blob")
            if raw_blob:
                blob: Dict[str, Any] = (
                    json.loads(raw_blob)
                    if isinstance(raw_blob, str)
                    else cast(Dict[str, Any], raw_blob)
                )
                comp = cast(Dict[str, Any], blob.get("components", {}))

                has_workout = (
                    len(cast(Sequence[Any], comp.get("workout", {}).get("blocks", [])))
                    > 0
                )
                has_material = (
                    len(
                        cast(
                            Sequence[Any],
                            comp.get("equipment_order", {}).get("items", []),
                        )
                    )
                    > 0
                )
                has_notes = bool(
                    cast(Dict[str, Any], comp.get("manual_notes", {})).get("content")
                ) or bool(s.get("ses_notes"))

                active_components = sum(
                    [int(has_workout), int(has_material), int(has_notes)]
                )

                if active_components > 1:
                    status_emoji = "📚"
                elif active_components == 1:
                    if has_workout:
                        status_emoji = "🏗️"
                    elif has_material:
                        status_emoji = "🎒"
                    elif has_notes:
                        status_emoji = "📝"

        ld = cast(Optional[Dict[str, Any]], s.get("locations"))
        lang_key = (
            "loc_name_en"
            if st.session_state.get("use_lang") == "en"
            else "loc_name_swe"
        )
        loc_name = str(ld.get(lang_key, "Unknown")) if ld is not None else "Unknown"

        raw_ts = s.get("ses_timestamp")
        date_str = (
            format_swedish_date(to_local_time(str(raw_ts)))
            if raw_ts
            else t("lbl_unknown_date", "sv")
        )

        options[f"{status_emoji} {date_str} - {loc_name}"] = s

    return options


def show_coach():
    """Main renderer for the Coach Hub (v3.0)."""
    lang = st.session_state.get("use_lang", "sv")
    user_rol_id = st.session_state.get("user_rol_id")

    if user_rol_id is None:
        st.warning(t("msg_session_expired", lang))
        st.stop()
    elif user_rol_id not in [1, 2]:
        st.error(t("msg_access_denied", lang))
        st.stop()

    try:
        now = get_now()
        t_now_rounded_str = (
            now
            - timedelta(
                minutes=now.minute % 5, seconds=now.second, microseconds=now.microsecond
            )
        ).isoformat()

        sessions = _get_cached_future_sessions(t_now_rounded_str)

        if not sessions:
            st.warning(t("msg_no_sessions_found", lang))
            return

        c1, c2 = st.columns([2, 1])
        with c1:
            selected_label = st.selectbox(
                t("lbl_select_session", lang), options=list(sessions.keys())
            )
            selected_session = cast(Dict[str, Any], sessions[selected_label])
            selected_session_id = int(selected_session.get("ses_id", 0))

        with c2:
            with st.expander(t("lbl_legend", lang), expanded=False):
                st.markdown(t("msg_legend_details", lang))

        st.write("---")

        with st.container(key=f"coach_hub_editor_flow_{selected_session_id}"):
            tab_arch, tab_gear, tab_bank, tab_admin = st.tabs(
                [
                    t("tab_architect", lang),
                    t("tab_gear", lang),
                    t("tab_exercise_bank", lang),
                    t("tab_admin", lang),
                ]
            )

            with tab_arch:
                render_architect(selected_session)
            with tab_gear:
                render_gear(selected_session)
            with tab_bank:
                render_exercise_bank()
            with tab_admin:
                render_coach_admin(selected_session)

    except Exception as e:
        st.error(f"{t('err_coach_hub', lang)}: {e}")
