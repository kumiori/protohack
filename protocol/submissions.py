"""Build privacy-scoped, idempotent questionnaire submissions."""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
from typing import Any, Iterable

from .domain import participant_alias
from .question_sets import QuestionSetBundle


def _submitted_at() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _has_answer(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, (list, tuple, set, dict)):
        return bool(value)
    return True


def _submission_id(
    *,
    participant_uuid: str,
    question_set_id: str,
    version: str,
) -> str:
    source = f"{participant_uuid}:{question_set_id}:{version}".encode("utf-8")
    return hashlib.blake2s(source, digest_size=12).hexdigest()


def build_question_set_submission(
    *,
    bundle: QuestionSetBundle,
    participant_uuid: str,
    answers: dict[str, Any],
    excluded_field_ids: Iterable[str] = (),
    submitted_at: str | None = None,
) -> dict[str, Any]:
    """Return one anonymous bundle submission, excluding sensitive scopes."""

    excluded = set(excluded_field_ids)
    known_fields = {question.field_id for question in bundle.questions}
    unknown_fields = set(answers) - known_fields
    if unknown_fields:
        raise ValueError(
            "Unknown answer fields: " + ", ".join(sorted(unknown_fields))
        )

    response_rows: list[dict[str, Any]] = []
    for question in bundle.questions:
        if question.field_id in excluded:
            continue
        value = answers.get(question.field_id)
        if not _has_answer(value):
            continue
        response_rows.append(
            {
                "question_id": question.id,
                "field_id": question.field_id,
                "question_type": question.input_type,
                "value": value,
            }
        )

    return {
        "submission_id": _submission_id(
            participant_uuid=participant_uuid,
            question_set_id=bundle.question_set_id,
            version=bundle.version,
        ),
        "participant_uuid": participant_uuid,
        "participant_alias": participant_alias(participant_uuid),
        "campaign_slug": bundle.campaign_slug,
        "event_slug": bundle.event_slug,
        "session_code": bundle.session_code,
        "question_set_id": bundle.question_set_id,
        "schema_id": bundle.schema_id,
        "version": bundle.version,
        "responses": response_rows,
        "submitted_at": submitted_at or _submitted_at(),
    }
