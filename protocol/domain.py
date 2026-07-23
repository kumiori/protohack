"""Pure protocol operations shared by the app and tests."""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import re
from typing import Any

from .models import Protocol


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def normalize_rationale(value: str, *, max_length: int = 600) -> str:
    compact = re.sub(r"\s+", " ", value or "").strip()
    if not compact:
        raise ValueError("Please add one sentence about why you chose this move.")
    if len(compact) > max_length:
        raise ValueError(f"Please keep the rationale under {max_length} characters.")
    return compact


def participant_alias(participant_uuid: str) -> str:
    """Stable public alias that never exposes the participant UUID."""

    digest = hashlib.blake2s(participant_uuid.encode("utf-8"), digest_size=3).hexdigest()
    return f"P-{digest.upper()}"


def build_strategic_profile(
    *,
    protocol: Protocol,
    participant_uuid: str,
    action_id: str,
    rationale: str,
    rationale_skipped: bool = False,
    integrated_at: str | None = None,
) -> dict[str, Any]:
    action = protocol.scenario.decision.action(action_id)
    rationale = "" if rationale_skipped else normalize_rationale(rationale)
    return {
        "participant_uuid": participant_uuid,
        "participant_alias": participant_alias(participant_uuid),
        "session_code": protocol.session_code,
        "protocol_id": protocol.id,
        "protocol_version": protocol.version,
        "scenario_id": protocol.scenario.id,
        "decision_id": protocol.scenario.decision.id,
        "action_id": action.id,
        "action_label": action.label,
        "rationale": rationale,
        "rationale_skipped": bool(rationale_skipped),
        "semantic_tags": list(action.semantic_tags),
        "capacities": list(action.capacities),
        "resource_types": list(action.resource_types),
        "tagger_version": protocol.tagger_version,
        "privacy_version": protocol.privacy_version,
        "integration_status": "integrated",
        "revision": 1,
        "integrated_at": integrated_at or utc_now_iso(),
    }
