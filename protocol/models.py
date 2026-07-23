"""Typed, immutable objects for the commons smoke protocol."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Action:
    id: str
    label: str
    description: str
    semantic_tags: tuple[str, ...]
    capacities: tuple[str, ...]
    resource_types: tuple[str, ...]


@dataclass(frozen=True)
class Decision:
    id: str
    prompt: str
    actions: tuple[Action, ...]

    def action(self, action_id: str) -> Action:
        for candidate in self.actions:
            if candidate.id == action_id:
                return candidate
        raise KeyError(f"Unknown action: {action_id}")


@dataclass(frozen=True)
class Scenario:
    id: str
    title: str
    body: str
    notice: str
    decision: Decision


@dataclass(frozen=True)
class InteractionContract:
    """Participant interaction guarantees declared by the protocol."""

    question_actions: tuple[str, ...]
    feedback_profile: str
    skip_requires_reason: bool
    confirmation_before_integration: bool
    show_textual_return_key: bool
    show_full_verification_hash: bool
    balloons_after_integration: bool


@dataclass(frozen=True)
class Protocol:
    id: str
    version: str
    status: str
    title: str
    session_code: str
    scenario: Scenario
    rationale_prompt: str
    rationale_hint: str
    rationale_id: str
    interaction: InteractionContract
    tagger_version: str
    privacy_version: str
    coordination_consent_version: str
