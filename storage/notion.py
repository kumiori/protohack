"""Notion-backed repository using the protohack database family."""

from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
from time import monotonic, sleep
from typing import Any, Iterable

from notion_client import Client
from notion_client.errors import APIResponseError

from .base import RepositoryHealth
from protocol.probe_results import assert_integrated_submission


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MANIFEST = ROOT / "config" / "protohack_notion.json"
DEFAULT_NOTION_VERSION = "2025-09-03"


def _text(content: str) -> list[dict[str, Any]]:
    value = str(content)
    chunks: list[str] = []
    current: list[str] = []
    current_units = 0
    for character in value:
        units = len(character.encode("utf-16-le")) // 2
        if current and current_units + units > 2000:
            chunks.append("".join(current))
            current = []
            current_units = 0
        current.append(character)
        current_units += units
    if current or not chunks:
        chunks.append("".join(current))
    return [
        {"type": "text", "text": {"content": chunk}}
        for chunk in chunks
    ]


def _rich(properties: dict[str, Any], name: str) -> str:
    values = (properties.get(name) or {}).get("rich_text") or []
    return "".join(
        str(value.get("plain_text") or (value.get("text") or {}).get("content") or "")
        for value in values
    )


def _title_value(properties: dict[str, Any], name: str = "Name") -> str:
    values = (properties.get(name) or {}).get("title") or []
    return "".join(
        str(value.get("plain_text") or (value.get("text") or {}).get("content") or "")
        for value in values
    )


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


def _safe_exception_message(exc: Exception) -> str:
    """Expose an actionable API message without headers, tokens, or payloads."""

    message = str(getattr(exc, "message", "") or str(exc) or type(exc).__name__)
    message = " ".join(message.split())
    return message[:500]


class ProbeSubmissionCommitError(RuntimeError):
    """A recoverable partial Notion commit with safe page identifiers."""

    def __init__(self, message: str, *, receipt: dict[str, Any]) -> None:
        super().__init__(message)
        self.receipt = receipt


class NotionRepository:
    HEALTH_SOURCE = "responses"

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
        self._health_result: RepositoryHealth | None = None
        self._health_checked_at = 0.0

    def health_check(self) -> RepositoryHealth:
        """Verify the configured integration can query its required data source."""

        if self._health_result is not None and monotonic() - self._health_checked_at < 60:
            return self._health_result

        def remember(result: RepositoryHealth) -> RepositoryHealth:
            self._health_result = result
            self._health_checked_at = monotonic()
            return result

        integration = "unknown"
        source_id = str(self._sources.get(self.HEALTH_SOURCE) or "")
        try:
            integration = str(self._client.users.me().get("name") or "unknown")
            self._client.data_sources.query(
                data_source_id=source_id,
                page_size=1,
            )
        except APIResponseError as exc:
            code = str(getattr(exc, "code", "") or "")
            status = (
                "inaccessible / not found"
                if code == "object_not_found" or getattr(exc, "status", 0) == 404
                else "unavailable"
            )
            return remember(RepositoryHealth(
                available=False,
                integration=integration,
                data_source_id=source_id,
                status=status,
                error_code=code or type(exc).__name__,
            ))
        except Exception as exc:
            return remember(RepositoryHealth(
                available=False,
                integration=integration,
                data_source_id=source_id,
                status="unavailable",
                error_code=type(exc).__name__,
            ))
        return remember(RepositoryHealth(
            available=True,
            integration=integration,
            data_source_id=source_id,
            status="available",
        ))

    def _persistence_call(self, callback):
        """Retry a bounded Notion rate limit without hiding other failures."""

        for attempt in range(4):
            try:
                return callback()
            except APIResponseError as exc:
                status = int(getattr(exc, "status", 0) or 0)
                code = str(getattr(exc, "code", "") or "")
                if status != 429 and code != "rate_limited":
                    raise
                if attempt == 3:
                    raise
                headers = getattr(exc, "headers", None) or {}
                try:
                    delay = float(headers.get("retry-after", 1))
                except (TypeError, ValueError):
                    delay = 1.0
                sleep(min(max(delay, 0.25), 5.0))

    def save_probe_trajectory(
        self, trajectory: dict[str, Any]
    ) -> dict[str, Any]:
        return self._save_probe_trajectory(trajectory)

    def _save_probe_trajectory(
        self,
        trajectory: dict[str, Any],
        *,
        player_page_id: str = "",
    ) -> dict[str, Any]:
        participation_id = str(trajectory["participation_id"])
        probe_id = str(trajectory["probe_id"])
        integrated = bool(trajectory.get("integrated"))
        submission_id = str(trajectory.get("submission_id") or "")
        query_property = "submission_id" if integrated else "participation_id"
        query_value = submission_id if integrated else participation_id
        pages = self._query_all(
            "responses",
            filter_={"property": query_property, "rich_text": {"equals": query_value}},
        )
        existing = next(
            (
                page
                for page in pages
                if _rich(page.get("properties") or {}, query_property) == query_value
            ),
            None,
        )
        events = ((trajectory.get("trajectory") or {}).get("events") or [])
        updated_at = str(events[-1].get("timestamp") or "") if events else None
        revision = int(trajectory.get("revision") or 0)
        if integrated and existing is None:
            related = self._query_all(
                "responses",
                filter_={
                    "property": "participation_id",
                    "rich_text": {"equals": participation_id},
                },
            )
            revision = max(
                [
                    int(((page.get("properties") or {}).get("revision") or {}).get("number") or 0)
                    for page in related
                    if _rich(page.get("properties") or {}, "probe_id") == probe_id
                ]
                or [0]
            ) + 1
        elif existing is not None:
            revision = int(
                ((existing.get("properties") or {}).get("revision") or {}).get("number")
                or revision
                or 1
            )
        trajectory = {**trajectory, "revision": revision}
        payload = json.dumps(trajectory, ensure_ascii=False, separators=(",", ":"))
        properties = {
            "record_type": {"select": {"name": str(trajectory.get("record_type") or "probe_submission")}},
            "value_label": {
                "rich_text": _text(f"{len(events)} trajectory events")
            },
            "value_json": {"rich_text": _text(payload)},
            "revision": {"number": revision},
            "submission_id": {
                "rich_text": _text(str(trajectory.get("submission_id") or ""))
            },
            "event_id": {"rich_text": _text(str(trajectory.get("event_id") or ""))},
            "probe_id": {"rich_text": _text(probe_id)},
            "probe_revision": {"number": int(trajectory["probe_revision"])},
            "participation_id": {"rich_text": _text(participation_id)},
            "submission_state": {
                "select": {"name": str(trajectory.get("state") or "draft")}
            },
            "environment": {
                "select": {"name": str(trajectory.get("environment") or "production")}
            },
        }
        if player_page_id:
            properties["player"] = _relation(player_page_id)
        if updated_at:
            properties["submitted_at"] = {"date": {"start": updated_at}}
        integrated_at = str(trajectory.get("integrated_at") or "")
        if integrated_at:
            properties["integrated_at"] = {"date": {"start": integrated_at}}
        if existing:
            self._persistence_call(
                lambda: self._client.pages.update(
                    page_id=str(existing["id"]),
                    properties=properties,
                )
            )
            result = dict(trajectory)
            result["_page_id"] = str(existing["id"])
            result["_created"] = False
            return result
        created = self._persistence_call(
            lambda: self._client.pages.create(
                parent={
                    "type": "data_source_id",
                    "data_source_id": self._sources["responses"],
                },
                properties={
                    "Name": {"title": _text(f"{probe_id} trajectory")},
                    "session": _relation(self._session_page_id),
                    **properties,
                    **({"created_at": {"date": {"start": str(trajectory.get("created_at") or updated_at)}}} if trajectory.get("created_at") or updated_at else {}),
                },
            )
        )
        result = dict(trajectory)
        result["_page_id"] = str(created["id"])
        result["_created"] = True
        return result

    @staticmethod
    def _location_properties(value: Any) -> dict[str, Any]:
        location = value if isinstance(value, dict) else {}
        label = str(
            location.get("display_label")
            or location.get("label")
            or location.get("formatted")
            or (value if isinstance(value, str) else "")
            or ""
        )
        latitude = location.get("latitude", location.get("lat"))
        longitude = location.get("longitude", location.get("lng"))
        return {
            "base_location": {
                "rich_text": _text(
                    json.dumps(location, ensure_ascii=False, separators=(",", ":"))
                    if location
                    else label
                )
            },
            "base_location_label": {"rich_text": _text(label)},
            "base_location_place_id": {
                "rich_text": _text(
                    str(location.get("place_id") or location.get("stable_place_id") or "")
                )
            },
            "base_location_lat": {
                "number": float(latitude) if latitude not in {None, ""} else None
            },
            "base_location_lon": {
                "number": float(longitude) if longitude not in {None, ""} else None
            },
        }

    def _probe_player_page(self, participant_id: str) -> dict[str, Any] | None:
        for property_name in ("participant_id", "participant_uuid"):
            pages = self._query_all(
                "players",
                filter_={
                    "property": property_name,
                    "rich_text": {"equals": participant_id},
                },
            )
            match = next(
                (
                    page
                    for page in pages
                    if _rich(page.get("properties") or {}, property_name)
                    == participant_id
                ),
                None,
            )
            if match:
                return match
        return None

    def _upsert_probe_player(self, envelope: dict[str, Any]) -> dict[str, Any]:
        player = dict(envelope.get("player") or {})
        credential = dict(player.get("credential") or {})
        participant_id = str(player.get("participant_id") or envelope["participant_id"])
        name = str(player.get("name") or "").strip()
        email = str(player.get("email") or "").strip()
        institution = str(player.get("institution") or "").strip()
        profile_json = json.dumps(
            {
                "profile_answers": player.get("profile_answers") or {},
                "answer_field_ids": player.get("answer_field_ids") or [],
                "trajectory_events": player.get("trajectory_events") or [],
            },
            ensure_ascii=False,
            separators=(",", ":"),
        )
        existing = self._probe_player_page(participant_id)
        existing_properties = (existing or {}).get("properties") or {}
        emoji = str(credential.get("emoji") or _rich(existing_properties, "access_code_emoji"))
        selector = str(credential.get("selector") or _rich(existing_properties, "access_code_selector"))
        selector_6 = str(credential.get("selector_6") or _rich(existing_properties, "access_code_selector_6"))
        verifier = str(credential.get("verifier") or _rich(existing_properties, "access_code_verifier"))
        if existing and not (selector and verifier):
            raise RuntimeError("Existing Player credential is incomplete.")
        properties: dict[str, Any] = {
            "Name": {"title": _text(name or f"Participant {participant_id[:8]}")},
            "session": _relation(self._session_page_id),
            "participant_id": {"rich_text": _text(participant_id)},
            "participant_uuid": {"rich_text": _text(participant_id)},
            "nickname": {"rich_text": _text(name)},
            "email": {"email": email or None},
            "institution": {"rich_text": _text(institution)},
            "access_code_emoji": {"rich_text": _text(emoji)},
            "access_code_selector": {"rich_text": _text(selector)},
            "access_code_selector_6": {"rich_text": _text(selector_6)},
            "access_code_verifier": {"rich_text": _text(verifier)},
            "profile_json": {"rich_text": _text(profile_json)},
            "role": {"select": {"name": "participant"}},
            "status": {"select": {"name": "active"}},
        }
        properties.update(self._location_properties(player.get("base_location")))
        if existing:
            page = self._persistence_call(
                lambda: self._client.pages.update(
                    page_id=str(existing["id"]), properties=properties
                )
            )
        else:
            page = self._persistence_call(
                lambda: self._client.pages.create(
                    parent={
                        "type": "data_source_id",
                        "data_source_id": self._sources["players"],
                    },
                    properties=properties,
                )
            )
        return page

    @staticmethod
    def _substantive_envelope(envelope: dict[str, Any]) -> dict[str, Any]:
        response = deepcopy(envelope)
        player = dict(response.get("player") or {})
        identity_fields = {
            str(field_id) for field_id in (player.get("answer_field_ids") or [])
        }
        response.pop("player", None)
        response.pop("access_code_selector", None)
        response.pop("access_code_verifier", None)
        payload = dict(response.get("payload") or {})
        payload.pop("identity", None)
        for container in (response, payload):
            trajectory = deepcopy(container.get("trajectory") or {})
            trajectory["events"] = [
                event
                for event in (trajectory.get("events") or [])
                if str(event.get("question_id") or "") not in identity_fields
            ]
            container["trajectory"] = trajectory
        response["payload"] = payload
        return response

    def commit_probe_submission(self, envelope: dict[str, Any]) -> dict[str, Any]:
        """Idempotently persist Player then linked Response and verify both."""

        participant_id = str(envelope.get("participant_id") or "")
        participation_id = str(envelope.get("participation_id") or "")
        submission_id = str(envelope.get("submission_id") or "")
        receipt: dict[str, Any] = {
            "operation": "commit_probe_submission",
            "repository": type(self).__name__,
            "target_data_source": str(self._sources.get("responses") or ""),
            "player_id": participant_id,
            "participation_id": participation_id,
            "submission_id": submission_id,
            "revision": int(envelope.get("revision") or 0),
            "phase": "prepare",
            "committed": False,
            "player_page_id": "",
            "response_page_id": "",
            "exception_class": "",
            "notion_status": 0,
            "notion_code": "",
            "sanitized_message": "",
            "rollback": {"attempted": False, "response": "not_needed", "player": "not_needed"},
            "stages": {
                "player_resolve_upsert": False,
                "player_identity_persisted": False,
                "response_persisted": False,
                "response_player_relation": False,
                "read_back_verified": False,
            },
        }
        player_existed = False
        response_created = False
        try:
            assert_integrated_submission(envelope, require_player=False)
            receipt["phase"] = "player_write"
            player_existed = self._probe_player_page(participant_id) is not None
            player_page = self._upsert_probe_player(envelope)
            player_page_id = str(player_page.get("id") or "")
            if not player_page_id:
                raise RuntimeError("Player upsert returned no page ID.")
            receipt["player_page_id"] = player_page_id
            receipt["stages"]["player_resolve_upsert"] = True
            receipt["stages"]["player_identity_persisted"] = True

            response = self._substantive_envelope(envelope)
            assert_integrated_submission(
                {**response, "player_page_id": player_page_id}
            )
            receipt["phase"] = "response_write"
            stored = self._save_probe_trajectory(
                response,
                player_page_id=player_page_id,
            )
            response_page_id = str(stored.get("_page_id") or "")
            if not response_page_id:
                raise RuntimeError("Response write returned no page ID.")
            receipt["response_page_id"] = response_page_id
            response_created = bool(stored.get("_created"))
            receipt["revision"] = int(stored.get("revision") or receipt["revision"])
            receipt["stages"]["response_persisted"] = True

            receipt["phase"] = "readback"
            player_read = self._persistence_call(
                lambda: self._client.pages.retrieve(page_id=player_page_id)
            )
            response_read = self._persistence_call(
                lambda: self._client.pages.retrieve(page_id=response_page_id)
            )
            player_properties = player_read.get("properties") or {}
            response_properties = response_read.get("properties") or {}
            try:
                persisted_envelope = json.loads(
                    _rich(response_properties, "value_json") or "{}"
                )
            except json.JSONDecodeError:
                persisted_envelope = {}
            relation_ids = {
                str(item.get("id") or "")
                for item in (response_properties.get("player") or {}).get("relation") or []
            }
            relation_ok = player_page_id in relation_ids
            receipt["stages"]["response_player_relation"] = relation_ok
            checks = {
                "player_id": _rich(player_properties, "participant_id")
                == str(envelope["participant_id"]),
                "submission_id": _rich(response_properties, "submission_id")
                == str(envelope["submission_id"]),
                "event_id": _rich(response_properties, "event_id")
                == str(envelope["event_id"]),
                "probe_id": _rich(response_properties, "probe_id")
                == str(envelope["probe_id"]),
                "probe_revision": int(
                    (response_properties.get("probe_revision") or {}).get("number") or 0
                )
                == int(envelope["probe_revision"]),
                "response_revision": int(
                    (response_properties.get("revision") or {}).get("number") or 0
                )
                == int(receipt["revision"]),
                # Notion's date property truncates seconds. The canonical
                # envelope stored in value_json retains the exact instant.
                "integrated_at": str(persisted_envelope.get("integrated_at") or "")
                == str(envelope["integrated_at"]),
                "player_relation": relation_ok,
            }
            receipt["readback_checks"] = checks
            if not checks["integrated_at"]:
                receipt["readback_detail"] = {
                    "integrated_at_expected": str(envelope["integrated_at"]),
                    "integrated_at_actual": _date(
                        response_properties, "integrated_at"
                    ),
                    "canonical_integrated_at_actual": str(
                        persisted_envelope.get("integrated_at") or ""
                    ),
                }
            verified = all(checks.values())
            receipt["stages"]["read_back_verified"] = verified
            receipt["committed"] = verified
            if not verified:
                raise RuntimeError("Player/Response read-back verification failed.")
            receipt["phase"] = "receipt"
            return receipt
        except Exception as exc:
            receipt["exception_class"] = type(exc).__name__
            receipt["notion_status"] = int(getattr(exc, "status", 0) or 0)
            receipt["notion_code"] = str(getattr(exc, "code", "") or "")
            receipt["sanitized_message"] = _safe_exception_message(exc)
            rollback = receipt["rollback"]
            if response_created or (receipt["player_page_id"] and not player_existed):
                rollback["attempted"] = True
            if response_created and receipt["response_page_id"]:
                try:
                    self._persistence_call(
                        lambda: self._client.pages.update(
                            page_id=receipt["response_page_id"], archived=True
                        )
                    )
                    rollback["response"] = "archived"
                except Exception as rollback_exc:
                    rollback["response"] = (
                        "failed: " + _safe_exception_message(rollback_exc)
                    )
            if receipt["player_page_id"] and not player_existed:
                try:
                    self._persistence_call(
                        lambda: self._client.pages.update(
                            page_id=receipt["player_page_id"], archived=True
                        )
                    )
                    rollback["player"] = "archived"
                except Exception as rollback_exc:
                    rollback["player"] = (
                        "failed: " + _safe_exception_message(rollback_exc)
                    )
            raise ProbeSubmissionCommitError(
                "Probe submission was not fully committed.", receipt=receipt
            ) from exc

    def get_probe_trajectory(
        self, participation_id: str
    ) -> dict[str, Any] | None:
        pages = self._query_all(
            "responses",
            filter_={
                "property": "participation_id",
                "rich_text": {"equals": participation_id},
            },
        )
        for page in pages:
            properties = page.get("properties") or {}
            if _rich(properties, "participation_id") != participation_id:
                continue
            value = self._probe_envelope_from_page(page)
            if value is not None:
                return value
        return None

    def _probe_envelope_from_page(
        self, page: dict[str, Any]
    ) -> dict[str, Any] | None:
        properties = page.get("properties") or {}
        raw = _rich(properties, "value_json")
        try:
            value = json.loads(raw)
        except json.JSONDecodeError:
            return None
        if value.get("record_type") not in {"probe_trajectory", "probe_submission"}:
            return None
        value["_page_id"] = str(page.get("id") or "")
        relations = (properties.get("player") or {}).get("relation") or []
        player_page_id = str(relations[0].get("id") or "") if relations else ""
        if player_page_id:
            player_page = self._client.pages.retrieve(page_id=player_page_id)
            player_properties = player_page.get("properties") or {}
            try:
                profile = json.loads(_rich(player_properties, "profile_json") or "{}")
            except json.JSONDecodeError:
                profile = {}
            profile_answers = (
                profile.get("profile_answers")
                if isinstance(profile.get("profile_answers"), dict)
                else profile
            )
            raw_location = _rich(player_properties, "base_location")
            try:
                base_location: Any = json.loads(raw_location) if raw_location else None
            except json.JSONDecodeError:
                base_location = raw_location or None
            value["player"] = {
                "participant_id": (
                    _rich(player_properties, "participant_id")
                    or _rich(player_properties, "participant_uuid")
                ),
                "name": _rich(player_properties, "nickname"),
                "email": _email(player_properties),
                "institution": _rich(player_properties, "institution"),
                "base_location": base_location,
                "profile_answers": profile_answers,
                "answer_field_ids": list(profile.get("answer_field_ids") or []),
                "trajectory_events": list(profile.get("trajectory_events") or []),
                "credential": {
                    "emoji": _rich(player_properties, "access_code_emoji"),
                    "selector": _rich(player_properties, "access_code_selector"),
                    "selector_6": _rich(player_properties, "access_code_selector_6"),
                    "verifier": _rich(player_properties, "access_code_verifier"),
                },
            }
            identity_events = list(profile.get("trajectory_events") or [])
            if identity_events:
                trajectory = deepcopy(value.get("trajectory") or {})
                events = list(trajectory.get("events") or []) + identity_events
                trajectory["events"] = sorted(
                    events,
                    key=lambda event: str(event.get("timestamp") or ""),
                )
                value["trajectory"] = trajectory
            value["player_page_id"] = player_page_id
        return value

    def list_probe_trajectories(
        self, event_id: str, probe_id: str
    ) -> list[dict[str, Any]]:
        rows = []
        for page in self._query_all(
            "responses",
            filter_={"property": "probe_id", "rich_text": {"equals": probe_id}},
        ):
            value = self._probe_envelope_from_page(page)
            if value is None:
                continue
            if str(value.get("event_id") or value.get("scope_id") or "") == event_id:
                rows.append(value)
        return rows

    def list_probe_response_audit_rows(self) -> list[dict[str, Any]]:
        """Return physical Response metadata without silently dropping bad rows."""

        rows: list[dict[str, Any]] = []
        for page in self._query_all("responses"):
            properties = page.get("properties") or {}
            raw = _rich(properties, "value_json")
            try:
                envelope = json.loads(raw) if raw else {}
            except json.JSONDecodeError:
                envelope = {}
            relations = (properties.get("player") or {}).get("relation") or []
            rows.append(
                {
                    **(envelope if isinstance(envelope, dict) else {}),
                    "_page_id": str(page.get("id") or ""),
                    "name": _title_value(properties),
                    "record_type": _select(properties, "record_type") or str(envelope.get("record_type") or ""),
                    "event_id": _rich(properties, "event_id") or str(envelope.get("event_id") or ""),
                    "probe_id": _rich(properties, "probe_id") or str(envelope.get("probe_id") or ""),
                    "probe_revision": int((properties.get("probe_revision") or {}).get("number") or envelope.get("probe_revision") or 0),
                    "submission_id": _rich(properties, "submission_id") or str(envelope.get("submission_id") or ""),
                    "state": _select(properties, "submission_state") or str(envelope.get("state") or ""),
                    "environment": _select(properties, "environment") or str(envelope.get("environment") or ""),
                    "created_at": _date(properties, "created_at") or str(envelope.get("created_at") or ""),
                    "integrated_at": _date(properties, "integrated_at") or str(envelope.get("integrated_at") or ""),
                    "revision": int((properties.get("revision") or {}).get("number") or envelope.get("revision") or 0),
                    "player_page_id": str(relations[0].get("id") or "") if relations else "",
                }
            )
        return rows

    def export_probe_players(self, page_ids: list[str]) -> list[dict[str, Any]]:
        records: list[dict[str, Any]] = []
        for page_id in page_ids:
            page = self._client.pages.retrieve(page_id=page_id)
            properties = page.get("properties") or {}
            records.append(
                {
                    "page_id": page_id,
                    "participant_id": _rich(properties, "participant_id") or _rich(properties, "participant_uuid"),
                    "name": _title_value(properties),
                    "email": _email(properties),
                    "institution": _rich(properties, "institution"),
                    "base_location": _rich(properties, "base_location"),
                    "profile_json": _rich(properties, "profile_json"),
                }
            )
        return records

    def archive_probe_cleanup(
        self, response_page_ids: list[str], player_page_ids: list[str]
    ) -> dict[str, int]:
        for page_id in response_page_ids:
            self._persistence_call(
                lambda page_id=page_id: self._client.pages.update(
                    page_id=page_id, archived=True
                )
            )
        for page_id in player_page_ids:
            self._persistence_call(
                lambda page_id=page_id: self._client.pages.update(
                    page_id=page_id, archived=True
                )
            )
        return {"responses": len(response_page_ids), "players": len(player_page_ids), "other": 0}

    def find_probe_trajectories_by_access_selector(
        self, access_code_selector: str
    ) -> list[dict[str, Any]]:
        players = self._query_all(
            "players",
            filter_={
                "property": "access_code_selector",
                "rich_text": {"equals": access_code_selector},
            },
        )
        return self._probe_trajectories_for_players(
            players,
            expected_property="access_code_selector",
            expected_value=access_code_selector,
        )

    def find_probe_trajectories_by_access_verifier(
        self, access_code_verifier: str
    ) -> list[dict[str, Any]]:
        players = self._query_all(
            "players",
            filter_={
                "property": "access_code_verifier",
                "rich_text": {"equals": access_code_verifier},
            },
        )
        return self._probe_trajectories_for_players(
            players,
            expected_property="access_code_verifier",
            expected_value=access_code_verifier,
        )

    def _probe_trajectories_for_players(
        self,
        players: list[dict[str, Any]],
        *,
        expected_property: str,
        expected_value: str,
    ) -> list[dict[str, Any]]:
        owners: dict[str, tuple[str, dict[str, str]]] = {}
        for page in players:
            properties = page.get("properties") or {}
            if _rich(properties, expected_property) != expected_value:
                continue
            participant_id = (
                _rich(properties, "participant_id")
                or _rich(properties, "participant_uuid")
            )
            if participant_id:
                owners[participant_id] = (
                    str(page.get("id") or ""),
                    {
                        "emoji": _rich(properties, "access_code_emoji"),
                        "selector": _rich(properties, "access_code_selector"),
                        "selector_6": _rich(properties, "access_code_selector_6"),
                        "verifier": _rich(properties, "access_code_verifier"),
                    },
                )

        matches: list[dict[str, Any]] = []
        for participant_id, (player_page_id, credential) in owners.items():
            if not player_page_id:
                continue
            for page in self._query_all(
                "responses",
                filter_={
                    "property": "player",
                    "relation": {"contains": player_page_id},
                },
            ):
                value = self._probe_envelope_from_page(page)
                if value is None or str(value.get("participant_id") or "") != participant_id:
                    continue
                player = dict(value.get("player") or {})
                player["credential"] = credential
                value["player"] = player
                matches.append(value)

        if owners:
            return matches
        for page in self._query_all("responses"):
            value = self._probe_envelope_from_page(page)
            if value is not None and str(value.get(expected_property) or "") == expected_value:
                # Read-only compatibility for submissions written before the
                # Player-owned credential migration.
                matches.append(value)
        return matches

    def discard_probe_trajectories(
        self, event_id: str, probe_id: str, *, batch_id: str | None = None
    ) -> int:
        count = 0
        for row in self.list_probe_trajectories(event_id, probe_id):
            if str(row.get("environment") or "") != "test":
                continue
            if batch_id is not None and str(row.get("batch_id") or "") != batch_id:
                continue
            page_id = str(row.get("_page_id") or "")
            if page_id:
                self._client.pages.update(page_id=page_id, archived=True)
                count += 1
        return count

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
    def _shared_goal_from_page(page: dict[str, Any]) -> dict[str, Any]:
        properties = page.get("properties") or {}
        return {
            "goal_id": _rich(properties, "goal_id"),
            "title": _title_value(properties),
            "objective": _rich(properties, "objective"),
            "created_by_agent_id": _rich(properties, "created_by_agent_id"),
            "created_at": _date(properties, "created_at"),
            "status": _select(properties, "status"),
            "visibility": _select(properties, "visibility"),
            "_page_id": str(page.get("id") or ""),
        }

    def create_shared_goal(self, goal: dict[str, Any]) -> dict[str, Any]:
        existing = self.get_shared_goal(str(goal["goal_id"]))
        if existing:
            return existing
        created = self._client.pages.create(
            parent={"type": "data_source_id", "data_source_id": self._sources["goals"]},
            properties={
                "Name": {"title": _text(str(goal["title"]))},
                "goal_id": {"rich_text": _text(str(goal["goal_id"]))},
                "objective": {"rich_text": _text(str(goal.get("objective") or ""))},
                "created_by_agent_id": {"rich_text": _text(str(goal.get("created_by_agent_id") or ""))},
                "created_at": {"date": {"start": str(goal["created_at"])}},
                "status": {"select": {"name": str(goal.get("status") or "open")}},
                "visibility": {"select": {"name": "public"}},
            },
        )
        result = dict(goal)
        result["_page_id"] = str(created.get("id") or "")
        return result

    def list_shared_goals(self) -> list[dict[str, Any]]:
        pages = self._query_all(
            "goals",
            filter_={"and": [
                {"property": "status", "select": {"equals": "open"}},
                {"property": "visibility", "select": {"equals": "public"}},
            ]},
        )
        return sorted(
            [self._shared_goal_from_page(page) for page in pages],
            key=lambda goal: str(goal.get("created_at", "")),
            reverse=True,
        )

    def get_shared_goal(self, goal_id: str) -> dict[str, Any] | None:
        pages = self._query_all(
            "goals",
            filter_={"property": "goal_id", "rich_text": {"equals": goal_id}},
        )
        page = next((
            candidate for candidate in pages
            if _rich(candidate.get("properties") or {}, "goal_id") == goal_id
        ), None)
        return self._shared_goal_from_page(page) if page else None

    @staticmethod
    def _goal_trajectory_from_page(page: dict[str, Any]) -> dict[str, Any]:
        properties = page.get("properties") or {}
        raw_payload = _rich(properties, "trajectory_payload")
        try:
            payload = json.loads(raw_payload) if raw_payload else {}
        except json.JSONDecodeError:
            payload = {}
        goal_relation = (properties.get("goal") or {}).get("relation") or []
        return {
            "trajectory_id": _rich(properties, "trajectory_id"),
            "goal_id": "",
            "agent_id": _rich(properties, "agent_id"),
            "agent_display_name": _rich(properties, "agent_display_name"),
            "agent_type": _select(properties, "agent_type"),
            "title": _rich(properties, "title"),
            "schema_version": _rich(properties, "schema_version"),
            "trajectory_payload": payload,
            "created_at": _date(properties, "created_at"),
            "updated_at": _date(properties, "updated_at"),
            "status": _select(properties, "status"),
            "source": _select(properties, "source"),
            "revision": int((properties.get("revision") or {}).get("number") or 1),
            "_goal_page_id": str(goal_relation[0].get("id") or "") if goal_relation else "",
            "_page_id": str(page.get("id") or ""),
        }

    def list_goal_trajectories(self, goal_id: str) -> list[dict[str, Any]]:
        goal = self.get_shared_goal(goal_id)
        if not goal:
            return []
        pages = self._query_all(
            "goal_trajectories",
            filter_={"property": "goal", "relation": {"contains": str(goal["_page_id"])}},
        )
        rows = []
        for page in pages:
            row = self._goal_trajectory_from_page(page)
            if row.get("status") != "withdrawn":
                row["goal_id"] = goal_id
                rows.append(row)
        return sorted(rows, key=lambda row: str(row.get("created_at", "")))

    def get_goal_trajectory(self, trajectory_id: str) -> dict[str, Any] | None:
        pages = self._query_all(
            "goal_trajectories",
            filter_={"property": "trajectory_id", "rich_text": {"equals": trajectory_id}},
        )
        page = next((
            candidate for candidate in pages
            if _rich(candidate.get("properties") or {}, "trajectory_id") == trajectory_id
        ), None)
        if not page:
            return None
        row = self._goal_trajectory_from_page(page)
        goal_page_id = str(row.pop("_goal_page_id", ""))
        goal_pages = self._query_all("goals")
        matching_goal = next(
            (goal for goal in goal_pages if str(goal.get("id") or "") == goal_page_id),
            None,
        )
        if matching_goal:
            row["goal_id"] = _rich(matching_goal.get("properties") or {}, "goal_id")
        return row

    def record_goal_trajectory(
        self,
        trajectory: dict[str, Any],
        *,
        update_existing: bool = False,
    ) -> dict[str, Any]:
        goal_id = str(trajectory["goal_id"])
        agent_id = str(trajectory["agent_id"])
        goal = self.get_shared_goal(goal_id)
        if not goal:
            raise ValueError("The shared goal does not exist.")
        duplicate = next((
            row for row in self.list_goal_trajectories(goal_id)
            if row.get("agent_id") == agent_id
        ), None)
        if duplicate and not update_existing:
            raise ValueError("This agent already has a trajectory for this goal.")
        if update_existing:
            if not duplicate or duplicate.get("trajectory_id") != trajectory.get("trajectory_id"):
                raise ValueError("The shared trajectory to update was not found.")
            if int(trajectory.get("revision") or 0) <= int(duplicate.get("revision") or 0):
                raise ValueError("A shared update must advance the revision.")
        payload_json = json.dumps(
            trajectory["trajectory_payload"],
            ensure_ascii=False,
            separators=(",", ":"),
        )
        properties = {
            "Name": {"title": _text(f"{trajectory['agent_display_name']} · {trajectory['title']}")},
            "goal": _relation(str(goal["_page_id"])),
            "trajectory_id": {"rich_text": _text(str(trajectory["trajectory_id"]))},
            "agent_id": {"rich_text": _text(agent_id)},
            "agent_display_name": {"rich_text": _text(str(trajectory["agent_display_name"]))},
            "agent_type": {"select": {"name": str(trajectory["agent_type"])}},
            "title": {"rich_text": _text(str(trajectory["title"]))},
            "schema_version": {"rich_text": _text(str(trajectory["schema_version"]))},
            "trajectory_payload": {"rich_text": _text(payload_json)},
            "created_at": {"date": {"start": str(trajectory["created_at"])}},
            "updated_at": {"date": {"start": str(trajectory["updated_at"])}},
            "status": {"select": {"name": str(trajectory["status"])}},
            "source": {"select": {"name": str(trajectory["source"])}},
            "revision": {"number": int(trajectory["revision"])},
        }
        if update_existing and duplicate:
            page = self._client.pages.update(
                page_id=str(duplicate["_page_id"]),
                properties=properties,
            )
        else:
            page = self._client.pages.create(
                parent={"type": "data_source_id", "data_source_id": self._sources["goal_trajectories"]},
                properties=properties,
            )
        result = dict(trajectory)
        result["_page_id"] = str(page.get("id") or "")
        return result

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
            response = self._persistence_call(
                lambda: self._client.data_sources.query(**arguments)
            )
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
