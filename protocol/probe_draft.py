"""Portable, participant-scoped checkpoint drafts for canonical Probe trajectories."""

from __future__ import annotations

from typing import Any, Mapping

import yaml
from probe_engine import ProbeDefinition, Trajectory, trajectory_from_dict


DRAFT_SCHEMA = "protocol-hack/probe-draft/v1"


def checkpoint_draft(
    probe: ProbeDefinition,
    trajectory: Trajectory,
    *,
    section_id: str,
) -> dict[str, Any]:
    checkpoint = next(
        (
            event
            for event in reversed(trajectory.events)
            if event.kind.value == "checkpoint"
            and event.metadata.get("section_id") == section_id
        ),
        None,
    )
    if checkpoint is None:
        raise ValueError(f"Section `{section_id}` has not been checkpointed.")
    participation = trajectory.participation

    def disposition(event: Any, sequence: int) -> dict[str, Any]:
        value = {
            "sequence": sequence,
            "id": event.id,
            "question_id": event.question_id,
            "question_revision": event.question_revision,
            "created_at": event.timestamp,
        }
        if event.kind.value == "answered":
            value["value"] = event.value
        else:
            value.update(
                {
                    "reason_codes": list(event.reason_codes),
                    "note": event.reason_note,
                }
            )
        return value

    indexed = list(enumerate(trajectory.events))
    return {
        "schema": DRAFT_SCHEMA,
        "probe": {"id": probe.id, "revision": probe.revision},
        "participation": {
            "id": participation.id,
            "participant_id": participation.participant_id,
            "scope_id": participation.scope_id,
        },
        "checkpoint": {
            "id": checkpoint.id,
            "section": section_id,
            "created_at": checkpoint.timestamp,
            "sequence": next(
                index for index, event in indexed if event.id == checkpoint.id
            ),
        },
        "answers": [
            disposition(event, index)
            for index, event in indexed
            if event.kind.value == "answered"
        ],
        "skips": [
            disposition(event, index)
            for index, event in indexed
            if event.kind.value == "skipped"
        ],
        "flags": [
            disposition(event, index)
            for index, event in indexed
            if event.kind.value == "flagged"
        ],
    }


def dump_checkpoint_draft(
    probe: ProbeDefinition,
    trajectory: Trajectory,
    *,
    section_id: str,
) -> str:
    return yaml.safe_dump(
        checkpoint_draft(probe, trajectory, section_id=section_id),
        allow_unicode=True,
        sort_keys=False,
    )


def load_checkpoint_draft(
    value: str | Mapping[str, Any],
    *,
    probe: ProbeDefinition,
) -> Trajectory:
    payload = yaml.safe_load(value) if isinstance(value, str) else dict(value)
    if not isinstance(payload, Mapping) or payload.get("schema") != DRAFT_SCHEMA:
        raise ValueError("Unsupported Probe draft schema.")
    source = payload.get("probe")
    if not isinstance(source, Mapping) or source.get("id") != probe.id:
        raise ValueError("Draft belongs to a different Probe.")
    revision = int(source.get("revision") or 0)
    if revision != probe.revision:
        raise ValueError(
            f"Draft Probe revision {revision} cannot be loaded as revision {probe.revision}; "
            "an explicit migration is required."
        )
    participation = payload.get("participation") or {}
    checkpoint = payload.get("checkpoint") or {}
    events: list[tuple[int, dict[str, Any]]] = []
    for key, kind in (("answers", "answered"), ("skips", "skipped"), ("flags", "flagged")):
        for item in payload.get(key) or ():
            event = {
                "id": str(item.get("id") or ""),
                "kind": kind,
                "timestamp": str(item.get("created_at") or ""),
                "question_id": str(item.get("question_id") or ""),
                "question_revision": item.get("question_revision"),
                "value": item.get("value") if kind == "answered" else None,
                "reason": str(item.get("note") or ""),
                "reason_codes": list(item.get("reason_codes") or ()),
                "reason_note": str(item.get("note") or ""),
                "legacy_reason_codes": [],
                "metadata": {},
            }
            events.append((int(item.get("sequence") or 0), event))
    events.append(
        (
            int(checkpoint.get("sequence") or len(events)),
            {
                "id": str(checkpoint.get("id") or ""),
                "kind": "checkpoint",
                "timestamp": str(checkpoint.get("created_at") or ""),
                "question_id": "",
                "question_revision": None,
                "value": None,
                "reason": "",
                "reason_codes": [],
                "reason_note": "",
                "legacy_reason_codes": [],
                "metadata": {"section_id": str(checkpoint.get("section") or "")},
            },
        )
    )
    trajectory = trajectory_from_dict(
        {
            "schema": "probe-trajectory/v1",
            "participation": {
                "id": str(participation.get("id") or ""),
                "participant_id": str(participation.get("participant_id") or ""),
                "probe_id": probe.id,
                "probe_revision": revision,
                "scope_id": str(participation.get("scope_id") or ""),
            },
            "events": [event for _, event in sorted(events, key=lambda row: row[0])],
        }
    )
    if trajectory.participation.probe_revision != probe.revision:
        raise ValueError("Draft trajectory revision does not match its Probe metadata.")
    return trajectory
