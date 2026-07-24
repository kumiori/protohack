"""Shared participant flow for YAML-authored questionnaire tracks."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from email.utils import parseaddr
import html
import uuid
from typing import Any

import streamlit as st

from protocol import (
    FLAG_REASON_LABELS,
    FLAG_REASON_OPTIONS,
    SKIP_REASON_LABELS,
    SKIP_REASON_OPTIONS,
    QuestionDefinition,
    QuestionSetBundle,
    build_question_event,
    build_track_feedback,
    normalize_access_key,
)
from storage.base import Repository
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
            "result": None,
        }
        st.session_state[key] = state
    return state


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
        [class*="st-key-question_card_"] { padding:clamp(1.2rem,3vw,2.4rem); margin:1rem 0 2rem; border:2px solid var(--ink); border-radius:22px; background:#fffdf6; box-shadow:9px 9px 0 var(--ink); }
        [class*="st-key-question_card_"] .track-question { margin:0 0 1.15rem; }
        [class*="st-key-question_card_"] .scenario { padding:0; margin:0; border:0; border-radius:0; background:transparent; box-shadow:none; }
        .track-question h2 { font-size:clamp(1.65rem,3.4vw,2.8rem) !important; margin:.5rem 0 .75rem; max-width:900px; }
        .track-context { color:rgba(18,33,27,.66); max-width:760px; line-height:1.55; margin-bottom:.4rem; }
        .track-review-row { display:grid; grid-template-columns:4rem minmax(0,1fr); gap:1rem; padding:1rem 0; border-bottom:1px solid rgba(18,33,27,.16); }
        .track-review-id { font-family:"DM Mono",monospace; font-size:.72rem; color:rgba(18,33,27,.55); }
        .track-review-row strong { display:block; margin-bottom:.35rem; }
        .track-review-value { color:rgba(18,33,27,.72); overflow-wrap:anywhere; }
        .track-done { padding:clamp(2rem,5vw,4rem); border:2px solid var(--ink); border-radius:22px; background:#fffdf6; text-align:center; margin:2rem 0; }
        .track-done-mark { width:4rem; height:4rem; margin:0 auto 1rem; display:grid; place-items:center; border:2px solid var(--ink); border-radius:50%; background:var(--acid); font-size:2rem; font-weight:800; }
        .track-access-key { margin:1rem 0; padding:1rem; border:2px solid var(--ink); border-radius:14px; background:#fffdf6; font-family:"DM Mono",monospace; font-size:clamp(1rem,2.4vw,1.45rem); text-align:center; letter-spacing:.04em; overflow-wrap:anywhere; }
        .track-integration-copy { color:rgba(18,33,27,.72); line-height:1.55; }
        .track-action-help { margin:.35rem 0 .65rem; color:rgba(18,33,27,.58); font-size:.82rem; }
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
          [class*="st-key-question_card_"] { box-shadow:5px 5px 0 var(--ink); }
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
    if isinstance(value, dict):
        return any(_is_answered(item) for item in value.values())
    if isinstance(value, (list, tuple, set)):
        return any(_is_answered(item) for item in value)
    return True


def _valid_optional_email(value: str) -> bool:
    if not value.strip():
        return True
    parsed = parseaddr(value.strip())[1]
    return (
        parsed == value.strip()
        and "@" in parsed
        and "." in parsed.rsplit("@", 1)[-1]
    )


def _answer_validation_error(
    question: QuestionDefinition,
    answer: Any,
) -> str:
    if not _is_answered(answer):
        return "Answer this question or use Skip."
    if question.input_type == "contact" and isinstance(answer, dict):
        for field, value in answer.items():
            if "email" in str(field).lower() and not _valid_optional_email(str(value or "")):
                return "That email address does not look complete."
    return ""


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
    events: dict[str, dict[str, Any]],
    runtime: TrackRuntime,
) -> None:
    for question in bundle.questions:
        if question.input_type == "review":
            continue
        event = events.get(question.id) or {}
        status = str(event.get("status") or "")
        if status == "skipped":
            reason = SKIP_REASON_LABELS.get(
                str(event.get("reason_code") or ""),
                str(event.get("reason_code") or "Reason not recorded"),
            )
            note = str(event.get("reason_text") or "")
            value_copy = f"Skipped · {reason}"
            if note:
                value_copy += f" — {note}"
        else:
            value_copy = _format_answer(
                event.get("answer"),
                runtime.options_for(question.id),
            )
            if status == "answered_and_flagged":
                reason = FLAG_REASON_LABELS.get(
                    str(event.get("reason_code") or ""),
                    str(event.get("reason_code") or "Flagged"),
                )
                value_copy += f" · Flagged: {reason}"
        st.markdown(
            f"""
            <div class="track-review-row">
              <div class="track-review-id">{html.escape(question.id)}</div>
              <div>
                <strong>{html.escape(question.title)}</strong>
                <div class="track-review-value">{html.escape(value_copy)}</div>
              </div>
            </div>
            """,
            unsafe_allow_html=True,
        )


def _latest_flag(
    feedback: list[dict[str, Any]],
    *,
    participant_id: str,
    track_id: str,
    question_id: str,
) -> dict[str, Any] | None:
    matches = [
        row
        for row in feedback
        if row.get("event_type") == "question_flagged"
        and str(row.get("participant_id") or row.get("participant_uuid") or "")
        == participant_id
        and str(row.get("track_id") or "") == track_id
        and str(row.get("question_id") or "") == question_id
    ]
    return matches[-1] if matches else None


def _render_flag_control(
    *,
    repository: Repository,
    bundle: QuestionSetBundle,
    participant_id: str,
    question: QuestionDefinition,
    existing_flag: dict[str, Any] | None,
) -> None:
    with st.popover("Flag", width="stretch"):
        st.caption("Flag this question without losing your current answer.")
        with st.form(
            f"track_flag_form_{bundle.question_set_id}_{question.id}",
            border=False,
        ):
            existing_code = str((existing_flag or {}).get("reason_code") or "")
            reason_codes = [value for value, _label in FLAG_REASON_OPTIONS]
            selected = st.selectbox(
                "Reason",
                options=reason_codes,
                index=(
                    reason_codes.index(existing_code)
                    if existing_code in reason_codes
                    else None
                ),
                placeholder="Choose a reason",
                format_func=lambda value: FLAG_REASON_LABELS[value],
            )
            comment = st.text_input(
                "Optional short comment",
                value=str((existing_flag or {}).get("reason_text") or ""),
                placeholder="Optional short comment",
            )
            submitted = st.form_submit_button("Save flag", width="stretch")
        if submitted:
            try:
                feedback = build_track_feedback(
                    event_type="question_flagged",
                    participant_id=participant_id,
                    session_code=bundle.session_code,
                    track_id=bundle.question_set_id,
                    question_id=question.id,
                    question_prompt=question.title,
                    reason_code=selected,
                    reason_text=comment,
                )
                repository.record_question_feedback(feedback)
            except ValueError as exc:
                st.warning(str(exc))
            except Exception:
                st.error("The flag was not saved. Your answer is still here.")
            else:
                st.success("Flag saved. Continue or skip when you are ready.")
                st.rerun()


def _render_skip_dialog(
    *,
    repository: Repository,
    bundle: QuestionSetBundle,
    participant_id: str,
    question: QuestionDefinition,
    state: dict[str, Any],
) -> None:
    @st.dialog("Skip question", width="large")
    def skip_dialog() -> None:
        st.markdown(f"### {question.title}")
        st.caption(
            "Tell us why you are skipping. The reason is part of the protocol record."
        )
        reason_codes = [value for value, _label in SKIP_REASON_OPTIONS]
        selected = st.radio(
            "Why skip?",
            options=reason_codes,
            index=None,
            format_func=lambda value: SKIP_REASON_LABELS[value],
        )
        comment = st.text_area(
            "Short comment",
            placeholder="Optional, except when choosing Other",
            height=120,
        )
        if st.button(
            "Skip and continue",
            type="primary",
            width="stretch",
            key=f"confirm_skip_{bundle.question_set_id}_{question.id}",
        ):
            try:
                feedback = build_track_feedback(
                    event_type="question_skipped",
                    participant_id=participant_id,
                    session_code=bundle.session_code,
                    track_id=bundle.question_set_id,
                    question_id=question.id,
                    question_prompt=question.title,
                    reason_code=selected,
                    reason_text=comment,
                )
                event = build_question_event(
                    status="skipped",
                    participant_id=participant_id,
                    session_code=bundle.session_code,
                    track_id=bundle.question_set_id,
                    question_id=question.id,
                    question_prompt=question.title,
                    reason_code=selected,
                    reason_text=comment,
                )
                repository.record_question_feedback(feedback)
                repository.record_question_event(event)
            except ValueError as exc:
                st.warning(str(exc))
                return
            except Exception:
                st.error("The skip was not saved. Please try again.")
                return
            state.pop("skip_question_id", None)
            st.rerun()

    skip_dialog()


def _render_integration_dialog(
    *,
    bundle: QuestionSetBundle,
    participant_id: str,
    completion_copy: str,
    map_page: str,
) -> None:
    @st.dialog("Contribution integrated", width="large")
    def integration_dialog() -> None:
        st.markdown(f"## {html.escape(completion_copy)}")
        st.markdown("**Access key**")
        st.markdown(
            f'<div class="track-access-key">{html.escape(participant_id)}</div>',
            unsafe_allow_html=True,
        )
        st.markdown(
            """
            <div class="track-integration-copy">
              <strong>Take a screenshot of this screen.</strong><br>
              Keep this key if you want to recognise or retrieve your contribution later.
            </div>
            """,
            unsafe_allow_html=True,
        )
        st.caption(
            f"This key is stable for {bundle.title} and remains in your private run link."
        )
        map_column, finish_column = st.columns([1.4, 1])
        map_column.page_link(
            map_page,
            label="View the Commons Map",
            icon="🗺️",
            width="stretch",
        )
        if finish_column.button(
            "Finish",
            type="secondary",
            width="stretch",
            key=f"finish_{bundle.question_set_id}",
        ):
            st.switch_page("views/home_redirect.py")

    integration_dialog()


def render_question_track(
    *,
    bundle: QuestionSetBundle,
    submit: Callable[[dict[str, Any]], dict[str, Any]],
    repository: Repository,
    participant_id: str,
    runtime: TrackRuntime | None = None,
    completion_copy: str,
    next_page: str | None = None,
    next_label: str = "Continue",
    existing_result: dict[str, Any] | None = None,
    integration: bool = False,
) -> None:
    """Render an immutable, forward-only track from one resolved YAML bundle."""

    _apply_track_styles()
    runtime = runtime or TrackRuntime()
    state = _track_state(bundle)
    questions = tuple(
        question
        for question in bundle.questions
        if question.input_type != "review"
    )
    try:
        persisted_events = repository.list_question_events(
            bundle.question_set_id,
            participant_id,
        )
        feedback = repository.list_question_feedback(bundle.session_code)
    except Exception:
        st.error("This track could not load its saved progression. Please refresh.")
        return
    events_by_question = {
        str(event.get("question_id") or ""): event
        for event in persisted_events
        if str(event.get("question_id") or "")
    }
    completed_count = 0
    for question in questions:
        if question.id not in events_by_question:
            break
        completed_count += 1

    if existing_result:
        state["result"] = existing_result
        state["stage"] = "integration" if integration else "done"
    elif questions and completed_count >= len(questions):
        state["stage"] = "review"
    elif completed_count:
        state["stage"] = "questions"

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
        return

    if stage == "integration":
        st.progress(1.0, text=f"{bundle.title} · Integrated")
        _render_integration_dialog(
            bundle=bundle,
            participant_id=participant_id,
            completion_copy=completion_copy,
            map_page=next_page or "views/commons_map.py",
        )
        return

    if stage == "review":
        st.progress(1.0, text=f"{bundle.title} · Review")
        st.markdown("## Review before integration")
        st.caption(
            "This is a record of the contribution as it was made. Earlier responses cannot be revised."
        )
        _review_rows(
            bundle=bundle,
            events=events_by_question,
            runtime=runtime,
        )
        submit_label = (
            "Integrate contribution"
            if integration
            else f"Complete {bundle.title}"
        )
        if st.button(
            submit_label,
            type="primary",
            width="stretch",
            key=f"submit_{bundle.id}",
        ):
            answers = {
                question.field_id: events_by_question[question.id]["answer"]
                for question in questions
                if question.id in events_by_question
                and "answer" in events_by_question[question.id]
            }
            try:
                state["result"] = submit(answers)
            except ValueError as exc:
                st.error(str(exc))
            except Exception:
                st.error(
                    "Integration did not complete. Your immutable question events are still saved."
                )
            else:
                state["stage"] = "integration" if integration else "done"
                st.rerun()
        return

    if not questions:
        st.error("This question set has no participant questions.")
        return
    index = min(completed_count, len(questions) - 1)
    question = questions[index]
    progress = (index + 1) / (len(questions) + 1)
    st.progress(
        progress,
        text=f"{bundle.title} · {index + 1} of {len(questions)}",
    )
    with st.container(
        key=f"question_card_{bundle.question_set_id}_{question.id}",
        border=False,
    ):
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
            saved_answer=None,
            runtime=runtime,
        )
        validation_error = _answer_validation_error(question, answer)
        if validation_error:
            st.markdown(
                f'<div class="track-action-help">{html.escape(validation_error)}</div>',
                unsafe_allow_html=True,
            )
    existing_flag = _latest_flag(
        feedback,
        participant_id=participant_id,
        track_id=bundle.question_set_id,
        question_id=question.id,
    )
    continue_column, flag_column, skip_column = st.columns([1.6, 0.5, 0.4])
    continue_clicked = continue_column.button(
        "Continue",
        type="primary",
        width="stretch",
        disabled=bool(validation_error),
        key=f"continue_{bundle.id}_{question.id}",
    )
    with flag_column:
        _render_flag_control(
            repository=repository,
            bundle=bundle,
            participant_id=participant_id,
            question=question,
            existing_flag=existing_flag,
        )
    skip_clicked = skip_column.button(
        "Skip",
        width="stretch",
        key=f"skip_{bundle.id}_{question.id}",
    )

    if continue_clicked:
        status = "answered_and_flagged" if existing_flag else "answered"
        try:
            event = build_question_event(
                status=status,
                participant_id=participant_id,
                session_code=bundle.session_code,
                track_id=bundle.question_set_id,
                question_id=question.id,
                question_prompt=question.title,
                answer=answer,
                reason_code=(
                    str(existing_flag.get("reason_code") or "")
                    if existing_flag
                    else None
                ),
                reason_text=(
                    str(existing_flag.get("reason_text") or "")
                    if existing_flag
                    else None
                ),
            )
            repository.record_question_event(event)
        except ValueError as exc:
            st.error(str(exc))
        except Exception:
            st.error("The response was not saved. Please try again.")
        else:
            st.rerun()
    elif skip_clicked:
        state["skip_question_id"] = question.id

    if state.get("skip_question_id") == question.id:
        _render_skip_dialog(
            repository=repository,
            bundle=bundle,
            participant_id=participant_id,
            question=question,
            state=state,
        )
