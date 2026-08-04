from pathlib import Path

from streamlit.testing.v1 import AppTest


VIEW = Path(__file__).parent.parent / "views" / "protocol_lab_host.py"


def rendered_text(app: AppTest) -> str:
    values = [markdown.value for markdown in app.markdown]
    values.extend(header.value for header in app.header)
    values.extend(subheader.value for subheader in app.subheader)
    values.extend(caption.value for caption in app.caption)
    return "\n".join(values)


def test_host_requires_authentication_before_showing_research_records() -> None:
    app = AppTest.from_file(str(VIEW), default_timeout=10).run()

    assert not app.exception
    assert "Protocol Laboratory Host" in rendered_text(app)
    assert any(text_input.label == "Host access code" for text_input in app.text_input)
    assert "Field-note records" not in rendered_text(app)


def test_authenticated_host_exposes_contract_provenance_and_diagnostics() -> None:
    app = AppTest.from_file(str(VIEW), default_timeout=10)
    app.session_state["protocol_lab_host_authenticated"] = True
    app.run()

    assert not app.exception
    text = rendered_text(app)
    assert "Fixed laboratory contract" in text
    assert "Experiment 01" in text
    assert "technical_fact" in text
    assert "historical_claim" in text
    assert "interpretive_hypothesis" in text
    assert "Field-note records" in text
    assert set(tab.label for tab in app.tabs) == {
        "Overview",
        "Contract",
        "Provenance",
        "Field notes",
        "Diagnostics",
    }
