"""A functional scientific-instrument interface study for the Commons protocol."""

from __future__ import annotations

import altair as alt
import pandas as pd
import streamlit as st
from streamlit_extras.stylable_container import stylable_container

from protocol import load_protocol
from storage import get_repository, repository_mode


PRIORITIES = ("Perceive", "Mobilise", "Decide", "Transform")
ACTORS = (
    "Residents",
    "Researchers",
    "Institutions",
    "Technologists",
    "Journalists",
    "Stewards",
)
CAPACITIES = (
    "Human expertise",
    "Technical tools",
    "Knowledge & data",
    "Community trust",
    "Institutional support",
    "Time & attention",
)
ACTIONS = (
    "Open inquiry",
    "Protect the resource",
    "Build a coalition",
    "Set a temporary rule",
)

CARD_STYLE = """
{
    background: rgba(6, 13, 12, .96);
    border: 1px solid var(--line);
    border-radius: 2px;
    padding: 1.5rem;
    height: 100%;
}
"""


def lab_card(key: str, extra_css: str | None = None):
    """Return a scoped, flat instrument panel."""

    styles = [CARD_STYLE]
    if extra_css:
        styles.append(extra_css)
    return stylable_container(key=key, css_styles=styles)


def section_title(number: str, title: str, note: str) -> None:
    st.markdown(
        f"""
        <div class="lab-section-head">
          <span>{number}</span><h2>{title}</h2><small>{note}</small>
        </div>
        """,
        unsafe_allow_html=True,
    )


def step_title(number: str, title: str, instruction: str) -> None:
    st.markdown(
        f"""
        <div class="lab-step-head">
          <b>{number}</b><div><h3>{title}</h3><p>{instruction}</p></div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def apply_lab_theme() -> None:
    st.markdown(
        """
        <style>
        @import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;500;600&display=swap');
        :root {
          --void:#010505; --panel:#060d0c; --surface:#0a1211;
          --line:#35413e; --line-soft:#1b2523; --text:#dddccf;
          --muted:#929d98; --accent:#d7ca3d; --signal:#79cbb6;
          --warning:#e27d3e;
        }
        html, body, [class*="st-"], .stApp {
          font-family:"IBM Plex Mono", "SFMono-Regular", Consolas, monospace !important;
        }
        .stApp {
          background:
            linear-gradient(rgba(121,203,182,.014) 1px, transparent 1px),
            linear-gradient(90deg, rgba(121,203,182,.014) 1px, transparent 1px),
            var(--void);
          background-size:32px 32px, 32px 32px, auto;
          color:var(--text);
        }
        [data-testid="stHeader"], [data-testid="stToolbar"], #MainMenu, footer { display:none; }
        [data-testid="stSidebar"] { background:#010303; border-right-color:#121918; }
        .block-container { max-width:1568px; padding:1rem 1.5rem 2rem !important; }
        [data-testid="stVerticalBlock"] { gap:1rem; }
        [data-testid="stHorizontalBlock"] { align-items:stretch; }

        h1, h2, h3, p { margin:0; }
        h1, h2, h3 { color:var(--text) !important; font-family:inherit !important; }
        h1 { font-size:2.5rem !important; line-height:1 !important; font-weight:600 !important; letter-spacing:.015em !important; }
        h2 { font-size:1.35rem !important; line-height:1.2 !important; font-weight:500 !important; letter-spacing:0 !important; }
        h3 { font-size:1rem !important; line-height:1.35 !important; font-weight:500 !important; letter-spacing:0 !important; }
        p, li, label, .stCaption { color:var(--text); font-size:.875rem; line-height:1.6; }

        .lab-masthead { display:flex; align-items:flex-end; justify-content:space-between; gap:2rem; padding:.5rem 0 1.5rem; }
        .lab-kicker, .lab-label { color:var(--signal); font-size:.75rem; letter-spacing:.1em; text-transform:uppercase; }
        .lab-masthead h1 { color:var(--accent) !important; margin:.5rem 0 !important; }
        .lab-masthead p { color:var(--muted); max-width:46rem; }
        .lab-live { display:flex; align-items:center; gap:.5rem; color:var(--signal); font-size:.75rem; letter-spacing:.08em; text-transform:uppercase; white-space:nowrap; padding-bottom:.25rem; }
        .lab-live::before { content:""; width:.5rem; height:.5rem; border-radius:50%; background:var(--signal); box-shadow:0 0 10px rgba(121,203,182,.65); }

        .lab-section-head { display:grid; grid-template-columns:2rem auto 1fr; align-items:baseline; gap:.5rem; border-bottom:1px solid var(--line-soft); padding-bottom:1rem; margin-bottom:1.5rem; }
        .lab-section-head span { color:var(--accent); font-size:.75rem; }
        .lab-section-head small { color:var(--muted); font-size:.75rem; text-align:right; }

        .lab-scenario-card { min-height:44rem; display:flex; flex-direction:column; }
        .lab-signal-code { color:var(--signal); font-size:.75rem; letter-spacing:.08em; text-transform:uppercase; }
        .lab-scenario-title { color:#e2e4d5; font-size:2rem; line-height:1.2; font-weight:500; margin:1.5rem 0 1rem; max-width:28rem; }
        .lab-copy { color:#c4c7bb; font-size:.875rem; line-height:1.7; margin:0 0 1.5rem; max-width:38rem; }
        .lab-tags { display:flex; flex-wrap:wrap; gap:.5rem; margin:0 0 1.5rem; }
        .lab-tag { border:1px solid #48615b; color:#b7cec8; padding:.25rem .5rem; font-size:.75rem; }
        .lab-tag.warn { border-color:#72432c; color:var(--warning); }
        .lab-scope { position:relative; height:12rem; overflow:hidden; border:1px solid var(--line-soft); margin:0 0 1.5rem; background:
          linear-gradient(rgba(121,203,182,.05) 1px,transparent 1px),
          linear-gradient(90deg,rgba(121,203,182,.05) 1px,transparent 1px),#030807;
          background-size:1.5rem 1.5rem; }
        .lab-scope::before { content:""; position:absolute; left:0; right:0; top:55%; height:1px; background:#54605d; }
        .lab-scope::after { content:""; position:absolute; width:.75rem; height:.75rem; border:1px solid var(--accent); border-radius:50%; left:67%; top:calc(55% - .375rem); background:#080d0c; box-shadow:0 0 16px rgba(215,202,61,.4); }
        .lab-wave { position:absolute; inset:0; clip-path:polygon(0 61%,10% 59%,20% 65%,30% 41%,40% 46%,50% 38%,60% 53%,70% 51%,80% 32%,90% 36%,100% 24%,100% 25%,90% 38%,80% 34%,70% 53%,60% 55%,50% 40%,40% 48%,30% 43%,20% 67%,10% 61%,0 63%); background:var(--signal); opacity:.8; }
        .lab-scope-readout { position:absolute; left:1rem; top:1rem; color:var(--muted); font-size:.75rem; }
        .lab-scenario-footer { border-top:1px solid var(--line-soft); padding-top:1rem; margin-top:1.5rem; }

        .lab-step-head { display:grid; grid-template-columns:2rem 1fr; gap:1rem; align-items:start; border-top:1px solid var(--line-soft); padding-top:1.5rem; margin-top:1.5rem; }
        .lab-step-head b { display:grid; place-items:center; width:2rem; height:2rem; border:1px solid var(--accent); border-radius:50%; color:var(--accent); font-size:.75rem; font-weight:500; }
        .lab-step-head h3 { margin:.1rem 0 .25rem !important; }
        .lab-step-head p { color:var(--muted); font-size:.75rem; }
        .lab-builder-note { color:var(--muted); font-size:.75rem; margin-top:-.5rem; }

        .lab-dimension { margin:0 0 1.5rem; }
        .lab-dimension:last-child { margin-bottom:0; }
        .lab-dimension-label { display:flex; justify-content:space-between; color:#c4c7bb; font-size:.75rem; margin-bottom:.5rem; }
        .lab-track { height:2px; background:#48504e; position:relative; }
        .lab-track i { display:block; height:100%; background:var(--accent); }
        .lab-track i::after { content:""; display:block; float:right; width:.5rem; height:.5rem; transform:translate(50%,-.2rem); border:1px solid var(--accent); background:var(--panel); }

        .lab-path { display:flex; align-items:center; margin:0 0 1.5rem; }
        .lab-node { width:1rem; height:1rem; border:1px solid #65716e; border-radius:50%; background:var(--panel); }
        .lab-node.active { background:var(--accent); border-color:var(--accent); }
        .lab-link { height:1px; flex:1; background:#3e4845; }
        .lab-note-grid { display:grid; grid-template-columns:repeat(4,1fr); gap:1.5rem; }
        .lab-note-grid b { display:block; color:#cbd0c4; font-size:.75rem; font-weight:500; margin-bottom:.5rem; }
        .lab-note-grid p { color:var(--muted); font-size:.75rem; line-height:1.5; }

        div[data-testid="stMetric"] { background:#040908; border:1px solid var(--line-soft); padding:1rem; }
        [data-testid="stMetric"] * { color:var(--text) !important; }
        [data-testid="stMetricLabel"] * { color:var(--muted) !important; font-size:.75rem; text-transform:uppercase; letter-spacing:.06em; }
        [data-testid="stMetricValue"] * { color:var(--text) !important; font-size:1.35rem; }
        [data-testid="stMetricDelta"] * { color:var(--signal) !important; font-size:.75rem; }

        div[data-baseweb="select"] > div, div[data-baseweb="input"] > div, textarea {
          background:#030807 !important; border-color:var(--line) !important; color:var(--text) !important; border-radius:1px !important;
        }
        input, textarea { color:var(--text) !important; caret-color:var(--accent) !important; font-size:.875rem !important; }
        [data-testid="stWidgetLabel"] p { color:#c4c7bb !important; font-size:.75rem !important; text-transform:uppercase; letter-spacing:.05em; }
        [data-baseweb="tag"] { background:#1a2c28 !important; border-radius:1px !important; }
        [data-testid="stRadio"] > div { gap:.5rem; }
        [data-testid="stRadio"] label { background:#050a09; border:1px solid var(--line-soft); padding:.65rem .75rem; margin:0; min-height:2.75rem; }
        [data-testid="stRadio"] label:has(input:checked) { border-color:var(--accent); background:#11140b; }
        [data-testid="stRadio"] label:has(input:checked) > div:first-child { background:var(--accent) !important; border-color:var(--accent) !important; }
        [data-testid="stRadio"] label:has(input:checked) > div:first-child > div { background:var(--accent) !important; }
        [data-testid="stButtonGroup"] button { border:1px solid var(--line) !important; border-radius:1px !important; background:#050a09 !important; color:var(--text) !important; min-height:2.5rem; }
        [data-testid="stButtonGroup"] button p { color:var(--text) !important; }
        button[data-testid="stBaseButton-pillsActive"] { border-color:var(--accent) !important; background:#11140b !important; }
        button[data-testid="stBaseButton-pillsActive"] p { color:#eeeedc !important; }
        [data-testid="stSlider"] [role="slider"] { background:var(--accent) !important; border-color:var(--accent) !important; }
        [data-testid="stSlider"] [data-baseweb="slider"] > div > div { background:transparent !important; }
        [data-baseweb="slider"] div[style*="height: 0.25rem"] { background-image:linear-gradient(#48504e,#48504e) !important; }
        .stButton > button, .stFormSubmitButton > button {
          width:100%; border:1px solid var(--accent) !important; border-radius:1px !important;
          background:var(--accent) !important; color:#111208 !important; font-family:inherit !important;
          font-size:.75rem !important; font-weight:600 !important; letter-spacing:.06em; text-transform:uppercase;
          min-height:3rem; box-shadow:none !important;
        }
        .stButton > button:hover, .stFormSubmitButton > button:hover { color:#030500 !important; filter:brightness(1.08); }
        [data-testid="stBaseButton-secondary"] { background:transparent !important; color:var(--signal) !important; border-color:#45665e !important; }
        [data-baseweb="progress-bar"] > div > div { background:#48504e !important; }
        [data-baseweb="progress-bar"] > div > div > div { background:var(--accent) !important; }
        [data-testid="stAlert"] { background:#0b1412; border:1px solid #405d56; border-radius:1px; color:var(--text); }
        [data-testid="stAlert"]:has(a[href*="stylable_container"]), [data-testid="stAlert"]:has(a[href*="st.container"]) { display:none; }
        [data-testid="stCaptionContainer"] p { color:var(--muted) !important; font-size:.75rem; }
        hr { border-color:var(--line-soft) !important; }

        @media(max-width:900px) {
          .block-container { padding:1rem !important; }
          .lab-masthead { align-items:flex-start; flex-direction:column; }
          .lab-live { padding:0; }
          h1 { font-size:2rem !important; }
          .lab-scenario-card { min-height:auto; }
          .lab-note-grid { grid-template-columns:1fr 1fr; }
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def impact_chart(score: int) -> alt.Chart:
    periods = list(range(1, 9))
    frame = pd.DataFrame(
        {
            "period": periods * 2,
            "value": [min(96, score * (.3 + period * .09)) for period in periods]
            + [min(72, 15 + period * 5.5) for period in periods],
            "signal": ["Projected response"] * 8 + ["Reference"] * 8,
        }
    )
    return (
        alt.Chart(frame)
        .mark_line(point=alt.OverlayMarkDef(size=24, filled=True), strokeWidth=1.5)
        .encode(
            x=alt.X("period:O", title=None, axis=alt.Axis(labelColor="#929d98", domainColor="#35413e", tickColor="#35413e")),
            y=alt.Y("value:Q", title=None, scale=alt.Scale(domain=[0, 100]), axis=alt.Axis(labelColor="#929d98", gridColor="#1b2523", domain=False)),
            color=alt.Color(
                "signal:N",
                scale=alt.Scale(domain=["Projected response", "Reference"], range=["#d7ca3d", "#68736f"]),
                legend=alt.Legend(title=None, labelColor="#c4c7bb", orient="top"),
            ),
            tooltip=["signal", "period", alt.Tooltip("value", format=".0f")],
        )
        .properties(height=220)
        .configure_view(stroke=None)
        .configure(background="transparent")
    )


def signal_event_frame(events: list[dict[str, object]]) -> tuple[pd.DataFrame, bool]:
    """Return timestamped events with a cumulative sequence; preview when empty."""

    rows = [
        {
            "timestamp": row.get("created_at"),
            "signal": str(row.get("event_type") or "event")
            .replace("question_", "")
            .replace("_", " ")
            .title(),
            "question": str(row.get("question_id") or "Protocol event"),
        }
        for row in events
    ]
    frame = pd.DataFrame(rows, columns=["timestamp", "signal", "question"])
    if not frame.empty:
        frame["timestamp"] = pd.to_datetime(frame["timestamp"], utc=True, errors="coerce")
        frame = frame.dropna(subset=["timestamp"]).sort_values("timestamp").reset_index(drop=True)

    is_preview = frame.empty
    if is_preview:
        origin = st.session_state.setdefault(
            "lab_signal_preview_origin", pd.Timestamp.now(tz="UTC").floor("min")
        )
        offsets = (0, 7, 13, 22, 31, 39, 52, 64)
        signals = ("Flagged", "Flagged", "Skipped", "Flagged", "Skipped", "Flagged", "Flagged", "Skipped")
        frame = pd.DataFrame(
            {
                "timestamp": [origin + pd.Timedelta(minutes=offset) for offset in offsets],
                "signal": signals,
                "question": ["Preview event"] * len(offsets),
            }
        )

    frame["cumulative"] = range(1, len(frame) + 1)
    return frame, is_preview


def signal_event_chart(frame: pd.DataFrame) -> alt.Chart:
    signal_types = list(dict.fromkeys(str(value) for value in frame["signal"]))
    palette = ["#d7ca3d", "#e27d3e", "#79cbb6", "#929d98"]
    return (
        alt.Chart(frame)
        .mark_point(filled=True, size=78, opacity=.92, stroke="#010505", strokeWidth=1)
        .encode(
            x=alt.X(
                "timestamp:T",
                title=None,
                axis=alt.Axis(
                    labelColor="#929d98",
                    labelFontSize=11,
                    format="%H:%M",
                    tickCount=8,
                    labelOverlap=True,
                    grid=False,
                    domainColor="#35413e",
                    tickColor="#35413e",
                ),
            ),
            y=alt.Y(
                "cumulative:Q",
                title="Cumulative events",
                axis=alt.Axis(
                    labelColor="#929d98",
                    titleColor="#929d98",
                    tickMinStep=1,
                    gridColor="#1b2523",
                    domain=False,
                ),
            ),
            color=alt.Color(
                "signal:N",
                scale=alt.Scale(domain=signal_types, range=palette[: len(signal_types)]),
                legend=alt.Legend(title=None, labelColor="#c4c7bb", orient="top-right"),
            ),
            tooltip=[
                alt.Tooltip("timestamp:T", title="Recorded", format="%Y-%m-%d %H:%M"),
                alt.Tooltip("signal:N", title="Signal"),
                alt.Tooltip("question:N", title="Question"),
                alt.Tooltip("cumulative:Q", title="Cumulative"),
            ],
        )
        .properties(height=150)
        .configure_view(stroke=None)
        .configure(background="transparent")
    )


apply_lab_theme()

protocol = load_protocol()
repository = get_repository()

if "lab_result" not in st.session_state:
    st.session_state.lab_result = {
        "priority": "Perceive",
        "actors": ["Researchers", "Residents"],
        "capacities": ["Human expertise", "Knowledge & data"],
        "action": "Open inquiry",
        "intensity": 62,
        "score": 68,
    }

result = st.session_state.lab_result

st.markdown(
    """
    <div class="lab-masthead">
      <div>
        <div class="lab-kicker">Protocol Hack · social systems laboratory</div>
        <h1>COMMONS SIMULATOR</h1>
        <p>Set initial conditions. Introduce a strategic intervention. Observe the modelled system response.</p>
      </div>
      <div class="lab-live">Instrument online · run 01</div>
    </div>
    """,
    unsafe_allow_html=True,
)

try:
    recorded_signal_events = repository.list_question_feedback(protocol.session_code)
except Exception:
    recorded_signal_events = []

signal_frame, signal_is_preview = signal_event_frame(recorded_signal_events)
with lab_card("lab_signal_record"):
    section_title("00", "Signal record", "Cumulative events · one dot per event")
    st.altair_chart(signal_event_chart(signal_frame), width="stretch", theme=None)
    if signal_is_preview:
        mode_label = "No recorded events yet · preview trace"
    else:
        mode_label = f"{len(signal_frame)} recorded events · {repository_mode()} storage"
    st.caption(mode_label)

scenario_col, experiment_col = st.columns([2, 3], gap="medium")

with scenario_col:
    with lab_card("lab_scenario", "{min-height:44rem;}"):
        section_title("01", "Scenario", "Input signal")
        st.markdown(
            """
            <div class="lab-signal-code">SCN-001 · coordination threshold</div>
            <div class="lab-scenario-title">A shared resource reaches a threshold</div>
            <div class="lab-copy">Your community depends on a shared place, dataset, or service. Use is growing, maintenance is uneven, and nobody agrees who should decide what happens next.</div>
            <div class="lab-tags"><span class="lab-tag">TRUST</span><span class="lab-tag warn">CAPACITY PRESSURE</span></div>
            <div class="lab-scope"><div class="lab-wave"></div><span class="lab-scope-readout">LOAD / COORDINATION</span></div>
            """,
            unsafe_allow_html=True,
        )
        st.progress(result["score"] / 100, text="System readiness")
        reveal = st.toggle("Reveal observer note", value=False)
        if reveal:
            st.info("The actor carrying the most risk may not be the actor with the loudest voice.", icon="🔬")
        st.markdown('<div class="lab-scenario-footer"></div>', unsafe_allow_html=True)
        st.page_link("views/commons.py", label="Open live protocol →", width="stretch")

with experiment_col:
    with lab_card("lab_experiment"):
        section_title("02", "Configure an experiment", "Initial conditions")
        st.markdown(
            '<div class="lab-builder-note">You are configuring a simulated social system—not completing a questionnaire.</div>',
            unsafe_allow_html=True,
        )
        with st.form("commons_strategy_lab", border=False):
            step_title("1", "Priority", "Choose the system variable to influence first.")
            priority = st.radio(
                "Priority",
                PRIORITIES,
                index=PRIORITIES.index(result["priority"]),
                horizontal=True,
                label_visibility="collapsed",
            )

            step_title("2", "Actors", "Introduce up to three agents into the experiment.")
            actors = st.pills(
                "Actors",
                ACTORS,
                default=result["actors"],
                selection_mode="multi",
                label_visibility="collapsed",
            )

            step_title("3", "Capacities", "Activate the resources available to the system.")
            capacities = st.pills(
                "Capacities",
                CAPACITIES,
                default=result["capacities"],
                selection_mode="multi",
                label_visibility="collapsed",
            )

            step_title("4", "Intervention", "Select the first action and set its strength.")
            action = st.radio(
                "Intervention",
                ACTIONS,
                index=ACTIONS.index(result["action"]),
                horizontal=True,
                label_visibility="collapsed",
            )
            intensity = st.slider("Intervention strength", 20, 100, result["intensity"], 5)
            rationale = st.text_area(
                "Laboratory note (optional)",
                placeholder="Record the trade-off this intervention accepts…",
                height=88,
            )
            submitted = st.form_submit_button("Run simulation →", width="stretch")

        if submitted:
            if not actors or not capacities:
                st.error("Introduce at least one actor and activate one capacity.")
            elif len(actors) > 3:
                st.error("Limit the experiment to three actors so the initial condition remains legible.")
            elif len(capacities) > 4:
                st.error("Activate no more than four capacities for this run.")
            else:
                score = min(96, round(28 + intensity * .38 + len(actors) * 5 + len(capacities) * 4))
                st.session_state.lab_result = {
                    "priority": priority,
                    "actors": list(actors),
                    "capacities": list(capacities),
                    "action": action,
                    "intensity": intensity,
                    "score": score,
                    "rationale": rationale,
                }
                st.toast("System response recalculated", icon="🔬")
                st.rerun()

st.markdown('<div style="height:8px"></div>', unsafe_allow_html=True)
section_title("03", "System state", "Modelled response · not a forecast")

dimensions_col, response_col = st.columns([2, 3], gap="medium")
with dimensions_col:
    with lab_card("lab_dimensions"):
        st.markdown("<h3>Strategic dimensions</h3>", unsafe_allow_html=True)
        st.markdown('<div style="height:24px"></div>', unsafe_allow_html=True)
        for left, right, value in (
            ("Protection", "Expansion", 58),
            ("Centralised", "Distributed", 72),
            ("Rapid response", "Deliberate", 45),
            ("Technical", "Social", 66),
        ):
            st.markdown(
                f'<div class="lab-dimension"><div class="lab-dimension-label"><span>{left}</span><span>{right}</span></div><div class="lab-track"><i style="width:{value}%"></i></div></div>',
                unsafe_allow_html=True,
            )
        st.markdown("<h3>Experiment path</h3>", unsafe_allow_html=True)
        st.markdown('<div style="height:16px"></div>', unsafe_allow_html=True)
        active_step = PRIORITIES.index(result["priority"])
        nodes: list[str] = []
        for index in range(4):
            nodes.append(f'<span class="lab-node {"active" if index == active_step else ""}"></span>')
            if index < 3:
                nodes.append('<span class="lab-link"></span>')
        st.markdown(f'<div class="lab-path">{"".join(nodes)}</div>', unsafe_allow_html=True)
        st.markdown(
            f'<div class="lab-tags"><span class="lab-tag">{result["priority"].upper()}</span><span class="lab-tag">{result["action"].upper()}</span></div>',
            unsafe_allow_html=True,
        )

with response_col:
    with lab_card("lab_response"):
        st.markdown("<h3>Response over time</h3>", unsafe_allow_html=True)
        st.markdown('<div style="height:16px"></div>', unsafe_allow_html=True)
        readiness, actors_metric, capacity_metric = st.columns(3)
        readiness.metric("Readiness", f"{result['score']}%", "+6")
        actors_metric.metric("Actors", len(result["actors"]), "introduced")
        capacity_metric.metric("Capacities", len(result["capacities"]), "active")
        st.altair_chart(impact_chart(result["score"]), width="stretch", theme=None)

with lab_card("lab_notes"):
    st.markdown(
        """
        <div class="lab-note-grid">
          <div><b>OPENNESS</b><p>Knowledge remains inspectable.</p></div>
          <div><b>COLLABORATION</b><p>Agents can alter one another.</p></div>
          <div><b>CARE</b><p>Human cost remains observable.</p></div>
          <div><b>SUSTAINABILITY</b><p>Long-term effects stay in frame.</p></div>
        </div>
        """,
        unsafe_allow_html=True,
    )
