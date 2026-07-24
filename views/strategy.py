"""YAML-flow Strategy participant track with runtime-resolved scenario nodes."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from protocol import build_strategic_profile, load_protocol, load_question_set
from storage import get_repository
from track_ui import (
    RuntimeOption,
    RuntimeScenario,
    TrackRuntime,
    participant_uuid,
    render_question_track,
)


bundle = load_question_set(
    Path(__file__).parents[1] / "protocol" / "specs" / "strategy_v1.yaml"
)
protocol = load_protocol()
repository = get_repository()
participant = participant_uuid()

runtime = TrackRuntime(
    scenario=RuntimeScenario(
        id=protocol.scenario.id,
        title=protocol.scenario.title,
        body=protocol.scenario.body,
        notice=protocol.scenario.notice,
    ),
    options_by_question={
        "S5": tuple(
            RuntimeOption(
                value=action.id,
                label=action.label,
                description=action.description,
            )
            for action in protocol.scenario.decision.actions
        )
    },
)


def submit_strategy(answers: dict[str, Any]) -> dict[str, Any]:
    action_id = str(answers.get("first_action") or "")
    rationale = str(answers.get("reasoning") or "")
    profile = build_strategic_profile(
        protocol=protocol,
        participant_uuid=participant,
        action_id=action_id,
        rationale=rationale,
    )
    profile.update(
        {
            "campaign_slug": bundle.campaign_slug,
            "event_slug": bundle.event_slug,
            "question_set_id": bundle.question_set_id,
            "schema_id": bundle.schema_id,
            "question_set_version": bundle.version,
            "question_answers": {
                question.id: answers.get(question.field_id)
                for question in bundle.questions
                if question.input_type != "review"
            },
        }
    )
    return repository.integrate_strategic_profile(profile)


render_question_track(
    bundle=bundle,
    submit=submit_strategy,
    runtime=runtime,
    completion_copy="Your strategy has entered the Commons Map.",
    next_page="views/commons_map.py",
    next_label="Open the Commons Map →",
)
