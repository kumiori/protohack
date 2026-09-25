#!/usr/bin/env python3
"""Create or verify the Protocol Hack Notion database family.

The script is deliberately safe to rerun. It records every created database in
``config/protohack_notion.json`` before adding relations, so an interrupted run
can resume without producing duplicate databases.

Examples:
    python scripts/bootstrap_protohack_notion.py plan
    python scripts/bootstrap_protohack_notion.py create --parent-page-id PAGE_ID
    python scripts/bootstrap_protohack_notion.py discover
    python scripts/bootstrap_protohack_notion.py verify
    python scripts/bootstrap_protohack_notion.py emit-secrets

Required for ``create``, ``discover``, and ``verify``:
    the environment variable selected by ``--token-env`` (default: NOTION_TOKEN)

The default API version matches the runtime. Override
it with NOTION_VERSION only after the application client is upgraded as well.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import sys
from typing import Any

# Direct execution sets ``sys.path[0]`` to ``scripts/``.  Add the repository
# root before importing application packages so every documented invocation
# works without an ambient PYTHONPATH.
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from notion_client import Client
from notion_client.errors import APIResponseError


DEFAULT_MANIFEST = ROOT / "config" / "protohack_notion.json"
DEFAULT_NOTION_VERSION = "2025-09-03"
SCHEMA_VERSION = "protohack-notion-v7-player-credential"
PREFIX = "protohack"


def rich_text() -> dict[str, Any]:
    return {"rich_text": {}}


def number() -> dict[str, Any]:
    return {"number": {"format": "number"}}


def date() -> dict[str, Any]:
    return {"date": {}}


def checkbox() -> dict[str, Any]:
    return {"checkbox": {}}


def select(*options: tuple[str, str]) -> dict[str, Any]:
    return {
        "select": {
            "options": [{"name": name, "color": color} for name, color in options]
        }
    }


DATABASES: dict[str, dict[str, Any]] = {
    "sessions": {
        "title": f"{PREFIX}_Sessions",
        "properties": {
            "session_code": {"title": {}},
            "session_name": rich_text(),
            "session_title": rich_text(),
            "session_order": number(),
            "session_description": rich_text(),
            "session_visualisation": rich_text(),
            "status": select(
                ("Draft", "gray"),
                ("Lobby", "yellow"),
                ("Open", "green"),
                ("Closed", "red"),
                ("Archived", "brown"),
            ),
            "mode": select(("Non-linear", "purple"), ("Linear", "blue")),
            "round_index": number(),
            "active": checkbox(),
            "start": date(),
            "end": date(),
            "created_at": date(),
            "notes": rich_text(),
        },
    },
    "statements": {
        "title": f"{PREFIX}_Statements",
        "properties": {
            "Name": {"title": {}},
            "theme": select(
                ("commons", "blue"),
                ("governance", "purple"),
                ("care", "pink"),
                ("power", "red"),
                ("action", "green"),
                ("other", "gray"),
            ),
            "active": checkbox(),
            "order": number(),
            "created_at": date(),
            "notes": rich_text(),
        },
    },
    "players": {
        "title": f"{PREFIX}_Players",
        "properties": {
            "Name": {"title": {}},
            "access_key": rich_text(),
            "nickname": rich_text(),
            "role": select(
                ("participant", "blue"),
                ("host", "purple"),
                ("admin", "red"),
                ("observer", "gray"),
            ),
            "status": select(("active", "green"), ("revoked", "red")),
            "consented": checkbox(),
            "consent_research": checkbox(),
            "preferred_mode": select(
                ("quick", "blue"),
                ("standard", "purple"),
                ("deep", "orange"),
            ),
            "email": {"email": {}},
            "emoji": rich_text(),
            "emoji_suffix_4": rich_text(),
            "emoji_suffix_6": rich_text(),
            "phrase": rich_text(),
            "joined_at": date(),
            "last_joined_on": date(),
            "last_seen": date(),
            "intent": rich_text(),
            "motivation": rich_text(),
            "participant_uuid": rich_text(),
            "participant_id": rich_text(),
            "access_code_selector": rich_text(),
            "access_code_selector_6": rich_text(),
            "access_code_emoji": rich_text(),
            "access_code_verifier": rich_text(),
            "institution": rich_text(),
            "base_location": rich_text(),
            "base_location_label": rich_text(),
            "base_location_place_id": rich_text(),
            "base_location_lat": number(),
            "base_location_lon": number(),
            "profile_json": rich_text(),
            "coordination_opt_in": checkbox(),
            "coordination_consent_version": rich_text(),
            "coordination_consented_at": date(),
            "coordination_status": select(
                ("anonymous_interest", "yellow"),
                ("reachable_interest", "green"),
                ("withdrawn", "gray"),
            ),
        },
    },
    "responses": {
        "title": f"{PREFIX}_Responses",
        "properties": {
            "Name": {"title": {}},
            "question_id": rich_text(),
            "item_id": rich_text(),
            "value_json": rich_text(),
            "response_value": rich_text(),
            "value": rich_text(),
            "value_label": rich_text(),
            "question_type": select(
                ("single", "blue"),
                ("multi", "purple"),
                ("text", "green"),
                ("scale", "orange"),
                ("geography_context", "yellow"),
                ("signal", "pink"),
                ("other", "gray"),
            ),
            "score": number(),
            "timestamp": date(),
            "submitted_at": date(),
            "created_at": date(),
            "page_index": number(),
            "depth": number(),
            "optional_text": rich_text(),
            "text_id": rich_text(),
            "device_id": rich_text(),
            "access_key": rich_text(),
            "note": rich_text(),
            "participant_uuid": rich_text(),
            "scenario_id": rich_text(),
            "decision_id": rich_text(),
            "action_id": rich_text(),
            "rationale": rich_text(),
            "semantic_tags_json": rich_text(),
            "tagger_version": rich_text(),
            "strategic_profile_json": rich_text(),
            "integration_status": select(
                ("integrated", "green"),
                ("superseded", "gray"),
            ),
            "integrated_at": date(),
            "protocol_version": rich_text(),
            "revision": number(),
            "submission_id": rich_text(),
            "participation_id": rich_text(),
            "event_id": rich_text(),
            "probe_id": rich_text(),
            "probe_revision": number(),
            "submission_state": select(
                ("draft", "gray"),
                ("submitted", "green"),
            ),
            "record_type": select(
                ("probe_submission", "blue"),
                ("legacy_response", "gray"),
            ),
            "environment": select(
                ("production", "green"),
                ("test", "yellow"),
                ("prelaunch", "orange"),
            ),
        },
    },
    "test_submissions": {
        "title": f"{PREFIX}_ProbeTestSubmissions",
        "properties": {
            "Name": {"title": {}},
            "event_id": rich_text(),
            "probe_id": rich_text(),
            "probe_revision": number(),
            "participant_id": rich_text(),
            "participation_id": rich_text(),
            "submission_id": rich_text(),
            "environment": select(("test", "yellow")),
            "state": select(("draft", "gray"), ("submitted", "green")),
            "batch_id": rich_text(),
            "access_code_selector": rich_text(),
            "access_code_verifier": rich_text(),
            "created_at": date(),
            "updated_at": date(),
            "payload": rich_text(),
            "receipt_metadata": rich_text(),
        },
    },
    "questions": {
        "title": f"{PREFIX}_Questions",
        "properties": {
            "Name": {"title": {}},
            "item_id": rich_text(),
            "question_text": rich_text(),
            "domain": select(
                ("commons", "blue"),
                ("governance", "purple"),
                ("care", "pink"),
                ("power", "red"),
                ("action", "green"),
                ("other", "gray"),
            ),
            "status": select(
                ("pending", "gray"),
                ("approved", "green"),
                ("rewrite", "orange"),
                ("parked", "red"),
            ),
            "approve_count": number(),
            "rewrite_count": number(),
            "park_count": number(),
            "created_at": date(),
            "last_updated": date(),
            "metadata_json": rich_text(),
        },
    },
    "moderation_votes": {
        "title": f"{PREFIX}_ModerationVotes",
        "properties": {
            "Name": {"title": {}},
            "vote": select(
                ("approve", "green"),
                ("rewrite", "orange"),
                ("park", "red"),
            ),
            "created_at": date(),
            "note": rich_text(),
        },
    },
    "decisions": {
        "title": f"{PREFIX}_Decisions",
        "properties": {
            "Name": {"title": {}},
            "type": select(
                ("description_status", "blue"),
                ("pathway_choice", "purple"),
                ("structure_choice", "pink"),
                ("publication_state", "green"),
                ("other", "gray"),
            ),
            "payload": rich_text(),
            "created_at": date(),
        },
    },
    "events": {
        "title": f"{PREFIX}_Events",
        "properties": {
            "Name": {"title": {}},
            "timestamp": date(),
            "event_type": select(
                ("page_view", "gray"),
                ("login_success", "green"),
                ("login_failure", "red"),
                ("mint_key", "blue"),
                ("question_rendered", "yellow"),
                ("answer_submitted", "green"),
                ("answer_deferred", "orange"),
                ("question_skipped", "orange"),
                ("question_flagged", "purple"),
                ("response_written", "green"),
                ("response_write_failed", "red"),
                ("overview_loaded", "blue"),
                ("host_loaded", "purple"),
                ("contamination_detected", "red"),
                ("logout", "brown"),
                ("other", "gray"),
            ),
            "item_id": rich_text(),
            "page": rich_text(),
            "value_label": rich_text(),
            "metadata_json": rich_text(),
            "device_id": rich_text(),
            "status": select(
                ("ok", "green"),
                ("warning", "yellow"),
                ("error", "red"),
            ),
        },
    },
    "goals": {
        "title": f"{PREFIX}_Goals",
        "properties": {
            "Name": {"title": {}},
            "goal_id": rich_text(),
            "objective": rich_text(),
            "created_by_agent_id": rich_text(),
            "status": select(("open", "green"), ("closed", "gray")),
            "visibility": select(("public", "blue")),
            "created_at": date(),
        },
    },
    "goal_trajectories": {
        "title": f"{PREFIX}_GoalTrajectories",
        "properties": {
            "Name": {"title": {}},
            "trajectory_id": rich_text(),
            "agent_id": rich_text(),
            "agent_display_name": rich_text(),
            "agent_type": select(
                ("person", "blue"),
                ("team", "green"),
                ("institution", "purple"),
                ("assistant", "orange"),
            ),
            "title": rich_text(),
            "schema_version": rich_text(),
            "trajectory_payload": rich_text(),
            "created_at": date(),
            "updated_at": date(),
            "status": select(
                ("draft", "gray"),
                ("shared", "green"),
                ("withdrawn", "red"),
            ),
            "source": select(
                ("created_for_goal", "blue"),
                ("imported_existing_plan", "purple"),
            ),
            "revision": number(),
        },
    },
}


# Discovery also adopts database families created by newer operational
# surfaces.  The timeline schemas are inspected and recorded rather than
# authored here; ``create`` remains limited to the schemas owned above.
DISCOVERY_DATABASES: dict[str, str] = {
    "statements": f"{PREFIX}_Statements",
    "sessions": f"{PREFIX}_Sessions",
    "responses": f"{PREFIX}_Responses",
    "questions": f"{PREFIX}_Questions",
    "players": f"{PREFIX}_Players",
    "decisions": f"{PREFIX}_Decisions",
    "moderation_votes": f"{PREFIX}_ModerationVotes",
    "events": f"{PREFIX}_Events",
    "goals": f"{PREFIX}_Goals",
    "goal_trajectories": f"{PREFIX}_GoalTrajectories",
    "timeline_rooms": f"{PREFIX}_TimelineRooms",
    "timeline_members": f"{PREFIX}_TimelineMembers",
    "timeline_events": f"{PREFIX}_TimelineEvents",
    "test_submissions": f"{PREFIX}_ProbeTestSubmissions",
}
DEFAULT_PARENT_TITLE = "Protocol Hack"


RELATIONS: dict[str, dict[str, tuple[str, str]]] = {
    "players": {"session": ("sessions", "players")},
    "statements": {"session": ("sessions", "statements")},
    "responses": {
        "session": ("sessions", "responses"),
        "statement": ("statements", "responses"),
        "question": ("questions", "responses"),
        "player": ("players", "responses"),
    },
    "questions": {
        "session": ("sessions", "questions"),
        "submitted_by": ("players", "questions_submitted"),
    },
    "moderation_votes": {
        "session": ("sessions", "moderation_votes"),
        "question": ("questions", "moderation_votes"),
        "voter": ("players", "moderation_votes"),
    },
    "decisions": {
        "session": ("sessions", "decisions"),
        "player": ("players", "decisions"),
    },
    "events": {
        "session": ("sessions", "events"),
        "player": ("players", "events"),
    },
    "goal_trajectories": {
        "goal": ("goals", "contributions"),
    },
}


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def title(content: str) -> list[dict[str, Any]]:
    return [{"type": "text", "text": {"content": content}}]


def load_manifest(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def write_manifest(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def _plain_text(items: list[dict[str, Any]] | None) -> str:
    return "".join(
        str(item.get("plain_text") or (item.get("text") or {}).get("content") or "")
        for item in (items or [])
    ).strip()


def object_title(payload: dict[str, Any]) -> str:
    """Read a page, database, or data-source title without guessing a key."""

    direct = _plain_text(payload.get("title"))
    if direct:
        return direct
    for property_value in (payload.get("properties") or {}).values():
        if property_value.get("type") == "title" or "title" in property_value:
            value = _plain_text(property_value.get("title"))
            if value:
                return value
    return ""


def _normalise_title(value: str) -> str:
    return "".join(character.lower() for character in value if character.isalnum())


def search_all(
    client: Client,
    *,
    query: str,
    object_type: str,
) -> list[dict[str, Any]]:
    """Exhaust an exact-purpose Notion search, including pagination."""

    results: list[dict[str, Any]] = []
    cursor = ""
    while True:
        arguments: dict[str, Any] = {
            "query": query,
            "filter": {"property": "object", "value": object_type},
            "page_size": 100,
        }
        if cursor:
            arguments["start_cursor"] = cursor
        response = client.search(**arguments)
        results.extend(response.get("results") or [])
        cursor = str(response.get("next_cursor") or "")
        if not response.get("has_more") or not cursor:
            return results


def resolve_parent_page(
    client: Client,
    *,
    requested_id: str,
    requested_title: str,
) -> dict[str, str]:
    """Resolve one accessible Protocol Hack parent, failing on ambiguity."""

    expected = _normalise_title(requested_title)
    if requested_id:
        page = client.pages.retrieve(page_id=requested_id)
        found_title = object_title(page)
        if _normalise_title(found_title) != expected:
            raise RuntimeError(
                f"Configured parent {requested_id} is titled {found_title!r}, "
                f"not {requested_title!r}."
            )
        return {
            "page_id": str(page["id"]),
            "title": found_title,
            "url": str(page.get("url") or ""),
        }

    matches = [
        page
        for page in search_all(client, query=requested_title, object_type="page")
        if not page.get("in_trash")
        and _normalise_title(object_title(page)) == expected
    ]
    if not matches:
        raise RuntimeError(
            f"No accessible Notion page exactly matching {requested_title!r}. "
            "Share the page with the integration or pass --parent-page-id."
        )
    if len(matches) > 1:
        ids = ", ".join(str(page.get("id") or "") for page in matches)
        raise RuntimeError(
            f"Multiple accessible pages exactly match {requested_title!r}: {ids}. "
            "Pass --parent-page-id to disambiguate."
        )
    page = matches[0]
    return {
        "page_id": str(page["id"]),
        "title": object_title(page),
        "url": str(page.get("url") or ""),
    }


def schema_snapshot(source: dict[str, Any]) -> dict[str, Any]:
    properties = source.get("properties") or {}
    return {
        "property_count": len(properties),
        "properties": {
            name: str(value.get("type") or "unknown")
            for name, value in sorted(properties.items())
        },
    }


def enumerate_child_data_sources(
    client: Client,
    *,
    parent_page_id: str,
) -> list[dict[str, Any]]:
    """Enumerate data sources belonging to direct child databases."""

    child_database_ids: list[str] = []
    cursor = ""
    while True:
        arguments: dict[str, Any] = {
            "block_id": parent_page_id,
            "page_size": 100,
        }
        if cursor:
            arguments["start_cursor"] = cursor
        response = client.blocks.children.list(**arguments)
        for block in response.get("results") or []:
            if block.get("type") == "child_database" and not block.get("in_trash"):
                child_database_ids.append(str(block.get("id") or ""))
        cursor = str(response.get("next_cursor") or "")
        if not response.get("has_more") or not cursor:
            break

    inventory: list[dict[str, Any]] = []
    for database_id in dict.fromkeys(filter(None, child_database_ids)):
        database = client.databases.retrieve(database_id=database_id)
        database_parent = database.get("parent") or {}
        if (
            database_parent.get("type") != "page_id"
            or str(database_parent.get("page_id") or "") != parent_page_id
        ):
            continue
        for source_reference in database.get("data_sources") or []:
            source_id = str(source_reference.get("id") or "")
            if not source_id:
                continue
            source = client.data_sources.retrieve(data_source_id=source_id)
            source_parent = source.get("parent") or {}
            if (
                source_parent.get("type") != "database_id"
                or str(source_parent.get("database_id") or "") != database_id
            ):
                continue
            inventory.append(
                {
                    "database": database,
                    "database_id": database_id,
                    "data_source": source,
                    "data_source_id": source_id,
                }
            )
    return inventory


def discover_database(
    inventory: list[dict[str, Any]],
    *,
    expected_title: str,
    parent_page_id: str,
) -> dict[str, Any]:
    """Resolve one exact data source from the enumerated parent inventory."""

    candidates: list[dict[str, Any]] = []
    for item in inventory:
        database = item["database"]
        source = item["data_source"]
        if object_title(database) != expected_title:
            continue
        if object_title(source) != expected_title:
            continue
        candidates.append(
            {
                "title": expected_title,
                "database_id": item["database_id"],
                "data_source_id": item["data_source_id"],
                "schema": schema_snapshot(source),
            }
        )

    unique = {
        (candidate["database_id"], candidate["data_source_id"]): candidate
        for candidate in candidates
    }
    if not unique:
        raise RuntimeError(
            f"Missing direct child data source {expected_title!r} under parent "
            f"{parent_page_id}."
        )
    if len(unique) > 1:
        ids = ", ".join(
            f"{database_id}/{source_id}"
            for database_id, source_id in sorted(unique)
        )
        raise RuntimeError(
            f"Ambiguous direct child data source {expected_title!r}: {ids}."
        )
    return next(iter(unique.values()))


def discover_seed_session(
    client: Client,
    *,
    sessions_data_source_id: str,
) -> dict[str, str]:
    session_code = "commons_pilot_2026"
    response = client.data_sources.query(
        data_source_id=sessions_data_source_id,
        filter={
            "property": "session_code",
            "title": {"equals": session_code},
        },
        page_size=2,
    )
    matches = response.get("results") or []
    if not matches:
        raise RuntimeError(
            f"Missing seed session {session_code!r} in the discovered Sessions "
            "data source."
        )
    if len(matches) > 1:
        ids = ", ".join(str(page.get("id") or "") for page in matches)
        raise RuntimeError(f"Duplicate seed sessions {session_code!r}: {ids}.")
    page = matches[0]
    return {
        "session_code": session_code,
        "page_id": str(page["id"]),
        "page_url": str(page.get("url") or ""),
    }


def token_or_fail(environment_name: str = "NOTION_TOKEN") -> str:
    """Read the CLI credential without importing application configuration."""

    token = str(os.getenv(environment_name, "") or "").strip()
    if not token:
        raise RuntimeError(
            f"{environment_name} is required for this command "
            f"(selected by --token-env)."
        )
    return token


def data_source_id(client: Client, database_id: str, response: dict[str, Any]) -> str:
    sources = response.get("data_sources") or []
    if not sources:
        sources = client.databases.retrieve(database_id=database_id).get(
            "data_sources", []
        )
    if not sources or not sources[0].get("id"):
        raise RuntimeError(f"No initial data source returned for {database_id}.")
    return str(sources[0]["id"])


def create_database(
    client: Client,
    *,
    parent_page_id: str,
    key: str,
) -> dict[str, str]:
    spec = DATABASES[key]
    response = client.databases.create(
        parent={"type": "page_id", "page_id": parent_page_id},
        title=title(str(spec["title"])),
        description=title("Protocol Hack questionnaire infrastructure."),
        is_inline=False,
        initial_data_source={"properties": spec["properties"]},
    )
    database_id = str(response["id"])
    return {
        "title": str(spec["title"]),
        "database_id": database_id,
        "data_source_id": data_source_id(client, database_id, response),
    }


def relation_spec(target_data_source_id: str, synced_name: str) -> dict[str, Any]:
    return {
        "relation": {
            "data_source_id": target_data_source_id,
            "dual_property": {"synced_property_name": synced_name},
        }
    }


def configure_relations(client: Client, databases: dict[str, Any]) -> None:
    for source_key, relation_map in RELATIONS.items():
        properties = {
            property_name: relation_spec(
                str(databases[target_key]["data_source_id"]), synced_name
            )
            for property_name, (target_key, synced_name) in relation_map.items()
        }
        client.data_sources.update(
            data_source_id=str(databases[source_key]["data_source_id"]),
            properties=properties,
        )


def reconcile_base_properties(client: Client, databases: dict[str, Any]) -> None:
    """Add current fields to an existing manifest without recreating databases."""

    for key, spec in DATABASES.items():
        source_id = str(databases[key]["data_source_id"])
        try:
            current = client.data_sources.retrieve(data_source_id=source_id)
        except APIResponseError as exc:
            if "Could not find data_source" not in str(exc):
                raise
            raise RuntimeError(
                "The manifest points to a data source unavailable to this "
                "integration. It likely belongs to another Notion workspace. "
                "Do not reuse this manifest: create a fresh manifest with "
                "--manifest and the target workspace's --parent-page-id."
            ) from exc
        actual = current.get("properties") or {}
        changes = {
            property_name: property_schema
            for property_name, property_schema in spec["properties"].items()
            if property_name not in actual
        }
        if changes:
            client.data_sources.update(
                data_source_id=source_id,
                properties=changes,
            )


def ensure_seed_session(client: Client, sessions_data_source_id: str) -> str:
    session_code = "commons_pilot_2026"
    result = client.data_sources.query(
        data_source_id=sessions_data_source_id,
        filter={
            "property": "session_code",
            "title": {"equals": session_code},
        },
        page_size=1,
    )
    if result.get("results"):
        return str(result["results"][0]["id"])

    created = client.pages.create(
        parent={"type": "data_source_id", "data_source_id": sessions_data_source_id},
        properties={
            "session_code": {"title": title(session_code)},
            "session_name": {"rich_text": title("Commons pilot")},
            "session_title": {"rich_text": title("Questioning the Commons")},
            "session_order": {"number": 10},
            "session_description": {
                "rich_text": title(
                    "Draft pilot for the first Protocol Hack commons questionnaire."
                )
            },
            "session_visualisation": {"rich_text": title("commons_overview")},
            "status": {"select": {"name": "Draft"}},
            "mode": {"select": {"name": "Non-linear"}},
            "round_index": {"number": 0},
            "active": {"checkbox": False},
            "created_at": {"date": {"start": now_iso()}},
            "notes": {"rich_text": title(SCHEMA_VERSION)},
        },
    )
    return str(created["id"])


def expected_type(schema: dict[str, Any]) -> str:
    return next(iter(schema))


def verify(client: Client, manifest: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    databases = manifest.get("databases") or {}
    for key, spec in DATABASES.items():
        recorded = databases.get(key)
        if not recorded:
            errors.append(f"Missing manifest entry: {key}")
            continue
        source_id = str(recorded.get("data_source_id") or "")
        if not source_id:
            errors.append(f"Missing data_source_id: {key}")
            continue
        try:
            source = client.data_sources.retrieve(data_source_id=source_id)
        except Exception as exc:
            errors.append(f"Cannot retrieve {key}: {exc}")
            continue
        properties = source.get("properties") or {}
        for property_name, expected_schema in spec["properties"].items():
            actual = properties.get(property_name)
            wanted_type = expected_type(expected_schema)
            if not actual:
                errors.append(f"{key}.{property_name}: missing")
            elif actual.get("type") != wanted_type:
                errors.append(
                    f"{key}.{property_name}: expected {wanted_type}, "
                    f"found {actual.get('type')}"
                )
        for property_name in RELATIONS.get(key, {}):
            actual = properties.get(property_name)
            if not actual or actual.get("type") != "relation":
                errors.append(f"{key}.{property_name}: missing relation")
    return errors


def verify_discovered(client: Client, manifest: dict[str, Any]) -> list[str]:
    """Verify identity, parentage, schema snapshot, and owned schema contracts."""

    errors: list[str] = []
    parent_page_id = str(manifest.get("parent_page_id") or "")
    parent_title = str(manifest.get("parent_title") or DEFAULT_PARENT_TITLE)
    if not parent_page_id:
        errors.append("Missing parent_page_id")
    else:
        try:
            parent = client.pages.retrieve(page_id=parent_page_id)
            if _normalise_title(object_title(parent)) != _normalise_title(parent_title):
                errors.append(
                    f"Parent title changed: expected {parent_title!r}, "
                    f"found {object_title(parent)!r}"
                )
        except Exception as exc:
            errors.append(f"Cannot retrieve parent page {parent_page_id}: {exc}")

    databases = manifest.get("databases") or {}
    for key, expected_title in DISCOVERY_DATABASES.items():
        recorded = databases.get(key)
        if not recorded:
            errors.append(f"Missing manifest entry: {key}")
            continue
        database_id = str(recorded.get("database_id") or "")
        source_id = str(recorded.get("data_source_id") or "")
        if not database_id:
            errors.append(f"Missing database_id: {key}")
        if not source_id:
            errors.append(f"Missing data_source_id: {key}")
        if not database_id or not source_id:
            continue

        try:
            database = client.databases.retrieve(database_id=database_id)
            source = client.data_sources.retrieve(data_source_id=source_id)
        except Exception as exc:
            errors.append(f"Cannot retrieve discovered object {key}: {exc}")
            continue

        database_parent = database.get("parent") or {}
        if (
            database_parent.get("type") != "page_id"
            or str(database_parent.get("page_id") or "") != parent_page_id
        ):
            errors.append(f"{key}: database is not a direct child of the parent")
        if object_title(database) != expected_title:
            errors.append(
                f"{key}: expected database title {expected_title!r}, "
                f"found {object_title(database)!r}"
            )

        source_parent = source.get("parent") or {}
        if (
            source_parent.get("type") != "database_id"
            or str(source_parent.get("database_id") or "") != database_id
        ):
            errors.append(f"{key}: data source does not belong to its database")
        if object_title(source) != expected_title:
            errors.append(
                f"{key}: expected data-source title {expected_title!r}, "
                f"found {object_title(source)!r}"
            )
        source_ids = {
            str(item.get("id") or "")
            for item in (database.get("data_sources") or [])
        }
        if source_id not in source_ids:
            errors.append(f"{key}: database does not list data source {source_id}")

        current_snapshot = schema_snapshot(source)
        if current_snapshot["property_count"] == 0:
            errors.append(f"{key}: schema has no properties")
        if recorded.get("schema") != current_snapshot:
            errors.append(f"{key}: schema differs from the discovered snapshot")

    # These are schemas authored and consumed by this repository, so discovery
    # also retains their stronger property and relation verification.
    errors.extend(verify(client, manifest))

    seed = manifest.get("seed_session") or {}
    expected_session_code = "commons_pilot_2026"
    seed_page_id = str(seed.get("page_id") or "")
    sessions_source_id = str(
        (databases.get("sessions") or {}).get("data_source_id") or ""
    )
    if not seed_page_id:
        errors.append("Missing seed_session.page_id")
    else:
        try:
            seed_page = client.pages.retrieve(page_id=seed_page_id)
            seed_parent = seed_page.get("parent") or {}
            if (
                seed_parent.get("type") != "data_source_id"
                or str(seed_parent.get("data_source_id") or "")
                != sessions_source_id
            ):
                errors.append(
                    "seed_session: page does not belong to the discovered "
                    "Sessions data source"
                )
            if object_title(seed_page) != expected_session_code:
                errors.append(
                    f"seed_session: expected {expected_session_code!r}, "
                    f"found {object_title(seed_page)!r}"
                )
        except Exception as exc:
            errors.append(f"Cannot retrieve seed session {seed_page_id}: {exc}")
    return list(dict.fromkeys(errors))


def validate_discovery_manifest(manifest: dict[str, Any]) -> list[str]:
    """Validate the manifest against objects already retrieved by discovery."""

    errors: list[str] = []
    if not manifest.get("parent_page_id"):
        errors.append("Missing parent_page_id")
    if not manifest.get("parent_title"):
        errors.append("Missing parent_title")
    databases = manifest.get("databases") or {}
    for key, expected_title in DISCOVERY_DATABASES.items():
        recorded = databases.get(key) or {}
        if not recorded:
            errors.append(f"Missing manifest entry: {key}")
            continue
        if recorded.get("title") != expected_title:
            errors.append(f"{key}: title is not {expected_title!r}")
        if not recorded.get("database_id"):
            errors.append(f"Missing database_id: {key}")
        if not recorded.get("data_source_id"):
            errors.append(f"Missing data_source_id: {key}")
        snapshot = recorded.get("schema") or {}
        properties = snapshot.get("properties") or {}
        if snapshot.get("property_count") != len(properties) or not properties:
            errors.append(f"{key}: invalid or empty schema snapshot")
            continue
        if key in DATABASES:
            for property_name, expected_schema in DATABASES[key][
                "properties"
            ].items():
                wanted_type = expected_type(expected_schema)
                if properties.get(property_name) != wanted_type:
                    errors.append(
                        f"{key}.{property_name}: expected {wanted_type}, "
                        f"found {properties.get(property_name)}"
                    )
            for property_name in RELATIONS.get(key, {}):
                if properties.get(property_name) != "relation":
                    errors.append(f"{key}.{property_name}: missing relation")
    seed = manifest.get("seed_session") or {}
    if seed.get("session_code") != "commons_pilot_2026":
        errors.append("Missing canonical seed session code")
    if not seed.get("page_id"):
        errors.append("Missing seed_session.page_id")
    return list(dict.fromkeys(errors))


def build_discovery_manifest(
    client: Client,
    *,
    parent: dict[str, str],
) -> dict[str, Any]:
    inventory = enumerate_child_data_sources(
        client,
        parent_page_id=parent["page_id"],
    )
    discovered: dict[str, Any] = {}
    for key, expected_title in DISCOVERY_DATABASES.items():
        discovered[key] = discover_database(
            inventory,
            expected_title=expected_title,
            parent_page_id=parent["page_id"],
        )

    integration = client.users.me()
    seed_session = discover_seed_session(
        client,
        sessions_data_source_id=str(discovered["sessions"]["data_source_id"]),
    )
    manifest: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "prefix": PREFIX,
        "parent_page_id": parent["page_id"],
        "parent_page_url": parent["url"],
        "parent_title": parent["title"],
        "status": "discovered",
        "updated_at": now_iso(),
        "discovery": {
            "integration_id": str(integration.get("id") or ""),
            "integration_name": str(integration.get("name") or ""),
            "direct_child_database_count": len(
                {item["database_id"] for item in inventory}
            ),
        },
        "databases": discovered,
        "seed_session": seed_session,
    }
    return manifest


def emit_secrets(manifest: dict[str, Any]) -> str:
    databases = manifest["databases"]
    lines = ["[notion]", '# token = "secret_..."']
    if manifest.get("parent_page_id"):
        lines.append(
            f'protohack_parent_page_id = "{manifest["parent_page_id"]}"'
        )
    ordered_keys = [key for key in DISCOVERY_DATABASES if key in databases]
    ordered_keys.extend(key for key in databases if key not in ordered_keys)
    for key in ordered_keys:
        record = databases[key]
        lines.append(f'protohack_{key}_db_id = "{record["database_id"]}"')
        if record.get("data_source_id"):
            lines.append(
                f'protohack_{key}_data_source_id = "{record["data_source_id"]}"'
            )
    lines.append('default_session_code = "commons_pilot_2026"')
    return "\n".join(lines)


def command_plan() -> None:
    print("Protocol Hack Notion database plan")
    for key, spec in DATABASES.items():
        print(f"- {key}: {spec['title']} ({len(spec['properties'])} base properties)")
    print(f"- seed session: commons_pilot_2026")
    print(f"- manifest: {DEFAULT_MANIFEST}")


def command_create(args: argparse.Namespace) -> None:
    token = token_or_fail(args.token_env)
    manifest_path = Path(args.manifest).resolve()
    manifest = load_manifest(manifest_path)
    parent_page_id = str(
        args.parent_page_id
        or manifest.get("parent_page_id")
        or os.getenv("PROTOHACK_NOTION_PARENT_PAGE_ID", "")
    ).strip()
    if not parent_page_id:
        raise RuntimeError(
            "Provide --parent-page-id or PROTOHACK_NOTION_PARENT_PAGE_ID."
        )

    client = Client(
        auth=token,
        notion_version=os.getenv("NOTION_VERSION", DEFAULT_NOTION_VERSION),
    )
    manifest["schema_version"] = SCHEMA_VERSION
    manifest.setdefault("prefix", PREFIX)
    manifest.setdefault("parent_page_id", parent_page_id)
    manifest.setdefault("databases", {})

    if manifest["parent_page_id"] != parent_page_id:
        raise RuntimeError(
            "Manifest parent_page_id does not match the requested parent."
        )

    for key in DATABASES:
        if key in manifest["databases"]:
            print(f"reuse {DATABASES[key]['title']}")
            continue
        print(f"create {DATABASES[key]['title']}")
        manifest["databases"][key] = create_database(
            client,
            parent_page_id=parent_page_id,
            key=key,
        )
        manifest["status"] = "databases_created"
        manifest["updated_at"] = now_iso()
        write_manifest(manifest_path, manifest)

    print("reconcile schema")
    reconcile_base_properties(client, manifest["databases"])
    print("configure relations")
    configure_relations(client, manifest["databases"])
    seed_id = ensure_seed_session(
        client, str(manifest["databases"]["sessions"]["data_source_id"])
    )
    manifest["seed_session"] = {
        "session_code": "commons_pilot_2026",
        "page_id": seed_id,
    }
    manifest["status"] = "ready"
    manifest["updated_at"] = now_iso()
    write_manifest(manifest_path, manifest)

    errors = verify(client, manifest)
    if errors:
        raise RuntimeError("Verification failed:\n- " + "\n- ".join(errors))
    print("ready")
    print(emit_secrets(manifest))


def command_discover(args: argparse.Namespace) -> None:
    token = token_or_fail(args.token_env)
    manifest_path = Path(args.manifest).resolve()
    existing = load_manifest(manifest_path)
    configured_parent_id = str(
        args.parent_page_id
        or os.getenv("PROTOHACK_NOTION_PARENT_PAGE_ID", "")
        or ""
    ).strip()
    manifest_parent_id = str(existing.get("parent_page_id") or "").strip()
    client = Client(
        auth=token,
        notion_version=os.getenv("NOTION_VERSION", DEFAULT_NOTION_VERSION),
    )
    if configured_parent_id:
        parent = resolve_parent_page(
            client,
            requested_id=configured_parent_id,
            requested_title=args.parent_title,
        )
    elif manifest_parent_id:
        try:
            parent = resolve_parent_page(
                client,
                requested_id=manifest_parent_id,
                requested_title=args.parent_title,
            )
        except Exception as exc:
            print(
                f"stored parent unavailable ({exc}); searching exact title",
                file=sys.stderr,
            )
            parent = resolve_parent_page(
                client,
                requested_id="",
                requested_title=args.parent_title,
            )
    else:
        parent = resolve_parent_page(
            client,
            requested_id="",
            requested_title=args.parent_title,
        )
    print(f"parent {parent['title']} ({parent['page_id']})")
    candidate = build_discovery_manifest(
        client,
        parent=parent,
    )
    errors = validate_discovery_manifest(candidate)
    if errors:
        raise RuntimeError("Discovery verification failed:\n- " + "\n- ".join(errors))

    write_manifest(manifest_path, candidate)
    written = load_manifest(manifest_path)
    errors = validate_discovery_manifest(written)
    if errors:
        raise RuntimeError(
            "Written manifest verification failed:\n- " + "\n- ".join(errors)
        )
    print(f"verified {len(DISCOVERY_DATABASES)} discovered databases")
    print(f"manifest {manifest_path}")
    print(emit_secrets(written))


def command_verify(args: argparse.Namespace) -> None:
    manifest_path = Path(args.manifest).resolve()
    manifest = load_manifest(manifest_path)
    if not manifest:
        raise RuntimeError(f"Manifest not found: {manifest_path}")
    client = Client(
        auth=token_or_fail(args.token_env),
        notion_version=os.getenv("NOTION_VERSION", DEFAULT_NOTION_VERSION),
    )
    databases = manifest.get("databases") or {}
    is_discovery_manifest = all(
        key in databases and databases[key].get("schema")
        for key in DISCOVERY_DATABASES
    )
    errors = (
        verify_discovered(client, manifest)
        if is_discovery_manifest
        else verify(client, manifest)
    )
    if errors:
        raise RuntimeError("Verification failed:\n- " + "\n- ".join(errors))
    count = len(DISCOVERY_DATABASES) if is_discovery_manifest else len(DATABASES)
    print(f"verified {count} databases ({SCHEMA_VERSION})")


def command_emit_secrets(args: argparse.Namespace) -> None:
    manifest = load_manifest(Path(args.manifest).resolve())
    if not manifest:
        raise RuntimeError(f"Manifest not found: {args.manifest}")
    print(emit_secrets(manifest))


def parser() -> argparse.ArgumentParser:
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument(
        "command",
        choices=("plan", "create", "discover", "verify", "emit-secrets"),
    )
    cli.add_argument("--parent-page-id", default="")
    cli.add_argument("--parent-title", default=DEFAULT_PARENT_TITLE)
    cli.add_argument("--manifest", default=str(DEFAULT_MANIFEST))
    cli.add_argument(
        "--token-env",
        default="NOTION_TOKEN",
        metavar="ENVIRONMENT_VARIABLE",
        help="environment variable containing the Notion token (default: NOTION_TOKEN)",
    )
    return cli


def main() -> None:
    args = parser().parse_args()
    if args.command == "plan":
        command_plan()
    elif args.command == "create":
        command_create(args)
    elif args.command == "discover":
        command_discover(args)
    elif args.command == "verify":
        command_verify(args)
    else:
        command_emit_secrets(args)


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(1)
