"""Process-local repository for tests, previews, and no-token development."""

from __future__ import annotations

from copy import deepcopy
from threading import RLock
from typing import Any


class InMemoryRepository:
    def __init__(self) -> None:
        self._strategies: dict[tuple[str, str, str], dict[str, Any]] = {}
        self._question_events: dict[tuple[str, str, str], dict[str, Any]] = {}
        self._question_set_submissions: dict[tuple[str, str, str], dict[str, Any]] = {}
        self._question_set_contacts: dict[tuple[str, str], dict[str, Any]] = {}
        self._coordination: dict[str, dict[str, Any]] = {}
        self._feedback: list[dict[str, Any]] = []
        self._protocol_lab_field_notes: dict[str, dict[str, Any]] = {}
        self._lock = RLock()

    def record_protocol_lab_field_note(
        self, note: dict[str, Any]
    ) -> dict[str, Any]:
        note_id = str(note["note_id"])
        with self._lock:
            self._protocol_lab_field_notes.setdefault(note_id, deepcopy(note))
            return deepcopy(self._protocol_lab_field_notes[note_id])

    def list_protocol_lab_field_notes(
        self, owner_key_hash: str | None = None
    ) -> list[dict[str, Any]]:
        with self._lock:
            rows = [
                deepcopy(note)
                for note in self._protocol_lab_field_notes.values()
                if owner_key_hash is None
                or note.get("owner_key_hash") == owner_key_hash
            ]
        return sorted(rows, key=lambda note: str(note.get("created_at", "")))

    @staticmethod
    def _question_event_key(event: dict[str, Any]) -> tuple[str, str, str]:
        return (
            str(event["participant_id"]),
            str(event["track_id"]),
            str(event["question_id"]),
        )

    def record_question_event(self, event: dict[str, Any]) -> dict[str, Any]:
        key = self._question_event_key(event)
        with self._lock:
            self._question_events.setdefault(key, deepcopy(event))
            return deepcopy(self._question_events[key])

    def list_question_events(
        self,
        track_id: str,
        participant_id: str | None = None,
    ) -> list[dict[str, Any]]:
        with self._lock:
            rows = [
                deepcopy(row)
                for row in self._question_events.values()
                if row.get("track_id") == track_id
                and (
                    participant_id is None
                    or row.get("participant_id") == participant_id
                )
            ]
        return sorted(rows, key=lambda row: str(row.get("timestamp", "")))

    @staticmethod
    def _submission_key(submission: dict[str, Any]) -> tuple[str, str, str]:
        return (
            str(submission["participant_uuid"]),
            str(submission["question_set_id"]),
            str(submission["version"]),
        )

    def record_question_set_submission(
        self, submission: dict[str, Any]
    ) -> dict[str, Any]:
        key = self._submission_key(submission)
        with self._lock:
            self._question_set_submissions.setdefault(key, deepcopy(submission))
            return deepcopy(self._question_set_submissions[key])

    def list_question_set_submissions(
        self, question_set_id: str
    ) -> list[dict[str, Any]]:
        with self._lock:
            rows = [
                deepcopy(row)
                for row in self._question_set_submissions.values()
                if row.get("question_set_id") == question_set_id
            ]
        return sorted(rows, key=lambda row: str(row.get("submitted_at", "")))

    @staticmethod
    def _question_set_contact_key(contact: dict[str, Any]) -> tuple[str, str]:
        return (
            str(contact["question_set_id"]),
            str(contact["participant_uuid"]),
        )

    def record_question_set_contact(
        self, contact: dict[str, Any]
    ) -> dict[str, Any]:
        key = self._question_set_contact_key(contact)
        with self._lock:
            existing = self._question_set_contacts.get(key, {})
            merged = {**existing, **deepcopy(contact)}
            self._question_set_contacts[key] = merged
            return deepcopy(merged)

    def get_question_set_contact(
        self,
        question_set_id: str,
        participant_uuid: str,
    ) -> dict[str, Any] | None:
        with self._lock:
            record = self._question_set_contacts.get(
                (question_set_id, participant_uuid)
            )
            return deepcopy(record) if record else None

    def list_question_set_contacts(
        self, question_set_id: str
    ) -> list[dict[str, Any]]:
        with self._lock:
            return [
                deepcopy(row)
                for (stored_question_set_id, _participant), row
                in self._question_set_contacts.items()
                if stored_question_set_id == question_set_id
            ]

    def record_question_feedback(self, feedback: dict[str, Any]) -> dict[str, Any]:
        with self._lock:
            self._feedback.append(deepcopy(feedback))
        return deepcopy(feedback)

    def list_question_feedback(self, session_code: str) -> list[dict[str, Any]]:
        with self._lock:
            rows = [
                deepcopy(row)
                for row in self._feedback
                if row.get("session_code") == session_code
            ]
        return sorted(rows, key=lambda row: str(row.get("created_at", "")))

    @staticmethod
    def _strategy_key(profile: dict[str, Any]) -> tuple[str, str, str]:
        return (
            str(profile["participant_uuid"]),
            str(profile["scenario_id"]),
            str(profile["protocol_version"]),
        )

    def integrate_strategic_profile(self, profile: dict[str, Any]) -> dict[str, Any]:
        """Create once; repeated clicks return the first integrated profile."""

        key = self._strategy_key(profile)
        with self._lock:
            self._strategies.setdefault(key, deepcopy(profile))
            return deepcopy(self._strategies[key])

    def list_strategic_profiles(self, session_code: str) -> list[dict[str, Any]]:
        with self._lock:
            rows = [
                deepcopy(row)
                for row in self._strategies.values()
                if row.get("session_code") == session_code
            ]
        return sorted(rows, key=lambda row: str(row.get("integrated_at", "")))

    def get_strategic_profile(
        self, participant_uuid: str, scenario_id: str, protocol_version: str
    ) -> dict[str, Any] | None:
        with self._lock:
            row = self._strategies.get((participant_uuid, scenario_id, protocol_version))
            return deepcopy(row) if row else None

    def record_coordination_interest(
        self,
        *,
        participant_uuid: str,
        session_code: str,
        email: str | None,
        consent_version: str,
        consented_at: str,
        name: str | None = None,
    ) -> dict[str, Any]:
        normalized_email = (email or "").strip() or None
        normalized_name = (name or "").strip() or None
        record = {
            "participant_uuid": participant_uuid,
            "session_code": session_code,
            "coordination_opt_in": True,
            "email": normalized_email,
            "name": normalized_name,
            "coordination_status": (
                "reachable_interest" if normalized_email else "anonymous_interest"
            ),
            "coordination_consent_version": consent_version,
            "coordination_consented_at": consented_at,
        }
        with self._lock:
            self._coordination[participant_uuid] = deepcopy(record)
        return record

    def get_coordination_interest(self, participant_uuid: str) -> dict[str, Any] | None:
        with self._lock:
            record = self._coordination.get(participant_uuid)
            return deepcopy(record) if record else None

    def list_coordination_interests(self, session_code: str) -> list[dict[str, Any]]:
        with self._lock:
            return [
                deepcopy(row)
                for row in self._coordination.values()
                if row.get("session_code") == session_code
            ]

    def delete_contact_data(self, participant_uuid: str) -> bool:
        with self._lock:
            return self._coordination.pop(participant_uuid, None) is not None
