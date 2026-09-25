from probe_ui import render_registered_probe
from protocol.probe_registry import resolve_probe
from storage.memory import InMemoryRepository


registration = resolve_probe(event_slug="commons-montreal", variant="short")
render_registered_probe(
    registration=registration,
    probe=registration.load(),
    repository=InMemoryRepository(),
    test_mode=False,
)
