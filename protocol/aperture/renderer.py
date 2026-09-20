"""Native Streamlit renderer for the one V0 question aperture."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import streamlit as st

from .directives import ApertureDocument, Directive, split_directives
from .registry import QuestionDefinition
from .responses import append_response, build_response


def _show_trace(event: dict[str, Any], question: QuestionDefinition) -> None:
    st.success("Contribution recorded")
    st.markdown(
        f"**Question**  \n{question.title}  \n"
        f"**Response**  \n{_display_value(event.get('value'))}  \n"
        f"**Context**  \n{event['page_id']}  \n"
        f"**Status**  \n{event['status']}"
    )
    st.caption(f"Trace ID: {event['event_id']}")


def _display_value(value: Any) -> str:
    if isinstance(value, list):
        return ", ".join(str(item) for item in value) or "No response"
    return str(value or "No response")


def render_question(
    *,
    document: ApertureDocument,
    directive: Directive,
    question: QuestionDefinition,
    participant_id: str,
    response_path: Path,
) -> None:
    state_key = f"aperture_trace:{document.page_id}:{directive.id}"
    st.divider()
    st.subheader(question.title)
    if question.context:
        st.caption(question.context)
    value_key = f"aperture_value:{document.page_id}:{directive.id}"
    if question.mode == "multiple_choice":
        value = st.multiselect(
            question.title,
            question.options,
            key=value_key,
            label_visibility="collapsed",
            placeholder="Choose one or more",
        )
    else:
        value = st.radio(
            question.title,
            question.options,
            index=None,
            key=value_key,
            label_visibility="collapsed",
        )
    comment = ""
    if question.allow_comment:
        comment = st.text_input(
            "Optional comment",
            key=f"aperture_comment:{document.page_id}:{directive.id}",
        )
    left, middle, right = st.columns(3)
    action = None
    if left.button("Continue", type="primary", width="stretch", key=f"continue:{directive.id}"):
        action = "answered"
    if middle.button("Flag", width="stretch", key=f"flag:{directive.id}"):
        action = "answered_and_flagged" if value else "flagged"
    if right.button("Skip", width="stretch", key=f"skip:{directive.id}"):
        action = "skipped"
    if action:
        try:
            event = build_response(
                page_id=document.page_id,
                directive_id=directive.id,
                participant_id=participant_id,
                status=action,
                value=value,
                comment=comment,
            )
        except ValueError as exc:
            st.warning(str(exc))
        else:
            append_response(response_path, event)
            st.session_state[state_key] = event
    if state_key in st.session_state:
        _show_trace(st.session_state[state_key], question)
    st.divider()


def render_document(
    *,
    document: ApertureDocument,
    registry: dict[str, QuestionDefinition],
    participant_id: str,
    response_path: Path,
) -> None:
    for part in split_directives(document.body):
        if isinstance(part, str):
            if part.strip():
                st.markdown(part)
            continue
        question = registry.get(part.id)
        if question is None:
            st.error(f"Unknown question directive: {part.id}")
            continue
        render_question(
            document=document,
            directive=part,
            question=question,
            participant_id=participant_id,
            response_path=response_path,
        )
