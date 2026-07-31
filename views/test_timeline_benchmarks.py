"""Scenario-first benchmark onboarding for the trajectory game."""

from __future__ import annotations

import html

import streamlit as st

from protocol.timeline_benchmarks import (
    BENCHMARKS,
    CHALLENGES,
    LEVELS,
    Benchmark,
    Challenge,
    benchmark_by_id,
    benchmarks_for_level,
    challenge_by_id,
)


STATE_PREFIX = "timeline_benchmarks_"
ACTIVE_BENCHMARK_KEY = "timeline_active_benchmark"


def _key(name: str) -> str:
    return f"{STATE_PREFIX}{name}"


def _select_benchmark(benchmark: Benchmark) -> None:
    st.session_state[_key("selected_kind")] = "benchmark"
    st.session_state[_key("selected_id")] = benchmark.id


def _select_challenge(challenge: Challenge) -> None:
    st.session_state[_key("selected_kind")] = "challenge"
    st.session_state[_key("selected_id")] = challenge.id


def _selected_payload() -> dict[str, object]:
    kind = str(st.session_state.get(_key("selected_kind")) or "benchmark")
    selected_id = str(
        st.session_state.get(_key("selected_id")) or "cook-dinner"
    )
    if kind == "challenge":
        return challenge_by_id(selected_id).payload()
    payload = benchmark_by_id(selected_id).payload()
    payload["kind"] = "benchmark"
    return payload


def _start_experiment(payload: dict[str, object]) -> None:
    for key in tuple(st.session_state):
        if str(key).startswith("timeline_game_"):
            del st.session_state[key]
    st.session_state[ACTIVE_BENCHMARK_KEY] = payload
    st.switch_page("views/test_timeline_game.py")


def _render_benchmark_card(benchmark: Benchmark) -> None:
    with st.container(key=f"benchmark_card_{benchmark.id}"):
        st.markdown(
            f"""
            <div class="benchmark-card-copy">
              <small>Level {benchmark.level} · {html.escape(benchmark.horizon_label)}</small>
              <h3>{html.escape(benchmark.title)}</h3>
              <p>{html.escape(benchmark.observation)}</p>
            </div>
            """,
            unsafe_allow_html=True,
        )
        if st.button(
            "Choose experiment",
            key=f"choose_benchmark_{benchmark.id}",
            width="stretch",
        ):
            _select_benchmark(benchmark)
            st.rerun()


def _render_challenge_card(challenge: Challenge) -> None:
    with st.container(key=f"challenge_card_{challenge.id}"):
        constraint_text = " · ".join(challenge.constraints)
        st.markdown(
            f"""
            <div class="benchmark-card-copy">
              <small>Challenge {challenge.number:02d} · {html.escape(challenge.horizon_label)}</small>
              <h3>{html.escape(challenge.title)}</h3>
              <p>{html.escape(constraint_text)}</p>
            </div>
            """,
            unsafe_allow_html=True,
        )
        if st.button(
            "Accept challenge",
            key=f"choose_challenge_{challenge.id}",
            width="stretch",
        ):
            _select_challenge(challenge)
            st.rerun()


def _apply_benchmark_theme() -> None:
    st.markdown(
        """
        <style>
        @import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;500;600&display=swap');
        .stApp {
          background:
            radial-gradient(circle at 82% 0%, rgba(103,142,130,.13), transparent 32rem),
            #020707;
          color:#edf2ed;
        }
        [data-testid="stHeader"], [data-testid="stToolbar"], #MainMenu, footer { display:none; }
        .block-container { max-width:1500px; padding:1.7rem 2rem 4rem; }
        html, body, .stApp, button, input, textarea {
          font-family:"IBM Plex Mono", monospace !important;
        }
        button p { color:inherit !important; }
        .benchmark-hero {
          border-bottom:1px solid #293934; padding:.3rem 0 1.7rem; margin-bottom:1.2rem;
        }
        .benchmark-hero small, .benchmark-level small {
          color:#dfe875; text-transform:uppercase; letter-spacing:.16em; font-size:.65rem;
        }
        .benchmark-hero h1 {
          color:#f0f4ef; font-size:clamp(2rem,4vw,4rem); line-height:1;
          max-width:16ch; margin:.55rem 0 .75rem; letter-spacing:-.045em;
        }
        .benchmark-hero p {
          color:#92a39d; max-width:70ch; line-height:1.65; font-size:.86rem;
        }
        .benchmark-level {
          display:flex; justify-content:space-between; gap:2rem; align-items:end;
          margin:1.4rem 0 1rem;
        }
        .benchmark-hero h1,
        .benchmark-level h2,
        .benchmark-card-copy h3 {
          color:#edf2ed !important;
        }
        .benchmark-level h2 { margin:.3rem 0 0; font-size:1.3rem; }
        .benchmark-level p { color:#82938d; max-width:48ch; font-size:.76rem; }
        [class*="st-key-benchmark_card_"],
        [class*="st-key-challenge_card_"] {
          min-height:15rem; border:1px solid #31443e; border-radius:8px;
          background:linear-gradient(145deg,#06110f,#030807); padding:1.15rem;
        }
        .benchmark-card-copy { min-height:10.3rem; }
        .benchmark-card-copy small {
          color:#70837c; text-transform:uppercase; letter-spacing:.1em; font-size:.6rem;
        }
        .benchmark-card-copy h3 { font-size:1.05rem; margin:.65rem 0; }
        .benchmark-card-copy p { color:#8fa19a; line-height:1.55; font-size:.73rem; }
        [class*="st-key-choose_benchmark_"] button,
        [class*="st-key-choose_challenge_"] button {
          border:1px solid #536a62 !important; background:transparent !important;
          color:#b9cbc4 !important; box-shadow:none !important;
        }
        [class*="st-key-choose_benchmark_"] button:hover,
        [class*="st-key-choose_challenge_"] button:hover {
          border-color:#dfe875 !important; color:#dfe875 !important;
        }
        .benchmark-shape {
          min-height:10rem; display:flex; align-items:center; justify-content:center;
          border:1px dashed #41554e; border-radius:8px; color:#93a69f;
          background:#040b09; font-size:1.1rem; letter-spacing:.08em;
        }
        [data-testid="stSidebar"] {
          background:#030807; border-right:1px solid #263732;
        }
        [data-testid="stSidebar"] h2 { color:#edf2ed !important; font-size:1rem; }
        [data-testid="stSidebar"] h3 { color:#dfe875 !important; font-size:1rem; }
        [data-testid="stSidebar"] p, [data-testid="stSidebar"] .stCaption {
          color:#8fa19a !important; font-size:.72rem; line-height:1.55;
        }
        .benchmark-sidebar-brief {
          border-top:1px solid #2e413b; padding-top:1rem; margin-top:.5rem;
        }
        .benchmark-sidebar-brief small {
          color:#71847d; text-transform:uppercase; letter-spacing:.12em; font-size:.58rem;
        }
        .benchmark-sidebar-brief h3 { margin:.45rem 0; }
        .benchmark-sidebar-brief p { margin:.4rem 0; }
        .benchmark-vocabulary {
          display:flex; flex-wrap:wrap; gap:.35rem; margin:.8rem 0;
        }
        .benchmark-vocabulary span {
          border:1px solid #3d514a; border-radius:99px; padding:.2rem .45rem;
          color:#a9bbb4; font-size:.58rem;
        }
        .st-key-start_timeline_benchmark button {
          min-height:3.1rem; background:#dfe875 !important; color:#101711 !important;
          border:0 !important; box-shadow:none !important;
        }
        [data-testid="stButtonGroup"] button {
          background:#030807 !important; border-color:#344841 !important;
          color:#a6b8b1 !important;
        }
        button[data-testid="stBaseButton-pillsActive"] {
          background:#dfe875 !important; color:#11160e !important;
          border-color:#dfe875 !important;
        }
        @media(max-width:800px) {
          .block-container { padding:1rem 1rem 3rem; }
          .benchmark-level { display:block; }
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


_apply_benchmark_theme()

if _key("selected_id") not in st.session_state:
    _select_benchmark(benchmark_by_id("cook-dinner"))

selected = _selected_payload()
with st.sidebar:
    st.markdown("## Experiment brief")
    st.markdown(
        f"""
        <div class="benchmark-sidebar-brief">
          <small>{html.escape(str(selected.get('horizon_label') or 'Open horizon'))}</small>
          <h3>{html.escape(str(selected['title']))}</h3>
          <p>{html.escape(str(selected['prompt']))}</p>
        </div>
        """,
        unsafe_allow_html=True,
    )
    vocabulary = tuple(selected.get("vocabulary") or ())
    if vocabulary:
        tags = "".join(
            f"<span>{html.escape(str(item))}</span>" for item in vocabulary
        )
        st.markdown(
            f'<div class="benchmark-vocabulary">{tags}</div>',
            unsafe_allow_html=True,
        )
    suggestions = tuple(selected.get("suggested_moves") or ())
    if suggestions:
        with st.expander("Possible moves", expanded=False):
            for suggestion in suggestions:
                st.caption(f"· {suggestion}")
    if selected.get("private"):
        st.info("Private exercise. Nothing is shared or saved.")
    st.caption(
        "There is no single correct answer. The experiment is the geometry you choose."
    )
    if st.button(
        "Start drawing",
        key="start_timeline_benchmark",
        type="primary",
        width="stretch",
    ):
        _start_experiment(selected)

st.markdown(
    """
    <div class="benchmark-hero">
      <small>Protocol test 03 · onboarding laboratory</small>
      <h1>How would you draw this trajectory?</h1>
      <p>Every benchmark is a small experiment. Familiar situations teach the geometry first; collective, historical and impossible problems reveal what the language can become.</p>
    </div>
    """,
    unsafe_allow_html=True,
)

mode = st.segmented_control(
    "Benchmark mode",
    options=("Levels", "Challenges", "Shape reading"),
    default="Levels",
    key=_key("mode"),
    label_visibility="collapsed",
    width="stretch",
)

if mode == "Levels":
    level = int(
        st.segmented_control(
            "Level",
            options=tuple(LEVELS),
            default=1,
            key=_key("level"),
            format_func=lambda value: f"{value:02d}",
            width="stretch",
        )
    )
    level_title, level_description = LEVELS[level]
    st.markdown(
        f"""
        <div class="benchmark-level">
          <div><small>Level {level:02d}</small><h2>{html.escape(level_title)}</h2></div>
          <p>{html.escape(level_description)}</p>
        </div>
        """,
        unsafe_allow_html=True,
    )
    level_benchmarks = benchmarks_for_level(level)
    for start in range(0, len(level_benchmarks), 2):
        columns = st.columns(2, gap="medium")
        for column, benchmark in zip(
            columns,
            level_benchmarks[start : start + 2],
        ):
            with column:
                _render_benchmark_card(benchmark)

    if level == 8:
        hidden = next(
            benchmark for benchmark in BENCHMARKS if benchmark.hidden
        )
        with st.expander("Reveal the hidden benchmark", expanded=False):
            _render_benchmark_card(hidden)

elif mode == "Challenges":
    st.markdown(
        """
        <div class="benchmark-level">
          <div><small>Small missions</small><h2>Challenge cards</h2></div>
          <p>Learn by representing something, not by reading a tutorial.</p>
        </div>
        """,
        unsafe_allow_html=True,
    )
    for start in range(0, len(CHALLENGES), 2):
        columns = st.columns(2, gap="medium")
        for column, challenge in zip(columns, CHALLENGES[start : start + 2]):
            with column:
                _render_challenge_card(challenge)

else:
    st.markdown(
        """
        <div class="benchmark-level">
          <div><small>Future experiment</small><h2>Read the shape</h2></div>
          <p>Hide every label and infer the story from curvature, kinks and uncertainty alone.</p>
        </div>
        """,
        unsafe_allow_html=True,
    )
    shape_columns = st.columns(3)
    shape_labels = (
        "smooth · smooth · milestone",
        "uncertainty ≈ kink · climb",
        "flat · breakthrough · open landing",
    )
    for column, label in zip(shape_columns, shape_labels):
        with column:
            st.markdown(
                f'<div class="benchmark-shape">{html.escape(label)}</div>',
                unsafe_allow_html=True,
            )
    st.caption(
        "The next prototype can generate anonymous trajectories and ask participants to guess the project family."
    )
