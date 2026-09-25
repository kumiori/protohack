from __future__ import annotations

from argparse import Namespace
import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

import scripts.bootstrap_protohack_notion as bootstrap


def rich_title(value: str) -> list[dict[str, str]]:
    return [{"plain_text": value}]


class FakeNotion:
    def __init__(self, *, missing_key: str = "") -> None:
        self.parent_id = "parent-id"
        self.parent = {
            "id": self.parent_id,
            "url": "https://www.notion.so/ProtocolHack-parent-id",
            "properties": {
                "title": {"type": "title", "title": rich_title("ProtocolHack")}
            },
        }
        self.databases_by_id: dict[str, dict[str, Any]] = {}
        self.sources_by_id: dict[str, dict[str, Any]] = {}
        self.seed_page = {
            "id": "seed-session-page",
            "url": "https://www.notion.so/seed-session-page",
            "parent": {
                "type": "data_source_id",
                "data_source_id": "source-sessions",
            },
            "properties": {
                "session_code": {
                    "type": "title",
                    "title": rich_title("commons_pilot_2026"),
                }
            },
        }
        for key, title in bootstrap.DISCOVERY_DATABASES.items():
            if key == missing_key:
                continue
            database_id = f"database-{key}"
            source_id = f"source-{key}"
            properties = {"Name": {"type": "title"}}
            if key in bootstrap.DATABASES:
                properties = {
                    name: {"type": bootstrap.expected_type(schema)}
                    for name, schema in bootstrap.DATABASES[key]["properties"].items()
                }
                properties.update(
                    {
                        name: {"type": "relation"}
                        for name in bootstrap.RELATIONS.get(key, {})
                    }
                )
            self.databases_by_id[database_id] = {
                "id": database_id,
                "title": rich_title(title),
                "parent": {"type": "page_id", "page_id": self.parent_id},
                "data_sources": [{"id": source_id, "name": title}],
            }
            self.sources_by_id[source_id] = {
                "id": source_id,
                "title": rich_title(title),
                "parent": {"type": "database_id", "database_id": database_id},
                "properties": properties,
            }

        self.pages = SimpleNamespace(retrieve=self.retrieve_page)
        self.databases = SimpleNamespace(retrieve=self.retrieve_database)
        self.data_sources = SimpleNamespace(
            retrieve=self.retrieve_source,
            query=self.query_source,
        )
        self.users = SimpleNamespace(me=self.me)
        self.blocks = SimpleNamespace(
            children=SimpleNamespace(list=self.list_children)
        )

    def search(self, **arguments: Any) -> dict[str, Any]:
        assert arguments["filter"] == {"property": "object", "value": "page"}
        return {"results": [self.parent], "has_more": False, "next_cursor": None}

    def retrieve_page(self, *, page_id: str) -> dict[str, Any]:
        if page_id == self.seed_page["id"]:
            return self.seed_page
        assert page_id == self.parent_id
        return self.parent

    def list_children(self, **arguments: Any) -> dict[str, Any]:
        assert arguments["block_id"] == self.parent_id
        return {
            "results": [
                {"id": database_id, "type": "child_database"}
                for database_id in self.databases_by_id
            ],
            "has_more": False,
            "next_cursor": None,
        }

    def retrieve_database(self, *, database_id: str) -> dict[str, Any]:
        return self.databases_by_id[database_id]

    def retrieve_source(self, *, data_source_id: str) -> dict[str, Any]:
        return self.sources_by_id[data_source_id]

    def query_source(self, **arguments: Any) -> dict[str, Any]:
        assert arguments["data_source_id"] == "source-sessions"
        assert arguments["filter"]["title"]["equals"] == "commons_pilot_2026"
        return {"results": [self.seed_page], "has_more": False}

    def me(self) -> dict[str, str]:
        return {"id": "integration-id", "name": "Protocol Hack tests"}


def arguments(manifest: Path) -> Namespace:
    return Namespace(
        manifest=str(manifest),
        parent_page_id="parent-id",
        parent_title="ProtocolHack",
        token_env="NOTION_TOKEN",
    )


def test_resolve_parent_can_search_for_exact_title() -> None:
    parent = bootstrap.resolve_parent_page(
        FakeNotion(),
        requested_id="",
        requested_title="Protocol Hack",
    )

    assert parent == {
        "page_id": "parent-id",
        "title": "ProtocolHack",
        "url": "https://www.notion.so/ProtocolHack-parent-id",
    }


def test_discover_writes_and_verifies_all_exact_objects(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    manifest_path = tmp_path / "protohack_notion.json"
    client = FakeNotion()
    monkeypatch.setattr(bootstrap, "Client", lambda **_: client)
    monkeypatch.setattr(bootstrap, "token_or_fail", lambda _name: "secret-test")

    bootstrap.command_discover(arguments(manifest_path))

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert list(manifest["databases"]) == list(bootstrap.DISCOVERY_DATABASES)
    assert manifest["parent_page_id"] == "parent-id"
    assert manifest["discovery"]["direct_child_database_count"] == 14
    assert manifest["seed_session"] == {
        "session_code": "commons_pilot_2026",
        "page_id": "seed-session-page",
        "page_url": "https://www.notion.so/seed-session-page",
    }
    for key, expected_title in bootstrap.DISCOVERY_DATABASES.items():
        record = manifest["databases"][key]
        assert record["title"] == expected_title
        assert record["database_id"] == f"database-{key}"
        assert record["data_source_id"] == f"source-{key}"
        assert record["schema"]["property_count"] > 0

    output = capsys.readouterr().out
    assert "verified 14 discovered databases" in output
    assert 'protohack_timeline_rooms_db_id = "database-timeline_rooms"' in output
    assert (
        'protohack_timeline_rooms_data_source_id = "source-timeline_rooms"'
        in output
    )


def test_discover_does_not_overwrite_manifest_when_inventory_is_incomplete(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    manifest_path = tmp_path / "protohack_notion.json"
    original = {"sentinel": "keep-me"}
    manifest_path.write_text(json.dumps(original), encoding="utf-8")
    client = FakeNotion(missing_key="timeline_events")
    monkeypatch.setattr(bootstrap, "Client", lambda **_: client)
    monkeypatch.setattr(bootstrap, "token_or_fail", lambda _name: "secret-test")

    with pytest.raises(RuntimeError, match="protohack_TimelineEvents"):
        bootstrap.command_discover(arguments(manifest_path))

    assert json.loads(manifest_path.read_text(encoding="utf-8")) == original


def test_discover_replaces_an_inaccessible_stored_parent_via_exact_search(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    manifest_path = tmp_path / "protohack_notion.json"
    manifest_path.write_text(
        json.dumps({"parent_page_id": "stale-parent"}),
        encoding="utf-8",
    )
    client = FakeNotion()
    monkeypatch.setattr(bootstrap, "Client", lambda **_: client)
    monkeypatch.setattr(bootstrap, "token_or_fail", lambda _name: "secret-test")
    args = arguments(manifest_path)
    args.parent_page_id = ""

    bootstrap.command_discover(args)

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest["parent_page_id"] == "parent-id"
