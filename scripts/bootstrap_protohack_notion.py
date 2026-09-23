#!/usr/bin/env python3
"""Create or verify the Protocol Hack Notion database family.

The script is deliberately safe to rerun. It records every created database in
``config/protohack_notion.json`` before adding relations, so an interrupted run
can resume without producing duplicate databases.

Examples:
    python scripts/bootstrap_protohack_notion.py plan
    python scripts/bootstrap_protohack_notion.py create --parent-page-id PAGE_ID
    python scripts/bootstrap_protohack_notion.py verify
    python scripts/bootstrap_protohack_notion.py emit-secrets

Required for ``create`` and ``verify``:
    NOTION_TOKEN

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

from notion_client import Client
from notion_client.errors import APIResponseError


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MANIFEST = ROOT / "config" / "protohack_notion.json"
DEFAULT_NOTION_VERSION = "2025-09-03"
SCHEMA_VERSION = "protohack-notion-v4-probe-test-submissions"
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


RELATIONS: dict[str, dict[str, tuple[str, str]]] = {
    "players": {"session": ("sessions", "players")},
    "statements": {"session": ("sessions", "statements")},
    "responses": {
        "session": ("sessions", "responses"),
        "statement": ("statements", "responses"),
        "question": ("questions", "responses"),
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


def token_or_fail() -> str:
    from storage.context import notion_token

    token = notion_token()
    if not token:
        raise RuntimeError("NOTION_TOKEN is required for this command.")
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
    """Add v2 fields to an existing manifest without recreating databases.

    The only removed field is ``responses.player``. Anonymous strategy records
    use ``participant_uuid`` as an opaque bridge and never relate to the contact
    database directly.
    """

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
        if key == "responses" and "player" in actual:
            changes["player"] = None
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
        if key == "responses" and "player" in properties:
            errors.append("responses.player: prohibited direct contact relation")
    return errors


def emit_secrets(manifest: dict[str, Any]) -> str:
    databases = manifest["databases"]
    mapping = {
        "protohack_sessions_db_id": "sessions",
        "protohack_statements_db_id": "statements",
        "protohack_players_db_id": "players",
        "protohack_responses_db_id": "responses",
        "protohack_test_submissions_db_id": "test_submissions",
        "protohack_questions_db_id": "questions",
        "protohack_moderation_votes_db_id": "moderation_votes",
        "protohack_decisions_db_id": "decisions",
        "protohack_events_db_id": "events",
        "protohack_goals_db_id": "goals",
        "protohack_goal_trajectories_db_id": "goal_trajectories",
    }
    lines = ["[notion]", '# token = "secret_..."']
    lines.extend(
        f'{setting} = "{databases[key]["database_id"]}"'
        for setting, key in mapping.items()
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
    token = token_or_fail()
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


def command_verify(args: argparse.Namespace) -> None:
    manifest_path = Path(args.manifest).resolve()
    manifest = load_manifest(manifest_path)
    if not manifest:
        raise RuntimeError(f"Manifest not found: {manifest_path}")
    client = Client(
        auth=token_or_fail(),
        notion_version=os.getenv("NOTION_VERSION", DEFAULT_NOTION_VERSION),
    )
    errors = verify(client, manifest)
    if errors:
        raise RuntimeError("Verification failed:\n- " + "\n- ".join(errors))
    print(f"verified {len(DATABASES)} databases ({SCHEMA_VERSION})")


def command_emit_secrets(args: argparse.Namespace) -> None:
    manifest = load_manifest(Path(args.manifest).resolve())
    if not manifest:
        raise RuntimeError(f"Manifest not found: {args.manifest}")
    print(emit_secrets(manifest))


def parser() -> argparse.ArgumentParser:
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument(
        "command",
        choices=("plan", "create", "verify", "emit-secrets"),
    )
    cli.add_argument("--parent-page-id", default="")
    cli.add_argument("--manifest", default=str(DEFAULT_MANIFEST))
    return cli


def main() -> None:
    args = parser().parse_args()
    if args.command == "plan":
        command_plan()
    elif args.command == "create":
        command_create(args)
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
