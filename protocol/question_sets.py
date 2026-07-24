"""Discover and inspect YAML-authored questionnaire bundles."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

import yaml

from .loader import StringSafeLoader


DEFAULT_QUESTION_SET_DIRECTORY = Path(__file__).parent / "specs"

QUESTION_TYPE_LABELS = {
    "contact": "Contact details",
    "location": "Location",
    "multiselect": "Multi-select",
    "review": "Review",
    "scenario": "Scenario",
    "single_choice": "Single choice",
    "text": "Open text",
    "textarea": "Open text",
}

MULTIPLE_CHOICE_TYPES = frozenset({"multiselect", "single_choice"})
OPEN_TEXT_TYPES = frozenset({"text", "textarea"})

ESTIMATED_SECONDS_BY_TYPE = {
    "contact": 60,
    "location": 45,
    "multiselect": 45,
    "review": 30,
    "scenario": 60,
    "single_choice": 30,
    "text": 60,
    "textarea": 90,
}


def _clean(value: Any) -> str:
    return str(value or "").strip()


def _string_list(value: Any) -> tuple[str, ...]:
    if not isinstance(value, list):
        return ()
    return tuple(item for raw in value if (item := _clean(raw)))


def _flatten_option_groups(value: Any) -> tuple[str, ...]:
    if not isinstance(value, dict):
        return ()
    options: list[str] = []
    for group_options in value.values():
        options.extend(_string_list(group_options))
    return tuple(options)


def _default_field_id(question_id: str) -> str:
    return question_id.lower().replace("-", "_").replace(" ", "_")


@dataclass(frozen=True)
class QuestionDefinition:
    id: str
    field_id: str
    input_type: str
    title: str
    group: str
    required: bool
    context: str
    options: tuple[str, ...]
    option_groups: tuple[tuple[str, tuple[str, ...]], ...]
    fields: tuple[str, ...]
    notes: str
    placeholder: str
    allow_other: bool
    node_kind: str
    dynamic: bool
    runtime_source: str

    @property
    def type_label(self) -> str:
        return QUESTION_TYPE_LABELS.get(
            self.input_type,
            self.input_type.replace("_", " ").title() or "Unknown",
        )


@dataclass(frozen=True)
class BundleValidation:
    errors: tuple[str, ...]
    warnings: tuple[str, ...]
    missing_fields: tuple[str, ...]
    unknown_field_types: tuple[str, ...]
    duplicate_ids: tuple[str, ...]

    @property
    def is_valid(self) -> bool:
        return not self.errors


@dataclass(frozen=True)
class QuestionSetBundle:
    id: str
    title: str
    summary: str
    description: str
    campaign_slug: str
    event_slug: str
    session_code: str
    question_set_id: str
    schema_id: str
    version: str
    order: int
    source_path: Path
    loaded_at: datetime
    questions: tuple[QuestionDefinition, ...]
    flow: tuple[str, ...]
    validation: BundleValidation

    @property
    def question_count(self) -> int:
        return len(self.questions)

    @property
    def required_count(self) -> int:
        return sum(question.required for question in self.questions)

    @property
    def optional_count(self) -> int:
        return self.question_count - self.required_count

    @property
    def multiple_choice_count(self) -> int:
        return sum(
            question.input_type in MULTIPLE_CHOICE_TYPES
            for question in self.questions
        )

    @property
    def open_text_count(self) -> int:
        return sum(
            question.input_type in OPEN_TEXT_TYPES for question in self.questions
        )

    @property
    def estimated_seconds(self) -> int:
        return sum(
            ESTIMATED_SECONDS_BY_TYPE.get(question.input_type, 45)
            for question in self.questions
        )

    @property
    def estimated_minutes(self) -> int:
        return max(1, round(self.estimated_seconds / 60))

    def count_nodes(self, node_kind: str) -> int:
        return sum(question.node_kind == node_kind for question in self.questions)


@dataclass(frozen=True)
class QuestionSetCatalog:
    bundles: tuple[QuestionSetBundle, ...]
    loaded_at: datetime
    discovery_errors: tuple[str, ...]

    @property
    def question_ids(self) -> tuple[str, ...]:
        return tuple(question.id for bundle in self.bundles for question in bundle.questions)

    @property
    def duplicate_question_ids(self) -> tuple[str, ...]:
        seen: set[str] = set()
        duplicates: set[str] = set()
        for question_id in self.question_ids:
            if question_id in seen:
                duplicates.add(question_id)
            seen.add(question_id)
        return tuple(sorted(duplicates))

    @property
    def estimated_minutes(self) -> int:
        seconds = sum(bundle.estimated_seconds for bundle in self.bundles)
        return max(1, round(seconds / 60)) if self.bundles else 0


def _question_from_mapping(raw: dict[str, Any]) -> QuestionDefinition:
    question_id = _clean(raw.get("id"))
    option_groups = tuple(
        (_clean(group), _string_list(values))
        for group, values in (raw.get("groups") or {}).items()
        if _clean(group)
    ) if isinstance(raw.get("groups"), dict) else ()
    options = _string_list(raw.get("options")) or _flatten_option_groups(raw.get("groups"))
    input_type = _clean(raw.get("type"))
    return QuestionDefinition(
        id=question_id,
        field_id=_clean(raw.get("field")) or _default_field_id(question_id),
        input_type=input_type,
        title=_clean(raw.get("title")) or QUESTION_TYPE_LABELS.get(input_type, "Untitled"),
        group=_clean(raw.get("group")) or input_type.replace("_", " ").title(),
        required=raw.get("required") is True,
        context=_clean(raw.get("context")),
        options=options,
        option_groups=option_groups,
        fields=_string_list(raw.get("fields")),
        notes=_clean(raw.get("notes")),
        placeholder=_clean(raw.get("placeholder")),
        allow_other=raw.get("allow_other") is True,
        node_kind=_clean(raw.get("node_kind")),
        dynamic=raw.get("dynamic") is True,
        runtime_source=_clean(raw.get("runtime_source")),
    )


def _duplicates(values: Iterable[str]) -> tuple[str, ...]:
    seen: set[str] = set()
    duplicates: set[str] = set()
    for value in values:
        if value in seen:
            duplicates.add(value)
        seen.add(value)
    return tuple(sorted(duplicates))


def _validate_bundle(
    *,
    raw: dict[str, Any],
    questions: tuple[QuestionDefinition, ...],
) -> BundleValidation:
    errors: list[str] = []
    warnings: list[str] = []
    missing_fields: list[str] = []

    metadata = raw.get("metadata")
    if not isinstance(metadata, dict):
        metadata = {}
        errors.append("metadata must be a mapping")

    for field in ("id", "title", "questions"):
        if not raw.get(field):
            missing_fields.append(field)
    for field in (
        "campaign_slug",
        "event_slug",
        "session_code",
        "question_set_id",
        "schema_id",
        "version",
    ):
        if not metadata.get(field):
            missing_fields.append(f"metadata.{field}")

    if missing_fields:
        errors.append("Required bundle fields are missing")

    duplicate_ids = _duplicates(question.id for question in questions if question.id)
    if duplicate_ids:
        errors.append("Question ids must be unique within a bundle")

    unknown_types = tuple(
        sorted(
            {
                question.input_type
                for question in questions
                if question.input_type not in QUESTION_TYPE_LABELS
            }
        )
    )
    if unknown_types:
        errors.append("Unknown question field types are present")

    for index, question in enumerate(questions, start=1):
        prefix = question.id or f"questions[{index}]"
        if not question.id:
            errors.append(f"{prefix}: id is required")
        if not question.input_type:
            errors.append(f"{prefix}: type is required")
        if (
            question.input_type in MULTIPLE_CHOICE_TYPES
            and not question.options
            and not question.dynamic
        ):
            warnings.append(f"{prefix}: choice question has no options")
        if question.field_id == _default_field_id(question.id):
            warnings.append(f"{prefix}: field id was derived from the YAML id")

    return BundleValidation(
        errors=tuple(errors),
        warnings=tuple(warnings),
        missing_fields=tuple(missing_fields),
        unknown_field_types=unknown_types,
        duplicate_ids=duplicate_ids,
    )


def load_question_set(
    path: str | Path,
    *,
    loaded_at: datetime | None = None,
) -> QuestionSetBundle:
    source_path = Path(path)
    with source_path.open("r", encoding="utf-8") as handle:
        raw = yaml.load(handle, Loader=StringSafeLoader)
    if not isinstance(raw, dict):
        raise ValueError(f"{source_path.name}: YAML root must be a mapping")
    if "questions" not in raw:
        raise ValueError(f"{source_path.name}: not a questionnaire bundle")
    if not isinstance(raw.get("questions"), list):
        raise ValueError(f"{source_path.name}: questions must be a list")

    metadata = raw.get("metadata") if isinstance(raw.get("metadata"), dict) else {}
    questions = tuple(
        _question_from_mapping(item)
        for item in raw["questions"]
        if isinstance(item, dict)
    )
    if len(questions) != len(raw["questions"]):
        raise ValueError(f"{source_path.name}: every question must be a mapping")

    validation = _validate_bundle(raw=raw, questions=questions)
    return QuestionSetBundle(
        id=_clean(raw.get("id")),
        title=_clean(raw.get("title")) or source_path.stem.replace("_", " ").title(),
        summary=_clean(raw.get("summary")),
        description=_clean(raw.get("description")),
        campaign_slug=_clean(metadata.get("campaign_slug")),
        event_slug=_clean(metadata.get("event_slug")),
        session_code=_clean(metadata.get("session_code")),
        question_set_id=_clean(metadata.get("question_set_id")),
        schema_id=_clean(metadata.get("schema_id")),
        version=_clean(metadata.get("version")),
        order=int(metadata.get("order") or 100),
        source_path=source_path.resolve(),
        loaded_at=loaded_at or datetime.now(timezone.utc),
        questions=questions,
        flow=_string_list(raw.get("flow")),
        validation=validation,
    )


def load_question_set_catalog(
    directory: str | Path = DEFAULT_QUESTION_SET_DIRECTORY,
) -> QuestionSetCatalog:
    source_directory = Path(directory)
    loaded_at = datetime.now(timezone.utc)
    bundles: list[QuestionSetBundle] = []
    discovery_errors: list[str] = []

    for source_path in sorted(source_directory.glob("*.yaml")):
        try:
            with source_path.open("r", encoding="utf-8") as handle:
                raw = yaml.load(handle, Loader=StringSafeLoader)
        except Exception as exc:
            discovery_errors.append(f"{source_path.name}: {exc}")
            continue
        if not isinstance(raw, dict) or "questions" not in raw:
            continue
        try:
            bundles.append(load_question_set(source_path, loaded_at=loaded_at))
        except Exception as exc:
            discovery_errors.append(f"{source_path.name}: {exc}")

    bundles.sort(key=lambda bundle: (bundle.order, bundle.title.casefold()))
    return QuestionSetCatalog(
        bundles=tuple(bundles),
        loaded_at=loaded_at,
        discovery_errors=tuple(discovery_errors),
    )
