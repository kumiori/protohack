"""Small storage contract that keeps strategic and contact records separate."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol


@dataclass(frozen=True)
class RepositoryHealth:
    available: bool
    integration: str
    data_source_id: str
    status: str
    error_code: str = ""


class Repository(Protocol):
    def health_check(self) -> RepositoryHealth: ...

    def save_probe_trajectory(
        self, trajectory: dict[str, Any]
    ) -> dict[str, Any]: ...

    def get_probe_trajectory(
        self, participation_id: str
    ) -> dict[str, Any] | None: ...

    def list_probe_trajectories(
        self, event_id: str, probe_id: str
    ) -> list[dict[str, Any]]: ...

    def find_probe_trajectories_by_access_selector(
        self, access_code_selector: str
    ) -> list[dict[str, Any]]: ...

    def discard_probe_trajectories(
        self, event_id: str, probe_id: str, *, batch_id: str | None = None
    ) -> int: ...

    def create_shared_goal(self, goal: dict[str, Any]) -> dict[str, Any]: ...

    def list_shared_goals(self) -> list[dict[str, Any]]: ...

    def get_shared_goal(self, goal_id: str) -> dict[str, Any] | None: ...

    def record_goal_trajectory(
        self,
        trajectory: dict[str, Any],
        *,
        update_existing: bool = False,
    ) -> dict[str, Any]: ...

    def list_goal_trajectories(self, goal_id: str) -> list[dict[str, Any]]: ...

    def get_goal_trajectory(self, trajectory_id: str) -> dict[str, Any] | None: ...

    def record_protocol_lab_field_note(
        self, note: dict[str, Any]
    ) -> dict[str, Any]: ...

    def list_protocol_lab_field_notes(
        self, owner_key_hash: str | None = None
    ) -> list[dict[str, Any]]: ...

    def record_question_event(
        self, event: dict[str, Any]
    ) -> dict[str, Any]: ...

    def list_question_events(
        self,
        track_id: str,
        participant_id: str | None = None,
    ) -> list[dict[str, Any]]: ...

    def record_question_set_submission(
        self, submission: dict[str, Any]
    ) -> dict[str, Any]: ...

    def list_question_set_submissions(
        self, question_set_id: str
    ) -> list[dict[str, Any]]: ...

    def record_question_set_contact(
        self, contact: dict[str, Any]
    ) -> dict[str, Any]: ...

    def get_question_set_contact(
        self,
        question_set_id: str,
        participant_uuid: str,
    ) -> dict[str, Any] | None: ...

    def list_question_set_contacts(
        self, question_set_id: str
    ) -> list[dict[str, Any]]: ...

    def record_question_feedback(self, feedback: dict[str, Any]) -> dict[str, Any]: ...

    def list_question_feedback(self, session_code: str) -> list[dict[str, Any]]: ...

    def integrate_strategic_profile(self, profile: dict[str, Any]) -> dict[str, Any]: ...

    def list_strategic_profiles(self, session_code: str) -> list[dict[str, Any]]: ...

    def get_strategic_profile(
        self, participant_uuid: str, scenario_id: str, protocol_version: str
    ) -> dict[str, Any] | None: ...

    def record_coordination_interest(
        self,
        *,
        participant_uuid: str,
        session_code: str,
        email: str | None,
        consent_version: str,
        consented_at: str,
        name: str | None = None,
    ) -> dict[str, Any]: ...

    def get_coordination_interest(self, participant_uuid: str) -> dict[str, Any] | None: ...

    def list_coordination_interests(self, session_code: str) -> list[dict[str, Any]]: ...

    def delete_contact_data(self, participant_uuid: str) -> bool: ...
