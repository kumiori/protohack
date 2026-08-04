import pytest

from protocol import build_question_event, build_track_feedback
from storage.memory import InMemoryRepository


PARTICIPANT = "00000000-0000-4000-8000-000000000001"
BASE = {
    "participant_id": PARTICIPANT,
    "session_code": "commons_pilot_2026",
    "track_id": "identity_v1",
    "question_id": "I1",
    "question_prompt": "Which roles best describe your participation?",
}


def test_answered_event_contains_the_answer_and_no_skip_sentinel() -> None:
    event = build_question_event(
        **BASE,
        status="answered",
        answer=["Researcher"],
        timestamp="2026-07-24T12:00:00+00:00",
    )

    assert event["status"] == "answered"
    assert event["answer"] == ["Researcher"]
    assert event["question_id"] == "I1"
    assert event["track_id"] == "identity_v1"
    assert event["participant_id"] == PARTICIPANT
    assert event["timestamp"] == "2026-07-24T12:00:00+00:00"
    assert "reason_code" not in event


def test_skip_is_explicit_and_never_encoded_as_a_null_answer() -> None:
    event = build_question_event(
        **BASE,
        status="skipped",
        reason_code="prefer_not_to_answer",
        reason_text="",
    )

    assert event["status"] == "skipped"
    assert event["reason_code"] == "prefer_not_to_answer"
    assert event["reason_text"] == ""
    assert "answer" not in event


def test_skip_requires_a_reason_and_other_requires_comment() -> None:
    with pytest.raises(ValueError, match="Choose a reason"):
        build_question_event(**BASE, status="skipped")

    with pytest.raises(ValueError, match="short comment"):
        build_question_event(
            **BASE,
            status="skipped",
            reason_code="other",
            reason_text="",
        )


def test_answered_and_flagged_event_preserves_flag_reason() -> None:
    event = build_question_event(
        **BASE,
        status="answered_and_flagged",
        answer=["Researcher"],
        reason_code="missing_option",
        reason_text="My role is not represented.",
    )

    assert event["status"] == "answered_and_flagged"
    assert event["reason_code"] == "missing_option"
    assert event["reason_text"] == "My role is not represented."


def test_feedback_uses_platform_track_and_participant_fields() -> None:
    feedback = build_track_feedback(
        **BASE,
        event_type="question_flagged",
        reason_code="unclear_wording",
        reason_text="The scope is ambiguous.",
        timestamp="2026-07-24T12:00:00+00:00",
    )

    assert feedback["reason_code"] == "unclear_wording"
    assert feedback["reason_text"] == "The scope is ambiguous."
    assert feedback["track_id"] == "identity_v1"
    assert feedback["participant_id"] == PARTICIPANT
    assert feedback["timestamp"] == "2026-07-24T12:00:00+00:00"


def test_question_event_storage_is_forward_only_and_idempotent() -> None:
    repository = InMemoryRepository()
    first = build_question_event(
        **BASE,
        status="answered",
        answer=["Researcher"],
        timestamp="2026-07-24T12:00:00+00:00",
    )
    attempted_revision = build_question_event(
        **BASE,
        status="answered",
        answer=["Observer"],
        timestamp="2026-07-24T12:05:00+00:00",
    )

    assert repository.record_question_event(first) == first
    assert repository.record_question_event(attempted_revision) == first
    assert repository.list_question_events("identity_v1", PARTICIPANT) == [first]
