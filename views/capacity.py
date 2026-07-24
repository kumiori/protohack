"""YAML-driven Capacity participant track."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from protocol import build_question_set_submission, load_question_set
from storage import get_repository
from track_ui import participant_uuid, render_question_track


bundle = load_question_set(
    Path(__file__).parents[1] / "protocol" / "specs" / "capacity_v1.yaml"
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


def submit_capacity(answers: dict[str, Any]) -> dict[str, Any]:
    submission = build_question_set_submission(
        bundle=bundle,
        participant_uuid=participant,
        answers=answers,
    )
    return repository.record_question_set_submission(submission)


render_question_track(
    bundle=bundle,
    submit=submit_capacity,
    repository=repository,
    participant_id=participant,
    completion_copy="Your capacity signals have been added.",
    next_page="views/strategy.py",
    next_label="Continue to Strategy →",
    existing_result=existing_submission,
)
