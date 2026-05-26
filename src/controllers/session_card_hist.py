import logging
from typing import Any, Dict, Optional, cast

import streamlit as st

from src.database import (
    get_supabase,  # Central JIT factory to mitigate stale connections
)
from src.lang import t


# [OPTIMIZATION]: Secure static weather rules for fallbacks (24h TTL)
@st.cache_data(ttl=86400)
def _fetch_cached_hist_weather_rule(wea_id: int) -> Optional[Dict[str, Any]]:
    """Fetches static weather metadata securely using a JIT client to safeguard context."""
    try:
        client = get_supabase()
        w_res = (
            client.table("weather_conditions")
            .select("*")
            .eq("wea_id", wea_id)
            .execute()
        )
        # Safe extraction guarding against empty lists or IndexError panics
        if w_res and w_res.data and len(w_res.data) > 0:
            first_row = w_res.data[0]
            if isinstance(first_row, dict):
                return cast(Dict[str, Any], first_row)
        return None
    except Exception as e:
        logging.error(
            f"Database error inside cached _fetch_cached_hist_weather_rule loop: {e}"
        )
        return None


def render_session_card(session: Dict[str, Any], weather: Dict[str, Any]):
    """
    Card for SESSION LIST / HISTORY.
    Uses a 2-column layout with rule-based icons, wind hazard alerts, and full i18n support.
    """
    loc = cast(Dict[str, Any], session.get("locations", {}))
    is_canceled = session.get("ses_is_canceled", False)
    lang = st.session_state.get("use_lang", "sv")

    # Presentation Layer: ID-based Emoji Mapping
    id_icon_map = {1: "☀️", 2: "☁️", 3: "🌦️", 4: "🌧️", 5: "💨", 6: "❄️", 7: "⛈️"}

    temp = str(weather.get("temperature", weather.get("temp", "--")))
    raw_wind = weather.get("wind_speed", weather.get("windspeed", None))
    wind = str(raw_wind if raw_wind is not None else "--")

    # Fetch weather metadata from relation
    db_weather: Optional[Dict[str, Any]] = session.get("weather_conditions")

    if not db_weather and session.get("ses_wea_id"):
        try:
            db_weather = _fetch_cached_hist_weather_rule(int(session["ses_wea_id"]))
        except Exception:
            pass

    # Determine icon and description strings
    if db_weather:
        wea_id = int(db_weather.get("wea_id", 2))
        icon = id_icon_map.get(wea_id, "📅")
        w_desc = db_weather.get(
            "wea_label_en" if lang == "en" else "wea_label_swe", "N/A"
        )
    else:
        legacy_desc = str(weather.get("weather_desc", weather.get("status", "Planned")))
        w_desc = legacy_desc
        legacy_upper = legacy_desc.upper()
        if "KLART" in legacy_upper or "CLEAR" in legacy_upper:
            icon = "☀️"
        elif "REGN" in legacy_upper or "RAIN" in legacy_upper:
            icon = "🌧️"
        elif "VIND" in legacy_upper or "WIND" in legacy_upper:
            icon = "💨"
        elif "SNÖ" in legacy_upper or "SNOW" in legacy_upper:
            icon = "❄️"
        else:
            icon = "📅"

    # --- RENDERING ---
    with st.container(border=True):
        if is_canceled:
            st.error(f"🚫 **{t('lbl_canceled', lang)}**")
            st.markdown(f"~~### {icon} {temp}°C~~")
            loc_name = loc.get(
                "loc_name_en" if lang == "en" else "loc_name_swe", "Unknown"
            )
            st.write(f"~~📍 **{t('lbl_location', lang)}:** {loc_name}~~")
        else:
            c1, c2 = st.columns(2)
            with c1:
                st.markdown(f"### {icon} {temp}°C")
                st.write(f"**{t('lbl_weather', lang)}:** {w_desc}")
            with c2:
                loc_name = loc.get(
                    "loc_name_en" if lang == "en" else "loc_name_swe", "Unknown"
                )
                st.write(f"📍 **{t('lbl_location', lang)}:** {loc_name}")
                st.write(f"💨 **{t('lbl_wind', lang)}:** {wind} m/s")

            # 💨 BUSINESS RULE IMPLEMENTATION: High Wind Safety Hazard Contextualization
            try:
                if raw_wind is not None and float(raw_wind) >= 10.0:
                    st.warning(t("msg_extreme_wind_alert", lang))
            except (ValueError, TypeError):
                pass
