"""Probe Engine trajectory persistence over the application repository."""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, timezone
from time import perf_counter
from typing import Any

from probe_engine import ProbeDefinition, ProbeRuntime, Trajectory, trajectory_from_dict

from storage.base import Repository


class ProbeRepositoryStore:
    def __init__(
        self,
        repository: Repository,
        *,
        probe_id: str,
        participant_id: str,
        scope_id: str,
        probe: ProbeDefinition | None = None,
        diagnostic_sink: Callable[[dict[str, Any]], None] | None = None,
        target: str = "probe trajectories",
    ) -> None:
        self.repository = repository
        self.probe_id = probe_id
        self.participant_id = participant_id
        self.scope_id = scope_id
        self.probe = probe
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
            "draft.hydrate",
            participation_id,
            lambda: self.repository.get_probe_trajectory(participation_id),
        )
        if record is None:
            return None
        return trajectory_from_dict(record["trajectory"])

    def checkpoint(self, trajectory: Trajectory) -> Trajectory:
        operation = (
            "sync.arrival"
            if trajectory.events and trajectory.events[-1].kind.value == "sync_point_reached"
            else "draft.session.save"
        )
        self._communicate(
            operation,
            trajectory.participation.id,
            lambda: self.repository.save_probe_trajectory(
                self._record(trajectory, integrated=False)
            ),
            event_count=len(trajectory.events),
        )
        return trajectory

    def observe(self, operation: str, trajectory: Trajectory) -> None:
        """Record a non-persistence boundary operation for developer diagnostics."""
        self._communicate(
            operation,
            trajectory.participation.id,
            lambda: None,
            event_count=len(trajectory.events),
        )

    def integrate(
        self,
        trajectory: Trajectory,
        *,
        idempotency_key: str,
    ) -> Trajectory:
        payload = self.submission_payload(
            trajectory,
            integrated=True,
            idempotency_key=idempotency_key,
        )
        self._communicate(
            "submission.commit",
            trajectory.participation.id,
            lambda: self.repository.save_probe_trajectory(payload),
            event_count=len(trajectory.events),
        )
        return trajectory

    def preview_payload(
        self,
        trajectory: Trajectory,
        *,
        idempotency_key: str,
    ) -> dict[str, Any]:
        """Build and report the exact final payload without performing a write."""
        return self._communicate(
            "submission.preview",
            trajectory.participation.id,
            lambda: self.submission_payload(
                trajectory,
                integrated=True,
                idempotency_key=idempotency_key,
            ),
            event_count=len(trajectory.events),
        )

    def submission_payload(
        self,
        trajectory: Trajectory,
        *,
        integrated: bool,
        idempotency_key: str = "",
    ) -> dict[str, Any]:
        """Build the exact canonical record passed to the repository adapter."""
        return self._record(
            trajectory,
            integrated=integrated,
            idempotency_key=idempotency_key,
        )

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
        record = {
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
        if self.probe is not None:
            reviewed = ProbeRuntime.hydrate(
                self.probe,
                trajectory,
                participant_id=self.participant_id,
                scope_id=self.scope_id,
            ).review()
            answers = {
                item.question_id: item.value
                for item in reviewed
                if item.value is not None and item.state.startswith("answered")
            }
            record["identity"] = {
                field_id: answers[field_id]
                for field_id in self.probe.authoring.profile_fields
                if field_id in answers
            }
            record["responses"] = {
                field_id: answers[field_id]
                for field_id in self.probe.authoring.session_fields
                if field_id in answers
            }
        return record
