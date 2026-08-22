"""Load question semantics kept separate from authored Markdown."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import yaml


@dataclass(frozen=True)
class QuestionDefinition:
    id: str
    title: str
    context: str
    mode: str
    options: tuple[str, ...]
    allow_comment: bool


def load_question_registry(path: Path) -> dict[str, QuestionDefinition]:
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError("The aperture question registry must be a mapping.")
    questions: dict[str, QuestionDefinition] = {}
    for question_id, item in raw.items():
        if not isinstance(item, dict) or item.get("type") != "question":
            raise ValueError(f"{question_id} must define a question.")
        mode = str(item.get("mode") or "")
        if mode not in {"single_choice", "multiple_choice"}:
            raise ValueError(
                f"{question_id} must use single_choice or multiple_choice mode."
            )
        options = tuple(str(option) for option in item.get("options") or ())
        if not str(item.get("title") or "").strip() or not options:
            raise ValueError(f"{question_id} needs a title and at least one option.")
        questions[str(question_id)] = QuestionDefinition(
            id=str(question_id),
            title=str(item["title"]),
            context=str(item.get("context") or ""),
            mode=mode,
            options=options,
            allow_comment=bool(item.get("allow_comment", False)),
        )
    return questions
