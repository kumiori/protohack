"""Shared participant flow for YAML-authored questionnaire tracks."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
import html
import uuid
from typing import Any

import streamlit as st

from protocol import QuestionDefinition, QuestionSetBundle, normalize_access_key
from ui import participant_refinement_styles


@dataclass(frozen=True)
class RuntimeScenario:
    id: str
    title: str
    body: str
    notice: str


@dataclass(frozen=True)
class RuntimeOption:
    value: str
    label: str
    description: str = ""


@dataclass(frozen=True)
class TrackRuntime:
    scenario: RuntimeScenario | None = None
    options_by_question: dict[str, tuple[RuntimeOption, ...]] | None = None

    def options_for(self, question_id: str) -> tuple[RuntimeOption, ...]:
        return (self.options_by_question or {}).get(question_id, ())


def participant_uuid() -> str:
    stored = st.session_state.get("participant_uuid")
    if stored:
        return str(stored)
    candidate = str(st.query_params.get("run") or "")
    try:
        value = normalize_access_key(candidate)
    except ValueError:
        value = str(uuid.uuid4())
        st.query_params["run"] = value
    st.session_state.participant_uuid = value
    return value


def _state_key(bundle: QuestionSetBundle) -> str:
    return f"question_track_{bundle.question_set_id}"


def _track_state(bundle: QuestionSetBundle) -> dict[str, Any]:
    key = _state_key(bundle)
    state = st.session_state.get(key)
    if not isinstance(state, dict):
        state = {
            "stage": "intro",
            "index": 0,
            "answers": {},
            "result": None,
        }
        st.session_state[key] = state
    return state


def _reset_track(bundle: QuestionSetBundle) -> None:
    prefix = f"track_widget_{bundle.question_set_id}_"
    for key in list(st.session_state):
        if str(key).startswith(prefix):
            st.session_state.pop(key, None)
    st.session_state.pop(_state_key(bundle), None)


def _apply_track_styles() -> None:
    participant_refinement_styles()
    st.markdown(
        """
        <style>
        .track-masthead { display:flex; justify-content:space-between; align-items:center; gap:1rem; padding:1.35rem 0 .65rem; border-bottom:1px solid rgba(18,33,27,.25); }
        .track-masthead strong { font-size:1rem; letter-spacing:-.02em; }
        .track-code { padding:.25rem .58rem; border:1px solid rgba(18,33,27,.45); border-radius:999px; font-family:"DM Mono",monospace; font-size:.68rem; text-transform:uppercase; letter-spacing:.08em; color:var(--ink); }
        .track-hero { padding:clamp(2.8rem,7vw,6rem) 0 2rem; max-width:960px; }
        .track-hero h1 { margin:.35rem 0 1rem; }
        .track-hero p { max-width:720px; font-size:1.2rem; line-height:1.55; color:rgba(18,33,27,.68); }
        .track-question { padding:clamp(1.2rem,3vw,2.4rem); margin:1rem 0 2rem; border:2px solid var(--ink); border-radius:22px; background:#fffdf6; box-shadow:9px 9px 0 var(--ink); }
        .track-question h2 { font-size:clamp(1.65rem,3.4vw,2.8rem) !important; margin:.5rem 0 .75rem; max-width:900px; }
        .track-context { color:rgba(18,33,27,.66); max-width:760px; line-height:1.55; }
        .track-review-row { display:grid; grid-template-columns:4rem minmax(0,1fr); gap:1rem; padding:1rem 0; border-bottom:1px solid rgba(18,33,27,.16); }
        .track-review-id { font-family:"DM Mono",monospace; font-size:.72rem; color:rgba(18,33,27,.55); }
        .track-review-row strong { display:block; margin-bottom:.35rem; }
        .track-review-value { color:rgba(18,33,27,.72); overflow-wrap:anywhere; }
        .track-done { padding:clamp(2rem,5vw,4rem); border:2px solid var(--ink); border-radius:22px; background:#fffdf6; text-align:center; margin:2rem 0; }
        .track-done-mark { width:4rem; height:4rem; margin:0 auto 1rem; display:grid; place-items:center; border:2px solid var(--ink); border-radius:50%; background:var(--acid); font-size:2rem; font-weight:800; }
        [class*="st-key-begin_"] button {
          background:var(--acid) !important;
          color:var(--ink) !important;
          box-shadow:4px 4px 0 var(--ink) !important;
          min-height:3.35rem;
        }
        [class*="st-key-begin_"] button:hover {
          background:var(--acid) !important;
          transform:translate(2px,2px) !important;
          box-shadow:2px 2px 0 var(--ink) !important;
        }
        @media (max-width:640px) {
          .track-question { box-shadow:5px 5px 0 var(--ink); }
          .track-review-row { grid-template-columns:2.6rem minmax(0,1fr); }
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def _is_answered(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, (list, tuple, dict, set)):
        return bool(value)
    return True


def _format_answer(value: Any, runtime_options: tuple[RuntimeOption, ...] = ()) -> str:
    labels = {option.value: option.label for option in runtime_options}
    if value is None or value == "" or value == [] or value == {}:
        return "Skipped"
    if isinstance(value, dict):
        parts = [
            f"{key}: {item}"
            for key, item in value.items()
            if str(item or "").strip()
        ]
        return " · ".join(parts) or "Skipped"
    if isinstance(value, (list, tuple)):
        return ", ".join(labels.get(str(item), str(item)) for item in value)
    return labels.get(str(value), str(value))


def _render_scenario(runtime: TrackRuntime) -> str:
    scenario = runtime.scenario
    if scenario is None:
        st.warning("This scenario has not been resolved by the Strategy runtime.")
        return ""
    st.markdown(
        f"""
        <div class="scenario">
          <div class="eyebrow">{html.escape(scenario.id)}</div>
          <h2>{html.escape(scenario.title)}</h2>
          <p>{html.escape(scenario.body)}</p>
          <div class="notice">{html.escape(scenario.notice)}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    return scenario.id


def _render_question_input(
    *,
    bundle: QuestionSetBundle,
    question: QuestionDefinition,
    saved_answer: Any,
    runtime: TrackRuntime,
) -> Any:
    key = f"track_widget_{bundle.question_set_id}_{question.id}"
    runtime_options = runtime.options_for(question.id)
    option_values = (
        [option.value for option in runtime_options]
        if runtime_options
        else list(question.options)
    )
    option_labels = {option.value: option.label for option in runtime_options}

    if question.input_type == "scenario":
        return _render_scenario(runtime)
    if question.input_type == "multiselect":
        selected = st.pills(
            question.title,
            options=option_values,
            default=list(saved_answer or []),
            selection_mode="multi",
            format_func=lambda value: option_labels.get(value, value),
            label_visibility="collapsed",
            key=key,
        )
        return list(selected)
    if question.input_type == "single_choice":
        selected = st.radio(
            question.title,
            options=option_values,
            index=(
                option_values.index(saved_answer)
                if saved_answer in option_values
                else None
            ),
            format_func=lambda value: option_labels.get(value, value),
            label_visibility="collapsed",
            key=key,
        )
        if selected and runtime_options:
            description = next(
                (
                    option.description
                    for option in runtime_options
                    if option.value == selected
                ),
                "",
            )
            if description:
                st.caption(description)
        return selected
    if question.input_type in {"text", "textarea"}:
        return st.text_area(
            question.title,
            value=str(saved_answer or ""),
            placeholder=question.placeholder or None,
            height=150,
            label_visibility="collapsed",
            key=key,
        )
    if question.input_type in {"contact", "location"}:
        saved_fields = saved_answer if isinstance(saved_answer, dict) else {}
        values: dict[str, str] = {}
        for index, field in enumerate(question.fields):
            values[field] = st.text_input(
                field,
                value=str(saved_fields.get(field) or ""),
                key=f"{key}_{index}",
            )
        return values
    st.error(f"Unsupported field type: {question.input_type}")
    return None


def _review_rows(
    *,
    bundle: QuestionSetBundle,
    answers: dict[str, Any],
    runtime: TrackRuntime,
) -> None:
    for question in bundle.questions:
        if question.input_type == "review":
            continue
        value = answers.get(question.field_id)
        st.markdown(
            f"""
            <div class="track-review-row">
              <div class="track-review-id">{html.escape(question.id)}</div>
              <div>
                <strong>{html.escape(question.title)}</strong>
                <div class="track-review-value">{html.escape(_format_answer(value, runtime.options_for(question.id)))}</div>
              </div>
            </div>
            """,
            unsafe_allow_html=True,
        )


def render_question_track(
    *,
    bundle: QuestionSetBundle,
    submit: Callable[[dict[str, Any]], dict[str, Any]],
    runtime: TrackRuntime | None = None,
    completion_copy: str,
    next_page: str | None = None,
    next_label: str = "Continue",
) -> None:
    """Render a progressive track directly from one resolved YAML bundle."""

    _apply_track_styles()
    runtime = runtime or TrackRuntime()
    state = _track_state(bundle)
    questions = tuple(
        question
        for question in bundle.questions
        if question.input_type != "review"
    )

    st.markdown(
        f"""
        <div class="track-masthead">
          <strong>Question the commons.</strong>
          <span class="track-code">{html.escape(bundle.question_set_id)} · {html.escape(bundle.version)}</span>
        </div>
        """,
        unsafe_allow_html=True,
    )

    stage = str(state.get("stage") or "intro")
    if stage == "intro":
        st.markdown(
            f"""
            <div class="track-hero">
              <div class="eyebrow">Question set · {bundle.question_count} nodes</div>
              <h1>{html.escape(bundle.title)}</h1>
              <p>{html.escape(bundle.description)}</p>
            </div>
            """,
            unsafe_allow_html=True,
        )
        st.caption(bundle.summary)
        if st.button(
            f"Begin {bundle.title.lower()}",
            type="primary",
            width="stretch",
            key=f"begin_{bundle.question_set_id}",
        ):
            state["stage"] = "questions"
            state["index"] = 0
            st.rerun()
        return

    if stage == "done":
        st.markdown(
            f"""
            <div class="track-done">
              <div class="track-done-mark">✓</div>
              <div class="eyebrow">{html.escape(bundle.question_set_id)} complete</div>
              <h2>{html.escape(completion_copy)}</h2>
            </div>
            """,
            unsafe_allow_html=True,
        )
        if next_page:
            st.page_link(next_page, label=next_label, width="stretch")
        if st.button(
            f"Review {bundle.title.lower()} again",
            width="stretch",
            key=f"reset_{bundle.question_set_id}",
        ):
            _reset_track(bundle)
            st.rerun()
        return

    if stage == "review":
        st.progress(1.0, text=f"{bundle.title} · Review")
        st.markdown("## Review before submission")
        st.caption(
            "Check the complete track. Use Back to change any answer before submitting."
        )
        _review_rows(
            bundle=bundle,
            answers=dict(state.get("answers") or {}),
            runtime=runtime,
        )
        back, submit_column = st.columns([1, 2])
        if back.button("Back", width="stretch", key=f"review_back_{bundle.id}"):
            state["stage"] = "questions"
            state["index"] = max(0, len(questions) - 1)
            st.rerun()
        if submit_column.button(
            f"Submit {bundle.title.lower()}",
            type="primary",
            width="stretch",
            key=f"submit_{bundle.id}",
        ):
            try:
                state["result"] = submit(dict(state.get("answers") or {}))
            except ValueError as exc:
                st.error(str(exc))
            except Exception:
                st.error("Submission did not complete. Your answers are still here.")
            else:
                state["stage"] = "done"
                st.rerun()
        return

    index = min(max(int(state.get("index") or 0), 0), max(len(questions) - 1, 0))
    if not questions:
        st.error("This question set has no participant questions.")
        return
    question = questions[index]
    answers = state.setdefault("answers", {})
    progress = (index + 1) / (len(questions) + 1)
    st.progress(
        progress,
        text=f"{bundle.title} · {index + 1} of {len(questions)}",
    )
    if question.input_type != "scenario":
        st.markdown(
            f"""
            <div class="track-question">
              <div class="eyebrow">{html.escape(question.id)} · {html.escape(question.group)} · {"Required" if question.required else "Optional"}</div>
              <h2>{html.escape(question.title)}</h2>
              <div class="track-context">{html.escape(question.context)}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    answer = _render_question_input(
        bundle=bundle,
        question=question,
        saved_answer=answers.get(question.field_id),
        runtime=runtime,
    )

    continue_column, back_column, skip_column = st.columns([1.6, 0.5, 0.4])
    continue_clicked = continue_column.button(
        "Continue to review" if index + 1 >= len(questions) else "Continue",
        type="secondary",
        width="stretch",
        key=f"continue_{bundle.id}_{question.id}",
    )
    back_clicked = back_column.button(
        "Back",
        width="stretch",
        disabled=index == 0,
        key=f"back_{bundle.id}_{question.id}",
    )
    skip_clicked = skip_column.button(
        "Skip",
        width="stretch",
        disabled=question.required,
        key=f"skip_{bundle.id}_{question.id}",
    )

    if continue_clicked:
        if question.required and not _is_answered(answer):
            st.error("This question is required before continuing.")
        else:
            answers[question.field_id] = answer
            if index + 1 >= len(questions):
                state["stage"] = "review"
            else:
                state["index"] = index + 1
            st.rerun()
    elif back_clicked:
        answers[question.field_id] = answer
        state["index"] = index - 1
        st.rerun()
    elif skip_clicked:
        answers[question.field_id] = None
        if index + 1 >= len(questions):
            state["stage"] = "review"
        else:
            state["index"] = index + 1
        st.rerun()
