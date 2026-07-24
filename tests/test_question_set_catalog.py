from pathlib import Path

from protocol import load_question_set, load_question_set_catalog


SPEC_DIRECTORY = Path(__file__).parent.parent / "protocol" / "specs"
HOST_VIEW = Path(__file__).parent.parent / "views" / "commons_host.py"


def test_catalog_discovers_questionnaire_bundles_in_authored_order() -> None:
    catalog = load_question_set_catalog(SPEC_DIRECTORY)

    assert [bundle.title for bundle in catalog.bundles] == [
        "Identity",
        "Capacity",
        "Strategy",
    ]
    assert [bundle.question_count for bundle in catalog.bundles] == [4, 7, 7]
    assert "commons_smoke_v1.yaml" not in {
        bundle.source_path.name for bundle in catalog.bundles
    }
    assert catalog.discovery_errors == ()
    assert catalog.duplicate_question_ids == ()


def test_resolved_bundle_metadata_and_statistics_come_from_yaml() -> None:
    identity, capacity, strategy = load_question_set_catalog(SPEC_DIRECTORY).bundles

    assert identity.campaign_slug == "questioning_commons"
    assert identity.event_slug == "commons_inquiry"
    assert identity.question_set_id == "identity_v1"
    assert identity.schema_id == "questionnaire_v1"
    assert identity.version == "v1"
    assert identity.summary == "Who is here?"
    assert identity.required_count == 0
    assert identity.optional_count == 4
    assert identity.multiple_choice_count == 3
    assert identity.open_text_count == 0

    assert capacity.multiple_choice_count == 3
    assert capacity.open_text_count == 3
    assert strategy.multiple_choice_count == 4
    assert strategy.open_text_count == 1

    assert all(bundle.validation.is_valid for bundle in (identity, capacity, strategy))
    assert all(not bundle.validation.warnings for bundle in (identity, capacity, strategy))


def test_strategy_flow_is_declared_in_yaml_and_classifies_nodes() -> None:
    strategy = load_question_set(SPEC_DIRECTORY / "strategy_v1.yaml")

    assert strategy.flow == (
        "Scenario",
        "Strategic priority",
        "Actors to mobilise",
        "Capacities to activate",
        "First action",
        "Explain your reasoning",
        "Review before integration",
    )
    assert strategy.count_nodes("scenario") == 1
    assert strategy.count_nodes("decision") == 3
    assert strategy.count_nodes("action") == 1
    assert strategy.count_nodes("review") == 1


def test_new_questionnaire_yaml_is_discovered_without_a_registry_edit(
    tmp_path: Path,
) -> None:
    source = tmp_path / "retrospective_v1.yaml"
    source.write_text(
        """
id: retrospective
title: Retrospective
summary: What should change next?
metadata:
  campaign_slug: questioning_commons
  event_slug: commons_inquiry
  session_code: commons_pilot_2026
  question_set_id: retrospective_v1
  schema_id: questionnaire_v1
  version: v1
  order: 40
questions:
  - id: R1
    field: reflection
    type: textarea
    group: Reflection
    required: false
    title: What should we keep?
""".strip(),
        encoding="utf-8",
    )

    catalog = load_question_set_catalog(tmp_path)

    assert [bundle.title for bundle in catalog.bundles] == ["Retrospective"]
    assert catalog.bundles[0].questions[0].field_id == "reflection"
    assert catalog.bundles[0].validation.is_valid


def test_validation_reports_unknown_types_duplicate_ids_and_missing_fields(
    tmp_path: Path,
) -> None:
    source = tmp_path / "broken.yaml"
    source.write_text(
        """
id: broken
title: Broken
metadata:
  campaign_slug: questioning_commons
questions:
  - id: Q1
    type: mystery_widget
  - id: Q1
    type: textarea
""".strip(),
        encoding="utf-8",
    )

    bundle = load_question_set(source)

    assert not bundle.validation.is_valid
    assert bundle.validation.duplicate_ids == ("Q1",)
    assert bundle.validation.unknown_field_types == ("mystery_widget",)
    assert "metadata.schema_id" in bundle.validation.missing_fields
    assert "Q1: field id was derived from the YAML id" in bundle.validation.warnings


def test_host_is_a_generic_question_set_console() -> None:
    source = HOST_VIEW.read_text(encoding="utf-8")

    assert "def render_question_set(bundle: QuestionSetBundle)" in source
    assert "load_question_set_catalog()" in source
    assert "[bundle.title for bundle in catalog.bundles] + [\"Diagnostics\"]" in source
    assert "repository.list_" not in source
    assert "load_protocol" not in source
    assert "Strategic profiles" not in source
    assert "Question feedback" not in source
    assert "Coordination" not in source
    assert "Pilot content" not in source
    assert "Smoking gun scenario" not in source
    assert "Current smoke simulation" not in source
