from probe_ui import render_registered_probe
from protocol.probe_registry import resolve_probe
from storage.memory import InMemoryRepository


class NewParticipantRepository(InMemoryRepository):
    def get_probe_trajectory(self, participation_id: str):
        raise RuntimeError("new participant must not perform a hydration read")


registration = resolve_probe(event_slug="commons-montreal", variant="short")
render_registered_probe(
    registration=registration,
    probe=registration.load(),
    repository=NewParticipantRepository(),
    test_mode=True,
)
