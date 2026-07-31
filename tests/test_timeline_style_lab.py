from pathlib import Path

from streamlit.testing.v1 import AppTest


ROOT = Path(__file__).parent.parent
APP = ROOT / "app.py"
GAME_VIEW = ROOT / "views" / "test_timeline_game.py"
STYLE_VIEW = ROOT / "views" / "test_timeline_style_lab.py"


def button(app: AppTest, label: str):
    return next(item for item in app.button if item.label == label)


def button_group(app: AppTest, label: str):
    return next(item for item in app.button_group if item.label == label)


def rendered_markdown(app: AppTest) -> str:
    return "\n".join(item.value for item in app.markdown)


def test_style_lab_is_a_registered_visual_only_wrapper() -> None:
    app_source = APP.read_text(encoding="utf-8")
    wrapper_source = STYLE_VIEW.read_text(encoding="utf-8")

    assert '"views/test_timeline_style_lab.py"' in app_source
    assert 'url_path="test-timeline-style-lab"' in app_source
    assert 'with_name("test_timeline_game.py")' in wrapper_source
    assert '"TIMELINE_STYLE_LAB": True' in wrapper_source
    assert "sample_trajectory" not in wrapper_source


def test_style_lab_exposes_three_visual_directions() -> None:
    app = AppTest.from_file(str(STYLE_VIEW), default_timeout=10).run()

    assert not app.exception
    selector = button_group(app, "Visual direction")
    assert selector.options == ["Instrument", "Playground", "Gallery"]
    assert selector.value == "Playground"
    assert app.session_state["timeline_style_lab_variant"] == "Playground"
    assert "Trajectory Style Lab" in rendered_markdown(app)


def test_standard_game_does_not_receive_style_lab_chrome() -> None:
    app = AppTest.from_file(str(GAME_VIEW), default_timeout=10).run()

    assert not app.exception
    assert "Experiment · visual system only" not in rendered_markdown(app)


def test_gallery_changes_presentation_without_changing_gameplay() -> None:
    app = AppTest.from_file(str(STYLE_VIEW), default_timeout=10).run()
    button_group(app, "Visual direction").set_value("Gallery").run()

    assert not app.exception
    assert app.session_state["timeline_style_lab_variant"] == "Gallery"
    assert "height:0; overflow:hidden" in rendered_markdown(app)

    button(app, "★  Release").click().run()

    assert not app.exception
    assert app.session_state["timeline_game_pending_type"] == "release"


def test_information_gateway_uses_the_shared_event_flow() -> None:
    app = AppTest.from_file(str(STYLE_VIEW), default_timeout=10).run()

    button(app, "◈  Information gateway").click().run()

    assert not app.exception
    assert app.session_state["timeline_game_pending_type"] == "gateway"
    assert button(app, "Place information gateway")
    assert any(
        caption.value == "A moment when information is exchanged."
        for caption in app.caption
    )


def test_extended_planning_primitives_are_live_objects() -> None:
    app = AppTest.from_file(str(STYLE_VIEW), default_timeout=10).run()

    for label in (
        "⋈  Merge",
        "⇄  Share resources",
        "◷  Wait",
        "◒  Prepare",
        "⌾  Get intelligence",
        "⟳  Synchronise",
    ):
        assert button(app, label)

    button(app, "⟳  Synchronise").click().run()

    assert not app.exception
    assert app.session_state["timeline_game_pending_type"] == "synchronise"
    assert button(app, "Place synchronise")
    assert any(
        caption.value == "Align timing or state across actors."
        for caption in app.caption
    )


def test_event_objects_have_shape_first_hover_motion() -> None:
    source = GAME_VIEW.read_text(encoding="utf-8")

    assert 'content:"★"' in source
    assert 'content:"●"' in source
    assert 'content:"◈"' in source
    assert 'content:"▲"' in source
    assert 'content:"■"' in source
    assert 'content:"▼"' in source
    assert 'content:"⋈"' in source
    assert 'content:"⇄"' in source
    assert 'content:"◷"' in source
    assert 'content:"◒"' in source
    assert 'content:"⌾"' in source
    assert 'content:"⟳"' in source
    assert "timeline-star-pulse" in source
    assert "transform:scale(1.12)" in source
    assert "transform:scale(1.12) rotate(45deg)" in source
    assert "transform:rotate(-8deg)" in source
    assert "transition:transform 150ms ease" in source
    assert '"primary"' in source
    assert "Convergence · simulated" in source
