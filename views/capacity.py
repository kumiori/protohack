"""YAML-driven Capacity participant track."""

from __future__ import annotations

from email.utils import parseaddr
from pathlib import Path
from typing import Any

from protocol import (
    build_question_set_submission,
    load_protocol,
    load_question_set,
)
from protocol.domain import utc_now_iso
from storage import get_repository
from track_ui import participant_uuid, render_question_track


bundle = load_question_set(
    Path(__file__).parents[1] / "protocol" / "specs" / "capacity_v1.yaml"
)
protocol = load_protocol()
repository = get_repository()
participant = participant_uuid()


def _valid_optional_email(value: str) -> bool:
    if not value.strip():
        return True
    parsed = parseaddr(value.strip())[1]
    return (
        parsed == value.strip()
        and "@" in parsed
        and "." in parsed.rsplit("@", 1)[-1]
    )


def submit_capacity(answers: dict[str, Any]) -> dict[str, Any]:
    contact = answers.get("coordination_contact")
    contact = contact if isinstance(contact, dict) else {}
    name = str(contact.get("Name or username") or "").strip()
    email = str(contact.get("Email") or "").strip()
    if not _valid_optional_email(email):
        raise ValueError(
            "That email address does not look complete. You may also leave it blank."
        )

    submission = build_question_set_submission(
        bundle=bundle,
        participant_uuid=participant,
        answers=answers,
        excluded_field_ids={"coordination_contact"},
    )
    saved = repository.record_question_set_submission(submission)
    if name or email:
        repository.record_coordination_interest(
            participant_uuid=participant,
            session_code=bundle.session_code,
            email=email or None,
            consent_version=protocol.coordination_consent_version,
            consented_at=utc_now_iso(),
            name=name or None,
        )
    return saved


render_question_track(
    bundle=bundle,
    submit=submit_capacity,
    completion_copy="Your capacity signals have been added.",
    next_page="views/strategy.py",
    next_label="Continue to Strategy →",
)
