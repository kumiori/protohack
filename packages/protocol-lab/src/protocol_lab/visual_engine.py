"""Protocol-neutral sequence projections for arbitrary renderers."""

from __future__ import annotations

from dataclasses import dataclass

from .engine import EngineState
from .models import ExperimentDefinition
from .scenario_engine import negotiation_steps


@dataclass(frozen=True)
class SequenceRow:
    message_id: str
    label: str
    sender_label: str
    receiver_label: str
    technical: str
    expanded: tuple[str, ...]
    pending_instance_ids: tuple[str, ...]


def sequence_rows(
    experiment: ExperimentDefinition,
    state: EngineState,
) -> tuple[SequenceRow, ...]:
    return tuple(
        SequenceRow(
            message_id=step.message_id,
            label=step.label,
            sender_label=experiment.participant(step.sender).label,
            receiver_label=experiment.participant(step.receiver).label,
            technical=step.technical,
            expanded=step.expanded,
            pending_instance_ids=tuple(
                message.instance_id
                for message in state.pending_messages
                if message.message_id == step.message_id
            ),
        )
        for step in negotiation_steps(experiment)
        if step.baseline
    )
