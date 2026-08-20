from protocol_lab import Command, ProtocolDefinition, ProtocolEngine
from protocol_lab.models import (
    FieldNotePrompt, InvariantDefinition, ParticipantDefinition, ProtocolIdentity,
    TransitionDefinition,
)


def tiny_definition():
    return ProtocolDefinition(
        schema_version="protocol_lab_experiment_v1", id="tiny", version="1",
        status="example", experiment_number=1, title="Tiny", experience_title="Tiny",
        atlas_functions=("connect",), question="Open?", human_question="Open?",
        rationale_question="Why?", rationale=(), shared_capability="connection",
        reveal="state", situation=("A gate is closed.",), need="Open it.", north_star="Open",
        protocol=ProtocolIdentity("tiny", "Tiny", "", "", ""), archaeology=(), evolution=(),
        participants=(ParticipantDefinition("gate", "Gate", "closed", ("closed", "open")),),
        messages=(), transitions=(TransitionDefinition("open", "gate", "closed", "open", "command"),),
        invariants=(InvariantDefinition("opened", "mechanical", "Gate opens", {"participant_state": {"participant": "gate", "equals": "open"}}),),
        failure_scenarios=(), hidden_state_rules=(), reflection_prompts=(),
        field_note_prompts=tuple(FieldNotePrompt(k, k, k.title()) for k in ("observation", "interpretation", "critique", "amendment")),
        completion={"participant_state": {"participant": "gate", "equals": "open"}},
        completion_status="complete", shippable=True,
    )


def test_public_engine_replays_deterministically():
    definition = tiny_definition()
    first = ProtocolEngine(definition)
    second = ProtocolEngine(definition)
    first.apply(Command.transition("open"))
    second.apply(Command.transition("open"))
    assert first.state.participant_state("gate") == "open"
    assert first.replay().replay_hash == second.replay().replay_hash
    assert first.evaluate_invariants() == second.evaluate_invariants()
