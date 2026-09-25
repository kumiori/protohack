"""Physical schema-neutral Notion sink for TEST Probe envelopes."""

from __future__ import annotations

from copy import deepcopy
import json
from typing import Any

from .notion import NotionRepository, _date, _rich, _text


class GenericNotionDebugRepository(NotionRepository):
    SOURCE = "test_submissions"
    HEALTH_SOURCE = SOURCE

    def _pages(self, *, property_name: str = "", equals: str = "") -> list[dict[str, Any]]:
        filter_ = (
            {"property": property_name, "rich_text": {"equals": equals}}
            if property_name
            else None
        )
        return list(self._query_all(self.SOURCE, filter_=filter_))

    @staticmethod
    def _from_page(page: dict[str, Any]) -> dict[str, Any] | None:
        properties = page.get("properties") or {}
        raw = _rich(properties, "payload")
        try:
            value = json.loads(raw)
        except json.JSONDecodeError:
            return None
        if value.get("schema") != "probe-submission-envelope/v1":
            return None
        value["_page_id"] = str(page.get("id") or "")
        value["receipt_metadata"] = json.loads(
            _rich(properties, "receipt_metadata") or "{}"
        )
        return value

    def save_probe_trajectory(self, envelope: dict[str, Any]) -> dict[str, Any]:
        participation_id = str(envelope["participation_id"])
        credential = dict((envelope.get("player") or {}).get("credential") or {})
        existing = next(
            (
                page
                for page in self._pages(
                    property_name="participation_id", equals=participation_id
                )
                if _rich(page.get("properties") or {}, "participation_id")
                == participation_id
            ),
            None,
        )
        serialized = json.dumps(envelope, ensure_ascii=False, separators=(",", ":"))
        properties = {
            "event_id": {"rich_text": _text(str(envelope["event_id"]))},
            "probe_id": {"rich_text": _text(str(envelope["probe_id"]))},
            "probe_revision": {"number": int(envelope["probe_revision"])},
            "participant_id": {"rich_text": _text(str(envelope["participant_id"]))},
            "participation_id": {"rich_text": _text(participation_id)},
            "submission_id": {"rich_text": _text(str(envelope.get("submission_id") or ""))},
            "environment": {"select": {"name": "test"}},
            "state": {"select": {"name": str(envelope.get("state") or "draft")}},
            "batch_id": {"rich_text": _text(str(envelope.get("batch_id") or ""))},
            "access_code_selector": {
                "rich_text": _text(str(credential.get("selector") or ""))
            },
            "access_code_verifier": {
                "rich_text": _text(str(credential.get("verifier") or ""))
            },
            "updated_at": {"date": {"start": str(envelope["updated_at"])}},
            "payload": {"rich_text": _text(serialized)},
            "receipt_metadata": {"rich_text": _text("{}")},
        }
        if existing:
            page_id = str(existing["id"])
            self._client.pages.update(page_id=page_id, properties=properties)
        else:
            created = self._client.pages.create(
                parent={
                    "type": "data_source_id",
                    "data_source_id": self._sources[self.SOURCE],
                },
                properties={
                    "Name": {"title": _text(f"{envelope['probe_id']} · {participation_id[:8]}")},
                    "created_at": {"date": {"start": str(envelope["created_at"])}},
                    **properties,
                },
            )
            page_id = str(created["id"])
        result = deepcopy(envelope)
        result["_page_id"] = page_id
        return result

    def commit_probe_submission(self, envelope: dict[str, Any]) -> dict[str, Any]:
        """TEST remains a schema-neutral forensic envelope sink."""

        stored = self.save_probe_trajectory(envelope)
        return {**stored, "committed": True, "stages": {"debug_envelope": True}}

    def get_probe_trajectory(self, participation_id: str) -> dict[str, Any] | None:
        for page in self._pages(
            property_name="participation_id", equals=participation_id
        ):
            value = self._from_page(page)
            if value and str(value.get("participation_id") or "") == participation_id:
                return value
        return None

    def list_probe_trajectories(
        self, event_id: str, probe_id: str
    ) -> list[dict[str, Any]]:
        rows = []
        for page in self._pages(property_name="event_id", equals=event_id):
            value = self._from_page(page)
            if value and str(value.get("probe_id") or "") == probe_id:
                rows.append(value)
        return rows

    def list_probe_response_audit_rows(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for page in self._pages():
            value = self._from_page(page)
            if value is None:
                rows.append(
                    {
                        "_page_id": str(page.get("id") or ""),
                        "record_type": "",
                        "state": "",
                    }
                )
                continue
            # The test repository is deliberately an envelope store and has no
            # physical Players table. Participant identity is its canonical key.
            value["player_page_id"] = str(value.get("participant_id") or "")
            rows.append(value)
        return rows

    def export_probe_players(self, page_ids: list[str]) -> list[dict[str, Any]]:
        return []

    def archive_probe_cleanup(
        self, response_page_ids: list[str], player_page_ids: list[str]
    ) -> dict[str, int]:
        for page_id in response_page_ids:
            self._client.pages.update(page_id=page_id, archived=True)
        return {"responses": len(response_page_ids), "players": 0, "other": 0}

    def find_probe_trajectories_by_access_selector(
        self, access_code_selector: str
    ) -> list[dict[str, Any]]:
        return [
            value
            for page in self._pages(
                property_name="access_code_selector", equals=access_code_selector
            )
            if (value := self._from_page(page)) is not None
        ]

    def find_probe_trajectories_by_access_verifier(
        self, access_code_verifier: str
    ) -> list[dict[str, Any]]:
        return [
            value
            for page in self._pages(
                property_name="access_code_verifier", equals=access_code_verifier
            )
            if (value := self._from_page(page)) is not None
        ]

    def discard_probe_trajectories(
        self, event_id: str, probe_id: str, *, batch_id: str | None = None
    ) -> int:
        count = 0
        for row in self.list_probe_trajectories(event_id, probe_id):
            if batch_id is not None and str(row.get("batch_id") or "") != batch_id:
                continue
            self._client.pages.update(page_id=str(row["_page_id"]), archived=True)
            count += 1
        return count
