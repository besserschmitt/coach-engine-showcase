import logging
from typing import Any, Dict, Optional, cast

import streamlit as st

from src.database import (
    get_supabase,  # Central JIT factory to mitigate stale connections
)
from src.engine import rules
from src.lang import t
from src.utils import format_swedish_date, to_local_time


# [OPTIMIZATION]: Secure static weather rules for fallbacks (24h TTL)
@st.cache_data(ttl=86400)
def _fetch_cached_card_weather_rule(wea_id: int) -> Optional[Dict[str, Any]]:
    """Fetches static weather rules securely using a JIT client to safeguard connection context."""
    try:
        client = get_supabase()
        w_res = (
            client.table("weather_conditions")
            .select("*")
            .eq("wea_id", wea_id)
            .execute()
        )
        # Safe slice extraction guarding against empty lists or IndexError panics
        if w_res and w_res.data and len(w_res.data) > 0:
            first_row = w_res.data[0]
            if isinstance(first_row, dict):
                return cast(Dict[str, Any], first_row)
        return None
    except Exception as e:
        logging.error(
            f"Database error inside cached _fetch_cached_card_weather_rule loop: {e}"
        )
        return None


def render_session_card(session: Dict[str, Any], weather: Dict[str, Any]):
    """
    Session Card for the HOME SCREEN.
    Focus: Clarity, i18n support, connection resiliency, and rule-based weather warnings.
    """
    lang = st.session_state.get("use_lang", "sv")
    ses_id = int(session.get("ses_id", 0))
    is_canceled = session.get("ses_is_canceled", False)

    local_dt = to_local_time(str(session.get("ses_timestamp", "")))
    loc_data = session.get("locations", {})
    loc_name = loc_data.get(
        "loc_name_en" if lang == "en" else "loc_name_swe", "Unknown"
    )

    # [OPTIMIZATION]: Eliminate N+1 queries. Check for pre-joined participants.
    pre_joined_participants = session.get("session_participants")
    has_leader = False

    if isinstance(pre_joined_participants, list):
        has_leader = any(
            bool(p.get("sep_is_leader", False)) for p in pre_joined_participants
        )
    else:
        # Fallback live check wrapped inside a resilient try-except block
        try:
            client = get_supabase()
            lead_res = (
                client.table("session_participants")
                .select("sep_user_id")
                .eq("sep_session_id", ses_id)
                .eq("sep_is_leader", True)
                .execute()
            )
            has_leader = (
                len(lead_res.data) > 0 if (lead_res and lead_res.data) else False
            )
        except Exception as e:
            logging.error(
                f"Database error checking live leadership fallback status: {e}"
            )
            has_leader = False

    with st.container(border=True):
        if is_canceled:
            st.error(f"🚫 **{t('lbl_canceled', lang)}**")
            st.markdown(f"~~📍 **{t('lbl_location', lang)}:** {loc_name}~~")
            st.markdown(
                f"~~⏰ **{t('lbl_time', lang)}:** {format_swedish_date(local_dt)}~~"
            )
            st.caption(t("msg_session_canceled_details", lang))
        else:
            st.markdown(f"📍 **{loc_name}**")
            st.markdown(f"⏰ **{format_swedish_date(local_dt)}**")

            # ====================================================================
            # 🌤️ Presentation Layer: Data-driven Weather & i18n
            # ====================================================================
            w_temp = str(weather.get("temperature", weather.get("temp", "0.0")))
            raw_wind = weather.get("wind_speed", weather.get("windspeed", None))

            # Fetch weather rules via JOIN or fallback to cache
            db_weather: Optional[Dict[str, Any]] = session.get("weather_conditions")

            if not db_weather and session.get("ses_wea_id"):
                try:
                    db_weather = _fetch_cached_card_weather_rule(
                        int(session["ses_wea_id"])
                    )
                except Exception:
                    pass

            # Fallback for new/unsaved sessions interpreted via engine rules
            if not db_weather:
                try:
                    wmo_code = int(
                        weather.get(
                            "wmo_code",
                            weather.get("weathercode", weather.get("wmo", 1)),
                        )
                    )
                    wind_speed = float(raw_wind) if raw_wind is not None else 0.0
                    calculated_id = rules.calculate_weather_id(wmo_code, wind_speed)
                    db_weather = _fetch_cached_card_weather_rule(calculated_id)
                except Exception:
                    pass

            # Dynamic icon mapping to wea_id
            icon_mapping = {
                1: "☀️",  # Klart & Soligt
                2: "☁️",  # Molnigt & Uppehåll
                3: "🌦️",  # Lätt regn & Duggregn
                4: "🌧️",  # Kraftigt regn & Ösregn
                5: "💨",  # Hård vind & Storm
                6: "❄️",  # Snö & Vinterväglag
                7: "⛈️",  # Åska & Oväder
            }

            if db_weather:
                current_wea_id = int(db_weather.get("wea_id", 1))
                w_icon = icon_mapping.get(
                    current_wea_id, "🌡️"
                )  # Fallback to temp icon if id missing

                w_label = db_weather.get(
                    "wea_label_en" if lang == "en" else "wea_label_swe", "N/A"
                )
                st.markdown(f"{w_icon} **{w_temp}°C** ({w_label})")

                w_note = db_weather.get(
                    "wea_note_en" if lang == "en" else "wea_note_swe"
                )
                if w_note:
                    st.caption(f"💡 *{w_note}*")
            else:
                w_desc = str(
                    weather.get("weather_desc", weather.get("status", "Unknown"))
                )
                st.markdown(f"☀️ **{w_temp}°C** ({w_desc})")

            # 💨 BUSINESS RULE IMPLEMENTATION: High Wind Safety Hazard Alert
            try:
                if raw_wind is not None and float(raw_wind) >= 10.0:
                    st.warning(t("msg_extreme_wind_alert", lang))
            except (ValueError, TypeError):
                pass

            # --- LEADER STATUS ---
            st.divider()
            if not has_leader:
                st.warning(t("msg_leader_needed", lang))
            else:
                st.success(t("msg_leader_secured", lang))
