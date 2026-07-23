from copy import deepcopy
from pathlib import Path

import storage.notion as notion_module
from scripts.bootstrap_protohack_notion import DATABASES, RELATIONS, SCHEMA_VERSION
from storage.notion import NotionRepository


PARTICIPANT = "00000000-0000-4000-8000-000000000001"


class FakeDataSources:
    def __init__(self, owner: "FakeClient") -> None:
        self.owner = owner

    def query(self, **arguments):
        source_id = arguments["data_source_id"]
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
          }
        }""",
        encoding="utf-8",
    )
    return path


def test_bootstrap_v2_has_no_strategy_to_contact_relation() -> None:
    assert SCHEMA_VERSION == "protohack-notion-v2-mapping-coordination"
    assert "player" not in RELATIONS["responses"]
    assert "participant_uuid" in DATABASES["responses"]["properties"]
    assert "rationale" in DATABASES["responses"]["properties"]
    assert "participant_uuid" in DATABASES["players"]["properties"]
    assert "coordination_status" in DATABASES["players"]["properties"]


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
