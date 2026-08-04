"""Participant-authored observations and privacy-safe notebook exports."""

from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
from typing import Any, Mapping

from protocol import access_key_hash, normalize_access_key, participant_alias

from .engine import Replay
from .models import ExperimentDefinition


@dataclass(frozen=True)
class FieldNote:
    note_id: str
    experiment_id: str
    experiment_version: str
    replay_hash: str
    owner_key_hash: str
    participant_alias: str
    observations: tuple[tuple[str, str], ...]
    challenged_rule_ids: tuple[str, ...]
    evidence_event_ids: tuple[str, ...]
    provenance: str
    created_at: str

    def as_record(self) -> dict[str, Any]:
        record = asdict(self)
        record["observations"] = dict(self.observations)
        record["challenged_rule_ids"] = list(self.challenged_rule_ids)
        record["evidence_event_ids"] = list(self.evidence_event_ids)
        return record


def build_field_note(
    *,
    experiment: ExperimentDefinition,
    session: Replay,
    access_key: str,
    observations: Mapping[str, str],
    challenged_rule_ids: tuple[str, ...] = (),
    created_at: str,
) -> FieldNote:
    canonical_key = normalize_access_key(access_key)
    if session.experiment_id != experiment.id:
        raise ValueError("Replay belongs to a different experiment.")
    normalized_observations = tuple(
        sorted(
            (str(key).strip(), str(value).strip())
            for key, value in observations.items()
            if str(key).strip() and str(value).strip()
        )
    )
    allowed_types = {prompt.note_type for prompt in experiment.field_note_prompts}
    unknown_types = sorted(
        note_type
        for note_type, _value in normalized_observations
        if note_type not in allowed_types
    )
    if unknown_types:
        raise ValueError(f"Unknown Field Note type: {', '.join(unknown_types)}")
    if not normalized_observations:
        raise ValueError("Add at least one Field Note before saving.")
    owner_hash = access_key_hash(canonical_key)
    identity = ":".join(
        (
            experiment.id,
            experiment.version,
            session.replay_hash,
            owner_hash,
        )
    )
    note_id = "field-note-" + hashlib.sha256(identity.encode("utf-8")).hexdigest()[:20]
    evidence = tuple(event.event_id for event in session.final_state.events)
    return FieldNote(
        note_id=note_id,
        experiment_id=experiment.id,
        experiment_version=experiment.version,
        replay_hash=session.replay_hash,
        owner_key_hash=owner_hash,
        participant_alias=participant_alias(canonical_key),
        observations=normalized_observations,
        challenged_rule_ids=tuple(sorted(set(challenged_rule_ids))),
        evidence_event_ids=evidence,
        provenance="participant_observation",
        created_at=str(created_at),
    )


def export_field_note(note: FieldNote) -> dict[str, Any]:
    """Return a notebook-safe projection with no access credential material."""

    return {
        "note_id": note.note_id,
        "experiment_id": note.experiment_id,
        "experiment_version": note.experiment_version,
        "replay_hash": note.replay_hash,
        "participant_alias": note.participant_alias,
        "observations": dict(note.observations),
        "challenged_rule_ids": list(note.challenged_rule_ids),
        "evidence_event_ids": list(note.evidence_event_ids),
        "provenance": note.provenance,
        "created_at": note.created_at,
    }
