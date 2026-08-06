"""A quiet, guided entrance for creating a semantic trajectory plan."""

from __future__ import annotations

from datetime import date, datetime, timedelta
import base64
import html
import json
from uuid import uuid4

import plotly.graph_objects as go
import streamlit as st
import streamlit.components.v1 as components
import yaml

from protocol.timeline import END_POINT, sample_trajectory
from protocol.timeline_plan import (
    QUALITATIVE_TIME_ANCHORS,
    TIME_UNITS_IN_DAYS,
    build_plan_payload,
    linear_time_ticks,
    plan_summary,
)
from protocol.trajectory_schema import (
    DEFAULT_CAMERA,
    LOCAL_STORAGE_LATEST_KEY,
    load_trajectory_yaml,
    normalise_trajectory_document,
)


STATE_PREFIX = "sketch_plan_"
ACTIVE_TRAJECTORY_KEY = "timeline_active_benchmark"
STAGES = ("identity", "now", "goal", "landing", "time", "confirm")
STEP_LABELS = ("Plan", "Now", "Goal", "Landing", "Time", "Ready")
PERSISTED_FIELDS = (
    "title",
    "description",
    "initial_condition",
    "goal_statement",
    "goal_conditions",
    "landing_mode",
    "guided_horizon",
    "guided_value",
    "guided_unit",
    "fixed_kind",
    "fixed_value",
    "fixed_unit",
    "fixed_date",
    "temporal_mode",
    "linear_unit",
)


def _key(name: str) -> str:
    return f"{STATE_PREFIX}{name}"


def _start_new_plan() -> None:
    for key in tuple(st.session_state):
        if str(key).startswith(STATE_PREFIX):
            del st.session_state[key]
    st.session_state[_key("created_at")] = datetime.now().astimezone().isoformat()
    st.session_state[_key("plan_id")] = uuid4().hex
    st.session_state[_key("stage")] = "identity"


def _set_stage(stage: str) -> None:
    _persist_inputs()
    st.session_state[_key("stage")] = stage


def _persist_inputs() -> None:
    for name in PERSISTED_FIELDS:
        widget_key = _key(name)
        if widget_key in st.session_state:
            st.session_state[_key(f"value_{name}")] = st.session_state[
                widget_key
            ]


def _value(name: str, default: object = "") -> object:
    return st.session_state.get(
        _key(name),
        st.session_state.get(_key(f"value_{name}"), default),
    )


def _valid_choice(value: object, options: tuple[str, ...]) -> str | None:
    clean = str(value) if value is not None else ""
    return clean if clean in options else None


def _render_progress(stage: str) -> None:
    current = STAGES.index(stage)
    items: list[str] = []
    for index, label in enumerate(STEP_LABELS):
        if index < current:
            marker, state = "✓", "done"
        elif index == current:
            marker, state = "→", "current"
        else:
            marker, state = "○", "pending"
        items.append(
            f'<div class="plan-step {state}"><b>{marker}</b>'
            f"<span>{html.escape(label)}</span></div>"
        )
    st.markdown(
        f'<div class="plan-steps">{"".join(items)}</div>',
        unsafe_allow_html=True,
    )


def _step_actions(
    *,
    back: str | None,
    onward: str,
    onward_label: str,
    disabled: bool = False,
) -> None:
    back_column, onward_column = st.columns([1, 2])
    with back_column:
        if back is None:
            if st.button("← Entrance", key="plan_back_entrance", width="stretch"):
                st.session_state[_key("stage")] = "entrance"
                st.rerun()
        elif st.button(
            "← Back",
            key=f"plan_back_{back}",
            width="stretch",
        ):
            _set_stage(back)
            st.rerun()
    with onward_column:
        if st.button(
            onward_label,
            key=f"plan_next_{onward}",
            type="primary",
            disabled=disabled,
            width="stretch",
        ):
            _set_stage(onward)
            st.rerun()


def _payload_from_state() -> dict[str, object]:
    landing_mode = _valid_choice(
        _value("landing_mode", None),
        ("Open", "Guided", "Fixed"),
    ) or "Open"
    temporal_mode = _valid_choice(
        _value("temporal_mode", None),
        ("Qualitative", "Linear"),
    ) or "Qualitative"
    return build_plan_payload(
        plan_id=str(st.session_state.get(_key("plan_id")) or ""),
        title=str(_value("title") or ""),
        description=str(_value("description") or ""),
        initial_condition=str(_value("initial_condition") or ""),
        goal_statement=str(_value("goal_statement") or ""),
        goal_conditions=str(_value("goal_conditions") or ""),
        landing_mode=landing_mode,
        temporal_mode=temporal_mode,
        created_at=str(st.session_state[_key("created_at")]),
        guided_horizon=str(_value("guided_horizon", "A few weeks")),
        guided_value=int(_value("guided_value", 3) or 3),
        guided_unit=str(_value("guided_unit", "Weeks")),
        fixed_kind=str(_value("fixed_kind", "Duration")),
        fixed_value=int(_value("fixed_value", 6) or 6),
        fixed_unit=str(_value("fixed_unit", "Weeks")),
        fixed_date=_value("fixed_date", None),
        linear_unit=str(_value("linear_unit", "Weeks")),
    )


def _preview_figure(payload: dict[str, object]) -> go.Figure:
    x, y, z = sample_trajectory([], samples_per_segment=90)
    figure = go.Figure()
    figure.add_trace(
        go.Scatter3d(
            x=x,
            y=y,
            z=z,
            mode="lines",
            line={"color": "#edf2ed", "width": 8},
            hoverinfo="skip",
            showlegend=False,
        )
    )
    figure.add_trace(
        go.Scatter3d(
            x=[x[0], END_POINT[0]],
            y=[y[0], END_POINT[1]],
            z=[z[0], END_POINT[2]],
            mode="markers+text",
            marker={
                "size": [7, 9],
                "color": ["#edf2ed", "#020707"],
                "line": {"color": "#dfe875", "width": 2},
            },
            text=["NOW", "GOAL"],
            textposition=["bottom center", "top center"],
            textfont={"color": "#b9c8c2", "size": 10},
            hoverinfo="skip",
            showlegend=False,
        )
    )
    qualitative = payload["temporal_mode"] == "qualitative"
    if qualitative:
        tick_values = [value for _, value in QUALITATIVE_TIME_ANCHORS]
        tick_text = [label.upper() for label, _ in QUALITATIVE_TIME_ANCHORS]
    else:
        start_day = date.fromisoformat(str(payload["start_date"]))
        end_day = (
            date.fromisoformat(str(payload["end_date"]))
            if payload.get("end_date")
            else start_day + timedelta(days=int(payload["horizon_days"]))
        )
        ticks = linear_time_ticks(
            start_date=start_day,
            end_date=end_day,
            unit=str(payload.get("time_unit") or "Days"),
        )
        tick_values = [position for position, _ in ticks]
        tick_text = [label for _, label in ticks]
    figure.update_layout(
        height=520,
        margin={"l": 0, "r": 0, "t": 4, "b": 0},
        paper_bgcolor="#020707",
        scene={
            "bgcolor": "#020707",
            "camera": DEFAULT_CAMERA,
            "aspectmode": "manual",
            "aspectratio": {"x": 2.4, "y": 0.6, "z": 1.0},
            "xaxis": {
                "title": "HORIZON" if qualitative else "TIME",
                "range": [0, 1],
                "tickvals": tick_values,
                "ticktext": tick_text,
                "gridcolor": "#17231f",
                "linecolor": "#40524b",
                "tickfont": {"color": "#9aaca5", "size": 12},
                "showbackground": False,
            },
            "yaxis": {
                "title": "ENTROPY",
                "range": [-0.12, 0.12],
                "gridcolor": "#17231f",
                "linecolor": "#40524b",
                "showticklabels": False,
                "showbackground": False,
            },
            "zaxis": {
                "title": "ENERGY",
                "range": [-0.02, 0.48],
                "gridcolor": "#17231f",
                "linecolor": "#40524b",
                "showticklabels": False,
                "showbackground": False,
            },
        },
    )
    return figure


def _enter_trajectory(payload: dict[str, object]) -> None:
    preserve_trajectory = bool(
        st.session_state.pop(_key("preserve_trajectory"), False)
    )
    if not preserve_trajectory:
        for key in tuple(st.session_state):
            if str(key).startswith("timeline_game_"):
                del st.session_state[key]
    landing_widget = {
        "open": "Open",
        "guided": "Guided",
        "planned": "Planned",
    }[str(payload["landing_mode"])]
    st.session_state[ACTIVE_TRAJECTORY_KEY] = payload
    st.session_state["timeline_game_landing_mode"] = landing_widget
    st.switch_page("views/test_timeline_game.py")


def _restore_document(document: dict[str, object]) -> None:
    normalised = normalise_trajectory_document(document)
    plan = dict(normalised["plan"])
    for key in tuple(st.session_state):
        if str(key).startswith("timeline_game_"):
            del st.session_state[key]
    st.session_state[ACTIVE_TRAJECTORY_KEY] = plan
    st.session_state["timeline_game_events"] = list(
        normalised["primitives"]
    )
    st.session_state["timeline_game_uncertainties"] = list(
        normalised["uncertainty"]
    )
    st.session_state["timeline_game_landing_mode"] = {
        "open": "Open",
        "guided": "Guided",
        "planned": "Planned",
    }.get(str(plan.get("landing_mode") or "open"), "Open")
    st.session_state["timeline_game_save_status"] = "Saved on this device"
    st.session_state["timeline_game_imported_camera"] = dict(
        normalised["view"]["camera"]
    )
    st.query_params.clear()
    st.switch_page("views/test_timeline_game.py")


def _render_open_saved_plan() -> None:
    components.html(
        f"""
        <a id="open-plan" target="_blank" rel="noopener" aria-disabled="true">Open a saved plan</a>
        <script>
        (() => {{
          const latestKey = {LOCAL_STORAGE_LATEST_KEY!r};
          const link = document.getElementById("open-plan");
          const raw = window.parent.localStorage.getItem(latestKey);
          link.textContent = raw ? "Open the latest saved plan ↗" : "No saved plan on this device";
          if (raw) {{
            const encoded = btoa(unescape(encodeURIComponent(raw)))
              .replace(/[+]/g, "-").replace(/[/]/g, "_").replace(/=+$/g, "");
            link.href = "/test-sketch-plan?restore=" + encoded;
            link.setAttribute("aria-disabled", "false");
          }}
        }})();
        </script>
        <style>
        html,body {{ margin:0; background:transparent; font-family:"IBM Plex Mono",monospace; }}
        a {{
          box-sizing:border-box; display:flex; align-items:center; justify-content:center;
          width:100%; min-height:49px; border-radius:999px;
          background:#06100e; color:#a8b9b3; border:1px solid #344941;
          font-size:16px; cursor:pointer; text-decoration:none; transition:all 120ms ease;
        }}
        a[aria-disabled="false"]:hover {{ color:#edf2ed; border-color:#8ca299; transform:translateY(-1px); }}
        a[aria-disabled="false"]:active {{ transform:scale(.98); }}
        a[aria-disabled="true"] {{
          pointer-events:none; cursor:not-allowed; background:#171b15; color:#7f887b;
          border:1px dashed #596158;
        }}
        </style>
        """,
        height=52,
    )


def _apply_theme() -> None:
    st.markdown(
        """
        <style>
        @import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;500;600&display=swap');
        [data-testid="stSidebar"], [data-testid="stSidebarCollapsedControl"] { display:none !important; }
        [data-testid="stHeader"], [data-testid="stToolbar"], #MainMenu, footer { display:none; }
        .stApp {
          background:radial-gradient(circle at 76% 4%,rgba(92,143,130,.14),transparent 31rem),#020707;
          color:#edf2ed;
        }
        :root {
          --plan-action:#c7d66d; --plan-action-hover:#d4e47b; --plan-action-text:#11160e;
          --type-hero:clamp(42px,5.2vw,72px);
          --type-page-title:clamp(32px,3.5vw,48px);
          --type-section:clamp(24px,2.2vw,32px);
          --type-control:20px; --type-button:17px;
          --type-body:clamp(15px,1.1vw,17px);
          --type-helper:14px; --type-option:13px; --type-meta:12px;
        }
        .block-container { max-width:1280px; padding:2.2rem 2rem 4rem; }
        html, body, .stApp, button, input, textarea { font-family:"IBM Plex Mono",monospace !important; }
        h1, h2, h3, p, label { color:#edf2ed !important; }
        button p { color:inherit !important; }
        .plan-entrance { min-height:72vh; display:flex; flex-direction:column; justify-content:center; }
        .plan-entrance small, .plan-stage-head small, .plan-confirm-copy small {
          color:#dfe875; text-transform:uppercase; letter-spacing:.17em; font-size:var(--type-meta);
        }
        .plan-entrance h1 {
          max-width:11ch; margin:.6rem 0 1rem; font-size:var(--type-hero) !important;
          font-weight:780; line-height:.98; letter-spacing:-.055em;
        }
        .plan-entrance > p { max-width:61ch; color:#94a69f !important; line-height:1.5; font-size:var(--type-body); }
        .plan-answers { display:grid; grid-template-columns:repeat(3,1fr); gap:1px; margin:2.2rem 0; background:#263832; border:1px solid #263832; }
        .plan-answers div { background:#050d0b; padding:1rem; }
        .plan-answers b { display:block; color:#dfe875; font-size:var(--type-helper); margin-bottom:.5em; }
        .plan-answers span { color:#9aacA5; font-size:var(--type-body); line-height:1.5; }
        .plan-actions { margin-top:.3rem; }
        .plan-steps { display:grid; grid-template-columns:repeat(6,1fr); gap:.4rem; margin:.4rem 0 2.5rem; }
        .plan-step { display:flex; gap:.5rem; align-items:center; padding:.7rem .65rem; border-bottom:2px solid #263832; color:#61736c; font-size:.63rem; }
        .plan-step.done { color:#8fa39b; border-color:#46665b; }
        .plan-step.done b { color:#78d6a7; }
        .plan-step.current { color:#edf2ed; border-color:#dfe875; background:#07110f; }
        .plan-step.current b { color:#dfe875; }
        .plan-stage-head { max-width:58rem; margin-bottom:2rem; }
        .plan-stage-head h1 { max-width:11.5ch; font-size:clamp(42px,5.2vw,64px) !important; font-weight:780; line-height:.98; letter-spacing:-.045em; margin:.55rem 0 1rem; }
        .plan-stage-head p { color:#91a39c !important; max-width:65ch; line-height:1.5; font-size:var(--type-body); }
        .plan-examples { color:#70827b; font-size:var(--type-helper); line-height:1.45; margin:.5em 0 1.5em; }
        [data-testid="stTextInput"] input, [data-testid="stTextArea"] textarea,
        div[data-baseweb="input"] > div { background:#06100e !important; color:#edf2ed !important; border-color:#3b5048 !important; }
        input, textarea { color:#edf2ed !important; caret-color:#dfe875 !important; }
        [data-testid="stWidgetLabel"] p { color:#b2c0ba !important; font-size:var(--type-helper) !important; line-height:1.45; letter-spacing:.03em; }
        [data-testid="stButtonGroup"] button { background:#04100d !important; color:#9fb1aa !important; border-color:#354a42 !important; min-height:52px; transition:all 120ms ease !important; }
        [data-testid="stButtonGroup"] button p, .stButton button p { font-size:var(--type-button) !important; line-height:1.2; }
        [data-testid="stButtonGroup"] button:hover { background:#0b1713 !important; color:#edf2ed !important; transform:translateY(-1px); }
        button[data-testid="stBaseButton-segmented_controlActive"] { background:#dfe875 !important; color:#11160e !important; border-color:#dfe875 !important; box-shadow:0 0 0 2px rgba(223,232,117,.13) !important; }
        .stButton button { transition:transform 90ms ease,filter 120ms ease,border-color 120ms ease !important; }
        .stButton button:hover { transform:translateY(-1px); }
        .stButton button:active { transform:scale(.97) !important; }
        .stButton button:disabled { opacity:.64 !important; color:#9aa59f !important; background:#141a17 !important; border:1px dashed #4e5a54 !important; cursor:not-allowed !important; }
        [data-testid="stExpander"] { border-color:#344740 !important; background:#040b09 !important; border-radius:10px !important; }
        [data-testid="stExpander"] summary:hover { background:#0a1512 !important; }
        [class*="st-key-plan_next_"] button, .st-key-plan_sketch_new button, .st-key-plan_enter_field button {
          min-height:52px !important; background:var(--plan-action) !important; color:var(--plan-action-text) !important; border:0 !important; box-shadow:0 10px 30px rgba(0,0,0,.25) !important;
        }
        [class*="st-key-plan_next_"] button p, .st-key-plan_sketch_new button p, .st-key-plan_enter_field button p { color:var(--plan-action-text) !important; -webkit-text-fill-color:var(--plan-action-text) !important; text-shadow:none !important; }
        [class*="st-key-plan_next_"] button:hover, .st-key-plan_sketch_new button:hover, .st-key-plan_enter_field button:hover { background:var(--plan-action-hover) !important; }
        [class*="st-key-plan_back_"] button, .st-key-plan_try_benchmark button, .st-key-plan_open_saved button {
          min-height:52px !important; background:#06100e !important; color:#a8b9b3 !important; border:1px solid #344941 !important; box-shadow:none !important;
        }
        .plan-landing-copy { border:1px solid #2a3b35; background:#05100d; padding:1rem; margin:.5em 0 1.5em; color:#a4b3ad; font-size:var(--type-helper); line-height:1.45; }
        .plan-review { display:grid; grid-template-columns:repeat(3,1fr); gap:1px; background:#253731; border:1px solid #253731; margin:.5rem 0 1.2rem; }
        .plan-review div { min-width:0; background:#050d0b; padding:.8rem; }
        .plan-review small { display:block; color:#6e817a; text-transform:uppercase; letter-spacing:.1em; font-size:.55rem; margin-bottom:.3rem; }
        .plan-review b { color:#dce7e1; font-size:.68rem; font-weight:500; overflow-wrap:anywhere; }
        [data-testid="stPlotlyChart"] { border:1px solid #1f302a; border-radius:12px; overflow:hidden; box-shadow:0 0 70px rgba(83,139,124,.08); }
        @media(max-width:900px) {
          :root { --type-hero:48px; --type-control:18px; --type-button:16px; --type-helper:13px; }
          .block-container { padding:1.2rem 1rem 3rem; }
          .plan-answers,.plan-review { grid-template-columns:1fr; }
          .plan-steps { grid-template-columns:repeat(3,1fr); }
          .plan-stage-head h1 { font-size:48px !important; }
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


_apply_theme()
restore_value = st.query_params.get("restore")
if restore_value:
    try:
        encoded = str(restore_value)
        encoded += "=" * (-len(encoded) % 4)
        restored_json = base64.urlsafe_b64decode(encoded).decode("utf-8")
        restored_source = json.loads(restored_json)
        if not isinstance(restored_source, dict):
            raise ValueError("The saved trajectory is not an object.")
        _restore_document(restored_source)
    except (ValueError, json.JSONDecodeError, UnicodeDecodeError) as exc:
        st.query_params.clear()
        st.error(f"The locally saved plan could not be restored: {exc}")

stage = str(st.session_state.get(_key("stage")) or "entrance")

if stage == "entrance":
    st.markdown(
        """
        <div class="plan-entrance">
          <small>Trajectory planner · experimental</small>
          <h1>Sketch a new plan</h1>
          <p>Turn a plan into a trajectory from now towards a goal. Begin with meaning; dates only appear when they genuinely help.</p>
          <div class="plan-answers">
            <div><b>What is this?</b><span>A tool for turning a plan into a trajectory through time.</span></div>
            <div><b>Why use it?</b><span>Make milestones, actions, uncertainty, energy and redirection visible.</span></div>
            <div><b>How does it work?</b><span>Describe now, define the goal, then shape the path between them.</span></div>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    with st.container(key="plan_actions"):
        if st.button(
            "Sketch a new plan",
            key="plan_sketch_new",
            type="primary",
            width="stretch",
        ):
            _start_new_plan()
            st.rerun()
        secondary_left, secondary_right = st.columns(2)
        with secondary_left:
            _render_open_saved_plan()
        with secondary_right:
            if st.button(
                "Try a benchmark",
                key="plan_try_benchmark",
                width="stretch",
            ):
                st.switch_page("views/test_timeline_benchmarks.py")
        with st.expander("Import a trajectory YAML", expanded=False):
            uploaded_plan = st.file_uploader(
                "Trajectory YAML",
                type=("yaml", "yml"),
                key="plan_import_yaml",
                label_visibility="collapsed",
            )
            if uploaded_plan is not None:
                try:
                    imported_document = load_trajectory_yaml(
                        uploaded_plan.getvalue()
                    )
                except (ValueError, yaml.YAMLError) as exc:
                    st.error(f"This trajectory YAML cannot be opened: {exc}")
                else:
                    st.caption(
                        f"Ready to open · {imported_document['plan']['title']}"
                    )
                    if st.button(
                        "Open imported trajectory",
                        key="plan_open_import",
                        type="primary",
                        width="stretch",
                    ):
                        _restore_document(imported_document)
else:
    _render_progress(stage)

    if stage == "identity":
        st.markdown(
            """
            <div class="plan-stage-head"><small>Step 1 · plan identity</small><h1>What are you trying to make happen?</h1><p>Name the possibility before any geometry appears.</p></div>
            """,
            unsafe_allow_html=True,
        )
        title = st.text_input(
            "Short title",
            value=str(_value("title")),
            max_chars=64,
            placeholder="Launch a website",
            key=_key("title"),
        )
        st.text_area(
            "One-sentence description · optional",
            value=str(_value("description")),
            max_chars=180,
            placeholder="A clear sentence about what this plan is for.",
            key=_key("description"),
        )
        st.markdown(
            '<div class="plan-examples">Try: Organise a dinner · Launch a website · Prepare a workshop · Move house · Start a collective initiative</div>',
            unsafe_allow_html=True,
        )
        _step_actions(
            back=None,
            onward="now",
            onward_label="Establish now →",
            disabled=not title.strip(),
        )

    elif stage == "now":
        st.markdown(
            """
            <div class="plan-stage-head"><small>Step 2 · beginning</small><h1>What is true now?</h1><p>Every trajectory begins now by definition. Describe the initial condition. There is no start date to configure.</p></div>
            """,
            unsafe_allow_html=True,
        )
        initial = st.text_area(
            "Initial condition",
            value=str(_value("initial_condition")),
            max_chars=220,
            placeholder="I have an idea but no team.",
            key=_key("initial_condition"),
        )
        st.markdown(
            '<div class="plan-examples">Examples: The manuscript exists as a draft. · The guests are invited but nothing is prepared. · We have no venue yet.</div>',
            unsafe_allow_html=True,
        )
        _step_actions(
            back="identity",
            onward="goal",
            onward_label="Define the goal →",
            disabled=not initial.strip(),
        )

    elif stage == "goal":
        st.markdown(
            """
            <div class="plan-stage-head"><small>Step 3 · goal</small><h1>What would count as arrival?</h1><p>The goal is semantic first. It does not need a date.</p></div>
            """,
            unsafe_allow_html=True,
        )
        goal = st.text_input(
            "Goal statement",
            value=str(_value("goal_statement")),
            max_chars=96,
            placeholder="The prototype is publicly accessible.",
            key=_key("goal_statement"),
        )
        st.text_area(
            "Conditions of success · optional",
            value=str(_value("goal_conditions")),
            max_chars=220,
            placeholder="What else must be true for this to feel complete?",
            key=_key("goal_conditions"),
        )
        _step_actions(
            back="now",
            onward="landing",
            onward_label="Choose how to land →",
            disabled=not goal.strip(),
        )

    elif stage == "landing":
        st.markdown(
            """
            <div class="plan-stage-head"><small>Step 4 · landing</small><h1>How precisely is arrival timed?</h1><p>This changes the temporal conditions of the goal, not the goal itself.</p></div>
            """,
            unsafe_allow_html=True,
        )
        landing_options = ("Open", "Guided", "Fixed")
        landing = st.segmented_control(
            "Landing mode",
            options=landing_options,
            default=_valid_choice(_value("landing_mode", None), landing_options),
            key=_key("landing_mode"),
            width="stretch",
        )
        if landing == "Open":
            st.markdown(
                '<div class="plan-landing-copy"><b>Open</b><br>The goal is known, but there is no target date.</div>',
                unsafe_allow_html=True,
            )
        elif landing == "Guided":
            st.markdown(
                '<div class="plan-landing-copy"><b>Guided</b><br>A broad horizon is known, without pretending it is an exact date.</div>',
                unsafe_allow_html=True,
            )
            guided_units = ("Weeks", "Months", "Years")
            current_guided_unit = _valid_choice(
                _value("guided_unit", "Weeks"),
                guided_units,
            ) or "Weeks"
            st.selectbox(
                "Approximate unit",
                options=guided_units,
                index=guided_units.index(current_guided_unit),
                key=_key("guided_unit"),
            )
            st.number_input(
                "Approximately how many?",
                min_value=1,
                max_value=100,
                value=max(1, int(_value("guided_value", 3) or 3)),
                step=1,
                key=_key("guided_value"),
            )
        elif landing == "Fixed":
            st.markdown(
                '<div class="plan-landing-copy"><b>Fixed</b><br>A date or measurable duration is part of the plan.</div>',
                unsafe_allow_html=True,
            )
            fixed_kind_options = ("Duration", "Date")
            fixed_kind = st.segmented_control(
                "Specify by",
                options=fixed_kind_options,
                default=_valid_choice(
                    _value("fixed_kind", "Duration"),
                    fixed_kind_options,
                ) or "Duration",
                key=_key("fixed_kind"),
                width="stretch",
            )
            if fixed_kind == "Duration":
                value_column, unit_column = st.columns([1, 2])
                with value_column:
                    st.number_input(
                        "Amount",
                        min_value=1,
                        max_value=500,
                        value=max(1, int(_value("fixed_value", 6) or 6)),
                        key=_key("fixed_value"),
                    )
                with unit_column:
                    fixed_units = tuple(TIME_UNITS_IN_DAYS)
                    current_fixed_unit = _valid_choice(
                        _value("fixed_unit", "Weeks"),
                        fixed_units,
                    ) or "Weeks"
                    st.selectbox(
                        "Unit",
                        options=fixed_units,
                        index=fixed_units.index(current_fixed_unit),
                        key=_key("fixed_unit"),
                    )
            else:
                st.date_input(
                    "Landing date",
                    value=_value(
                        "fixed_date",
                        date.today() + timedelta(days=42),
                    ),
                    min_value=date.today() + timedelta(days=1),
                    key=_key("fixed_date"),
                )
        _step_actions(
            back="goal",
            onward="time",
            onward_label="Choose the time language →",
            disabled=landing not in landing_options,
        )

    elif stage == "time":
        st.markdown(
            """
            <div class="plan-stage-head"><small>Step 5 · time language</small><h1>How should this journey speak about time?</h1><p>Qualitative time uses meaningful horizons. Linear time uses elapsed duration or calendar dates.</p></div>
            """,
            unsafe_allow_html=True,
        )
        temporal_options = ("Qualitative", "Linear")
        temporal_mode = st.segmented_control(
            "Time language",
            options=temporal_options,
            default=_valid_choice(
                _value("temporal_mode", None),
                temporal_options,
            ),
            key=_key("temporal_mode"),
            width="stretch",
        )
        if temporal_mode == "Qualitative":
            st.markdown(
                '<div class="plan-landing-copy"><b>Now · Soon · Later · Sometime · Eventually · Landing</b><br>Meaningful horizons with deliberately non-uniform spacing.</div>',
                unsafe_allow_html=True,
            )
        elif temporal_mode == "Linear":
            st.markdown(
                '<div class="plan-landing-copy"><b>Linear timeline</b><br>Elapsed intervals or calendar dates, spaced in proportion to time.</div>',
                unsafe_allow_html=True,
            )
            linear_units = tuple(TIME_UNITS_IN_DAYS)
            current_linear_unit = _valid_choice(
                _value("linear_unit", "Weeks"),
                linear_units,
            ) or "Weeks"
            st.selectbox(
                "Preferred unit",
                options=linear_units,
                index=linear_units.index(current_linear_unit),
                key=_key("linear_unit"),
            )
        _step_actions(
            back="landing",
            onward="confirm",
            onward_label="Generate the path →",
            disabled=temporal_mode not in temporal_options,
        )

    else:
        payload = _payload_from_state()
        st.markdown(
            """
            <div class="plan-confirm-copy"><small>Initial trajectory</small><h1>Your path now exists.</h1><p>The endpoints are clear. The curve is provisional and will change as you add actions, events, milestones and uncertainty.</p></div>
            """,
            unsafe_allow_html=True,
        )
        summary = "".join(
            f"<div><small>{html.escape(label)}</small><b>{html.escape(value)}</b></div>"
            for label, value in plan_summary(payload)
        )
        st.markdown(
            f'<div class="plan-review">{summary}</div>',
            unsafe_allow_html=True,
        )
        st.plotly_chart(
            _preview_figure(payload),
            width="stretch",
            config={"displayModeBar": False, "displaylogo": False},
            key="plan_initial_trajectory",
        )
        back_column, enter_column = st.columns([1, 2])
        with back_column:
            if st.button("← Time language", key="plan_back_time", width="stretch"):
                _set_stage("time")
                st.rerun()
        with enter_column:
            if st.button(
                "Enter the trajectory field",
                key="plan_enter_field",
                type="primary",
                width="stretch",
            ):
                _enter_trajectory(payload)
