"""Notion-backed repository using the protohack database family."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Iterable

from notion_client import Client


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MANIFEST = ROOT / "config" / "protohack_notion.json"
DEFAULT_NOTION_VERSION = "2025-09-03"


def _text(content: str) -> list[dict[str, Any]]:
    value = str(content)
    chunks = [value[index : index + 2000] for index in range(0, len(value), 2000)]
    return [
        {"type": "text", "text": {"content": chunk}}
        for chunk in (chunks or [""])
    ]


def _rich(properties: dict[str, Any], name: str) -> str:
    values = (properties.get(name) or {}).get("rich_text") or []
    return "".join(str(value.get("plain_text") or "") for value in values)


def _email(properties: dict[str, Any], name: str = "email") -> str | None:
    value = (properties.get(name) or {}).get("email")
    return str(value).strip() if value else None


def _select(properties: dict[str, Any], name: str) -> str:
    value = (properties.get(name) or {}).get("select") or {}
    return str(value.get("name") or "")


def _date(properties: dict[str, Any], name: str) -> str:
    value = (properties.get(name) or {}).get("date") or {}
    return str(value.get("start") or "")


def _relation(page_id: str) -> dict[str, Any]:
    return {"relation": [{"id": page_id}]}


class NotionRepository:
    def __init__(
        self,
        *,
        token: str,
        manifest_path: str | Path = DEFAULT_MANIFEST,
        notion_version: str = DEFAULT_NOTION_VERSION,
    ) -> None:
        manifest = json.loads(Path(manifest_path).read_text(encoding="utf-8"))
        databases = manifest["databases"]
        self._sources = {
            key: str(value["data_source_id"]) for key, value in databases.items()
        }
        self._session_page_id = str(manifest["seed_session"]["page_id"])
        self._client = Client(auth=token, notion_version=notion_version)

    @staticmethod
    def _protocol_lab_field_note_from_page(
        page: dict[str, Any],
    ) -> dict[str, Any]:
        properties = page.get("properties") or {}
        raw = _rich(properties, "metadata_json")
        try:
            note = json.loads(raw) if raw else {}
        except json.JSONDecodeError:
            note = {}
        note.setdefault("note_id", _rich(properties, "item_id"))
        note.setdefault("experiment_id", _rich(properties, "page"))
        note.setdefault("owner_key_hash", _rich(properties, "device_id"))
        note.setdefault("created_at", _date(properties, "timestamp"))
        note["_page_id"] = str(page.get("id") or "")
        return note

    def record_protocol_lab_field_note(
        self, note: dict[str, Any]
    ) -> dict[str, Any]:
        existing = next(
            (
                row
                for row in self.list_protocol_lab_field_notes(
                    str(note["owner_key_hash"])
                )
                if row.get("note_id") == note.get("note_id")
            ),
            None,
        )
        if existing:
            return existing
        metadata_json = json.dumps(note, ensure_ascii=False, separators=(",", ":"))
        created = self._client.pages.create(
            parent={
                "type": "data_source_id",
                "data_source_id": self._sources["events"],
            },
            properties={
                "Name": {
                    "title": _text(
                        f"Field note {note['participant_alias']} · "
                        f"{str(note['note_id'])[-8:]}"
                    )
                },
                "session": _relation(self._session_page_id),
                "timestamp": {"date": {"start": str(note["created_at"])}},
                "event_type": {"select": {"name": "protocol_lab_field_note"}},
                "item_id": {"rich_text": _text(str(note["note_id"]))},
                "page": {"rich_text": _text(str(note["experiment_id"]))},
                "value_label": {
                    "rich_text": _text(str(note["participant_alias"]))
                },
                "metadata_json": {"rich_text": _text(metadata_json)},
                "device_id": {
                    "rich_text": _text(str(note["owner_key_hash"]))
                },
                "status": {"select": {"name": "saved"}},
            },
        )
        result = dict(note)
        result["_page_id"] = str(created["id"])
        return result

    def list_protocol_lab_field_notes(
        self, owner_key_hash: str | None = None
    ) -> list[dict[str, Any]]:
        clauses: list[dict[str, Any]] = [
            {
                "property": "event_type",
                "select": {"equals": "protocol_lab_field_note"},
            }
        ]
        if owner_key_hash is not None:
            clauses.append(
                {
                    "property": "device_id",
                    "rich_text": {"equals": owner_key_hash},
                }
            )
        pages = self._query_all(
            "events",
            filter_={"and": clauses},
        )
        notes = [
            self._protocol_lab_field_note_from_page(page)
            for page in pages
            if _select(page.get("properties") or {}, "event_type")
            == "protocol_lab_field_note"
            and (
                owner_key_hash is None
                or _rich(page.get("properties") or {}, "device_id")
                == owner_key_hash
            )
        ]
        return sorted(notes, key=lambda note: str(note.get("created_at", "")))

    @staticmethod
    def _question_set_submission_from_page(
        page: dict[str, Any],
    ) -> dict[str, Any]:
        properties = page.get("properties") or {}
        raw = _rich(properties, "value_json")
        try:
            submission = json.loads(raw) if raw else {}
        except json.JSONDecodeError:
            submission = {}
        submission["_page_id"] = str(page.get("id") or "")
        return submission

    def record_question_set_submission(
        self, submission: dict[str, Any]
    ) -> dict[str, Any]:
        participant_uuid = str(submission["participant_uuid"])
        question_set_id = str(submission["question_set_id"])
        version = str(submission["version"])
        pages = self._query_all(
            "responses",
            filter_={
                "and": [
                    {
                        "property": "participant_uuid",
                        "rich_text": {"equals": participant_uuid},
                    },
                    {
                        "property": "text_id",
                        "rich_text": {"equals": question_set_id},
                    },
                    {
                        "property": "protocol_version",
                        "rich_text": {"equals": version},
                    },
                ]
            },
        )
        existing = next(
            (
                page
                for page in pages
                if _rich(page.get("properties") or {}, "text_id")
                == question_set_id
                and _rich(page.get("properties") or {}, "participant_uuid")
                == participant_uuid
            ),
            None,
        )
        if existing:
            return self._question_set_submission_from_page(existing)

        submission_json = json.dumps(
            submission,
            ensure_ascii=False,
            separators=(",", ":"),
        )
        created = self._client.pages.create(
            parent={
                "type": "data_source_id",
                "data_source_id": self._sources["responses"],
            },
            properties={
                "Name": {
                    "title": _text(
                        f"{question_set_id} {submission['participant_alias']}"
                    )
                },
                "session": _relation(self._session_page_id),
                "participant_uuid": {"rich_text": _text(participant_uuid)},
                "question_id": {"rich_text": _text(question_set_id)},
                "item_id": {
                    "rich_text": _text(str(submission["submission_id"]))
                },
                "response_value": {"rich_text": _text(question_set_id)},
                "value_label": {
                    "rich_text": _text(
                        f"{len(submission.get('responses') or [])} responses"
                    )
                },
                "value_json": {"rich_text": _text(submission_json)},
                "question_type": {"select": {"name": "other"}},
                "text_id": {"rich_text": _text(question_set_id)},
                "device_id": {"rich_text": _text(participant_uuid)},
                "submitted_at": {
                    "date": {"start": str(submission["submitted_at"])}
                },
                "created_at": {
                    "date": {"start": str(submission["submitted_at"])}
                },
                "protocol_version": {"rich_text": _text(version)},
                "revision": {"number": 1},
            },
        )
        result = dict(submission)
        result["_page_id"] = str(created["id"])
        return result

    def list_question_set_submissions(
        self, question_set_id: str
    ) -> list[dict[str, Any]]:
        pages = self._query_all(
            "responses",
            filter_={
                "property": "text_id",
                "rich_text": {"equals": question_set_id},
            },
        )
        submissions = [
            self._question_set_submission_from_page(page)
            for page in pages
            if _rich(page.get("properties") or {}, "text_id") == question_set_id
            and _rich(page.get("properties") or {}, "value_json")
        ]
        return sorted(
            submissions,
            key=lambda row: str(row.get("submitted_at", "")),
        )

    @staticmethod
    def _question_set_contact_from_page(
        page: dict[str, Any],
    ) -> dict[str, Any]:
        properties = page.get("properties") or {}
        return {
            "record_type": "question_set_contact",
            "question_set_id": _rich(
                properties, "coordination_consent_version"
            ),
            "participant_uuid": _rich(properties, "participant_uuid"),
            "access_key": _rich(properties, "participant_uuid"),
            "name": _rich(properties, "nickname") or None,
            "email": _email(properties),
            "communication_consent": bool(
                (properties.get("coordination_opt_in") or {}).get("checkbox")
            ),
            "updated_at": _date(properties, "coordination_consented_at"),
            "_page_id": str(page.get("id") or ""),
        }

    def _question_set_contact_page(
        self,
        question_set_id: str,
        participant_uuid: str,
    ) -> dict[str, Any] | None:
        pages = self._query_all(
            "players",
            filter_={
                "and": [
                    {
                        "property": "participant_uuid",
                        "rich_text": {"equals": participant_uuid},
                    },
                    {
                        "property": "coordination_consent_version",
                        "rich_text": {"equals": question_set_id},
                    },
                ]
            },
        )
        return next(
            (
                page
                for page in pages
                if _rich(page.get("properties") or {}, "participant_uuid")
                == participant_uuid
                and _rich(
                    page.get("properties") or {},
                    "coordination_consent_version",
                )
                == question_set_id
            ),
            None,
        )

    def get_question_set_contact(
        self,
        question_set_id: str,
        participant_uuid: str,
    ) -> dict[str, Any] | None:
        page = self._question_set_contact_page(
            question_set_id,
            participant_uuid,
        )
        return self._question_set_contact_from_page(page) if page else None

    def record_question_set_contact(
        self, contact: dict[str, Any]
    ) -> dict[str, Any]:
        question_set_id = str(contact["question_set_id"])
        participant_uuid = str(contact["participant_uuid"])
        existing_page = self._question_set_contact_page(
            question_set_id,
            participant_uuid,
        )
        existing = (
            self._question_set_contact_from_page(existing_page)
            if existing_page
            else {}
        )
        merged = {**existing, **contact}
        normalized_name = str(merged.get("name") or "").strip()
        normalized_email = str(merged.get("email") or "").strip()
        consent = merged.get("communication_consent") is True
        updated_at = str(merged.get("updated_at") or "")
        properties: dict[str, Any] = {
            "Name": {
                "title": _text(
                    f"{question_set_id} contact {participant_uuid[:8]}"
                )
            },
            "session": _relation(self._session_page_id),
            "participant_uuid": {"rich_text": _text(participant_uuid)},
            "access_key": {"rich_text": _text(participant_uuid)},
            "nickname": {"rich_text": _text(normalized_name)},
            "email": {"email": normalized_email or None},
            "coordination_opt_in": {"checkbox": consent},
            "coordination_status": {
                "select": {
                    "name": (
                        "reachable_interest"
                        if consent and normalized_email
                        else "anonymous_interest"
                    )
                }
            },
            "coordination_consent_version": {
                "rich_text": _text(question_set_id)
            },
            "role": {"select": {"name": "participant"}},
            "status": {"select": {"name": "active"}},
            "consented": {"checkbox": consent},
        }
        if updated_at:
            properties["coordination_consented_at"] = {
                "date": {"start": updated_at}
            }

        if existing_page:
            page = self._client.pages.update(
                page_id=str(existing_page["id"]),
                properties=properties,
            )
        else:
            page = self._client.pages.create(
                parent={
                    "type": "data_source_id",
                    "data_source_id": self._sources["players"],
                },
                properties=properties,
            )
        result = dict(merged)
        result["_page_id"] = str(page.get("id") or "")
        return result

    def list_question_set_contacts(
        self, question_set_id: str
    ) -> list[dict[str, Any]]:
        pages = self._query_all(
            "players",
            filter_={
                "property": "coordination_consent_version",
                "rich_text": {"equals": question_set_id},
            },
        )
        return [
            self._question_set_contact_from_page(page)
            for page in pages
            if _rich(
                page.get("properties") or {},
                "coordination_consent_version",
            )
            == question_set_id
        ]

    @staticmethod
    def _feedback_from_page(page: dict[str, Any]) -> dict[str, Any]:
        properties = page.get("properties") or {}
        raw = _rich(properties, "metadata_json")
        try:
            feedback = json.loads(raw) if raw else {}
        except json.JSONDecodeError:
            feedback = {}
        feedback.setdefault("event_type", _select(properties, "event_type"))
        feedback.setdefault("question_id", _rich(properties, "item_id"))
        feedback.setdefault("created_at", _date(properties, "timestamp"))
        feedback["_page_id"] = str(page.get("id") or "")
        return feedback

    def record_question_feedback(self, feedback: dict[str, Any]) -> dict[str, Any]:
        event_type = str(feedback["event_type"])
        metadata_json = json.dumps(feedback, ensure_ascii=False, separators=(",", ":"))
        created = self._client.pages.create(
            parent={"type": "data_source_id", "data_source_id": self._sources["events"]},
            properties={
                "Name": {
                    "title": _text(
                        f"{event_type.replace('_', ' ').title()} "
                        f"{feedback['participant_alias']} · {feedback['question_id']}"
                    )
                },
                "session": _relation(self._session_page_id),
                "timestamp": {"date": {"start": str(feedback["created_at"])}},
                "event_type": {"select": {"name": event_type}},
                "item_id": {"rich_text": _text(str(feedback["question_id"]))},
                "page": {"rich_text": _text(str(feedback["protocol_id"]))},
                "value_label": {
                    "rich_text": _text(
                        ", ".join(feedback.get("flag_labels") or [])
                        or str(feedback.get("note") or "")
                    )
                },
                "metadata_json": {"rich_text": _text(metadata_json)},
                "device_id": {"rich_text": _text(str(feedback["participant_uuid"]))},
                "status": {"select": {"name": "ok"}},
            },
        )
        result = dict(feedback)
        result["_page_id"] = str(created["id"])
        return result

    def list_question_feedback(self, session_code: str) -> list[dict[str, Any]]:
        pages = self._query_all(
            "events",
            filter_={"property": "session", "relation": {"contains": self._session_page_id}},
        )
        feedback = [
            self._feedback_from_page(page)
            for page in pages
            if _select(page.get("properties") or {}, "event_type")
            in {"question_flagged", "question_skipped"}
        ]
        return sorted(feedback, key=lambda row: str(row.get("created_at", "")))

    @staticmethod
    def _question_event_from_page(page: dict[str, Any]) -> dict[str, Any]:
        properties = page.get("properties") or {}
        raw = _rich(properties, "metadata_json")
        try:
            event = json.loads(raw) if raw else {}
        except json.JSONDecodeError:
            event = {}
        event.setdefault("event_type", _select(properties, "event_type"))
        event.setdefault("status", _select(properties, "status"))
        event.setdefault("question_id", _rich(properties, "item_id"))
        event.setdefault("track_id", _rich(properties, "page"))
        event.setdefault("participant_id", _rich(properties, "device_id"))
        event.setdefault("timestamp", _date(properties, "timestamp"))
        event["_page_id"] = str(page.get("id") or "")
        return event

    def record_question_event(self, event: dict[str, Any]) -> dict[str, Any]:
        existing = next(
            (
                row
                for row in self.list_question_events(
                    str(event["track_id"]),
                    str(event["participant_id"]),
                )
                if row.get("question_id") == event.get("question_id")
            ),
            None,
        )
        if existing:
            return existing

        metadata_json = json.dumps(event, ensure_ascii=False, separators=(",", ":"))
        created = self._client.pages.create(
            parent={
                "type": "data_source_id",
                "data_source_id": self._sources["events"],
            },
            properties={
                "Name": {
                    "title": _text(
                        f"{str(event['status']).replace('_', ' ').title()} "
                        f"{event['participant_alias']} · {event['question_id']}"
                    )
                },
                "session": _relation(self._session_page_id),
                "timestamp": {"date": {"start": str(event["timestamp"])}},
                "event_type": {"select": {"name": "question_event"}},
                "item_id": {"rich_text": _text(str(event["question_id"]))},
                "page": {"rich_text": _text(str(event["track_id"]))},
                "value_label": {"rich_text": _text(str(event["status"]))},
                "metadata_json": {"rich_text": _text(metadata_json)},
                "device_id": {"rich_text": _text(str(event["participant_id"]))},
                "status": {"select": {"name": str(event["status"])}},
            },
        )
        result = dict(event)
        result["_page_id"] = str(created["id"])
        return result

    def list_question_events(
        self,
        track_id: str,
        participant_id: str | None = None,
    ) -> list[dict[str, Any]]:
        clauses: list[dict[str, Any]] = [
            {
                "property": "event_type",
                "select": {"equals": "question_event"},
            },
            {
                "property": "page",
                "rich_text": {"equals": track_id},
            },
        ]
        if participant_id is not None:
            clauses.append(
                {
                    "property": "device_id",
                    "rich_text": {"equals": participant_id},
                }
            )
        pages = self._query_all(
            "events",
            filter_={"and": clauses},
        )
        events = [
            self._question_event_from_page(page)
            for page in pages
            if _select(page.get("properties") or {}, "event_type")
            == "question_event"
            and _rich(page.get("properties") or {}, "page") == track_id
            and (
                participant_id is None
                or _rich(page.get("properties") or {}, "device_id")
                == participant_id
            )
        ]
        return sorted(events, key=lambda row: str(row.get("timestamp", "")))

    def _query_all(
        self, data_source: str, *, filter_: dict[str, Any] | None = None
    ) -> Iterable[dict[str, Any]]:
        cursor: str | None = None
        while True:
            arguments: dict[str, Any] = {
                "data_source_id": self._sources[data_source],
                "page_size": 100,
            }
            if filter_:
                arguments["filter"] = filter_
            if cursor:
                arguments["start_cursor"] = cursor
            response = self._client.data_sources.query(**arguments)
            yield from response.get("results") or []
            if not response.get("has_more"):
                return
            cursor = response.get("next_cursor")

    @staticmethod
    def _strategy_filter(
        participant_uuid: str, scenario_id: str, protocol_version: str
    ) -> dict[str, Any]:
        return {
            "and": [
                {"property": "participant_uuid", "rich_text": {"equals": participant_uuid}},
                {"property": "scenario_id", "rich_text": {"equals": scenario_id}},
                {"property": "protocol_version", "rich_text": {"equals": protocol_version}},
            ]
        }

    def _strategy_from_page(self, page: dict[str, Any]) -> dict[str, Any]:
        properties = page.get("properties") or {}
        profile_json = _rich(properties, "strategic_profile_json")
        if profile_json:
            profile = json.loads(profile_json)
        else:
            profile = {
                "participant_uuid": _rich(properties, "participant_uuid"),
                "scenario_id": _rich(properties, "scenario_id"),
                "decision_id": _rich(properties, "decision_id"),
                "action_id": _rich(properties, "action_id"),
                "rationale": _rich(properties, "rationale"),
                "protocol_version": _rich(properties, "protocol_version"),
                "integrated_at": _date(properties, "integrated_at"),
            }
        profile["_page_id"] = str(page.get("id") or "")
        return profile

    def get_strategic_profile(
        self, participant_uuid: str, scenario_id: str, protocol_version: str
    ) -> dict[str, Any] | None:
        pages = self._query_all(
            "responses",
            filter_=self._strategy_filter(participant_uuid, scenario_id, protocol_version),
        )
        page = next(
            (
                candidate
                for candidate in pages
                if _rich(
                    candidate.get("properties") or {},
                    "strategic_profile_json",
                )
            ),
            None,
        )
        return self._strategy_from_page(page) if page else None

    def integrate_strategic_profile(self, profile: dict[str, Any]) -> dict[str, Any]:
        existing = self.get_strategic_profile(
            str(profile["participant_uuid"]),
            str(profile["scenario_id"]),
            str(profile["protocol_version"]),
        )
        if existing:
            return existing

        profile_json = json.dumps(profile, ensure_ascii=False, separators=(",", ":"))
        action_id = str(profile["action_id"])
        created = self._client.pages.create(
            parent={"type": "data_source_id", "data_source_id": self._sources["responses"]},
            properties={
                "Name": {"title": _text(f"Strategy {profile['participant_alias']} · {profile['scenario_id']}")},
                "session": _relation(self._session_page_id),
                "participant_uuid": {"rich_text": _text(str(profile["participant_uuid"]))},
                "scenario_id": {"rich_text": _text(str(profile["scenario_id"]))},
                "decision_id": {"rich_text": _text(str(profile["decision_id"]))},
                "action_id": {"rich_text": _text(action_id)},
                "question_id": {"rich_text": _text(str(profile["decision_id"]))},
                "item_id": {"rich_text": _text(action_id)},
                "response_value": {"rich_text": _text(action_id)},
                "value_label": {"rich_text": _text(str(profile["action_label"]))},
                "value_json": {"rich_text": _text(profile_json)},
                "rationale": {"rich_text": _text(str(profile["rationale"]))},
                "semantic_tags_json": {"rich_text": _text(json.dumps(profile["semantic_tags"]))},
                "tagger_version": {"rich_text": _text(str(profile["tagger_version"]))},
                "strategic_profile_json": {"rich_text": _text(profile_json)},
                "integration_status": {"select": {"name": "integrated"}},
                "integrated_at": {"date": {"start": str(profile["integrated_at"])}},
                "submitted_at": {"date": {"start": str(profile["integrated_at"])}},
                "created_at": {"date": {"start": str(profile["integrated_at"])}},
                "protocol_version": {"rich_text": _text(str(profile["protocol_version"]))},
                "revision": {"number": int(profile.get("revision") or 1)},
                "question_type": {"select": {"name": "single"}},
                "text_id": {"rich_text": _text(str(profile["protocol_id"]))},
            },
        )
        result = dict(profile)
        result["_page_id"] = str(created["id"])
        return result

    def list_strategic_profiles(self, session_code: str) -> list[dict[str, Any]]:
        # This pilot has one configured session. Filtering via the session relation
        # avoids duplicating the session code on every strategic record.
        pages = self._query_all(
            "responses",
            filter_={"property": "session", "relation": {"contains": self._session_page_id}},
        )
        profiles = [
            self._strategy_from_page(page)
            for page in pages
            if _rich(page.get("properties") or {}, "strategic_profile_json")
        ]
        return sorted(profiles, key=lambda row: str(row.get("integrated_at", "")))

    @staticmethod
    def _coordination_from_page(page: dict[str, Any]) -> dict[str, Any]:
        properties = page.get("properties") or {}
        return {
            "participant_uuid": _rich(properties, "participant_uuid"),
            "name": _rich(properties, "nickname") or None,
            "email": _email(properties),
            "coordination_opt_in": bool(
                (properties.get("coordination_opt_in") or {}).get("checkbox")
            ),
            "coordination_status": _select(properties, "coordination_status"),
            "coordination_consent_version": _rich(
                properties, "coordination_consent_version"
            ),
            "coordination_consented_at": _date(
                properties, "coordination_consented_at"
            ),
            "_page_id": str(page.get("id") or ""),
        }

    def _coordination_page(self, participant_uuid: str) -> dict[str, Any] | None:
        pages = self._query_all(
            "players",
            filter_={
                "property": "participant_uuid",
                "rich_text": {"equals": participant_uuid},
            },
        )
        return next(iter(pages), None)

    def get_coordination_interest(self, participant_uuid: str) -> dict[str, Any] | None:
        page = self._coordination_page(participant_uuid)
        return self._coordination_from_page(page) if page else None

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
        status = "reachable_interest" if normalized_email else "anonymous_interest"
        properties: dict[str, Any] = {
            "Name": {"title": _text(f"Coordination {participant_uuid[:8]}")},
            "session": _relation(self._session_page_id),
            "participant_uuid": {"rich_text": _text(participant_uuid)},
            "nickname": {"rich_text": _text(normalized_name or "")},
            "coordination_opt_in": {"checkbox": True},
            "coordination_status": {"select": {"name": status}},
            "coordination_consent_version": {"rich_text": _text(consent_version)},
            "coordination_consented_at": {"date": {"start": consented_at}},
            "role": {"select": {"name": "participant"}},
            "status": {"select": {"name": "active"}},
            "consented": {"checkbox": True},
        }
        if normalized_email:
            properties["email"] = {"email": normalized_email}
        else:
            properties["email"] = {"email": None}

        existing = self._coordination_page(participant_uuid)
        if existing:
            page = self._client.pages.update(page_id=str(existing["id"]), properties=properties)
        else:
            page = self._client.pages.create(
                parent={"type": "data_source_id", "data_source_id": self._sources["players"]},
                properties=properties,
            )
        return self._coordination_from_page(page)

    def list_coordination_interests(self, session_code: str) -> list[dict[str, Any]]:
        pages = self._query_all(
            "players",
            filter_={
                "and": [
                    {"property": "session", "relation": {"contains": self._session_page_id}},
                    {"property": "coordination_opt_in", "checkbox": {"equals": True}},
                ]
            },
        )
        return [self._coordination_from_page(page) for page in pages]

    def delete_contact_data(self, participant_uuid: str) -> bool:
        page = self._coordination_page(participant_uuid)
        if not page:
            return False
        self._client.pages.update(page_id=str(page["id"]), in_trash=True)
        return True
