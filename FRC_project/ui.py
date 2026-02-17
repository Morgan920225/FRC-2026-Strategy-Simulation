"""
FRC 2026 REBUILT - The Blue Alliance Style Dashboard.

Run with: streamlit run ui.py

A consolidated, dashboard-first application with top-level tabs for 
simulation, rules, archetypes, historical data, workflow, and settings.
"""

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import random
import os
import re
import base64
from PIL import Image

from src.tba_client import TBAClient, TBAError
from src.tba_mapper import map_team_to_archetype, get_team_summary
from src.config import ARCHETYPE_DEFAULTS
from src.models import (
    AutoAction,
    StrategyPreset,
)
from src.strategy import AUTO_PRESETS, create_alliance_config
from src.stats import MonteCarloRunner

# ---------------------------------------------------------------------------
# Page Configuration
# ---------------------------------------------------------------------------
st.set_page_config(
    page_title="FRC 2026 REBUILT | The Blue Alliance Simulator",
    page_icon="🤖",
    layout="wide",
)

# ---------------------------------------------------------------------------
# Theme & State Management
# ---------------------------------------------------------------------------
if "theme" not in st.session_state:
    st.session_state.theme = "FRC Blue (TBA)"

# Theme CSS Injection
def inject_theme(theme):
    if theme == "Dark Mode":
        st.markdown("""
            <style>
            /* ===== Page & Layout ===== */
            .stApp { background-color: #0E1117; color: #FAFAFA; }
            header[data-testid="stHeader"] { background-color: #0E1117; }
            [data-testid="stSidebar"] { background-color: #161B22; }
            [data-testid="stSidebar"] * { color: #FAFAFA !important; }
            [data-testid="stSidebar"] hr { border-color: #3E4147; }
            
            /* ===== Text & Headers ===== */
            .stMarkdown, .stMarkdown p, .stMarkdown li, .stMarkdown h1, .stMarkdown h2, .stMarkdown h3 { color: #FAFAFA !important; }
            .stCaptionContainer, .stCaption { color: #B0B0B0 !important; }
            [data-testid="stMetricLabel"] { color: #FAFAFA !important; }
            [data-testid="stMetricValue"] { color: #FAFAFA !important; }
            
            /* ===== Inputs & Selectboxes & Selection Fix ===== */
            .stSelectbox label, .stNumberInput label, .stTextInput label, .stSlider label, .stRadio label { color: #FAFAFA !important; }
            
            /* Aggressive Selectbox Overrides */
            div[data-baseweb="select"] > div:first-child { background-color: #262730 !important; color: #FAFAFA !important; border: 1px solid #4A4A4A; }
            div[data-baseweb="popover"] { background-color: #1E2127 !important; color: #FAFAFA !important; }
            div[data-baseweb="menu"] { background-color: #1E2127 !important; }
            ul[data-baseweb="menu"] { background-color: #1E2127 !important; }
            li[data-baseweb="option"] { color: #FAFAFA !important; }
            
            /* Input Fields */
            div[data-baseweb="input"] { background-color: #262730 !important; color: #FAFAFA !important; border: 1px solid #4A4A4A; }
            div[data-baseweb="input"] > div { background-color: #262730 !important; color: #FAFAFA !important; }
            input[type="text"], input[type="number"] { color: #FAFAFA !important; caret-color: #FAFAFA !important; }
            
            /* ===== Tabs & Expanders ===== */
            
            /* ===== Tabs & Expanders ===== */
            button[data-baseweb="tab"] { color: #FAFAFA !important; }
            button[data-baseweb="tab"] p { color: #FAFAFA !important; }
            .stExpander { background-color: #1E2127; border-color: #3E4147; }
            .stExpander summary { color: #FAFAFA !important; }
            .stExpander summary span { color: #FAFAFA !important; }
            
            /* ===== Tables & Logic ===== */
            [data-testid="stDataFrame"] { background-color: #1E2127; }
            [data-testid="stGraphVizChart"] text { fill: #FAFAFA !important; }
            
            /* ===== Dividers ===== */
            hr { border-color: #3E4147 !important; }
            
            /* ===== Alerts & Notifications ===== */
            [data-testid="stNotification"], [data-testid="stAlert"] { background-color: #1E2127 !important; border: 1px solid #3E4147; }
            [data-testid="stNotification"] p, [data-testid="stAlert"] p { color: #FAFAFA !important; }
            [data-testid="stAlert"] [data-testid="stMarkdownContainer"] { color: #FAFAFA !important; }
            </style>
        """, unsafe_allow_html=True)
    elif theme == "High Contrast":
        st.markdown("""
            <style>
            .stApp { background-color: #000000; color: #FFFF00; }
            [data-testid="stSidebar"] { background-color: #000000; border-right: 2px solid #FFFF00; }
            [data-testid="stSidebar"] * { color: #FFFF00 !important; }
            .stMarkdown, .stMarkdown p, .stMarkdown h1, .stMarkdown h2, .stMarkdown h3 { color: #FFFF00 !important; }
            .stMetricLabel, .stMetricValue { color: #FFFF00 !important; }
            .stButton>button { border: 2px solid #FFFF00; color: #FFFF00; background-color: #000000; }
            button[data-baseweb="tab"] p { color: #FFFF00 !important; }
            .stSelectbox label, .stNumberInput label, .stTextInput label { color: #FFFF00 !important; }
            [data-baseweb="select"] > div { background-color: #000000 !important; border: 1px solid #FFFF00; }
            [data-baseweb="input"] { background-color: #000000 !important; border: 1px solid #FFFF00; }
            [data-baseweb="input"] input { color: #FFFF00 !important; -webkit-text-fill-color: #FFFF00 !important; }
            
            /* ===== Alerts ===== */
            [data-testid="stNotification"], [data-testid="stAlert"] { background-color: #000000 !important; border: 2px solid #FFFF00; color: #FFFF00 !important; }
            [data-testid="stNotification"] p, [data-testid="stAlert"] p { color: #FFFF00 !important; }
            [data-testid="stAlert"] [data-testid="stMarkdownContainer"] { color: #FFFF00 !important; }
            </style>
        """, unsafe_allow_html=True)

inject_theme(st.session_state.theme)

def get_plotly_template():
    if st.session_state.theme == "Dark Mode" or st.session_state.theme == "High Contrast":
        return "plotly_dark"
    return "plotly_white"

# ---------------------------------------------------------------------------
# Constants & Helpers
# ---------------------------------------------------------------------------
ARCHETYPES = list(ARCHETYPE_DEFAULTS.keys())
STRATEGIES = [p.value for p in StrategyPreset]

ARCHETYPE_LABELS = {
    "elite_turret": "Elite Turret",
    "elite_multishot": "Elite Multishot",
    "strong_scorer": "Strong Scorer",
    "everybot": "Everybot",
    "kitbot_plus": "KitBot+",
    "kitbot_base": "KitBot Base",
    "defense_bot": "Defense Bot",
}

STRATEGY_LABELS = {
    "full_offense": "Full Offense",
    "2_score_1_defend": "2 Score + 1 Defend",
    "1_score_2_defend": "1 Score + 2 Defend",
    "deny_and_score": "Deny & Score",
    "surge": "Surge",
}

STRATEGY_DETAILS = {
    "full_offense": "Maximum aggression. All 3 robots focus on scoring cycles when their Hub is active. During inactive shifts, they stockpile fuel to prepare for the next 'Active' window. Best for high-tier alliances with strong scoring reliability.",
    "2_score_1_defend": "Balanced approach. Two robots handle all scoring, while the third robot crosses the field to harass the opponent's best scorer. Effective for slowing down elite teams.",
    "1_score_2_defend": "Defensive lockdown. Focuses all scoring through one elite robot while the other two play heavy defense or neutral zone denial. High risk if the primary scorer fails.",
    "deny_and_score": "Resource denial. One robot camps the Neutral Zone during inactive shifts to 'starve' the opponent of fuel, while others stockpile at the Outposts.",
    "surge": "Burst-heavy. Entire alliance stockpiles at the Outpost during inactive shifts and converges for a massive 3-robot 'dump' the moment the Hub activates. Depletes field fuel rapidly."
}

STRATEGY_TIPS = {
    "full_offense": "Best used when all three robots have high accuracy and the opponent lacks dedicated defenders.",
    "2_score_1_defend": "Assign your fastest, most agile robot to harass the opponent's primary 'Elite' turret scorer.",
    "1_score_2_defend": "Effective if you have one 'super-bot' and two partners with broken or low-efficiency intakes.",
    "deny_and_score": "Crucial in low-fuel matches where starving the opponent's Neutral Zone access can decide the game.",
    "surge": "All 3 robots must fire simultaneously at the start of the active shift to maximize the burst bonus."
}

AUTO_PRESET_LABELS = {
    "all_score": "All Score Fuel",
    "2_score_1_climb": "2 Score + 1 Climb L1",
    "2_score_1_disrupt": "2 Score + 1 Disrupt",
    "1_score_1_climb_1_disrupt": "1 Score + 1 Climb + 1 Disrupt",
}

# ---------------------------------------------------------------------------
# Sidebar - Global Configuration
# ---------------------------------------------------------------------------
# TBA API Key
if "tba_api_key" not in st.session_state:
    st.session_state.tba_api_key = ""

st.sidebar.header("🔑 TBA API Configuration")
tba_key = st.sidebar.text_input(
    "The Blue Alliance API Key",
    type="password",
    value=st.session_state.tba_api_key,
    key="tba_api_key_input",
    help="Enter your TBA API key to access live event data. Get a free key at: https://www.thebluealliance.com/account"
)

# Update session state
if tba_key:
    st.session_state.tba_api_key = tba_key
    st.sidebar.success("✅ API Key Set")
else:
    st.sidebar.info("ℹ️ [Get API Key](https://www.thebluealliance.com/account)")

st.sidebar.divider()

st.sidebar.header("Alliance Configuration")

# Default: Quick Mode is always active
# Custom mode is behind a checkbox
use_custom = st.sidebar.checkbox(
    "🔧 Use Custom Subsystems",
    value=False,
    key="use_custom_mode",
    help="Enable manual tuning of each robot's subsystems instead of using archetype presets."
)
is_custom = use_custom

def _build_custom_robot(prefix, robot_num, base_archetype_key):
    st.sidebar.markdown(f"**{prefix} Robot {robot_num}**")
    base = st.sidebar.selectbox(f"Base for R{robot_num}", ARCHETYPES, index=ARCHETYPES.index(base_archetype_key), format_func=lambda x: ARCHETYPE_LABELS[x], key=f"{prefix.lower()}_q1_c{robot_num}") 
    d = ARCHETYPE_DEFAULTS[base]
    
    with st.sidebar.expander(f"R{robot_num} Subsystems"):
        storage = st.slider("Storage Cap", 1, 30, d.get("storage_capacity", 10), help="Max fuel pieces. High capacity allows for long 'burst' scoring (scoring many points at once) but increases the time spent in the 'Intake' phase. Large stockpiles are vulnerable to being defended.", key=f"{prefix.lower()}_c{robot_num}_cap")
        acc = st.slider("Accuracy (%)", 30, 100, int(d.get("accuracy", 0.5) * 100), help="Probability of a shot scoring in an active Hub. Higher accuracy directly correlates to higher score per cycle. Accuracy is penalized if an opponent is defending you.", key=f"{prefix.lower()}_c{robot_num}_acc")
        rate = st.slider("Shoot Rate (f/s)", 1.0, 15.0, float(d.get("shoot_rate", 5.0)), help="Speed of launching fuel. Faster rates are critical for strategies like 'Surge' where you need to dump your entire storage in the limited Hub activation window.", key=f"{prefix.lower()}_c{robot_num}_rate")
        climb = st.selectbox("Climb Target", [0, 1, 2, 3], index=d.get("climb_level", 0), help="Target level for endgame. Level 3 (30 pts) is the highest but hardest. Level 1 (10 pts) is reliable. Higher targets take longer to attempt and have lower success percentages.", key=f"{prefix.lower()}_c{robot_num}_climb")
        climb_start = st.slider("Climb Start (s)", 0, 30, int(d.get("climb_start_time", 10)), help="Match time remaining when the robot stops scoring and moves to the Tower. Starting too late (e.g. 2s) might cause a 'Fail' if the climb duration exceeds time. Starting too early (e.g. 25s) guarantees points but loses valuable scoring time.", key=f"{prefix.lower()}_c{robot_num}_cstart")
        
    return {"base": base, "storage_capacity": storage, "accuracy": acc/100.0, "shoot_rate": rate, "climb_target": climb, "climb_start_time": climb_start}

def _build_quick_alliance(prefix, color_divider, default_indices, strat_key):
    st.sidebar.subheader(f"{prefix} Alliance", divider=color_divider)

    # Set default values if keys don't exist (first render)
    keys = [f"{prefix.lower()}_q1", f"{prefix.lower()}_q2", f"{prefix.lower()}_q3"]
    for i, key in enumerate(keys):
        if key not in st.session_state:
            st.session_state[key] = ARCHETYPES[default_indices[i]]

    a1 = st.sidebar.selectbox(
        f"{prefix} R1", ARCHETYPES,
        format_func=lambda x: ARCHETYPE_LABELS[x],
        key=f"{prefix.lower()}_q1"
    )
    a2 = st.sidebar.selectbox(
        f"{prefix} R2", ARCHETYPES,
        format_func=lambda x: ARCHETYPE_LABELS[x],
        key=f"{prefix.lower()}_q2"
    )
    a3 = st.sidebar.selectbox(
        f"{prefix} R3", ARCHETYPES,
        format_func=lambda x: ARCHETYPE_LABELS[x],
        key=f"{prefix.lower()}_q3"
    )

    # Set default strategy and auto plan if they don't exist
    if strat_key not in st.session_state:
        st.session_state[strat_key] = STRATEGIES[0]
    auto_key = f"{prefix.lower()}_auto"
    if auto_key not in st.session_state:
        st.session_state[auto_key] = list(AUTO_PRESET_LABELS.keys())[0]

    strat = st.sidebar.selectbox(
        f"{prefix} Strategy", STRATEGIES,
        format_func=lambda x: STRATEGY_LABELS[x],
        key=strat_key
    )
    auto_preset = st.sidebar.selectbox(
        f"{prefix} Auto Plan", list(AUTO_PRESET_LABELS.keys()),
        format_func=lambda x: AUTO_PRESET_LABELS[x],
        key=f"{prefix.lower()}_auto"
    )

    return [a1, a2, a3], strat, auto_preset

# Randomize button MUST come before alliance building
randomize_clicked = st.sidebar.button(
    "🎲 Randomize Alliances",
    help="Randomly shuffle archetype selections for quick testing",
    use_container_width=True
)

if randomize_clicked:
    if not is_custom:
        # Directly set widget keys to randomized values
        # This overwrites Streamlit's internal widget state correctly
        st.session_state.red_q1 = random.choice(ARCHETYPES)
        st.session_state.red_q2 = random.choice(ARCHETYPES)
        st.session_state.red_q3 = random.choice(ARCHETYPES)
        st.session_state.blue_q1 = random.choice(ARCHETYPES)
        st.session_state.blue_q2 = random.choice(ARCHETYPES)
        st.session_state.blue_q3 = random.choice(ARCHETYPES)

        # Also randomize strategies and auto plans for complete testing
        st.session_state.rs = random.choice(STRATEGIES)
        st.session_state.bs = random.choice(STRATEGIES)
        st.session_state.red_auto = random.choice(list(AUTO_PRESET_LABELS.keys()))
        st.session_state.blue_auto = random.choice(list(AUTO_PRESET_LABELS.keys()))

        # Set flag for success toast
        st.session_state._randomize_toast = True
        st.rerun()
    else:
        # Show warning in custom mode
        st.sidebar.warning("⚠️ Randomize only works in Quick (Archetype) mode.")

# Show success toast after randomization
if st.session_state.get("_randomize_toast"):
    st.sidebar.success("🎲 Alliances randomized!")
    del st.session_state._randomize_toast

st.sidebar.divider()

if not is_custom:
    red_archs, red_strategy, red_auto_preset = _build_quick_alliance("Red", "red", [0, 2, 3], "rs")
    blue_archs, blue_strategy, blue_auto_preset = _build_quick_alliance("Blue", "blue", [2, 3, 4], "bs")
else:
    with st.sidebar.expander("⚙️ Custom Subsystem Configuration", expanded=True):
        red_overrides = [_build_custom_robot("Red", i+1, ["elite_turret", "strong_scorer", "everybot"][i]) for i in range(3)]
        red_strategy = st.sidebar.selectbox("Red Strategy", STRATEGIES, index=0, format_func=lambda x: STRATEGY_LABELS[x], key="rs_c")
        blue_overrides = [_build_custom_robot("Blue", i+1, ["strong_scorer", "everybot", "kitbot_plus"][i]) for i in range(3)]
        blue_strategy = st.sidebar.selectbox("Blue Strategy", STRATEGIES, index=0, format_func=lambda x: STRATEGY_LABELS[x], key="bs_c")

st.sidebar.divider()
num_sims = st.sidebar.slider("Simulations", 10, 500, 100, step=10)
seed = st.sidebar.number_input("Seed", value=42, min_value=0)

run_sim = st.sidebar.button("Run Simulation", type="primary", use_container_width=True)
find_best = st.sidebar.button("Find Best Strategy", help="Simulates all 25 strategy combinations (Red vs Blue) to find the optimal matchup for each alliance.", use_container_width=True)

st.sidebar.divider()

# Theme selector (moved from Settings tab)
st.sidebar.subheader("⚙️ App Theme")
st.sidebar.radio(
    "Choose Theme",
    ["FRC Blue (TBA)", "Dark Mode", "High Contrast"],
    key="theme",
    help="Changes the visual appearance of the dashboard"
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _run_single(red_cfg, blue_cfg, n, s):
    runner = MonteCarloRunner(red_cfg, blue_cfg, num_simulations=n, base_seed=s)
    return runner.run()

# ---------------------------------------------------------------------------
# Header
# ---------------------------------------------------------------------------
# ---------------------------------------------------------------------------
# Header
# ---------------------------------------------------------------------------
# ---------------------------------------------------------------------------
# Header (Refactored for Perfect Alignment)
# ---------------------------------------------------------------------------
def img_to_bytes(img_path):
    img_bytes = Path(img_path).read_bytes()
    encoded = base64.b64encode(img_bytes).decode()
    return encoded

from pathlib import Path

# Determine logo source
logo_src = ""
logo_width = "300px"
if os.path.exists("ARC logo.png"):
    logo_src = f"data:image/png;base64,{img_to_bytes('ARC logo.png')}"
elif os.path.exists("ARC-logo.svg"):
    logo_src = f"data:image/svg+xml;base64,{img_to_bytes('ARC-logo.svg')}"

if logo_src:
    st.markdown(f"""
    <div style="display: flex; align-items: flex-start; gap: 20px; padding-bottom: 20px;">
        <img src="{logo_src}" style="width: {logo_width}; height: auto;">
        <div style="padding-top: 0px;"> <!-- Fine-tune top padding here -->
            <h1 style="margin: 0; line-height: 1.0; font-size: 3.5rem;">FRC 2026 REBUILT</h1>
            <p style="margin: 5px 0 0 0; line-height: 1.2; font-size: 1.2rem; color: #666;">The Blue Alliance Style Match Simulator & Insights Dashboard</p>
        </div>
    </div>
    """, unsafe_allow_html=True)
else:
    col_logo, col_title = st.columns([1.5, 5])
    with col_logo:
        st.markdown("# 🤖")
    with col_title:
        st.title("FRC 2026 REBUILT")
        st.caption("The Blue Alliance Style Match Simulator & Insights Dashboard")

# ---------------------------------------------------------------------------
# Main Tabs
# ---------------------------------------------------------------------------
tab_event, tab_sim, tab_strat, tab_arch, tab_rules = st.tabs([
    "🏟️ Event Center",
    "📊 Match Simulator",
    "🎯 Strategy Advisor",
    "🤖 Robot Database",
    "📜 Rules & About"
])

# ---------------------------------------------------------------------------
# Tab: Simulation
# ---------------------------------------------------------------------------
with tab_sim:
    if run_sim:
        with st.spinner("Simulating match cycles..."):
            if not is_custom:
                red_alliance = create_alliance_config(red_archs, red_strategy, auto_plan=[a.value for a in AUTO_PRESETS[red_auto_preset]])
                blue_alliance = create_alliance_config(blue_archs, blue_strategy, auto_plan=[a.value for a in AUTO_PRESETS[blue_auto_preset]])
            else:
                red_alliance = create_alliance_config([ov["base"] for ov in red_overrides], red_strategy)
                blue_alliance = create_alliance_config([ov["base"] for ov in blue_overrides], blue_strategy)
                for i, r in enumerate(red_alliance.robots):
                    r.storage_capacity = red_overrides[i]["storage_capacity"]
                    r.accuracy = red_overrides[i]["accuracy"]
                    r.shoot_rate = red_overrides[i]["shoot_rate"]
                    r.climb_target = red_overrides[i]["climb_target"]
                    r.climb_start_time = red_overrides[i]["climb_start_time"]
                for i, r in enumerate(blue_alliance.robots):
                    r.storage_capacity = blue_overrides[i]["storage_capacity"]
                    r.accuracy = blue_overrides[i]["accuracy"]
                    r.shoot_rate = blue_overrides[i]["shoot_rate"]
                    r.climb_target = blue_overrides[i]["climb_target"]
                    r.climb_start_time = blue_overrides[i]["climb_start_time"]
            
            stats = _run_single(red_alliance, blue_alliance, num_sims, seed)
            st.session_state["last_stats"] = stats

    if find_best:
        with st.spinner("Evaluating all 25 strategy combinations..."):
            if not is_custom:
                red_archs_sa, blue_archs_sa = red_archs, blue_archs
            else:
                red_archs_sa = [ov["base"] for ov in red_overrides]
                blue_archs_sa = [ov["base"] for ov in blue_overrides]
            
            results = []
            for rs in STRATEGIES:
                for bs in STRATEGIES:
                    rc = create_alliance_config(red_archs_sa, rs)
                    bc = create_alliance_config(blue_archs_sa, bs)
                    s = _run_single(rc, bc, min(num_sims, 50), seed)
                    s["red_strat"], s["blue_strat"] = rs, bs
                    results.append(s)
            st.session_state["best_strat_results"] = results

    stats = st.session_state.get("last_stats")
    if stats:
        st.header("Match Results Dashboard")
        m_col1, m_col2, m_col3 = st.columns(3)
        m_col1.metric("Red Win Rate", f"{stats['red_win_pct']:.1f}%")
        m_col2.metric("Blue Win Rate", f"{stats['blue_win_pct']:.1f}%")
        m_col3.metric("Avg RP (R/B)", f"{stats['red_rp_avg']:.2f} / {stats['blue_rp_avg']:.2f}")

        st.divider()
        c1, c2 = st.columns(2)
        with c1:
            fig_win = go.Figure(data=[go.Pie(labels=["Red", "Blue", "Tie"], values=[stats["red_win_pct"], stats["blue_win_pct"], stats["tie_pct"]], hole=.4, marker_colors=["#e74c3c", "#3498db", "#95a5a6"])])
            fig_win.update_layout(template=get_plotly_template(), paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", font=dict(color="#FAFAFA" if st.session_state.theme != "FRC Blue (TBA)" else "#000000"))
            st.plotly_chart(fig_win, use_container_width=True)
        with c2:
            fig_hist = go.Figure()
            rh, bh = stats["red_score_histogram"], stats["blue_score_histogram"]
            buckets = sorted(set(list(rh.keys()) + list(bh.keys())), key=lambda x: int(x.split("-")[0]))
            fig_hist.add_trace(go.Bar(name="Red", x=buckets, y=[rh.get(b, 0) for b in buckets], marker_color="rgba(231,76,60,0.6)"))
            fig_hist.add_trace(go.Bar(name="Blue", x=buckets, y=[bh.get(b, 0) for b in buckets], marker_color="rgba(52,152,219,0.6)"))
            fig_hist.update_layout(barmode="overlay", title="Score Probability Density", template=get_plotly_template(), paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", font=dict(color="#FAFAFA" if st.session_state.theme != "FRC Blue (TBA)" else "#000000"))
            st.plotly_chart(fig_hist, use_container_width=True)

        st.subheader("Alliance Stats Summary")
        st.caption("📊 Hover over column headers in the dataframe below for metric explanations")
        s_df = pd.DataFrame({
            "Metric": ["Avg Score", "Score Range", "Fuel Avg", "Tower Avg", "RP Avg", "Energized %", "Traversal %"],
            "Red Alliance": [
                f"{stats['red_avg_score']:.1f}",
                f"{stats['red_score_min']} - {stats['red_score_max']}",
                f"{stats['red_fuel_avg']:.1f}",
                f"{stats['red_tower_avg']:.1f}",
                f"{stats['red_rp_avg']:.2f}",
                f"{stats['red_energized_rate']:.1f}%",
                f"{stats['red_traversal_rate']:.1f}%"
            ],
            "Blue Alliance": [
                f"{stats['blue_avg_score']:.1f}",
                f"{stats['blue_score_min']} - {stats['blue_score_max']}",
                f"{stats['blue_fuel_avg']:.1f}",
                f"{stats['blue_tower_avg']:.1f}",
                f"{stats['blue_rp_avg']:.2f}",
                f"{stats['blue_energized_rate']:.1f}%",
                f"{stats['blue_traversal_rate']:.1f}%"
            ]
        })

        # Use st.table for better theme compatibility (CSS injection doesn't affect st.dataframe iframe)
        st.table(s_df)

        # Plain-English Results Interpretation Panel
        st.divider()
        st.subheader("📊 Match Analysis")

        # Determine dominant alliance
        if stats['red_win_pct'] > 60:
            dominant = "Red"
            dominant_color = "🔴"
            win_margin = stats['red_win_pct']
        elif stats['blue_win_pct'] > 60:
            dominant = "Blue"
            dominant_color = "🔵"
            win_margin = stats['blue_win_pct']
        else:
            dominant = None
            dominant_color = "⚖️"
            win_margin = max(stats['red_win_pct'], stats['blue_win_pct'])

        # Generate interpretation
        if dominant:
            interpretation = f"{dominant_color} **{dominant} Alliance dominates this matchup** with a {win_margin:.1f}% win rate.\n\n"
        else:
            interpretation = f"{dominant_color} **Close matchup** — both alliances have competitive win rates.\n\n"

        # Key factors
        interpretation += "**Key Factors:**\n"

        # Fuel scoring
        if stats['red_fuel_avg'] > stats['blue_fuel_avg'] * 1.2:
            interpretation += f"- Red Alliance's fuel game ({stats['red_fuel_avg']:.1f} pts avg) is significantly stronger.\n"
        elif stats['blue_fuel_avg'] > stats['red_fuel_avg'] * 1.2:
            interpretation += f"- Blue Alliance's fuel game ({stats['blue_fuel_avg']:.1f} pts avg) is significantly stronger.\n"

        # Tower climbing
        if stats['red_tower_avg'] > stats['blue_tower_avg'] * 1.3:
            interpretation += f"- Red Alliance's climbing ({stats['red_tower_avg']:.1f} pts avg) provides a decisive advantage.\n"
        elif stats['blue_tower_avg'] > stats['red_tower_avg'] * 1.3:
            interpretation += f"- Blue Alliance's climbing ({stats['blue_tower_avg']:.1f} pts avg) provides a decisive advantage.\n"

        # Bonus RP achievement
        if stats['red_energized_rate'] > 80 or stats['red_traversal_rate'] > 80:
            interpretation += f"- Red Alliance consistently achieves bonus RPs (Energized: {stats['red_energized_rate']:.0f}%, Traversal: {stats['red_traversal_rate']:.0f}%).\n"
        if stats['blue_energized_rate'] > 80 or stats['blue_traversal_rate'] > 80:
            interpretation += f"- Blue Alliance consistently achieves bonus RPs (Energized: {stats['blue_energized_rate']:.0f}%, Traversal: {stats['blue_traversal_rate']:.0f}%).\n"

        # Counter-strategy recommendation (only if one alliance is losing badly)
        if stats['red_win_pct'] < 40:
            interpretation += f"\n💡 **Counter-Strategy Tip:** Red Alliance should consider defensive tactics or resource denial to disrupt Blue's scoring rhythm."
        elif stats['blue_win_pct'] < 40:
            interpretation += f"\n💡 **Counter-Strategy Tip:** Blue Alliance should consider defensive tactics or resource denial to disrupt Red's scoring rhythm."

        st.info(interpretation)

    best_res = st.session_state.get("best_strat_results")
    if best_res:
        st.divider()
        st.subheader("Optimal Strategy Matrix")
        st.caption("Average Ranking Points (RP) across all 25 strategy combinations. High values indicate stronger matchups.")
        
        matrix_red = []
        matrix_blue = []
        for rs in STRATEGIES:
            row_red = []
            row_blue = []
            for bs in STRATEGIES:
                match = next(r for r in best_res if r["red_strat"] == rs and r["blue_strat"] == bs)
                row_red.append(match["red_rp_avg"])
                row_blue.append(match["blue_rp_avg"])
            matrix_red.append(row_red)
            matrix_blue.append(row_blue)
        
        col_h1, col_h2 = st.columns(2)
        with col_h1:
            fig_heat_red = go.Figure(data=go.Heatmap(z=matrix_red, x=[STRATEGY_LABELS[s] for s in STRATEGIES], y=[STRATEGY_LABELS[s] for s in STRATEGIES], colorscale='Reds', texttemplate="%{z:.2f}"))
            fig_heat_red.update_layout(title="Red Alliance Avg RP", xaxis_title="Blue Strategy", yaxis_title="Red Strategy", template=get_plotly_template(), paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", font=dict(color="#FAFAFA" if st.session_state.theme != "FRC Blue (TBA)" else "#000000"))
            st.plotly_chart(fig_heat_red, use_container_width=True)
        
        with col_h2:
            fig_heat_blue = go.Figure(data=go.Heatmap(z=matrix_blue, x=[STRATEGY_LABELS[s] for s in STRATEGIES], y=[STRATEGY_LABELS[s] for s in STRATEGIES], colorscale='Blues', texttemplate="%{z:.2f}"))
            fig_heat_blue.update_layout(title="Blue Alliance Avg RP", xaxis_title="Blue Strategy", yaxis_title="Red Strategy", template=get_plotly_template(), paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", font=dict(color="#FAFAFA" if st.session_state.theme != "FRC Blue (TBA)" else "#000000"))
            st.plotly_chart(fig_heat_blue, use_container_width=True)

# ---------------------------------------------------------------------------
# Tab: Rules & About
# ---------------------------------------------------------------------------
# ---------------------------------------------------------------------------
# Tab: Rules & About
# ---------------------------------------------------------------------------
with tab_rules:
    st.header("📜 FRC 2026 REBUILT: User Manual")
    
    st.markdown("""
    Welcome to the **FRC 2026 REBUILT Dashboard**. This tool combines **The Blue Alliance (TBA)** live data with a powerful **Monte Carlo Simulator** to help you make data-driven decisions during competition.
    """)

    st.divider()

    # 1. Quick Start
    st.subheader("🚀 1. Getting Started")
    st.info("⚠️ **TBA API Key Required:** To access live data, paste your TBA API Key in the **sidebar**. Get a free key at [thebluealliance.com/account](https://www.thebluealliance.com/account).")
    
    col_q1, col_q2 = st.columns(2)
    with col_q1:
        st.markdown("**Core Workflow:**")
        st.markdown("""
        1. **Select an Event** in the **Event Center** tab.
        2. **Find a Team** using the "Team Quick-Look" tool.
        3. **Simulate a Match** using the **Strategy Advisor** to test your alliance against an opponent.
        4. **Pick Partners** using the **Alliance Picker** for playoffs.
        """)
    with col_q2:
        st.markdown("**Navigation:**")
        st.markdown("""
        - **Sidebar:** Configure API Key, Simulation Settings (Number of Sims, Seed), and App Theme.
        - **Tabs:** Switch between different tools (Event Center, Match Sim, Strategy Advisor, etc.).
        """)

    st.divider()

    # 2. Functional Guides
    st.subheader("📘 2. Feature Procedures")

    with st.expander("🏟️ **Event Center (Scouting & Schedules)**", expanded=True):
        st.markdown("""
        Use this tab to browse real-time event data.
        
        **Procedure:**
        1. **Select Event:** Use the dropdowns to pick the **Year**, **Event Type** (Regional, District, etc.), and specific **Event**.
        2. **Check Schedule:** Opens the **Match Schedule** sub-tab to view upcoming and completed matches.
        3. **View Rankings:** Check the **Rankings & OPR** sub-tab for current standings and computed OPR stats.
        4. **Track a Team:**
           - Enter a team number in the "Track team's next match" box at the top.
           - Click **"Track This Team"** to see a countdown timer to their next match.
        5. **Scout Specific Team:**
           - Go to **Team Quick-Look** sub-tab.
           - Enter a team number and click **"Look Up Team"**.
           - Review their stats (OPR, Rank) and recent match scores.
           - **Crucial Step:** Click **"📊 Use this team in Simulator"** to load their archetype into the Strategy Advisor for simulation.
        """)

    with st.expander("🎯 **Strategy Advisor (Match Prediction)**"):
        st.markdown("""
        Predict match outcomes and optimize your strategy before the match starts.
        
        **Procedure:**
        1. **Setup Match:** Enter the **6 Team Numbers** (Red 1-3, Blue 1-3) for the match you want to simulate.
           - *Tip:* If you used "Team Quick-Look" in the Event Center, your team is already pre-filled.
        2. **Analyze:** Click **"🔍 Analyze Match"**.
           - The app fetches **OPR Data** from TBA to assign accurate robot profiles (Archetypes) to each team.
           - It runs **50 Simulations** to determine the win probability.
        3. **Review Results:**
           - **Recommended Strategy:** See which strategy (e.g., *Full Offense*, *Defense*) gives your alliance the highest Expected RP.
           - **Win Probability:** Inspect the "Red Win Rate" and score predictions.
        4. **"What If" Explorer:**
           - Scroll down to the explorer section.
           - Select a different strategy from the dropdown to see how it changes your win rate compared to the recommendation.
        """)

    with st.expander("🤝 **Alliance Picker (Playoff Selection)**"):
        st.markdown("""
        Find the perfect alliance partner for playoffs.
        
        **Procedure:**
        1. **Prerequisite:** Ensure an event is selected in the **Event Center**.
        2. **Setup:**
           - Enter **Your Team Number**.
           - (Optional) Select teams that have **already been picked** to exclude them from the list.
        3. **Search:** Click **"🔍 Find Best Alliance Partners"**.
        4. **Analyze Candidates:**
           - The table ranks available teams by **Expected Alliance RP** if paired with you.
           - **Role Balance Warning:** Watch for warnings if top candidates are all the same type (e.g., all Scorers with no Defense).
        5. **Test a Pick:**
           - Select a specific candidate from the bottom dropdown.
           - Click **"📊 Simulate with this Pick"** to see detailed simulation results for that specific Hypothetical Alliance.
        """)

    with st.expander("📊 **Match Simulator (Custom Scenarios)**"):
        st.markdown("""
        Run custom simulations with manual control over robot designs.
        
        **Procedure:**
        1. **Set Mode:** In the **Sidebar**, toggle "🔧 Use Custom Subsystems" if you want to manually tune robot stats (Accuracy, Speed, etc.). Otherwise, leave it off for **Quick Mode** (Archetypes).
        2. **Configure Alliances:** Select Archetypes (e.g., *Elite Turret*, *Everybot*) for Red and Blue alliance slots in the sidebar.
        3. **Run Sim:** Click **"Run Simulation"** in the sidebar.
        4. **View Data:**
           - **Win Rates:** Pie chart of Red vs. Blue wins.
           - **Score Distribution:** Histogram showing the range of probable scores.
           - **Detailed Stats:** Table with average Fuel Scored, Tower Points, and RP rates.
        """)

    with st.expander("🤖 **Robot Database (Archetypes)**"):
        st.markdown("""
        Reference for the pre-defined robot profiles used in simulation.
        
        **Procedure:**
        - Select an **Archetype** from the dropdown to view its specs (Shooter Accuracy, Storage, Climb Success).
        - Use the **Comparison Table** to see all archetypes side-by-side.
        """)
        
    st.divider()

    # 3. Game Rules Reference
    st.subheader("📜 3. Game Rules Reference")
    col_r1, col_r2 = st.columns(2)
    with col_r1:
        st.markdown("""
        **Scoring Values**
        - **Active Hub Fuel:** 1 point
        - **Tower Level 1:** 10 points (15 in Auto)
        - **Tower Level 2:** 20 points
        - **Tower Level 3:** 30 points
        """)
    with col_r2:
        st.markdown("""
        **Ranking Points (RP)**
        - **Match Win:** 3 RP
        - **Tie:** 1 RP
        - **Energized (Bonus):** 100+ fuel scored (1 RP)
        - **Supercharged (Bonus):** 360+ fuel scored (1 RP)
        - **Traversal (Bonus):** 50+ tower points (1 RP)
        """)

    st.divider()
    
    # 4. Simulation Architecture
    with st.expander("⚙️ System Architecture (Technical)", expanded=False):
        def get_workflow_graph(theme):
            # Define colors based on theme
            if theme == "Dark Mode":
                # Dark Mode Palette
                c_user = "#1E3A5F"; c_all = "#3D3800"; c_match = "#3D3800";
                c_rob = "#1B3D1E"; c_field = "#1B3D1E"; c_stats = "#1A237E";
                c_bg = "#1E2127"; c_edge = "#AAAAAA"; c_font = "#FAFAFA";
                c_clust = "#1E2127";
            elif theme == "High Contrast":
                # High Contrast Palette (Yellow/Black)
                c_user = "#333300"; c_all = "#333300"; c_match = "#333300";
                c_rob = "#003300"; c_field = "#003300"; c_stats = "#1A1A1A";
                c_bg = "#000000"; c_edge = "#FFFF00"; c_font = "#FFFF00";
                c_clust = "#1A1A1A";
            else:
                # Default Light Theme
                c_user = "#E1F5FE"; c_all = "#FFF9C4"; c_match = "#FFF9C4";
                c_rob = "#C8E6C9"; c_field = "#C8E6C9"; c_stats = "#1A237E";
                c_bg = "transparent"; c_edge = "#555555"; c_font = "#000000";
                c_clust = "#F5F5F5";

            stats_font = "#FFFFFF" if theme != "High Contrast" else "#FFFF00"

            return f"""
            digraph G {{
                graph [splines=ortho, nodesep=1.5, ranksep=1.0, overlap=false, compound=true, bgcolor="transparent"];
                rankdir=TB;
                node [shape=box, style="filled,rounded", fontname="Arial", margin=0.2, width=3.5, fontcolor="{c_font}"];
                edge [fontname="Arial", fontsize=10, color="{c_edge}", fontcolor="{c_font}"];

                # Nodes
                User [label="User Inputs", shape=oval, fillcolor="{c_user}", color="#0277BD"];
                Alliance [label="Alliance Manager\\n(Strategy Prep)", fillcolor="{c_all}", color="#FBC02D"];
                Match [label="Match Engine\\n(Timer & Phase Control)", fillcolor="{c_match}", color="#FBC02D"];

                subgraph cluster_loop {{
                    label = "SIMULATION LOOP (0.5s Ticks)";
                    style = "dashed,rounded";
                    color = "{c_edge}";
                    fontcolor = "{c_font}";
                    bgcolor = "{c_clust}";
                    margin = 50;

                    {{rank=same; Robot; Field;}}
                    Robot [label="Robot Behavior\\n(Cycle Logic)", fillcolor="{c_rob}", color="#2E7D32"];
                    Field [label="Field Manager\\n(Field State & Physics)", fillcolor="{c_field}", color="#2E7D32"];

                    Robot -> Field [label=" Interact / Score ", dir=both, arrowhead=normal, arrowtail=normal, penwidth=2.0];
                }}

                Stats [label="Statistics & Output\\n(Data Aggregation / Monte Carlo)", fillcolor="{c_stats}", color="{c_stats}", fontcolor="{stats_font}"];

                # Vertical Flow
                User -> Alliance;
                Alliance -> Match;
                Match -> Robot [lhead=cluster_loop];
                Robot -> Stats [ltail=cluster_loop];

                # Orthogonal Feedback Loops
                Stats -> Alliance [label=" Iteration Loop (Reset Field)", constraint=false, color="{c_stats}", fontcolor="{c_stats}"];
                Alliance -> Stats [label=" Initial Strategy Data", constraint=false, style=dotted];
            }}
            """
            
        st.graphviz_chart(get_workflow_graph(st.session_state.theme))
        st.caption("Visual representation of the decoupled multi-agent simulation loop running under the hood.")

    st.caption(f"FRC 2026 REBUILT v2.0 | Developed for Team 7130 | TBA API Status: {'✅ Connected' if st.session_state.get('tba_api_key') else '⚠️ Key Missing'}")

# ---------------------------------------------------------------------------
# Tab: Robot Database
# ---------------------------------------------------------------------------
with tab_arch:
    st.header("Robot Archetype Database")
    arch_selection = st.selectbox("Select Archetype", ARCHETYPES, format_func=lambda x: ARCHETYPE_LABELS[x])
    d = ARCHETYPE_DEFAULTS[arch_selection]
    
    c1, c2, c3 = st.columns(3)
    with c1:
        st.write(f"**Shooter:** {d['shooter_type'].replace('_', ' ').title()}")
        st.write(f"**Accuracy:** {d['accuracy']*100:.1f}%")
    with c2:
        st.write(f"**Storage:** {d['storage_capacity']} Fuel")
        st.write(f"**Cycle Time:** {d['cycle_time_mean']}s")
    with c3:
        st.write(f"**Climb Success:**")
        st.progress(d['climb_success_L1'], text=f"L1: {d['climb_success_L1']*100:.0f}%")
        st.progress(d['climb_success_L2'], text=f"L2: {d['climb_success_L2']*100:.0f}%")
        st.progress(d['climb_success_L3'], text=f"L3: {d['climb_success_L3']*100:.0f}%")

    st.divider()
    st.subheader("Full Season Comparison Table")
    comp_data = []
    for a in ARCHETYPES:
        ad = ARCHETYPE_DEFAULTS[a]
        comp_data.append({
            "Name": ARCHETYPE_LABELS[a],
            "Type": ad['shooter_type'],
            "Cap": ad['storage_capacity'],
            "Cycle": ad['cycle_time_mean'],
            "Acc": f"{ad['accuracy']*100:.0f}%",
            "L1%": f"{ad['climb_success_L1']*100:.0f}%",
            "L2%": f"{ad['climb_success_L2']*100:.0f}%",
            "L3%": f"{ad['climb_success_L3']*100:.0f}%"
        })
    st.dataframe(pd.DataFrame(comp_data), use_container_width=True)

# ---------------------------------------------------------------------------
# Tab: Strategy Advisor
# ---------------------------------------------------------------------------
with tab_strat:
    st.header("🎯 Strategy Advisor")
    st.caption("AI-powered match analysis and strategy recommendations based on real team data")

    # ==================== Match Setup Panel ====================
    st.subheader("Match Setup")

    col_setup1, col_setup2 = st.columns(2)

    with col_setup1:
        st.markdown("**Your Alliance**")
        my_r1 = st.number_input("Your R1 Team #", min_value=1, max_value=99999, value=7130, key="strat_my_r1")
        my_r2 = st.number_input("Your R2 Team #", min_value=1, max_value=99999, value=254, key="strat_my_r2")
        my_r3 = st.number_input("Your R3 Team #", min_value=1, max_value=99999, value=1678, key="strat_my_r3")

    with col_setup2:
        st.markdown("**Opponent Alliance**")
        opp_r1 = st.number_input("Opp R1 Team #", min_value=1, max_value=99999, value=971, key="strat_opp_r1")
        opp_r2 = st.number_input("Opp R2 Team #", min_value=1, max_value=99999, value=973, key="strat_opp_r2")
        opp_r3 = st.number_input("Opp R3 Team #", min_value=1, max_value=99999, value=5026, key="strat_opp_r3")

    # Event context (optional, inherited from Event Center)
    use_event_data = st.checkbox(
        "Use Event Center data for OPR lookup",
        value=True,
        help="If checked, will fetch real OPR from the selected event. Otherwise uses placeholder values."
    )

    if use_event_data and st.session_state.get("selected_event_key"):
        event_context = st.session_state["selected_event_key"]
        st.caption(f"📍 Using event: {event_context}")
    else:
        event_context = None
        st.caption("⚠️ No event selected. Using placeholder OPR values.")

    analyze_btn = st.button("🔍 Analyze Match", type="primary", use_container_width=True)

    # ==================== Auto-Archetype Assignment ====================
    if analyze_btn:
        with st.spinner("Fetching team data and mapping archetypes..."):
            my_teams = [my_r1, my_r2, my_r3]
            opp_teams = [opp_r1, opp_r2, opp_r3]

            # Initialize archetype assignments
            my_archetypes = []
            opp_archetypes = []
            my_oprs = []
            opp_oprs = []

            api_key = st.session_state.get("tba_api_key", "")

            if api_key and use_event_data and event_context:
                try:
                    tba = TBAClient(api_key)
                    opr_data = tba.get_event_oprs(event_context)

                    if opr_data and "oprs" in opr_data:
                        oprs_dict = opr_data["oprs"]

                        # Map my teams
                        for team_num in my_teams:
                            team_key = f"frc{team_num}"
                            opr_val = oprs_dict.get(team_key, 30.0)
                            my_oprs.append(opr_val)
                            archetype = map_team_to_archetype(opr_val)
                            my_archetypes.append(archetype)

                        # Map opponent teams
                        for team_num in opp_teams:
                            team_key = f"frc{team_num}"
                            opr_val = oprs_dict.get(team_key, 30.0)
                            opp_oprs.append(opr_val)
                            archetype = map_team_to_archetype(opr_val)
                            opp_archetypes.append(archetype)
                    else:
                        # Fallback: placeholder OPRs
                        my_oprs = [50.0, 45.0, 35.0]
                        opp_oprs = [40.0, 38.0, 30.0]
                        my_archetypes = [map_team_to_archetype(o) for o in my_oprs]
                        opp_archetypes = [map_team_to_archetype(o) for o in opp_oprs]

                except (TBAError, Exception) as e:
                    st.warning(f"Could not fetch OPR data: {e}. Using placeholder values.")
                    my_oprs = [50.0, 45.0, 35.0]
                    opp_oprs = [40.0, 38.0, 30.0]
                    my_archetypes = [map_team_to_archetype(o) for o in my_oprs]
                    opp_archetypes = [map_team_to_archetype(o) for o in opp_oprs]
            else:
                # No API key or event: use placeholders
                my_oprs = [50.0, 45.0, 35.0]
                opp_oprs = [40.0, 38.0, 30.0]
                my_archetypes = [map_team_to_archetype(o) for o in my_oprs]
                opp_archetypes = [map_team_to_archetype(o) for o in opp_oprs]

            # Store in session state
            st.session_state["strat_my_archetypes"] = my_archetypes
            st.session_state["strat_opp_archetypes"] = opp_archetypes
            st.session_state["strat_my_oprs"] = my_oprs
            st.session_state["strat_opp_oprs"] = opp_oprs
            st.session_state["strat_my_teams"] = my_teams
            st.session_state["strat_opp_teams"] = opp_teams

    # Display archetype assignments
    if "strat_my_archetypes" in st.session_state:
        st.divider()
        st.subheader("Archetype Assignments")

        col_my, col_opp = st.columns(2)

        with col_my:
            st.markdown("**Your Alliance**")
            for i, (team, arch, opr) in enumerate(zip(
                st.session_state["strat_my_teams"],
                st.session_state["strat_my_archetypes"],
                st.session_state["strat_my_oprs"]
            )):
                # Allow override
                override_arch = st.selectbox(
                    f"Team {team}",
                    ARCHETYPES,
                    index=ARCHETYPES.index(arch),
                    format_func=lambda x: f"{ARCHETYPE_LABELS[x]} (OPR: {opr:.1f})",
                    key=f"strat_my_override_{i}"
                )
                st.session_state["strat_my_archetypes"][i] = override_arch

        with col_opp:
            st.markdown("**Opponent Alliance**")
            for i, (team, arch, opr) in enumerate(zip(
                st.session_state["strat_opp_teams"],
                st.session_state["strat_opp_archetypes"],
                st.session_state["strat_opp_oprs"]
            )):
                # Allow override
                override_arch = st.selectbox(
                    f"Team {team}",
                    ARCHETYPES,
                    index=ARCHETYPES.index(arch),
                    format_func=lambda x: f"{ARCHETYPE_LABELS[x]} (OPR: {opr:.1f})",
                    key=f"strat_opp_override_{i}"
                )
                st.session_state["strat_opp_archetypes"][i] = override_arch

        # ==================== Strategy Recommendation ====================
        st.divider()
        st.subheader("💡 Recommended Strategy")

        my_archs_final = st.session_state["strat_my_archetypes"]
        opp_archs_final = st.session_state["strat_opp_archetypes"]

        # Simple recommendation logic: test all 5 strategies, pick best avg RP
        best_strat = None
        best_rp = 0
        strat_results = {}

        with st.spinner("Running strategy simulations..."):
            for strat in STRATEGIES:
                my_cfg = create_alliance_config(my_archs_final, strat)
                opp_cfg = create_alliance_config(opp_archs_final, "full_offense")  # Assume opponent plays default
                sim_result = _run_single(my_cfg, opp_cfg, 50, seed)
                strat_results[strat] = sim_result

                if sim_result["red_rp_avg"] > best_rp:
                    best_rp = sim_result["red_rp_avg"]
                    best_strat = strat

        st.session_state["strat_results"] = strat_results
        st.session_state["strat_best"] = best_strat

        st.success(f"**{STRATEGY_LABELS[best_strat]}** — Expected RP: {best_rp:.2f}")
        st.write(STRATEGY_DETAILS[best_strat])
        st.info(f"💡 Winning Tip: {STRATEGY_TIPS[best_strat]}")

        # Quick sim results
        best_res = strat_results[best_strat]
        col_win, col_rp, col_score = st.columns(3)
        col_win.metric("Win Probability", f"{best_res['red_win_pct']:.1f}%")
        col_rp.metric("Avg RP", f"{best_res['red_rp_avg']:.2f}")
        col_score.metric("Avg Score", f"{best_res['red_avg_score']:.1f}")

        # ==================== "What If" Explorer ====================
        st.divider()
        st.subheader("🔀 'What If' Strategy Explorer")
        st.caption("Compare how different strategies perform against this opponent")

        selected_strat = st.selectbox(
            "Try a different strategy:",
            STRATEGIES,
            index=STRATEGIES.index(best_strat),
            format_func=lambda x: STRATEGY_LABELS[x],
            key="strat_whatif"
        )

        if selected_strat != best_strat:
            whatif_res = strat_results[selected_strat]
            st.markdown(f"**{STRATEGY_LABELS[selected_strat]}**")
            st.write(STRATEGY_DETAILS[selected_strat])

            col_w1, col_w2, col_w3 = st.columns(3)
            col_w1.metric("Win Probability", f"{whatif_res['red_win_pct']:.1f}%",
                          delta=f"{whatif_res['red_win_pct'] - best_res['red_win_pct']:.1f}%")
            col_w2.metric("Avg RP", f"{whatif_res['red_rp_avg']:.2f}",
                          delta=f"{whatif_res['red_rp_avg'] - best_res['red_rp_avg']:.2f}")
            col_w3.metric("Avg Score", f"{whatif_res['red_avg_score']:.1f}",
                          delta=f"{whatif_res['red_avg_score'] - best_res['red_avg_score']:.1f}")

        # Comparison table
        st.subheader("All Strategies Comparison")
        comp_rows = []
        for s in STRATEGIES:
            res = strat_results[s]
            comp_rows.append({
                "Strategy": STRATEGY_LABELS[s],
                "Win %": f"{res['red_win_pct']:.1f}%",
                "Avg RP": f"{res['red_rp_avg']:.2f}",
                "Avg Score": f"{res['red_avg_score']:.1f}",
                "Energized %": f"{res['red_energized_rate']:.1f}%",
                "Traversal %": f"{res['red_traversal_rate']:.1f}%",
            })
        st.dataframe(pd.DataFrame(comp_rows), use_container_width=True, hide_index=True)

    # ==================== Strategy Reference (Collapsed) ====================
    st.divider()
    with st.expander("📚 Strategy Reference Guide", expanded=False):
        st.markdown("### Tactical Breakdowns")
        for k, v in STRATEGY_LABELS.items():
            st.markdown(f"**{v}**")
            st.write(STRATEGY_DETAILS[k])
            st.caption(f"💡 {STRATEGY_TIPS[k]}")
            st.markdown("---")

        st.markdown("### The Hub Shift Meta")
        st.markdown("""
        The core of REBUILT is the **25-second Hub shift**.
        - **Active Alliance**: Your goal is maximum throughput. Use high-rate shooters to empty your stockpile and Neutral Zone as fast as possible.
        - **Inactive Alliance**: Do not waste fuel. Use this time to collect 100% of your storage capacity at the Outposts and pre-position at the Hub. The moment the Hub lights up, you should be able to score 30+ points in the first 3 seconds.
        """)

    # ==================== Alliance Picker ====================
    st.divider()
    st.header("🤝 Alliance Picker")
    st.caption("Find the best alliance partners during alliance selection")

    api_key = st.session_state.get("tba_api_key", "")
    if not api_key:
        st.info("🔑 Enter your TBA API key in the sidebar to use the Alliance Picker.")
    elif not st.session_state.get("selected_event_key"):
        st.info("📍 Select an event in the Event Center tab first to load available teams.")
    else:
        col_pick1, col_pick2 = st.columns([1, 2])

        with col_pick1:
            your_team = st.number_input(
                "Your Team Number",
                min_value=1,
                max_value=99999,
                value=st.session_state.get("ec_team_number", 7130),
                key="alliance_picker_team"
            )

        with col_pick2:
            # Get already picked teams from Event Center alliances
            already_picked = []
            try:
                tba = TBAClient(api_key)
                event_key = st.session_state["selected_event_key"]
                alliances_data = tba.get_event_alliances(event_key)
                if alliances_data:
                    for alliance in alliances_data:
                        picks = [int(t.replace("frc", "")) for t in alliance.get("picks", [])]
                        already_picked.extend(picks)
            except:
                pass

            # Get all teams at event
            all_teams = []
            try:
                event_teams = tba.get_event_teams(event_key)
                if event_teams:
                    all_teams = [t["team_number"] for t in event_teams]
            except:
                pass

            # Multiselect for already picked teams
            picked_teams = st.multiselect(
                "Already Picked Teams (exclude from candidates)",
                options=sorted(all_teams) if all_teams else [],
                default=already_picked,
                key="alliance_picker_picked",
                help="Teams already in alliances will be excluded from recommendations"
            )

        if st.button("🔍 Find Best Alliance Partners", type="primary", use_container_width=True):
            with st.spinner("Analyzing all available candidates..."):
                try:
                    # Get event data
                    tba = TBAClient(api_key)
                    event_key = st.session_state["selected_event_key"]
                    opr_data = tba.get_event_oprs(event_key)
                    event_teams = tba.get_event_teams(event_key)

                    if not opr_data or not event_teams:
                        st.error("Could not fetch event data.")
                    else:
                        # Get your team's archetype
                        your_opr = opr_data.get("oprs", {}).get(f"frc{your_team}", 40.0)
                        your_archetype = map_team_to_archetype(your_opr)

                        # Get all available candidates
                        all_team_nums = [t["team_number"] for t in event_teams]
                        available = [
                            t for t in all_team_nums
                            if t != your_team and t not in picked_teams
                        ]

                        # Build candidate rankings
                        candidates = []
                        for candidate_num in available:
                            candidate_key = f"frc{candidate_num}"
                            candidate_opr = opr_data.get("oprs", {}).get(candidate_key, 30.0)
                            candidate_archetype = map_team_to_archetype(candidate_opr)

                            # Find best remaining third robot
                            remaining = [t for t in available if t != candidate_num]
                            best_third_opr = 0
                            best_third_arch = "everybot"
                            for third in remaining[:5]:  # Check top 5 to save time
                                third_key = f"frc{third}"
                                third_opr = opr_data.get("oprs", {}).get(third_key, 25.0)
                                if third_opr > best_third_opr:
                                    best_third_opr = third_opr
                                    best_third_arch = map_team_to_archetype(third_opr)

                            # Simulate alliance: your team + candidate + best remaining
                            alliance_archs = [your_archetype, candidate_archetype, best_third_arch]
                            opponent_archs = ["strong_scorer", "everybot", "kitbot_plus"]  # Generic opponent

                            my_cfg = create_alliance_config(alliance_archs, "full_offense")
                            opp_cfg = create_alliance_config(opponent_archs, "full_offense")
                            result = _run_single(my_cfg, opp_cfg, 30, seed)

                            # Determine suggested role
                            if candidate_archetype in ["elite_turret", "elite_multishot", "strong_scorer"]:
                                role = "Primary Scorer"
                            elif candidate_archetype == "defense_bot":
                                role = "Defender"
                            else:
                                role = "Support Scorer"

                            # Get team name
                            team_data = next((t for t in event_teams if t["team_number"] == candidate_num), None)
                            team_name = team_data.get("nickname", "") if team_data else ""

                            candidates.append({
                                "Team #": candidate_num,
                                "Name": team_name[:25],  # Truncate long names
                                "OPR": round(candidate_opr, 1),
                                "Archetype": ARCHETYPE_LABELS[candidate_archetype],
                                "Expected RP": round(result["red_rp_avg"], 2),
                                "Win %": round(result["red_win_pct"], 1),
                                "Role": role,
                                "_archetype_key": candidate_archetype,
                            })

                        # Sort by Expected RP descending
                        candidates.sort(key=lambda x: x["Expected RP"], reverse=True)

                        # Store in session state
                        st.session_state["alliance_candidates"] = candidates
                        st.session_state["alliance_your_team"] = your_team
                        st.session_state["alliance_your_archetype"] = your_archetype

                except Exception as e:
                    st.error(f"Error analyzing candidates: {e}")

        # Display results
        if "alliance_candidates" in st.session_state:
            candidates = st.session_state["alliance_candidates"]
            your_team = st.session_state["alliance_your_team"]
            your_archetype = st.session_state["alliance_your_archetype"]

            st.divider()
            st.subheader("🏆 Recommended Alliance Partners")
            st.caption(f"Your team: {your_team} — {ARCHETYPE_LABELS[your_archetype]}")

            # Role balance check
            top_5_archs = [c["_archetype_key"] for c in candidates[:5]]
            scorer_archs = ["elite_turret", "elite_multishot", "strong_scorer"]
            top_5_scorers = sum(1 for a in top_5_archs if a in scorer_archs)

            if top_5_scorers >= 4:
                st.warning("⚠️ **Role Balance Alert:** Top candidates are all scorers. Consider picking a defender for strategic flexibility.")

            # Display table
            display_candidates = [
                {k: v for k, v in c.items() if not k.startswith("_")}
                for c in candidates
            ]

            st.dataframe(
                pd.DataFrame(display_candidates),
                use_container_width=True,
                hide_index=True,
                column_config={
                    "Expected RP": st.column_config.ProgressColumn(
                        "Expected RP",
                        min_value=0,
                        max_value=6,
                        format="%.2f",
                    ),
                    "Win %": st.column_config.ProgressColumn(
                        "Win %",
                        min_value=0,
                        max_value=100,
                        format="%.1f%%",
                    ),
                },
            )

            # Simulate with selected pick
            st.divider()
            st.subheader("Test a Specific Pick")
            selected_pick = st.selectbox(
                "Select a candidate to simulate",
                options=[c["Team #"] for c in candidates[:10]],
                format_func=lambda t: f"Team {t} — {next(c['Name'] for c in candidates if c['Team #'] == t)}",
                key="alliance_test_pick"
            )

            if st.button("📊 Simulate with this Pick", use_container_width=True):
                # Find selected candidate
                candidate = next(c for c in candidates if c["Team #"] == selected_pick)

                # Build alliance
                your_arch = st.session_state["alliance_your_archetype"]
                candidate_arch = candidate["_archetype_key"]

                # Let user pick third robot
                st.info(f"Alliance: {your_team} ({ARCHETYPE_LABELS[your_arch]}) + {selected_pick} ({candidate['Archetype']}) + [select third]")

                # Show top 3 available robots for third pick
                remaining = [c for c in candidates if c["Team #"] != selected_pick][:3]
                if remaining:
                    st.write("**Suggested third robots:**")
                    for r in remaining:
                        st.write(f"- Team {r['Team #']}: {r['Name']} ({r['Archetype']}, OPR: {r['OPR']})")

                    # Auto-simulate with best third
                    best_third_arch = remaining[0]["_archetype_key"]
                    alliance_archs = [your_arch, candidate_arch, best_third_arch]
                    opponent_archs = ["strong_scorer", "everybot", "kitbot_plus"]

                    my_cfg = create_alliance_config(alliance_archs, "full_offense")
                    opp_cfg = create_alliance_config(opponent_archs, "full_offense")
                    result = _run_single(my_cfg, opp_cfg, 100, seed)

                    st.success("✅ Simulation complete!")
                    col_s1, col_s2, col_s3 = st.columns(3)
                    col_s1.metric("Win %", f"{result['red_win_pct']:.1f}%")
                    col_s2.metric("Expected RP", f"{result['red_rp_avg']:.2f}")
                    col_s3.metric("Avg Score", f"{result['red_avg_score']:.1f}")

# ---------------------------------------------------------------------------
# Tab: Event Center
# ---------------------------------------------------------------------------
with tab_event:
    st.header("🏟️ Event Center")
    st.caption("Live event data powered by The Blue Alliance API")

    # --- Graceful degradation: no API key ---
    api_key = st.session_state.get("tba_api_key", "")
    if not api_key:
        st.info(
            "🔑 **Enter your TBA API key in the sidebar** to view live event data.\n\n"
            "Get a free key at [thebluealliance.com/account](https://www.thebluealliance.com/account)."
        )
    else:
        try:
            tba = TBAClient(api_key)

            # ---- Event Selector ----
            # TBA event_type mapping for categorization
            EVENT_CATEGORIES = {
                "🏆 Regional": {0},                        # Regional
                "🔷 District": {1, 2, 5},                  # District, District CMP, District CMP Division
                "🌟 Championship": {3, 4, 6},              # CMP Division, CMP Finals, Festival of Champs
                "🎉 Off-Season": {99, 100},                # Offseason, Preseason
            }

            ec_col1, ec_col2, ec_col3 = st.columns([1, 1.5, 2.5])
            with ec_col1:
                selected_year = st.selectbox(
                    "Year", list(range(2025, 2019, -1)), index=0, key="ec_year"
                )
            with ec_col2:
                selected_category = st.selectbox(
                    "Event Type",
                    list(EVENT_CATEGORIES.keys()),
                    index=0,
                    key="ec_category",
                )

            events_raw = tba.get_events_by_year(selected_year)

            with ec_col3:
                if events_raw:
                    events_raw.sort(key=lambda e: e.get("start_date", ""))
                    allowed_types = EVENT_CATEGORIES[selected_category]
                    filtered_events = [
                        e for e in events_raw
                        if e.get("event_type", 99) in allowed_types
                    ]
                    if filtered_events:
                        event_options = {
                            f"{e['name']} ({e['key']})": e["key"]
                            for e in filtered_events
                        }
                        selected_event_label = st.selectbox(
                            "Event", list(event_options.keys()), key="ec_event"
                        )
                        selected_event_key = event_options[selected_event_label]
                        st.session_state["selected_event_key"] = selected_event_key
                    else:
                        st.info(f"No {selected_category.split(' ', 1)[1]} events found for {selected_year}.")
                        selected_event_key = None
                else:
                    st.warning("Could not load events for this year.")
                    selected_event_key = None

            if selected_event_key:
                st.divider()

                # ---- Next Match Notification (Feature 6) ----
                if "next_match_team" not in st.session_state:
                    st.session_state.next_match_team = None

                col_nm1, col_nm2 = st.columns([2, 3])
                with col_nm1:
                    track_team = st.number_input(
                        "⏰ Track team's next match",
                        min_value=1,
                        max_value=99999,
                        value=st.session_state.next_match_team or 254,
                        key="next_match_team_input",
                        help="Enter your team number to see countdown to next match"
                    )
                    if st.button("Track This Team", use_container_width=True):
                        st.session_state.next_match_team = track_team
                        st.rerun()

                with col_nm2:
                    if st.session_state.next_match_team:
                        try:
                            import datetime
                            matches_raw = tba.get_event_matches(selected_event_key)
                            team_key = f"frc{st.session_state.next_match_team}"

                            # Find next unplayed match for this team
                            now = datetime.datetime.now(datetime.timezone.utc)
                            upcoming_matches = []

                            for m in matches_raw:
                                red_teams = m.get("alliances", {}).get("red", {}).get("team_keys", [])
                                blue_teams = m.get("alliances", {}).get("blue", {}).get("team_keys", [])

                                if team_key in red_teams or team_key in blue_teams:
                                    # Check if match has been played
                                    red_score = m.get("alliances", {}).get("red", {}).get("score")
                                    if red_score is None or red_score < 0:
                                        # Match not played yet
                                        match_time = m.get("actual_time") or m.get("predicted_time") or m.get("time")
                                        if match_time:
                                            match_dt = datetime.datetime.fromtimestamp(match_time, datetime.timezone.utc)
                                            if match_dt > now:
                                                upcoming_matches.append({
                                                    "match": m,
                                                    "time": match_dt,
                                                    "label": f"{m['comp_level'].upper()} {m['match_number']}"
                                                })

                            if upcoming_matches:
                                # Sort by time and get next match
                                upcoming_matches.sort(key=lambda x: x["time"])
                                next_match = upcoming_matches[0]

                                time_diff = next_match["time"] - now
                                minutes_left = int(time_diff.total_seconds() / 60)
                                hours_left = minutes_left // 60
                                mins_remainder = minutes_left % 60

                                if minutes_left < 0:
                                    st.info(f"🏁 Team {st.session_state.next_match_team}'s {next_match['label']} is starting now!")
                                elif hours_left > 0:
                                    st.success(f"⏰ **Next match:** {next_match['label']} in **{hours_left}h {mins_remainder}m**")
                                elif minutes_left <= 15:
                                    st.warning(f"🚨 **Next match:** {next_match['label']} in **{minutes_left} minutes!**")
                                else:
                                    st.info(f"⏰ **Next match:** {next_match['label']} in **{minutes_left} minutes**")
                            else:
                                st.caption(f"No upcoming matches found for team {st.session_state.next_match_team}")

                        except Exception as e:
                            st.caption("Could not fetch match schedule")

                st.divider()

                # ---- Sub-tabs inside Event Center ----
                ec_tab_rank, ec_tab_matches, ec_tab_alliances, ec_tab_team = st.tabs([
                    "📋 Rankings & OPR",
                    "📅 Match Schedule",
                    "🤝 Alliance Bracket",
                    "🔎 Team Quick-Look",
                ])

                # ==== Rankings & OPR ====
                with ec_tab_rank:
                    rankings_data = tba.get_event_rankings(selected_event_key)
                    opr_data = tba.get_event_oprs(selected_event_key)

                    if rankings_data and "rankings" in rankings_data and opr_data:
                        rows = []
                        for r in rankings_data["rankings"]:
                            tk = r.get("team_key", "")
                            num = tk.replace("frc", "")
                            rec = r.get("record", {})
                            record_str = f"{rec.get('wins',0)}-{rec.get('losses',0)}-{rec.get('ties',0)}"
                            opr_val = opr_data.get("oprs", {}).get(tk, 0)
                            dpr_val = opr_data.get("dprs", {}).get(tk, 0)
                            ccwm_val = opr_data.get("ccwms", {}).get(tk, 0)
                            rp_total = 0
                            for si in r.get("sort_orders", []):
                                rp_total = si
                                break
                            rows.append({
                                "Rank": r.get("rank"),
                                "Team #": num,
                                "Record": record_str,
                                "RP": rp_total,
                                "OPR": round(opr_val, 2),
                                "DPR": round(dpr_val, 2),
                                "CCWM": round(ccwm_val, 2),
                                "Archetype": ARCHETYPE_LABELS.get(
                                    map_team_to_archetype(opr_val), "Unknown"
                                ),
                            })
                        df_rank = pd.DataFrame(rows)
                        st.dataframe(
                            df_rank,
                            use_container_width=True,
                            hide_index=True,
                            column_config={
                                "OPR": st.column_config.ProgressColumn(
                                    "OPR",
                                    min_value=0,
                                    max_value=float(df_rank["OPR"].max()) * 1.1 if len(df_rank) else 100,
                                    format="%.1f",
                                    help="Offensive Power Rating - estimates a team's average contribution to their alliance score"
                                ),
                                "DPR": st.column_config.NumberColumn(
                                    "DPR",
                                    help="Defensive Power Rating - estimates points prevented on opposing alliance"
                                ),
                                "CCWM": st.column_config.NumberColumn(
                                    "CCWM",
                                    help="Calculated Contribution to Winning Margin - positive values indicate the team helps their alliance win by more"
                                ),
                                "RP": st.column_config.NumberColumn(
                                    "RP",
                                    help="Total Ranking Points - used for seeding and playoff qualification"
                                ),
                            },
                        )
                    else:
                        st.warning("Rankings or OPR data not yet available for this event.")

                # ==== Match Schedule ====
                with ec_tab_matches:
                    matches_raw = tba.get_event_matches(selected_event_key)

                    if matches_raw:
                        level_order = {"qm": 0, "ef": 1, "qf": 2, "sf": 3, "f": 4}
                        matches_raw.sort(
                            key=lambda m: (
                                level_order.get(m.get("comp_level", "qm"), 0),
                                m.get("set_number", 0),
                                m.get("match_number", 0),
                            )
                        )

                        completed, upcoming = [], []
                        for m in matches_raw:
                            red_a = m.get("alliances", {}).get("red", {})
                            blue_a = m.get("alliances", {}).get("blue", {})
                            label = f"{m['comp_level'].upper()} {m['match_number']}"
                            red_teams = [t.replace("frc", "") for t in red_a.get("team_keys", [])]
                            blue_teams = [t.replace("frc", "") for t in blue_a.get("team_keys", [])]
                            red_score = red_a.get("score")
                            blue_score = blue_a.get("score")

                            row = {
                                "Match": label,
                                "Red 1": red_teams[0] if len(red_teams) > 0 else "",
                                "Red 2": red_teams[1] if len(red_teams) > 1 else "",
                                "Red 3": red_teams[2] if len(red_teams) > 2 else "",
                                "Blue 1": blue_teams[0] if len(blue_teams) > 0 else "",
                                "Blue 2": blue_teams[1] if len(blue_teams) > 1 else "",
                                "Blue 3": blue_teams[2] if len(blue_teams) > 2 else "",
                                "Red Score": red_score if red_score is not None and red_score >= 0 else "",
                                "Blue Score": blue_score if blue_score is not None and blue_score >= 0 else "",
                            }
                            if red_score is not None and red_score >= 0:
                                completed.append(row)
                            else:
                                upcoming.append(row)

                        if upcoming:
                            st.subheader("⏳ Upcoming Matches")
                            st.dataframe(pd.DataFrame(upcoming), use_container_width=True, hide_index=True)
                        if completed:
                            st.subheader("✅ Completed Matches")
                            st.dataframe(pd.DataFrame(completed), use_container_width=True, hide_index=True)
                    else:
                        st.info("No match data available yet for this event.")

                # ==== Alliance Bracket ====
                with ec_tab_alliances:
                    alliances_data = tba.get_event_alliances(selected_event_key)
                    if alliances_data:
                        rows_a = []
                        picked_teams = set()
                        for idx, a in enumerate(alliances_data, 1):
                            picks = [t.replace("frc", "") for t in a.get("picks", [])]
                            picked_teams.update(picks)
                            row = {"Alliance": f"Alliance {idx}"}
                            for j, p in enumerate(picks):
                                row[f"Pick {j+1}"] = p
                            status = a.get("status", {})
                            rec = status.get("record", {})
                            if rec:
                                row["Record"] = f"{rec.get('wins',0)}-{rec.get('losses',0)}-{rec.get('ties',0)}"
                            rows_a.append(row)
                        st.dataframe(pd.DataFrame(rows_a), use_container_width=True, hide_index=True)

                        # Available teams (not yet picked)
                        event_teams = tba.get_event_teams(selected_event_key)
                        if event_teams:
                            all_team_nums = {str(t["team_number"]) for t in event_teams}
                            available = sorted(all_team_nums - picked_teams, key=lambda x: int(x))
                            if available:
                                with st.expander(f"📝 Available Teams ({len(available)}) — not yet picked"):
                                    st.write(", ".join(available))
                    else:
                        st.info("Alliance selections not yet available for this event.")

                # ==== Team Quick-Look ====
                with ec_tab_team:
                    ql_team = st.number_input("Team Number", min_value=1, max_value=99999, value=7130, key="ec_ql_team")

                    if st.button("Look Up Team", key="ec_ql_btn"):
                        summary = get_team_summary(tba, ql_team, selected_event_key)
                        if summary:
                            st.success(f"**{summary['name']}** — Team {summary['number']}")
                            mc1, mc2, mc3, mc4 = st.columns(4)
                            mc1.metric("OPR", f"{summary['opr']:.1f}" if summary["opr"] else "N/A")
                            mc2.metric("DPR", f"{summary['dpr']:.1f}" if summary["dpr"] else "N/A")
                            mc3.metric("CCWM", f"{summary['ccwm']:.1f}" if summary["ccwm"] else "N/A")
                            mc4.metric("Rank", summary["rank"] or "N/A")
                            if summary["record"]:
                                rec = summary["record"]
                                st.caption(f"Record: {rec.get('wins',0)}-{rec.get('losses',0)}-{rec.get('ties',0)}")
                            if summary["archetype"]:
                                st.info(f"🤖 Mapped Archetype: **{ARCHETYPE_LABELS.get(summary['archetype'], summary['archetype'])}**")

                            # Recent matches for this team
                            team_matches = tba.get_team_matches_at_event(ql_team, selected_event_key)
                            if team_matches:
                                team_matches.sort(key=lambda m: m.get("match_number", 0))
                                scores = []
                                team_key = f"frc{ql_team}"
                                for m in team_matches[-8:]:
                                    red_keys = m.get("alliances", {}).get("red", {}).get("team_keys", [])
                                    if team_key in red_keys:
                                        s = m.get("alliances", {}).get("red", {}).get("score", None)
                                    else:
                                        s = m.get("alliances", {}).get("blue", {}).get("score", None)
                                    if s is not None and s >= 0:
                                        scores.append({"Match": f"{m['comp_level'].upper()} {m['match_number']}", "Score": s})
                                if scores:
                                    st.subheader("Recent Match Scores")
                                    st.dataframe(pd.DataFrame(scores), hide_index=True, use_container_width=True)

                            # "Use this team in Simulator" button
                            if summary["archetype"]:
                                if st.button("📊 Use this team in Simulator", key="ec_use_team"):
                                    st.session_state["ec_team_archetype"] = summary["archetype"]
                                    st.session_state["ec_team_number"] = ql_team
                                    st.success(f"Team {ql_team} ({ARCHETYPE_LABELS.get(summary['archetype'])}) is ready — switch to a sidebar alliance slot.")
                        else:
                            st.warning(f"Team {ql_team} not found at this event, or TBA data unavailable.")

        except TBAError as e:
            st.error(f"❌ TBA API Error: {e}")
        except Exception as e:
            st.error(f"❌ Unexpected error: {e}")


# ---------------------------------------------------------------------------
# Footer
# ---------------------------------------------------------------------------
st.divider()
st.caption("© 2026 FRC Tactic Supervisor AI. Inspired by The Blue Alliance.")
