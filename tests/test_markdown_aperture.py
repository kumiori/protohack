import json
from pathlib import Path

import pytest

from protocol.aperture import (
    Directive,
    append_response,
    build_response,
    load_document,
    load_question_registry,
    split_directives,
)


ROOT = Path(__file__).parent.parent


def test_authored_markdown_stays_readable_and_scatters_stable_apertures() -> None:
    document = load_document(ROOT / "content" / "experiments" / "first_aperture.md")
    parts = split_directives(document.body)

    assert document.page_id == "first_aperture"
    directive_ids = [part.id for part in parts if isinstance(part, Directive)]
    assert directive_ids == [
        "commons_first_move",
        "attribution_under_transformation",
        "consent_after_transformation",
        "value_return",
        "closure_test",
        "authority_without_center",
        "necessity_or_project",
        "protocol_politics",
        "commons_or_extraction",
        "protocol_engagement",
    ]
    assert all(
        isinstance(parts[index - 1], str) and isinstance(parts[index + 1], str)
        for index, part in enumerate(parts)
        if isinstance(part, Directive)
    )
    assert "A commons does not begin with agreement" in document.body
    assert "What happens after the answer" in document.body


def test_question_wording_is_resolved_from_registry_not_markdown() -> None:
    registry = load_question_registry(
        ROOT / "protocol" / "specs" / "aperture_questions.yaml"
    )
    question = registry["commons_first_move"]

    assert question.title == "What should happen first?"
    assert question.options[0] == "Reveal provenance"
    assert question.options[-1] == "Do nothing yet"
    assert question.allow_comment is True

    assert registry["attribution_under_transformation"].mode == "multiple_choice"
    assert registry["closure_test"].mode == "single_choice"
    document = load_document(ROOT / "content" / "experiments" / "first_aperture.md")
    used_ids = {
        part.id for part in split_directives(document.body) if isinstance(part, Directive)
    }
    assert used_ids == set(registry)


def test_response_trace_is_separate_append_only_jsonl(tmp_path: Path) -> None:
    response = build_response(
        page_id="first_aperture",
        directive_id="commons_first_move",
        participant_id="participant-1",
        status="answered",
        value="Reveal provenance",
        comment="Start here.",
        timestamp="2026-08-22T12:00:00+00:00",
        event_id="7F3A",
    )
    target = tmp_path / "responses" / "first_aperture.jsonl"
    append_response(target, response)
    append_response(target, {**response, "event_id": "7F3B", "status": "flagged"})

    rows = [json.loads(line) for line in target.read_text(encoding="utf-8").splitlines()]
    assert [row["event_id"] for row in rows] == ["7F3A", "7F3B"]
    assert set(rows[0]) == {
        "event_id",
        "timestamp",
        "page_id",
        "directive_id",
        "directive_type",
        "participant_id",
        "status",
        "value",
        "comment",
    }


def test_answer_requires_a_value() -> None:
    with pytest.raises(ValueError, match="Choose a response"):
        build_response(
            page_id="first_aperture",
            directive_id="commons_first_move",
            participant_id="participant-1",
            status="answered",
        )


def test_route_is_registered_and_discovers_markdown_files() -> None:
    router = (ROOT / "app.py").read_text(encoding="utf-8")
    view = (ROOT / "views" / "test_markdown_aperture.py").read_text(encoding="utf-8")

    assert 'url_path="test-markdown-aperture"' in router
    assert 'glob("*.md")' in view
