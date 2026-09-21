from pathlib import Path

import pytest
import yaml
from probe_engine import (
    EventKind,
    ProbeRuntime,
    ResolutionState,
    RuntimeError as ProbeRuntimeError,
    evaluate_representation,
)

from event_ui import _synthetic_trajectories
from protocol.probe_registry import registered_events, resolve_event, resolve_probe
from protocol.probe_draft import dump_checkpoint_draft, load_checkpoint_draft
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
    assert probe.revision == 4
    assert probe.step("portrait").field_ids[:3] == (
        "name",
        "email",
        "participation_position",
    )


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
    probe = _probe()

    assert "Generate ephemeral synthetic test data" in source
    assert "evaluate_representation" in source
    assert "generated on this render · not persisted" in source
    assert "if test_mode:" in source
    assert [representation.id for representation in probe.representations] == [
        "participation_overview",
        "participant_portrait",
        "knowledge_exchange",
        "future_landscape",
    ]
    assert "Aucune représentation n’est définie pour cette Probe." in source
    assert "Les représentations sont définies, mais aucune donnée n’est encore disponible." in source
    assert "Representation placeholder" not in source

    trajectories = _synthetic_trajectories(probe, "montreal-test")
    assert trajectories
    assert [
        evaluate_representation(probe, representation, trajectories).representation_id
        for representation in probe.representations
    ] == [
        "participation_overview",
        "participant_portrait",
        "knowledge_exchange",
        "future_landscape",
    ]


def test_authored_step_and_field_copy_crosses_the_canonical_boundary() -> None:
    source = yaml.safe_load(_source_text())
    probe = _probe()

    assert len(source["step_copy"]) == len(probe.steps) == 18
    assert len(source["questions"]) == len(probe.questions) == 25
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


def test_participation_position_is_single_and_controls_organisation_fields() -> None:
    probe = _probe()
    position = probe.question("participation_position")
    assert position.input_type.value == "single_with_other"
    assert [option.value for option in position.options] == [
        "individual",
        "organisation",
        "data_organisation",
        "other",
    ]
    condition = probe.question("organisation_name").visible_if
    assert condition is not None
    assert condition.operator == "any"
    assert {
        (clause.field_id, clause.operator, clause.value)
        for clause in condition.clauses
    } == {
        ("participation_position", "equals", "organisation"),
        ("participation_position", "equals", "data_organisation"),
    }

    runtime = ProbeRuntime(
        probe,
        participant_id="participant-position",
        scope_id="montreal_communs_2026",
    )
    runtime.answer("participation_position", "organisation")
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


def test_functions_are_flat_families_while_topics_remain_grouped_expanders() -> None:
    source = (ROOT / "probe_ui.py").read_text(encoding="utf-8")
    probe = _probe()

    functions = probe.taxonomy("functions")
    assert functions.groups == ()
    assert [option.value for option in functions.options] == [
        "leadership",
        "research_teaching",
        "collections",
        "data_tech",
        "law_policy",
        "communication_publics",
        "partnerships_funding",
        "communities",
        "other",
    ]
    assert probe.taxonomy("commons_ai_topics").presentation["groups"] == "expanders"
    assert 'taxonomy_presentation.get("groups") == "expanders"' in source
    assert "st.expander(" in source
    assert "group_title" in source


def test_collaborator_revision_preserves_identity_and_companion_semantics() -> None:
    probe = _probe()
    source = _source_text()

    assert "email" in probe.authoring.profile_fields
    assert "email" not in probe.authoring.session_fields
    email = probe.question("email")
    assert email.prompt == "Mon adresse courriel"
    assert "clé" not in email.context.casefold()
    assert "retrouver mes réponses" in email.context

    functions = probe.question("functions")
    assert [(item.id, item.required) for item in functions.companions] == [
        ("function_title", False)
    ]
    frictions = probe.question("frictions")
    assert [(item.id, item.required) for item in frictions.companions] == [
        ("frictions_detail", False)
    ]
    assert functions.other.required is True
    assert frictions.other.required is True

    assert "présentation anonymisée des résultats" in source
    assert "seront détruites après 5 ans" in source
    assert "geneva_2027_source_verification" in source


def test_availability_keeps_stable_values_and_exposes_select_all_shortcut() -> None:
    availability = _probe().question("availability")
    assert [option.value for option in availability.options] == [
        "oct28_am_online",
        "oct28_pm_inrs",
        "oct29_am_inrs",
        "oct29_pm_inrs",
    ]
    assert [option.label for option in availability.options] == [
        "28 octobre, matin",
        "28 octobre, après-midi",
        "29 octobre, matin",
        "29 octobre, après-midi",
    ]
    shortcut = availability.shortcuts[0]
    assert (shortcut.id, shortcut.label, shortcut.select) == (
        "both_full_days",
        "Les deux journées",
        (
            "oct28_am_online",
            "oct28_pm_inrs",
            "oct29_am_inrs",
            "oct29_pm_inrs",
        ),
    )
    ui_source = (ROOT / "probe_ui.py").read_text(encoding="utf-8")
    assert "for shortcut in field.shortcuts" in ui_source
    assert "set(shortcut_values) <= set(" in ui_source


def test_information_steps_checkpoint_copy_and_truthful_done_are_rendered_generically() -> None:
    probe = _probe()
    ui_source = (ROOT / "probe_ui.py").read_text(encoding="utf-8")

    assert probe.step("future_intro").field_ids == ()
    assert probe.step("future_intro").title == "Genève 2027"
    assert probe.step("future_intro").cta == "Je me projette"
    assert "not step.field_ids" in ui_source
    assert "visited_information_steps" in ui_source
    assert (
        "Vous pouvez ci-dessous télécharger un fichier contenant vos réponses "
        in ui_source
    )
    assert 'probe_submission_receipt_{participation_id}' in ui_source
    assert "Les réponses ne sont pas présentées comme enregistrées" in ui_source
    assert 'font-size: clamp(2.35rem, 7vw, 5.5rem)' in ui_source


@pytest.mark.parametrize(
    "field_id,value",
    [
        ("knowledge_offer", ["governance_models"]),
        ("knowledge_need", ["apis_ai"]),
        ("inspiration", ["practice_method"]),
        ("future_outcome", ["coalition"]),
    ],
)
def test_substantive_questions_require_answer_or_explicit_skip(
    field_id: str, value: list[str]
) -> None:
    probe = _probe()
    field = probe.question(field_id)
    assert field.independently_answerable is True

    answered = ProbeRuntime(probe, participant_id="answered", scope_id="montreal")
    answered.answer(field_id, value)
    assert answered.resolution(field_id).state == ResolutionState.ANSWERED

    skipped = ProbeRuntime(probe, participant_id="skipped", scope_id="montreal")
    skipped.skip(field_id, reason_codes=["prefer_not"])
    assert skipped.resolution(field_id).state == ResolutionState.SKIPPED


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
        "participation_position": "organisation",
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

    assert [item["operation"] for item in diagnostics] == [
        "draft.session.save",
        "draft.hydrate",
    ]
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
    runtime.skip("dietary_preferences", reason_codes=["prefer_not"])
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
        "selected": ["person_collective", "other"],
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


def test_other_text_is_required_only_when_other_is_selected() -> None:
    probe = _probe()
    runtime = ProbeRuntime(probe, participant_id="participant", scope_id="montreal")

    runtime.answer("future_outcome", ["coalition"])
    with pytest.raises(ProbeRuntimeError, match="requires other text"):
        runtime.answer(
            "future_outcome",
            {"selected": ["other"], "other": {"value": ""}},
        )
    value = {
        "selected": ["coalition", "other"],
        "other": {"value": "Une institution durable"},
    }
    runtime.answer("future_outcome", value)
    assert {item.question_id: item.value for item in runtime.review()}[
        "future_outcome"
    ] == value


def test_max_select_rejects_the_exact_over_limit_state() -> None:
    runtime = ProbeRuntime(_probe(), participant_id="participant", scope_id="montreal")

    with pytest.raises(ProbeRuntimeError, match="allows at most 3 selections"):
        runtime.answer(
            "inspiration",
            [
                "person_collective",
                "practice_method",
                "tool_infrastructure",
                "project_experiment",
            ],
        )


def test_every_authored_skip_reason_uses_the_canonical_registry() -> None:
    probe = _probe()
    authored_codes = [option.value for option in probe.resolution.skip_reasons.options]

    for code in authored_codes:
        runtime = ProbeRuntime(probe, participant_id=f"participant-{code}", scope_id="montreal")
        runtime.skip(
            "dietary_preferences",
            reason_codes=[code],
            note="Mon motif" if code == "other" else "",
        )
        event = runtime.trajectory.events[-1]
        assert event.kind == EventKind.SKIPPED
        assert event.reason_codes == (code,)

    ui_source = (ROOT / "probe_ui.py").read_text(encoding="utf-8")
    assert "runtime.probe.resolution.skip_reasons.options" in ui_source
    assert "no_option_fits" not in ui_source


def test_consent_skip_ends_without_becoming_affirmative_consent() -> None:
    probe = _probe()
    consent = probe.question("participation_acknowledgement")
    assert consent.skippable is True
    assert consent.skip_action == "end"
    assert [option.value for option in consent.options] == [
        "accept",
        "decline",
        "read_not_understood",
        "not_read",
    ]
    assert {route.action for route in consent.routes} == {
        "end",
        "show_contact",
        "return_to_information",
    }
    runtime = ProbeRuntime(probe, participant_id="participant", scope_id="montreal")
    runtime.skip("participation_acknowledgement", reason_codes=["prefer_not"])
    resolution = runtime.resolution("participation_acknowledgement")
    assert resolution.state == ResolutionState.SKIPPED
    assert resolution.event is not None
    assert resolution.event.value is None


def test_preview_is_side_effect_free_and_equals_the_committed_payload() -> None:
    probe = _probe()

    class CaptureRepository(InMemoryRepository):
        def __init__(self) -> None:
            super().__init__()
            self.saved: list[dict] = []

        def save_probe_trajectory(self, trajectory: dict) -> dict:
            self.saved.append(trajectory)
            return super().save_probe_trajectory(trajectory)

    repository = CaptureRepository()
    store = ProbeRepositoryStore(
        repository,
        probe_id=probe.id,
        participant_id="participant",
        scope_id="montreal",
    )
    runtime = ProbeRuntime(
        probe,
        participant_id="participant",
        scope_id="montreal",
        participation_id="participation",
    )
    runtime.answer("name", "Ada")
    prepared = runtime.prepare_finalisation(idempotency_key="participation")
    preview = store.preview_payload(
        prepared,
        idempotency_key="participation",
    )

    assert repository.saved == []
    runtime.finalise(
        store,
        idempotency_key="participation",
        prepared=prepared,
    )
    assert repository.saved == [preview]


def test_authored_checkpoint_capabilities_drive_the_generic_surface() -> None:
    probe = _probe()
    for section in probe.sections:
        assert section.checkpoint_config.enabled is True
        assert section.checkpoint_config.review is True
        assert section.checkpoint_config.draft_save is True
        assert section.checkpoint_config.export_yaml is True

    source = (ROOT / "probe_ui.py").read_text(encoding="utf-8")
    event_source = (ROOT / "event_ui.py").read_text(encoding="utf-8")
    assert "section.checkpoint_config" in source
    assert "Enregistrer cette étape" in source
    assert "Enregistrer et télécharger" in source
    assert "on_click=save_checkpoint" in source
    assert "Étape enregistrée. Une copie YAML a été téléchargée sur votre appareil." in source
    assert "Modifications non enregistrées" in source
    assert "draft_repository=draft_repository" in event_source
    assert "draft_repository = repository if test_mode else _draft_repository(event.id)" in event_source


def test_checkpoint_retains_answer_skip_and_flag_without_becoming_submission() -> None:
    probe = _probe()
    repository = InMemoryRepository()
    store = ProbeRepositoryStore(
        repository,
        probe_id=probe.id,
        participant_id="participant",
        scope_id="montreal",
    )
    runtime = ProbeRuntime(
        probe,
        participant_id="participant",
        scope_id="montreal",
        participation_id="participation",
    )
    runtime.answer("availability", ["oct28_am_online"])
    runtime.skip("dietary_preferences", reason_codes=["prefer_not"])
    runtime.flag("availability", reason_codes=["useful"])

    runtime.reach_checkpoint("participation", store)
    saved = repository.get_probe_trajectory("participation")
    assert saved is not None
    assert saved["integrated"] is False
    assert not any(
        event["kind"] == "integrated" for event in saved["trajectory"]["events"]
    )
    restored = store.load("participation")
    assert restored == runtime.trajectory


def test_yaml_checkpoint_draft_round_trips_and_rejects_revision_drift() -> None:
    probe = _probe()
    runtime = ProbeRuntime(
        probe,
        participant_id="participant",
        scope_id="montreal",
        participation_id="participation",
    )
    runtime.answer("availability", ["oct28_am_online"])
    runtime.reach_checkpoint(
        "participation",
        ProbeRepositoryStore(
            InMemoryRepository(),
            probe_id=probe.id,
            participant_id="participant",
            scope_id="montreal",
        ),
    )
    exported = dump_checkpoint_draft(
        probe,
        runtime.trajectory,
        section_id="participation",
    )
    assert load_checkpoint_draft(exported, probe=probe) == runtime.trajectory
    exported_payload = yaml.safe_load(exported)
    assert "trajectory" not in exported_payload
    assert set(exported_payload) == {
        "schema",
        "probe",
        "participation",
        "checkpoint",
        "answers",
        "skips",
        "flags",
    }
    assert "token" not in exported.casefold()
    assert "notion" not in exported.casefold()

    payload = exported_payload
    payload["probe"]["revision"] = probe.revision - 1
    with pytest.raises(ValueError, match="explicit migration"):
        load_checkpoint_draft(payload, probe=probe)


def test_resaved_yaml_snapshot_keeps_the_latest_canonical_answer_state() -> None:
    probe = _probe()
    store = ProbeRepositoryStore(
        InMemoryRepository(),
        probe_id=probe.id,
        participant_id="participant",
        scope_id="montreal",
    )
    runtime = ProbeRuntime(
        probe,
        participant_id="participant",
        scope_id="montreal",
        participation_id="participation",
    )
    runtime.answer("availability", ["oct28_am_online"])
    runtime.reach_checkpoint("participation", store)
    runtime.answer("availability", ["oct29_pm_inrs"])
    runtime.reach_checkpoint("participation", store)

    restored = load_checkpoint_draft(
        dump_checkpoint_draft(
            probe,
            runtime.trajectory,
            section_id="participation",
        ),
        probe=probe,
    )
    hydrated = ProbeRuntime.hydrate(
        probe,
        restored,
        participant_id="participant",
        scope_id="montreal",
    )
    assert {item.question_id: item.value for item in hydrated.review()}[
        "availability"
    ] == ["oct29_pm_inrs"]


def test_checkpoint_and_sync_are_independent_runtime_operations() -> None:
    probe = _probe()
    diagnostics: list[dict] = []
    store = ProbeRepositoryStore(
        InMemoryRepository(),
        probe_id=probe.id,
        participant_id="participant",
        scope_id="montreal",
        diagnostic_sink=diagnostics.append,
    )
    runtime = ProbeRuntime(
        probe,
        participant_id="participant",
        scope_id="montreal",
        participation_id="participation",
    )
    runtime.reach_checkpoint("exchange", store)
    assert [event.kind for event in runtime.trajectory.events] == [EventKind.CHECKPOINT]
    runtime.reach_sync_point("exchange", store)
    assert [event.kind for event in runtime.trajectory.events] == [
        EventKind.CHECKPOINT,
        EventKind.SYNC_POINT_REACHED,
    ]
    assert [item["operation"] for item in diagnostics] == [
        "draft.session.save",
        "sync.arrival",
    ]


def test_debug_palette_is_copyable_and_has_aa_code_contrast() -> None:
    source = (ROOT / "probe_ui.py").read_text(encoding="utf-8")

    def luminance(hex_colour: str) -> float:
        channels = [int(hex_colour[index : index + 2], 16) / 255 for index in (1, 3, 5)]
        linear = [
            value / 12.92 if value <= 0.04045 else ((value + 0.055) / 1.055) ** 2.4
            for value in channels
        ]
        return 0.2126 * linear[0] + 0.7152 * linear[1] + 0.0722 * linear[2]

    foreground = luminance("#f7fff9")
    background = luminance("#081d18")
    contrast = (max(foreground, background) + 0.05) / (
        min(foreground, background) + 0.05
    )
    assert contrast >= 4.5
    assert "Developer · Copy debug state" in source
    assert 'language="json"' in source
    assert '"checkpointed.draft"' in source
    assert '"committed.submission"' in source
    assert '"notion_api_requests_so_far"' in source
    assert '"supposed production-equivalent"' in source
    assert '"estimated real"' in source
    assert "state: saved" not in source
    for operation in (
        "draft.session.save",
        "draft.yaml.export",
        "draft.hydrate",
        "submission.preview",
        "submission.commit",
    ):
        assert operation in source or operation in (
            ROOT / "protocol" / "probe_store.py"
        ).read_text(encoding="utf-8")
