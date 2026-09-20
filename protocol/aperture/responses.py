"""Build and append the deliberately small V0 response trace."""

from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
import secrets
from typing import Any


STATUSES = frozenset({"answered", "skipped", "flagged", "answered_and_flagged"})


def build_response(
    *,
    page_id: str,
    directive_id: str,
    participant_id: str,
    status: str,
    value: Any = None,
    comment: str = "",
    timestamp: str | None = None,
    event_id: str | None = None,
) -> dict[str, Any]:
    if status not in STATUSES:
        raise ValueError(f"Unsupported aperture response status: {status}")
    if status in {"answered", "answered_and_flagged"} and not value:
        raise ValueError("Choose a response before continuing.")
    return {
        "event_id": event_id or secrets.token_hex(4).upper(),
        "timestamp": timestamp
        or datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "page_id": page_id,
        "directive_id": directive_id,
        "directive_type": "question",
        "participant_id": participant_id,
        "status": status,
        "value": value,
        "comment": comment.strip(),
    }


def append_response(path: Path, response: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(response, ensure_ascii=False, sort_keys=True) + "\n")
