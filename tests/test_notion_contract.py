from copy import deepcopy
import httpx
import json
from pathlib import Path

import pytest
import storage.notion as notion_module
from notion_client.errors import APIResponseError
from scripts.bootstrap_protohack_notion import DATABASES, RELATIONS, SCHEMA_VERSION
from protocol.shared_goals import build_goal_trajectory
from protocol.timeline_plan import build_plan_payload
from protocol.trajectory_schema import build_trajectory_document
from storage.notion import NotionRepository
from storage.notion import ProbeSubmissionCommitError
from storage.notion_debug import GenericNotionDebugRepository


PARTICIPANT = "00000000-0000-4000-8000-000000000001"


def test_notion_rich_text_chunks_respect_utf16_unit_limit() -> None:
    content = "a" * 1998 + "🌊🦊" + "b" * 12

    chunks = notion_module._text(content)

    assert "".join(item["text"]["content"] for item in chunks) == content
    assert all(
        len(item["text"]["content"].encode("utf-16-le")) // 2 <= 2000
        for item in chunks
    )


def test_debug_repository_health_normalises_inaccessible_data_source() -> None:
    class Users:
        @staticmethod
        def me():
            return {"name": "fuckthesystem"}

    class DataSources:
        calls = 0

        @classmethod
        def query(cls, **_arguments):
            cls.calls += 1
            raise APIResponseError(
                code="object_not_found",
                status=404,
                message="raw Notion message must not reach participants",
                headers=httpx.Headers(),
                raw_body_text="{}",
            )

    repository = object.__new__(GenericNotionDebugRepository)
    repository._sources = {"test_submissions": "5559d76a-d0b2-4c9b-8115-6c4ad1ee97f9"}
    repository._client = type("Client", (), {"users": Users(), "data_sources": DataSources()})()
    repository._health_result = None
    repository._health_checked_at = 0.0

    first = repository.health_check()
    second = repository.health_check()

    assert first == second
    assert first.available is False
    assert first.integration == "fuckthesystem"
    assert first.data_source_id == "5559d76a-d0b2-4c9b-8115-6c4ad1ee97f9"
    assert first.status == "inaccessible / not found"
    assert first.error_code == "object_not_found"
    assert DataSources.calls == 1


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
        source = str(parent.get("data_source_id") or "")
        if source.endswith("players"):
            self.owner.players.append(page)
        elif source.endswith("responses"):
            self.owner.responses.append(page)
        return page

    def update(self, *, page_id, **changes):
        self.owner.updated.append({"page_id": page_id, **deepcopy(changes)})
        for collection in (
            self.owner.players,
            self.owner.responses,
            self.owner.events,
            self.owner.goals,
            self.owner.goal_trajectories,
        ):
            for page in collection:
                if page["id"] == page_id:
                    page["properties"].update(deepcopy(changes.get("properties") or {}))
                    return page
        return {"id": page_id, "properties": changes.get("properties", {})}

    def retrieve(self, *, page_id):
        for collection in (
            self.owner.players,
            self.owner.responses,
            self.owner.events,
            self.owner.goals,
            self.owner.goal_trajectories,
        ):
            for page in collection:
                if page["id"] == page_id:
                    return deepcopy(page)
        raise KeyError(page_id)


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


def test_bootstrap_has_explicit_probe_player_relation_and_profile_fields() -> None:
    assert SCHEMA_VERSION == "protohack-notion-v7-player-credential"
    assert RELATIONS["responses"]["player"] == ("players", "responses")
    assert "participant_uuid" in DATABASES["responses"]["properties"]
    assert "rationale" in DATABASES["responses"]["properties"]
    assert "participant_uuid" in DATABASES["players"]["properties"]
    assert "coordination_status" in DATABASES["players"]["properties"]
    assert "participant_id" in DATABASES["players"]["properties"]
    assert "access_code_selector" in DATABASES["players"]["properties"]
    assert "access_code_selector_6" in DATABASES["players"]["properties"]
    assert "access_code_emoji" in DATABASES["players"]["properties"]
    assert "access_code_verifier" in DATABASES["players"]["properties"]
    assert "institution" in DATABASES["players"]["properties"]
    assert "base_location_place_id" in DATABASES["players"]["properties"]
    assert "goals" in DATABASES
    assert "goal_trajectories" in DATABASES
    assert RELATIONS["goal_trajectories"]["goal"] == ("goals", "contributions")
    assert "trajectory_payload" in DATABASES["goal_trajectories"]["properties"]
    assert DATABASES["test_submissions"]["title"] == "protohack_ProbeTestSubmissions"
    assert "payload" in DATABASES["test_submissions"]["properties"]
    assert "access_code_verifier" in DATABASES["test_submissions"]["properties"]
    assert "record_type" in DATABASES["responses"]["properties"]
    assert "environment" in DATABASES["responses"]["properties"]


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


def _probe_submission_envelope() -> dict:
    from protocol.probe_access import access_code_from_key

    credential = access_code_from_key("12345678-1234-5678-1234-567812345678")
    return {
        "record_type": "probe_submission",
        "schema": "probe-submission-envelope/v1",
        "created_at": "2026-09-24T12:00:00+00:00",
        "updated_at": "2026-09-24T12:01:00+00:00",
        "integrated_at": "2026-09-24T12:01:00+00:00",
        "environment": "production",
        "event_id": "montreal_communs_2026",
        "participation_id": "participation-1",
        "participant_id": PARTICIPANT,
        "probe_id": "montreal_communs_data_ai_short_2026",
        "probe_revision": 5,
        "submission_id": "submission-1",
        "state": "submitted",
        "revision": 1,
        "integrated": True,
        "trajectory": {
            "events": [
                {
                    "timestamp": "2026-09-24T12:00:30+00:00",
                    "question_id": "email",
                    "kind": "answered",
                    "value": "andres@example.org",
                },
                {
                    "timestamp": "2026-09-24T12:01:00+00:00",
                    "question_id": "participation_position",
                    "kind": "answered",
                    "value": "individual",
                },
            ]
        },
        "player": {
            "participant_id": PARTICIPANT,
            "name": "Andrés",
            "email": "andres@example.org",
            "institution": "CNRS",
            "base_location": {
                "display_label": "Paris, France",
                "place_id": "test:paris",
                "latitude": 48.8566,
                "longitude": 2.3522,
            },
            "profile_answers": {"functions": ["research"]},
            "answer_field_ids": ["email", "name", "base_location"],
            "trajectory_events": [
                {
                    "timestamp": "2026-09-24T12:00:30+00:00",
                    "question_id": "email",
                    "kind": "answered",
                    "value": "andres@example.org",
                }
            ],
            "credential": {
                "emoji": credential.emoji,
                "selector": credential.selector,
                "selector_6": credential.selector_6,
                "verifier": credential.verifier,
            },
        },
        "responses": {"participation_position": "individual"},
        "payload": {
            "schema": "probe-submission/v1",
            "answers": {"participation_position": "individual"},
            "trajectory": {"events": []},
        },
    }


def test_probe_commit_upserts_player_links_response_and_verifies_readback(
    monkeypatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(notion_module, "Client", FakeClient)
    repository = NotionRepository(token="test", manifest_path=_manifest(tmp_path))
    client = FakeClient.instance
    assert client is not None

    first = repository.commit_probe_submission(_probe_submission_envelope())
    second_envelope = _probe_submission_envelope()
    second_envelope["player"]["institution"] = "CNRS updated"
    second = repository.commit_probe_submission(second_envelope)

    assert first["committed"] is True
    assert all(first["stages"].values())
    assert second["committed"] is True
    assert len(client.players) == 1
    assert len(client.responses) == 1
    player = client.players[0]
    response = client.responses[0]
    assert notion_module._rich(player["properties"], "participant_id") == PARTICIPANT
    assert player["properties"]["email"]["email"] == "andres@example.org"
    assert notion_module._rich(player["properties"], "institution") == "CNRS updated"
    credential = _probe_submission_envelope()["player"]["credential"]
    assert notion_module._rich(player["properties"], "access_code_emoji") == credential["emoji"]
    assert notion_module._rich(player["properties"], "access_code_selector") == credential["selector"]
    assert notion_module._rich(player["properties"], "access_code_selector_6") == credential["selector_6"]
    assert notion_module._rich(player["properties"], "access_code_verifier") == credential["verifier"]
    assert response["properties"]["player"] == {
        "relation": [{"id": player["id"]}]
    }
    persisted = json.loads(notion_module._rich(response["properties"], "value_json"))
    assert "player" not in persisted
    assert "access_code_verifier" not in persisted
    assert "credential" not in persisted
    assert "email" not in persisted["payload"]
    assert {
        event.get("question_id")
        for event in persisted["trajectory"]["events"]
    } == {"participation_position"}

    hydrated = repository.get_probe_trajectory("participation-1")
    assert hydrated is not None
    assert {
        event.get("question_id") for event in hydrated["trajectory"]["events"]
    } == {"email", "participation_position"}


def test_revised_probe_submission_creates_second_response_revision(
    monkeypatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(notion_module, "Client", FakeClient)
    repository = NotionRepository(token="test", manifest_path=_manifest(tmp_path))
    client = FakeClient.instance
    assert client is not None

    repository.commit_probe_submission(_probe_submission_envelope())
    revised = _probe_submission_envelope()
    revised["submission_id"] = "submission-2"
    revised["integrated_at"] = "2026-09-24T13:00:00+00:00"
    revised["updated_at"] = revised["integrated_at"]
    revised["trajectory"]["events"][-1]["timestamp"] = revised["integrated_at"]
    repository.commit_probe_submission(revised)

    assert len(client.players) == 1
    assert len(client.responses) == 2
    assert [
        page["properties"]["revision"]["number"] for page in client.responses
    ] == [1, 2]


def test_probe_commit_reports_player_id_when_response_write_fails(
    monkeypatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(notion_module, "Client", FakeClient)
    repository = NotionRepository(token="test", manifest_path=_manifest(tmp_path))
    monkeypatch.setattr(
        repository,
        "_save_probe_trajectory",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError("write failed")),
    )

    with pytest.raises(ProbeSubmissionCommitError) as raised:
        repository.commit_probe_submission(_probe_submission_envelope())

    receipt = raised.value.receipt
    assert receipt["committed"] is False
    assert receipt["player_page_id"]
    assert receipt["response_page_id"] == ""
    assert receipt["stages"]["player_identity_persisted"] is True
    assert receipt["stages"]["response_persisted"] is False
    assert receipt["phase"] == "response_write"
    assert receipt["exception_class"] == "RuntimeError"
    assert receipt["sanitized_message"] == "write failed"
    assert receipt["rollback"] == {
        "attempted": True,
        "response": "not_needed",
        "player": "archived",
    }
    assert any(
        update["page_id"] == receipt["player_page_id"]
        and update.get("archived") is True
        for update in FakeClient.instance.updated
    )


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
