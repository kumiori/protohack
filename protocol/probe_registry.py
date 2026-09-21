"""Application registry for local canonical Probe Engine definitions."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from probe_engine import ProbeDefinition, load_yaml_probe


APP_ROOT = Path(__file__).resolve().parents[1]
QUESTION_SETS = APP_ROOT / "question_sets"
PROBE_ENGINE_COMMIT = "ee367a6d096a2e3d1a578ee5c024faa3c7024f43"


@dataclass(frozen=True)
class RegisteredProbe:
    event_id: str
    event_slug: str
    variant: str
    session_code: str
    probe_id: str
    title: str
    source_path: Path

    def load(self) -> ProbeDefinition:
        probe = load_yaml_probe(self.source_path)
        if probe.id != self.probe_id:
            raise ValueError(
                f"Registered Probe `{self.probe_id}` resolved source `{probe.id}`."
            )
        return probe


@dataclass(frozen=True)
class RegisteredEvent:
    id: str
    slug: str
    title: str
    default_view: str
    results_enabled: bool
    host_enabled: bool
    participant_intro: tuple[str, ...] = ()

    @property
    def probes(self) -> tuple[RegisteredProbe, ...]:
        return tuple(item for item in _REGISTRY if item.event_id == self.id)


_REGISTRY = (
    RegisteredProbe(
        event_id="montreal_communs_2026",
        event_slug="commons-montreal",
        variant="short",
        session_code="montreal_communs_2026",
        probe_id="montreal_communs_data_ai_short_2026",
        title="Forum Communs de données et IA",
        source_path=QUESTION_SETS / "montreal_communs_2026" / "short.yaml",
    ),
    RegisteredProbe(
        event_id="montreal_initial_conditions_2026",
        event_slug="commons-montreal-initial-conditions",
        variant="initial-conditions-v0",
        session_code="montreal_initial_conditions_2026",
        probe_id="montreal_initial_conditions_2026",
        title="Commons Montréal — Conditions initiales",
        source_path=QUESTION_SETS / "montreal_communs_2026" / "initial_conditions_v0.yaml",
    ),
)

_EVENTS = (
    RegisteredEvent(
        id="montreal_communs_2026",
        slug="commons-montreal",
        title="Commons Montréal",
        default_view="probe",
        results_enabled=True,
        host_enabled=True,
        participant_intro=(
            "Sauf indication contraire, plusieurs réponses peuvent être sélectionnées.",
            "Vous pouvez changer d’avis : la relecture finale permettra d’inspecter et de faire évoluer vos réponses. Il n’y a volontairement pas de bouton Retour pendant le parcours ; prenez un instant avant de continuer.",
        ),
    ),
    RegisteredEvent(
        id="montreal_initial_conditions_2026",
        slug="commons-montreal-initial-conditions",
        title="Commons Montréal — Conditions initiales",
        default_view="probe",
        results_enabled=True,
        host_enabled=True,
        participant_intro=(
            "Sauf indication contraire, plusieurs réponses peuvent être sélectionnées.",
            "Chaque question peut être répondue, passée ou signalée, puis relue avant validation.",
        ),
    ),
)


def registered_probes() -> tuple[RegisteredProbe, ...]:
    return _REGISTRY


def registered_events() -> tuple[RegisteredEvent, ...]:
    return _EVENTS


def resolve_event(*, event_id: str = "", slug: str = "") -> RegisteredEvent:
    matches = [
        event
        for event in _EVENTS
        if (not event_id or event.id == event_id) and (not slug or event.slug == slug)
    ]
    if not any((event_id, slug)) or len(matches) != 1:
        raise ValueError(f"No unique registered event for id={event_id!r} slug={slug!r}.")
    return matches[0]


def resolve_probe(
    *,
    session_code: str = "",
    probe_id: str = "",
    event_slug: str = "",
    variant: str = "",
) -> RegisteredProbe:
    matches = [
        entry
        for entry in _REGISTRY
        if (not session_code or entry.session_code == session_code)
        and (not probe_id or entry.probe_id == probe_id)
        and (not event_slug or entry.event_slug == event_slug)
        and (not variant or entry.variant == variant)
    ]
    if not any((session_code, probe_id, event_slug, variant)) or len(matches) != 1:
        raise ValueError(
            "No unique registered Probe for "
            f"event_slug={event_slug!r} variant={variant!r} "
            f"session_code={session_code!r} probe_id={probe_id!r}."
        )
    return matches[0]
