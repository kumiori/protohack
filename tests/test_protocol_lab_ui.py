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
ATLAS_VIEW = ROOT / "views" / "protocol_lab.py"
CONNECTION_VIEW = ROOT / "views" / "protocol_lab_connection.py"
FEATURE_REGISTRY = ROOT / "FEATURE_REGISTRY.md"


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
    assert '"views/protocol_lab_connection.py"' in source
    assert 'url_path="protocol-lab-connection"' in source
    assert "._url_path" not in source
    assert '"views/protocol_lab_host.py"' in source
    assert 'url_path="protocol-lab-host"' in source
    registry = FEATURE_REGISTRY.read_text(encoding="utf-8")
    assert "Protocol Atlas organised by human function" in registry
    assert "Human rationale and independent sequence-space narration" in registry
    assert "`/protocol-lab-connection?run=<id>`" in registry


def test_atlas_is_a_stable_entrance_not_a_session_selected_experiment() -> None:
    app = AppTest.from_file(str(ATLAS_VIEW), default_timeout=10).run()

    assert not app.exception
    text = rendered_text(app)
    assert "Protocol Laboratory" in text
    assert "Experiment 01" in text
    assert "Connection" in text
    assert "Identity" in text
    assert "How little must two strangers share before they can begin communicating?" in text
    assert not any(button.key == "lab_begin_negotiation" for button in app.button)
    experiment_link = app.get("link_button")[0].proto
    assert experiment_link.label == "Enter Experiment 01 →"
    assert experiment_link.url == "/protocol-lab-connection"


def test_participant_can_execute_the_spatial_handshake() -> None:
    app = AppTest.from_file(str(CONNECTION_VIEW), default_timeout=10).run()

    assert not app.exception
    text = rendered_text(app)
    assert "The Handshake" in text
    assert "Think about beginning communication." in text
    assert "How little must two strangers share before they can begin communicating?" in text
    assert "How do two parties establish enough shared state" in text
    assert "We can establish a shared coordinate system" in text
    assert "two independent sequence spaces" in text
    assert "Two parties want to communicate" in text
    assert "Neither knows whether the other is ready" in text
    assert button_by_key(app, "lab_begin_negotiation")
    assert "Experiment 01 uses the TCP three-way handshake" in text
    assert "Interpretive traces" in text
    assert "Mode · Interactive" in text
    assert button_by_key(app, "lab_multiplayer_future").disabled
    assert button_by_key(app, "lab_open_archaeology")
    assert app.query_params["run"]

    button_by_key(app, "lab_open_archaeology").click().run()
    archaeology = rendered_text(app)
    assert "Protocol archaeology" in archaeology
    assert "Why was this invented?" in archaeology

    button_by_key(app, "lab_begin_negotiation").click().run()

    assert not app.exception
    assert app.session_state["protocol_lab_commands_experiment_01_tcp_handshake"] == [
        Command.transition("client_active_open")
    ]
    text = rendered_text(app)
    assert "You / Client" in text
    assert "Other side / Server" in text
    assert "Local protocol state" in text
    assert "Sequence" in text
    assert "Step 1 of 3" in text
    assert "Knock" in text
    assert "I want to open a connection." in text
    assert "I will begin counting my stream from 100." in text
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
    assert "I heard you starting at 100, so I expect 101 from you." in rendered_text(app)
    assert "I will begin my own count from 500." in rendered_text(app)
    assert "Confirm" in rendered_text(app)
    assert "I heard that you start at 500, so I expect 501 from you." in rendered_text(app)
    assert "Step 3 of 3" in rendered_text(app)
    assert button_by_key(app, "lab_guided_deliver_m0003").label == (
        "Send your confirmation"
    )

    button_by_key(app, "lab_guided_deliver_m0003").click().run()
    text = rendered_text(app)
    assert "What actually happened?" in text
    assert "Surprisingly little." in text
    assert "They do not need the same starting point" in text
    assert "We can both count, independently" in text
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
    app = AppTest.from_file(str(CONNECTION_VIEW), default_timeout=10).run()

    assert "How do two endpoints establish compatible connection state" not in rendered_text(app)

    button_by_key(app, "lab_toggle_inspect").click().run()

    assert not app.exception
    text = rendered_text(app)
    assert "synchronised technical layer" in text
    assert "How do two endpoints establish compatible connection state" in text
    assert "Invariants" in text
    assert "State transitions" in text
