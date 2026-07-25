"""Independent YAML-driven Mosaic participant track."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from protocol import (
    QuestionDefinition,
    build_question_set_submission,
    load_question_set,
)
from protocol.domain import utc_now_iso
from storage import get_repository
from track_ui import participant_uuid, render_question_track


bundle = load_question_set(
    Path(__file__).parents[1] / "protocol" / "specs" / "mosaic.yaml"
)
repository = get_repository()
participant = participant_uuid()
existing_submission = next(
    (
        row
        for row in repository.list_question_set_submissions(
            bundle.question_set_id
        )
        if str(row.get("participant_uuid") or "") == participant
    ),
    None,
)


def record_mosaic_contact_answer(
    question: QuestionDefinition,
    answer: Any,
) -> None:
    contact: dict[str, Any] = {
        "record_type": "mosaic_contacts",
        "question_set_id": bundle.question_set_id,
        "participant_uuid": participant,
        "access_key": participant,
        "updated_at": utc_now_iso(),
    }
    if question.field_id == "mosaic_name":
        contact["name"] = str(answer or "").strip() or None
    elif question.field_id == "mosaic_email":
        contact["email"] = str(answer or "").strip() or None
        contact["communication_consent"] = True
    repository.record_question_set_contact(contact)


def submit_mosaic(answers: dict[str, Any]) -> dict[str, Any]:
    submission = build_question_set_submission(
        bundle=bundle,
        participant_uuid=participant,
        answers=answers,
    )
    submission["record_type"] = "mosaic_responses"
    consent = answers.get("mosaic_communication_consent") == "yes"
    existing_contact = repository.get_question_set_contact(
        bundle.question_set_id,
        participant,
    )
    if existing_contact or consent:
        repository.record_question_set_contact(
            {
                "record_type": "mosaic_contacts",
                "question_set_id": bundle.question_set_id,
                "participant_uuid": participant,
                "access_key": participant,
                "communication_consent": consent,
                "updated_at": utc_now_iso(),
            }
        )
    return repository.record_question_set_submission(submission)


render_question_track(
    bundle=bundle,
    submit=submit_mosaic,
    repository=repository,
    participant_id=participant,
    completion_copy="Your contribution has entered the Mosaic map.",
    next_page="views/commons_map.py",
    existing_result=existing_submission,
    integration=True,
    record_scoped_answer=record_mosaic_contact_answer,
)
