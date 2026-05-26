import copy
from typing import Any, Dict, List, Optional

from src.engine import rules
from src.engine.architect import calculate_total_duration


def _safe_int(val: Any, default: int = -1) -> int:
    """Coerces mixed database types into clean integers to safeguard structural lookups."""
    try:
        if val is None or val == "":
            return default
        return int(float(val))
    except (ValueError, TypeError):
        return default


def _get_exercise_meta(exe: Dict[str, Any]) -> Dict[str, str]:
    """
    Extracts high-level category metadata and structural iconography for UI rendering layers.
    Addresses equipment categorization safely using type-coerced IDs.
    """
    # Safeguard against implicit type variations by running index identifiers through safe coercion
    equ_id = _safe_int(exe.get("exe_equ_id"), -1)

    # 1. Bodyweight / Equipment-Free Patterns
    if equ_id in [-1, 0]:
        return {"icon": "👤", "label": "Egenvikt"}

    # 2. Environmental Geography / Fixed Infrastructure Elements
    if equ_id == 12:  # Wall / Mur
        return {
            "icon": "🧱",
            "label": exe.get("equ_name_swe") or exe.get("exe_category_swe") or "Mur",
        }
    if equ_id == 13:  # Stairs / Trappa
        return {
            "icon": "🧗",
            "label": exe.get("equ_name_swe") or exe.get("exe_category_swe") or "Trappa",
        }
    if equ_id == 17:  # Hill / Backe
        return {
            "icon": "⛰️",
            "label": exe.get("equ_name_swe") or exe.get("exe_category_swe") or "Backe",
        }

    # 3. Portable Equipment Categories (Leverages dynamic text injected inside the architect engine)
    dynamic_label = (
        exe.get("exe_category_swe") or exe.get("equ_name_swe") or "Utrustning"
    )
    return {"icon": "🔧", "label": dynamic_label}


def package_2_0_blob(
    protocol: str,
    blocks: List[Dict[str, Any]],
    config: Dict[str, Any],
    manual_notes: str,
    equipment_list: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """
    Packages and structures the entire workout session into the Coach Engine Standard (v4.0).
    Injects render_meta details into active blocks for presentation layer rendering.
    """
    workout_seconds = calculate_total_duration(protocol, config)
    total_minutes = (workout_seconds // 60) + rules.DEFAULT_WARMUP_MIN

    clean_notes = str(manual_notes).strip()

    # Process block arrays safely to inject visual rendering parameters
    processed_blocks = copy.deepcopy(blocks)
    for block in processed_blocks:
        if not isinstance(block, dict):
            continue

        exercises = block.get("exercises", [])
        if isinstance(exercises, list):
            for exe in exercises:
                # Type safeguard: ensure the active exercise instance is a dictionary before updating keys
                if isinstance(exe, dict):
                    exe["render_meta"] = _get_exercise_meta(exe)

    return {
        "version": "4.0",
        "metadata": {
            "estimated_duration_min": int(total_minutes),
            "warmup_min": rules.DEFAULT_WARMUP_MIN,
            "workout_sec": workout_seconds,
            "target_total_min": 45,
        },
        "components": {
            "workout": {
                "active": True if processed_blocks else False,
                "protocol": protocol,
                "config": config,
                "blocks": processed_blocks,
            },
            "notes": clean_notes,
            "manual_notes": {
                "active": True if clean_notes else False,
                "content": clean_notes,
            },
            "equipment_order": {
                "active": True if equipment_list else False,
                "items": equipment_list,
            },
        },
    }


def update_equipment_in_blob(
    current_blob: Dict[str, Any],
    equipment_list: List[Dict[str, Any]],
    manual_notes: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Updates session equipment data and metadata strings.
    Preserves structural integrity of existing render_meta parameters inside active blocks.
    """
    if not current_blob:
        return package_2_0_blob(
            "Manual pass", [], {}, manual_notes or "", equipment_list
        )

    new_blob = copy.deepcopy(current_blob)

    if "components" not in new_blob:
        new_blob["components"] = {}

    new_blob["components"]["equipment_order"] = {
        "active": True if equipment_list else False,
        "items": equipment_list,
    }

    if manual_notes is not None:
        clean_notes = str(manual_notes).strip()
        new_blob["components"]["notes"] = clean_notes
        new_blob["components"]["manual_notes"] = {
            "active": True if clean_notes else False,
            "content": clean_notes,
        }

    return new_blob
