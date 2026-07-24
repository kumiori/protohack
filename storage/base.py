"""Small storage contract that keeps strategic and contact records separate."""

from __future__ import annotations

from typing import Any, Protocol


class Repository(Protocol):
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
