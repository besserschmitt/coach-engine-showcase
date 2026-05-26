import json
import logging
from typing import Any, Dict, List, Optional, Sequence, cast

import streamlit as st

from src.database import get_supabase  # Central JIT factory
from src.engine import formatter
from src.lang import t


def render_gear(session: Dict[str, Any]):
    """
    Equipment/Packing list management panel.
    Synchronizes local session state with the global hardware inventory.
    """
    lang = st.session_state.get("use_lang", "sv")

    st.info(t("msg_gear_info", lang))

    # Injection of optimized touch-interface styles
    st.markdown(
        """
        <style>
        [data-testid="stCheckbox"] [data-testid="stWidgetLabel"] p { font-size: 1.2rem !important; font-weight: 500; }
        [data-testid="stCheckbox"] div[role="checkbox"] { height: 25px; width: 25px; }
        .category-header {
            background-color: #1E1E1E; padding: 5px 15px; border-radius: 5px;
            margin-top: 15px; margin-bottom: 5px; color: #FF4B4B;
            font-weight: bold; letter-spacing: 1px; text-transform: uppercase;
        }
        </style>
    """,
        unsafe_allow_html=True,
    )

    if st.session_state.get("show_gear_balloons"):
        st.balloons()
        st.session_state.show_gear_balloons = False

    ses_id = int(session.get("ses_id", 0))
    current_blob = _get_current_blob(session)
    saved_iv_ids = _extract_saved_ids(current_blob)

    st.divider()

    # Fetch inventory via JIT factory
    all_items = _get_cached_inventory()
    ld_raw = session.get("locations")
    ld = cast(Optional[Dict[str, Any]], ld_raw)
    loc_id = int(ld.get("loc_id", -1)) if ld else -1

    # Filter items based on local geography rules
    display_items = [
        i
        for i in all_items
        if int(cast(Dict[str, Any], i.get("equipment", {})).get("loc_id", -1))
        in [-1, loc_id]
        and int(i.get("iv_count", 0)) > 0
    ]

    # Sort categories alphabetically
    display_items.sort(
        key=lambda x: (
            str(cast(Dict[str, Any], x["equipment"]).get("equ_name_swe", ""))
            .strip()
            .upper(),
            str(x.get("iv_spec", "")).upper(),
        )
    )

    # Render category-grouped checkbox units
    final_list: List[Dict[str, Any]] = []

    unique_categories = sorted(
        list(
            {
                str(cast(Dict[str, Any], i["equipment"]).get("equ_name_swe", ""))
                .strip()
                .upper()
                for i in display_items
            }
        )
    )

    for cat in unique_categories:
        st.markdown(f'<div class="category-header">{cat}</div>', unsafe_allow_html=True)

        with st.container(border=True):
            cat_items = [
                x
                for x in display_items
                if str(cast(Dict[str, Any], x["equipment"]).get("equ_name_swe", ""))
                .strip()
                .upper()
                == cat
            ]

            for ci in cat_items:
                spec = str(ci.get("iv_spec", t("lbl_standard", lang)))
                iv_id = int(ci.get("iv_id", 0))
                count_avail = int(ci.get("iv_count", 0))

                for unit_idx in range(count_avail):
                    unit_key = f"gear_unit_{ses_id}_{iv_id}_{unit_idx}"

                    # [FIXED BUG]: Check status safely without mutating the source list
                    is_checked = iv_id in saved_iv_ids

                    if st.checkbox(spec, key=unit_key, value=is_checked):
                        final_list.append(
                            {"item": f"{cat} ({spec})", "count": 1, "iv_id": iv_id}
                        )

    st.info(t("msg_save_confirmation", lang))
    st.divider()

    # Commit state to the JSON blob architecture
    if st.button(
        t("btn_lock_gear", lang),
        type="primary",
        use_container_width=True,
        key=f"btn_lock_gear_{ses_id}",
    ):
        try:
            client = get_supabase()
            manual_notes = str(st.session_state.get(f"arch_manual_notes_{ses_id}", ""))
            updated_blob = formatter.update_equipment_in_blob(
                current_blob, final_list, manual_notes
            )

            client.table("workout_sessions").update({"ses_json_blob": updated_blob}).eq(
                "ses_id", ses_id
            ).execute()

            st.cache_data.clear()
            st.session_state.show_gear_balloons = True
            st.rerun()
        except Exception as e:
            st.error(t("err_save_failed", lang))
            logging.error(f"Failed to commit equipment JSON blob: {e}")


def _get_current_blob(session: Dict[str, Any]) -> Dict[str, Any]:
    raw = session.get("ses_json_blob")
    if isinstance(raw, str):
        try:
            return cast(Dict[str, Any], json.loads(raw))
        except json.JSONDecodeError:  # Only catch decoding errors
            return {}
    return cast(Dict[str, Any], raw) if isinstance(raw, dict) else {}


def _extract_saved_ids(blob: Dict[str, Any]) -> List[int]:
    comp = cast(Dict[str, Any], blob.get("components", {}))
    order = cast(Dict[str, Any], comp.get("equipment_order", {}))
    if order.get("active"):
        return [
            int(cast(Dict[str, Any], i).get("iv_id", 0))
            for i in cast(Sequence, order.get("items", []))
            if isinstance(i, dict)
        ]
    return []


@st.cache_data(ttl=86400)
def _get_cached_inventory() -> List[Dict[str, Any]]:
    try:
        client = get_supabase()
        res = (
            client.table("equipment_inventory")
            .select("*, equipment(*)")
            .eq("iv_is_active", True)
            .execute()
        )
        return cast(List[Dict[str, Any]], res.data) if res and res.data else []
    except Exception as e:
        logging.error(f"Error fetching inventory: {e}")
        return []
