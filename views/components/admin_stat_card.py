import streamlit as st
from src.lang import t


def render_stat_card(
    first_name: str,
    display_name: str,
    total_pass: int,
    under_10: int,
    bad_weather: int,
    over_20: int,
    storm: int,
    total_leader: int,
    is_current_user: bool = False,
):
    """
    Renders a responsive statistics card with full i18n support and hardened layout.
    """

    lang = st.session_state.get("use_lang", "sv")

    # Rank logic - Internationalized
    if total_pass >= 20:
        rank = t("rank_elite_veteran", lang)
    elif total_pass >= 10:
        rank = t("rank_heavy_hitter", lang)
    elif total_pass >= 5:
        rank = t("rank_active_member", lang)
    else:
        rank = t("rank_recruit", lang)

    with st.container(border=True):
        # Top row: Name and total sessions
        c1, c2 = st.columns([2.5, 1])
        with c1:
            me_tag = t("lbl_me", lang) if is_current_user else ""
            st.markdown(f"### **{first_name}** {me_tag}")
            st.caption(f"{display_name}  •  **{rank}**")
        with c2:
            st.metric(label=t("lbl_total_sessions", lang), value=total_pass)

        st.write("---")  # Visual separator

        # Bottom row: Optimized layout for mobile devices
        sc1, sc2, sc3, sc4, sc5 = st.columns(5)

        sc1.caption("❄️ -10°C")
        sc1.markdown(f"#### **{under_10}**")

        sc2.caption("🌧️ " + t("lbl_bad_weather", lang))
        sc2.markdown(f"#### **{bad_weather}**")

        sc3.caption("☀️ +20°C")
        sc3.markdown(f"#### **{over_20}**")

        sc4.caption("💨 " + t("lbl_storm", lang))
        sc4.markdown(f"#### **{storm}**")

        sc5.caption("👑 " + t("lbl_leader_caps", lang))
        sc5.markdown(f"#### **{total_leader}**")
