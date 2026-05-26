import streamlit as st
from typing import cast, Dict, Any, List
import json
from src.lang import t


def render_workout_blob(session: Dict[str, Any]):
    """The universal render engine for workout sessions (v3.0 - Final Version)."""
    lang = st.session_state.get("use_lang", "sv")

    # 1. Fetch and sanitize the JSON blob
    blob = session.get("ses_json_blob")
    if isinstance(blob, str):
        try:
            blob = json.loads(blob)
        except:
            blob = None

    if not isinstance(blob, dict):
        st.info(t("msg_no_session", lang))
        return

    st.divider()
    comp = cast(Dict[str, Any], blob.get("components", {}))
    work = cast(Dict[str, Any], comp.get("workout", {}))

    # --- SECTION A: WORKOUT BLOCKS ---
    if work.get("active"):
        protocol = str(work.get("protocol", t("lbl_todays_session", lang)))
        st.subheader(f"⚡️🤸‍♂️ {protocol} 🧎‍♀️🔥")

        blocks = cast(List[Dict[str, Any]], work.get("blocks", []))
        for b in blocks:
            block_title = str(b.get("block_name", "Block"))
            with st.expander(f"**{block_title}**", expanded=True):
                exercises = cast(List[Dict[str, Any]], b.get("exercises", []))
                for ex in exercises:
                    # Name based on language selection
                    name = str(
                        ex.get(
                            "exe_name_en" if lang == "en" else "exe_name_swe",
                            ex.get("exe_name_swe", "Exercise"),
                        )
                    )

                    # Branding
                    author_id = int(ex.get("exe_author", 0))
                    author_name = str(ex.get("author_name", ""))
                    if author_id >= 10 and author_name:
                        name = f"{name} by 💡 {author_name.split(' ')[0]}"

                    st.markdown(f"**{name}**")

                    # --- META & MILJÖ RENDER ---
                    meta = ex.get("render_meta", {"icon": "👤", "label": "Egenvikt"})

                    # Rad 1: Utrustning/Typ (👤 eller 🔧)
                    st.caption(f"{meta['icon']} {meta['label']}")

                    # Rad 2: Geografiska förutsättningar (Miljö)
                    props = []
                    if ex.get("exe_is_standing"):
                        props.append("🧍")
                    if ex.get("exe_is_rain_safe"):
                        props.append("🌧️")
                    if ex.get("exe_hill"):
                        props.append("⛰️")
                    if ex.get("exe_staircase"):
                        props.append("🧗‍♂️")

                    if props:
                        st.markdown(" ".join(props))

                    # Simplified exercise adaptation
                    if ex.get("simplified_exercise"):
                        st.info(
                            f"{t('lbl_simplified_exercise', lang)}: {ex['simplified_exercise']}"
                        )

                    if ex.get("exe_description"):
                        st.write(
                            str(
                                ex.get(
                                    "exe_description_en"
                                    if lang == "en"
                                    else "exe_description",
                                    "",
                                )
                            )
                        )

                    st.divider()

    # --- SECTION B: COACH NOTES ---
    notes_content = comp.get("notes", comp.get("manual_notes", {}).get("content", ""))
    if notes_content:
        st.subheader(t("lbl_coach_notes", lang))
        st.info(str(notes_content))

    # --- SECTION C: EQUIPMENT LIST ---
    eq_order = cast(Dict[str, Any], comp.get("equipment_order", {}))
    if eq_order.get("active"):
        items = cast(List[Dict[str, Any]], eq_order.get("items", []))
        if len(items) > 0:
            st.subheader(t("lbl_equipment_list", lang))
            for i in items:
                st.write(f"- {i.get('count')}x {i.get('item')}")
