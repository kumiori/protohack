from __future__ import annotations

from pathlib import Path

import pytest
from probe_engine import InputType, ProbeRuntime, ResolutionState

from protocol.probe_registry import resolve_probe
from protocol.probe_store import ProbeRepositoryStore
from storage.memory import InMemoryRepository


ROOT = Path(__file__).parent.parent


def _probe():
    return resolve_probe(event_slug="commons-montreal", variant="short").load()


def test_rendered_action_hierarchy_is_explicit() -> None:
    source = (ROOT / "probe_ui.py").read_text(encoding="utf-8")
    assert '"Passer"' in source
    assert 'type="secondary"' in source
    assert '[data-testid="stBaseButton-secondary"]' in source
    assert "background: #f8f7f2 !important" in source
    assert '[data-testid="stPopover"] button' in source
    assert '"Enregistrer et télécharger"' in source
    assert 'type="primary"' in source


def test_welcome_uses_only_the_canonical_editorial_copy() -> None:
    probe = _probe()
    welcome = probe.step("welcome")
    source = (ROOT / "probe_ui.py").read_text(encoding="utf-8")
    assert welcome.title == "Communs de données et IA"
    assert "Pour démarrer le Forum" in welcome.body
    assert "Mieux nous connaître." in welcome.body
    assert "Merci pour votre contribution à cette démarche collective." in welcome.body
    assert welcome.cta == "Commencer"
    assert 'welcome = probe.step("welcome")' in source
    assert "event.participant_intro" not in source


def test_portrait_email_is_rendered_and_canonically_identity_scoped() -> None:
    probe = _probe()
    email = probe.question("email")
    assert probe.step("portrait").field_ids[:2] == ("name", "email")
    assert email.input_type == InputType.EMAIL
    assert "email" in probe.authoring.profile_fields
    assert "email" not in probe.authoring.session_fields

    runtime = ProbeRuntime(probe, participant_id="email", scope_id="montreal")
    runtime.answer("email", "personne@example.org")
    with pytest.raises(Exception, match="email"):
        runtime.answer("email", "pas une adresse")

    runtime.answer("knowledge_offer", ["governance_models"])
    payload = ProbeRepositoryStore(
        InMemoryRepository(),
        probe=probe,
        probe_id=probe.id,
        participant_id="email",
        scope_id="montreal",
    ).submission_payload(runtime.trajectory, integrated=True)
    assert payload["player"]["email"] == "personne@example.org"
    assert "identity" not in payload
    assert "email" not in payload["payload"]
    assert "email" not in payload["responses"]
    assert payload["responses"]["knowledge_offer"] == ["governance_models"]


def test_position_and_availability_match_the_authoritative_options() -> None:
    probe = _probe()
    position = probe.question("participation_position")
    assert position.input_type == InputType.SINGLE_WITH_OTHER
    assert [option.label for option in position.options] == [
        "À titre individuel",
        "Au nom d’une organisation impliquée dans la production, la gestion ou la gouvernance de données culturelles",
        "Autre",
    ]
    assert "organisation GLAM" not in (ROOT / "question_sets/montreal_communs_2026/short.yaml").read_text(encoding="utf-8")

    availability = probe.question("availability")
    labels = [option.label for option in availability.options]
    assert labels == [
        "28 octobre, matin",
        "28 octobre, après-midi",
        "29 octobre, matin",
        "29 octobre, après-midi",
    ]
    assert not any("en ligne" in label or "présentiel" in label for label in labels)


def test_location_renderer_has_no_redundant_modify_action() -> None:
    source = (ROOT / "protocol/location_lookup.py").read_text(encoding="utf-8")
    assert "Modifier ma recherche" not in source
    assert "lookup_query_key" in source


@pytest.mark.parametrize(
    "field_id,value",
    [
        ("knowledge_offer", ["governance_models"]),
        ("knowledge_need", ["apis_ai"]),
        ("frictions", ["time"]),
        ("inspiration", ["practice_method"]),
        ("future_outcome", ["coalition"]),
        ("future_effects", ["change_practice"]),
        ("scenario_position", ["researcher"]),
    ],
)
def test_substantive_resolution_is_answer_or_valid_skip(field_id: str, value: list[str]) -> None:
    probe = _probe()
    untouched = ProbeRuntime(probe, participant_id="untouched", scope_id="montreal")
    assert untouched.resolution(field_id).state == ResolutionState.UNRESOLVED

    answered = ProbeRuntime(probe, participant_id="answered", scope_id="montreal")
    answered.answer(field_id, value)
    assert answered.resolution(field_id).state == ResolutionState.ANSWERED

    skipped = ProbeRuntime(probe, participant_id="skipped", scope_id="montreal")
    skipped.skip(field_id, reason_codes=["prefer_not"])
    assert skipped.resolution(field_id).state == ResolutionState.SKIPPED


def test_optional_companions_and_required_other_remain_distinct() -> None:
    probe = _probe()
    runtime = ProbeRuntime(probe, participant_id="companions", scope_id="montreal")
    runtime.answer("frictions", {"selected": ["time"], "companions": {}})
    assert runtime.resolution("frictions").state == ResolutionState.ANSWERED
    with pytest.raises(Exception, match="other text"):
        runtime.answer(
            "frictions",
            {"selected": ["other"], "other": {"value": ""}, "companions": {}},
        )
    assert probe.question("frictions").companions[0].prompt == "Je précise, si je le souhaite"
    assert probe.question("frictions").companions[0].required is False


def test_geneva_is_a_real_information_step_before_future_questions() -> None:
    probe = _probe()
    geneva = probe.step("future_intro")
    assert geneva.field_ids == ()
    assert geneva.title == "Genève 2027"
    assert geneva.cta == "Je me projette"
    assert geneva.id == probe.sections[-1].step_ids[0]
    assert "Objectif : identifier des pistes d’action" in geneva.body
    assert "Nous nous projetons au lendemain" in geneva.body


def test_checkpoint_is_optional_and_uses_stable_status_grid() -> None:
    source = (ROOT / "probe_ui.py").read_text(encoding="utf-8")
    assert "disabled=not checkpointed" not in source
    assert "probe-checkpoint-grid" in source
    assert "──────────────" not in source
    assert "Un fichier contenant vos réponses jusqu’à cette étape a été téléchargé." in source
    assert "YAML" not in source[source.index("def _render_checkpoint_surface"):source.index("def render_registered_probe")]
    assert '"Relire cette section",\n        type="secondary"' in source


def test_portrait_checkpoint_can_acquire_saved_state() -> None:
    probe = _probe()
    repository = InMemoryRepository()
    store = ProbeRepositoryStore(
        repository,
        probe=probe,
        probe_id=probe.id,
        participant_id="portrait",
        scope_id="montreal",
    )
    runtime = ProbeRuntime(
        probe,
        participant_id="portrait",
        scope_id="montreal",
        participation_id="portrait-checkpoint",
    )
    runtime.reach_checkpoint("portrait", store)

    assert any(
        event.kind.value == "checkpoint"
        and event.metadata.get("section_id") == "portrait"
        for event in runtime.trajectory.events
    )
    persisted = repository.get_probe_trajectory("portrait-checkpoint")
    assert persisted is not None
    assert persisted["integrated"] is False
