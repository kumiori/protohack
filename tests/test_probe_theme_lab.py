from pathlib import Path

from streamlit.testing.v1 import AppTest

from probe_theme import (
    PALETTES,
    TYPOGRAPHY_PRESET_NAME,
    TYPOGRAPHY_TOKENS,
    contrast_ratio,
    dump_theme_config,
    repository_revision,
    theme_config,
    typography_css,
    typography_for_preset,
)


ROOT = Path(__file__).parent.parent
APP = ROOT / "app.py"
VIEW = ROOT / "views" / "test_probe_theme_lab.py"


def rendered_markdown(app: AppTest) -> str:
    return "\n".join(item.value for item in app.markdown)


def test_theme_lab_is_registered_as_a_developer_page() -> None:
    source = APP.read_text(encoding="utf-8")
    view_source = VIEW.read_text(encoding="utf-8")
    assert '"views/test_probe_theme_lab.py"' in source
    assert 'url_path="test-probe-theme-lab"' in source
    assert "stylable_container" not in view_source
    assert "st.container(key=key)" in view_source
    assert ".st-key-{key}" in view_source


def test_theme_lab_renders_all_specimens_candidates_states_and_compositions() -> None:
    app = AppTest.from_file(str(VIEW), default_timeout=15).run()
    assert not app.exception
    markup = rendered_markdown(app)
    assert TYPOGRAPHY_PRESET_NAME in markup
    for copy in (
        "Communs de données et IA", "Qui suis-je ?", "Genève 2027",
        "Dans quelle position est-ce que je participe ?", "Étape 4 sur 18",
        "BUTTON", "PILL", "INPUT", "SKIP", "CHECKPOINT", "TOAST",
        "1 · LANDING", "6 · FINAL INTEGRATION",
    ):
        assert copy in markup
    for width in (390, 768, 1280, 1600):
        assert f"{width} px" in markup
    assert len(PALETTES) == 4
    assert not [item for item in app.selectbox if item.label == "Typography preset"]
    assert len([item for item in app.button if item.label == "Continuer"]) == 4
    assert len([item for item in app.text_input if item.label == "Votre réponse"]) == 4
    assert next(item for item in app.button if item.label == "Apply preview")


def test_theme_config_is_portable_and_contrast_is_calculated() -> None:
    config = theme_config(TYPOGRAPHY_TOKENS, PALETTES["Palette A · acid signal"])
    exported = dump_theme_config(config)
    assert exported.startswith("typography:")
    assert "palette:" in exported
    assert contrast_ratio("#12211b", "#f3f0e8") > 10


def test_editorial_balanced_v2_is_the_exact_shared_typography_contract() -> None:
    typography = typography_for_preset(TYPOGRAPHY_PRESET_NAME)
    assert TYPOGRAPHY_PRESET_NAME == "editorial-balanced-v2"
    assert typography == TYPOGRAPHY_TOKENS
    assert typography["display"] == {
        "min": 42,
        "max": 52,
        "fluid": "4vw",
        "line_height": 1.02,
        "weight": 800,
        "max_width": "none",
    }
    assert typography["section"]["size"] == 40
    assert typography["section"]["line_height"] == 1.10
    assert typography["question"]["size"] == 23
    assert typography["question"]["line_height"] == 1.25
    assert typography["lead"] == {
        "size": 20,
        "line_height": 1.5,
        "weight": 400,
        "max_width": "62ch",
    }
    assert typography["body"] == {
        "size": 18,
        "line_height": 1.55,
        "weight": 400,
        "max_width": "68ch",
    }
    assert typography["option"]["size"] == 17
    assert typography["helper"]["size"] == 15
    assert typography["metadata"]["size"] == 14
    css = typography_css()
    for declaration in (
        "--type-display:clamp(42px, 4vw, 52px)",
        "--type-section:40px",
        "--type-question:23px",
        "--type-lead:20px",
        "--type-body:18px",
        "--type-option:17px",
        "--type-helper:15px",
        "--type-metadata:14px",
        "--paragraph-spacing:1.25em",
        "--control-min-height:52px",
        "--control-text-offset:1px",
        "--input-min-height:50px",
        "--pill-min-height:2.4rem",
        "--space-question:36px",
    ):
        assert declaration in css


def test_shared_component_geometry_is_explicit_and_content_driven() -> None:
    css = typography_css()
    for declaration in (
        "padding:0.55rem 0.85rem",
        "height:auto",
        "white-space:normal",
        "grid-template-columns:minmax(0, 1fr) auto auto",
        "column-gap:24px",
        "grid-template-areas:\"answer answer\" \"skip flag\"",
        "grid-template-areas:\"continue continue\" \"skip flag\"",
    ):
        assert declaration in css


def test_revision_badge_source_contains_date_time_and_commit() -> None:
    revision = repository_revision()
    assert revision.commit
    assert revision.updated_at
    assert "T" in revision.updated_at or revision.updated_at == "unknown"
