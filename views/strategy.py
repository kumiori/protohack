"""YAML-flow Strategy participant track with runtime-resolved scenario nodes."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from protocol import (
    build_question_set_submission,
    build_strategic_profile,
    load_protocol,
    load_question_set,
)
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
existing_submission = next(
    (
        row
        for row in repository.list_question_set_submissions(
            bundle.question_set_id
        )
        if str(row.get("participant_uuid") or "") == participant
    ),
    None,
)
existing_profile = repository.get_strategic_profile(
    participant,
    protocol.scenario.id,
    protocol.version,
)

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
    submission = build_question_set_submission(
        bundle=bundle,
        participant_uuid=participant,
        answers=answers,
    )
    action_id = str(answers.get("first_action") or "")
    rationale = str(answers.get("reasoning") or "")
    integrated: dict[str, Any] | None = None
    if action_id:
        profile = build_strategic_profile(
            protocol=protocol,
            participant_uuid=participant,
            action_id=action_id,
            rationale=rationale,
            rationale_skipped=not bool(rationale.strip()),
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
        integrated = repository.integrate_strategic_profile(profile)
    saved_submission = repository.record_question_set_submission(submission)
    return integrated or saved_submission


render_question_track(
    bundle=bundle,
    submit=submit_strategy,
    repository=repository,
    participant_id=participant,
    runtime=runtime,
    completion_copy="Your contribution has entered the Commons Map.",
    next_page="views/commons_map.py",
    next_label="Open the Commons Map →",
    existing_result=existing_submission or existing_profile,
    integration=True,
)
