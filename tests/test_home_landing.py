from pathlib import Path


HOME_VIEW = Path(__file__).parent.parent / "views" / "home_redirect.py"
APP_ENTRY = Path(__file__).parent.parent / "app.py"


def test_application_root_renders_home_without_redirecting_to_commons() -> None:
    app_source = APP_ENTRY.read_text(encoding="utf-8")
    home_source = HOME_VIEW.read_text(encoding="utf-8")

    home_page_registration = app_source.index('"views/home_redirect.py"')
    default_registration = app_source.index("default=True", home_page_registration)

    assert default_registration > home_page_registration
    assert "st.switch_page" not in home_source
    assert 'class="landing-shell"' in home_source


def test_landing_sidebar_is_local_only_and_preserves_deployed_chrome() -> None:
    app_source = APP_ENTRY.read_text(encoding="utf-8")
    source = HOME_VIEW.read_text(encoding="utf-8")

    assert 'initial_sidebar_state="collapsed"' in app_source
    assert 'data-testid="stSidebarCollapsedControl"' in app_source
    assert "local_debug_enabled(request_url)" in source
    assert "render_local_landing_debug(request_url)" in source
    assert "if not show_local_debug" in source
    assert "__LANDING_SIDEBAR_VISIBILITY__" in source


def test_home_uses_a_living_network_instead_of_a_centralized_orbit() -> None:
    source = HOME_VIEW.read_text(encoding="utf-8")

    assert 'class="living-network"' in source
    assert 'class="commons-core">[[ commons ]]' in source
    assert "Array.from({ length: 34 }" in source
    assert "worldPosition" in source
    assert "rotate3d" in source
    assert "context.ellipse" in source
    assert "unsafe_allow_javascript=True" in source
    assert 'class="orbit-plane ' not in source
    assert 'class="orbit-dot"' not in source


def test_home_network_connections_are_temporary_and_not_only_proximity_based() -> None:
    source = HOME_VIEW.read_text(encoding="utf-8")

    assert "const proximity =" in source
    assert "const affinityBridge =" in source
    assert "quadraticCurveTo" in source
    assert "target > current ? .07 : .018" in source
    assert 'matchMedia("(prefers-reduced-motion: reduce)")' in source
    assert "if (reducedMotion.matches) draw(38)" in source


def test_home_explains_the_simulation_below_the_primary_action() -> None:
    source = HOME_VIEW.read_text(encoding="utf-8")
    button_position = source.index('class="landing-enter"')
    principles_position = source.index('class="landing-principles"')

    assert principles_position > button_position
    assert "<h3>Many actors</h3>" in source
    assert "<h3>Connected choices</h3>" in source
    assert "<h3>Evolving futures</h3>" in source
    assert "Diverse voices<br>shape the system." in source
    assert "Actions influence<br>what comes next." in source
    assert "No fixed path.<br>Multiple possibilities." in source
