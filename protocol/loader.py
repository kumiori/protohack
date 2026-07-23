"""Load and validate protocol YAML without YAML 1.1 boolean surprises."""

from __future__ import annotations

from pathlib import Path
import re
from typing import Any

import yaml

from .models import Action, Decision, InteractionContract, Protocol, Scenario


class StringSafeLoader(yaml.SafeLoader):
    """SafeLoader variant where only true/false spellings become booleans."""


for first_character, resolvers in list(StringSafeLoader.yaml_implicit_resolvers.items()):
    StringSafeLoader.yaml_implicit_resolvers[first_character] = [
        resolver for resolver in resolvers if resolver[0] != "tag:yaml.org,2002:bool"
    ]
StringSafeLoader.add_implicit_resolver(
    "tag:yaml.org,2002:bool",
    re.compile(r"^(?:true|True|TRUE|false|False|FALSE)$"),
    list("tTfF"),
)


DEFAULT_PROTOCOL_PATH = Path(__file__).parent / "specs" / "commons_smoke_v1.yaml"


def _required(mapping: dict[str, Any], key: str) -> Any:
    value = mapping.get(key)
    if value is None or value == "":
        raise ValueError(f"Protocol field is required: {key}")
    return value


def _strings(value: Any, *, field: str) -> tuple[str, ...]:
    if not isinstance(value, list) or not value:
        raise ValueError(f"Protocol field must be a non-empty list: {field}")
    return tuple(str(item).strip() for item in value if str(item).strip())


def _boolean(mapping: dict[str, Any], key: str) -> bool:
    value = _required(mapping, key)
    if not isinstance(value, bool):
        raise ValueError(f"Protocol field must be true or false: {key}")
    return value


def load_protocol(path: str | Path = DEFAULT_PROTOCOL_PATH) -> Protocol:
    source = Path(path)
    with source.open("r", encoding="utf-8") as handle:
        raw = yaml.load(handle, Loader=StringSafeLoader)
    if not isinstance(raw, dict):
        raise ValueError("Protocol YAML must contain a mapping.")

    scenario_raw = _required(raw, "scenario")
    interaction_raw = _required(raw, "interaction")
    decision_raw = _required(scenario_raw, "decision")
    actions_raw = _required(decision_raw, "actions")
    if not isinstance(actions_raw, list) or len(actions_raw) < 2:
        raise ValueError("The smoke decision needs at least two actions.")

    action_ids: set[str] = set()
    actions: list[Action] = []
    for index, item in enumerate(actions_raw):
        action_id = str(_required(item, "id"))
        if action_id in action_ids:
            raise ValueError(f"Duplicate action id: {action_id}")
        action_ids.add(action_id)
        actions.append(
            Action(
                id=action_id,
                label=str(_required(item, "label")),
                description=str(_required(item, "description")),
                semantic_tags=_strings(item.get("semantic_tags"), field=f"actions[{index}].semantic_tags"),
                capacities=_strings(item.get("capacities"), field=f"actions[{index}].capacities"),
                resource_types=_strings(item.get("resource_types"), field=f"actions[{index}].resource_types"),
            )
        )

    return Protocol(
        id=str(_required(raw, "id")),
        version=str(_required(raw, "version")),
        status=str(_required(raw, "status")),
        title=str(_required(raw, "title")),
        session_code=str(_required(raw, "session_code")),
        scenario=Scenario(
            id=str(_required(scenario_raw, "id")),
            title=str(_required(scenario_raw, "title")),
            body=str(_required(scenario_raw, "body")),
            notice=str(_required(scenario_raw, "notice")),
            decision=Decision(
                id=str(_required(decision_raw, "id")),
                prompt=str(_required(decision_raw, "prompt")),
                actions=tuple(actions),
            ),
        ),
        rationale_prompt=str(_required(raw, "rationale_prompt")),
        rationale_hint=str(_required(raw, "rationale_hint")),
        rationale_id=str(_required(raw, "rationale_id")),
        interaction=InteractionContract(
            question_actions=_strings(
                interaction_raw.get("question_actions"),
                field="interaction.question_actions",
            ),
            feedback_profile=str(_required(interaction_raw, "feedback_profile")),
            skip_requires_reason=_boolean(interaction_raw, "skip_requires_reason"),
            confirmation_before_integration=_boolean(
                interaction_raw, "confirmation_before_integration"
            ),
            show_textual_return_key=_boolean(
                interaction_raw, "show_textual_return_key"
            ),
            show_full_verification_hash=_boolean(
                interaction_raw, "show_full_verification_hash"
            ),
            balloons_after_integration=_boolean(
                interaction_raw, "balloons_after_integration"
            ),
        ),
        tagger_version=str(_required(raw, "tagger_version")),
        privacy_version=str(_required(raw, "privacy_version")),
        coordination_consent_version=str(_required(raw, "coordination_consent_version")),
    )
