import logging
from typing import Any, Dict, List, cast

import streamlit as st

from src.database import (
    get_supabase,  # Central JIT factory to mitigate stale connections
)
from src.engine import rules
from src.lang import t


def _safe_int(val: Any, default: int = -1) -> int:
    """Coerces mixed data types into clean integers to shield structural checks."""
    try:
        if val is None or val == "":
            return default
        return int(float(val))
    except (ValueError, TypeError):
        return default


# [OPTIMIZATION]: Exercise bank cached for 24 hours.
@st.cache_data(ttl=86400)
def fetch_all_active_exercises() -> List[Dict[str, Any]]:
    """Fetches active exercises with author information using a resilient JIT client."""
    try:
        client = get_supabase()
        query = (
            client.table("exercises")
            .select("*, author_info:users!exe_author(use_display_name)")
            .eq("is_blacklisted", False)
        )
        res = query.execute()
        return cast(List[Dict[str, Any]], res.data) if res and res.data else []
    except Exception as e:
        logging.error(
            f"Database error inside cached fetch_all_active_exercises loop: {e}"
        )
        return []


# [OPTIMIZATION]: Business rules for specific weather IDs cached for 24 hours.
@st.cache_data(ttl=86400)
def fetch_weather_rules(wea_id: int) -> Dict[str, Any]:
    """Retrieves and caches business logic for specific weather IDs with index safeguards."""
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
        return {}
    except Exception as e:
        logging.error(f"Database error inside cached fetch_weather_rules wrapper: {e}")
        return {}


def get_filtered_exercises(
    selected_levels: List[int],
    brought_equipment_ids: List[int],
    weather: Dict[str, Any],
    location_features: Dict[str, bool],
    force_bodyweight: bool = False,
) -> List[Dict[str, Any]]:
    """
    Selects and filters exercises based on architectural levels, available gear,
    environmental constraints, and weather-driven safety logic.
    """
    all_candidates = fetch_all_active_exercises()
    if not all_candidates:
        return []

    # Weather-ID resolution metric handling
    wmo_code = int(
        weather.get("wmo_code", weather.get("weathercode", weather.get("wmo", 1)))
    )
    wind_speed = float(weather.get("wind_speed", 0.0))
    wea_id = rules.calculate_weather_id(wmo_code, wind_speed)

    # Fetch cached environmental configurations
    weather_rules = fetch_weather_rules(wea_id)
    is_extreme_wind = wind_speed >= rules.EXTREME_WIND_THRESHOLD

    filtered_list = []
    safe_brought_ids = [
        _safe_int(eid) for eid in brought_equipment_ids if eid is not None
    ]

    for exe in all_candidates:
        if not isinstance(exe, dict):
            continue

        # --- A: LEVEL FILTER ---
        if exe.get("exe_level") not in selected_levels:
            continue

        # --- B: EQUIPMENT CONFIGURATION INTEGRITY ---
        # Normalize column key discrepancies using safe type coercion
        exe_equ_id = _safe_int(exe.get("exe_equ_id", exe.get("exe_equipment_id", -1)))

        if exe_equ_id != -1:
            if force_bodyweight:
                continue
            if safe_brought_ids and exe_equ_id not in safe_brought_ids:
                continue
            # BUSINESS RULE ENFORCEMENT: Avoid loose gear accessories during extreme wind conditions
            if is_extreme_wind and exe_equ_id not in rules.ELEVATION_IDS:
                continue

        # --- C: WEATHER & ENVIRONMENT INTELLIGENCE ---
        if weather_rules.get("wea_trigger_standing") and not exe.get(
            "exe_is_standing", True
        ):
            continue

        if weather_rules.get("wea_trigger_rain_safe") and not exe.get(
            "exe_is_rain_safe", True
        ):
            continue

        if exe.get("exe_hill") and not location_features.get("has_hill"):
            continue
        if exe.get("exe_staircase") and not location_features.get("has_stairs"):
            continue

        # --- D: DYNAMIC CREDITS ---
        author_id = _safe_int(exe.get("exe_author", 0))
        author_data = exe.get("author_info")

        if author_id != rules.SYSTEM_AUTHOR_ID and isinstance(author_data, dict):
            exe["display_credits"] = True
            exe["author_name"] = author_data.get(
                "use_display_name", t("lbl_guest_coach", "en")
            )
        else:
            exe["display_credits"] = False
            exe["author_name"] = "System"

        filtered_list.append(exe)

    return filtered_list
