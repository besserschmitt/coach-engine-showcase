import logging
from typing import Any, Dict, List, Optional, cast

import pandas as pd
import streamlit as st

from src.database import (
    get_supabase,  # Central JIT factory to mitigate stale connections
)
from src.lang import t


# [OPTIMIZATION]: Cached for 24h to maximize app responsiveness
@st.cache_data(ttl=86400)
def get_cached_exercises() -> Optional[List[Dict[str, Any]]]:
    """Fetches the complete exercise bank alongside relational attributes via a resilient client."""
    try:
        client = get_supabase()
        res = (
            client.table("exercises")
            .select("*, equipment(equ_name_swe), users!exe_author(use_first_name)")
            .order("exe_name_swe")
            .execute()
        )
        return cast(List[Dict[str, Any]], res.data) if res and res.data else None
    except Exception as e:
        logging.error(
            f"Operational error during cached get_cached_exercises compilation: {e}"
        )
        return None


# [OPTIMIZATION]: Cached for 24h to shield baseline equipment records
@st.cache_data(ttl=86400)
def get_cached_equipment_map() -> Dict[str, int]:
    """Retrieves and maps equipment metadata strings directly onto backend sequence IDs."""
    try:
        client = get_supabase()
        equ_res = client.table("equipment").select("equ_id, equ_name_swe").execute()

        # Maintain a clean integer base mapping anchor; strings are handled downstream
        equ_map: Dict[str, int] = {}
        if equ_res and equ_res.data:
            for item in cast(List[Dict[str, Any]], equ_res.data):
                if isinstance(item, dict) and "equ_name_swe" in item:
                    equ_map[str(item["equ_name_swe"])] = int(item["equ_id"])
        return equ_map
    except Exception as e:
        logging.error(
            f"Exception encountered inside cached get_cached_equipment_map pool: {e}"
        )
        return {}


def render_exercise_bank():
    """Renders the comprehensive library system including submission engines and attribute matrix filters."""
    lang = st.session_state.get("use_lang", "sv")

    # --- INFRASTRUCTURE ADVISORY LAYOUT ---
    st.info(t("msg_bank_info", lang))

    def clear_search():
        st.session_state.bank_search_val = ""

    # 1. CONTRIBUTIONS GATING INTERFACE
    with st.expander(t("btn_contribute_exercise", lang), expanded=False):
        with st.form("new_exercise_form_v3", clear_on_submit=True):
            st.text_input(t("lbl_exe_name", lang), key="new_exe_name_swe")
            st.text_area(t("lbl_instructions", lang), key="new_exe_desc")

            c1, c2 = st.columns(2)
            raw_equ_map = get_cached_equipment_map()

            # Dynamically append localized fallback option variables safely
            bodyweight_label = t("lbl_bodyweight", lang)
            display_options = [bodyweight_label] + list(raw_equ_map.keys())

            c1.selectbox(
                t("lbl_equipment", lang),
                options=display_options,
                key="new_exe_equ",
            )
            c2.select_slider(
                t("lbl_level", lang), options=[1, 2, 3], value=2, key="new_exe_lvl"
            )

            cc1, cc2, cc3, cc4 = st.columns(4)
            cc1.checkbox(t("lbl_standing", lang), value=True, key="new_exe_stand")
            cc2.checkbox(t("lbl_rain", lang), value=True, key="new_exe_rain")
            cc3.checkbox(t("lbl_hill", lang), False, key="new_exe_hill")
            cc4.checkbox(t("lbl_wall", lang), False, key="new_exe_wall")

            if st.form_submit_button(
                t("btn_save_bank", lang), use_container_width=True
            ):
                name_swe = str(st.session_state.get("new_exe_name_swe", "")).strip()
                selected_equ_string = st.session_state.get(
                    "new_exe_equ", bodyweight_label
                )

                # Resolve true entity integer indexes accurately
                resolved_equ_id = (
                    raw_equ_map.get(selected_equ_string, -1)
                    if selected_equ_string != bodyweight_label
                    else -1
                )

                if name_swe:
                    new_data = {
                        "exe_name_swe": name_swe,
                        "exe_description": str(
                            st.session_state.get("new_exe_desc", "")
                        ),
                        "exe_equ_id": resolved_equ_id,
                        "exe_level": int(st.session_state.get("new_exe_lvl", 2)),
                        "exe_is_standing": bool(
                            st.session_state.get("new_exe_stand", True)
                        ),
                        "exe_is_rain_safe": bool(
                            st.session_state.get("new_exe_rain", True)
                        ),
                        "exe_hill": bool(st.session_state.get("new_exe_hill", False)),
                        "exe_staircase": bool(
                            st.session_state.get("new_exe_wall", False)
                        ),
                        "exe_author": int(st.session_state.get("user_id", 0)),
                    }
                    try:
                        client = get_supabase()
                        client.table("exercises").insert(new_data).execute()

                        # Invalidate memory stores globally to force visibility updates on card streams
                        st.cache_data.clear()
                        st.success(t("msg_saved", lang))
                        st.rerun()
                    except Exception as transaction_err:
                        st.error(t("err_save_failed", lang))
                        logging.error(
                            f"Exception raised during entry save transaction execution pass: {transaction_err}"
                        )

    # 2. RUNTIME DATA RETRIEVAL LAYERS
    cached_data = get_cached_exercises()
    if not cached_data:
        st.info(t("msg_bank_empty", lang))
        return

    df_exe = pd.DataFrame(cached_data)

    # Establish dynamic hardware mappings cleanly over Pandas vectorized data-frames
    equipment_header_lbl = t("lbl_equipment", lang)
    df_exe[equipment_header_lbl] = df_exe["equipment"].apply(
        lambda x: (
            x["equ_name_swe"]
            if (isinstance(x, dict) and x and "equ_name_swe" in x)
            else t("lbl_bodyweight", lang)
        )
    )

    # 3. INTERACTIVE AGGREGATION FILTERS
    c_search, c_equip = st.columns([2, 1.2])
    if "bank_search_val" not in st.session_state:
        st.session_state.bank_search_val = ""

    search = c_search.text_input(t("lbl_search_exe", lang), key="bank_search_val")
    filter_equ = c_equip.multiselect(
        t("lbl_equipment", lang),
        options=sorted(df_exe[equipment_header_lbl].unique().tolist()),
    )

    if search:
        st.button(t("btn_clear_search", lang), on_click=clear_search, type="secondary")

    mask = df_exe["exe_name_swe"].str.contains(search, case=False, na=False)
    if filter_equ:
        mask = mask & df_exe[equipment_header_lbl].isin(filter_equ)
    filtered_df = df_exe[mask]

    # 4. PRESENTATION LAYER OUTPUT RUNDOWN
    st.caption(
        f"{t('lbl_showing', lang)} {len(filtered_df)} {t('lbl_exercises', lang)}"
    )

    for _, row in filtered_df.iterrows():
        r = cast(Dict[str, Any], row.to_dict())

        # --- DYNAMIC AUTHOR ATTRIBUTION MAPPING ---
        author_id = int(r.get("exe_author", 0))
        author_name = (
            r.get("users", {}).get("use_first_name", "")
            if isinstance(r.get("users"), dict)
            else ""
        )

        # Append contribution honors if the identity context maps past standard indices
        if author_id >= 10 and author_name:
            display_name = f"{r.get('exe_name_swe', 'Namnlös')} by 🔥 {author_name}"
        else:
            display_name = str(r.get("exe_name_swe", t("lbl_nameless", lang)))

        with st.container(border=True):
            col1, col2 = st.columns([3, 1.2])
            col1.markdown(
                f"**{display_name}** *{t('lbl_level', lang)} {r.get('exe_level', 2)}*"
            )
            col2.markdown(
                f"<div style='text-align: right; color: gray; font-size: 0.85rem;'>🔧 {r[equipment_header_lbl]}</div>",
                unsafe_allow_html=True,
            )

            props = []
            if r.get("exe_is_standing"):
                props.append(f"🧍 {t('lbl_standing', lang)}")
            if r.get("exe_is_rain_safe"):
                props.append(f"🌧️ {t('lbl_rain', lang)}")
            if r.get("exe_hill"):
                props.append(f"⛰️ {t('lbl_hill', lang)}")
            if r.get("exe_staircase"):
                props.append(f"🧗‍♀️ {t('lbl_wall', lang)}")

            if props:
                st.caption(" | ".join(props))

            if r.get("exe_description"):
                with st.expander(t("lbl_instructions", lang)):
                    st.write(r.get("exe_description"))
