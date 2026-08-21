"""Load and validate versioned, protocol-neutral experiment definitions."""

from __future__ import annotations

from pathlib import Path
import re
from typing import Any, Iterable, Mapping

import yaml

from .models import (
    FIELD_NOTE_TYPES,
    FAILURE_FAMILIES,
    INVARIANT_KINDS,
    PROVENANCE_KINDS,
    Claim,
    EvolutionEntry,
    ExperimentDefinition,
    FieldNotePrompt,
    FailureScenario,
    HiddenStateRule,
    InvariantDefinition,
    MessageDefinition,
    ParticipantDefinition,
    ProtocolIdentity,
    ReflectionPrompt,
    TimerDirective,
    TransitionDefinition,
)


class ExperimentValidationError(ValueError):
    """Raised when an experiment cannot satisfy the laboratory contract."""


class StringSafeLoader(yaml.SafeLoader):
    """Safe loader that preserves authored yes/no values as strings."""


for _first_character, _resolvers in list(
    StringSafeLoader.yaml_implicit_resolvers.items()
):
    StringSafeLoader.yaml_implicit_resolvers[_first_character] = [
        resolver
        for resolver in _resolvers
        if resolver[0] != "tag:yaml.org,2002:bool"
    ]
StringSafeLoader.add_constructor(
    "tag:yaml.org,2002:bool",
    lambda loader, node: loader.construct_scalar(node).lower() == "true",
)
StringSafeLoader.add_implicit_resolver(
    "tag:yaml.org,2002:bool",
    re.compile(r"^(?:true|True|TRUE|false|False|FALSE)$"),
    list("tTfF"),
)


def _text(value: Any) -> str:
    return str(value or "").strip()


def _rows(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    return [dict(row) for row in value if isinstance(row, dict)]


def _strings(value: Any) -> tuple[str, ...]:
    if not isinstance(value, list):
        return ()
    return tuple(text for item in value if (text := _text(item)))


def _required(raw: Mapping[str, Any], names: Iterable[str]) -> list[str]:
    return [name for name in names if not raw.get(name)]


def _unique_ids(rows: Iterable[Any], label: str, errors: list[str]) -> None:
    seen: set[str] = set()
    for row in rows:
        value = _text(getattr(row, "id", ""))
        if not value:
            errors.append(f"{label} contains an item without an id")
        elif value in seen:
            errors.append(f"{label} contains duplicate id {value}")
        seen.add(value)


def _claim(row: Mapping[str, Any]) -> Claim:
    return Claim(
        id=_text(row.get("id")),
        text=_text(row.get("text")),
        provenance=_text(row.get("provenance")),
        source_label=_text(row.get("source_label")),
        source_url=_text(row.get("source_url")),
    )


def _evolution(row: Mapping[str, Any]) -> EvolutionEntry:
    return EvolutionEntry(
        year=_text(row.get("year")),
        title=_text(row.get("title")),
        description=_text(row.get("description")),
        source_label=_text(row.get("source_label")),
        source_url=_text(row.get("source_url")),
    )


def _participant(row: Mapping[str, Any]) -> ParticipantDefinition:
    return ParticipantDefinition(
        id=_text(row.get("id")),
        label=_text(row.get("label")),
        initial_state=_text(row.get("initial_state")),
        states=_strings(row.get("states")),
    )


def _message(row: Mapping[str, Any]) -> MessageDefinition:
    metadata = row.get("metadata") if isinstance(row.get("metadata"), dict) else {}
    return MessageDefinition(
        id=_text(row.get("id")),
        label=_text(row.get("label")),
        human_label=_text(row.get("human_label")),
        sender=_text(row.get("sender")),
        receiver=_text(row.get("receiver")),
        technical=_text(row.get("technical")),
        expanded=_strings(row.get("expanded")),
        metadata=tuple(
            sorted((_text(key), _text(value)) for key, value in metadata.items())
        ),
        baseline=row.get("baseline") is not False,
    )


def _timer(row: Mapping[str, Any]) -> TimerDirective:
    return TimerDirective(
        id=_text(row.get("id")),
        owner=_text(row.get("owner")),
        after_ticks=int(row.get("after_ticks") or 0),
    )


def _transition(row: Mapping[str, Any]) -> TransitionDefinition:
    return TransitionDefinition(
        id=_text(row.get("id")),
        actor=_text(row.get("actor")),
        from_state=_text(row.get("from")),
        to_state=_text(row.get("to")),
        trigger=_text(row.get("trigger")),
        command=_text(row.get("command")),
        on_message=_text(row.get("on_message")),
        on_timer=_text(row.get("on_timer")),
        emit=_strings(row.get("emit")),
        start_timers=tuple(_timer(item) for item in _rows(row.get("start_timers"))),
        cancel_timers=_strings(row.get("cancel_timers")),
        note=_text(row.get("note")),
    )


def _invariant(row: Mapping[str, Any]) -> InvariantDefinition:
    assertion = row.get("assert") if isinstance(row.get("assert"), dict) else {}
    return InvariantDefinition(
        id=_text(row.get("id")),
        kind=_text(row.get("kind")),
        description=_text(row.get("description")),
        assertion=dict(assertion),
    )


def _failure(row: Mapping[str, Any]) -> FailureScenario:
    return FailureScenario(
        id=_text(row.get("id")),
        family=_text(row.get("family")),
        label=_text(row.get("label")),
        description=_text(row.get("description")),
        operation=_text(row.get("operation")),
        applicable_messages=_strings(row.get("applicable_messages")),
        message=_text(row.get("message")),
        sender=_text(row.get("sender")),
        receiver=_text(row.get("receiver")),
        delay_ticks=int(row.get("delay_ticks") or 0),
        transition=_text(row.get("transition")),
        response=_text(row.get("response")),
    )


def _hidden_state(row: Mapping[str, Any]) -> HiddenStateRule:
    return HiddenStateRule(
        id=_text(row.get("id")),
        dimension=_text(row.get("dimension")),
        trigger_event=_text(row.get("trigger_event")),
        level=_text(row.get("level")),
        actor=_text(row.get("actor")),
        observation=_text(row.get("observation")),
        provenance=_text(row.get("provenance")),
    )


def _reflection(row: Mapping[str, Any]) -> ReflectionPrompt:
    return ReflectionPrompt(
        id=_text(row.get("id")),
        trigger_event=_text(row.get("trigger_event")),
        question=_text(row.get("question")),
        provenance=_text(row.get("provenance")),
    )


def _field_note_prompt(row: Mapping[str, Any]) -> FieldNotePrompt:
    return FieldNotePrompt(
        id=_text(row.get("id")),
        note_type=_text(row.get("note_type")),
        prompt=_text(row.get("prompt")),
    )


def load_experiment(path: str | Path) -> ExperimentDefinition:
    source = Path(path)
    raw = yaml.load(source.read_text(encoding="utf-8"), Loader=StringSafeLoader)
    if not isinstance(raw, dict):
        raise ExperimentValidationError(f"{source.name}: root must be a mapping")

    required = (
        "schema_version",
        "id",
        "version",
        "title",
        "experience_title",
        "atlas_functions",
        "question",
        "human_question",
        "situation",
        "need",
        "protocol",
        "archaeology",
        "evolution",
        "participants",
        "messages",
        "transitions",
        "invariants",
        "failure_scenarios",
        "hidden_state_rules",
        "reflection_prompts",
        "field_note_prompts",
        "completion",
    )
    missing = _required(raw, required)
    if missing:
        raise ExperimentValidationError(
            f"{source.name}: missing required fields: {', '.join(missing)}"
        )

    protocol_raw = raw.get("protocol")
    if not isinstance(protocol_raw, dict):
        raise ExperimentValidationError(f"{source.name}: protocol must be a mapping")

    experiment = ExperimentDefinition(
        schema_version=_text(raw.get("schema_version")),
        id=_text(raw.get("id")),
        version=_text(raw.get("version")),
        status=_text(raw.get("status")) or "canary",
        experiment_number=int(raw.get("experiment_number") or 0),
        title=_text(raw.get("title")),
        experience_title=_text(raw.get("experience_title")),
        atlas_functions=_strings(raw.get("atlas_functions")),
        question=_text(raw.get("question")),
        human_question=_text(raw.get("human_question")),
        rationale_question=_text(raw.get("rationale_question")),
        rationale=_strings(raw.get("rationale")),
        shared_capability=_text(raw.get("shared_capability")),
        reveal=_text(raw.get("reveal")),
        situation=_strings(raw.get("situation")),
        need=_text(raw.get("need")),
        north_star=_text(raw.get("north_star")),
        protocol=ProtocolIdentity(
            id=_text(protocol_raw.get("id")),
            name=_text(protocol_raw.get("name")),
            source_label=_text(protocol_raw.get("source_label")),
            source_url=_text(protocol_raw.get("source_url")),
            critical_reflection=_text(protocol_raw.get("critical_reflection")),
        ),
        archaeology=tuple(_claim(row) for row in _rows(raw.get("archaeology"))),
        evolution=tuple(_evolution(row) for row in _rows(raw.get("evolution"))),
        participants=tuple(
            _participant(row) for row in _rows(raw.get("participants"))
        ),
        messages=tuple(_message(row) for row in _rows(raw.get("messages"))),
        transitions=tuple(
            _transition(row) for row in _rows(raw.get("transitions"))
        ),
        invariants=tuple(
            _invariant(row) for row in _rows(raw.get("invariants"))
        ),
        failure_scenarios=tuple(
            _failure(row) for row in _rows(raw.get("failure_scenarios"))
        ),
        hidden_state_rules=tuple(
            _hidden_state(row) for row in _rows(raw.get("hidden_state_rules"))
        ),
        reflection_prompts=tuple(
            _reflection(row) for row in _rows(raw.get("reflection_prompts"))
        ),
        field_note_prompts=tuple(
            _field_note_prompt(row) for row in _rows(raw.get("field_note_prompts"))
        ),
        completion=(
            dict(raw.get("completion"))
            if isinstance(raw.get("completion"), dict)
            else {}
        ),
        completion_status=_text(raw.get("completion_status")) or "complete",
        shippable=raw.get("shippable") is True,
    )
    _validate_experiment(experiment, source)
    return experiment


def _validate_experiment(
    experiment: ExperimentDefinition,
    source: Path,
) -> None:
    errors: list[str] = []
    if experiment.schema_version != "protocol_lab_experiment_v1":
        errors.append("schema_version must be protocol_lab_experiment_v1")
    if not experiment.atlas_functions:
        errors.append("atlas_functions must not be empty")
    if not experiment.situation:
        errors.append("situation must not be empty")
    if not experiment.protocol.id or not experiment.protocol.name:
        errors.append("protocol requires id and name")
    if not experiment.completion:
        errors.append("completion must declare a protocol-neutral condition")

    for label, rows in (
        ("archaeology", experiment.archaeology),
        ("participants", experiment.participants),
        ("messages", experiment.messages),
        ("transitions", experiment.transitions),
        ("invariants", experiment.invariants),
        ("failure_scenarios", experiment.failure_scenarios),
        ("hidden_state_rules", experiment.hidden_state_rules),
        ("reflection_prompts", experiment.reflection_prompts),
        ("field_note_prompts", experiment.field_note_prompts),
    ):
        if not rows:
            errors.append(f"{label} must not be empty")
        _unique_ids(rows, label, errors)

    participant_ids = {participant.id for participant in experiment.participants}
    message_ids = {message.id for message in experiment.messages}
    for participant in experiment.participants:
        if not participant.states:
            errors.append(f"participant {participant.id} has no states")
        if participant.initial_state not in participant.states:
            errors.append(
                f"participant {participant.id} initial state is not declared"
            )
    for message in experiment.messages:
        if message.sender not in participant_ids or message.receiver not in participant_ids:
            errors.append(f"message {message.id} references an unknown participant")
        if not message.expanded:
            errors.append(f"message {message.id} has no expanded negotiation")
    for transition in experiment.transitions:
        if transition.actor not in participant_ids:
            errors.append(f"transition {transition.id} has unknown actor")
            continue
        actor = experiment.participant(transition.actor)
        if transition.from_state not in actor.states or transition.to_state not in actor.states:
            errors.append(f"transition {transition.id} references an unknown state")
        if transition.trigger not in {"command", "message", "timer"}:
            errors.append(f"transition {transition.id} has unknown trigger")
        if transition.on_message and transition.on_message not in message_ids:
            errors.append(f"transition {transition.id} has unknown message")
        for emitted in transition.emit:
            if emitted not in message_ids:
                errors.append(f"transition {transition.id} emits unknown message {emitted}")
    for invariant in experiment.invariants:
        if invariant.kind not in INVARIANT_KINDS:
            errors.append(f"invariant {invariant.id} has unknown kind")
        if not invariant.assertion:
            errors.append(f"invariant {invariant.id} has no assertion")
    for failure in experiment.failure_scenarios:
        if failure.family not in FAILURE_FAMILIES:
            errors.append(f"failure {failure.id} has unknown family")
        for message_id in failure.applicable_messages:
            if message_id not in message_ids:
                errors.append(f"failure {failure.id} has unknown message {message_id}")
        if failure.transition:
            try:
                experiment.transition(failure.transition)
            except KeyError:
                errors.append(
                    f"failure {failure.id} has unknown transition {failure.transition}"
                )
    for rule in experiment.hidden_state_rules:
        if rule.provenance not in PROVENANCE_KINDS:
            errors.append(f"hidden-state rule {rule.id} has unknown provenance")
    for prompt in experiment.reflection_prompts:
        if prompt.provenance not in PROVENANCE_KINDS:
            errors.append(f"reflection prompt {prompt.id} has unknown provenance")
    note_types = tuple(prompt.note_type for prompt in experiment.field_note_prompts)
    if note_types != FIELD_NOTE_TYPES:
        errors.append(
            "field_note_prompts must declare observation, interpretation, critique, "
            "and amendment in that order"
        )
    for prompt in experiment.field_note_prompts:
        if not prompt.prompt:
            errors.append(f"field-note prompt {prompt.id} has no prompt")
    for claim in experiment.archaeology:
        if claim.provenance not in PROVENANCE_KINDS:
            errors.append(f"archaeology claim {claim.id} has unknown provenance")

    if errors:
        raise ExperimentValidationError(f"{source.name}: " + "; ".join(errors))
