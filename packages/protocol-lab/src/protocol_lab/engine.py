"""Deterministic, protocol-neutral execution engine for laboratory experiments."""

from __future__ import annotations

from dataclasses import asdict, dataclass, replace
import hashlib
import json
from typing import Any, Mapping, Sequence

from .models import ExperimentDefinition, TransitionDefinition


class ProtocolCommandError(ValueError):
    """Raised when a command cannot be applied to the current state."""


@dataclass(frozen=True)
class Command:
    action: str
    transition_id: str = ""
    message_instance_id: str = ""
    ticks: int = 0
    failure_id: str = ""

    @classmethod
    def transition(cls, transition_id: str) -> "Command":
        return cls(action="transition", transition_id=transition_id)

    @classmethod
    def deliver(cls, message_instance_id: str) -> "Command":
        return cls(action="deliver", message_instance_id=message_instance_id)

    @classmethod
    def wait(cls, ticks: int = 1) -> "Command":
        return cls(action="wait", ticks=ticks)

    @classmethod
    def failure(
        cls,
        failure_id: str,
        message_instance_id: str = "",
    ) -> "Command":
        return cls(
            action="failure",
            failure_id=failure_id,
            message_instance_id=message_instance_id,
        )


@dataclass(frozen=True)
class MessageInstance:
    instance_id: str
    message_id: str
    sender: str
    receiver: str
    created_tick: int
    deliver_at: int
    source_event_id: str
    replayed: bool = False
    manipulated: bool = False


@dataclass(frozen=True)
class TimerInstance:
    timer_id: str
    owner: str
    due_tick: int


@dataclass(frozen=True)
class ProtocolEvent:
    event_id: str
    event_type: str
    event_key: str
    tick: int
    label: str
    actor: str = ""
    transition_id: str = ""
    message_id: str = ""
    message_instance_id: str = ""
    failure_id: str = ""
    failure_family: str = ""
    details: tuple[tuple[str, str], ...] = ()


@dataclass(frozen=True)
class InvariantResult:
    invariant_id: str
    kind: str
    description: str
    status: str
    evidence_event_ids: tuple[str, ...]


@dataclass(frozen=True)
class HiddenStateObservation:
    rule_id: str
    dimension: str
    level: str
    actor: str
    observation: str
    provenance: str
    evidence_event_id: str


@dataclass(frozen=True)
class ReflectionCue:
    prompt_id: str
    question: str
    provenance: str
    evidence_event_id: str


@dataclass(frozen=True)
class EngineState:
    experiment_id: str
    experiment_version: str
    tick: int
    participant_states: tuple[tuple[str, str], ...]
    pending_messages: tuple[MessageInstance, ...]
    timers: tuple[TimerInstance, ...]
    events: tuple[ProtocolEvent, ...]
    invariant_results: tuple[InvariantResult, ...]
    hidden_state_observations: tuple[HiddenStateObservation, ...]
    reflection_cues: tuple[ReflectionCue, ...]
    status: str
    next_event_number: int
    next_message_number: int

    def participant_state(self, participant_id: str) -> str:
        try:
            return dict(self.participant_states)[participant_id]
        except KeyError as exc:
            raise KeyError(f"Unknown participant: {participant_id}") from exc


@dataclass(frozen=True)
class Replay:
    experiment_id: str
    experiment_version: str
    commands: tuple[Command, ...]
    final_state: EngineState
    replay_hash: str


def initial_state(experiment: ExperimentDefinition) -> EngineState:
    state = EngineState(
        experiment_id=experiment.id,
        experiment_version=experiment.version,
        tick=0,
        participant_states=tuple(
            (participant.id, participant.initial_state)
            for participant in experiment.participants
        ),
        pending_messages=(),
        timers=(),
        events=(),
        invariant_results=(),
        hidden_state_observations=(),
        reflection_cues=(),
        status="ready",
        next_event_number=1,
        next_message_number=1,
    )
    return replace(state, invariant_results=_evaluate_invariants(experiment, state))


def apply_command(
    experiment: ExperimentDefinition,
    state: EngineState,
    command: Command,
) -> EngineState:
    _check_identity(experiment, state)
    if command.action == "transition":
        transition = experiment.transition(command.transition_id)
        if transition.trigger != "command":
            current = state.participant_state(transition.actor)
            raise ProtocolCommandError(
                f"Transition {transition.id} for {transition.actor} in {current} "
                f"is triggered by {transition.trigger}, not a command."
            )
        result = _apply_transition(experiment, state, transition)
    elif command.action == "deliver":
        result = _deliver(experiment, state, command.message_instance_id)
    elif command.action == "wait":
        result = _wait(experiment, state, command.ticks)
    elif command.action == "failure":
        result = _apply_failure(
            experiment,
            state,
            command.failure_id,
            command.message_instance_id,
        )
    else:
        raise ProtocolCommandError(f"Unknown command action: {command.action}")
    return _finalize(experiment, result)


def replay(
    experiment: ExperimentDefinition,
    commands: Sequence[Command],
) -> Replay:
    state = initial_state(experiment)
    for command in commands:
        state = apply_command(experiment, state, command)
    payload = {
        "experiment_id": experiment.id,
        "experiment_version": experiment.version,
        "commands": [asdict(command) for command in commands],
        "events": [asdict(event) for event in state.events],
        "participant_states": list(state.participant_states),
    }
    replay_hash = hashlib.sha256(
        json.dumps(
            payload,
            sort_keys=True,
            ensure_ascii=False,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()
    return Replay(
        experiment_id=experiment.id,
        experiment_version=experiment.version,
        commands=tuple(commands),
        final_state=state,
        replay_hash=replay_hash,
    )


def _check_identity(
    experiment: ExperimentDefinition,
    state: EngineState,
) -> None:
    if (
        state.experiment_id != experiment.id
        or state.experiment_version != experiment.version
    ):
        raise ProtocolCommandError(
            "Engine state belongs to a different experiment definition."
        )


def _event(
    state: EngineState,
    *,
    event_type: str,
    event_key: str,
    label: str,
    actor: str = "",
    transition_id: str = "",
    message_id: str = "",
    message_instance_id: str = "",
    failure_id: str = "",
    failure_family: str = "",
    details: Mapping[str, Any] | None = None,
) -> tuple[EngineState, ProtocolEvent]:
    event = ProtocolEvent(
        event_id=f"e{state.next_event_number:04d}",
        event_type=event_type,
        event_key=event_key,
        tick=state.tick,
        label=label,
        actor=actor,
        transition_id=transition_id,
        message_id=message_id,
        message_instance_id=message_instance_id,
        failure_id=failure_id,
        failure_family=failure_family,
        details=tuple(
            sorted((str(key), str(value)) for key, value in (details or {}).items())
        ),
    )
    return (
        replace(
            state,
            events=(*state.events, event),
            next_event_number=state.next_event_number + 1,
        ),
        event,
    )


def _apply_transition(
    experiment: ExperimentDefinition,
    state: EngineState,
    transition: TransitionDefinition,
) -> EngineState:
    current = state.participant_state(transition.actor)
    if current != transition.from_state:
        raise ProtocolCommandError(
            f"Participant {transition.actor} is in {current}; transition "
            f"{transition.id} requires {transition.from_state}."
        )

    participant_states = dict(state.participant_states)
    participant_states[transition.actor] = transition.to_state
    state = replace(
        state,
        participant_states=tuple(
            (participant.id, participant_states[participant.id])
            for participant in experiment.participants
        ),
    )
    state, _transition_event = _event(
        state,
        event_type="transition",
        event_key=f"transition:{transition.id}",
        label=(
            f"{experiment.participant(transition.actor).label}: "
            f"{transition.from_state} → {transition.to_state}"
        ),
        actor=transition.actor,
        transition_id=transition.id,
        details={"note": transition.note},
    )

    if transition.cancel_timers:
        state = replace(
            state,
            timers=tuple(
                timer
                for timer in state.timers
                if timer.timer_id not in transition.cancel_timers
            ),
        )

    for message_id in transition.emit:
        state = _emit_message(experiment, state, message_id)

    timers = list(state.timers)
    for directive in transition.start_timers:
        timers = [
            timer
            for timer in timers
            if not (
                timer.timer_id == directive.id
                and timer.owner == directive.owner
            )
        ]
        timers.append(
            TimerInstance(
                timer_id=directive.id,
                owner=directive.owner,
                due_tick=state.tick + directive.after_ticks,
            )
        )
    return replace(state, timers=tuple(timers))


def _emit_message(
    experiment: ExperimentDefinition,
    state: EngineState,
    message_id: str,
    *,
    replayed: bool = False,
    manipulated: bool = False,
    sender: str = "",
    receiver: str = "",
) -> EngineState:
    definition = experiment.message(message_id)
    instance_id = f"m{state.next_message_number:04d}"
    state, event = _event(
        state,
        event_type="message_emitted",
        event_key=f"message_emitted:{message_id}",
        label=f"{definition.label} emitted",
        actor=sender or definition.sender,
        message_id=message_id,
        message_instance_id=instance_id,
        details={"replayed": replayed, "manipulated": manipulated},
    )
    instance = MessageInstance(
        instance_id=instance_id,
        message_id=message_id,
        sender=sender or definition.sender,
        receiver=receiver or definition.receiver,
        created_tick=state.tick,
        deliver_at=state.tick,
        source_event_id=event.event_id,
        replayed=replayed,
        manipulated=manipulated,
    )
    return replace(
        state,
        pending_messages=(*state.pending_messages, instance),
        next_message_number=state.next_message_number + 1,
    )


def _deliver(
    experiment: ExperimentDefinition,
    state: EngineState,
    instance_id: str,
) -> EngineState:
    message = next(
        (
            candidate
            for candidate in state.pending_messages
            if candidate.instance_id == instance_id
        ),
        None,
    )
    if message is None:
        raise ProtocolCommandError(f"Unknown pending message: {instance_id}")
    if message.deliver_at > state.tick:
        raise ProtocolCommandError(
            f"Message {instance_id} is delayed until tick {message.deliver_at}."
        )

    state = replace(
        state,
        pending_messages=tuple(
            candidate
            for candidate in state.pending_messages
            if candidate.instance_id != instance_id
        ),
    )
    definition = experiment.message(message.message_id)
    state, _delivery_event = _event(
        state,
        event_type="message_delivered",
        event_key=f"message_delivered:{message.message_id}",
        label=f"{definition.label} delivered to {message.receiver}",
        actor=message.receiver,
        message_id=message.message_id,
        message_instance_id=message.instance_id,
    )
    current = state.participant_state(message.receiver)
    transition = next(
        (
            candidate
            for candidate in experiment.transitions
            if candidate.trigger == "message"
            and candidate.actor == message.receiver
            and candidate.from_state == current
            and candidate.on_message == message.message_id
        ),
        None,
    )
    if transition is None:
        state, _ = _event(
            state,
            event_type="message_rejected",
            event_key=f"message_rejected:{message.message_id}",
            label=(
                f"{definition.label} has no valid transition for "
                f"{message.receiver} in {current}"
            ),
            actor=message.receiver,
            message_id=message.message_id,
            message_instance_id=message.instance_id,
            details={"state": current},
        )
        return state
    return _apply_transition(experiment, state, transition)


def _wait(
    experiment: ExperimentDefinition,
    state: EngineState,
    ticks: int,
) -> EngineState:
    if ticks < 1:
        raise ProtocolCommandError("Wait requires at least one logical tick.")
    for _ in range(ticks):
        state = replace(state, tick=state.tick + 1)
        state, _ = _event(
            state,
            event_type="clock_advanced",
            event_key="clock_advanced",
            label=f"Logical clock advanced to {state.tick}",
        )
        due = sorted(
            (timer for timer in state.timers if timer.due_tick <= state.tick),
            key=lambda timer: (timer.due_tick, timer.timer_id, timer.owner),
        )
        for timer in due:
            if timer not in state.timers:
                continue
            state = replace(
                state,
                timers=tuple(candidate for candidate in state.timers if candidate != timer),
            )
            state, _ = _event(
                state,
                event_type="timer_expired",
                event_key="timer_expired",
                label=f"{timer.timer_id} expired for {timer.owner}",
                actor=timer.owner,
                details={"timer_id": timer.timer_id},
            )
            current = state.participant_state(timer.owner)
            transition = next(
                (
                    candidate
                    for candidate in experiment.transitions
                    if candidate.trigger == "timer"
                    and candidate.actor == timer.owner
                    and candidate.from_state == current
                    and candidate.on_timer == timer.timer_id
                ),
                None,
            )
            if transition is not None:
                state = _apply_transition(experiment, state, transition)
    return state


def _target_message(
    state: EngineState,
    instance_id: str,
) -> MessageInstance:
    if instance_id:
        target = next(
            (
                message
                for message in state.pending_messages
                if message.instance_id == instance_id
            ),
            None,
        )
        if target is None:
            raise ProtocolCommandError(f"Unknown pending message: {instance_id}")
        return target
    if not state.pending_messages:
        raise ProtocolCommandError("This intervention requires a pending message.")
    return state.pending_messages[0]


def _apply_failure(
    experiment: ExperimentDefinition,
    state: EngineState,
    failure_id: str,
    instance_id: str,
) -> EngineState:
    failure = experiment.failure(failure_id)
    operation = failure.operation
    target: MessageInstance | None = None
    if operation in {"drop", "delay", "duplicate", "reorder", "manipulate"}:
        target = _target_message(state, instance_id)
        if (
            failure.applicable_messages
            and target.message_id not in failure.applicable_messages
        ):
            raise ProtocolCommandError(
                f"{failure.label} does not apply to {target.message_id}."
            )

    state, intervention_event = _event(
        state,
        event_type="intervention",
        event_key=f"intervention:{failure.family}",
        label=failure.label,
        failure_id=failure.id,
        failure_family=failure.family,
        message_id=target.message_id if target else failure.message,
        message_instance_id=target.instance_id if target else "",
        details={"operation": operation, "response": failure.response},
    )

    if operation == "drop" and target:
        return replace(
            state,
            pending_messages=tuple(
                message
                for message in state.pending_messages
                if message.instance_id != target.instance_id
            ),
        )
    if operation == "delay" and target:
        return replace(
            state,
            pending_messages=tuple(
                replace(
                    message,
                    deliver_at=message.deliver_at + max(1, failure.delay_ticks),
                )
                if message.instance_id == target.instance_id
                else message
                for message in state.pending_messages
            ),
        )
    if operation == "duplicate" and target:
        return _copy_message(state, target, replayed=False)
    if operation == "reorder" and target:
        others = [
            message
            for message in state.pending_messages
            if message.instance_id != target.instance_id
        ]
        return replace(state, pending_messages=tuple((*others, target)))
    if operation == "replay":
        replay_target = target
        if replay_target is None:
            candidates = [
                message
                for message in state.pending_messages
                if not failure.applicable_messages
                or message.message_id in failure.applicable_messages
            ]
            if candidates:
                replay_target = candidates[0]
        if replay_target is not None:
            return _copy_message(state, replay_target, replayed=True)
        if not failure.applicable_messages:
            raise ProtocolCommandError("Replay requires a declared message.")
        message_id = failure.applicable_messages[0]
        return _emit_message(experiment, state, message_id, replayed=True)
    if operation == "forge":
        if not failure.message:
            raise ProtocolCommandError("Forgery requires a declared message type.")
        return _emit_message(
            experiment,
            state,
            failure.message,
            replayed=True,
            manipulated=True,
            sender=failure.sender,
            receiver=failure.receiver,
        )
    if operation == "manipulate" and target:
        definition = experiment.message(failure.message)
        return replace(
            state,
            pending_messages=tuple(
                replace(
                    message,
                    message_id=failure.message,
                    sender=definition.sender,
                    receiver=definition.receiver,
                    manipulated=True,
                )
                if message.instance_id == target.instance_id
                else message
                for message in state.pending_messages
            ),
        )
    if operation == "wait":
        return _wait(experiment, state, max(1, failure.delay_ticks))
    if operation == "transition":
        if not failure.transition:
            raise ProtocolCommandError("Policy or protocol response requires a transition.")
        return _apply_transition(
            experiment,
            state,
            experiment.transition(failure.transition),
        )
    raise ProtocolCommandError(f"Unsupported failure operation: {operation}")


def _copy_message(
    state: EngineState,
    source: MessageInstance,
    *,
    replayed: bool,
) -> EngineState:
    copy = replace(
        source,
        instance_id=f"m{state.next_message_number:04d}",
        created_tick=state.tick,
        source_event_id=state.events[-1].event_id,
        replayed=replayed,
    )
    return replace(
        state,
        pending_messages=(*state.pending_messages, copy),
        next_message_number=state.next_message_number + 1,
    )


def _finalize(
    experiment: ExperimentDefinition,
    state: EngineState,
) -> EngineState:
    previous = {result.invariant_id: result.status for result in state.invariant_results}
    results = _evaluate_invariants(experiment, state)
    state = replace(state, invariant_results=results)
    for result in results:
        if result.status == "violated" and previous.get(result.invariant_id) != "violated":
            state, _ = _event(
                state,
                event_type="invariant_violated",
                event_key="invariant_violated",
                label=result.description,
                details={"invariant_id": result.invariant_id},
            )

    old_event_ids = {
        observation.evidence_event_id
        for observation in state.hidden_state_observations
    }
    observations = list(state.hidden_state_observations)
    cues = list(state.reflection_cues)
    existing_cues = {
        (cue.prompt_id, cue.evidence_event_id)
        for cue in cues
    }
    for event in state.events:
        if event.event_id not in old_event_ids:
            for rule in experiment.hidden_state_rules:
                if rule.trigger_event == event.event_key:
                    observations.append(
                        HiddenStateObservation(
                            rule_id=rule.id,
                            dimension=rule.dimension,
                            level=rule.level,
                            actor=rule.actor,
                            observation=rule.observation,
                            provenance=rule.provenance,
                            evidence_event_id=event.event_id,
                        )
                    )
        for prompt in experiment.reflection_prompts:
            key = (prompt.id, event.event_id)
            if prompt.trigger_event == event.event_key and key not in existing_cues:
                cues.append(
                    ReflectionCue(
                        prompt_id=prompt.id,
                        question=prompt.question,
                        provenance=prompt.provenance,
                        evidence_event_id=event.event_id,
                    )
                )
                existing_cues.add(key)

    status = "in_progress"
    participant_states = dict(state.participant_states)
    if _condition(experiment, state, experiment.completion):
        status = experiment.completion_status
    elif any(value == "REFUSED" for value in participant_states.values()):
        status = "refused"
    elif not state.events:
        status = "ready"

    completion_event_key = f"status:{experiment.completion_status}"
    if status == experiment.completion_status and not any(
        event.event_key == completion_event_key for event in state.events
    ):
        state, status_event = _event(
            state,
            event_type="status",
            event_key=completion_event_key,
            label=f"Experiment reached {experiment.completion_status}",
        )
        for rule in experiment.hidden_state_rules:
            if rule.trigger_event == status_event.event_key:
                observations.append(
                    HiddenStateObservation(
                        rule_id=rule.id,
                        dimension=rule.dimension,
                        level=rule.level,
                        actor=rule.actor,
                        observation=rule.observation,
                        provenance=rule.provenance,
                        evidence_event_id=status_event.event_id,
                    )
                )
        for prompt in experiment.reflection_prompts:
            if prompt.trigger_event == status_event.event_key:
                cues.append(
                    ReflectionCue(
                        prompt_id=prompt.id,
                        question=prompt.question,
                        provenance=prompt.provenance,
                        evidence_event_id=status_event.event_id,
                    )
                )

    return replace(
        state,
        hidden_state_observations=tuple(observations),
        reflection_cues=tuple(cues),
        status=status,
    )


def _evaluate_invariants(
    experiment: ExperimentDefinition,
    state: EngineState,
) -> tuple[InvariantResult, ...]:
    evidence = (state.events[-1].event_id,) if state.events else ()
    return tuple(
        InvariantResult(
            invariant_id=invariant.id,
            kind=invariant.kind,
            description=invariant.description,
            status=(
                "holds"
                if _condition(experiment, state, invariant.assertion)
                else "violated"
            ),
            evidence_event_ids=evidence,
        )
        for invariant in experiment.invariants
    )


def _condition(
    experiment: ExperimentDefinition,
    state: EngineState,
    condition: Mapping[str, Any],
) -> bool:
    if "states_are_declared" in condition:
        return all(
            current in experiment.participant(participant_id).states
            for participant_id, current in state.participant_states
        )
    if "messages_are_declared" in condition:
        declared = {message.id for message in experiment.messages}
        return all(message.message_id in declared for message in state.pending_messages)
    if "any_participant_state" in condition:
        expected = str(condition["any_participant_state"])
        return any(current == expected for _, current in state.participant_states)
    if "all_participants_state" in condition:
        expected = str(condition["all_participants_state"])
        return bool(state.participant_states) and all(
            current == expected for _, current in state.participant_states
        )
    if "pending_message" in condition:
        expected = str(condition["pending_message"])
        return any(message.message_id == expected for message in state.pending_messages)
    if "any_pending_message" in condition:
        return bool(state.pending_messages) is bool(condition["any_pending_message"])
    if "any_active_timer" in condition:
        return bool(state.timers) is bool(condition["any_active_timer"])
    if "participant_state" in condition:
        value = condition["participant_state"]
        if not isinstance(value, Mapping):
            return False
        participant_id = str(value.get("participant") or "")
        expected = str(value.get("equals") or "")
        try:
            return state.participant_state(participant_id) == expected
        except KeyError:
            return False
    if "any" in condition:
        values = condition["any"]
        return isinstance(values, list) and any(
            isinstance(value, Mapping) and _condition(experiment, state, value)
            for value in values
        )
    if "all" in condition:
        values = condition["all"]
        return isinstance(values, list) and all(
            isinstance(value, Mapping) and _condition(experiment, state, value)
            for value in values
        )
    if "not" in condition:
        value = condition["not"]
        return isinstance(value, Mapping) and not _condition(experiment, state, value)
    if "implies" in condition:
        value = condition["implies"]
        if not isinstance(value, Mapping):
            return False
        antecedent = value.get("if")
        consequent = value.get("then")
        if not isinstance(antecedent, Mapping) or not isinstance(consequent, Mapping):
            return False
        return not _condition(experiment, state, antecedent) or _condition(
            experiment,
            state,
            consequent,
        )
    return False
