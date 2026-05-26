import random
from typing import Any, Dict, List, Optional

from src.database import get_equipment_name_swe
from src.engine.rules import MAX_EQUIPMENT_TYPES_PER_SESSION, get_available_env_themes


def _safe_int(val: Any, default: int = -1) -> int:
    """Forces values into clean integers to eliminate float/string mismatches from database layers."""
    try:
        if val is None or val == "":
            return default
        return int(float(val))
    except (ValueError, TypeError):
        return default


def _inject_equipment_name(exercise: Dict[str, Any]) -> Dict[str, Any]:
    """
    Checks if an exercise's category represents equipment or contains a valid equipment ID.
    If true, overrides the generic category name with the localized Swedish equipment name.
    """
    if not exercise:
        return exercise

    exe_copy = exercise.copy()
    equ_id = exe_copy.get("exe_equ_id")

    # Values above 0 that are not fixed structures (12=Wall, 13=Stairs, 17=Hill) are portable equipment
    is_portable_equipment = (
        equ_id and _safe_int(equ_id) > 0 and _safe_int(equ_id) not in [12, 13, 17]
    )

    # Clean character case anomalies from the database category field
    cat_swe = str(exe_copy.get("exe_category_swe", "")).strip().lower()

    if cat_swe == "utrustning" or is_portable_equipment:
        if equ_id:
            specific_name = get_equipment_name_swe(_safe_int(equ_id))
            if specific_name:
                exe_copy["exe_category_swe"] = specific_name
                exe_copy["equ_name_swe"] = specific_name

    return exe_copy


def generate_session_structure(
    protocol: str,
    filtered_exercises: List[Dict[str, Any]],
    config: Dict[str, Any],
    location: Dict[str, Any],
) -> List[Dict[str, Any]]:
    """
    Main distributor for the workout architecture (v4.0).
    Ensures structural synchronization with UI configuration keys and rule engines.
    """
    if not filtered_exercises and protocol != "Cherry Pick":
        return []

    if protocol == "Triplets":
        return _build_triplets(filtered_exercises, config.get("num_blocks", 4))

    elif protocol == "Tabata":
        return _build_tabata(
            filtered_exercises, config.get("num_stations", 6), location
        )

    elif protocol == "EMOM":
        total_mins = config.get("total_minutes", 20)
        loop_size_cfg = config.get("loop_size", 4)
        return _build_emom(
            filtered_exercises, total_mins, location, loop_size=loop_size_cfg
        )

    elif protocol == "Cherry Pick":
        sub_proto = config.get("cherry_pick_protocol", "Tabata")
        chosen_map = config.get("chosen_exercises", {})
        all_exercises = config.get("all_exercises_pool", filtered_exercises)

        if sub_proto == "Tabata":
            return _build_cherry_pick_tabata(
                chosen_map, config.get("num_stations", 6), all_exercises
            )
        elif sub_proto == "Triplets":
            return _build_cherry_pick_triplets(
                chosen_map, config.get("num_blocks", 4), all_exercises
            )

    return []


def _build_triplets(
    exercises: List[Dict[str, Any]], num_blocks: int
) -> List[Dict[str, Any]]:
    """
    Builds Triplets: 3 exercises per block, high-intensity 3-minute intervals.
    Enforces distinct equipment types within a triplet block to avoid logistical bottle-necks.
    """
    blocks = []
    available = exercises.copy()
    random.shuffle(available)

    for i in range(num_blocks):
        block_exercises: List[Dict[str, Any]] = []
        used_equipment_in_block = set()

        attempts = 0
        while (
            len(block_exercises) < 3
            and len(available) > 0
            and attempts < len(available)
        ):
            exe = available.pop(0)
            equ_id = _safe_int(exe.get("exe_equ_id"))

            if equ_id == -1 or equ_id not in used_equipment_in_block:
                block_exercises.append(_inject_equipment_name(exe))
                if equ_id != -1:
                    used_equipment_in_block.add(equ_id)
            else:
                available.append(exe)
                attempts += 1

        if len(block_exercises) < 3:
            available = exercises.copy()
            random.shuffle(available)
            while len(block_exercises) < 3 and len(available) > 0:
                exe = available.pop(0)
                block_exercises.append(_inject_equipment_name(exe))

        blocks.append(
            {
                "block_id": i + 1,
                "block_name": f"Triplet {i + 1} (3 min)",
                "protocol_meta": "10 reps per exercise, rotate continuously for 3 min",
                "exercises": block_exercises,
            }
        )
    return blocks


def _build_tabata(
    exercises: List[Dict[str, Any]], num_stations: int, location: Dict[str, Any]
) -> List[Dict[str, Any]]:
    """
    Builds Station Tabata with a strict A/B structure (Topping + Base).
    Safeguarded against equipment capacity constraints and runtime type anomalies.
    """
    available = exercises.copy()
    random.shuffle(available)

    station_themes = []
    env_themes = get_available_env_themes(location)

    for theme in env_themes:
        if len(station_themes) < num_stations:
            station_themes.append(theme)

    all_env_ids = [12, 13, 17]

    portable_ids = list(
        set(
            _safe_int(e.get("exe_equ_id"))
            for e in available
            if _safe_int(e.get("exe_equ_id")) not in ([-1] + all_env_ids)
        )
    )
    random.shuffle(portable_ids)
    session_portable_pool = portable_ids[:MAX_EQUIPMENT_TYPES_PER_SESSION]

    for p_id in session_portable_pool:
        if len(station_themes) < num_stations:
            station_themes.append(p_id)

    while len(station_themes) < num_stations:
        station_themes.append(-1)
    random.shuffle(station_themes)

    blocks = []
    for i, target in enumerate(station_themes):
        safe_target = _safe_int(target)

        theme_matches = [
            e
            for e in available
            if _safe_int(e.get("exe_equ_id")) == safe_target and safe_target != -1
        ]

        bw_matches = [e for e in available if _safe_int(e.get("exe_equ_id")) == -1]

        exe_a = (
            theme_matches[0]
            if theme_matches
            else (bw_matches[0] if bw_matches else None)
        )
        if exe_a:
            available = [e for e in available if e.get("exe_id") != exe_a.get("exe_id")]
            bw_matches = [e for e in available if _safe_int(e.get("exe_equ_id")) == -1]

        exe_b = bw_matches[0] if bw_matches else None
        if exe_b:
            available = [e for e in available if e.get("exe_id") != exe_b.get("exe_id")]

        final_exercises = []
        if exe_a:
            final_exercises.append(_inject_equipment_name(exe_a))
        if exe_b:
            final_exercises.append(_inject_equipment_name(exe_b))

        blocks.append(
            {
                "block_id": i + 1,
                "block_name": f"Station {i + 1}",
                "exercises": final_exercises,
            }
        )

    return blocks


def _build_emom(
    exercises: List[Dict[str, Any]],
    total_minutes: int,
    location: Dict[str, Any],
    loop_size: int = 4,
) -> List[Dict[str, Any]]:
    """
    Builds EMOM (Every Minute On the Minute) around a rolling template.
    Enforces rigid equipment constraints and runtime structural safety checks.
    """
    available = exercises.copy()
    random.shuffle(available)

    env_themes = get_available_env_themes(location)
    all_env_ids = [12, 13, 17]

    portable_ids = list(
        set(
            _safe_int(e.get("exe_equ_id"))
            for e in available
            if _safe_int(e.get("exe_equ_id")) not in ([-1] + all_env_ids)
        )
    )
    random.shuffle(portable_ids)
    session_portable_pool = portable_ids[:MAX_EQUIPMENT_TYPES_PER_SESSION]

    loop_themes = (env_themes + session_portable_pool + [-1, -1, -1, -1, -1])[
        :loop_size
    ]
    random.shuffle(loop_themes)

    loop_content = []
    for target_eid in loop_themes:
        safe_target = _safe_int(target_eid)
        matches = [
            e for e in available if _safe_int(e.get("exe_equ_id")) == safe_target
        ]
        if not matches:
            matches = [e for e in available if _safe_int(e.get("exe_equ_id")) == -1]

        selected_exe = matches[0] if matches else None
        if selected_exe:
            loop_content.append(_inject_equipment_name(selected_exe))
            available = [
                e for e in available if e.get("exe_id") != selected_exe.get("exe_id")
            ]

    full_schedule = []
    for minute in range(1, total_minutes + 1):
        loop_idx = (minute - 1) % loop_size
        exe = loop_content[loop_idx] if loop_idx < len(loop_content) else None
        full_schedule.append(
            {
                "block_id": minute,
                "block_name": f"Minute {minute}",
                "protocol_meta": "Start a new exercise block every full minute",
                "exercises": [exe] if exe else [],
            }
        )
    return full_schedule


def _build_cherry_pick_tabata(
    chosen_map: Dict[str, Optional[int]],
    num_stations: int,
    all_exercises: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """Constructs a customized Station Tabata structure using specifically locked user selections."""
    exe_lookup = {int(e["exe_id"]): e for e in all_exercises}
    blocks = []

    for i in range(num_stations):
        final_exercises = []
        id_a = chosen_map.get(f"station_{i + 1}_a")
        id_b = chosen_map.get(f"station_{i + 1}_b")

        if id_a and int(id_a) in exe_lookup:
            final_exercises.append(_inject_equipment_name(exe_lookup[int(id_a)]))
        if id_b and int(id_b) in exe_lookup:
            final_exercises.append(_inject_equipment_name(exe_lookup[int(id_b)]))

        blocks.append(
            {
                "block_id": i + 1,
                "block_name": f"Station {i + 1}",
                "exercises": final_exercises,
            }
        )
    return blocks


def _build_cherry_pick_triplets(
    chosen_map: Dict[str, Optional[int]],
    num_blocks: int,
    all_exercises: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """Constructs a customized Triplet block collection using explicitly selected user choices."""
    exe_lookup = {int(e["exe_id"]): e for e in all_exercises}
    blocks = []

    for i in range(num_blocks):
        final_exercises = []
        id_1 = chosen_map.get(f"triplet_{i + 1}_1")
        id_2 = chosen_map.get(f"triplet_{i + 1}_2")
        id_3 = chosen_map.get(f"triplet_{i + 1}_3")

        if id_1 and int(id_1) in exe_lookup:
            final_exercises.append(_inject_equipment_name(exe_lookup[int(id_1)]))
        if id_2 and int(id_2) in exe_lookup:
            final_exercises.append(_inject_equipment_name(exe_lookup[int(id_2)]))
        if id_3 and int(id_3) in exe_lookup:
            final_exercises.append(_inject_equipment_name(exe_lookup[int(id_3)]))

        blocks.append(
            {
                "block_id": i + 1,
                "block_name": f"Triplet {i + 1} (3 min)",
                "protocol_meta": "10 reps per exercise, rotate continuously for 3 min",
                "exercises": final_exercises,
            }
        )
    return blocks


def build_workout(
    protocol: str,
    exercises: List[Dict[str, Any]],
    config: Dict[str, Any],
    location: Dict[str, Any],
) -> List[Dict[str, Any]]:
    """Orchestrates structural engine builds safeguarding runtime execution boundaries."""
    return generate_session_structure(protocol, exercises, config, location)


def calculate_total_duration(protocol: str, config: Dict[str, Any]) -> int:
    """Calculates total workout duration in seconds for validation and UI layout synchronization."""
    if protocol == "Tabata" or (
        protocol == "Cherry Pick" and config.get("cherry_pick_protocol") == "Tabata"
    ):
        s, r, w, rest, trans = (
            config.get("num_stations", 0),
            config.get("rounds_per_station", 8),
            config.get("work_sec", 20),
            config.get("rest_sec", 10),
            config.get("transition_sec", 60),
        )
        return (s * (r * (w + rest))) + ((s - 1) * trans)
    elif protocol == "Triplets" or (
        protocol == "Cherry Pick" and config.get("cherry_pick_protocol") == "Triplets"
    ):
        b, w, r = (
            config.get("num_blocks", 0),
            config.get("work_sec", 180),
            config.get("rest_sec", 60),
        )
        return (b * w) + ((b - 1) * r)
    elif protocol == "EMOM":
        return config.get("total_minutes", 20) * 60
    return 0
