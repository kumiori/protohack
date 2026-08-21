"""Shared-goal coordination records around unchanged trajectory documents."""

from __future__ import annotations

from datetime import datetime
from typing import Mapping, Sequence
from uuid import uuid4

import yaml

from trajectory_engine.schema import normalise_trajectory_document


BUNDLE_SCHEMA_VERSION = "trajectory-bundle/v2"
AGENT_TYPES = ("person", "team", "institution", "assistant")
CONTRIBUTION_STATUSES = ("draft", "shared", "withdrawn")
CONTRIBUTION_SOURCES = ("created_for_goal", "imported_existing_plan")
AGENT_COLOURS = ("#6ec5ff", "#ffad66", "#78d6a7", "#d7a6ff", "#f3df72")


def _now() -> str:
    return datetime.now().astimezone().isoformat()


def new_goal_id() -> str:
    return f"goal-{uuid4().hex[:10]}"


def new_trajectory_id() -> str:
    return f"trajectory-{uuid4().hex}"


def build_shared_goal(
    *,
    goal_id: str,
    title: str,
    objective: str = "",
    description: str = "",
    created_by_agent_id: str = "",
    created_at: str | None = None,
    status: str = "open",
) -> dict[str, str]:
    """Build one public shared objective; it never owns one merged path."""

    clean_id = goal_id.strip()
    clean_title = title.strip()
    clean_status = status.strip().lower()
    if not clean_id or not clean_title:
        raise ValueError("A shared goal needs an ID and title.")
    if clean_status not in {"open", "closed"}:
        raise ValueError("A shared goal status must be open or closed.")
    return {
        "goal_id": clean_id,
        "title": clean_title,
        "objective": (objective or description).strip(),
        "created_by_agent_id": created_by_agent_id.strip(),
        "created_at": created_at or _now(),
        "status": clean_status,
        "visibility": "public",
    }


def build_goal_trajectory(
    document: Mapping[str, object],
    *,
    goal_id: str,
    agent_id: str,
    agent_display_name: str,
    agent_type: str = "person",
    colour: str = "",
    trajectory_id: str = "",
    source: str = "created_for_goal",
    status: str = "shared",
    created_at: str | None = None,
    updated_at: str | None = None,
    revision: int = 1,
) -> dict[str, object]:
    """Wrap one canonical trajectory without adding fields to its schema."""

    clean_goal_id = goal_id.strip()
    clean_agent_id = agent_id.strip()
    clean_name = agent_display_name.strip()
    clean_type = agent_type.strip().lower()
    clean_source = source.strip().lower()
    clean_status = status.strip().lower()
    if not clean_goal_id or not clean_agent_id or not clean_name:
        raise ValueError("Goal ID, agent ID and display name are required.")
    if clean_type not in AGENT_TYPES:
        raise ValueError(f"Unknown agent type: {clean_type}")
    if clean_source not in CONTRIBUTION_SOURCES:
        raise ValueError(f"Unknown contribution source: {clean_source}")
    if clean_status not in CONTRIBUTION_STATUSES:
        raise ValueError(f"Unknown contribution status: {clean_status}")
    payload = normalise_trajectory_document(document)
    creation_time = created_at or _now()
    return {
        "trajectory_id": trajectory_id.strip() or new_trajectory_id(),
        "goal_id": clean_goal_id,
        "agent_id": clean_agent_id,
        "agent_display_name": clean_name,
        "agent_type": clean_type,
        "colour": colour.strip() or AGENT_COLOURS[0],
        "title": str(payload["plan"]["title"]),
        "schema_version": str(payload["schema_version"]),
        "trajectory_payload": payload,
        "created_at": creation_time,
        "updated_at": updated_at or creation_time,
        "status": clean_status,
        "source": clean_source,
        "revision": max(1, int(revision)),
    }


def revised_goal_trajectory(
    existing: Mapping[str, object],
    document: Mapping[str, object],
    *,
    agent_id: str,
    updated_at: str | None = None,
) -> dict[str, object]:
    """Replace a shared payload while preserving identity and authorship."""

    if str(existing.get("agent_id") or "") != agent_id.strip():
        raise ValueError("Only the contributing agent can update this trajectory.")
    return build_goal_trajectory(
        document,
        goal_id=str(existing["goal_id"]),
        agent_id=str(existing["agent_id"]),
        agent_display_name=str(existing["agent_display_name"]),
        agent_type=str(existing.get("agent_type") or "person"),
        colour=str(existing.get("colour") or ""),
        trajectory_id=str(existing["trajectory_id"]),
        source=str(existing.get("source") or "created_for_goal"),
        status=str(existing.get("status") or "shared"),
        created_at=str(existing["created_at"]),
        updated_at=updated_at or _now(),
        revision=int(existing.get("revision") or 1) + 1,
    )


def build_goal_bundle(
    *,
    goal: Mapping[str, object],
    trajectories: Sequence[Mapping[str, object]],
) -> dict[str, object]:
    """Build a portable snapshot without treating it as primary persistence."""

    clean_goal = build_shared_goal(
        goal_id=str(goal.get("goal_id") or ""),
        title=str(goal.get("title") or ""),
        objective=str(goal.get("objective") or goal.get("description") or ""),
        created_by_agent_id=str(goal.get("created_by_agent_id") or ""),
        created_at=str(goal.get("created_at") or "") or None,
        status=str(goal.get("status") or "open"),
    )
    contributions: list[dict[str, object]] = []
    seen_agents: set[str] = set()
    for source in trajectories:
        agent_id = str(source.get("agent_id") or "").strip()
        if agent_id in seen_agents:
            raise ValueError(f"Agent {agent_id!r} already has a trajectory in this goal.")
        seen_agents.add(agent_id)
        payload = source.get("trajectory_payload")
        if not isinstance(payload, Mapping):
            raise ValueError("Every contribution needs a canonical trajectory payload.")
        contributions.append(build_goal_trajectory(
            payload,
            goal_id=clean_goal["goal_id"],
            agent_id=agent_id,
            agent_display_name=str(source.get("agent_display_name") or agent_id),
            agent_type=str(source.get("agent_type") or "person"),
            colour=str(source.get("colour") or AGENT_COLOURS[len(contributions) % len(AGENT_COLOURS)]),
            trajectory_id=str(source.get("trajectory_id") or ""),
            source=str(source.get("source") or "created_for_goal"),
            status=str(source.get("status") or "shared"),
            created_at=str(source.get("created_at") or "") or None,
            updated_at=str(source.get("updated_at") or "") or None,
            revision=int(source.get("revision") or 1),
        ))
    return {"schema_version": BUNDLE_SCHEMA_VERSION, "goal": clean_goal, "trajectories": contributions}


def goal_bundle_yaml(bundle: Mapping[str, object]) -> str:
    return yaml.safe_dump(dict(bundle), sort_keys=False, allow_unicode=True, width=96)


def load_goal_bundle_yaml(source: str | bytes) -> dict[str, object]:
    loaded = yaml.safe_load(source)
    if not isinstance(loaded, Mapping) or loaded.get("schema_version") != BUNDLE_SCHEMA_VERSION:
        raise ValueError("Unsupported shared-goal bundle schema.")
    goal = loaded.get("goal")
    trajectories = loaded.get("trajectories")
    if not isinstance(goal, Mapping) or not isinstance(trajectories, list):
        raise ValueError("The bundle needs a goal and trajectory list.")
    return build_goal_bundle(goal=goal, trajectories=trajectories)
