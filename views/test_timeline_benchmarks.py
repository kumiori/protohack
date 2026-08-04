"""Scenario-first benchmark onboarding for the trajectory game."""

from __future__ import annotations

from datetime import date, timedelta
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


def _begin_benchmark(benchmark: Benchmark) -> None:
    _select_benchmark(benchmark)
    for name in (
        "start_choice",
        "custom_start_date",
        "end_date",
        "start_date",
        "end_date_value",
        "destination_choice",
        "custom_destination",
        "destination",
    ):
        st.session_state.pop(_key(name), None)
    st.session_state[_key("setup_stage")] = "horizon"


def _begin_challenge(challenge: Challenge) -> None:
    _select_challenge(challenge)
    for name in (
        "start_choice",
        "custom_start_date",
        "end_date",
        "start_date",
        "end_date_value",
        "destination_choice",
        "custom_destination",
        "destination",
    ):
        st.session_state.pop(_key(name), None)
    st.session_state[_key("setup_stage")] = "horizon"


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


def _destination_suggestions(payload: dict[str, object]) -> tuple[str, ...]:
    explicit = {
        "cook-dinner": ("Dinner served", "Friends around the table"),
        "bicycle-puncture": ("Bicycle ready to ride",),
        "birthday-dinner": ("Birthday celebrated", "Dinner served"),
        "new-apartment": ("Moved in", "First night at home"),
        "neighbourhood-picnic": ("Picnic happens",),
        "scientific-workshop": ("Workshop takes place", "Publication released"),
        "short-documentary": ("Film released",),
        "write-book": ("Manuscript complete", "Book published"),
        "open-source-project": ("First public release",),
        "public-initiative": ("Initiative operating",),
    }
    selected_id = str(payload.get("id") or "")
    if selected_id in explicit:
        return explicit[selected_id]
    title = str(payload.get("title") or "Journey").strip()
    return (f"{title} complete",)


def _render_setup_progress(stage: str) -> None:
    labels = ("Benchmark", "Time horizon", "Destination", "Imagine journey")
    order = {"horizon": 1, "destination": 2, "ready": 3}
    current = order.get(stage, 0)
    items: list[str] = []
    for index, label in enumerate(labels):
        if index < current:
            marker, state = "✓", "done"
        elif index == current:
            marker, state = "→", "current"
        else:
            marker, state = "○", "pending"
        items.append(
            f'<div class="benchmark-step {state}"><b>{marker}</b>'
            f"<span>{html.escape(label)}</span></div>"
        )
    st.markdown(
        f'<div class="benchmark-steps">{"".join(items)}</div>',
        unsafe_allow_html=True,
    )


def _render_guided_setup(payload: dict[str, object], stage: str) -> None:
    _render_setup_progress(stage)
    st.markdown(
        f"""
        <div class="benchmark-setup-title">
          <small>Experiment · {html.escape(str(payload.get('horizon_label') or 'Open horizon'))}</small>
          <h1>{html.escape(str(payload['title']))}</h1>
          <p>{html.escape(str(payload['prompt']))}</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    if stage == "horizon":
        st.markdown("## Where are you starting?")
        start_choice = st.segmented_control(
            "Starting point",
            options=("Now", "Tomorrow", "Custom"),
            default="Now",
            key=_key("start_choice"),
            label_visibility="collapsed",
            width="stretch",
        )
        if start_choice == "Tomorrow":
            start_date = date.today() + timedelta(days=1)
        elif start_choice == "Custom":
            start_date = st.date_input(
                "Start date",
                value=date.today(),
                key=_key("custom_start_date"),
            )
        else:
            start_date = date.today()

        suggested_end = start_date + timedelta(
            days=max(1, int(payload.get("horizon_days") or 1))
        )
        end_date = st.date_input(
            "The journey ends around",
            value=suggested_end,
            min_value=start_date,
            key=_key("end_date"),
        )
        st.caption(
            f"{start_date.strftime('%d %b %Y')} → "
            f"{end_date.strftime('%d %b %Y')} · "
            f"{max(1, (end_date - start_date).days)} day horizon"
        )
        back, onward = st.columns([1, 2])
        with back:
            if st.button(
                "← Experiments",
                key="benchmark_setup_back",
                width="stretch",
            ):
                st.session_state[_key("setup_stage")] = "browse"
                st.rerun()
        with onward:
            if st.button(
                "Choose destination →",
                key="benchmark_setup_horizon_next",
                type="primary",
                width="stretch",
            ):
                st.session_state[_key("start_date")] = start_date.isoformat()
                st.session_state[_key("end_date_value")] = end_date.isoformat()
                st.session_state[_key("setup_stage")] = "destination"
                st.rerun()
        return

    if stage == "destination":
        st.markdown("## Where do you plan to arrive?")
        suggestions = (*_destination_suggestions(payload), "Custom")
        destination_choice = st.segmented_control(
            "Destination",
            options=suggestions,
            default=suggestions[0],
            key=_key("destination_choice"),
            label_visibility="collapsed",
            width="stretch",
        )
        if destination_choice == "Custom":
            destination = st.text_input(
                "Name the destination",
                placeholder="What becomes possible at the end?",
                max_chars=64,
                key=_key("custom_destination"),
            ).strip()
        else:
            destination = str(destination_choice)
        st.caption(
            "This fixes where the trajectory lands, not every step needed to get there."
        )
        back, onward = st.columns([1, 2])
        with back:
            if st.button(
                "← Time horizon",
                key="benchmark_setup_destination_back",
                width="stretch",
            ):
                st.session_state[_key("setup_stage")] = "horizon"
                st.rerun()
        with onward:
            if st.button(
                "Create the endpoints →",
                key="benchmark_setup_destination_next",
                type="primary",
                disabled=not destination,
                width="stretch",
            ):
                st.session_state[_key("destination")] = destination
                st.session_state[_key("setup_stage")] = "ready"
                st.rerun()
        return

    start_value = date.fromisoformat(str(st.session_state[_key("start_date")]))
    end_value = date.fromisoformat(
        str(st.session_state[_key("end_date_value")])
    )
    destination = str(st.session_state[_key("destination")])
    st.markdown(
        f"""
        <div class="benchmark-reveal">
          <small>Let’s imagine the journey.</small>
          <div class="benchmark-endpoints" aria-label="Trajectory endpoints">
            <div><i></i><b>{start_value.strftime('%d %b')}</b><span>Starting here</span></div>
            <em></em>
            <div><i></i><b>{html.escape(destination)}</b><span>{end_value.strftime('%d %b %Y')}</span></div>
          </div>
          <h2>Your endpoints exist.</h2>
          <p>Now let the first path grow between them.</p>
        </div>
        """,
        unsafe_allow_html=True,
    )
    back, onward = st.columns([1, 2])
    with back:
        if st.button(
            "← Destination",
            key="benchmark_setup_ready_back",
            width="stretch",
        ):
            st.session_state[_key("setup_stage")] = "destination"
            st.rerun()
    with onward:
        if st.button(
            "Draw the trajectory",
            key="start_timeline_benchmark",
            type="primary",
            width="stretch",
        ):
            configured = dict(payload)
            configured.update(
                {
                    "start_date": start_value.isoformat(),
                    "end_date": end_value.isoformat(),
                    "horizon_days": max(1, (end_value - start_value).days),
                    "destination_label": destination,
                    "guided_setup": True,
                }
            )
            _start_experiment(configured)


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
            type=(
                "primary"
                if (
                    st.session_state.get(_key("selected_kind")) == "benchmark"
                    and st.session_state.get(_key("selected_id"))
                    == benchmark.id
                )
                else "secondary"
            ),
            width="stretch",
        ):
            _begin_benchmark(benchmark)
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
            type=(
                "primary"
                if (
                    st.session_state.get(_key("selected_kind")) == "challenge"
                    and st.session_state.get(_key("selected_id"))
                    == challenge.id
                )
                else "secondary"
            ),
            width="stretch",
        ):
            _begin_challenge(challenge)
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
          transition:border-color 140ms ease, transform 140ms ease,
            box-shadow 140ms ease;
        }
        [class*="st-key-benchmark_card_"]:hover,
        [class*="st-key-challenge_card_"]:hover {
          border-color:#64786f; transform:translateY(-2px);
          box-shadow:0 14px 36px rgba(0,0,0,.24);
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
          transition:transform 100ms ease, background 140ms ease,
            border-color 140ms ease !important;
        }
        [class*="st-key-choose_benchmark_"] button:hover,
        [class*="st-key-choose_challenge_"] button:hover {
          border-color:#dfe875 !important; color:#dfe875 !important;
          background:#0c1713 !important; transform:translateY(-2px);
        }
        [class*="st-key-choose_benchmark_"] button:active,
        [class*="st-key-choose_challenge_"] button:active,
        .stButton button:active,
        [data-testid="stButtonGroup"] button:active {
          transform:scale(.97) !important; transition-duration:70ms !important;
        }
        [class*="st-key-choose_benchmark_"] button[data-testid="stBaseButton-primary"],
        [class*="st-key-choose_challenge_"] button[data-testid="stBaseButton-primary"] {
          background:#dfe875 !important; color:#11160e !important;
          border-color:#dfe875 !important;
          box-shadow:0 0 0 3px rgba(223,232,117,.13) !important;
        }
        .benchmark-shape {
          min-height:10rem; display:flex; align-items:center; justify-content:center;
          border:1px dashed #41554e; border-radius:8px; color:#93a69f;
          background:#040b09; font-size:1.1rem; letter-spacing:.08em;
        }
        .st-key-start_timeline_benchmark button {
          min-height:3.7rem; background:#dfe875 !important; color:#101711 !important;
          border:0 !important; box-shadow:0 10px 30px rgba(0,0,0,.28) !important;
        }
        [data-testid="stButtonGroup"] button {
          background:#030807 !important; border-color:#344841 !important;
          color:#a6b8b1 !important; min-height:2.9rem;
          transition:background 140ms ease, color 140ms ease,
            transform 100ms ease !important;
        }
        [data-testid="stButtonGroup"] button:hover {
          background:#0a1512 !important; border-color:#91a69e !important;
          color:#edf2ed !important;
        }
        button[data-testid="stBaseButton-pillsActive"],
        button[data-testid="stBaseButton-segmented_controlActive"] {
          background:#dfe875 !important; color:#11160e !important;
          border-color:#dfe875 !important;
          box-shadow:inset 0 -3px 0 rgba(17,22,14,.18) !important;
        }
        button:disabled {
          opacity:.32 !important; cursor:not-allowed !important;
          border-style:dashed !important;
        }
        .benchmark-steps {
          display:grid; grid-template-columns:repeat(4,1fr); gap:.55rem;
          margin:.7rem 0 2.6rem;
        }
        .benchmark-step {
          display:flex; align-items:center; gap:.6rem; padding:.7rem .75rem;
          border-bottom:2px solid #263732; color:#64756f;
          font-size:.67rem; letter-spacing:.04em;
        }
        .benchmark-step b { font-size:.95rem; font-weight:500; }
        .benchmark-step.done { color:#8eaa9f; border-color:#47665c; }
        .benchmark-step.done b { color:#78d6a7; }
        .benchmark-step.current {
          color:#f0f4ef; border-color:#dfe875; background:#07110f;
        }
        .benchmark-step.current b { color:#dfe875; }
        .benchmark-setup-title {
          max-width:62rem; padding:0 0 2.4rem; margin-bottom:1.7rem;
          border-bottom:1px solid #263732;
        }
        .benchmark-setup-title small, .benchmark-reveal small {
          color:#dfe875; text-transform:uppercase; letter-spacing:.15em;
          font-size:.64rem;
        }
        .benchmark-setup-title h1 {
          color:#f0f4ef; font-size:clamp(2rem,4vw,3.7rem);
          line-height:1.05; letter-spacing:-.045em; margin:.55rem 0 .8rem;
        }
        .benchmark-setup-title h1,
        .benchmark-setup-title + div h2,
        [data-testid="stMain"] h2 {
          color:#edf2ed !important;
        }
        .benchmark-setup-title p {
          color:#91a39d; max-width:65ch; line-height:1.65; font-size:.82rem;
        }
        div[data-baseweb="input"] > div {
          background:#06100e !important; border-color:#3b5048 !important;
        }
        div[data-baseweb="input"] input {
          color:#edf2ed !important; caret-color:#dfe875 !important;
        }
        .st-key-benchmark_setup_back button,
        .st-key-benchmark_setup_destination_back button,
        .st-key-benchmark_setup_ready_back button {
          background:#06100e !important; color:#aebeb8 !important;
          border:1px solid #3a4e47 !important; box-shadow:none !important;
        }
        .st-key-benchmark_setup_back button:hover,
        .st-key-benchmark_setup_destination_back button:hover,
        .st-key-benchmark_setup_ready_back button:hover {
          color:#edf2ed !important; border-color:#82978f !important;
          transform:translateY(-1px);
        }
        .st-key-benchmark_setup_horizon_next button,
        .st-key-benchmark_setup_destination_next button {
          background:#dfe875 !important; color:#11160e !important;
          border:0 !important; box-shadow:0 8px 24px rgba(0,0,0,.24) !important;
        }
        .benchmark-reveal {
          min-height:24rem; display:flex; flex-direction:column;
          justify-content:center; text-align:center; padding:2rem;
          border:1px solid #23332e; border-radius:16px;
          background:radial-gradient(circle at 50% 50%,rgba(101,151,137,.10),transparent 40%);
          margin-bottom:1rem;
        }
        .benchmark-reveal h2 { margin:2.2rem 0 .35rem; color:#edf2ed; }
        .benchmark-reveal p { color:#84958f; }
        .benchmark-endpoints {
          display:grid; grid-template-columns:minmax(8rem,1fr) minmax(8rem,2fr) minmax(8rem,1fr);
          align-items:center; width:min(56rem,92%); margin:3rem auto 0;
        }
        .benchmark-endpoints > div {
          display:flex; flex-direction:column; align-items:center; gap:.35rem;
        }
        .benchmark-endpoints i {
          width:1.5rem; height:1.5rem; display:block; border-radius:50%;
          background:#edf2ed; box-shadow:0 0 0 8px rgba(237,242,237,.06);
          animation:endpoint-arrive 500ms cubic-bezier(.2,.8,.2,1) both;
        }
        .benchmark-endpoints > div:last-child i {
          background:transparent; border:2px solid #dfe875;
          animation-delay:180ms;
        }
        .benchmark-endpoints em {
          height:1px; border-top:1px dashed #4c625a; transform:scaleX(0);
          transform-origin:left; animation:path-preview 700ms 320ms ease forwards;
        }
        .benchmark-endpoints b { color:#edf2ed; font-size:.78rem; margin-top:.55rem; }
        .benchmark-endpoints span { color:#71827d; font-size:.62rem; }
        @keyframes endpoint-arrive {
          from { opacity:0; transform:scale(.25); }
          to { opacity:1; transform:scale(1); }
        }
        @keyframes path-preview {
          to { transform:scaleX(1); }
        }
        @media(max-width:800px) {
          .block-container { padding:1rem 1rem 3rem; }
          .benchmark-level { display:block; }
          .benchmark-steps { grid-template-columns:1fr 1fr; }
          .benchmark-endpoints { grid-template-columns:1fr; gap:1rem; }
          .benchmark-endpoints em { width:1px; height:3rem; border-top:0; border-left:1px dashed #4c625a; }
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


_apply_benchmark_theme()

if _key("selected_id") not in st.session_state:
    _select_benchmark(benchmark_by_id("cook-dinner"))

selected = _selected_payload()
setup_stage = str(st.session_state.get(_key("setup_stage")) or "browse")
if setup_stage != "browse":
    _render_guided_setup(selected, setup_stage)
else:
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

if setup_stage == "browse" and mode == "Levels":
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

elif setup_stage == "browse" and mode == "Challenges":
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

elif setup_stage == "browse":
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
