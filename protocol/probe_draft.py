"""Portable, participant-scoped checkpoint drafts for canonical Probe trajectories."""

from __future__ import annotations

from typing import Any, Mapping

import yaml
from probe_engine import ProbeDefinition, ProbeRuntime, Trajectory, trajectory_from_dict


DRAFT_SCHEMA = "protocol-hack/probe-draft/v1"
STATE_SCHEMA = "protocol-hack/probe-state/v1"


def probe_state(probe: ProbeDefinition, trajectory: Trajectory) -> dict[str, Any]:
    """Wrap the one canonical trajectory used by both UI and submission."""

    return {
        "schema": STATE_SCHEMA,
        "probe": {"id": probe.id, "revision": probe.revision},
        "trajectory": trajectory.to_dict(),
    }


def dump_probe_state(probe: ProbeDefinition, trajectory: Trajectory) -> str:
    return yaml.safe_dump(
        probe_state(probe, trajectory),
        allow_unicode=True,
        sort_keys=False,
    )


def load_probe_state(
    value: str | Mapping[str, Any],
    *,
    probe: ProbeDefinition,
    participant_id: str = "",
    participation_id: str = "",
    expected_scope_id: str = "",
) -> Trajectory:
    """Validate and normalize an uploaded full or partial Probe trajectory."""

    payload = yaml.safe_load(value) if isinstance(value, str) else dict(value)
    if not isinstance(payload, Mapping):
        raise ValueError("Le fichier YAML ne contient pas un état Probe valide.")
    if payload.get("schema") == DRAFT_SCHEMA:
        trajectory = load_checkpoint_draft(payload, probe=probe)
    elif payload.get("schema") == STATE_SCHEMA:
        source = payload.get("probe")
        if not isinstance(source, Mapping) or source.get("id") != probe.id:
            raise ValueError("Le fichier appartient à une autre Probe.")
        revision = int(source.get("revision") or 0)
        raw_trajectory = payload.get("trajectory")
        if not isinstance(raw_trajectory, Mapping):
            raise ValueError("Le fichier ne contient pas de trajectoire canonique.")
        rebound = dict(raw_trajectory)
        participation = dict(rebound.get("participation") or {})
        question_ids = {
            str(event.get("question_id") or "")
            for event in (rebound.get("events") or ())
            if str(event.get("question_id") or "")
        }
        unknown = question_ids - {question.id for question in probe.questions}
        if unknown:
            raise ValueError(
                "Le fichier contient des questions incompatibles : "
                + ", ".join(sorted(unknown))
            )
        if revision != probe.revision:
            participation["probe_revision"] = probe.revision
        if participant_id:
            participation["participant_id"] = participant_id
        if participation_id:
            participation["id"] = participation_id
        rebound["participation"] = participation
        trajectory = trajectory_from_dict(rebound)
    else:
        raise ValueError("Schéma YAML de réponses non pris en charge.")

    participation = trajectory.participation
    if expected_scope_id and participation.scope_id != expected_scope_id:
        raise ValueError("Le fichier appartient à un autre événement.")
    if participant_id or participation_id:
        rebound = trajectory.to_dict()
        rebound_participation = dict(rebound.get("participation") or {})
        if participant_id:
            rebound_participation["participant_id"] = participant_id
        if participation_id:
            rebound_participation["id"] = participation_id
        rebound["participation"] = rebound_participation
        trajectory = trajectory_from_dict(rebound)
        participation = trajectory.participation
    scope_id = expected_scope_id or participation.scope_id
    runtime = ProbeRuntime.hydrate(
        probe,
        trajectory,
        participant_id=participant_id or participation.participant_id,
        scope_id=scope_id,
    )
    return runtime.trajectory


def inspect_probe_state(
    value: str | Mapping[str, Any], *, probe: ProbeDefinition
) -> dict[str, Any]:
    payload = yaml.safe_load(value) if isinstance(value, str) else dict(value)
    source = payload.get("probe") if isinstance(payload, Mapping) else {}
    source_revision = int((source or {}).get("revision") or 0)
    trajectory = load_probe_state(payload, probe=probe)
    counts = {"answered": 0, "skipped": 0, "flagged": 0}
    touched_questions: set[str] = set()
    checkpoint_sections: set[str] = set()
    for event in trajectory.events:
        kind = event.kind.value
        if kind in counts:
            counts[kind] += 1
        if event.question_id:
            touched_questions.add(event.question_id)
        if kind == "checkpoint" and event.metadata.get("section_id"):
            checkpoint_sections.add(str(event.metadata["section_id"]))
    sections = [
        section.title
        for section in probe.sections
        if section.id in checkpoint_sections
        or any(
            field_id in touched_questions
            for step_id in section.step_ids
            for field_id in probe.step(step_id).field_ids
        )
    ]
    return {
        "probe_id": probe.id,
        "revision": source_revision or probe.revision,
        "current_revision": probe.revision,
        "revision_compatible": True,
        "answers": counts["answered"],
        "skips": counts["skipped"],
        "flags": counts["flagged"],
        "sections": sections,
    }


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
