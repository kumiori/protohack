"""Canonical, portable trajectory-plan schema and YAML helpers."""

from __future__ import annotations

from datetime import date, datetime
from typing import Mapping, Sequence

import yaml

from trajectory_engine.geometry import (
    DIRECTIONAL_MODES,
    EVENT_TYPES,
    INFLUENCE_SCALES,
    LEGACY_INFLUENCE_SCALES,
    TOPOLOGY_MODES,
    UNCERTAINTY_STRENGTHS,
    directional_mode,
    geometry_for_influence,
    topology_mode,
    uncertainty_geometry,
)
from trajectory_engine.planning import REALIZATION_STATUSES


SCHEMA_VERSION = "trajectory-plan/v2"
LEGACY_SCHEMA_VERSIONS = {"", "trajectory-plan/v1"}
LOCAL_STORAGE_LATEST_KEY = "protocol-hack:trajectory-plan:latest:v1"
LOCAL_STORAGE_PREFIX = "protocol-hack:trajectory-plan:v1:"
DEFAULT_CAMERA: dict[str, object] = {
    "eye": {"x": 0.08, "y": 0.42, "z": -2.35},
    "center": {"x": 0.0, "y": 0.0, "z": 0.0},
    "up": {"x": 0.0, "y": 1.0, "z": 0.0},
}


def _serialisable(value: object) -> object:
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    if isinstance(value, Mapping):
        return {str(key): _serialisable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_serialisable(item) for item in value]
    return value


def build_trajectory_document(
    *,
    plan: Mapping[str, object],
    primitives: Sequence[Mapping[str, object]],
    uncertainty: Sequence[Mapping[str, object]],
    camera: Mapping[str, object] | None = None,
) -> dict[str, object]:
    """Return the canonical editable plan document."""

    return {
        "schema_version": SCHEMA_VERSION,
        "plan": _serialisable(dict(plan)),
        "primitives": _serialisable(
            [_normalise_primitive(item) for item in primitives]
        ),
        "uncertainty": _serialisable([dict(item) for item in uncertainty]),
        "view": {
            "camera": _serialisable(dict(camera or DEFAULT_CAMERA)),
        },
    }


def trajectory_yaml(document: Mapping[str, object]) -> str:
    """Encode a canonical trajectory document as readable YAML."""

    return yaml.safe_dump(
        _serialisable(dict(document)),
        sort_keys=False,
        allow_unicode=True,
        width=96,
    )


def _normalise_string_list(value: object) -> list[str]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        return []
    return [str(item).strip() for item in value if str(item).strip()]


def _normalise_branch_labels(
    value: object,
    *,
    move_id: str,
    topology: str,
) -> list[dict[str, str]]:
    if topology != "branching":
        return []
    labels: list[dict[str, str]] = []
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
        for index, item in enumerate(value[:2]):
            if isinstance(item, Mapping):
                label = str(item.get("label") or "").strip()
                branch_id = str(item.get("id") or "").strip()
            else:
                label = str(item).strip()
                branch_id = ""
            labels.append(
                {
                    "id": branch_id or f"{move_id}:{index + 1}",
                    "parent_id": move_id,
                    "label": label or f"Option {chr(65 + index)}",
                }
            )
    while len(labels) < 2:
        index = len(labels)
        labels.append(
            {
                "id": f"{move_id}:{index + 1}",
                "parent_id": move_id,
                "label": f"Option {chr(65 + index)}",
            }
        )
    return labels[:2]


def _normalise_primitive(source: Mapping[str, object]) -> dict[str, object]:
    primitive = dict(source)
    event_type = str(primitive.get("type") or "event")
    if event_type not in EVENT_TYPES:
        raise ValueError(f"Unknown primitive type: {event_type}")
    move_id = str(primitive.get("id") or "").strip()
    if not move_id:
        raise ValueError("Every primitive needs an ID.")
    influence = str(
        primitive.get("influence_scale")
        or LEGACY_INFLUENCE_SCALES.get(
            str(primitive.get("importance") or ""),
            "Structural",
        )
    ).title()
    if influence not in INFLUENCE_SCALES:
        influence = "Structural"
    geometry = geometry_for_influence(influence)
    direction = directional_mode(primitive)
    if direction not in DIRECTIONAL_MODES:
        direction = "gradually"
    topology = topology_mode(primitive)
    if topology not in TOPOLOGY_MODES:
        topology = "continuation"
    time_parameter = primitive.get("time_parameter")
    if time_parameter is None:
        time_parameter = primitive.get("temporal_position")
    if time_parameter is None:
        raise ValueError("Every primitive needs time_parameter.")
    created_at = str(primitive.get("created_at") or "").strip()
    modified_at = str(primitive.get("modified_at") or created_at).strip()
    if not created_at:
        created_at = datetime.now().astimezone().isoformat()
    if not modified_at:
        modified_at = created_at
    energy_effect = float(
        primitive["energy_effect"]
        if primitive.get("energy_effect") is not None
        else primitive["energy_offset"]
        if primitive.get("energy_offset") is not None
        else geometry["energy_offset"]
    )
    uncertainty_effect = float(
        primitive["uncertainty_effect"]
        if primitive.get("uncertainty_effect") is not None
        else primitive["entropy_effect"]
        if primitive.get("entropy_effect") is not None
        else primitive["alignment_offset"]
        if primitive.get("alignment_offset") is not None
        else 0.0
    )
    influence_radius = float(
        primitive["influence_radius"]
        if primitive.get("influence_radius") is not None
        else primitive["influence_width"]
        if primitive.get("influence_width") is not None
        else geometry["influence_width"]
    )
    date_value = str(
        primitive.get("date") or primitive.get("date_value") or ""
    )
    primitive.update(
        {
            "id": move_id,
            "type": event_type,
            "title": str(primitive.get("title") or EVENT_TYPES[event_type]["label"]),
            "time_parameter": min(
                1.0,
                max(0.0, float(time_parameter)),
            ),
            "temporal_position": min(1.0, max(0.0, float(time_parameter))),
            "date": date_value,
            "date_value": date_value,
            "time_basis": str(primitive.get("time_basis") or "relative"),
            "influence_scale": influence,
            "directional_mode": direction,
            "topology_mode": topology,
            "branch_parent": (
                str(primitive.get("branch_parent") or "").strip() or None
            ),
            "branch_labels": _normalise_branch_labels(
                primitive.get("branch_labels"),
                move_id=move_id,
                topology=topology,
            ),
            "energy_effect": energy_effect,
            "uncertainty_effect": uncertainty_effect,
            # Read/write aliases retained for trajectory-plan/v2 compatibility.
            "entropy_effect": uncertainty_effect,
            "influence_radius": influence_radius,
            # Runtime aliases remain in v2 so the stable trajectory engine can
            # render old and new plans through the same deterministic path.
            "energy_offset": energy_effect,
            "alignment_offset": uncertainty_effect,
            "influence_width": influence_radius,
            "interval_status": str(
                primitive.get("interval_status") or "active"
            ),
            "description": str(primitive.get("description") or ""),
            "intention": str(primitive.get("intention") or ""),
            "dependencies": _normalise_string_list(
                primitive.get("dependencies")
            ),
            "responsible_actors": _normalise_string_list(
                primitive.get("responsible_actors")
            ),
            "collaborators": _normalise_string_list(
                primitive.get("collaborators")
            ),
            "resources_needed": _normalise_string_list(
                primitive.get("resources_needed")
            ),
            "completion_evidence": _normalise_string_list(
                primitive.get("completion_evidence")
            ),
            "visibility": str(primitive.get("visibility") or "Private"),
            "tags": _normalise_string_list(primitive.get("tags")),
            "notes": str(primitive.get("notes") or ""),
            "created_at": created_at,
            "modified_at": modified_at,
            "status": (
                str(primitive.get("status") or "Planned")
                if str(primitive.get("status") or "Planned") in REALIZATION_STATUSES
                else "Planned"
            ),
            "actual_timestamp": (
                str(primitive.get("actual_timestamp"))
                if primitive.get("actual_timestamp")
                else None
            ),
            "actual_time_expression": str(primitive.get("actual_time_expression") or ""),
            "realization_note": str(primitive.get("realization_note") or ""),
            "trajectory_revision_needed": bool(primitive.get("trajectory_revision_needed", False)),
            "realization_history": list(primitive.get("realization_history") or []),
        }
    )
    return primitive


def _normalise_uncertainty(source: Mapping[str, object]) -> dict[str, object]:
    chunk = dict(source)
    strength = str(chunk.get("strength") or "Marked")
    if strength not in UNCERTAINTY_STRENGTHS:
        strength = "Marked"
    style = uncertainty_geometry(strength)
    start = min(0.98, max(0.0, float(chunk.get("start_parameter", 0.32))))
    end = min(1.0, max(start + 0.02, float(chunk.get("end_parameter", 0.56))))
    center = (start + end) / 2.0
    mode = str(chunk.get("profile_mode") or "balanced").lower()
    if mode not in {"balanced", "expands", "contracts"}:
        mode = "balanced"
    chunk.update(
        {
            "strength": strength,
            "start_parameter": start,
            "end_parameter": end,
            "center_parameter": center,
            "temporal_width": end - start,
            "profile_mode": mode,
            "radius": float(
                chunk["radius"]
                if chunk.get("radius") is not None
                else style["radius"]
            ),
            "opacity": float(
                chunk["opacity"]
                if chunk.get("opacity") is not None
                else style["opacity"]
            ),
        }
    )
    return chunk


def normalise_trajectory_document(
    source: Mapping[str, object],
) -> dict[str, object]:
    """Validate an import and apply migration-safe geometric defaults."""

    version = str(source.get("schema_version") or "")
    if version != SCHEMA_VERSION and version not in LEGACY_SCHEMA_VERSIONS:
        raise ValueError(
            f"Unsupported trajectory schema: {version or 'missing'}"
        )
    plan = source.get("plan")
    if not isinstance(plan, Mapping):
        raise ValueError("The trajectory YAML needs a plan object.")
    title = str(plan.get("title") or "").strip()
    goal = str(plan.get("goal_statement") or plan.get("destination_label") or "").strip()
    now = str(plan.get("initial_condition") or "").strip()
    if not title or not goal or not now:
        raise ValueError("Imported plans require identity, now and goal.")
    normalised_plan = dict(plan)
    normalised_plan.update(
        {
            "source_kind": "plan",
            "title": title,
            "initial_condition": now,
            "goal_statement": goal,
            "destination_label": goal,
            "guided_setup": True,
            "axis_y_label": "Uncertainty",
        }
    )
    primitives_source = source.get("primitives") or []
    uncertainty_source = source.get("uncertainty") or []
    if not isinstance(primitives_source, list) or not isinstance(
        uncertainty_source, list
    ):
        raise ValueError("Primitives and uncertainty must be YAML lists.")
    view = source.get("view")
    camera = (
        view.get("camera")
        if isinstance(view, Mapping) and isinstance(view.get("camera"), Mapping)
        else DEFAULT_CAMERA
    )
    return build_trajectory_document(
        plan=normalised_plan,
        primitives=[_normalise_primitive(item) for item in primitives_source],
        uncertainty=[_normalise_uncertainty(item) for item in uncertainty_source],
        camera=camera,
    )


def load_trajectory_yaml(source: str | bytes) -> dict[str, object]:
    """Decode, validate and migrate one YAML trajectory document."""

    loaded = yaml.safe_load(source)
    if not isinstance(loaded, Mapping):
        raise ValueError("The YAML root must be a trajectory object.")
    return normalise_trajectory_document(loaded)
