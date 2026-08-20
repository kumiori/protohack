"""Smallest useful in-code protocol definition."""

from protocol_lab import Command, ProtocolDefinition, ProtocolEngine
from protocol_lab.models import (
    FieldNotePrompt, InvariantDefinition, ParticipantDefinition, ProtocolIdentity,
    TransitionDefinition,
)

definition = ProtocolDefinition(
    schema_version="protocol_lab_experiment_v1", id="minimal", version="1",
    status="example", experiment_number=1, title="Door", experience_title="Door",
    atlas_functions=("coordinate",), question="Can it open?", human_question="Can it open?",
    rationale_question="Why?", rationale=(), shared_capability="entry", reveal="state",
    situation=("A door is closed.",), need="Open it.", north_star="Open door",
    protocol=ProtocolIdentity("door", "Door", "", "", ""), archaeology=(), evolution=(),
    participants=(ParticipantDefinition("door", "Door", "closed", ("closed", "open")),),
    messages=(), transitions=(TransitionDefinition("open", "door", "closed", "open", "command"),),
    invariants=(InvariantDefinition("opened", "mechanical", "Door opens", {"participant_state": {"participant": "door", "equals": "open"}}),),
    failure_scenarios=(), hidden_state_rules=(), reflection_prompts=(),
    field_note_prompts=tuple(FieldNotePrompt(k, k, k.title()) for k in ("observation", "interpretation", "critique", "amendment")),
    completion={"participant_state": {"participant": "door", "equals": "open"}},
    completion_status="complete", shippable=True,
)

engine = ProtocolEngine(definition)
engine.apply(Command.transition("open"))
print(engine.state.participant_state("door"), engine.replay().replay_hash)
