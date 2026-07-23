import pytest

from protocol import (
    access_key_emoji,
    access_key_hash,
    build_question_feedback,
    normalize_access_key,
)


PARTICIPANT = "00000000-0000-4000-8000-000000000001"


def test_access_key_has_copyable_text_hash_and_stable_emoji() -> None:
    assert normalize_access_key(PARTICIPANT) == PARTICIPANT
    assert len(access_key_hash(PARTICIPANT)) == 64
    assert access_key_hash(PARTICIPANT) == access_key_hash(PARTICIPANT)
    assert len(access_key_emoji(PARTICIPANT)) >= 4


def test_invalid_access_key_is_rejected() -> None:
    with pytest.raises(ValueError, match="complete textual access key"):
        normalize_access_key("◆✨🌋🏅")


def test_skip_requires_a_reason_and_preserves_labels() -> None:
    with pytest.raises(ValueError, match="why you are skipping"):
        build_question_feedback(
            event_type="question_skipped",
            participant_uuid=PARTICIPANT,
            session_code="commons_pilot_2026",
            protocol_id="commons_smoke",
            protocol_version="0.2.0-draft",
            question_id="DEC_001",
            question_prompt="What do you do first?",
            flags=[],
            note="",
        )

    feedback = build_question_feedback(
        event_type="question_skipped",
        participant_uuid=PARTICIPANT,
        session_code="commons_pilot_2026",
        protocol_id="commons_smoke",
        protocol_version="0.2.0-draft",
        question_id="DEC_001",
        question_prompt="What do you do first?",
        flags=["unclear", "unclear", "unknown"],
        note="  Needs  context. ",
        created_at="2026-07-22T12:00:00+00:00",
    )

    assert feedback["flags"] == ["unclear"]
    assert feedback["flag_labels"] == ["Unclear"]
    assert feedback["note"] == "Needs context."


def test_flag_must_contain_feedback() -> None:
    with pytest.raises(ValueError, match="Choose a flag"):
        build_question_feedback(
            event_type="question_flagged",
            participant_uuid=PARTICIPANT,
            session_code="commons_pilot_2026",
            protocol_id="commons_smoke",
            protocol_version="0.2.0-draft",
            question_id="RAT_001",
            question_prompt="Why did you choose this?",
            flags=[],
            note="",
        )
