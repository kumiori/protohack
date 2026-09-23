from copy import deepcopy
import json
from pathlib import Path

import storage.notion as notion_module
from scripts.bootstrap_protohack_notion import DATABASES, RELATIONS, SCHEMA_VERSION
from protocol.shared_goals import build_goal_trajectory
from protocol.timeline_plan import build_plan_payload
from protocol.trajectory_schema import build_trajectory_document
from storage.notion import NotionRepository


PARTICIPANT = "00000000-0000-4000-8000-000000000001"


def _trajectory_document() -> dict[str, object]:
    plan = build_plan_payload(
        title="X path",
        description="",
        initial_condition="We have an idea.",
        goal_statement="The panel has taken place.",
        goal_conditions="",
        landing_mode="Open",
        temporal_mode="Qualitative",
        created_at="2026-08-10T12:00:00+03:00",
    )
    return build_trajectory_document(plan=plan, primitives=[], uncertainty=[])


class FakeDataSources:
    def __init__(self, owner: "FakeClient") -> None:
        self.owner = owner

    def query(self, **arguments):
        source_id = arguments["data_source_id"]
        if source_id.endswith("goal-trajectories"):
            return {"results": deepcopy(self.owner.goal_trajectories), "has_more": False}
        if source_id.endswith("goals"):
            return {"results": deepcopy(self.owner.goals), "has_more": False}
        if source_id.endswith("responses"):
            return {"results": deepcopy(self.owner.responses), "has_more": False}
        if source_id.endswith("events"):
            return {"results": deepcopy(self.owner.events), "has_more": False}
        return {"results": deepcopy(self.owner.players), "has_more": False}


class FakePages:
    def __init__(self, owner: "FakeClient") -> None:
        self.owner = owner

    def create(self, *, parent, properties):
        page = {"id": f"page-{len(self.owner.created) + 1}", "properties": properties}
        self.owner.created.append(deepcopy(page))
        return page

    def update(self, *, page_id, **changes):
        self.owner.updated.append({"page_id": page_id, **deepcopy(changes)})
        return {"id": page_id, "properties": changes.get("properties", {})}


class FakeClient:
    instance: "FakeClient | None" = None

    def __init__(self, **_arguments) -> None:
        FakeClient.instance = self
        self.responses: list[dict] = []
        self.players: list[dict] = []
        self.events: list[dict] = []
        self.goals: list[dict] = []
        self.goal_trajectories: list[dict] = []
        self.created: list[dict] = []
        self.updated: list[dict] = []
        self.data_sources = FakeDataSources(self)
        self.pages = FakePages(self)


def _manifest(tmp_path: Path) -> Path:
    path = tmp_path / "manifest.json"
    path.write_text(
        """{
          "seed_session": {"page_id": "session-page"},
          "databases": {
            "responses": {"data_source_id": "source-responses"},
            "players": {"data_source_id": "source-players"},
            "events": {"data_source_id": "source-events"}
            ,"goals": {"data_source_id": "source-goals"}
            ,"goal_trajectories": {"data_source_id": "source-goal-trajectories"}
          }
        }""",
        encoding="utf-8",
    )
    return path


def test_bootstrap_v2_has_no_strategy_to_contact_relation() -> None:
    assert SCHEMA_VERSION == "protohack-notion-v4-probe-test-submissions"
    assert "player" not in RELATIONS["responses"]
    assert "participant_uuid" in DATABASES["responses"]["properties"]
    assert "rationale" in DATABASES["responses"]["properties"]
    assert "participant_uuid" in DATABASES["players"]["properties"]
    assert "coordination_status" in DATABASES["players"]["properties"]
    assert "goals" in DATABASES
    assert "goal_trajectories" in DATABASES
    assert RELATIONS["goal_trajectories"]["goal"] == ("goals", "contributions")
    assert "trajectory_payload" in DATABASES["goal_trajectories"]["properties"]
    assert DATABASES["test_submissions"]["title"] == "protohack_ProbeTestSubmissions"
    assert "payload" in DATABASES["test_submissions"]["properties"]
    assert "access_code_verifier" in DATABASES["test_submissions"]["properties"]


def test_shared_trajectory_write_keeps_canonical_payload_in_one_field(
    monkeypatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(notion_module, "Client", FakeClient)
    repository = NotionRepository(token="test", manifest_path=_manifest(tmp_path))
    client = FakeClient.instance
    assert client is not None
    client.goals = [{
        "id": "goal-page",
        "properties": {
            "Name": {"title": [{"plain_text": "AI Summit 2027"}]},
            "goal_id": {"rich_text": [{"plain_text": "summit-2027"}]},
            "objective": {"rich_text": [{"plain_text": "Organise the panel."}]},
            "created_by_agent_id": {"rich_text": [{"plain_text": "andres"}]},
            "created_at": {"date": {"start": "2026-08-10T12:00:00+03:00"}},
            "status": {"select": {"name": "open"}},
            "visibility": {"select": {"name": "public"}},
        },
    }]
    shared = build_goal_trajectory(
        _trajectory_document(),
        goal_id="summit-2027",
        agent_id="x",
        agent_display_name="X",
        created_at="2026-08-10T13:00:00+03:00",
    )

    repository.record_goal_trajectory(shared)

    created = client.created[-1]["properties"]
    serialized = "".join(
        item["text"]["content"]
        for item in created["trajectory_payload"]["rich_text"]
    )
    payload = json.loads(serialized)
    assert payload["schema_version"] == "trajectory-plan/v2"
    assert "goal_id" not in payload["plan"]
    assert created["goal"] == {"relation": [{"id": "goal-page"}]}
    assert created["revision"] == {"number": 1}


def test_strategy_write_never_contains_player_relation(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(notion_module, "Client", FakeClient)
    repository = NotionRepository(token="test", manifest_path=_manifest(tmp_path))
    repository.integrate_strategic_profile(
        {
            "participant_uuid": PARTICIPANT,
            "participant_alias": "P-ABC123",
            "session_code": "commons_pilot_2026",
            "protocol_id": "commons_smoke",
            "protocol_version": "0.1.0-draft",
            "scenario_id": "SCN_001",
            "decision_id": "DEC_001",
            "action_id": "ACT_001",
            "action_label": "Make the system visible",
            "rationale": "Visibility comes first.",
            "semantic_tags": ["visibility"],
            "capacities": ["synthesis"],
            "resource_types": ["Knowledge"],
            "tagger_version": "authored-actions-v1",
            "privacy_version": "strategy-contact-separation-v1",
            "integration_status": "integrated",
            "revision": 1,
            "integrated_at": "2026-07-22T12:00:00+00:00",
        }
    )

    properties = FakeClient.instance.created[0]["properties"]  # type: ignore[union-attr]
    assert "participant_uuid" in properties
    assert "player" not in properties
    assert "email" not in properties


def test_contact_deletion_trashes_only_player_page(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(notion_module, "Client", FakeClient)
    repository = NotionRepository(token="test", manifest_path=_manifest(tmp_path))
    client = FakeClient.instance
    assert client is not None
    client.players = [
        {
            "id": "contact-page",
            "properties": {
                "participant_uuid": {"rich_text": [{"plain_text": PARTICIPANT}]}
            },
        }
    ]

    assert repository.delete_contact_data(PARTICIPANT) is True
    assert client.updated == [{"page_id": "contact-page", "in_trash": True}]


def test_feedback_write_uses_events_without_player_relation(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(notion_module, "Client", FakeClient)
    repository = NotionRepository(token="test", manifest_path=_manifest(tmp_path))
    repository.record_question_feedback(
        {
            "event_type": "question_skipped",
            "participant_uuid": PARTICIPANT,
            "participant_alias": "P-ABC123",
            "session_code": "commons_pilot_2026",
            "protocol_id": "commons_smoke",
            "protocol_version": "0.2.0-draft",
            "question_id": "RAT_001",
            "question_prompt": "Why did you choose this?",
            "flags": ["unclear"],
            "flag_labels": ["Unclear"],
            "note": "I cannot answer yet.",
            "created_at": "2026-07-22T12:00:00+00:00",
        }
    )

    properties = FakeClient.instance.created[0]["properties"]  # type: ignore[union-attr]
    assert properties["event_type"] == {"select": {"name": "question_skipped"}}
    assert "player" not in properties
    assert "email" not in properties


def test_question_event_write_uses_immutable_event_metadata(
    monkeypatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(notion_module, "Client", FakeClient)
    repository = NotionRepository(token="test", manifest_path=_manifest(tmp_path))
    repository.record_question_event(
        {
            "event_id": "event-1",
            "event_type": "question_event",
            "status": "skipped",
            "participant_id": PARTICIPANT,
            "participant_uuid": PARTICIPANT,
            "participant_alias": "P-ABC123",
            "session_code": "commons_pilot_2026",
            "track_id": "capacity_v1",
            "question_id": "C3",
            "question_prompt": "What do you currently need?",
            "reason_code": "prefer_not_to_answer",
            "reason_text": "",
            "timestamp": "2026-07-24T12:00:00+00:00",
            "created_at": "2026-07-24T12:00:00+00:00",
        }
    )

    properties = FakeClient.instance.created[0]["properties"]  # type: ignore[union-attr]
    assert properties["event_type"] == {"select": {"name": "question_event"}}
    assert properties["status"] == {"select": {"name": "skipped"}}
    assert properties["page"]["rich_text"][0]["text"]["content"] == "capacity_v1"
    serialized = "".join(
        item["text"]["content"] for item in properties["metadata_json"]["rich_text"]
    )
    assert json.loads(serialized)["reason_code"] == "prefer_not_to_answer"
    assert "answer" not in json.loads(serialized)


def test_question_set_submission_writes_anonymous_bundle_json(
    monkeypatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(notion_module, "Client", FakeClient)
    repository = NotionRepository(token="test", manifest_path=_manifest(tmp_path))
    repository.record_question_set_submission(
        {
            "submission_id": "submission-1",
            "participant_uuid": PARTICIPANT,
            "participant_alias": "P-ABC123",
            "campaign_slug": "questioning_commons",
            "event_slug": "commons_inquiry",
            "session_code": "commons_pilot_2026",
            "question_set_id": "capacity_v1",
            "schema_id": "questionnaire_v1",
            "version": "v1",
            "responses": [
                {
                    "question_id": "C3",
                    "field_id": "current_needs",
                    "question_type": "textarea",
                    "value": "A shared dataset.",
                }
            ],
            "submitted_at": "2026-07-24T12:00:00+00:00",
        }
    )

    properties = FakeClient.instance.created[0]["properties"]  # type: ignore[union-attr]
    assert properties["text_id"]["rich_text"][0]["text"]["content"] == "capacity_v1"
    assert properties["question_id"]["rich_text"][0]["text"]["content"] == "capacity_v1"
    serialized = "".join(
        item["text"]["content"] for item in properties["value_json"]["rich_text"]
    )
    assert json.loads(serialized)["responses"][0]["question_id"] == "C3"
    assert "email" not in serialized
    assert "player" not in properties


def test_mosaic_contact_uses_players_not_analytical_responses(
    monkeypatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(notion_module, "Client", FakeClient)
    repository = NotionRepository(token="test", manifest_path=_manifest(tmp_path))
    repository.record_question_set_contact(
        {
            "record_type": "mosaic_contacts",
            "question_set_id": "mosaic_v1",
            "participant_uuid": PARTICIPANT,
            "access_key": PARTICIPANT,
            "name": "Participant",
            "email": "participant@example.org",
            "communication_consent": True,
            "updated_at": "2026-07-25T10:00:00+00:00",
        }
    )

    client = FakeClient.instance
    assert client is not None
    assert len(client.created) == 1
    properties = client.created[0]["properties"]
    assert properties["email"] == {"email": "participant@example.org"}
    assert properties["coordination_consent_version"]["rich_text"][0]["text"][
        "content"
    ] == "mosaic_v1"
    assert properties["coordination_opt_in"] == {"checkbox": True}
    assert client.responses == []
