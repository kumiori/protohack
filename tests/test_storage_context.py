from __future__ import annotations

import storage.context as context


def test_app_notion_secret_wins_over_generic_legacy_environment_token(
    monkeypatch,
) -> None:
    monkeypatch.delenv("PROTOHACK_NOTION_TOKEN", raising=False)
    monkeypatch.setenv("NOTION_TOKEN", "stale-generic-token")
    monkeypatch.setattr(
        context,
        "_secret",
        lambda section, key: "working-app-token"
        if (section, key) == ("notion", "api_key")
        else "",
    )

    assert context.notion_token() == "working-app-token"


def test_explicit_protohack_environment_override_remains_highest_priority(
    monkeypatch,
) -> None:
    monkeypatch.setenv("PROTOHACK_NOTION_TOKEN", "explicit-protohack-token")
    monkeypatch.setenv("NOTION_TOKEN", "generic-token")
    monkeypatch.setattr(context, "_secret", lambda _section, _key: "app-token")

    assert context.notion_token() == "explicit-protohack-token"
