from pathlib import Path

from streamlit.testing.v1 import AppTest

from protocol.timeline_benchmarks import (
    BENCHMARKS,
    CHALLENGES,
    LEVELS,
    benchmark_by_id,
    benchmarks_for_level,
    challenge_by_id,
)


ROOT = Path(__file__).parent.parent
VIEW = ROOT / "views" / "test_timeline_benchmarks.py"
GAME_VIEW = ROOT / "views" / "test_timeline_game.py"
APP = ROOT / "app.py"


def keyed_button(app: AppTest, key: str):
    matches = [candidate for candidate in app.button if candidate.key == key]
    assert len(matches) == 1
    return matches[0]


def test_eight_levels_progress_from_immediate_to_impossible() -> None:
    assert tuple(LEVELS) == tuple(range(1, 9))
    assert LEVELS[1][0] == "Immediate action"
    assert LEVELS[8][0] == "Impossible problems"
    assert all(benchmarks_for_level(level) for level in LEVELS)


def test_benchmark_catalog_preserves_the_onboarding_examples() -> None:
    titles = {benchmark.title for benchmark in BENCHMARKS}

    assert {
        "Cook dinner for friends",
        "Fix a bicycle puncture",
        "Organise a birthday dinner",
        "Move into a new apartment",
        "Organise a neighbourhood picnic",
        "Organise a scientific workshop",
        "Produce a short documentary",
        "Write a book",
        "Build an open-source project",
        "Design a new public initiative",
        "Reconstruct the Apollo programme",
        "Reconstruct Wikipedia",
        "Reconstruct Linux",
        "Reconstruct the Human Genome Project",
        "Reconstruct the Internet",
        "Climate transition",
        "European AI infrastructure",
        "Peace negotiation",
        "Mars mission",
        "Make Paris bicycle-friendly",
    } <= titles
    hidden = [benchmark for benchmark in BENCHMARKS if benchmark.hidden]
    assert [benchmark.id for benchmark in hidden] == [
        "paris-bicycle-friendly"
    ]
    assert hidden[0] not in benchmarks_for_level(8)


def test_challenge_cards_preserve_constraints_and_privacy() -> None:
    assert [challenge.number for challenge in CHALLENGES] == list(range(1, 7))
    assert challenge_by_id("morning").exercise_minutes == 15
    assert challenge_by_id("dinner-friends").constraints == (
        "Maximum 5 moves",
        "Maximum 1 uncertainty",
    )
    assert challenge_by_id("last-holiday").constraints == (
        "Include 1 kink",
        "Include 1 uncertainty",
        "Include 1 milestone",
    )
    assert challenge_by_id("next-year").private is True


def test_payload_carries_the_selected_horizon_into_the_game() -> None:
    benchmark = benchmark_by_id("scientific-workshop")
    payload = benchmark.payload()

    assert payload["horizon_label"] == "6 months"
    assert payload["horizon_days"] == 180
    assert "Alignment" in payload["vocabulary"]

    challenge_payload = challenge_by_id("phd").payload()
    assert challenge_payload["kind"] == "challenge"
    assert challenge_payload["horizon_days"] == 1825


def test_benchmark_page_is_registered_and_sidebar_first() -> None:
    app_source = APP.read_text(encoding="utf-8")
    view_source = VIEW.read_text(encoding="utf-8")
    game_source = GAME_VIEW.read_text(encoding="utf-8")

    assert '"views/test_timeline_benchmarks.py"' in app_source
    assert 'url_path="test-timeline-benchmarks"' in app_source
    assert 'initial_sidebar_state="expanded"' in app_source
    assert "with st.sidebar:" in view_source
    assert "Experiment brief" in view_source
    assert "Start drawing" in view_source
    assert "Shape reading" in view_source
    assert "with st.sidebar:" in game_source
    assert "rail_column" not in game_source
    assert 'with st.container(key="timeline_stage"):' in game_source


def test_selecting_a_benchmark_updates_the_sidebar_brief() -> None:
    app = AppTest.from_file(str(VIEW), default_timeout=10).run()

    keyed_button(app, "choose_benchmark_bicycle-puncture").click().run()

    assert not app.exception
    assert (
        app.session_state["timeline_benchmarks_selected_id"]
        == "bicycle-puncture"
    )
    rendered = "\n".join(markdown.value for markdown in app.markdown)
    assert "Fix a bicycle puncture" in rendered
    assert "30–60 minutes" in rendered


def test_game_uses_selected_benchmark_without_prefilling_moves() -> None:
    app = AppTest.from_file(str(GAME_VIEW), default_timeout=10)
    app.session_state["timeline_active_benchmark"] = benchmark_by_id(
        "cook-dinner"
    ).payload()
    app.run()

    assert not app.exception
    assert app.session_state["timeline_game_events"] == []
    rendered = "\n".join(markdown.value for markdown in app.markdown)
    assert "Cook dinner for friends" in rendered
    assert "2 hours" in rendered
