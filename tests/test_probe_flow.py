from pathlib import Path

import pytest
import yaml
from probe_engine import EventKind, ProbeRuntime

from protocol.probe_registry import registered_events, resolve_event, resolve_probe
from protocol.probe_store import ProbeRepositoryStore
from storage.memory import InMemoryRepository


ROOT = Path(__file__).parent.parent


def _source_text() -> str:
    return resolve_probe(session_code="montreal_communs_2026").source_path.read_text(
        encoding="utf-8"
    )


def _probe():
    return resolve_probe(session_code="montreal_communs_2026").load()


def test_montreal_resolves_through_the_generic_probe_registry() -> None:
    registration = resolve_probe(session_code="montreal_communs_2026")
    probe = registration.load()

    assert registration.event_id == "montreal_communs_2026"
    assert registration.event_slug == "commons-montreal"
    assert registration.probe_id == "montreal_communs_data_ai_short_2026"
    assert probe.id == registration.probe_id
    assert registration.source_path == ROOT / "question_sets" / "montreal_communs_2026" / "short.yaml"
    assert len(probe.steps) == 18
    assert probe.step("portrait").field_ids[:2] == ("name", "participation_position")


def test_both_montreal_sources_are_local_network_free_and_registered() -> None:
    registry_source = (ROOT / "protocol" / "probe_registry.py").read_text(encoding="utf-8")
    expected = {
        "commons-montreal": "short.yaml",
        "commons-montreal-initial-conditions": "initial_conditions_v0.yaml",
    }
    for slug, filename in expected.items():
        registration = resolve_probe(event_slug=slug)
        assert registration.source_path.name == filename
        assert registration.source_path.is_file()
        assert registration.source_path.is_relative_to(ROOT / "question_sets")
        assert registration.load().id == registration.probe_id
    assert "urlopen" not in registry_source
    assert "source_url" not in registry_source
    assert "tempfile" not in registry_source
    assert len(list((ROOT / "question_sets").rglob("short.yaml"))) == 1


def test_event_surface_wraps_the_generic_probe_adapter() -> None:
    root = Path(__file__).parent.parent
    app_source = (root / "app.py").read_text(encoding="utf-8")
    event_source = (root / "event_ui.py").read_text(encoding="utf-8")
    ui_source = (root / "probe_ui.py").read_text(encoding="utf-8")
    loader_source = (root / "protocol" / "question_sets.py").read_text(
        encoding="utf-8"
    )

    assert "page_for_event(event) for event in registered_events()" in app_source
    assert 'url_path=event.slug' in event_source
    assert 'view == "results"' in event_source
    assert 'view == "host"' in event_source
    assert "variant=variant" in event_source
    assert not (root / "views" / "montreal.py").exists()
    assert not (root / "views" / "montreal_overview.py").exists()
    assert not (root / "views" / "montreal_host.py").exists()
    assert not (root / "views" / "probe.py").exists()
    assert 'st.sidebar.expander("Developer · Identity"' in ui_source
    assert 'st.sidebar.expander("Developer · Persistence"' in ui_source
    assert 'st.sidebar.expander("Developer · Canonical event log"' in ui_source
    assert "TEST MODE · DRY RUN" in ui_source
    assert "with st.popover(label" in ui_source
    assert 'label="Signaler"' in ui_source
    assert '"Enregistrer la révision"' in ui_source
    assert "columns(2, gap=\"large\")" in ui_source
    assert "runtime.skip(" in ui_source
    assert 'label="Signaler"' in ui_source
    assert '"Passer"' in ui_source
    assert '"Intégrer au paysage commun"' in ui_source
    assert "runtime.flag(" in ui_source
    assert 'st.query_params["participation"] =' not in ui_source
    assert "_normalise_rich_questionnaire" not in loader_source
    assert not (root / "protocol" / "specs" / "montreal_communs_1.yaml").exists()


def test_long_and_short_are_distinct_registry_variants() -> None:
    short = resolve_probe(event_slug="commons-montreal", variant="short")

    assert short.variant == "short"
    with pytest.raises(ValueError, match="variant='long'"):
        resolve_probe(event_slug="commons-montreal", variant="long")


def test_event_registration_drives_canonical_surface_family() -> None:
    event = resolve_event(slug="commons-montreal")

    assert event.id == "montreal_communs_2026"
    assert event.default_view == "probe"
    assert event.results_enabled is True
    assert event.host_enabled is True
    assert event in registered_events()
    assert event.probes[0].session_code == event.id

    initial = resolve_event(slug="commons-montreal-initial-conditions")
    assert initial.default_view == "probe"
    assert initial.results_enabled is True
    assert initial.host_enabled is True
    assert initial.probes[0].probe_id == "montreal_initial_conditions_2026"


def test_test_results_restore_ephemeral_canonical_generation() -> None:
    source = (ROOT / "event_ui.py").read_text(encoding="utf-8")

    assert "Generate ephemeral synthetic test data" in source
    assert "evaluate_representation" in source
    assert "generated on this render · not persisted" in source
    assert "if test_mode:" in source


def test_authored_step_and_field_copy_crosses_the_canonical_boundary() -> None:
    source = yaml.safe_load(_source_text())
    probe = _probe()

    assert len(source["step_copy"]) == len(probe.steps) == 18
    assert len(source["questions"]) == len(probe.questions) == 24
    for step_id, authored_step in source["step_copy"].items():
        step = probe.step(step_id)
        assert (step.title, step.body, step.cta) == (
            authored_step["title"],
            authored_step["body"],
            authored_step["cta"],
        )
    for authored_field in source["questions"]:
        field = probe.question(authored_field["id"])
        assert field.prompt == authored_field["prompt"]
        assert field.revision == authored_field["revision"]


def test_participation_position_is_composable_and_controls_organisation_fields() -> None:
    probe = _probe()
    position = probe.question("participation_position")
    assert position.input_type.value == "multi_with_other"
    assert [option.value for option in position.options] == [
        "individual",
        "organisation",
        "other",
    ]
    condition = probe.question("organisation_name").visible_if
    assert condition is not None
    assert (condition.field_id, condition.operator, condition.value) == (
        "participation_position",
        "contains",
        "organisation",
    )

    runtime = ProbeRuntime(
        probe,
        participant_id="participant-position",
        scope_id="montreal_communs_2026",
    )
    runtime.answer("participation_position", ["individual", "organisation"])
    runtime.answer("organisation_name", "Organisation test")


def test_optional_companion_may_be_empty_without_invalidating_parent_answer() -> None:
    probe = _probe()
    runtime = ProbeRuntime(
        probe,
        participant_id="participant-companion",
        scope_id="montreal_communs_2026",
    )
    value = {"selected": ["governance_models"], "companions": {}}

    runtime.answer("knowledge_offer", value)

    assert {item.question_id: item.value for item in runtime.review()}[
        "knowledge_offer"
    ] == value


def test_grouped_taxonomy_presentation_uses_collapsed_expanders() -> None:
    source = (ROOT / "probe_ui.py").read_text(encoding="utf-8")

    assert "collapse_groups = bool(taxonomy and taxonomy.groups)" in source
    assert "st.expander(group.label, expanded=False)" in source


def test_canonical_values_survive_checkpoint_restart_and_hydration() -> None:
    probe = _probe()
    repository = InMemoryRepository()
    store = ProbeRepositoryStore(
        repository,
        probe_id=probe.id,
        participant_id="participant-1",
        scope_id="montreal_communs_2026",
    )
    runtime = ProbeRuntime(
        probe,
        participant_id="participant-1",
        scope_id="montreal_communs_2026",
        participation_id="participation-1",
    )
    answers = {
        "name": "Ada Lovelace",
        "availability": ["oct28_am_online"],
        "knowledge_offer": ["governance_models", "apis_ai"],
        "participation_position": ["organisation"],
        "document_project": "yes",
        "project_name": "Communs IA",
        "future_conditions": [
            {
                "id": "condition-1",
                "action": "Former une coalition",
                "actors": ["cultural_institution", "commons_movement"],
            }
        ],
    }
    for field_id, value in answers.items():
        runtime.answer(field_id, value)

    runtime.checkpoint(store)
    restored = store.load("participation-1")
    assert restored is not None
    hydrated = ProbeRuntime.hydrate(
        probe,
        restored,
        participant_id="participant-1",
        scope_id="montreal_communs_2026",
    )

    reviewed = {item.question_id: item for item in hydrated.review()}
    for field_id, value in answers.items():
        assert reviewed[field_id].value == value
        assert reviewed[field_id].question_revision == probe.question(field_id).revision


def test_structured_location_survives_checkpoint_restart_and_hydration() -> None:
    probe = _probe()
    repository = InMemoryRepository()
    store = ProbeRepositoryStore(
        repository,
        probe_id=probe.id,
        participant_id="participant-location",
        scope_id="montreal_communs_2026",
    )
    runtime = ProbeRuntime(
        probe,
        participant_id="participant-location",
        scope_id="montreal_communs_2026",
        participation_id="participation-location",
    )
    location = {
        "display_label": "Montréal, Québec, Canada",
        "locality": "Montréal",
        "region": "Québec",
        "country": "Canada",
        "country_code": "CA",
        "place_id": "opencage:montreal",
        "latitude": 45.5019,
        "longitude": -73.5674,
    }

    runtime.answer("base_location", location)
    runtime.checkpoint(store)
    restored = store.load("participation-location")
    assert restored is not None
    hydrated = ProbeRuntime.hydrate(
        probe,
        restored,
        participant_id="participant-location",
        scope_id="montreal_communs_2026",
    )

    assert {item.question_id: item.value for item in hydrated.review()}[
        "base_location"
    ] == location


def test_checkpoint_and_sync_arrival_are_persisted_without_release_logic() -> None:
    probe = _probe()
    repository = InMemoryRepository()
    store = ProbeRepositoryStore(
        repository,
        probe_id=probe.id,
        participant_id="participant-1",
        scope_id="montreal_communs_2026",
    )
    runtime = ProbeRuntime(
        probe,
        participant_id="participant-1",
        scope_id="montreal_communs_2026",
        participation_id="participation-1",
    )

    runtime.reach_section_boundary("exchange", store)

    assert [event.kind for event in runtime.trajectory.events] == [
        EventKind.CHECKPOINT,
        EventKind.SYNC_POINT_REACHED,
    ]
    restored = store.load("participation-1")
    assert restored == runtime.trajectory


def test_probe_store_reports_persistence_boundary_metadata() -> None:
    probe = _probe()
    diagnostics: list[dict] = []
    repository = InMemoryRepository()
    store = ProbeRepositoryStore(
        repository,
        probe_id=probe.id,
        participant_id="participant-1",
        scope_id="montreal_communs_2026",
        diagnostic_sink=diagnostics.append,
        target="test:probe_trajectories",
    )
    runtime = ProbeRuntime(
        probe,
        participant_id="participant-1",
        scope_id="montreal_communs_2026",
        participation_id="participation-1",
    )
    runtime.answer("name", "Private value")

    runtime.checkpoint(store)
    store.load("participation-1")

    assert [item["operation"] for item in diagnostics] == ["upsert", "load"]
    assert diagnostics[0]["target"] == "test:probe_trajectories"
    assert diagnostics[0]["record_identity"] == "participation-1"
    assert diagnostics[0]["trajectory_event_count"] == 1
    assert diagnostics[0]["success"] is True
    assert "duration_ms" in diagnostics[0]
    assert "Private value" not in repr(diagnostics)


def test_answer_skip_flag_and_review_revision_remain_distinct_events() -> None:
    probe = _probe()
    runtime = ProbeRuntime(
        probe,
        participant_id="participant-1",
        scope_id="montreal_communs_2026",
        participation_id="participation-1",
    )

    runtime.answer("availability", ["oct28_am_online"])
    runtime.skip("dietary_preferences", reason="participant_skip")
    runtime.answer("name", "Première réponse")
    runtime.flag(
        "name",
        reason_codes=["thought_provoking"],
        note="À approfondir",
    )
    runtime.answer("name", "Réponse révisée")
    runtime.answer("dietary_preferences", ["vegetarian"])

    review = {item.question_id: item for item in runtime.review()}
    assert review["availability"].value == ["oct28_am_online"]
    assert review["dietary_preferences"].state.startswith("answered")
    assert review["dietary_preferences"].value == ["vegetarian"]
    assert review["name"].value == "Réponse révisée"
    flagged = next(
        event for event in runtime.trajectory.events if event.kind == EventKind.FLAGGED
    )
    assert flagged.reason_codes == ("thought_provoking",)
    assert flagged.reason_note == "À approfondir"
    assert [event.kind for event in runtime.trajectory.events] == [
        EventKind.ANSWERED,
        EventKind.SKIPPED,
        EventKind.ANSWERED,
        EventKind.FLAGGED,
        EventKind.ANSWERED,
        EventKind.ANSWERED,
    ]


def test_repeatable_accepts_selected_suggestion_as_the_action_value() -> None:
    probe = _probe()
    runtime = ProbeRuntime(
        probe,
        participant_id="participant-1",
        scope_id="montreal_communs_2026",
        participation_id="participation-1",
    )
    value = [
        {
            "id": "step-1",
            "action": "Concertation / consultation",
            "actors": ["commons_movement"],
        }
    ]

    runtime.answer("future_conditions", value)

    review = {item.question_id: item for item in runtime.review()}
    assert review["future_conditions"].value == value


def test_composed_other_survives_checkpoint_hydration_and_review() -> None:
    probe = _probe()
    repository = InMemoryRepository()
    store = ProbeRepositoryStore(
        repository,
        probe_id=probe.id,
        participant_id="participant-1",
        scope_id="montreal_communs_2026",
    )
    runtime = ProbeRuntime(
        probe,
        participant_id="participant-1",
        scope_id="montreal_communs_2026",
        participation_id="participation-1",
    )
    value = {
        "selected": ["group", "other"],
        "companions": {"inspiration_detail": "Un laboratoire citoyen"},
    }

    runtime.answer("inspiration", value)
    runtime.checkpoint(store)
    restored = store.load("participation-1")
    assert restored is not None
    hydrated = ProbeRuntime.hydrate(
        probe,
        restored,
        participant_id="participant-1",
        scope_id="montreal_communs_2026",
    )

    review = {item.question_id: item for item in hydrated.review()}
    assert review["inspiration"].value == value


def test_nested_composed_other_survives_repeatable_answer() -> None:
    probe = _probe()
    runtime = ProbeRuntime(
        probe,
        participant_id="participant-1",
        scope_id="montreal_communs_2026",
        participation_id="participation-1",
    )
    value = [
        {
            "id": "step-1",
            "action": "Concertation / consultation",
            "actors": {
                "selected": ["civil_society", "other"],
                "other": {"value": "Habitant·es du quartier"},
            },
        }
    ]

    runtime.answer("future_conditions", value)

    review = {item.question_id: item for item in runtime.review()}
    assert review["future_conditions"].value == value
