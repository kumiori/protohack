from __future__ import annotations

from pathlib import Path

from probe_engine import ProbeRuntime, trajectory_from_dict
from streamlit.testing.v1 import AppTest

from protocol.probe_access import (
    access_code_from_key,
    normalize_emoji_selector,
    resolve_probe_access_input,
)
from protocol.access_keys import access_key_hash
from protocol.probe_registry import resolve_probe
from protocol.probe_store import ProbeRepositoryStore
from storage.memory import InMemoryRepository


ACCESS_KEY = "00000000-0000-4000-8000-000000000001"
NEW_PARTICIPANT_APP = Path(__file__).parent / "fixtures" / "probe_new_participant_app.py"


def test_new_participant_does_not_query_remote_storage_before_first_answer() -> None:
    app = AppTest.from_file(str(NEW_PARTICIPANT_APP), default_timeout=10).run()
    assert not app.exception

    next(button for button in app.button if button.label == "Oui, je commence").click().run()

    assert not app.exception
    assert any(
        title.value == "Informations sur ma participation" for title in app.title
    )


def test_four_emoji_selector_is_copy_safe_and_has_a_verifier() -> None:
    code = access_code_from_key(ACCESS_KEY)
    assert code.selector
    assert normalize_emoji_selector(" ".join(code.selector)) == code.selector
    assert code.verifier == access_key_hash(ACCESS_KEY)
    assert len(code.verifier) == 64


def test_full_and_short_credentials_resolve_to_the_same_selector() -> None:
    code = access_code_from_key(ACCESS_KEY)
    assert resolve_probe_access_input(code.selector) == (code.selector, None)
    assert resolve_probe_access_input(ACCESS_KEY) == (code.selector, code.verifier)


def test_generic_envelope_round_trips_into_results_trajectory() -> None:
    registration = resolve_probe(event_slug="commons-montreal", variant="short")
    probe = registration.load()
    repository = InMemoryRepository()
    runtime = ProbeRuntime(
        probe,
        participant_id="participant",
        participation_id="participation",
        scope_id=registration.session_code,
    )
    runtime.answer("availability", ["oct28_am_online"])
    store = ProbeRepositoryStore(
        repository,
        probe=probe,
        probe_id=probe.id,
        participant_id="participant",
        scope_id=registration.session_code,
        environment="test",
        batch_id="batch-1",
    )
    code = access_code_from_key(ACCESS_KEY)
    store.set_access_code(selector=code.selector, verifier=code.verifier)
    prepared = runtime.prepare_finalisation(idempotency_key="submission-1")
    preview = store.preview_payload(prepared, idempotency_key="submission-1")
    runtime.finalise(store, idempotency_key="submission-1", prepared=prepared)

    assert store.last_receipt is not None
    assert store.last_receipt["success"] is True
    assert store.last_receipt["repository_result"] == preview
    assert preview["schema"] == "probe-submission-envelope/v1"
    assert preview["payload"]["schema"] == "probe-submission/v1"
    assert preview["payload"]["answers"]["availability"] == ["oct28_am_online"]
    assert preview["access_code_selector"] == code.selector
    assert preview["state"] == "submitted"

    matches = repository.find_probe_trajectories_by_access_selector(code.selector)
    assert len(matches) == 1
    restored = trajectory_from_dict(matches[0]["trajectory"])
    hydrated = ProbeRuntime.hydrate(
        probe,
        restored,
        participant_id="participant",
        scope_id=registration.session_code,
    )
    assert {item.question_id: item.value for item in hydrated.review()}[
        "availability"
    ] == ["oct28_am_online"]


def test_discard_test_records_never_removes_production_envelopes() -> None:
    repository = InMemoryRepository()
    base = {
        "record_type": "probe_submission",
        "event_id": "event",
        "probe_id": "probe",
        "probe_revision": 1,
        "participant_id": "participant",
        "trajectory": {"participation": {}, "events": []},
    }
    repository.save_probe_trajectory(
        {**base, "participation_id": "test", "environment": "test", "batch_id": "a"}
    )
    repository.save_probe_trajectory(
        {**base, "participation_id": "prod", "environment": "production"}
    )
    assert repository.discard_probe_trajectories("event", "probe") == 1
    assert repository.get_probe_trajectory("test") is None
    assert repository.get_probe_trajectory("prod") is not None


def test_later_checkpoint_persists_every_earlier_uncheckpointed_answer() -> None:
    registration = resolve_probe(event_slug="commons-montreal", variant="short")
    probe = registration.load()
    repository = InMemoryRepository()
    runtime = ProbeRuntime(
        probe,
        participant_id="participant",
        participation_id="cumulative",
        scope_id=registration.session_code,
    )
    runtime.answer("availability", ["oct28_am_online"])
    runtime.answer("name", "Ada")
    runtime.answer("knowledge_offer", ["governance_models"])
    store = ProbeRepositoryStore(
        repository,
        probe=probe,
        probe_id=probe.id,
        participant_id="participant",
        scope_id=registration.session_code,
        environment="test",
    )

    prepared = runtime.prepare_checkpoint("exchange")
    runtime.commit_checkpoint("exchange", store, prepared=prepared)
    stored = repository.get_probe_trajectory("cumulative")
    assert stored is not None
    hydrated = ProbeRuntime.hydrate(
        probe,
        trajectory_from_dict(stored["trajectory"]),
        participant_id="participant",
        scope_id=registration.session_code,
    )
    answers = {item.question_id: item.value for item in hydrated.review()}
    assert answers["availability"] == ["oct28_am_online"]
    assert answers["name"] == "Ada"
    assert answers["knowledge_offer"] == ["governance_models"]
