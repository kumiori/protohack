"""Human-authored evidence that remains outside machine protocol state."""

from dataclasses import dataclass


@dataclass(frozen=True)
class Observation:
    observation_id: str
    replay_hash: str
    text: str
    evidence_event_ids: tuple[str, ...] = ()
    replay_position: int | None = None
    interpretation: str = ""
    provenance: str = "participant_observation"
