"""Integrity rules and participant-level projection for Probe submissions."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from typing import Any, Iterable


REQUIRED_INTEGRATED_FIELDS = (
    "event_id",
    "probe_id",
    "probe_revision",
    "submission_id",
    "integrated_at",
)


def canonical_submission_errors(row: dict[str, Any]) -> tuple[str, ...]:
    """Return precise reasons why a physical Response is not canonical."""

    errors: list[str] = []
    if str(row.get("record_type") or "") != "probe_submission":
        errors.append("record_type is not probe_submission")
    for field in REQUIRED_INTEGRATED_FIELDS:
        if row.get(field) in {None, ""}:
            errors.append(f"missing {field}")
    if str(row.get("state") or row.get("submission_state") or "") != "submitted":
        errors.append("submission_state is not submitted")
    if not str(row.get("player_page_id") or ""):
        errors.append("missing player relation")
    payload = row.get("payload")
    if not isinstance(payload, dict) or payload.get("schema") != "probe-submission/v1":
        errors.append("invalid canonical payload")
    trajectory = row.get("trajectory")
    if not isinstance(trajectory, dict) or not isinstance(trajectory.get("events"), list):
        errors.append("invalid trajectory")
    return tuple(errors)


def assert_integrated_submission(row: dict[str, Any], *, require_player: bool = True) -> None:
    """Fail loudly before a malformed integrated submission reaches storage."""

    candidate = dict(row)
    if not require_player:
        candidate.setdefault("player_page_id", "pending-player-upsert")
    errors = canonical_submission_errors(candidate)
    if errors:
        raise ValueError("Invalid integrated Probe submission: " + "; ".join(errors))


def _identity(row: dict[str, Any]) -> str:
    return str(row.get("player_page_id") or row.get("participant_id") or "")


@dataclass(frozen=True)
class ProbeResultsAudit:
    counts: dict[str, Any]
    included: tuple[dict[str, Any], ...]
    excluded: tuple[dict[str, Any], ...]
    trajectories: tuple[dict[str, Any], ...]


def audit_probe_submissions(
    rows: Iterable[dict[str, Any]], *, event_id: str, probe_id: str
) -> ProbeResultsAudit:
    """Audit physical rows and select the latest valid submission per person."""

    physical = [dict(row) for row in rows]
    record_types = Counter(str(row.get("record_type") or "missing") for row in physical)
    events = Counter(str(row.get("event_id") or "missing") for row in physical)
    probes = Counter(str(row.get("probe_id") or "missing") for row in physical)
    states = Counter(
        str(row.get("state") or row.get("submission_state") or "missing")
        for row in physical
    )
    valid: list[dict[str, Any]] = []
    excluded: list[dict[str, Any]] = []
    for row in physical:
        reasons = list(canonical_submission_errors(row))
        if str(row.get("event_id") or "") != event_id:
            reasons.append("different event_id")
        if str(row.get("probe_id") or "") != probe_id:
            reasons.append("different probe_id")
        if reasons:
            excluded.append({**row, "exclusion_reasons": tuple(dict.fromkeys(reasons))})
        else:
            valid.append(row)

    latest: dict[str, dict[str, Any]] = {}
    superseded: list[dict[str, Any]] = []
    for row in sorted(
        valid,
        key=lambda item: (
            str(item.get("integrated_at") or ""),
            int(item.get("revision") or 0),
            str(item.get("submission_id") or ""),
        ),
    ):
        identity = _identity(row)
        previous = latest.get(identity)
        if previous is not None:
            superseded.append(
                {**previous, "exclusion_reasons": ("superseded by later submission",)}
            )
        latest[identity] = row

    included = tuple(latest.values())
    excluded.extend(superseded)
    counts = {
        "physical_rows": len(physical),
        "by_record_type": dict(record_types),
        "by_event_id": dict(events),
        "by_probe_id": dict(probes),
        "by_submission_state": dict(states),
        "valid_canonical_envelopes": len(valid),
        "distinct_submission_ids": len(
            {str(row.get("submission_id")) for row in valid}
        ),
        "distinct_participants": len({_identity(row) for row in valid}),
        "latest_submissions": len(included),
        "trajectories_used": len(included),
    }
    return ProbeResultsAudit(
        counts=counts,
        included=included,
        excluded=tuple(excluded),
        trajectories=tuple(dict(row["trajectory"]) for row in included),
    )
