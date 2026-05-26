from typing import Any, Dict, List

# --- SESSION ARCHITECTURE (Levels) ---
LEVEL_DEFINITIONS = {
    1: "Monostructural (Cardio/Simple movement)",
    2: "Hybrid Structure (Combination exercises)",
    3: "Multi-Segment/'The Gauntlet' (High complexity/Elite)",
}

# --- METRIC WEATHER THRESHOLDS (Engine Standard: m/s and degrees Celsius) ---
EXTREME_WIND_THRESHOLD = (
    10.0  # m/s (approx. 36 km/h — strong breeze, light gear becomes unstable)
)
WMO_THUNDERSTORM_CODES = [95, 96, 99]
WMO_SNOW_CODES = [71, 73, 75, 77, 85, 86]
WMO_HEAVY_RAIN_CODES = [63, 65, 81, 82]
WMO_LIGHT_RAIN_CODES = [51, 53, 55, 61, 80]

# --- TERMINOLOGY ---
ADAPTATION_TERM = "förenklad övning"

# --- EQUIPMENT LOGIC ---
MAX_EQUIPMENT_TYPES_PER_STATION = 1
MAX_EQUIPMENT_TYPES_PER_SESSION = 4
EXCLUSIVE_EQUIPMENT_KEYWORDS = ["TRX", "REP", "ROPE", "BATTLE", "STAV", "GUMMIBAND"]

# --- ENVIRONMENT PRIORITIES ---
PREFER_HILL_OVER_STATIONARY = True
PREFER_WALL_OVER_TREE = True
PRIORITIZE_ENVIRONMENT = True

# --- AUTHOR CREDITS ---
SYSTEM_AUTHOR_ID = 0
DEFAULT_WARMUP_MIN = 5

# --- ENVIRONMENT GEOGRAPHY CONFIG ---
ENV_IDS = {"MUR": 12, "TRAPPA": 13, "BACKE": 17}
ELEVATION_IDS = [12, 13]


# ====================================================================
# 🌤️ ENGINE CORE: WEATHER ID RESOLVER
# ====================================================================


def calculate_weather_id(wmo_code: int, wind_speed: float) -> int:
    """
    Maps raw metrics from the weather API (WMO code and wind speed) to
    the internal system-ID (1-7) used in the weather_conditions table.
    This decouples the application from external API providers.
    """
    # Rule 1: Thunderstorms override all
    if wmo_code in WMO_THUNDERSTORM_CODES:
        return 7

    # Rule 2: Extreme wind (Business rule: avoid light gear/floor exercises)
    if wind_speed >= EXTREME_WIND_THRESHOLD:
        return 5

    # Rule 3: Winter conditions / Slippage risk
    if wmo_code in WMO_SNOW_CODES:
        return 6

    # Rule 4: Heavy rain (Forces standing exercises)
    if wmo_code in WMO_HEAVY_RAIN_CODES:
        return 4

    # Rule 5: Light rain / Drizzle
    if wmo_code in [3, 45, 48]:  # Cloud variations mapped before base cases
        return 3 if wmo_code in WMO_LIGHT_RAIN_CODES else 2

    if wmo_code in WMO_LIGHT_RAIN_CODES:
        return 3

    # Rule 6: Cloudy / Overcast
    if wmo_code in [3, 45, 48]:
        return 2

    # Standard fallback: Clear & Sunny
    return 1


# ====================================================================
# 🛠️ HELPER FUNCTIONS
# ====================================================================


def can_share_equipment(equ_name: str) -> bool:
    """Checks if equipment can be shared or if it is exclusive."""
    if not equ_name:
        return True
    name_upper = equ_name.upper()
    return not any(k in name_upper for k in EXCLUSIVE_EQUIPMENT_KEYWORDS)


def _is_true(val: Any) -> bool:
    """Forces mixed API/database variants of truthy parameters into native boolean True or False."""
    if val is None:
        return False
    if isinstance(val, (int, float)):
        return int(val) == 1
    return str(val).lower() in ["true", "1", "t", "yes", "y"]


def get_available_env_themes(location: Dict[str, Any]) -> List[int]:
    """Returns available environment themes based on location geography attributes."""
    themes = []
    if not location:
        return themes

    # Validate hill capability (System code 17)
    if _is_true(location.get("loc_has_hill")):
        themes.append(ENV_IDS["BACKE"])

    # Validate staircase capability which unlocks both stair loops (13) and wall structures (12)
    if _is_true(location.get("loc_has_staircase")):
        themes.append(ENV_IDS["MUR"])
        themes.append(ENV_IDS["TRAPPA"])

    return themes
