from protocol import build_question_feedback, build_strategic_profile, load_protocol
from storage.memory import InMemoryRepository


PARTICIPANT = "00000000-0000-4000-8000-000000000001"


def _profile() -> dict:
    return build_strategic_profile(
        protocol=load_protocol(),
        participant_uuid=PARTICIPANT,
        action_id="ACT_001",
        rationale="I would first make the unequal maintenance burden visible.",
        integrated_at="2026-07-22T12:00:00+00:00",
    )


def test_strategy_integration_is_idempotent() -> None:
    repository = InMemoryRepository()
    first = repository.integrate_strategic_profile(_profile())
    changed = _profile()
    changed["rationale"] = "A later double click must not rewrite the first record."
    second = repository.integrate_strategic_profile(changed)

    assert first == second
    assert len(repository.list_strategic_profiles("commons_pilot_2026")) == 1


def test_yes_without_email_is_anonymous_interest() -> None:
    repository = InMemoryRepository()
    record = repository.record_coordination_interest(
        participant_uuid=PARTICIPANT,
        session_code="commons_pilot_2026",
        email=None,
        consent_version="pilot-interest-v1",
        consented_at="2026-07-22T12:01:00+00:00",
    )

    assert record["coordination_status"] == "anonymous_interest"
    assert record["email"] is None


def test_contact_deletion_never_deletes_strategy() -> None:
    repository = InMemoryRepository()
    repository.integrate_strategic_profile(_profile())
    repository.record_coordination_interest(
        participant_uuid=PARTICIPANT,
        session_code="commons_pilot_2026",
        email="participant@example.org",
        consent_version="pilot-interest-v1",
        consented_at="2026-07-22T12:01:00+00:00",
    )

    assert repository.delete_contact_data(PARTICIPANT) is True
    assert repository.get_coordination_interest(PARTICIPANT) is None
    assert len(repository.list_strategic_profiles("commons_pilot_2026")) == 1


def test_no_contact_record_is_created_for_not_now() -> None:
    repository = InMemoryRepository()
    repository.integrate_strategic_profile(_profile())

    assert repository.get_coordination_interest(PARTICIPANT) is None


def test_question_feedback_is_separate_from_strategy_and_contact() -> None:
    repository = InMemoryRepository()
    feedback = build_question_feedback(
        event_type="question_flagged",
        participant_uuid=PARTICIPANT,
        session_code="commons_pilot_2026",
        protocol_id="commons_smoke",
        protocol_version="0.2.0-draft",
        question_id="DEC_001",
        question_prompt="What do you do first?",
        flags=["missing_option"],
        note="A stewardship option is missing.",
        created_at="2026-07-22T12:00:00+00:00",
    )
    repository.record_question_feedback(feedback)

    rows = repository.list_question_feedback("commons_pilot_2026")
    assert rows == [feedback]
    assert repository.list_strategic_profiles("commons_pilot_2026") == []
    assert repository.list_coordination_interests("commons_pilot_2026") == []


def test_mosaic_contact_store_is_separate_from_analytical_responses() -> None:
    repository = InMemoryRepository()
    repository.record_question_set_contact(
        {
            "record_type": "mosaic_contacts",
            "question_set_id": "mosaic_v1",
            "participant_uuid": PARTICIPANT,
            "access_key": PARTICIPANT,
            "name": "Participant",
        }
    )
    repository.record_question_set_contact(
        {
            "record_type": "mosaic_contacts",
            "question_set_id": "mosaic_v1",
            "participant_uuid": PARTICIPANT,
            "access_key": PARTICIPANT,
            "email": "participant@example.org",
            "communication_consent": True,
        }
    )

    contact = repository.get_question_set_contact("mosaic_v1", PARTICIPANT)
    assert contact is not None
    assert contact["name"] == "Participant"
    assert contact["email"] == "participant@example.org"
    assert contact["communication_consent"] is True
    assert repository.list_question_set_submissions("mosaic_v1") == []
    assert repository.list_question_set_contacts("mosaic_v1") == [contact]
