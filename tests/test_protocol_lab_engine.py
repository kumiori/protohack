from pathlib import Path

import pytest

from protocol_lab import (
    Command,
    ProtocolCommandError,
    apply_command,
    initial_state,
    load_experiment,
    replay,
)


SPEC_DIRECTORY = Path(__file__).parent.parent / "protocol_lab" / "specs"


def tcp_experiment():
    return load_experiment(SPEC_DIRECTORY / "tcp_handshake_v1.yaml")


def test_baseline_handshake_executes_through_generic_commands() -> None:
    experiment = tcp_experiment()
    state = initial_state(experiment)

    state = apply_command(
        experiment,
        state,
        Command.transition("client_active_open"),
    )
    assert state.participant_state("client") == "SYN-SENT"
    assert [message.message_id for message in state.pending_messages] == ["syn"]

    state = apply_command(
        experiment,
        state,
        Command.deliver(state.pending_messages[0].instance_id),
    )
    assert state.participant_state("server") == "SYN-RECEIVED"
    assert [message.message_id for message in state.pending_messages] == [
        "syn_ack"
    ]

    state = apply_command(
        experiment,
        state,
        Command.deliver(state.pending_messages[0].instance_id),
    )
    assert state.participant_state("client") == "ESTABLISHED"
    assert [message.message_id for message in state.pending_messages] == ["ack"]

    state = apply_command(
        experiment,
        state,
        Command.deliver(state.pending_messages[0].instance_id),
    )

    assert state.status == "established"
    assert state.participant_states == (
        ("client", "ESTABLISHED"),
        ("server", "ESTABLISHED"),
    )
    assert not state.pending_messages
    assert all(result.status == "holds" for result in state.invariant_results)


def test_commands_reject_state_machine_shortcuts() -> None:
    experiment = tcp_experiment()

    with pytest.raises(ProtocolCommandError) as error:
        apply_command(
            experiment,
            initial_state(experiment),
            Command.transition("server_receives_ack"),
        )

    assert "server" in str(error.value)
    assert "LISTEN" in str(error.value)


def test_engine_completion_is_defined_by_each_experiment() -> None:
    experiment = load_experiment(SPEC_DIRECTORY / "oauth_canary.yaml")
    state = apply_command(
        experiment,
        initial_state(experiment),
        Command.transition("grant"),
    )
    state = apply_command(
        experiment,
        state,
        Command.deliver(state.pending_messages[0].instance_id),
    )

    assert state.participant_states == (
        ("owner", "CONSENTED"),
        ("client", "AUTHORIZED"),
    )
    assert state.status == "complete"


def test_replay_is_deterministic_and_does_not_mutate_the_initial_state() -> None:
    experiment = tcp_experiment()
    start = initial_state(experiment)
    commands = (
        Command.transition("client_active_open"),
        Command.deliver("m0001"),
        Command.deliver("m0002"),
        Command.deliver("m0003"),
    )

    first = replay(experiment, commands)
    second = replay(experiment, commands)

    assert first.replay_hash == second.replay_hash
    assert len(first.replay_hash) == 64
    assert first.final_state == second.final_state
    assert start.status == "ready"
    assert start.events == ()


def test_packet_loss_and_logical_time_produce_a_replayable_retry() -> None:
    experiment = tcp_experiment()
    state = apply_command(
        experiment,
        initial_state(experiment),
        Command.transition("client_active_open"),
    )
    state = apply_command(
        experiment,
        state,
        Command.failure("natural_loss", "m0001"),
    )

    assert not state.pending_messages
    assert state.events[-1].failure_family == "natural"

    state = apply_command(experiment, state, Command.wait(3))

    assert state.tick == 3
    assert [message.message_id for message in state.pending_messages] == ["syn"]
    assert any(event.event_type == "timer_expired" for event in state.events)
    assert any(
        observation.dimension == "Risk"
        and observation.evidence_event_id
        for observation in state.hidden_state_observations
    )
    assert any(
        cue.prompt_id == "reflect_timeout" for cue in state.reflection_cues
    )


def test_forged_message_is_visible_but_cannot_skip_receiver_state() -> None:
    experiment = tcp_experiment()
    state = apply_command(
        experiment,
        initial_state(experiment),
        Command.failure("adversary_forgery"),
    )

    forged = state.pending_messages[0]
    assert forged.message_id == "ack"
    assert forged.manipulated is True

    state = apply_command(
        experiment,
        state,
        Command.deliver(forged.instance_id),
    )

    assert state.participant_state("server") == "LISTEN"
    assert state.events[-1].event_type == "message_rejected"
    assert "LISTEN" in state.events[-1].label


def test_simultaneous_open_converges_without_a_tcp_specific_engine_path() -> None:
    experiment = tcp_experiment()
    commands = (
        Command.transition("client_active_open"),
        Command.transition("server_active_open"),
        Command.deliver("m0001"),
        Command.deliver("m0002"),
        Command.deliver("m0004"),
        Command.deliver("m0003"),
    )

    result = replay(experiment, commands)

    assert result.final_state.participant_state("client") == "ESTABLISHED"
    assert result.final_state.participant_state("server") == "ESTABLISHED"
    assert result.final_state.status == "established"
    assert all(
        invariant.status == "holds"
        for invariant in result.final_state.invariant_results
    )
