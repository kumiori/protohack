from event_ui import render_event
import event_ui
from protocol.probe_registry import resolve_event
from storage.base import RepositoryHealth
from storage.memory import InMemoryRepository


class UnavailableRepository(InMemoryRepository):
    def health_check(self) -> RepositoryHealth:
        return RepositoryHealth(
            available=False,
            integration="fuckthesystem",
            data_source_id="unavailable-production-source",
            status="unavailable",
            error_code="object_not_found",
        )


repository = UnavailableRepository()
event_ui.get_repository = lambda: repository
event_ui.repository_mode = lambda: "notion"

render_event(resolve_event(slug="commons-montreal"))
