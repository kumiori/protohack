import json
from pathlib import Path

from protocol import build_question_set_submission, load_question_set
from storage.memory import InMemoryRepository


ROOT = Path(__file__).parent.parent
CAPACITY_PATH = ROOT / "protocol" / "specs" / "capacity_v1.yaml"
STRATEGY_PATH = ROOT / "protocol" / "specs" / "strategy_v1.yaml"
MOSAIC_PATH = ROOT / "protocol" / "specs" / "mosaic.yaml"
APP_ENTRY = ROOT / "app.py"
COMMONS_VIEW = ROOT / "views" / "commons.py"
CAPACITY_VIEW = ROOT / "views" / "capacity.py"
STRATEGY_VIEW = ROOT / "views" / "strategy.py"
MOSAIC_VIEW = ROOT / "views" / "mosaic.py"
TRACK_UI = ROOT / "track_ui.py"
PARTICIPANT = "00000000-0000-4000-8000-000000000001"


def test_capacity_submission_uses_yaml_ids() -> None:
    bundle = load_question_set(CAPACITY_PATH)
    answers = {
        "network_utility": ["Find collaborators", "Access data"],
        "relevant_domains": ["Research"],
        "current_needs": "A shared dataset.",
        "time_horizon": "Next month",
        "current_contribution": "Evaluation methods.",
        "network_improvement": "A visible project index.",
    }

    submission = build_question_set_submission(
        bundle=bundle,
        participant_uuid=PARTICIPANT,
        answers=answers,
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
    assert "coordination_contact" not in serialized


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
    mosaic_source = MOSAIC_VIEW.read_text(encoding="utf-8")

    assert '"views/commons.py"' in app_source
    assert '"identity_v1.yaml"' in commons_source
    assert '"views/capacity.py"' in commons_source
    assert "test_smokegun.py" not in commons_source
    assert '"views/capacity.py"' in app_source
    assert 'url_path="capacity"' in app_source
    assert '"views/strategy.py"' in app_source
    assert 'url_path="strategy"' in app_source
    assert '"capacity_v1.yaml"' in capacity_source
    assert "coordination_contact" not in capacity_source
    assert '"strategy_v1.yaml"' in strategy_source
    assert '"question_answers"' in strategy_source
    assert '"views/mosaic.py"' in app_source
    assert 'url_path="mosaic"' in app_source
    assert '"mosaic.yaml"' in mosaic_source
    assert "render_question_track(" in mosaic_source
    assert "record_scoped_answer=record_mosaic_contact_answer" in mosaic_source
    assert "integration=True" in mosaic_source
    assert 'submission["record_type"] = "mosaic_responses"' in mosaic_source
    assert '"record_type": "mosaic_contacts"' in mosaic_source


def test_mosaic_submission_separates_contact_and_keeps_canonical_metadata() -> None:
    bundle = load_question_set(MOSAIC_PATH)
    submission = build_question_set_submission(
        bundle=bundle,
        participant_uuid=PARTICIPANT,
        answers={
            "mosaic_name": {"stored_separately": True},
            "mosaic_city": "Paris",
            "mosaic_contribution_areas": ["research"],
            "mosaic_communication_consent": "yes",
            "mosaic_email": {"stored_separately": True},
        },
        submitted_at="2026-07-25T10:00:00+00:00",
    )

    by_field = {
        response["field_id"]: response
        for response in submission["responses"]
    }
    assert "mosaic_name" not in by_field
    assert "mosaic_email" not in by_field
    assert by_field["mosaic_city"]["canonical_field"] == "geography.city"
    assert (
        by_field["mosaic_contribution_areas"]["canonical_field"]
        == "capacity.offer"
    )
    assert (
        by_field["mosaic_communication_consent"]["canonical_field"]
        == "consent.coordination"
    )
    assert "participant@example.org" not in json.dumps(submission)


def test_tracks_use_the_forward_only_platform_controls() -> None:
    source = TRACK_UI.read_text(encoding="utf-8")

    assert "st.columns([1.6, 0.5, 0.4])" in source
    assert "continue_column, flag_column, skip_column" in source
    assert "_render_flag_control(" in source
    assert "_render_skip_dialog(" in source
    assert "Skip and continue" in source
    assert '"Back"' not in source
    assert "review_back" not in source
    assert "repository.record_question_event(event)" in source
    assert 'status = "answered_and_flagged" if existing_flag else "answered"' in source
    assert 'key=f"question_card_{bundle.question_set_id}_{question.id}"' in source
    assert '[class*="st-key-question_card_"]' in source
    assert source.index("with st.container(") < source.index("answer = _render_question_input(")
    assert "border:2px solid var(--ink)" in source
    assert "box-shadow:9px 9px 0 var(--ink)" in source
    assert '[class*="st-key-begin_"] button' in source
    assert 'if question.input_type != "scenario":' in source


def test_strategy_ends_in_the_access_key_integration_dialogue() -> None:
    source = TRACK_UI.read_text(encoding="utf-8")
    strategy_source = STRATEGY_VIEW.read_text(encoding="utf-8")

    assert '@st.dialog(dialog_title, width="large")' in source
    assert "Take a screenshot of this screen." in source
    assert "recognise or retrieve your contribution later" in source
    assert "View the Commons Map" in source
    assert '"Finish"' in source
    assert "existing_result=existing_submission or existing_profile" in strategy_source
    assert "integration=True" in strategy_source


def test_mosaic_polish_is_yaml_driven_and_animated() -> None:
    source = TRACK_UI.read_text(encoding="utf-8")
    bundle = load_question_set(MOSAIC_PATH)

    assert bundle.landing_title == "MOSAIC"
    assert "Coordination begins with visibility." in bundle.landing_body
    assert bundle.landing_note == (
        "Many questions allow multiple selections. Choose everything that applies."
    )
    assert bundle.begin_label == "Join the initiative"
    assert bundle.completion_title == "Contribution integrated into Mosaic"
    assert "added to the Mosaic network" in bundle.completion_body
    assert bundle.completion_map_label == "View Mosaic Map"
    assert bundle.completion_animation == "network_balloons"
    assert "and question.enabled" in source
    assert 'state["stage"] = "integrating"' in source
    assert 'state.get("stage") not in {"integrating", "integration"}' in source
    assert "Your contribution is entering Mosaic." in source
    assert "st.balloons()" in source
    assert "@st.fragment(run_every=0.4)" in source
    assert "time.monotonic() - started_at >= 2.8" in source
    assert "_render_question_link(question)" in source
    assert 'os.getenv(question.link_env, "").strip()' in source
    assert '[class*="st-key-question_card_mosaic_v1"]' in source


def test_conditional_review_uses_only_the_resolved_question_branch() -> None:
    source = TRACK_UI.read_text(encoding="utf-8")

    assert "and question.is_visible(resolved_answers)" in source
    assert "_review_rows(\n            questions=questions," in source
