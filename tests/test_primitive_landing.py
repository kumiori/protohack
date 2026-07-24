from pathlib import Path
import re


ROOT = Path(__file__).parent.parent
VIEW = ROOT / "views" / "test_landing_primitives.py"


def test_primitive_landing_contains_no_authored_html_markup() -> None:
    source = VIEW.read_text(encoding="utf-8")

    assert "unsafe_allow_html" not in source
    assert "st.markdown" not in source
    assert "stylable_container" not in source
    assert re.search(r"<\s*/?\s*[a-zA-Z]", source) is None


def test_primitive_landing_is_registered_under_tests() -> None:
    router = (ROOT / "app.py").read_text(encoding="utf-8")

    assert '"views/test_landing_primitives.py"' in router
    assert 'url_path="test-landing-primitives"' in router
