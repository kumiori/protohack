"""Parse front matter and the single directive supported by the V0 experiment."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re
from typing import Any

import yaml


DIRECTIVE_PATTERN = re.compile(
    r"\{\{\s*(?P<kind>question)\s*:\s*(?P<id>[a-z0-9][a-z0-9_-]*)\s*\}\}"
)


@dataclass(frozen=True)
class Directive:
    kind: str
    id: str


@dataclass(frozen=True)
class ApertureDocument:
    metadata: dict[str, Any]
    body: str
    source_path: Path

    @property
    def page_id(self) -> str:
        return str(self.metadata["id"])


def load_document(path: Path) -> ApertureDocument:
    text = path.read_text(encoding="utf-8")
    match = re.match(r"\A---\s*\n(.*?)\n---\s*\n?(.*)\Z", text, re.DOTALL)
    if not match:
        raise ValueError(f"{path.name} must begin with YAML front matter.")
    metadata = yaml.safe_load(match.group(1))
    if not isinstance(metadata, dict) or not str(metadata.get("id") or "").strip():
        raise ValueError(f"{path.name} front matter must contain a stable id.")
    return ApertureDocument(metadata=metadata, body=match.group(2), source_path=path)


def split_directives(body: str) -> list[str | Directive]:
    """Return ordinary Markdown chunks interleaved with explicit directives."""

    parts: list[str | Directive] = []
    cursor = 0
    for match in DIRECTIVE_PATTERN.finditer(body):
        if match.start() > cursor:
            parts.append(body[cursor : match.start()])
        parts.append(Directive(kind=match.group("kind"), id=match.group("id")))
        cursor = match.end()
    if cursor < len(body):
        parts.append(body[cursor:])
    return parts

