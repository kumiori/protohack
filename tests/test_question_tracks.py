import json
from pathlib import Path

from protocol import build_question_set_submission, load_question_set
from storage.memory import InMemoryRepository


ROOT = Path(__file__).parent.parent
CAPACITY_PATH = ROOT / "protocol" / "specs" / "capacity_v1.yaml"
STRATEGY_PATH = ROOT / "protocol" / "specs" / "strategy_v1.yaml"
APP_ENTRY = ROOT / "app.py"
COMMONS_VIEW = ROOT / "views" / "commons.py"
CAPACITY_VIEW = ROOT / "views" / "capacity.py"
STRATEGY_VIEW = ROOT / "views" / "strategy.py"
TRACK_UI = ROOT / "track_ui.py"
PARTICIPANT = "00000000-0000-4000-8000-000000000001"


def test_capacity_submission_uses_yaml_ids_and_excludes_contact_scope() -> None:
    bundle = load_question_set(CAPACITY_PATH)
    answers = {
        "network_utility": ["Find collaborators", "Access data"],
        "relevant_domains": ["Research"],
        "current_needs": "A shared dataset.",
        "time_horizon": "Next month",
        "current_contribution": "Evaluation methods.",
        "network_improvement": "A visible project index.",
        "coordination_contact": {
            "Name or username": "Participant",
            "Email": "participant@example.org",
        },
    }

    submission = build_question_set_submission(
        bundle=bundle,
        participant_uuid=PARTICIPANT,
        answers=answers,
        excluded_field_ids={"coordination_contact"},
        submitted_at="2026-07-24T12:00:00+00:00",
    )

    assert submission["question_set_id"] == "capacity_v1"
    assert submission["schema_id"] == "questionnaire_v1"
    assert submission["session_code"] == "commons_pilot_2026"
    assert [row["question_id"] for row in submission["responses"]] == [
        "C1",
        "C2",
        "C3",
        "C4",
        "C5",
        "C6",
    ]
    serialized = json.dumps(submission)
    assert "participant@example.org" not in serialized
    assert "Name or username" not in serialized


def test_capacity_submission_is_idempotent_in_preview_storage() -> None:
    bundle = load_question_set(CAPACITY_PATH)
    first = build_question_set_submission(
        bundle=bundle,
        participant_uuid=PARTICIPANT,
        answers={"current_needs": "Funding."},
        submitted_at="2026-07-24T12:00:00+00:00",
    )
    changed = build_question_set_submission(
        bundle=bundle,
        participant_uuid=PARTICIPANT,
        answers={"current_needs": "A later duplicate must not overwrite this."},
        submitted_at="2026-07-24T12:05:00+00:00",
    )
    repository = InMemoryRepository()

    assert repository.record_question_set_submission(first) == first
    assert repository.record_question_set_submission(changed) == first
    assert repository.list_question_set_submissions("capacity_v1") == [first]


def test_capacity_contact_is_kept_in_the_separate_contact_store() -> None:
    repository = InMemoryRepository()
    repository.record_coordination_interest(
        participant_uuid=PARTICIPANT,
        session_code="commons_pilot_2026",
        email="participant@example.org",
        consent_version="pilot-interest-v1",
        consented_at="2026-07-24T12:00:00+00:00",
        name="Participant",
    )

    record = repository.get_coordination_interest(PARTICIPANT)
    assert record is not None
    assert record["name"] == "Participant"
    assert record["email"] == "participant@example.org"
    assert repository.list_question_set_submissions("capacity_v1") == []


def test_strategy_track_resolves_only_declared_runtime_nodes() -> None:
    bundle = load_question_set(STRATEGY_PATH)
    by_id = {question.id: question for question in bundle.questions}

    assert by_id["S1"].runtime_source == "commons_smoke_v1.scenario"
    assert by_id["S5"].runtime_source == (
        "commons_smoke_v1.scenario.decision.actions"
    )
    assert by_id["S2"].options == ("Perceive", "Mobilise", "Decide", "Transform")
    assert by_id["S3"].required is True
    assert by_id["S4"].required is True
    assert by_id["S5"].required is True
    assert by_id["S6"].required is True


def test_capacity_and_strategy_are_additive_navigation_tracks() -> None:
    app_source = APP_ENTRY.read_text(encoding="utf-8")
    commons_source = COMMONS_VIEW.read_text(encoding="utf-8")
    capacity_source = CAPACITY_VIEW.read_text(encoding="utf-8")
    strategy_source = STRATEGY_VIEW.read_text(encoding="utf-8")

    assert '"views/commons.py"' in app_source
    assert '"identity_v1.yaml"' in commons_source
    assert '"views/capacity.py"' in commons_source
    assert "test_smokegun.py" not in commons_source
    assert '"views/capacity.py"' in app_source
    assert 'url_path="capacity"' in app_source
    assert '"views/strategy.py"' in app_source
    assert 'url_path="strategy"' in app_source
    assert '"capacity_v1.yaml"' in capacity_source
    assert "excluded_field_ids={\"coordination_contact\"}" in capacity_source
    assert '"strategy_v1.yaml"' in strategy_source
    assert '"question_answers"' in strategy_source


def test_track_actions_match_the_commons_participant_geometry() -> None:
    source = TRACK_UI.read_text(encoding="utf-8")

    assert "st.columns([1.6, 0.5, 0.4])" in source
    assert 'type="secondary"' in source
    assert "continue_column, back_column, skip_column" in source
    assert "border:2px solid var(--ink)" in source
    assert "box-shadow:9px 9px 0 var(--ink)" in source
    assert '[class*="st-key-begin_"] button' in source
    assert 'if question.input_type != "scenario":' in source
