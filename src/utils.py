import logging
import time
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, cast

import pytz
import requests
import streamlit as st
from dateutil import parser

from src.config import IS_DEMO
from src.database import (
    get_supabase,  # Central JIT factory to mitigate stale connections
)
from src.lang import t

# --- CONFIGURATION ---
STOCKHOLM_TZ = pytz.timezone("Europe/Stockholm")
LAT = 59.19
LON = 17.75


def get_now() -> datetime:
    """Returns the current timestamp in the Stockholm/Rönninge timezone."""
    return datetime.now(STOCKHOLM_TZ)


def to_local_time(utc_dt_str: str) -> datetime:
    """Converts an ISO string from the database to local Stockholm time safely."""
    try:
        dt = parser.isoparse(utc_dt_str)
        return dt.astimezone(STOCKHOLM_TZ)
    except Exception:
        return get_now()


# ====================================================================
# 🌍 INTERNATIONALIZATION (i18n) DATE ENGINE
# ====================================================================


def get_localized_day(dt: datetime, lang: str = "sv") -> str:
    """Returns the localized name of the weekday based on the active language selection."""
    days_sv = [
        "Måndag",
        "Tisdag",
        "Onsdag",
        "Torsdag",
        "Fredag",
        "Lördag",
        "Söndag",
    ]
    days_en = [
        "Monday",
        "Tuesday",
        "Wednesday",
        "Thursday",
        "Friday",
        "Saturday",
        "Sunday",
    ]
    return days_sv[dt.weekday()] if lang == "sv" else days_en[dt.weekday()]


def get_swe_day(dt: datetime) -> str:
    """Backward compatible alias for older legacy modules."""
    return get_localized_day(dt, lang="sv")


def format_localized_date(dt: datetime) -> str:
    """Formats time, weekday, and month names dynamically based on the session language locale."""
    lang = st.session_state.get("use_lang", "sv")

    months_sv = [
        "Januari",
        "Februari",
        "Mars",
        "April",
        "Maj",
        "Juni",
        "Juli",
        "Augusti",
        "September",
        "Oktober",
        "November",
        "December",
    ]
    months_en = [
        "January",
        "February",
        "March",
        "April",
        "May",
        "June",
        "July",
        "August",
        "September",
        "October",
        "November",
        "December",
    ]

    time_str = dt.strftime("%H:%M")
    day_name = get_localized_day(dt, lang)

    if lang == "sv":
        return f"{time_str} ({day_name} {dt.day} {months_sv[dt.month - 1]})"
    else:
        return f"{time_str} ({day_name}, {months_en[dt.month - 1]} {dt.day})"


def format_swedish_date(dt: datetime) -> str:
    """Backward compatible alias to prevent UI presentation cards from crashing."""
    return format_localized_date(dt)


# ====================================================================
# 🌤️ WEATHER ENGINE & API BINDINGS
# ====================================================================


@st.cache_data(ttl=43200)  # 12-hour cache window
def get_weather_data(target_dt: Optional[datetime] = None) -> Dict[str, Any]:
    """
    Fetches real-time weather metrics with caching and graceful error fallbacks.
    Bypasses external network API calls entirely when operating inside sandbox or demo contexts.
    """
    lang = st.session_state.get("use_lang", "sv")

    # Dynamic baseline defaults anchored to central translation keys
    weather_summary = {
        "status": "mock" if IS_DEMO else "error",
        "temperature": 18.0 if IS_DEMO else 15.0,
        "wind_speed": 2.0 if IS_DEMO else 0.0,
        "weather_desc": t("lbl_mock_weather_desc", lang)
        if IS_DEMO
        else t("lbl_weather_unavailable", lang),
        "wmo_code": 0 if IS_DEMO else 1,
    }

    # ENVIRONMENT CIRCUIT BREAKER: Stop live connectivity if executing inside sandbox environments
    if IS_DEMO:
        return weather_summary

    url = f"https://api.open-meteo.com/v1/forecast?latitude={LAT}&longitude={LON}&hourly=temperature_2m,weather_code,wind_speed_10m&wind_speed_unit=ms&timezone=Europe%2FBerlin"
    response = None

    try:
        response = requests.get(url, timeout=15)
        response.raise_for_status()
        data = response.json()

        idx = 0
        if target_dt and "hourly" in data:
            local_target = target_dt.astimezone(STOCKHOLM_TZ)
            target_iso = local_target.replace(
                minute=0, second=0, microsecond=0
            ).strftime("%Y-%m-%dT%H:%M")
            if target_iso in data["hourly"]["time"]:
                idx = data["hourly"]["time"].index(target_iso)

        hourly = data.get("hourly", {})
        temp = hourly.get("temperature_2m", [15.0])[idx]
        wind = hourly.get("wind_speed_10m", [0.0])[idx]
        code = hourly.get("weather_code", [0])[idx]

        weather_map = {
            0: "Clear",
            1: "Mostly clear",
            2: "Partly cloudy",
            3: "Cloudy",
            45: "Fog",
            48: "Rime fog",
            51: "Light drizzle",
            53: "Drizzle",
            55: "Heavy drizzle",
            61: "Light rain",
            63: "Rain",
            65: "Heavy rain",
            71: "Light snow",
            73: "Snow",
            75: "Heavy snow",
            80: "Light showers",
            81: "Showers",
            82: "Heavy showers",
            95: "Thunderstorm",
            96: "Thunderstorm with hail",
            99: "Thunderstorm with heavy hail",
        }

        weather_summary.update(
            {
                "temperature": float(temp) if temp is not None else 15.0,
                "wind_speed": float(wind) if wind is not None else 0.0,
                "weather_desc": weather_map.get(code, "Variable"),
                "wmo_code": int(code) if code is not None else 1,
                "status": "ok",
            }
        )

    except requests.exceptions.HTTPError as http_err:
        if response is not None and getattr(response, "status_code", 0) == 429:
            logging.warning(
                "Weather API limit exceeded (HTTP 429 Rate Limiting triggered)."
            )
            weather_summary["weather_desc"] = t("lbl_weather_rate_limited", lang)
        else:
            logging.error(f"Weather API HTTP connection failure: {http_err}")
    except Exception as general_err:
        logging.error(f"Weather API connection exception encountered: {general_err}")

    return weather_summary


# ====================================================================
# 🔄 BATCH & JIT SYNC LAYERS
# ====================================================================


def sync_upcoming_weather(days_ahead: int = 14, force: bool = False):
    """Updates future schedule blocks and computes matching structural Weather IDs."""
    from src.engine import rules

    if IS_DEMO:
        return

    now_utc = datetime.now(pytz.UTC)
    horizon = now_utc + timedelta(days=days_ahead)
    threshold = now_utc - timedelta(hours=12)

    try:
        client = get_supabase()
        res = (
            client.table("workout_sessions")
            .select("*")
            .gte("ses_timestamp", now_utc.isoformat())
            .lte("ses_timestamp", horizon.isoformat())
            .execute()
        )

        if not res or not res.data:
            return

        sessions = cast(List[Dict[str, Any]], res.data)

        for session in sessions:
            last_fetch = session.get("ses_weather_fetched_timestamp")
            needs_update = (
                force or not last_fetch or parser.isoparse(str(last_fetch)) < threshold
            )

            if needs_update:
                ses_id = session.get("ses_id")
                ses_ts = session.get("ses_timestamp")

                if ses_id and ses_ts:
                    ses_time = parser.isoparse(str(ses_ts))
                    fresh = get_weather_data(target_dt=ses_time)

                    if fresh["status"] == "ok":
                        wea_id = rules.calculate_weather_id(
                            fresh["wmo_code"], fresh["wind_speed"]
                        )

                        client.table("workout_sessions").update(
                            {
                                "ses_weather_swe": fresh["weather_desc"],
                                "ses_temp": fresh["temperature"],
                                "ses_wind_speed": fresh["wind_speed"],
                                "ses_weather_fetched_timestamp": now_utc.isoformat(),
                                "ses_wea_id": wea_id,
                                "ses_raw_weather_api_string": fresh["weather_desc"],
                            }
                        ).eq("ses_id", ses_id).execute()
    except Exception as e:
        logging.error(
            f"Error inside background sync_upcoming_weather batch script: {e}"
        )


def sync_session_weather(session: Dict[str, Any]) -> Dict[str, Any]:
    """Just-In-Time evaluation layer for validating individual session parameters safely."""
    ses_id = session.get("ses_id")
    cache_key = f"weather_cache_{ses_id}"

    if cache_key in st.session_state:
        ts = st.session_state.get(f"{cache_key}_ts", 0)
        try:
            safe_ts = float(str(ts))
        except (ValueError, TypeError):
            safe_ts = time.time()
        if (time.time() - safe_ts) < 600:
            return cast(Dict[str, Any], st.session_state[cache_key])

    ses_ts = session.get("ses_timestamp")
    if ses_ts:
        session_dt = parser.isoparse(str(ses_ts))
        if session_dt < datetime.now(pytz.UTC) and session.get("ses_weather_swe"):
            try:
                temp_val = float(str(session.get("ses_temp", 15.0)))
            except (ValueError, TypeError):
                temp_val = 15.0

            try:
                wind_val = float(str(session.get("ses_wind_speed", 0.0)))
            except (ValueError, TypeError):
                wind_val = 0.0

            wmo_fallback = 1
            raw_weather = session.get("weather_conditions")
            if isinstance(raw_weather, dict):
                weather_dict = cast(Dict[str, Any], raw_weather)
                codes = weather_dict.get("wea_smhi_codes")
                if isinstance(codes, list) and len(codes) > 0:
                    try:
                        wmo_fallback = int(str(codes[0]))
                    except (ValueError, TypeError):
                        wmo_fallback = 1

            data = {
                "weather_desc": session.get("ses_weather_swe"),
                "temperature": temp_val,
                "wind_speed": wind_val,
                "wmo_code": wmo_fallback,
                "status": "historical_db",
            }
            st.session_state[cache_key] = data
            st.session_state[f"{cache_key}_ts"] = time.time()
            return data

    if ses_ts:
        session_dt = parser.isoparse(str(ses_ts))
        if (session_dt - datetime.now(pytz.UTC)).total_seconds() > 1209600:
            return {
                "weather_desc": "Forecast unavailable",
                "temperature": 15.0,
                "wind_speed": 0.0,
                "wmo_code": 1,
                "status": "too_far_ahead",
            }

    last_fetch = session.get("ses_weather_fetched_timestamp")
    if last_fetch:
        fetch_dt = parser.isoparse(str(last_fetch))
        if (datetime.now(pytz.UTC) - fetch_dt).total_seconds() < 43200:
            try:
                temp_val = float(str(session.get("ses_temp", 15.0)))
            except (ValueError, TypeError):
                temp_val = 15.0

            try:
                wind_val = float(str(session.get("ses_wind_speed", 0.0)))
            except (ValueError, TypeError):
                wind_val = 0.0

            wmo_upcoming = 1
            raw_upcoming_weather = session.get("weather_conditions")
            if isinstance(raw_upcoming_weather, dict):
                upcoming_dict = cast(Dict[str, Any], raw_upcoming_weather)
                up_codes = upcoming_dict.get("wea_smhi_codes")
                if isinstance(up_codes, list) and len(up_codes) > 0:
                    try:
                        wmo_upcoming = int(str(up_codes[0]))
                    except (ValueError, TypeError):
                        wmo_upcoming = 1

            data = {
                "weather_desc": session.get("ses_weather_swe"),
                "temperature": temp_val,
                "wind_speed": wind_val,
                "wmo_code": wmo_upcoming,
                "status": "db_cached",
            }
            st.session_state[cache_key] = data
            st.session_state[f"{cache_key}_ts"] = time.time()
            return data

    return get_weather_data(target_dt=parser.isoparse(str(ses_ts)) if ses_ts else None)


def ensure_weather_context() -> None:
    """Ensures weather context is initialized in the global state."""
    now = get_now()
    if "weather" not in st.session_state:
        st.session_state["weather"] = get_weather_data()
        st.session_state["weather_timestamp"] = now


# ====================================================================
# 🔒 AUDIT ENGINE
# ====================================================================


@st.cache_data(ttl=86400)
def _get_cached_audit_type_id(action_code: str) -> Optional[int]:
    """Retrieves the system index ID for a log transaction code from RAM storage safely."""
    try:
        client = get_supabase()
        res = (
            client.table("audit_log_type")
            .select("alt_id")
            .eq("alt_code", action_code)
            .execute()
        )
        # Protect logic loop against empty array mappings or Postgrest exceptions
        if res and res.data and len(res.data) > 0:
            first_row = res.data[0]
            if isinstance(first_row, dict):
                val = first_row.get("alt_id")
                if val is not None:
                    return int(str(val))
        return None
    except Exception as lookup_err:
        logging.error(
            f"Exception triggered while running cached audit identity check: {lookup_err}"
        )
        return None


def log_audit_event(
    action_code: str,
    crud_type: str,
    target_table: Optional[str] = None,
    target_id: Optional[Any] = None,
    old_payload: Optional[Dict] = None,
    new_payload: Optional[Dict] = None,
) -> None:
    """Writes a traceable administrative event directly to the audit logging ledger."""
    try:
        alt_id = _get_cached_audit_type_id(action_code)

        if alt_id is not None:
            log_entry = {
                "al_action_type_id": alt_id,
                "al_actor_user_id": st.session_state.get("user_id", 0),
                "al_crud_type": crud_type,
                "al_target_table": target_table,
                "al_target_id": str(target_id) if target_id else None,
                "al_old_payload": old_payload,
                "al_new_payload": new_payload,
            }
            client = get_supabase()
            client.table("audit_log").insert(log_entry).execute()
    except Exception as log_err:
        logging.error(f"System audit recording layer failure: {log_err}")
