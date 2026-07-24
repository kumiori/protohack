"""Immutable, forward-only participant events for YAML question tracks."""

from __future__ import annotations

import hashlib
import re
from typing import Any

from .domain import participant_alias, utc_now_iso


QUESTION_EVENT_STATUSES = frozenset(
    {"answered", "skipped", "answered_and_flagged"}
)

FLAG_REASON_OPTIONS: tuple[tuple[str, str], ...] = (
    ("unclear_wording", "Unclear wording"),
    ("missing_option", "Missing option"),
    ("not_applicable", "Not applicable"),
    ("sensitive_question", "Sensitive question"),
    ("technical_issue", "Technical issue"),
    ("other", "Other"),
)
FLAG_REASON_LABELS = dict(FLAG_REASON_OPTIONS)

SKIP_REASON_OPTIONS: tuple[tuple[str, str], ...] = (
    ("prefer_not_to_answer", "Prefer not to answer"),
    ("not_applicable", "Not applicable"),
    ("do_not_understand", "I do not understand the question"),
    ("no_suitable_option", "No suitable option"),
    ("other", "Other"),
)
SKIP_REASON_LABELS = dict(SKIP_REASON_OPTIONS)


def _compact_text(value: Any, *, limit: int = 500) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()[:limit]


def _has_answer(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, dict):
        return any(_has_answer(item) for item in value.values())
    if isinstance(value, (list, tuple, set)):
        return any(_has_answer(item) for item in value)
    return True


def _normalize_reason(
    *,
    reason_code: str | None,
    reason_text: str | None,
    labels: dict[str, str],
    require_other_text: bool,
) -> tuple[str, str]:
    code = _compact_text(reason_code, limit=80)
    text = _compact_text(reason_text)
    if code not in labels:
        raise ValueError("Choose a reason.")
    if require_other_text and code == "other" and not text:
        raise ValueError("Add a short comment when choosing Other.")
    return code, text


def _event_id(*, participant_id: str, track_id: str, question_id: str) -> str:
    source = f"{participant_id}:{track_id}:{question_id}".encode("utf-8")
    return hashlib.blake2s(source, digest_size=12).hexdigest()


def build_question_event(
    *,
    status: str,
    participant_id: str,
    session_code: str,
    track_id: str,
    question_id: str,
    question_prompt: str,
    answer: Any = None,
    reason_code: str | None = None,
    reason_text: str | None = None,
    timestamp: str | None = None,
) -> dict[str, Any]:
    """Build one immutable terminal event for a question."""

    if status not in QUESTION_EVENT_STATUSES:
        raise ValueError(f"Unsupported question status: {status}")

    event: dict[str, Any] = {
        "event_id": _event_id(
            participant_id=participant_id,
            track_id=track_id,
            question_id=question_id,
        ),
        "event_type": "question_event",
        "status": status,
        "question_id": _compact_text(question_id, limit=120),
        "question_prompt": _compact_text(question_prompt),
        "track_id": _compact_text(track_id, limit=120),
        "participant_id": participant_id,
        "participant_uuid": participant_id,
        "participant_alias": participant_alias(participant_id),
        "session_code": _compact_text(session_code, limit=120),
        "timestamp": timestamp or utc_now_iso(),
    }
    event["created_at"] = event["timestamp"]

    if status == "skipped":
        code, text = _normalize_reason(
            reason_code=reason_code,
            reason_text=reason_text,
            labels=SKIP_REASON_LABELS,
            require_other_text=True,
        )
        event["reason_code"] = code
        event["reason_text"] = text
        return event

    if not _has_answer(answer):
        raise ValueError("Answer this question or use Skip.")
    event["answer"] = answer

    if status == "answered_and_flagged":
        code, text = _normalize_reason(
            reason_code=reason_code,
            reason_text=reason_text,
            labels=FLAG_REASON_LABELS,
            require_other_text=False,
        )
        event["reason_code"] = code
        event["reason_text"] = text
    return event


def build_track_feedback(
    *,
    event_type: str,
    participant_id: str,
    session_code: str,
    track_id: str,
    question_id: str,
    question_prompt: str,
    reason_code: str | None,
    reason_text: str | None,
    timestamp: str | None = None,
) -> dict[str, Any]:
    """Build an immediate flag or skip feedback event with generic metadata."""

    if event_type == "question_flagged":
        labels = FLAG_REASON_LABELS
        require_other_text = False
    elif event_type == "question_skipped":
        labels = SKIP_REASON_LABELS
        require_other_text = True
    else:
        raise ValueError(f"Unsupported feedback event: {event_type}")

    code, text = _normalize_reason(
        reason_code=reason_code,
        reason_text=reason_text,
        labels=labels,
        require_other_text=require_other_text,
    )
    created_at = timestamp or utc_now_iso()
    return {
        "event_type": event_type,
        "participant_id": participant_id,
        "participant_uuid": participant_id,
        "participant_alias": participant_alias(participant_id),
        "session_code": _compact_text(session_code, limit=120),
        "track_id": _compact_text(track_id, limit=120),
        "protocol_id": _compact_text(track_id, limit=120),
        "protocol_version": "",
        "question_id": _compact_text(question_id, limit=120),
        "question_prompt": _compact_text(question_prompt),
        "reason_code": code,
        "reason_text": text,
        "flags": [code],
        "flag_labels": [labels[code]],
        "note": text,
        "timestamp": created_at,
        "created_at": created_at,
    }
