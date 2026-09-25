from runtime_environment import developer_sidebar_enabled


def test_developer_sidebar_can_be_enabled_explicitly_on_deployed_route(
    monkeypatch,
) -> None:
    monkeypatch.setenv("PROTOHACK_ENVIRONMENT", "production")

    assert developer_sidebar_enabled({}) is False
    assert developer_sidebar_enabled({"developer": "1"}) is True
    assert developer_sidebar_enabled({"developer": "true"}) is True
