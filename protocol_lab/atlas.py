"""Human-function index for Protocol Laboratory experiments."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .loader import load_experiment
from .models import ExperimentDefinition


ATLAS_FUNCTIONS = (
    "Connection",
    "Identity",
    "Discovery",
    "Agreement",
    "Delegation",
    "Synchronisation",
    "Memory",
    "Trust",
    "Exchange",
)


@dataclass(frozen=True)
class AtlasEntry:
    experiment: ExperimentDefinition
    primary_function: str


@dataclass(frozen=True)
class ProtocolAtlas:
    functions: tuple[str, ...]
    entries: tuple[AtlasEntry, ...]

    def entries_for(self, function: str) -> tuple[AtlasEntry, ...]:
        return tuple(
            entry
            for entry in self.entries
            if function in entry.experiment.atlas_functions
        )


def load_atlas(spec_directory: str | Path) -> ProtocolAtlas:
    experiments = [
        load_experiment(path)
        for path in sorted(Path(spec_directory).glob("*.yaml"))
    ]
    experiments.sort(
        key=lambda experiment: (
            0 if experiment.shippable else 1,
            experiment.experiment_number or 999,
            experiment.title,
        )
    )
    entries = tuple(
        AtlasEntry(
            experiment=experiment,
            primary_function=(experiment.atlas_functions[0]),
        )
        for experiment in experiments
    )
    return ProtocolAtlas(functions=ATLAS_FUNCTIONS, entries=entries)
