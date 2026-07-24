"""YAML-driven Identity participant track at /commons."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from protocol import build_question_set_submission, load_question_set
from storage import get_repository
from track_ui import participant_uuid, render_question_track


bundle = load_question_set(
    Path(__file__).parents[1] / "protocol" / "specs" / "identity_v1.yaml"
)
repository = get_repository()
participant = participant_uuid()


def submit_identity(answers: dict[str, Any]) -> dict[str, Any]:
    submission = build_question_set_submission(
        bundle=bundle,
        participant_uuid=participant,
        answers=answers,
    )
    return repository.record_question_set_submission(submission)


render_question_track(
    bundle=bundle,
    submit=submit_identity,
    completion_copy="Your identity signals have been added.",
    next_page="views/capacity.py",
    next_label="Continue to Capacity →",
)
