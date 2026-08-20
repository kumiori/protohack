"""Definition-driven compressed and expanded protocol language."""

from __future__ import annotations

from dataclasses import dataclass

from .models import ExperimentDefinition


@dataclass(frozen=True)
class NegotiationStep:
    message_id: str
    label: str
    sender: str
    receiver: str
    technical: str
    expanded: tuple[str, ...]
    baseline: bool


def negotiation_steps(
    experiment: ExperimentDefinition,
) -> tuple[NegotiationStep, ...]:
    return tuple(
        NegotiationStep(
            message_id=message.id,
            label=message.label,
            sender=message.sender,
            receiver=message.receiver,
            technical=message.technical,
            expanded=message.expanded,
            baseline=message.baseline,
        )
        for message in experiment.messages
    )


def compressed_script(experiment: ExperimentDefinition) -> tuple[str, ...]:
    return tuple(
        step.label for step in negotiation_steps(experiment) if step.baseline
    )
