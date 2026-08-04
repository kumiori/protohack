from pathlib import Path

import pytest

from protocol_lab import ExperimentValidationError, load_experiment


ROOT = Path(__file__).parent.parent
SPEC_DIRECTORY = ROOT / "protocol_lab" / "specs"


def test_tcp_experiment_satisfies_the_fixed_laboratory_contract() -> None:
    experiment = load_experiment(SPEC_DIRECTORY / "tcp_handshake_v1.yaml")

    assert experiment.id == "experiment_01_tcp_handshake"
    assert experiment.experiment_number == 1
    assert experiment.experience_title == "The Handshake"
    assert experiment.situation == (
        "Two parties want to communicate.",
        "Neither knows whether the other is ready.",
    )
    assert experiment.atlas_functions == ("Connection", "Synchronisation")
    assert experiment.question == (
        "How do two endpoints establish compatible connection state before "
        "exchanging a reliable byte stream?"
    )
    assert experiment.human_question == (
        "How do two parties establish enough shared state to begin communicating?"
    )
    assert experiment.need.startswith("Synchronize a shared connection")
    assert experiment.protocol.name == "TCP three-way handshake"
    assert experiment.archaeology
    assert experiment.evolution
    assert experiment.participants
    assert experiment.messages
    assert experiment.transitions
    assert experiment.invariants
    assert experiment.failure_scenarios
    assert experiment.hidden_state_rules
    assert "Symmetry" in {
        rule.dimension for rule in experiment.hidden_state_rules
    }
    assert experiment.reflection_prompts
    assert tuple(prompt.note_type for prompt in experiment.field_note_prompts) == (
        "observation",
        "interpretation",
        "critique",
        "amendment",
    )
    assert {failure.family for failure in experiment.failure_scenarios} == {
        "natural",
        "adversary",
        "protocol_response",
        "institutional_policy",
    }
    assert all(message.expanded for message in experiment.messages)


def test_tcp_baseline_excludes_scenario_only_messages() -> None:
    experiment = load_experiment(SPEC_DIRECTORY / "tcp_handshake_v1.yaml")

    assert [message.id for message in experiment.messages if message.baseline] == [
        "syn",
        "syn_ack",
        "ack",
    ]


@pytest.mark.parametrize(
    "filename,expected_function",
    [
        ("oauth_canary.yaml", "Identity"),
        ("git_canary.yaml", "Memory"),
        ("mcp_canary.yaml", "Delegation"),
    ],
)
def test_future_protocol_canaries_use_the_same_definition_contract(
    filename: str,
    expected_function: str,
) -> None:
    experiment = load_experiment(SPEC_DIRECTORY / filename)

    assert expected_function in experiment.atlas_functions
    assert experiment.question
    assert experiment.human_question
    assert experiment.experience_title
    assert experiment.situation
    assert experiment.need
    assert experiment.invariants
    assert tuple(prompt.note_type for prompt in experiment.field_note_prompts) == (
        "observation",
        "interpretation",
        "critique",
        "amendment",
    )
    assert experiment.shippable is False


def test_incomplete_experiment_is_rejected_at_the_public_loader_boundary(
    tmp_path: Path,
) -> None:
    source = tmp_path / "incomplete.yaml"
    source.write_text(
        """
schema_version: protocol_lab_experiment_v1
id: incomplete
version: v1
title: Incomplete
question: What is missing?
""".strip(),
        encoding="utf-8",
    )

    with pytest.raises(ExperimentValidationError) as error:
        load_experiment(source)

    assert "need" in str(error.value)
    assert "atlas_functions" in str(error.value)
