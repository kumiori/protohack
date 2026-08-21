"""Public API for the UI-independent protocol-lab package."""

from .engine import (
    Command,
    EngineState,
    HiddenStateObservation,
    InvariantResult,
    MessageInstance,
    ProtocolCommandError,
    ProtocolEvent as Event,
    ReflectionCue,
    Replay,
    TimerInstance,
    apply_command,
    initial_state,
    replay,
)
from .loader import ExperimentValidationError, load_experiment
from .models import ExperimentDefinition as ProtocolDefinition
from .observation import Observation
from .runtime import ProtocolEngine

__version__ = "0.1.0"

__all__ = [
    "Command", "EngineState", "Event", "ExperimentValidationError",
    "HiddenStateObservation", "InvariantResult", "MessageInstance",
    "Observation", "ProtocolCommandError", "ProtocolDefinition",
    "ProtocolEngine", "ReflectionCue", "Replay", "TimerInstance",
    "apply_command", "initial_state", "load_experiment",
    "replay",
]
