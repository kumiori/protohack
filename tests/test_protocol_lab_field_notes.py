import json
from pathlib import Path

from protocol import access_key_hash
from protocol_lab import (
    Command,
    build_field_note,
    export_field_note,
    load_experiment,
    replay,
)
from storage.memory import InMemoryRepository


SPEC_DIRECTORY = Path(__file__).parent.parent / "protocol_lab" / "specs"
PARTICIPANT = "00000000-0000-4000-8000-000000000001"


def completed_replay():
    experiment = load_experiment(SPEC_DIRECTORY / "tcp_handshake_v1.yaml")
    session = replay(
        experiment,
        (
            Command.transition("client_active_open"),
            Command.deliver("m0001"),
            Command.deliver("m0002"),
            Command.deliver("m0003"),
        ),
    )
    return experiment, session


def test_field_note_is_participant_observation_with_replay_evidence() -> None:
    experiment, session = completed_replay()
    note = build_field_note(
        experiment=experiment,
        session=session,
        access_key=PARTICIPANT,
        observations={
            "observation": "SYN leaves the initiator waiting.",
            "interpretation": "The first transition makes the roles asymmetric.",
            "critique": "Agreement must remain mutual and visible.",
            "amendment": "Show who allocated state first.",
        },
        challenged_rule_ids=("trust_syn_ack",),
        created_at="2026-08-04T12:00:00+00:00",
    )

    assert note.provenance == "participant_observation"
    assert note.owner_key_hash == access_key_hash(PARTICIPANT)
    assert note.replay_hash == session.replay_hash
    assert note.evidence_event_ids
    assert note.challenged_rule_ids == ("trust_syn_ack",)

    exported = export_field_note(note)
    serialized = json.dumps(exported)
    assert PARTICIPANT not in serialized
    assert note.owner_key_hash not in serialized
    assert exported["participant_alias"].startswith("P-")


def test_field_note_persistence_is_idempotent_and_separate_from_contact() -> None:
    experiment, session = completed_replay()
    note = build_field_note(
        experiment=experiment,
        session=session,
        access_key=PARTICIPANT,
        observations={"amendment": "Make refusal visible earlier."},
        created_at="2026-08-04T12:00:00+00:00",
    )
    repository = InMemoryRepository()

    assert repository.record_protocol_lab_field_note(note.as_record()) == note.as_record()
    assert repository.record_protocol_lab_field_note(note.as_record()) == note.as_record()
    assert repository.list_protocol_lab_field_notes(note.owner_key_hash) == [
        note.as_record()
    ]
    assert repository.get_coordination_interest(PARTICIPANT) is None

    repository.record_coordination_interest(
        participant_uuid=PARTICIPANT,
        session_code="protocol_lab_pilot_2026",
        email="participant@example.org",
        consent_version="protocol-lab-join-v1",
        consented_at="2026-08-04T12:05:00+00:00",
    )

    serialized_note = json.dumps(
        repository.list_protocol_lab_field_notes(note.owner_key_hash)
    )
    assert "participant@example.org" not in serialized_note
    assert repository.get_coordination_interest(PARTICIPANT)["email"] == (
        "participant@example.org"
    )


def test_field_note_rejects_undeclared_note_types() -> None:
    experiment, session = completed_replay()

    try:
        build_field_note(
            experiment=experiment,
            session=session,
            access_key=PARTICIPANT,
            observations={"comment": "An untyped generic comment."},
            created_at="2026-08-04T12:00:00+00:00",
        )
    except ValueError as exc:
        assert "Unknown Field Note type" in str(exc)
    else:
        raise AssertionError("An undeclared Field Note type was accepted")
