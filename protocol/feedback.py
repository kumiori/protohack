"""Question feedback shared by flag and skip flows."""

from __future__ import annotations

from typing import Any, Iterable

from .domain import participant_alias, utc_now_iso


QUESTION_FLAG_OPTIONS: tuple[tuple[str, str], ...] = (
    ("interesting_question", "Interesting question"),
    ("useful_for_coordination", "Useful for coordination"),
    ("incomplete", "Incomplete"),
    ("misleading", "Misleading"),
    ("too_narrow", "Too narrow"),
    ("unclear", "Unclear"),
    ("missing_option", "Missing option"),
)
QUESTION_FLAG_LABELS = dict(QUESTION_FLAG_OPTIONS)


def normalize_question_feedback(
    flags: Iterable[Any] | None,
    note: str | None,
    *,
    require_reason: bool = False,
) -> tuple[list[str], str]:
    allowed = set(QUESTION_FLAG_LABELS)
    normalized_flags: list[str] = []
    seen: set[str] = set()
    for value in flags or []:
        token = str(value or "").strip()
        if token in allowed and token not in seen:
            normalized_flags.append(token)
            seen.add(token)
    normalized_note = " ".join(str(note or "").split())[:500]
    if require_reason and not normalized_flags and not normalized_note:
        raise ValueError("Tell us why you are skipping this question.")
    return normalized_flags, normalized_note


def build_question_feedback(
    *,
    event_type: str,
    participant_uuid: str,
    session_code: str,
    protocol_id: str,
    protocol_version: str,
    question_id: str,
    question_prompt: str,
    flags: Iterable[Any] | None,
    note: str | None,
    created_at: str | None = None,
) -> dict[str, Any]:
    if event_type not in {"question_flagged", "question_skipped"}:
        raise ValueError(f"Unsupported feedback event: {event_type}")
    normalized_flags, normalized_note = normalize_question_feedback(
        flags,
        note,
        require_reason=event_type == "question_skipped",
    )
    if event_type == "question_flagged" and not normalized_flags and not normalized_note:
        raise ValueError("Choose a flag or add a short note.")
    return {
        "event_type": event_type,
        "participant_uuid": participant_uuid,
        "participant_alias": participant_alias(participant_uuid),
        "session_code": session_code,
        "protocol_id": protocol_id,
        "protocol_version": protocol_version,
        "question_id": question_id,
        "question_prompt": " ".join(str(question_prompt or "").split())[:500],
        "flags": normalized_flags,
        "flag_labels": [QUESTION_FLAG_LABELS[flag] for flag in normalized_flags],
        "note": normalized_note,
        "created_at": created_at or utc_now_iso(),
    }
