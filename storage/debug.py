"""Schema-neutral disposable sink for canonical Probe submission envelopes."""

from __future__ import annotations

from .memory import InMemoryRepository


class GenericDebugRepository(InMemoryRepository):
    """One process-local test store shared by every registered Probe.

    It deliberately inherits the production repository contract.  Test mode
    changes the destination, never the canonical submission semantics.
    """
