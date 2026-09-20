"""Probe Engine trajectory persistence over the application repository."""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, timezone
from time import perf_counter
from typing import Any

from probe_engine import Trajectory, trajectory_from_dict

from storage.base import Repository


class ProbeRepositoryStore:
    def __init__(
        self,
        repository: Repository,
        *,
        probe_id: str,
        participant_id: str,
        scope_id: str,
        diagnostic_sink: Callable[[dict[str, Any]], None] | None = None,
        target: str = "probe trajectories",
    ) -> None:
        self.repository = repository
        self.probe_id = probe_id
        self.participant_id = participant_id
        self.scope_id = scope_id
        self.diagnostic_sink = diagnostic_sink
        self.target = target

    def _communicate(
        self,
        operation: str,
        identity: str,
        callback: Callable[[], Any],
        *,
        event_count: int | None = None,
    ) -> Any:
        started = perf_counter()
        diagnostic = {
            "operation": operation,
            "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "target": self.target,
            "record_identity": identity,
            "success": False,
        }
        if event_count is not None:
            diagnostic["trajectory_event_count"] = event_count
        try:
            result = callback()
            diagnostic["success"] = True
            diagnostic["items_affected"] = 0 if result is None else 1
            return result
        except Exception as exc:
            diagnostic["error"] = type(exc).__name__
            raise
        finally:
            diagnostic["duration_ms"] = round((perf_counter() - started) * 1000, 2)
            if self.diagnostic_sink:
                self.diagnostic_sink(diagnostic)

    def load(self, participation_id: str) -> Trajectory | None:
        record = self._communicate(
            "load",
            participation_id,
            lambda: self.repository.get_probe_trajectory(participation_id),
        )
        if record is None:
            return None
        return trajectory_from_dict(record["trajectory"])

    def checkpoint(self, trajectory: Trajectory) -> Trajectory:
        self._communicate(
            "upsert",
            trajectory.participation.id,
            lambda: self.repository.save_probe_trajectory(
                self._record(trajectory, integrated=False)
            ),
            event_count=len(trajectory.events),
        )
        return trajectory

    def integrate(
        self,
        trajectory: Trajectory,
        *,
        idempotency_key: str,
    ) -> Trajectory:
        self._communicate(
            "integrate",
            trajectory.participation.id,
            lambda: self.repository.save_probe_trajectory(
                self._record(
                    trajectory,
                    integrated=True,
                    idempotency_key=idempotency_key,
                )
            ),
            event_count=len(trajectory.events),
        )
        return trajectory

    def _record(
        self,
        trajectory: Trajectory,
        *,
        integrated: bool,
        idempotency_key: str = "",
    ) -> dict[str, Any]:
        participation = trajectory.participation
        if (
            participation.probe_id != self.probe_id
            or participation.participant_id != self.participant_id
            or participation.scope_id != self.scope_id
        ):
            raise ValueError("Probe trajectory identity does not match its repository store.")
        return {
            "record_type": "probe_trajectory",
            "participation_id": participation.id,
            "participant_id": participation.participant_id,
            "probe_id": participation.probe_id,
            "probe_revision": participation.probe_revision,
            "scope_id": participation.scope_id,
            "integrated": integrated,
            "idempotency_key": idempotency_key,
            "trajectory": trajectory.to_dict(),
        }
