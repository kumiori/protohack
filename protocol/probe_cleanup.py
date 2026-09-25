"""Safe, explicit cleanup planning for Probe prelaunch data."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable


@dataclass(frozen=True)
class ProbeCleanupPlan:
    event_id: str
    probe_id: str
    cutoff: str
    responses: tuple[dict[str, Any], ...]
    player_page_ids: tuple[str, ...]
    legacy_candidates: tuple[dict[str, Any], ...]

    def responses_export(self) -> dict[str, Any]:
        return {
            "schema": "probe-cleanup-export/v1",
            "kind": "Responses",
            "scope": {"event_id": self.event_id, "probe_id": self.probe_id, "before": self.cutoff},
            "records": list(self.responses),
        }


def plan_probe_cleanup(
    rows: Iterable[dict[str, Any]], *, event_id: str, probe_id: str, cutoff: str
) -> ProbeCleanupPlan:
    """Select only explicit test/prelaunch rows; report legacy rows separately."""

    physical = [dict(row) for row in rows]
    matched = tuple(
        row
        for row in physical
        if str(row.get("event_id") or "") == event_id
        and str(row.get("probe_id") or "") == probe_id
        and str(row.get("environment") or "") in {"test", "prelaunch"}
        and bool(row.get("created_at"))
        and str(row["created_at"]) < cutoff
        and bool(row.get("_page_id"))
    )
    matched_ids = {str(row["_page_id"]) for row in matched}
    linked: dict[str, set[str]] = {}
    for row in physical:
        player = str(row.get("player_page_id") or "")
        page_id = str(row.get("_page_id") or "")
        if player and page_id:
            linked.setdefault(player, set()).add(page_id)
    safe_players = tuple(
        sorted(
            player
            for player in {str(row.get("player_page_id") or "") for row in matched}
            if player and linked.get(player, set()) <= matched_ids
        )
    )
    legacy = tuple(
        row
        for row in physical
        if str(row.get("created_at") or "") < cutoff
        and (
            not row.get("event_id")
            or not row.get("probe_id")
            or not row.get("environment")
        )
        and (
            str(row.get("probe_id") or "") == probe_id
            or probe_id in str(row.get("name") or "")
            or str((row.get("payload") or {}).get("probe", {}).get("id") or "") == probe_id
        )
    )
    return ProbeCleanupPlan(
        event_id=event_id,
        probe_id=probe_id,
        cutoff=cutoff,
        responses=matched,
        player_page_ids=safe_players,
        legacy_candidates=legacy,
    )
