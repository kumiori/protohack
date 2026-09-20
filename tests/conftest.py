"""Keep automated tests isolated from locally configured production storage."""

from __future__ import annotations

import pytest


@pytest.fixture(autouse=True)
def force_preview_storage_for_tests(monkeypatch: pytest.MonkeyPatch) -> None:
    """Prevent AppTest runs from using a developer's real Notion credential."""

    monkeypatch.setenv("PROTOHACK_DEMO_MODE", "true")
