from pathlib import Path

from streamlit.testing.v1 import AppTest

from protocol_lab import (
    Command,
    compressed_script,
    initial_state,
    load_atlas,
    load_experiment,
    sequence_rows,
)
from protocol_lab.laboratory_ui import _list_saved_field_notes


ROOT = Path(__file__).parent.parent
SPEC_DIRECTORY = ROOT / "protocol_lab" / "specs"
APP_ENTRY = ROOT / "app.py"
VIEW = ROOT / "views" / "protocol_lab.py"


def button_by_key(app: AppTest, key: str):
    return next(button for button in app.button if button.key == key)


def rendered_text(app: AppTest) -> str:
    values = [markdown.value for markdown in app.markdown]
    values.extend(title.value for title in app.title)
    values.extend(header.value for header in app.header)
    values.extend(subheader.value for subheader in app.subheader)
    values.extend(caption.value for caption in app.caption)
    values.extend(toast.value for toast in app.toast)
    return "\n".join(values)


def test_field_notes_tolerate_a_repository_loaded_before_the_lab_methods() -> None:
    class LegacyInMemoryRepository:
        pass

    assert _list_saved_field_notes(LegacyInMemoryRepository(), "owner-hash") == []


def test_atlas_is_organized_by_human_function_not_protocol_name() -> None:
    atlas = load_atlas(SPEC_DIRECTORY)

    assert atlas.functions == (
        "Connection",
        "Identity",
        "Discovery",
        "Agreement",
        "Delegation",
        "Synchronisation",
        "Memory",
        "Trust",
        "Exchange",
    )
    assert [entry.experiment.id for entry in atlas.entries_for("Connection")] == [
        "experiment_01_tcp_handshake"
    ]
    assert atlas.entries_for("Identity")[0].experiment.shippable is False


def test_scenario_and_visual_views_are_definition_driven() -> None:
    oauth = load_experiment(SPEC_DIRECTORY / "oauth_canary.yaml")

    assert compressed_script(oauth) == ("Consent",)
    assert sequence_rows(oauth, initial_state(oauth))[0].label == "Consent"
    assert sequence_rows(oauth, initial_state(oauth))[0].expanded == (
        "Owner: You may do this specific thing, for this purpose.",
    )


def test_protocol_laboratory_is_an_additive_registered_route() -> None:
    source = APP_ENTRY.read_text(encoding="utf-8")

    assert '"views/protocol_lab.py"' in source
    assert 'url_path="protocol-lab"' in source
    assert '"views/protocol_lab_host.py"' in source
    assert 'url_path="protocol-lab-host"' in source


def test_participant_can_enter_experiment_and_execute_first_message() -> None:
    app = AppTest.from_file(str(VIEW), default_timeout=10).run()

    assert not app.exception
    text = rendered_text(app)
    assert "Protocol Laboratory" in text
    assert "Experiment 01" in text
    assert "Connection" in text
    assert "Identity" in text

    button_by_key(app, "lab_begin_experiment_01_tcp_handshake").click().run()

    assert not app.exception
    text = rendered_text(app)
    assert "The Handshake" in text
    assert "Think about beginning communication." in text
    assert "How do two parties establish enough shared state" in text
    assert "Two parties want to communicate" in text
    assert "Neither knows whether the other is ready" in text
    assert button_by_key(app, "lab_begin_negotiation")
    assert "Experiment 01 uses the TCP three-way handshake" in text
    assert "Interpretive traces" in text

    button_by_key(app, "lab_begin_negotiation").click().run()

    assert not app.exception
    assert app.session_state["protocol_lab_commands_experiment_01_tcp_handshake"] == [
        Command.transition("client_active_open")
    ]
    text = rendered_text(app)
    assert "I want to begin. Here is where my sequence starts." in text
    assert any("Commitment" in toast.value for toast in app.toast)
    assert button_by_key(app, "lab_guided_deliver_m0001").label == (
        "Send your opening message"
    )
    assert "View packet details" in {expander.label for expander in app.expander}

    button_by_key(app, "lab_guided_deliver_m0001").click().run()

    assert not app.exception
    assert app.session_state["protocol_lab_commands_experiment_01_tcp_handshake"] == [
        Command.transition("client_active_open"),
        Command.deliver("m0001"),
        Command.deliver("m0002"),
    ]
    assert "What changed?" not in rendered_text(app)
    assert app.toast
    assert "Other side: I heard your beginning. Here is mine." in rendered_text(app)
    assert button_by_key(app, "lab_guided_deliver_m0003").label == (
        "Send your confirmation"
    )

    button_by_key(app, "lab_guided_deliver_m0003").click().run()
    assert "What actually happened?" in rendered_text(app)
    assert button_by_key(app, "lab_reveal_compression")

    button_by_key(app, "lab_reveal_compression").click().run()
    text = rendered_text(app)
    assert "This negotiation is compressed into three messages" in text
    assert "Technical architecture · TCP three-way handshake" in text
    assert button_by_key(app, "lab_continue_to_disrupt")

    button_by_key(app, "lab_continue_to_disrupt").click().run()
    assert app.session_state[
        "protocol_lab_current_stage_experiment_01_tcp_handshake"
    ] == "disrupt"
    assert "Run the negotiation again" in rendered_text(app)


def test_technical_layer_is_disclosed_only_when_inspect_is_opened() -> None:
    app = AppTest.from_file(str(VIEW), default_timeout=10).run()
    button_by_key(app, "lab_begin_experiment_01_tcp_handshake").click().run()

    assert "How do two endpoints establish compatible connection state" not in rendered_text(app)

    button_by_key(app, "lab_toggle_inspect").click().run()

    assert not app.exception
    text = rendered_text(app)
    assert "synchronised technical layer" in text
    assert "How do two endpoints establish compatible connection state" in text
    assert "Invariants" in text
