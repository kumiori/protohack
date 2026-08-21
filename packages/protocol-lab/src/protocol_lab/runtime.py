"""Small stateful facade over the immutable deterministic engine."""

from __future__ import annotations

from typing import Iterable

from .engine import (
    Command,
    EngineState,
    InvariantResult,
    Replay,
    apply_command,
    initial_state,
    replay as build_replay,
)
from .models import ExperimentDefinition


class ProtocolEngine:
    """Execute one definition while retaining its explicit command history."""

    def __init__(self, definition: ExperimentDefinition) -> None:
        self.definition = definition
        self._commands: list[Command] = []
        self._state = initial_state(definition)

    @property
    def state(self) -> EngineState:
        return self._state

    @property
    def commands(self) -> tuple[Command, ...]:
        return tuple(self._commands)

    def apply(self, command: Command) -> EngineState:
        self._state = apply_command(self.definition, self._state, command)
        self._commands.append(command)
        return self._state

    def apply_all(self, commands: Iterable[Command]) -> EngineState:
        for command in commands:
            self.apply(command)
        return self._state

    def replay(self) -> Replay:
        return build_replay(self.definition, self._commands)

    def evaluate_invariants(self) -> tuple[InvariantResult, ...]:
        return self._state.invariant_results
