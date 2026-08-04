"""Fixed Streamlit laboratory shell for any validated experiment definition."""

from __future__ import annotations

import html
import json
from pathlib import Path
import time
from typing import Any

import streamlit as st

from protocol import access_key_hash
from protocol.domain import utc_now_iso

from .atlas import ProtocolAtlas
from .engine import Command, ProtocolCommandError, Replay, replay
from .models import ExperimentDefinition, FailureScenario
from .reflection_engine import FieldNote, build_field_note, export_field_note
from .visual_engine import sequence_rows


LAB_CYCLE = (
    "Question",
    "Need",
    "Archaeology",
    "Observe",
    "Expand",
    "Execute",
    "Break",
    "Understand",
    "Field notes",
    "Join us",
)


def _state_key(experiment: ExperimentDefinition, name: str) -> str:
    return f"protocol_lab_{name}_{experiment.id}"


def _humanize(value: str) -> str:
    return str(value).replace("_", " ").strip().capitalize()


def _apply_styles() -> None:
    st.markdown(
        """
        <style>
        :root {
          --lab-bg:#090d0e; --lab-panel:#0d1213; --lab-panel-2:#111718;
          --lab-line:#283031; --lab-text:#d8ded9; --lab-muted:#7e8984;
          --lab-acid:#d8f36a; --lab-yellow:#e6d858; --lab-orange:#f69a56;
          --lab-red:#e06f67; --lab-cyan:#8fcfc1;
        }
        .stApp { background:radial-gradient(circle at 54% -15%,#172021 0,#0a0e0f 38%,#070a0b 100%) !important; color:var(--lab-text) !important; }
        [data-testid="stSidebar"] { display:none !important; }
        [data-testid="stHeader"] { display:none !important; }
        .block-container { width:100%; max-width:none !important; padding:1rem 1.15rem 2rem !important; }
        .stApp, .stApp p, .stApp label, .stApp [data-testid="stCaptionContainer"] { color:var(--lab-text); }
        .stApp h1, .stApp h2, .stApp h3 { color:var(--lab-text) !important; font-family:"DM Mono",monospace !important; letter-spacing:.01em !important; }
        .stApp h1 { font-size:clamp(1.7rem,3vw,2.65rem) !important; line-height:1.05 !important; }
        .stApp h2 { font-size:1.25rem !important; }
        .stApp h3 { font-size:.82rem !important; text-transform:uppercase; letter-spacing:.08em !important; }
        .lab-kicker, .lab-provenance, .lab-label { font-family:"DM Mono",monospace; text-transform:uppercase; letter-spacing:.09em; font-size:.63rem; color:var(--lab-muted); }
        .lab-topbar { display:flex; align-items:center; justify-content:space-between; gap:1rem; padding:.35rem .2rem .8rem; border-bottom:1px solid var(--lab-line); font-family:"DM Mono",monospace; text-transform:uppercase; letter-spacing:.08em; font-size:.7rem; }
        .lab-topbar b { color:var(--lab-text); font-weight:500; }
        .lab-topbar span:last-child { color:var(--lab-acid); }
        .st-key-lab_rail, .st-key-lab_workspace, .st-key-lab_telemetry { border:1px solid var(--lab-line); border-radius:8px; background:linear-gradient(145deg,rgba(17,23,24,.96),rgba(10,14,15,.98)); min-height:76vh; padding:1rem; box-shadow:inset 0 1px 0 rgba(255,255,255,.025); }
        .lab-brand { font-family:"DM Mono",monospace; font-size:1.05rem; font-weight:600; letter-spacing:.08em; margin:.1rem 0 1.55rem; }
        .lab-prompt { color:var(--lab-acid); font-size:1.1rem; margin-top:.25rem; }
        .lab-rail-section { margin:1.2rem 0 .45rem; padding-top:.85rem; border-top:1px solid var(--lab-line); font-family:"DM Mono",monospace; color:var(--lab-muted); font-size:.58rem; text-transform:uppercase; letter-spacing:.08em; }
        .lab-function-list { display:grid; gap:.28rem; }
        .lab-function-item { display:flex; align-items:center; gap:.55rem; padding:.48rem .55rem; border:1px solid transparent; border-radius:5px; color:#aab3ae; font-family:"DM Mono",monospace; font-size:.66rem; }
        .lab-function-item::before { content:"◇"; color:var(--lab-muted); }
        .lab-function-item.active { border-color:#3b4341; background:rgba(216,243,106,.08); color:var(--lab-acid); }
        .lab-function-item.active::before { content:"▣"; color:var(--lab-acid); }
        .lab-objective { border:1px solid var(--lab-line); border-radius:6px; padding:.8rem; font-size:.72rem; line-height:1.5; color:#c5cdc8; }
        .lab-objective b { display:block; color:var(--lab-acid); font-family:"DM Mono",monospace; font-size:.6rem; margin-top:.65rem; }
        .lab-route-link { display:block; color:#aab3ae !important; text-decoration:none; font-family:"DM Mono",monospace; font-size:.65rem; padding:.4rem 0; }
        .lab-route-link:hover { color:var(--lab-acid) !important; }
        .lab-mission { border-bottom:1px solid var(--lab-line); padding:.25rem 0 1rem; margin-bottom:.75rem; }
        .lab-mission p { margin:.3rem 0; font-size:.92rem; line-height:1.45; color:#cbd2ce; }
        .lab-mission .need { color:var(--lab-muted); font-size:.75rem; }
        .lab-console-grid { display:grid; grid-template-columns:minmax(0,1.55fr) minmax(220px,.8fr); border:1px solid var(--lab-line); border-radius:7px; overflow:hidden; min-height:330px; background:#090d0e; }
        .lab-terminal { padding:1rem 1.05rem; border-right:1px solid var(--lab-line); font-family:"DM Mono",monospace; font-size:.68rem; line-height:1.6; }
        .lab-terminal-line { margin:0 0 .72rem; }
        .lab-terminal-meta { color:#b7c0ba; text-transform:uppercase; font-size:.59rem; }
        .lab-terminal-copy { color:var(--lab-acid); }
        .lab-terminal-system { color:var(--lab-cyan); }
        .lab-cursor { color:var(--lab-acid); animation:labBlink 1.1s steps(2,end) infinite; }
        @keyframes labBlink { 50% { opacity:.15; } }
        .lab-signal { padding:1rem; font-family:"DM Mono",monospace; }
        .lab-peer-row { display:flex; justify-content:space-between; gap:.8rem; color:#bdc6c0; font-size:.6rem; text-transform:uppercase; margin-bottom:1rem; }
        .lab-signal-row { position:relative; padding:.72rem 0; text-align:center; color:#c8d0cb; font-size:.65rem; }
        .lab-signal-row::before { content:""; position:absolute; left:10%; right:10%; top:50%; border-top:1px solid #626b67; }
        .lab-signal-row.right::after { content:"›"; position:absolute; right:8%; top:calc(50% - .72rem); font-size:1.25rem; color:#858e89; }
        .lab-signal-row.left::after { content:"‹"; position:absolute; left:8%; top:calc(50% - .72rem); font-size:1.25rem; color:#858e89; }
        .lab-signal-row span { position:relative; background:#090d0e; padding:0 .55rem; }
        .lab-signal-row.pending span { color:var(--lab-acid); }
        .lab-signal-row.done span::before { content:"✓ "; color:var(--lab-acid); }
        .lab-signal-expanded { color:var(--lab-muted); font-size:.58rem; line-height:1.4; text-align:left; padding:.2rem .4rem .7rem; }
        .lab-signal-expanded p { margin:.16rem 0; color:#9ea8a2; }
        .lab-participants { display:grid; grid-template-columns:repeat(auto-fit,minmax(120px,1fr)); gap:.5rem; margin:.8rem 0; }
        .lab-participant { border:1px solid var(--lab-line); border-radius:5px; padding:.65rem .75rem; background:#0c1112; }
        .lab-participant span { color:var(--lab-muted); font-family:"DM Mono",monospace; font-size:.58rem; text-transform:uppercase; }
        .lab-participant b { display:block; font-family:"DM Mono",monospace; color:var(--lab-acid); margin-top:.2rem; font-size:.72rem; }
        .lab-telemetry-section { border-top:1px solid var(--lab-line); padding-top:.85rem; margin-top:.9rem; }
        .lab-state-row { display:grid; grid-template-columns:minmax(0,1fr) auto; align-items:baseline; gap:.8rem; padding:.28rem 0; font-family:"DM Mono",monospace; font-size:.62rem; color:#aab3ae; }
        .lab-state-row b { color:var(--lab-text); font-weight:500; text-align:right; font-variant-numeric:tabular-nums; }
        .lab-state-row b.acid { color:var(--lab-acid); }
        .lab-state-row b.danger { color:var(--lab-red); }
        .lab-meter-row { display:grid; grid-template-columns:1fr auto; gap:.5rem; align-items:center; margin:.5rem 0; font-family:"DM Mono",monospace; font-size:.59rem; color:#aab3ae; }
        .lab-meter { display:flex; gap:2px; }
        .lab-meter i { width:8px; height:7px; background:#242a2a; display:block; }
        .lab-meter i.on { background:var(--lab-acid); }
        .lab-meter-row small { grid-column:1/-1; color:#66706b; text-transform:uppercase; }
        .lab-tip { border:1px solid #3e4542; border-radius:6px; padding:.75rem; color:#cdd66e; font-family:"DM Mono",monospace; font-size:.61rem; line-height:1.55; }
        .lab-cycle { display:flex; overflow-x:auto; gap:.35rem; padding:.35rem 0 .7rem; }
        .lab-cycle span { white-space:nowrap; font-family:"DM Mono",monospace; font-size:.55rem; text-transform:uppercase; letter-spacing:.06em; color:#65706b; }
        .lab-cycle span:not(:last-child)::after { content:" /"; opacity:.55; }
        .lab-claim { padding:.8rem 0; border-bottom:1px solid var(--lab-line); max-width:900px; }
        .lab-claim p { margin:.3rem 0; line-height:1.5; font-size:.78rem; }
        .lab-claim a { color:var(--lab-acid); }
        .lab-evolution { border-left:1px solid #555f5a; margin:.5rem 0 1rem .35rem; padding-left:1rem; }
        .lab-evolution article { position:relative; padding:.15rem 0 1rem; }
        .lab-evolution article::before { content:""; position:absolute; left:-1.23rem; top:.4rem; width:.42rem; height:.42rem; border-radius:50%; background:var(--lab-acid); }
        .lab-evolution p { color:var(--lab-muted); font-size:.72rem; }
        .lab-event { display:grid; grid-template-columns:3rem 1fr; gap:1rem; padding:.55rem 0; border-bottom:1px solid var(--lab-line); align-items:baseline; }
        .lab-event code { font-size:.52rem; color:#727d77; font-weight:400; }
        .lab-observation { border-left:3px solid var(--lab-yellow); background:#101516; padding:.7rem .8rem; margin:.5rem 0; font-size:.72rem; }
        .lab-observation b { display:block; color:var(--lab-acid); margin:.2rem 0; }
        .lab-invariant { border:1px solid var(--lab-line); border-radius:5px; padding:.7rem .8rem; margin:.45rem 0; background:#0c1112; font-size:.7rem; }
        .lab-holds { color:var(--lab-acid); margin:0 .45rem; }
        .lab-violated { color:var(--lab-red); margin:0 .45rem; }
        .lab-privacy { background:#101817; border:1px solid #29433d; border-radius:5px; padding:.8rem; margin:.8rem 0; font-size:.7rem; }
        .st-key-lab_atlas_shell { max-width:1120px; margin:4vh auto; border:1px solid var(--lab-line); border-radius:9px; background:rgba(10,14,15,.95); padding:clamp(1.2rem,4vw,3rem); }
        .lab-hero { padding:.5rem 0 1.2rem; max-width:880px; }
        .lab-hero h1 { margin:.45rem 0 .8rem; font-size:clamp(2.4rem,6vw,5.3rem) !important; color:var(--lab-text) !important; }
        .lab-hero p { max-width:760px; font-family:"DM Mono",monospace; font-size:.85rem; line-height:1.7; color:var(--lab-muted); }
        .lab-north-star { border-left:3px solid var(--lab-acid); padding:.8rem 1rem; background:#0d1313; font-size:.82rem; line-height:1.6; margin:.5rem 0 1.3rem; }
        .lab-atlas { display:flex; flex-wrap:wrap; gap:.38rem; margin:.8rem 0 1.2rem; }
        .lab-function { border:1px solid var(--lab-line); border-radius:4px; padding:.32rem .55rem; font-family:"DM Mono",monospace; font-size:.58rem; color:var(--lab-muted); }
        .lab-function.active { color:var(--lab-acid); border-color:#69783a; background:rgba(216,243,106,.06); }
        .lab-experiment-card { border:1px solid #3e4643; border-radius:7px; padding:1.2rem; background:#0b1011; margin:.8rem 0 1rem; }
        .lab-experiment-card h2 { font-size:clamp(1.5rem,3vw,2.5rem) !important; margin:.35rem 0 .65rem; }
        .lab-experience-heading { padding:.6rem 0 1.2rem; }
        .lab-experience-heading h1 { margin:.35rem 0 .6rem; font-size:clamp(2.5rem,6vw,5.3rem) !important; }
        .lab-guided-question { max-width:980px; font-size:clamp(1.45rem,3.2vw,2.75rem); line-height:1.18; margin:.5rem 0 2rem; color:#eef2ee; }
        .lab-situation { min-height:35vh; display:flex; flex-direction:column; justify-content:center; max-width:860px; padding:1.2rem 0; }
        .lab-situation-line { font-size:clamp(1.15rem,2.2vw,1.8rem); line-height:1.5; margin:.1rem 0; color:#cfd6d1; }
        .lab-protocol-footnote { margin-top:.8rem; color:var(--lab-muted); font-family:"DM Mono",monospace; font-size:.62rem; }
        .lab-stage-nav { display:grid; grid-template-columns:repeat(4,1fr); gap:.35rem; margin:.2rem 0 1.4rem; }
        .lab-stage-step { border-top:2px solid #303837; padding:.55rem 0; color:#69736e; font-family:"DM Mono",monospace; font-size:.58rem; text-transform:uppercase; letter-spacing:.08em; }
        .lab-stage-step.active { border-color:var(--lab-acid); color:var(--lab-acid); }
        .lab-stage-step.complete { border-color:#73803e; color:#a8b16d; }
        .lab-exchange { min-height:34vh; display:flex; flex-direction:column; justify-content:center; max-width:940px; margin:auto; }
        .lab-exchange-parties { display:grid; grid-template-columns:1fr 1fr; gap:1rem; align-items:stretch; }
        .lab-party { position:relative; border:1px solid var(--lab-line); border-radius:7px; padding:1.25rem; min-height:10rem; background:#0b1011; }
        .lab-party.active { border-color:#6f7d3c; box-shadow:inset 0 0 0 1px rgba(216,243,106,.08); }
        .lab-party span { font-family:"DM Mono",monospace; color:var(--lab-muted); font-size:.6rem; text-transform:uppercase; letter-spacing:.08em; }
        .lab-party p { margin:.75rem 0 0; font-size:clamp(1rem,1.7vw,1.25rem); line-height:1.55; color:#dce2de; }
        .lab-party.active::after { content:""; position:absolute; right:1rem; bottom:1rem; width:.45rem; height:.45rem; border-radius:50%; background:var(--lab-acid); animation:labPulse 1.2s ease-in-out infinite; }
        .lab-message-flight { display:grid; place-items:center; min-height:2.3rem; color:var(--lab-acid); font-family:"DM Mono",monospace; font-size:.7rem; text-align:center; padding:.55rem; animation:labSignal 620ms ease-out both; }
        @keyframes labSignal { from { opacity:.15; transform:translateX(-8%); } to { opacity:1; transform:translateX(0); } }
        @keyframes labPulse { 50% { opacity:.25; transform:scale(.72); } }
        .lab-reflection { max-width:850px; min-height:34vh; display:flex; flex-direction:column; justify-content:center; }
        .lab-reflection h2 { font-size:clamp(2rem,4vw,3.5rem) !important; text-transform:none !important; }
        .lab-reflection ul { margin:1rem 0 1.5rem; padding-left:1.2rem; }
        .lab-reflection li { margin:.65rem 0; color:#cbd3ce; line-height:1.5; }
        .lab-compression-reveal { max-width:900px; margin:2rem auto; padding:2rem 0; text-align:center; }
        .lab-compression-reveal h2 { font-size:clamp(1.8rem,4vw,3.2rem) !important; text-transform:none !important; }
        .lab-compressed-messages { display:flex; justify-content:center; flex-wrap:wrap; gap:.6rem; margin:2rem 0; }
        .lab-compressed-messages span { border:1px solid #6f7d3c; color:var(--lab-acid); padding:.7rem 1rem; border-radius:5px; font-family:"DM Mono",monospace; }
        .lab-human-sequence { display:grid; gap:.6rem; max-width:720px; margin:1.5rem auto; text-align:left; }
        .lab-human-sequence p { border-left:2px solid #59625f; padding:.4rem .8rem; margin:0; color:#bfc8c2; }
        .lab-inspect-drawer { position:fixed; z-index:999; top:9.5rem; right:1.5rem; width:min(450px,calc(100vw - 3rem)); max-height:72vh; overflow:auto; border:1px solid #59645f; border-radius:8px; background:rgba(8,12,13,.98); padding:1.1rem; box-shadow:0 18px 60px rgba(0,0,0,.55); backdrop-filter:blur(12px); }
        .st-key-lab_toggle_inspect { position:relative; z-index:1001; }
        .lab-inspect-drawer h3 { margin:1.1rem 0 .45rem; }
        .lab-inspect-row { display:grid; grid-template-columns:minmax(0,1fr) auto; gap:1rem; padding:.3rem 0; border-bottom:1px solid #202828; font-family:"DM Mono",monospace; font-size:.6rem; }
        .lab-inspect-row b { color:var(--lab-acid); font-variant-numeric:tabular-nums; text-align:right; }
        div.stButton > button, div.stFormSubmitButton > button, div.stDownloadButton > button { background:#101516 !important; border:1px solid #38413e !important; border-radius:5px !important; color:#cbd3ce !important; box-shadow:none !important; min-height:2.55rem !important; font-family:"DM Mono",monospace !important; font-size:.64rem !important; text-transform:uppercase; letter-spacing:.04em; }
        div.stButton > button:hover, div.stFormSubmitButton > button:hover, div.stDownloadButton > button:hover { background:#171d1d !important; border-color:var(--lab-acid) !important; color:var(--lab-acid) !important; transform:none !important; box-shadow:none !important; }
        div.stButton > button[data-testid="stBaseButton-primary"] { background:var(--lab-acid) !important; border-color:var(--lab-acid) !important; color:#0a0e0f !important; }
        div.stButton > button:disabled, div.stFormSubmitButton > button:disabled { opacity:1 !important; color:#89948e !important; border-color:#303836 !important; background:#0c1112 !important; cursor:not-allowed !important; }
        div.stButton > button:disabled p, div.stFormSubmitButton > button:disabled p { color:#89948e !important; }
        div.st-key-lab_toggle_expansion button[data-testid="stBaseButton-secondary"] { background:#101516 !important; border-color:#38413e !important; color:#cbd3ce !important; }
        div[class*="st-key-lab_begin_"] div.stButton > button { background:var(--lab-acid) !important; border-color:var(--lab-acid) !important; color:#0a0e0f !important; }
        div[class*="st-key-lab_primary_action_"] div.stButton > button { background:var(--lab-acid) !important; border-color:var(--lab-acid) !important; color:#0a0e0f !important; }
        div[class*="st-key-lab_begin_"] button p, div[class*="st-key-lab_primary_action_"] button p { color:#0a0e0f !important; }
        [data-baseweb="tab-list"] { gap:.3rem; border-bottom:1px solid var(--lab-line); }
        [data-baseweb="tab"] { color:#7f8984 !important; font-family:"DM Mono",monospace; font-size:.62rem; text-transform:uppercase; letter-spacing:.04em; padding:.65rem .7rem !important; }
        [data-baseweb="tab"][aria-selected="true"] { color:var(--lab-acid) !important; }
        [data-baseweb="tab-highlight"] { background-color:var(--lab-acid) !important; }
        [data-testid="stAlert"], [data-testid="stExpander"] { background:#101516 !important; border:1px solid var(--lab-line) !important; color:var(--lab-text) !important; border-radius:5px !important; }
        [data-baseweb="input"] > div, [data-baseweb="textarea"] > div, [data-baseweb="select"] > div { background:#0b1011 !important; border-color:#343d39 !important; color:var(--lab-text) !important; }
        textarea, input { color:var(--lab-text) !important; font-family:"DM Mono",monospace !important; }
        [data-testid="stSlider"] { color:var(--lab-acid); }
        hr { border-color:var(--lab-line) !important; }
        @media (max-width:980px) {
          .st-key-lab_rail, .st-key-lab_workspace, .st-key-lab_telemetry { min-height:unset; }
          .lab-function-item:not(.active) { display:none; }
          .lab-console-grid { grid-template-columns:1fr; }
          .lab-terminal { border-right:0; border-bottom:1px solid var(--lab-line); }
        }
        @media (max-width:640px) {
          .block-container { padding:.7rem !important; }
          .lab-topbar { align-items:flex-start; flex-direction:column; gap:.3rem; }
          .st-key-lab_atlas_shell { margin:0; padding:1rem; }
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def render_atlas_landing(
    *,
    atlas: ProtocolAtlas,
    active_experiment: ExperimentDefinition,
) -> None:
    _apply_styles()
    with st.container(key="lab_atlas_shell"):
        st.markdown(
            f"""
            <section class="lab-hero">
              <div class="lab-kicker">Protocol Laboratory &nbsp; / &nbsp; Founding pilot</div>
              <div class="lab-prompt">&gt;_</div>
              <h1>Think with protocols.</h1>
              <p>RECONSTRUCT / EXECUTE / BREAK / UNDERSTAND / REDESIGN</p>
            </section>
            <div class="lab-north-star">{html.escape(active_experiment.north_star)}</div>
            """,
            unsafe_allow_html=True,
        )
        function_chips = "".join(
            (
                '<span class="lab-function active">'
                if atlas.entries_for(function_name)
                and any(
                    entry.experiment.shippable
                    for entry in atlas.entries_for(function_name)
                )
                else '<span class="lab-function">'
            )
            + html.escape(function_name)
            + "</span>"
            for function_name in atlas.functions
        )
        st.markdown(
            f'<div class="lab-atlas">{function_chips}</div>',
            unsafe_allow_html=True,
        )
        st.markdown(
            f"""
            <section class="lab-experiment-card">
              <div class="lab-kicker">Experiment {active_experiment.experiment_number:02d} &nbsp; / &nbsp; {html.escape(active_experiment.atlas_functions[0])}</div>
              <h2>{html.escape(active_experiment.experience_title)}</h2>
              <p><b>{html.escape(active_experiment.human_question)}</b></p>
              <p class="lab-protocol-footnote">Experiment {active_experiment.experiment_number:02d} uses the {html.escape(active_experiment.protocol.name)}.</p>
            </section>
            """,
            unsafe_allow_html=True,
        )
        if st.button(
            "Enter Experiment 01 →",
            key=f"lab_begin_{active_experiment.id}",
            type="primary",
        ):
            st.session_state[_state_key(active_experiment, "stage")] = "experiment"
            st.rerun()

        with st.expander("Queued experiments / architecture canaries"):
            for entry in atlas.entries:
                if entry.experiment.shippable:
                    continue
                st.markdown(
                    f"**{html.escape(entry.experiment.title)}** · "
                    f"{html.escape(' / '.join(entry.experiment.atlas_functions))}  \n"
                    f"{html.escape(entry.experiment.question)}  \n"
                    f"*{html.escape(entry.experiment.human_question)}*"
                )


def _commands(experiment: ExperimentDefinition) -> list[Command]:
    value = st.session_state.setdefault(
        _state_key(experiment, "commands"),
        [],
    )
    if not isinstance(value, list) or not all(
        isinstance(command, Command) for command in value
    ):
        value = []
        st.session_state[_state_key(experiment, "commands")] = value
    return value


def _append_command(experiment: ExperimentDefinition, command: Command) -> None:
    commands = _commands(experiment)
    commands.append(command)
    st.session_state[_state_key(experiment, "commands")] = commands
    st.rerun()


def _current_replay(experiment: ExperimentDefinition) -> Replay:
    try:
        return replay(experiment, tuple(_commands(experiment)))
    except ProtocolCommandError as exc:
        st.error(f"This replay could not be reconstructed: {exc}")
        st.session_state[_state_key(experiment, "commands")] = []
        return replay(experiment, ())


def _render_lab_rail(experiment: ExperimentDefinition, current_stage: str) -> None:
    st.markdown(
        '<div class="lab-brand">PROTOCOL LAB<div class="lab-prompt">&gt;_</div></div>',
        unsafe_allow_html=True,
    )
    st.markdown('<div class="lab-label">Experiment path</div>', unsafe_allow_html=True)
    stages = ("connect", "disrupt", "interpret", "respond")
    progress = "".join(
        f'<div class="lab-function-item{(" active" if stage == current_stage else "")}">{index:02d} &nbsp; {stage.title()}</div>'
        for index, stage in enumerate(stages, start=1)
    )
    st.markdown(f'<div class="lab-function-list">{progress}</div>', unsafe_allow_html=True)
    st.markdown(
        '<div class="lab-rail-section">Specimen</div>'
        f'<div class="lab-objective">Experiment {experiment.experiment_number:02d}'
        f'<b>{html.escape(experiment.atlas_functions[0])}</b></div>',
        unsafe_allow_html=True,
    )
    if st.button("← Protocol Atlas", key="lab_back_to_atlas", width="stretch"):
        st.session_state[_state_key(experiment, "stage")] = "atlas"
        st.rerun()
    st.markdown(
        '<a class="lab-route-link" href="/commons">◇ Commons research instrument</a>',
        unsafe_allow_html=True,
    )


def _level_strength(level: str) -> int:
    normalized = level.casefold()
    if normalized in {"none", "unknown", "unresolved"}:
        return 0
    if normalized in {"low", "bounded"}:
        return 1
    if normalized in {"partial", "mixed", "waiting", "asymmetric", "reversible"}:
        return 2
    if normalized in {"medium", "elevated", "active"}:
        return 3
    if normalized in {"high", "strong"}:
        return 4
    if normalized in {"critical", "violated"}:
        return 5
    return 2


def _render_telemetry(
    experiment: ExperimentDefinition,
    session: Replay,
) -> None:
    state = session.final_state
    emitted = sum(event.event_type == "message_emitted" for event in state.events)
    holds = sum(result.status == "holds" for result in state.invariant_results)
    violated = sum(result.status == "violated" for result in state.invariant_results)
    state_rows = "".join(
        '<div class="lab-state-row">'
        f"<span>{html.escape(experiment.participant(participant_id).label)}</span>"
        f'<b class="acid">{html.escape(value)}</b></div>'
        for participant_id, value in state.participant_states
    )
    st.markdown(
        '<div class="lab-label">State</div>'
        f'<div class="lab-state-row"><span>Experiment</span><b class="acid">{html.escape(state.status.upper())}</b></div>'
        f'<div class="lab-state-row"><span>Messages</span><b>{emitted}</b></div>'
        f'<div class="lab-state-row"><span>Pending</span><b>{len(state.pending_messages)}</b></div>'
        f'<div class="lab-state-row"><span>Logical time</span><b>{state.tick:02d}</b></div>'
        f'<div class="lab-state-row"><span>Replay</span><b>{html.escape(session.replay_hash[:8])}</b></div>'
        '<div class="lab-telemetry-section"><div class="lab-label">Participants</div>'
        f"{state_rows}</div>"
        '<div class="lab-telemetry-section"><div class="lab-label">Invariants</div>'
        f'<div class="lab-state-row"><span>Holding</span><b class="acid">{holds}</b></div>'
        f'<div class="lab-state-row"><span>Violated</span><b class="{("danger" if violated else "")}">{violated}</b></div></div>',
        unsafe_allow_html=True,
    )

    latest = {
        observation.dimension: observation
        for observation in state.hidden_state_observations
    }
    dimensions = tuple(dict.fromkeys(rule.dimension for rule in experiment.hidden_state_rules))
    meter_rows: list[str] = []
    for dimension in dimensions:
        observation = latest.get(dimension)
        level = observation.level if observation else "not yet exposed"
        strength = _level_strength(level) if observation else 0
        segments = "".join(
            f'<i class="{("on" if index < strength else "")}"></i>'
            for index in range(5)
        )
        meter_rows.append(
            '<div class="lab-meter-row">'
            f"<span>{html.escape(dimension)}</span>"
            f'<span class="lab-meter">{segments}</span>'
            f"<small>{html.escape(level)}</small>"
            "</div>"
        )
    meters = "".join(meter_rows)
    st.markdown(
        '<div class="lab-telemetry-section"><div class="lab-label">Interpretive traces</div>'
        f"{meters}<div class=\"lab-provenance\">Declared model / not measurement</div></div>",
        unsafe_allow_html=True,
    )

    st.markdown('<div class="lab-telemetry-section"><div class="lab-label">Controls</div></div>', unsafe_allow_html=True)
    control_columns = st.columns(3)
    commands = _commands(experiment)
    with control_columns[0]:
        if st.button("Rewind", key="lab_rewind", disabled=not commands, width="stretch"):
            commands.pop()
            st.session_state[_state_key(experiment, "commands")] = commands
            st.rerun()
    with control_columns[1]:
        if st.button("Replay", key="lab_replay", disabled=not state.events, width="stretch"):
            st.session_state[_state_key(experiment, "event_cursor")] = 0
            st.rerun()
    with control_columns[2]:
        if st.button("Reset", key="lab_reset", width="stretch"):
            st.session_state[_state_key(experiment, "commands")] = []
            st.session_state[_state_key(experiment, "collapse_pending")] = True
            st.session_state[_state_key(experiment, "milestone_ready")] = False
            st.session_state[_state_key(experiment, "current_stage")] = "connect"
            st.session_state[_state_key(experiment, "counterpart_reaction")] = ""
            st.rerun()

    tip = (
        state.reflection_cues[-1].question
        if state.reflection_cues
        else experiment.protocol.critical_reflection
    )
    st.markdown(
        '<div class="lab-telemetry-section">'
        f'<div class="lab-tip">◇ TIP / {html.escape(tip)}</div></div>',
        unsafe_allow_html=True,
    )


def _render_question_need_protocol(experiment: ExperimentDefinition) -> None:
    st.markdown(
        '<div class="lab-mission">'
        '<div class="lab-label">Question / Need / Protocol</div>'
        f'<p><b>Technical question</b><br>{html.escape(experiment.question)}</p>'
        f'<p class="human"><b>Human translation</b><br>{html.escape(experiment.human_question)}</p>'
        f'<p class="need">{html.escape(experiment.need)} &nbsp; / &nbsp; '
        f'{html.escape(experiment.protocol.name)}</p></div>',
        unsafe_allow_html=True,
    )


def _render_archaeology(experiment: ExperimentDefinition) -> None:
    st.subheader("Protocol archaeology")
    st.caption(
        "Why was this invented? What alternatives existed? Which assumptions survived—and which broke?"
    )
    for claim in experiment.archaeology:
        source = (
            f' · <a href="{html.escape(claim.source_url)}">{html.escape(claim.source_label)}</a>'
            if claim.source_url
            else ""
        )
        st.markdown(
            f"""
            <article class="lab-claim">
              <span class="lab-provenance">{html.escape(claim.provenance)}</span>
              <p>{html.escape(claim.text)}</p>
              <small>{source}</small>
            </article>
            """,
            unsafe_allow_html=True,
        )
    st.markdown("### Protocol evolution")
    entries = "".join(
        "<article>"
        f'<div class="lab-kicker">{html.escape(item.year)}</div>'
        f"<b>{html.escape(item.title)}</b>"
        f"<p>{html.escape(item.description)}</p>"
        "</article>"
        for item in experiment.evolution
    )
    st.markdown(
        f'<div class="lab-evolution">{entries}</div>',
        unsafe_allow_html=True,
    )


def _render_compression(
    experiment: ExperimentDefinition,
    session: Replay,
) -> None:
    state = session.final_state
    completed_once_key = _state_key(experiment, "completed_once")
    if state.status == experiment.completion_status:
        st.session_state[completed_once_key] = True
    expand_key = _state_key(experiment, "expanded")
    if st.session_state.pop(_state_key(experiment, "collapse_pending"), False):
        st.session_state[expand_key] = False
    if expand_key not in st.session_state:
        st.session_state[expand_key] = not bool(
            st.session_state.get(completed_once_key)
        )
    expanded = bool(st.session_state[expand_key])
    if st.button(
        "Collapse negotiation" if expanded else "Expand negotiation",
        key="lab_toggle_expansion",
        help="Move between protocol compression and the negotiation it represents.",
    ):
        st.session_state[expand_key] = not expanded
        st.rerun()
    transcript_events = tuple(
        event
        for event in state.events
        if event.event_type
        in {
            "message_emitted",
            "intervention",
            "timer_expired",
            "message_rejected",
            "status",
        }
    )[-9:]
    terminal_lines: list[str] = []
    if not transcript_events:
        terminal_lines.extend(
            (
                '<div class="lab-terminal-line"><span class="lab-terminal-meta">LAB [TICK 00]</span><br>'
                '<span class="lab-terminal-system">Experiment armed. Awaiting the first command.</span></div>',
                '<div class="lab-terminal-line"><span class="lab-terminal-meta">QUESTION</span><br>'
                f'<span class="lab-terminal-copy">{html.escape(experiment.question)}</span><br>'
                f'<span class="lab-terminal-system">HUMAN TRANSLATION / {html.escape(experiment.human_question)}</span></div>',
            )
        )
    for event in transcript_events:
        actor = "LAB"
        if event.actor:
            try:
                actor = experiment.participant(event.actor).label
            except KeyError:
                actor = event.actor
        if event.message_id:
            message = experiment.message(event.message_id)
            copy = (
                " / ".join(message.expanded)
                if expanded
                else f"{message.label} — {message.technical}"
            )
            copy_class = "lab-terminal-copy"
        else:
            copy = event.label
            copy_class = "lab-terminal-system"
        terminal_lines.append(
            '<div class="lab-terminal-line">'
            f'<span class="lab-terminal-meta">{html.escape(actor)} [TICK {event.tick:02d}] · {html.escape(event.event_id)}</span><br>'
            f'<span class="{copy_class}">{html.escape(copy)}</span></div>'
        )
    terminal_lines.append('<div class="lab-cursor">_</div>')

    rows = sequence_rows(experiment, state)
    emitted_ids = {
        event.message_id
        for event in state.events
        if event.event_type == "message_emitted"
    }
    first_participant = experiment.participants[0].id
    signal_rows: list[str] = []
    for row in rows:
        direction = "right" if experiment.message(row.message_id).sender == first_participant else "left"
        status = " pending" if row.pending_instance_ids else (" done" if row.message_id in emitted_ids else "")
        signal_rows.append(
            f'<div class="lab-signal-row {direction}{status}"><span>{html.escape(row.label)}</span></div>'
        )
        if expanded and (row.pending_instance_ids or row.message_id in emitted_ids):
            expanded_copy = "".join(
                f"<p>{html.escape(line)}</p>" for line in row.expanded
            )
            signal_rows.append(
                f'<div class="lab-signal-expanded">{expanded_copy}</div>'
            )
    peer_labels = "".join(
        f"<span>{html.escape(participant.label)}</span>"
        for participant in experiment.participants
    )
    st.markdown(
        '<div class="lab-console-grid">'
        f'<div class="lab-terminal">{"".join(terminal_lines)}</div>'
        '<div class="lab-signal">'
        f'<div class="lab-peer-row">{peer_labels}</div>'
        f'{"".join(signal_rows)}</div></div>',
        unsafe_allow_html=True,
    )


def _render_execution(
    experiment: ExperimentDefinition,
    session: Replay,
) -> None:
    state = session.final_state
    st.markdown('<div class="lab-rail-section">Command deck</div>', unsafe_allow_html=True)
    st.caption(
        f"Logical tick {state.tick} · {len(state.pending_messages)} pending · "
        f"Replay {session.replay_hash[:12]}"
    )

    failure_transition_ids = {
        failure.transition
        for failure in experiment.failure_scenarios
        if failure.transition
    }
    available = [
        transition
        for transition in experiment.transitions
        if transition.trigger == "command"
        and transition.id not in failure_transition_ids
        and state.participant_state(transition.actor) == transition.from_state
    ]
    actions: list[tuple[str, str, bool, str, Command]] = []
    for transition in available:
        actions.append(
            (
                _humanize(transition.command or transition.id),
                f"lab_cmd_{transition.id}",
                False,
                "primary" if not actions else "secondary",
                Command.transition(transition.id),
            )
        )
    for message in state.pending_messages:
        definition = experiment.message(message.message_id)
        delayed = message.deliver_at > state.tick
        label = (
            f"Deliver {definition.label} · available at tick {message.deliver_at}"
            if delayed
            else f"Deliver {definition.label} → {experiment.participant(message.receiver).label}"
        )
        actions.append(
            (
                label,
                f"lab_deliver_{message.instance_id}",
                delayed,
                "primary" if not delayed else "secondary",
                Command.deliver(message.instance_id),
            )
        )
    actions.append(("Wait +1", "lab_wait_one", False, "secondary", Command.wait(1)))
    action_columns = st.columns(min(4, len(actions)))
    for index, (label, key, disabled, button_type, command) in enumerate(actions):
        with action_columns[index % len(action_columns)]:
            with st.container(key=f"lab_primary_action_{index}" if button_type == "primary" else None):
                if st.button(
                    label,
                    key=key,
                    disabled=disabled,
                    type=button_type,
                    width="stretch",
                ):
                    _append_command(experiment, command)

    if state.events:
        max_index = len(state.events) - 1
        cursor_key = _state_key(experiment, "event_cursor")
        stored_cursor = min(
            max_index,
            int(st.session_state.get(cursor_key, max_index)),
        )
        st.session_state[cursor_key] = stored_cursor
        cursor = st.slider(
            "Inspect replay event",
            min_value=0,
            max_value=max_index,
            key=cursor_key,
            format="Event %d",
        )
        inspected = state.events[cursor]
        st.caption(f"{inspected.event_id} · tick {inspected.tick}")
        st.markdown(f"**{html.escape(inspected.label)}**")
        with st.expander("Complete event record"):
            for event in state.events:
                st.markdown(
                    f'<div class="lab-event"><code>{event.event_id}</code><span>{html.escape(event.label)}</span></div>',
                    unsafe_allow_html=True,
                )


def _opening_transition(experiment: ExperimentDefinition, session: Replay):
    failure_transition_ids = {
        failure.transition for failure in experiment.failure_scenarios if failure.transition
    }
    for transition in experiment.transitions:
        if (
            transition.trigger == "command"
            and transition.id not in failure_transition_ids
            and session.final_state.participant_state(transition.actor)
            == transition.from_state
        ):
            return transition
    return None


def _apply_guided_command(
    experiment: ExperimentDefinition,
    command: Command,
) -> None:
    before = _current_replay(experiment)
    commands = [*before.commands, command]
    after = replay(experiment, tuple(commands))
    _queue_ambient_discoveries(experiment, before, after)
    st.session_state[_state_key(experiment, "commands")] = commands
    st.rerun()


def _queue_ambient_discoveries(
    experiment: ExperimentDefinition,
    before: Replay,
    after: Replay,
) -> None:
    previous_count = len(before.final_state.hidden_state_observations)
    observations = after.final_state.hidden_state_observations[previous_count:]
    discoveries = [
        f"{observation.dimension} · {observation.level}\n{observation.observation}"
        for observation in observations
    ]
    if discoveries:
        st.session_state[_state_key(experiment, "ambient_discoveries")] = discoveries[-4:]


def _render_ambient_discoveries(experiment: ExperimentDefinition) -> None:
    key = _state_key(experiment, "ambient_discoveries")
    discoveries = st.session_state.pop(key, [])
    for discovery in discoveries:
        st.toast(discovery, icon="💡", duration="short")


def _deliver_player_message(
    experiment: ExperimentDefinition,
    session: Replay,
    message_instance_id: str,
) -> None:
    commands = [*session.commands, Command.deliver(message_instance_id)]
    updated = replay(experiment, tuple(commands))
    first_participant = experiment.participants[0].id

    # The laboratory operates the counterpart. A short delay lets the response
    # feel transmitted rather than computed in the same instant.
    while updated.final_state.pending_messages:
        response = updated.final_state.pending_messages[0]
        definition = experiment.message(response.message_id)
        if definition.sender == first_participant or response.deliver_at > updated.final_state.tick:
            break
        time.sleep(0.42)
        st.session_state[_state_key(experiment, "counterpart_reaction")] = " ".join(
            definition.expanded
        )
        commands.append(Command.deliver(response.instance_id))
        updated = replay(experiment, tuple(commands))

    _queue_ambient_discoveries(experiment, session, updated)
    st.session_state[_state_key(experiment, "commands")] = commands
    if updated.final_state.status == experiment.completion_status:
        st.session_state[_state_key(experiment, "milestone_ready")] = True
    st.rerun()


def _render_stage_progress(current_stage: str) -> None:
    stages = ("connect", "disrupt", "interpret", "respond")
    current_index = stages.index(current_stage)
    items = "".join(
        f'<div class="lab-stage-step{(" active" if stage == current_stage else " complete" if index < current_index else "")}">'
        f'{index + 1:02d} &nbsp; {stage}</div>'
        for index, stage in enumerate(stages)
    )
    st.markdown(f'<div class="lab-stage-nav">{items}</div>', unsafe_allow_html=True)


def _render_situation(
    experiment: ExperimentDefinition,
    session: Replay,
) -> None:
    situation = "".join(
        f'<p class="lab-situation-line">{html.escape(line)}</p>'
        for line in experiment.situation
    )
    st.markdown(
        '<section class="lab-situation">'
        '<div class="lab-label">The situation</div>'
        f'{situation}</section>',
        unsafe_allow_html=True,
    )
    transition = _opening_transition(experiment, session)
    if transition and st.button(
        "Begin the negotiation",
        key="lab_begin_negotiation",
        type="primary",
        width="stretch",
    ):
        st.session_state[_state_key(experiment, "counterpart_reaction")] = ""
        _apply_guided_command(
            experiment,
            Command.transition(transition.id),
        )
    st.markdown(
        f'<p class="lab-protocol-footnote">Experiment {experiment.experiment_number:02d} uses the {html.escape(experiment.protocol.name)}.</p>',
        unsafe_allow_html=True,
    )


def _guided_action_label(
    experiment: ExperimentDefinition,
    session: Replay,
    message_id: str,
) -> str:
    definition = experiment.message(message_id)
    emitted = sum(
        event.event_type == "message_emitted" for event in session.final_state.events
    )
    first_participant = experiment.participants[0].id
    if definition.sender != first_participant:
        return "Receive their reply"
    if emitted <= 1:
        return "Send your opening message"
    return "Send your confirmation"


def _render_packet_details(
    experiment: ExperimentDefinition,
    session: Replay,
    message_id: str,
) -> None:
    definition = experiment.message(message_id)
    state = session.final_state
    with st.expander("View packet details"):
        st.markdown(f"**{definition.label}** — {definition.technical}")
        metadata = dict(definition.metadata)
        for key, value in metadata.items():
            st.caption(f"{_humanize(key)}: {value}")
        st.caption(
            f"{_humanize(definition.sender)} → {_humanize(definition.receiver)} · "
            f"logical time {state.tick}"
        )


def _render_exchange(
    experiment: ExperimentDefinition,
    session: Replay,
) -> None:
    state = session.final_state
    if not state.pending_messages:
        st.markdown(
            '<section class="lab-exchange"><div class="lab-label">The exchange</div>'
            '<p class="lab-situation-line">No message is currently moving. One side is waiting.</p></section>',
            unsafe_allow_html=True,
        )
        if st.button("Wait", key="lab_guided_wait", type="primary"):
            _apply_guided_command(experiment, Command.wait(1))
        st.caption("Advance logical time by one tick")
        return

    pending = state.pending_messages[0]
    definition = experiment.message(pending.message_id)
    copy = " ".join(definition.expanded)
    first_participant = experiment.participants[0].id
    sender_is_you = definition.sender == first_participant
    you_copy = copy if sender_is_you else "Waiting for the message."
    other_copy = copy if not sender_is_you else str(
        st.session_state.get(_state_key(experiment, "counterpart_reaction"))
        or "Waiting."
    )
    st.markdown(
        '<section class="lab-exchange">'
        '<div class="lab-label">The active message</div>'
        '<div class="lab-exchange-parties">'
        f'<article class="lab-party{(" active" if sender_is_you else "")}"><span>You</span><p>{html.escape(you_copy)}</p></article>'
        f'<article class="lab-party{("" if sender_is_you else " active")}"><span>Other side</span><p>{html.escape(other_copy)}</p></article>'
        '</div>'
        f'<div class="lab-message-flight">{("YOU → OTHER SIDE" if sender_is_you else "OTHER SIDE → YOU")}</div>'
        '</section>',
        unsafe_allow_html=True,
    )
    _render_packet_details(experiment, session, pending.message_id)
    action_label = _guided_action_label(experiment, session, pending.message_id)
    delayed = pending.deliver_at > state.tick
    if st.button(
        action_label,
        key=f"lab_guided_deliver_{pending.instance_id}",
        type="primary",
        disabled=delayed,
        width="stretch",
    ):
        _deliver_player_message(experiment, session, pending.instance_id)
    st.caption(
        f"{definition.label} → {_humanize(definition.receiver)}"
        if not delayed
        else f"Available at logical time {pending.deliver_at}"
    )


def _render_milestone(
    experiment: ExperimentDefinition,
    session: Replay,
) -> None:
    observations = session.final_state.hidden_state_observations[-5:]
    if observations:
        items = "".join(
            f"<li>{html.escape(observation.observation)}</li>"
            for observation in observations
        )
    else:
        items = "<li>A message changed what one participant could know and do.</li>"
    st.markdown(
        '<section class="lab-reflection">'
        '<div class="lab-label">Milestone reached</div>'
        '<h2>What actually happened?</h2>'
        f'<ul>{items}</ul>'
        '<p class="lab-protocol-footnote">These are interpretations linked to the exchange, not objective measurements.</p>'
        '</section>',
        unsafe_allow_html=True,
    )
    if st.button(
        "See what was compressed",
        key="lab_reveal_compression",
        type="primary",
        width="stretch",
    ):
        st.session_state[_state_key(experiment, "milestone_ready")] = False
        st.rerun()


def _render_compression_reveal(
    experiment: ExperimentDefinition,
    session: Replay,
) -> None:
    baseline = tuple(message for message in experiment.messages if message.baseline)
    human_steps = "".join(
        f"<p>{index}. {html.escape(' '.join(message.expanded))}</p>"
        for index, message in enumerate(baseline, start=1)
    )
    compressed = "".join(
        f"<span>{html.escape(message.label)}</span>" for message in baseline
    )
    st.markdown(
        '<section class="lab-compression-reveal">'
        '<div class="lab-label">Compression reveal</div>'
        '<h2>This negotiation is compressed into three messages.</h2>'
        f'<div class="lab-human-sequence">{human_steps}</div>'
        f'<div class="lab-compressed-messages">{compressed}</div>'
        f'<p class="lab-protocol-footnote">Technical architecture · {html.escape(experiment.protocol.name)}</p>'
        '</section>',
        unsafe_allow_html=True,
    )
    if st.button(
        "Disrupt the negotiation",
        key="lab_continue_to_disrupt",
        type="primary",
        width="stretch",
    ):
        st.session_state[_state_key(experiment, "current_stage")] = "disrupt"
        st.session_state[_state_key(experiment, "completed_once")] = True
        st.rerun()


def _render_connect(
    experiment: ExperimentDefinition,
    session: Replay,
) -> None:
    state = session.final_state
    if not session.commands:
        _render_situation(experiment, session)
        return
    if state.status == experiment.completion_status:
        st.session_state[_state_key(experiment, "completed_once")] = True
        if st.session_state.get(_state_key(experiment, "milestone_ready"), True):
            _render_milestone(experiment, session)
            return
        _render_compression_reveal(experiment, session)
        return
    _render_exchange(experiment, session)


def _render_inspection(
    experiment: ExperimentDefinition,
    session: Replay,
) -> None:
    state = session.final_state
    participant_rows = "".join(
        '<div class="lab-inspect-row">'
        f'<span>{html.escape(_humanize(participant_id))} state</span>'
        f'<b>{html.escape(value)}</b></div>'
        for participant_id, value in state.participant_states
    )
    message_rows: list[str] = []
    for pending in state.pending_messages:
        definition = experiment.message(pending.message_id)
        metadata = " · ".join(
            f"{_humanize(key)} {value}" for key, value in definition.metadata
        )
        message_rows.append(
            '<div class="lab-inspect-row">'
            f'<span>{html.escape(definition.label)} · {html.escape(metadata)}</span>'
            f'<b>{html.escape(pending.instance_id)}</b></div>'
        )
    timer_rows = "".join(
        '<div class="lab-inspect-row">'
        f'<span>{html.escape(timer.timer_id)}</span>'
        f'<b>tick {timer.due_tick}</b></div>'
        for timer in state.timers
    )
    invariant_rows = "".join(
        '<div class="lab-inspect-row">'
        f'<span>{html.escape(result.description)}</span>'
        f'<b>{html.escape(result.status.upper())}</b></div>'
        for result in state.invariant_results
    )
    event_rows = "".join(
        '<div class="lab-event">'
        f'<code>{html.escape(event.event_id)}</code>'
        f'<span>{html.escape(event.label)}</span></div>'
        for event in state.events[-10:]
    ) or '<p class="lab-protocol-footnote">No events yet.</p>'
    message_markup = "".join(message_rows) or (
        '<p class="lab-protocol-footnote">No message pending.</p>'
    )
    timer_markup = timer_rows or (
        '<p class="lab-protocol-footnote">No active timer.</p>'
    )
    st.markdown(
        '<section class="lab-inspect-drawer"><div class="lab-label">X-ray mode · synchronised technical layer</div>'
        f'<p><b>{html.escape(experiment.question)}</b></p>'
        f'<p class="lab-protocol-footnote">{html.escape(experiment.protocol.name)}</p>'
        f'<div class="lab-inspect-row"><span>Logical time</span><b>{state.tick:02d}</b></div>'
        f'<div class="lab-inspect-row"><span>Replay</span><b>{html.escape(session.replay_hash[:10])}</b></div>'
        '<h3>Participants</h3>'
        f'{participant_rows}'
        '<h3>Messages and sequence space</h3>'
        f'{message_markup}'
        '<h3>Timers</h3>'
        f'{timer_markup}'
        '<h3>Invariants</h3>'
        f'{invariant_rows}'
        '<h3>Recent event record</h3>'
        f'{event_rows}'
        '</section>',
        unsafe_allow_html=True,
    )


def _failure_target(
    failure: FailureScenario,
    session: Replay,
) -> str:
    for message in session.final_state.pending_messages:
        if (
            not failure.applicable_messages
            or message.message_id in failure.applicable_messages
        ):
            return message.instance_id
    return ""


def _failure_available(
    experiment: ExperimentDefinition,
    failure: FailureScenario,
    session: Replay,
) -> bool:
    if failure.operation in {"drop", "delay", "duplicate", "reorder", "manipulate"}:
        return bool(_failure_target(failure, session))
    if failure.operation == "transition" and failure.transition:
        transition = experiment.transition(failure.transition)
        return (
            session.final_state.participant_state(transition.actor)
            == transition.from_state
        )
    return True


def _render_break(
    experiment: ExperimentDefinition,
    session: Replay,
) -> None:
    st.subheader("Break the protocol")
    st.caption(
        "Separate disturbance, adversarial intervention, built-in protocol response, and institutional policy."
    )
    family_copy = {
        "natural": ("Natural disturbances", "Noise, loss, delay, duplication and reordering."),
        "adversary": ("Adversarial interventions", "Replay, forgery and manipulation."),
        "protocol_response": ("Protocol responses", "Timeouts, retries and other mechanisms defined by the protocol."),
        "institutional_policy": ("Institutional policies", "Filtering, access policy and explicit refusal."),
    }
    tabs = st.tabs([family_copy[family][0] for family in family_copy])
    for tab, family in zip(tabs, family_copy):
        with tab:
            st.caption(family_copy[family][1])
            for failure in experiment.failure_scenarios:
                if failure.family != family:
                    continue
                with st.container(border=True):
                    st.markdown(f"**{failure.label}**")
                    st.write(failure.description)
                    st.caption(f"Consequence / rationale: {failure.response}")
                    available = _failure_available(experiment, failure, session)
                    if st.button(
                        f"Try {failure.label.lower()}",
                        key=f"lab_failure_{failure.id}",
                        disabled=not available,
                        help=(
                            None
                            if available
                            else "Unavailable in the current state. Prepare or advance the negotiation first."
                        ),
                    ):
                        _append_command(
                            experiment,
                            Command.failure(
                                failure.id,
                                _failure_target(failure, session),
                            ),
                        )


def _render_understand(
    experiment: ExperimentDefinition,
    session: Replay,
) -> None:
    state = session.final_state
    st.subheader("Understand what changed")
    st.caption(
        "These are evidence-linked interpretations, not objective measurements. Challenge them."
    )
    st.markdown("### Invariants")
    for result in state.invariant_results:
        st.markdown(
            f"""
            <div class="lab-invariant">
              <span class="lab-provenance">{html.escape(result.kind)}</span>
              <b class="lab-{html.escape(result.status)}">{html.escape(result.status.upper())}</b>
              <div>{html.escape(result.description)}</div>
              <small>Evidence: {html.escape(', '.join(result.evidence_event_ids) or 'initial state')}</small>
            </div>
            """,
            unsafe_allow_html=True,
        )
    st.markdown("### Hidden state")
    if not state.hidden_state_observations:
        st.info("Execute or break the protocol to expose agency, opacity, trust, risk and commitment.")
    for observation in state.hidden_state_observations:
        st.markdown(
            f"""
            <div class="lab-observation">
              <span class="lab-provenance">{html.escape(observation.provenance)} · evidence {html.escape(observation.evidence_event_id)}</span><br>
              <b>{html.escape(observation.dimension)} · {html.escape(observation.level)}</b>
              {html.escape(observation.observation)}
            </div>
            """,
            unsafe_allow_html=True,
        )
    if state.reflection_cues:
        st.markdown("### Reflection pauses")
        for cue in state.reflection_cues:
            st.info(cue.question, icon="💭")

    labels = {
        rule.id: f"{rule.dimension} · {rule.observation}"
        for rule in experiment.hidden_state_rules
    }
    st.multiselect(
        "Challenge an interpretation",
        options=list(labels),
        format_func=lambda value: labels[value],
        key=_state_key(experiment, "challenged_rules"),
        help="Your challenge becomes a participant observation, not a correction silently applied to the model.",
    )


def _build_note_from_state(
    experiment: ExperimentDefinition,
    session: Replay,
    participant_id: str,
) -> FieldNote:
    observations = {
        prompt.note_type: str(
            st.session_state.get(_state_key(experiment, f"field_{prompt.id}")) or ""
        )
        for prompt in experiment.field_note_prompts
    }
    challenged = tuple(
        st.session_state.get(_state_key(experiment, "challenged_rules")) or ()
    )
    return build_field_note(
        experiment=experiment,
        session=session,
        access_key=participant_id,
        observations=observations,
        challenged_rule_ids=challenged,
        created_at=utc_now_iso(),
    )


def _field_note_storage_available(repository: Any) -> bool:
    return callable(getattr(repository, "record_protocol_lab_field_note", None)) and callable(
        getattr(repository, "list_protocol_lab_field_notes", None)
    )


def _list_saved_field_notes(
    repository: Any,
    owner_key_hash: str | None = None,
) -> list[dict[str, Any]]:
    list_notes = getattr(repository, "list_protocol_lab_field_notes", None)
    if not callable(list_notes):
        return []
    return list(list_notes(owner_key_hash))


def _render_field_notes(
    experiment: ExperimentDefinition,
    session: Replay,
    *,
    repository: Any,
    participant_id: str,
) -> None:
    st.subheader("Field notes")
    st.caption(
        f"Nobody is expected to rewrite {experiment.protocol.name} from scratch. "
        "Record observations, anomalies, criticisms and proposed modifications."
    )
    storage_available = _field_note_storage_available(repository)
    if not storage_available:
        st.warning(
            "This running app was loaded before Field Notes storage became available. "
            "Private preparation and download still work; restart the app to enable "
            "shared saving and resume.",
            icon="🔄",
        )
    for prompt in experiment.field_note_prompts:
        st.markdown(f"**{prompt.note_type.title()}**")
        st.text_area(
            prompt.prompt,
            key=_state_key(experiment, f"field_{prompt.id}"),
            max_chars=1200,
        )
    if st.button("Prepare session notebook", key="lab_prepare_notebook"):
        try:
            note = _build_note_from_state(experiment, session, participant_id)
        except ValueError as exc:
            st.warning(str(exc))
        else:
            st.session_state[_state_key(experiment, "prepared_note")] = note
            st.rerun()

    note = st.session_state.get(_state_key(experiment, "prepared_note"))
    if isinstance(note, FieldNote):
        exported = export_field_note(note)
        st.download_button(
            "Download private notebook",
            data=json.dumps(exported, ensure_ascii=False, indent=2),
            file_name=f"{experiment.id}-field-note.json",
            mime="application/json",
            key="lab_download_notebook",
        )
        st.markdown(
            '<div class="lab-privacy"><b>Private by default.</b> Preparing or downloading this notebook writes nothing to shared storage. Saving below is a separate explicit action.</div>',
            unsafe_allow_html=True,
        )
        if st.button(
            "Save selected field notes",
            key="lab_save_field_notes",
            type="primary",
            disabled=not storage_available,
        ):
            repository.record_protocol_lab_field_note(note.as_record())
            st.session_state[_state_key(experiment, "note_saved")] = True
            st.rerun()
    if st.session_state.get(_state_key(experiment, "note_saved")):
        st.success("Field notes saved under your access-key identity.")

    owner_hash = access_key_hash(participant_id)
    saved_notes = _list_saved_field_notes(repository, owner_hash)
    if saved_notes:
        st.caption(f"{len(saved_notes)} saved notebook record(s) can be resumed with this access key.")

    st.markdown("### Join us")
    st.markdown(
        '<div class="lab-privacy"><b>Separate records.</b> Joining the research network is optional. Contact details never enter field notes or replay exports.</div>',
        unsafe_allow_html=True,
    )
    with st.form("protocol_lab_join_form"):
        join = st.checkbox(
            "I would like to join the Protocol Laboratory research community",
            key="lab_join_consent",
        )
        email = st.text_input(
            "Email (optional)",
            key="lab_join_email",
            disabled=not join,
        )
        submitted = st.form_submit_button(
            "Join us",
            disabled=not join,
        )
        if submitted:
            repository.record_coordination_interest(
                participant_uuid=participant_id,
                session_code="protocol_lab_pilot_2026",
                email=email or None,
                consent_version="protocol-lab-join-v1",
                consented_at=utc_now_iso(),
            )
            st.success(
                "Your invitation preference was saved separately from the experiment."
            )


def _render_disrupt_stage(
    experiment: ExperimentDefinition,
    session: Replay,
) -> None:
    state = session.final_state
    if not session.commands or state.status == experiment.completion_status:
        st.markdown(
            '<section class="lab-situation"><div class="lab-label">Disrupt</div>'
            '<p class="lab-situation-line">Run the negotiation again, then intervene while a message is moving.</p>'
            '<p class="lab-situation-line">Disturbance, adversarial action, protocol response and policy will remain distinct.</p></section>',
            unsafe_allow_html=True,
        )
        opening = _opening_transition(experiment, replay(experiment, ()))
        if opening and st.button(
            "Begin a disruption run",
            key="lab_begin_disruption",
            type="primary",
            width="stretch",
        ):
            st.session_state[_state_key(experiment, "commands")] = [
                Command.transition(opening.id)
            ]
            st.session_state[_state_key(experiment, "counterpart_reaction")] = ""
            st.rerun()
        return

    _render_break(experiment, session)
    if not state.pending_messages:
        if st.button("Wait", key="lab_disrupt_wait"):
            _append_command(experiment, Command.wait(1))
        st.caption("Advance logical time by one tick")
    st.divider()
    if st.button(
        "Interpret what happened",
        key="lab_continue_to_interpret",
        type="primary",
        width="stretch",
    ):
        st.session_state[_state_key(experiment, "current_stage")] = "interpret"
        st.rerun()


def _render_interpret_stage(
    experiment: ExperimentDefinition,
    session: Replay,
) -> None:
    _render_understand(experiment, session)
    if st.button(
        "Respond with a Field Note",
        key="lab_continue_to_respond",
        type="primary",
        width="stretch",
    ):
        st.session_state[_state_key(experiment, "current_stage")] = "respond"
        st.rerun()


def render_laboratory(
    *,
    experiment: ExperimentDefinition,
    repository: Any,
    participant_id: str,
) -> None:
    _apply_styles()
    session = _current_replay(experiment)
    state = session.final_state
    _render_ambient_discoveries(experiment)
    stage_key = _state_key(experiment, "current_stage")
    current_stage = str(st.session_state.setdefault(stage_key, "connect"))
    if current_stage not in {"connect", "disrupt", "interpret", "respond"}:
        current_stage = "connect"
        st.session_state[stage_key] = current_stage
    st.markdown(
        '<div class="lab-topbar">'
        f'<b>Protocol Laboratory &nbsp; / &nbsp; Experiment {experiment.experiment_number:02d} &nbsp; / &nbsp; {html.escape(experiment.atlas_functions[0])}</b>'
        f'<span>{html.escape(current_stage.upper())}</span>'
        "</div>",
        unsafe_allow_html=True,
    )
    rail_column, workspace_column, telemetry_column = st.columns(
        (0.72, 3.25, 1.02),
        gap="small",
    )
    with rail_column:
        with st.container(key="lab_rail"):
            _render_lab_rail(experiment, current_stage)
    with workspace_column:
        with st.container(key="lab_workspace"):
            heading_column, inspect_column = st.columns((4.5, 1))
            with heading_column:
                st.markdown(
                    '<section class="lab-experience-heading">'
                    f'<div class="lab-kicker">Experiment {experiment.experiment_number:02d} &nbsp; / &nbsp; {html.escape(experiment.atlas_functions[0])}</div>'
                    f'<h1>{html.escape(experiment.experience_title)}</h1>'
                    '<p class="lab-situation-line">Think about beginning communication.</p>'
                    '</section>',
                    unsafe_allow_html=True,
                )
            inspect_key = _state_key(experiment, "inspect_open")
            with inspect_column:
                if st.button(
                    "Close inspect" if st.session_state.get(inspect_key) else "Inspect",
                    key="lab_toggle_inspect",
                    width="stretch",
                ):
                    st.session_state[inspect_key] = not bool(
                        st.session_state.get(inspect_key)
                    )
                    st.rerun()
            if st.session_state.get(inspect_key):
                _render_inspection(experiment, session)

            _render_stage_progress(current_stage)
            st.markdown(
                f'<div class="lab-guided-question">{html.escape(experiment.human_question)}</div>',
                unsafe_allow_html=True,
            )

            if current_stage == "connect":
                _render_connect(experiment, session)
            elif current_stage == "disrupt":
                _render_disrupt_stage(experiment, session)
            elif current_stage == "interpret":
                _render_interpret_stage(experiment, session)
            else:
                _render_field_notes(
                    experiment,
                    session,
                    repository=repository,
                    participant_id=participant_id,
                )

            with st.expander("Advanced · Protocol archaeology and evolution"):
                _render_archaeology(experiment)
            if current_stage != "respond":
                with st.expander("Library · Field notes"):
                    _render_field_notes(
                        experiment,
                        session,
                        repository=repository,
                        participant_id=participant_id,
                    )
    with telemetry_column:
        with st.container(key="lab_telemetry"):
            _render_telemetry(experiment, session)
