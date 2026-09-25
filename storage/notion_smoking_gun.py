"""Minimal Notion CREATE + READ BACK diagnostic, independent of Probe semantics."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
from time import perf_counter
import traceback
from typing import Any, Callable
import uuid

from notion_client import Client

from .notion import DEFAULT_MANIFEST, DEFAULT_NOTION_VERSION, _text, _title_value


@dataclass(frozen=True)
class SmokingGunTarget:
    environment: str
    source_key: str
    database: str
    database_id: str
    data_source_id: str
    source: str
    repository: str = "Notion"
    operation: str = "CREATE + READ BACK + VALUE MATCH + REVERT"


class NotionSmokingGun:
    """Exercise one exact Notion target without invoking application repositories."""

    def __init__(
        self,
        *,
        token: str,
        environment: str,
        manifest_path: str | Path = DEFAULT_MANIFEST,
        notion_version: str = DEFAULT_NOTION_VERSION,
        client: Any | None = None,
    ) -> None:
        resolved_manifest = Path(manifest_path).resolve()
        manifest = json.loads(resolved_manifest.read_text(encoding="utf-8"))
        normalized = environment.upper()
        source_key = "test_submissions" if normalized == "TEST" else "responses"
        target = manifest["databases"][source_key]
        self.target = SmokingGunTarget(
            environment=normalized,
            source_key=source_key,
            database=str(target["title"]),
            database_id=str(target["database_id"]),
            data_source_id=str(target["data_source_id"]),
            source=str(resolved_manifest.relative_to(resolved_manifest.parents[1])),
        )
        self.token_configured = bool(token)
        self.token_fingerprint = (
            "sha256:" + hashlib.sha256(token.encode("utf-8")).hexdigest()[:8]
            if token
            else "not configured"
        )
        self._token_redaction = token
        self.client = client or Client(auth=token, notion_version=notion_version)
        self.trace: list[dict[str, Any]] = []
        self.raw_traceback = ""
        self.integration = "unknown"
        self.title_property = "Name"
        self.last_page_id = ""
        self.last_name = ""

    @staticmethod
    def _timestamp() -> str:
        return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")

    def _safe_error(self, exc: Exception) -> dict[str, Any]:
        raw = traceback.format_exc()
        message = str(exc)
        self.raw_traceback = (
            raw.replace(self._token_redaction, "[REDACTED]")
            if self._token_redaction
            else raw
        )
        if self._token_redaction:
            message = message.replace(self._token_redaction, "[REDACTED]")
        return {
            "exception_type": type(exc).__name__,
            "notion_code": str(getattr(exc, "code", "") or "unknown"),
            "http": int(getattr(exc, "status", 0) or 0),
            "data_source_id": self.target.data_source_id,
            "message": message,
        }

    def _operation(
        self,
        step: str,
        operation: str,
        callback: Callable[[], Any],
        *,
        request_fields: list[str] | None = None,
        request: dict[str, Any] | None = None,
    ) -> Any:
        started = perf_counter()
        entry: dict[str, Any] = {
            "step": step,
            "operation": operation,
            "timestamp": self._timestamp(),
            "target_id": self.target.data_source_id,
            "request_fields": request_fields or [],
            "request": request or {},
            "success": False,
        }
        try:
            result = callback()
            entry.update(
                {
                    "success": True,
                    "http": 200,
                    "elapsed_ms": round((perf_counter() - started) * 1000, 2),
                }
            )
            self.trace.append(entry)
            return result
        except Exception as exc:
            entry.update(self._safe_error(exc))
            entry["elapsed_ms"] = round((perf_counter() - started) * 1000, 2)
            self.trace.append(entry)
            raise

    def begin_run(self, run_id: str) -> None:
        self.trace = [
            {
                "step": "RUN",
                "run_id": run_id,
                "timestamp": self._timestamp(),
                "environment": self.target.environment,
                "repository": self.target.repository.lower(),
                "token_configured": self.token_configured,
                "token_fingerprint": self.token_fingerprint,
                "data_source_id": self.target.data_source_id,
                "database_id": self.target.database_id,
                "database": self.target.database,
                "source": self.target.source,
                "success": True,
            }
        ]
        self.raw_traceback = ""

    def instantiate_client(self) -> None:
        self.trace.append(
            {
                "step": "01 CLIENT",
                "operation": "instantiate Notion client",
                "timestamp": self._timestamp(),
                "target_id": self.target.data_source_id,
                "success": True,
                "token_configured": self.token_configured,
            }
        )

    def test_access(self) -> None:
        me = self._operation(
            "02 TARGET RESOLUTION",
            "retrieve integration identity",
            self.client.users.me,
        )
        self.integration = str(me.get("name") or "unknown")
        self.trace[-1]["integration"] = self.integration
        response = self._operation(
            "03 ACCESS TEST",
            "query data source",
            lambda: self.client.data_sources.query(
                data_source_id=self.target.data_source_id,
                page_size=1,
            ),
        )
        self.trace[-1]["result_count"] = len(response.get("results") or [])

    def read_schema(self) -> dict[str, Any]:
        schema = self._operation(
            "04 SCHEMA",
            "retrieve data-source schema",
            lambda: self.client.data_sources.retrieve(
                data_source_id=self.target.data_source_id
            ),
        )
        properties = schema.get("properties") or {}
        self.title_property = next(
            (
                str(name)
                for name, definition in properties.items()
                if definition.get("type") == "title"
            ),
            "Name",
        )
        self.trace[-1].update(
            {
                "title_property": self.title_property,
                "required_properties": [self.title_property],
                "schema_properties": sorted(str(name) for name in properties),
            }
        )
        return schema

    def create_record(self, name: str) -> str:
        properties = {self.title_property: {"title": _text(name)}}
        page = self._operation(
            "05 CREATE",
            "create page",
            lambda: self.client.pages.create(
                parent={
                    "type": "data_source_id",
                    "data_source_id": self.target.data_source_id,
                },
                properties=properties,
            ),
            request_fields=[self.title_property],
            request={self.title_property: name},
        )
        self.last_page_id = str(page.get("id") or "")
        self.last_name = name
        self.trace[-1]["page_id"] = self.last_page_id
        return self.last_page_id

    def read_back(self, page_id: str) -> bool:
        page = self._operation(
            "06 READ BACK",
            "retrieve created page",
            lambda: self.client.pages.retrieve(page_id=page_id),
        )
        actual = _title_value(page.get("properties") or {}, self.title_property)
        matches = actual == self.last_name
        self.trace[-1].update(
            {
                "page_id": str(page.get("id") or page_id),
                "name": actual,
                "value_matches": matches,
            }
        )
        return matches

    def archive(self, page_id: str) -> bool:
        self._operation(
            "08 REVERT",
            "archive exact smoke page",
            lambda: self.client.pages.update(page_id=page_id, in_trash=True),
            request_fields=["in_trash"],
            request={"in_trash": True},
        )
        page = self._operation(
            "09 VERIFY REVERT",
            "retrieve exact page and verify archived state",
            lambda: self.client.pages.retrieve(page_id=page_id),
        )
        archived = bool(page.get("in_trash") or page.get("archived"))
        self.trace[-1].update({"page_id": page_id, "archived": archived})
        if archived:
            self.last_page_id = ""
        return archived

    def run_all(self, message: str, *, run_id: str | None = None) -> bool:
        identifier = run_id or uuid.uuid4().hex[:8]
        self.begin_run(identifier)
        self.instantiate_client()
        value_matches = False
        reverted = False
        failure_step = ""
        try:
            self.test_access()
            self.read_schema()
            name = f"SMOKE TEST — {identifier} · {message.strip()}"
            page_id = self.create_record(name)
            value_matches = self.read_back(page_id)
            self.trace.append(
                {
                    "step": "07 VALUE MATCH",
                    "operation": "compare exact written and retrieved title",
                    "success": value_matches,
                    "page_id": page_id,
                }
            )
        except Exception:
            failure_step = str(self.trace[-1]["step"])

        if self.last_page_id:
            try:
                reverted = self.archive(self.last_page_id)
            except Exception:
                failure_step = failure_step or str(self.trace[-1]["step"])

        passed = value_matches and reverted and not failure_step
        if passed:
            self.trace.append(
                {
                    "step": "RESULT",
                    "result": f"{self.target.environment} SMOKE TEST: PASS",
                    "success": True,
                    "active_record_remains": False,
                }
            )
            return True

        record_remains = bool(self.last_page_id)
        self.trace.append(
            {
                "step": "RESULT",
                "result": (
                    f"{self.target.environment} SMOKE TEST: PARTIAL FAILURE"
                    if record_remains
                    else f"{self.target.environment} SMOKE TEST: FAIL"
                ),
                "failure_step": failure_step or "07 VALUE MATCH",
                "success": False,
                "active_record_remains": record_remains,
                "created_record_id": self.last_page_id if record_remains else "",
            }
        )
        return False
