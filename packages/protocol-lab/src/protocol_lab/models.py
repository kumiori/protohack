"""Immutable, protocol-neutral authoring objects for a protocol experiment."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping


PROVENANCE_KINDS = (
    "technical_fact",
    "historical_claim",
    "interpretive_hypothesis",
    "participant_observation",
)

FAILURE_FAMILIES = (
    "natural",
    "adversary",
    "protocol_response",
    "institutional_policy",
)
FIELD_NOTE_TYPES = ("observation", "interpretation", "critique", "amendment")
INVARIANT_KINDS = ("mechanical", "interpretive")


@dataclass(frozen=True)
class Claim:
    id: str
    text: str
    provenance: str
    source_label: str = ""
    source_url: str = ""


@dataclass(frozen=True)
class EvolutionEntry:
    year: str
    title: str
    description: str
    source_label: str = ""
    source_url: str = ""


@dataclass(frozen=True)
class ProtocolIdentity:
    id: str
    name: str
    source_label: str
    source_url: str
    critical_reflection: str


@dataclass(frozen=True)
class ParticipantDefinition:
    id: str
    label: str
    initial_state: str
    states: tuple[str, ...]


@dataclass(frozen=True)
class MessageDefinition:
    id: str
    label: str
    human_label: str
    sender: str
    receiver: str
    technical: str
    expanded: tuple[str, ...]
    metadata: tuple[tuple[str, str], ...] = ()
    baseline: bool = True


@dataclass(frozen=True)
class TimerDirective:
    id: str
    owner: str
    after_ticks: int


@dataclass(frozen=True)
class TransitionDefinition:
    id: str
    actor: str
    from_state: str
    to_state: str
    trigger: str
    command: str = ""
    on_message: str = ""
    on_timer: str = ""
    emit: tuple[str, ...] = ()
    start_timers: tuple[TimerDirective, ...] = ()
    cancel_timers: tuple[str, ...] = ()
    note: str = ""


@dataclass(frozen=True)
class InvariantDefinition:
    id: str
    kind: str
    description: str
    assertion: Mapping[str, Any]


@dataclass(frozen=True)
class FailureScenario:
    id: str
    family: str
    label: str
    description: str
    operation: str
    applicable_messages: tuple[str, ...] = ()
    message: str = ""
    sender: str = ""
    receiver: str = ""
    delay_ticks: int = 0
    transition: str = ""
    response: str = ""


@dataclass(frozen=True)
class HiddenStateRule:
    id: str
    dimension: str
    trigger_event: str
    level: str
    actor: str
    observation: str
    provenance: str


@dataclass(frozen=True)
class ReflectionPrompt:
    id: str
    trigger_event: str
    question: str
    provenance: str


@dataclass(frozen=True)
class FieldNotePrompt:
    id: str
    note_type: str
    prompt: str


@dataclass(frozen=True)
class ExperimentDefinition:
    schema_version: str
    id: str
    version: str
    status: str
    experiment_number: int
    title: str
    experience_title: str
    atlas_functions: tuple[str, ...]
    question: str
    human_question: str
    rationale_question: str
    rationale: tuple[str, ...]
    shared_capability: str
    reveal: str
    situation: tuple[str, ...]
    need: str
    north_star: str
    protocol: ProtocolIdentity
    archaeology: tuple[Claim, ...]
    evolution: tuple[EvolutionEntry, ...]
    participants: tuple[ParticipantDefinition, ...]
    messages: tuple[MessageDefinition, ...]
    transitions: tuple[TransitionDefinition, ...]
    invariants: tuple[InvariantDefinition, ...]
    failure_scenarios: tuple[FailureScenario, ...]
    hidden_state_rules: tuple[HiddenStateRule, ...]
    reflection_prompts: tuple[ReflectionPrompt, ...]
    field_note_prompts: tuple[FieldNotePrompt, ...]
    completion: Mapping[str, Any]
    completion_status: str
    shippable: bool

    def participant(self, participant_id: str) -> ParticipantDefinition:
        for participant in self.participants:
            if participant.id == participant_id:
                return participant
        raise KeyError(f"Unknown participant: {participant_id}")

    def message(self, message_id: str) -> MessageDefinition:
        for message in self.messages:
            if message.id == message_id:
                return message
        raise KeyError(f"Unknown message: {message_id}")

    def transition(self, transition_id: str) -> TransitionDefinition:
        for transition in self.transitions:
            if transition.id == transition_id:
                return transition
        raise KeyError(f"Unknown transition: {transition_id}")

    def failure(self, failure_id: str) -> FailureScenario:
        for failure in self.failure_scenarios:
            if failure.id == failure_id:
                return failure
        raise KeyError(f"Unknown failure scenario: {failure_id}")
