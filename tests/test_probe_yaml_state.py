from probe_engine import ProbeRuntime
import pytest
import yaml
from streamlit.testing.v1 import AppTest
from streamlit.proto.Common_pb2 import FileURLs
from streamlit.runtime.uploaded_file_manager import UploadedFile, UploadedFileRec

from protocol.probe_draft import dump_probe_state, inspect_probe_state, load_probe_state
from protocol.probe_registry import resolve_probe
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
LOCAL_DEVELOPER_APP = ROOT / "tests" / "fixtures" / "probe_local_developer_app.py"
TEST_MODE_APP = ROOT / "tests" / "fixtures" / "probe_new_participant_app.py"
REVIEW_EXPORT_APP = ROOT / "tests" / "fixtures" / "probe_review_export_app.py"
RETURNING_REVIEW_APP = ROOT / "tests" / "fixtures" / "probe_returning_review_app.py"


def _runtime():
    registration = resolve_probe(event_slug="commons-montreal", variant="short")
    probe = registration.load()
    runtime = ProbeRuntime(
        probe,
        participant_id="participant",
        participation_id="participation",
        scope_id=registration.session_code,
    )
    return registration, probe, runtime


def test_complete_yaml_state_round_trip_is_semantically_lossless() -> None:
    registration, probe, runtime = _runtime()
    runtime.answer("participation_acknowledgement", "accept")
    runtime.answer("availability", ["oct28_am_online"])
    runtime.skip("dietary_preferences", reason_codes=["prefer_not"])
    runtime.flag("availability", reason_codes=["useful"])
    runtime.answer(
        "base_location",
        {
            "display_label": "Montréal, Québec, Canada",
            "locality": "Montréal",
            "region": "Québec",
            "country": "Canada",
            "country_code": "CA",
            "place_id": "test:montreal",
            "latitude": 45.5019,
            "longitude": -73.5674,
        },
    )
    runtime.answer(
        "functions",
        {
            "selected": ["research_teaching", "other"],
            "other": {"value": "Facilitation algorithmique"},
            "companions": {"function_title": "Modèle léger"},
        },
    )
    runtime.answer(
        "future_conditions",
        [
            {
                "id": "step-1",
                "action": "Documenter un protocole",
                "actors": {"selected": ["civil_society"]},
            }
        ],
    )

    exported = dump_probe_state(probe, runtime.trajectory)
    restored = load_probe_state(
        exported,
        probe=probe,
        expected_scope_id=registration.session_code,
    )

    assert restored == runtime.trajectory
    diagnostic = inspect_probe_state(exported, probe=probe)
    assert diagnostic["answers"] == 5
    assert diagnostic["skips"] == 1
    assert diagnostic["flags"] == 1


def test_partial_yaml_rebinds_runtime_identity_without_answering_later_fields() -> None:
    registration, probe, runtime = _runtime()
    runtime.answer("participation_acknowledgement", "accept")
    runtime.answer("availability", ["oct28_am_online"])
    exported = dump_probe_state(probe, runtime.trajectory)

    restored = load_probe_state(
        exported,
        probe=probe,
        participant_id="new-session-participant",
        participation_id="new-session-participation",
        expected_scope_id=registration.session_code,
    )
    hydrated = ProbeRuntime.hydrate(
        probe,
        restored,
        participant_id="new-session-participant",
        scope_id=registration.session_code,
    )
    review = {item.question_id: item for item in hydrated.review()}

    assert review["availability"].value == ["oct28_am_online"]
    assert review["knowledge_offer"].value is None


def test_revision_drift_is_explicitly_accepted_only_when_question_ids_are_compatible() -> None:
    registration, probe, runtime = _runtime()
    runtime.answer("availability", ["oct28_am_online"])
    payload = yaml.safe_load(dump_probe_state(probe, runtime.trajectory))
    payload["probe"]["revision"] = 4
    payload["trajectory"]["participation"]["probe_revision"] = 4

    diagnostic = inspect_probe_state(payload, probe=probe)
    restored = load_probe_state(
        payload,
        probe=probe,
        expected_scope_id=registration.session_code,
    )

    assert diagnostic["revision"] == 4
    assert diagnostic["current_revision"] == 5
    assert restored.participation.probe_revision == 5

    payload["trajectory"]["events"][0]["question_id"] = "removed_question"
    with pytest.raises(ValueError, match="removed_question"):
        load_probe_state(payload, probe=probe)


@pytest.mark.parametrize("app_path", (LOCAL_DEVELOPER_APP, TEST_MODE_APP))
def test_probe_surface_renders_yaml_controls_in_developer_modes(app_path: Path) -> None:
    app = AppTest.from_file(str(app_path), default_timeout=10).run()
    next(button for button in app.button if button.label == "Oui, je commence").click().run()

    assert not app.exception
    labels = [item.label for item in app.expander]
    assert "Developer · Response state" in labels
    assert "Charger des réponses" in [item.label for item in app.get("file_uploader")]
    assert "Télécharger YAML" in [item.label for item in app.get("download_button")]


def test_partial_yaml_upload_hydrates_canonical_session_without_persistence() -> None:
    registration, probe, source_runtime = _runtime()
    source_runtime.answer("participation_acknowledgement", "accept")
    partial_yaml = dump_probe_state(probe, source_runtime.trajectory)

    app = AppTest.from_file(str(LOCAL_DEVELOPER_APP), default_timeout=10).run()
    next(button for button in app.button if button.label == "Oui, je commence").click().run()
    participation_id = app.session_state[
        f"probe_participation_{registration.session_code}"
    ]
    upload_key = f"probe_state_upload_{participation_id}"
    app.session_state[upload_key] = UploadedFile(
        UploadedFileRec(
            "partial-state",
            "partial.yaml",
            "application/yaml",
            partial_yaml.encode("utf-8"),
        ),
        FileURLs(),
    )

    app.run()
    assert not app.exception
    assert "Fichier reconnu" in [item.value for item in app.success]
    diagnostic = next(code.value for code in app.code if "Probe       " in code.value)
    assert f"Probe       {probe.id}" in diagnostic
    assert f"Revision    {probe.revision}" in diagnostic
    assert "Réponses    1" in diagnostic

    next(button for button in app.button if button.label == "Charger dans la session").click().run()
    assert not app.exception
    hydrated = ProbeRuntime.hydrate(
        probe,
        app.session_state[f"probe_session_trajectory_{participation_id}"],
        participant_id=app.session_state["participant_uuid"],
        scope_id=registration.session_code,
    )
    assert {
        item.question_id: item.value for item in hydrated.review()
    }["participation_acknowledgement"] == "accept"
    assert app.session_state[f"probe_persistence_log_{participation_id}"] == []
    assert "Télécharger YAML" in [
        item.label for item in app.get("download_button")
    ]


def test_review_surface_renders_full_yaml_download() -> None:
    app = AppTest.from_file(str(REVIEW_EXPORT_APP), default_timeout=10).run()

    assert not app.exception
    labels = [item.label for item in app.get("download_button")]
    assert "Télécharger YAML" in labels
    assert "Télécharger mes réponses" in labels


def test_yaml_review_integration_reveals_credential_only_after_receipt() -> None:
    app = AppTest.from_file(str(REVIEW_EXPORT_APP), default_timeout=10).run()

    assert "J’ai conservé mon code" not in [item.label for item in app.button]
    next(
        button for button in app.button if button.label == "Intégrer mes réponses"
    ).click().run()

    assert not app.exception
    receipt = app.session_state[
        "probe_submission_receipt_review-export-participation"
    ]
    assert receipt["success"] is True
    assert "J’ai conservé mon code" in [item.label for item in app.button]
    assert app.session_state["probe_stage_review-export-participation"] == "review"

    next(
        button for button in app.button if button.label == "J’ai conservé mon code"
    ).click().run()
    assert not app.exception
    assert app.session_state["probe_stage_review-export-participation"] == "done"
    assert "Merci" in [item.value for item in app.title]


def test_returning_review_integrates_without_credential_dialog() -> None:
    app = AppTest.from_file(str(RETURNING_REVIEW_APP), default_timeout=10).run()

    assert "J’ai conservé mon code" not in [item.label for item in app.button]
    next(
        button for button in app.button if button.label == "Intégrer mes réponses"
    ).click().run()

    assert not app.exception
    assert "J’ai conservé mon code" not in [item.label for item in app.button]
    assert app.session_state["probe_stage_returning-review-participation"] == "done"
    assert "Merci" in [item.value for item in app.title]
