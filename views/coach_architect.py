import json
from typing import Any, Dict, Optional, cast

import streamlit as st

from src.database import get_equipment_name_swe, get_supabase
from src.engine import architect, formatter, rules, selector
from src.lang import t
from src.utils import sync_session_weather
from views.components.workout_view import render_workout_blob


def render_architect(session: Dict[str, Any]):
    """Renderer for the Architect tab (v4.0)."""
    lang = st.session_state.get("use_lang", "sv")
    ses_id = int(session["ses_id"])
    preview_key = f"preview_blob_{ses_id}"
    db_weather_payload_key = f"db_weather_payload_{ses_id}"

    st.info(t("msg_architect_info", lang))

    existing_notes = ""
    if session.get("ses_json_blob"):
        blob_raw = session["ses_json_blob"]
        blob_data = (
            json.loads(blob_raw)
            if isinstance(blob_raw, str)
            else cast(Dict[str, Any], blob_raw)
        )
        existing_notes = blob_data.get("components", {}).get("notes", "") or ""

    # --- 1. CONFIGURATION ---
    with st.container(border=True):
        c_proto, c_toggles = st.columns([1, 1.4])
        protocol = str(
            c_proto.selectbox(
                t("lbl_protocol", lang),
                ["Tabata", "Triplets", "EMOM", "Cherry Pick", "Manuellt pass"],
                index=0,
                key=f"arch_proto_select_{ses_id}",
            )
        )

        is_auto = protocol in ["Tabata", "Triplets", "EMOM", "Cherry Pick"]

        with c_toggles:
            st.markdown(f"**{t('lbl_levels', lang)}:**")
            lvl_1 = st.toggle(
                t("lvl_1_label", lang),
                value=True,
                disabled=not is_auto,
                key=f"arch_lvl_1_{ses_id}",
            )
            lvl_2 = st.toggle(
                t("lvl_2_label", lang),
                value=True,
                disabled=not is_auto,
                key=f"arch_lvl_2_{ses_id}",
            )
            lvl_3 = st.toggle(
                t("lvl_3_label", lang),
                value=True,
                disabled=not is_auto,
                key=f"arch_lvl_3_{ses_id}",
            )

            selected_levels = [
                l2 for i, l2 in enumerate([1, 2, 3]) if [lvl_1, lvl_2, lvl_3][i]
            ]
            st.divider()

            equ_id = session.get("ses_equ_id")
            dynamic_equ_name = ""
            if "equipment" in session and isinstance(session["equipment"], dict):
                dynamic_equ_name = str(session["equipment"].get("equ_name_swe", ""))
            elif equ_id:
                dynamic_equ_name = get_equipment_name_swe(int(equ_id))

            dynamic_equ_label = (
                f"🔧 {dynamic_equ_name}"
                if dynamic_equ_name
                else f"🔧 {t('lbl_bodyweight_only', lang)}"
            )

            st.markdown(f"**{t('lbl_equip_filter', lang)}:**")
            force_bodyweight = st.toggle(
                dynamic_equ_label,
                value=False,
                disabled=not is_auto,
                key=f"arch_force_bodyweight_{ses_id}",
            )

    # --- 2. INTERVALS & TIME ---
    config = _render_protocol_config(protocol, ses_id, lang)
    manual_notes = str(
        st.text_area(
            t("lbl_manual_notes", lang),
            value=existing_notes,
            key=f"arch_manual_notes_{ses_id}",
            placeholder=t("ph_manual_notes", lang),
        )
    )

    # --- 3. ACTION: GENERATE SUGGESTION / PREVIEW ---
    st.divider()
    if is_auto:
        # Cherry Pick features a preview verification button instead of immediate publishing
        if st.button(
            t("btn_generate_suggestion", lang),
            use_container_width=True,
            type="secondary",
            key=f"btn_gen_{ses_id}",
        ):
            with st.status(t("msg_architect_thinking", lang), expanded=True) as status:
                weather = sync_session_weather(session)
                loc_data = cast(Optional[Dict[str, Any]], session.get("locations"))

                features = {
                    "has_hill": bool(loc_data.get("loc_has_hill", False))
                    if loc_data
                    else False,
                    "has_stairs": bool(loc_data.get("loc_has_staircase", False))
                    if loc_data
                    else False,
                }

                wmo_code = int(weather.get("wmo_code", 1))
                wind_speed = float(weather.get("wind_speed", 0.0))
                wea_id = rules.calculate_weather_id(wmo_code, wind_speed)

                st.session_state[db_weather_payload_key] = {
                    "ses_wea_id": wea_id,
                    "ses_raw_weather_api_string": str(weather.get("status", "unknown")),
                }

                filtered_exercises = selector.get_filtered_exercises(
                    selected_levels,
                    [],
                    weather,
                    features,
                    force_bodyweight=force_bodyweight,
                )

                if protocol == "Cherry Pick":
                    config["all_exercises_pool"] = selector.fetch_all_active_exercises()

                structure = architect.generate_session_structure(
                    protocol, filtered_exercises, config, loc_data or {}
                )

                generated_blob = formatter.package_2_0_blob(
                    protocol
                    if protocol != "Cherry Pick"
                    else config.get("cherry_pick_protocol", "Tabata"),
                    structure,
                    config,
                    manual_notes,
                    [],
                )

                st.session_state[preview_key] = generated_blob
                status.update(
                    label=t("msg_suggestion_generated", lang),
                    state="complete",
                    expanded=False,
                )
    else:
        if st.button(
            t("btn_save_manual", lang),
            type="primary",
            use_container_width=True,
            key=f"btn_save_man_{ses_id}",
        ):
            try:
                weather = sync_session_weather(session)
                wea_id = rules.calculate_weather_id(
                    int(weather.get("wmo_code", 1)),
                    float(weather.get("wind_speed", 0.0)),
                )
                manual_blob = formatter.package_2_0_blob(
                    protocol, [], {}, manual_notes, []
                )

                client = get_supabase()
                client.table("workout_sessions").update(
                    {
                        "ses_json_blob": manual_blob,
                        "ses_wea_id": wea_id,
                        "ses_raw_weather_api_string": str(
                            weather.get("status", "unknown")
                        ),
                    }
                ).eq("ses_id", ses_id).execute()

                for k in [preview_key, db_weather_payload_key]:
                    st.session_state.pop(k, None)
                st.cache_data.clear()
                st.balloons()
                st.rerun()
            except Exception as e:
                st.error(f"{t('err_save_manual', lang)}: {e}")

    # --- 4. PREVIEW & SUMMARY ---
    if preview_key in st.session_state and protocol != "Manuellt pass":
        blob = cast(Dict[str, Any], st.session_state[preview_key])

        # Clean title without excessive framing layouts
        st.markdown(f"### 📊 {t('lbl_architect_summary', lang)}")

        meta = cast(Dict[str, Any], blob.get("metadata", {}))
        duration = meta.get("estimated_duration_min", 0)

        # Compact specification row instead of heavy st.metric card arrays
        c1, c2, c3 = st.columns([1, 1, 2])
        c1.markdown(f"**{t('lbl_protocol', lang)}:** `{protocol}`")
        c2.markdown(f"**{t('lbl_duration', lang)}:** `{duration} min`")

        # Dynamic structure evaluation depending on active architecture configurations
        timeline_str = "⏱️ Full rullning"
        if protocol == "Tabata" or (
            protocol == "Cherry Pick" and config.get("cherry_pick_protocol") == "Tabata"
        ):
            stations = config.get("num_stations", 6)
            timeline_str = f"⏱️ {stations} stationer × 8 varv (20s/10s)"
        elif protocol == "Triplets" or (
            protocol == "Cherry Pick"
            and config.get("cherry_pick_protocol") == "Triplets"
        ):
            blocks = config.get("num_blocks", 4)
            timeline_str = f"⏱️ {blocks} triplet-block × 3 min"
        elif protocol == "EMOM":
            total_m = config.get("total_minutes", 20)
            loop_s = config.get("loop_size", 4)
            timeline_str = f"⏱️ {total_m} min EMOM (Rullande {loop_s}-minutersmall)"

        c3.markdown(f"**Struktur:** *{timeline_str}*")

        st.divider()
        render_workout_blob({"ses_json_blob": blob})

        if st.button(
            t("btn_publish", lang),
            type="primary",
            use_container_width=True,
            key=f"btn_pub_{ses_id}",
        ):
            blob["components"]["notes"] = str(
                st.session_state.get(f"arch_manual_notes_{ses_id}", "")
            )
            update_payload = {"ses_json_blob": blob}
            update_payload.update(st.session_state.get(db_weather_payload_key, {}))

            client = get_supabase()
            client.table("workout_sessions").update(update_payload).eq(
                "ses_id", ses_id
            ).execute()
            st.cache_data.clear()
            st.balloons()
            st.rerun()


def _render_protocol_config(protocol: str, ses_id: int, lang: str) -> Dict[str, Any]:
    config: Dict[str, Any] = {}
    if protocol == "Manuellt pass":
        return config

    with st.container(border=True):
        if protocol == "Cherry Pick":
            chosen_map: Dict[str, Optional[int]] = {}

            c_type, c_vol = st.columns(2)
            sub_proto = c_type.selectbox(
                t("lbl_cp_select_base", lang),
                ["Tabata", "Triplets"],
                key=f"cp_sub_{ses_id}",
            )
            config["cherry_pick_protocol"] = sub_proto

            exercises = selector.fetch_all_active_exercises()
            exercises_sorted = sorted(
                exercises, key=lambda x: str(x.get("exe_name_swe", ""))
            )

            exe_options: Dict[str, Optional[int]] = {
                f"-- {t('lbl_cp_choose_exercise', lang)} --": None
            }
            for e in exercises_sorted:
                eq_id = architect._safe_int(e.get("exe_equ_id"))
                if eq_id > 0:
                    eq_name = get_equipment_name_swe(eq_id)
                    bracket_info = eq_name if eq_name else "Utrustning"
                else:
                    bracket_info = "Egenvikt"

                label = f"{e.get('exe_name_swe')} ({bracket_info})"
                exe_options[label] = int(e["exe_id"])

            if sub_proto == "Tabata":
                num_stations = int(
                    c_vol.number_input(
                        t("lbl_stations", lang), 1, 15, 6, key=f"cp_stat_{ses_id}"
                    )
                )
                config["num_stations"] = num_stations
                config["rounds_per_station"] = 8
                config["work_sec"] = 20
                config["rest_sec"] = 10
                config["transition_sec"] = 60

                weather_alert_triggered = False

                for i in range(num_stations):
                    with st.container(border=True):
                        st.markdown(f"**{t('lbl_station', lang)} {i + 1}**")
                        col_a, col_b = st.columns(2)

                        sel_a = col_a.selectbox(
                            t("lbl_cp_topping", lang),
                            options=list(exe_options.keys()),
                            key=f"cp_s_{i + 1}_a_{ses_id}",
                        )
                        sel_b = col_b.selectbox(
                            t("lbl_cp_base", lang),
                            options=list(exe_options.keys()),
                            key=f"cp_s_{i + 1}_b_{ses_id}",
                        )

                        id_a = exe_options[sel_a]
                        id_b = exe_options[sel_b]
                        chosen_map[f"station_{i + 1}_a"] = id_a
                        chosen_map[f"station_{i + 1}_b"] = id_b

                        for eid in [id_a, id_b]:
                            if eid:
                                match = next(
                                    (x for x in exercises if int(x["exe_id"]) == eid),
                                    None,
                                )
                                if match and not match.get("exe_is_standing", True):
                                    weather_alert_triggered = True

                if weather_alert_triggered:
                    st.caption(f"ℹ️ *{t('msg_cp_weather_floor_note', lang)}*")

            elif sub_proto == "Triplets":
                num_blocks = int(
                    c_vol.number_input(
                        t("lbl_blocks", lang), 1, 15, 4, key=f"cp_blk_{ses_id}"
                    )
                )
                config["num_blocks"] = num_blocks
                config["work_sec"] = 180
                config["rest_sec"] = 60

                for i in range(num_blocks):
                    with st.container(border=True):
                        st.markdown(
                            f"**{t('lbl_cp_triplet_block', lang)} {i + 1} (3 {t('lbl_minutes_short', lang)})**"
                        )
                        col1, col2, col3 = st.columns(3)

                        sel_1 = col1.selectbox(
                            f"{t('lbl_exercise', lang)} 1",
                            options=list(exe_options.keys()),
                            key=f"cp_t_{i + 1}_1_{ses_id}",
                        )
                        sel_2 = col2.selectbox(
                            f"{t('lbl_exercise', lang)} 2",
                            options=list(exe_options.keys()),
                            key=f"cp_t_{i + 1}_2_{ses_id}",
                        )
                        sel_3 = col3.selectbox(
                            f"{t('lbl_exercise', lang)} 3",
                            options=list(exe_options.keys()),
                            key=f"cp_t_{i + 1}_3_{ses_id}",
                        )

                        chosen_map[f"triplet_{i + 1}_1"] = exe_options[sel_1]
                        chosen_map[f"triplet_{i + 1}_2"] = exe_options[sel_2]
                        chosen_map[f"triplet_{i + 1}_3"] = exe_options[sel_3]

            config["chosen_exercises"] = chosen_map
            return config

        c1, c2, c3 = st.columns(3)
        if protocol == "Tabata":
            config["num_stations"] = int(
                c1.number_input(
                    t("lbl_stations", lang), 1, 15, 6, key=f"tab_stat_{ses_id}"
                )
            )
            config["rounds_per_station"] = int(
                c2.number_input(
                    t("lbl_rounds", lang), 1, 10, 8, key=f"tab_rond_{ses_id}"
                )
            )
            config["work_sec"] = int(
                c3.number_input(
                    t("lbl_work_sec", lang), 5, 60, 20, key=f"tab_work_{ses_id}"
                )
            )
            config["rest_sec"] = 10
            config["transition_sec"] = 60
        elif protocol == "Triplets":
            config["num_blocks"] = int(
                c1.number_input(
                    t("lbl_blocks", lang), 1, 15, 4, key=f"trip_blk_{ses_id}"
                )
            )
            config["work_sec"] = int(
                c2.number_input(
                    t("lbl_work_sec", lang), 30, 600, 180, key=f"trip_work_{ses_id}"
                )
            )
            config["rest_sec"] = int(
                c3.number_input(
                    t("lbl_rest_sec", lang), 10, 120, 60, key=f"trip_rest_{ses_id}"
                )
            )
        elif protocol == "EMOM":
            config["total_minutes"] = int(
                c1.number_input(
                    t("lbl_minutes", lang), 1, 60, 20, key=f"emom_min_{ses_id}"
                )
            )
            config["loop_size"] = int(
                c2.number_input(
                    "Loop-storlek (antal övningar)", 1, 10, 4, key=f"emom_loop_{ses_id}"
                )
            )
            config["work_sec"] = 60
            config["rest_sec"] = 0
    return config
