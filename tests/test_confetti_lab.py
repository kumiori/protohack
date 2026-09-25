from pathlib import Path

from streamlit.testing.v1 import AppTest

from confetti_burst import VARIANTS


ROOT = Path(__file__).parent.parent


def test_confetti_lab_is_visible_and_offers_bottom_up_variants() -> None:
    app_source = (ROOT / "app.py").read_text(encoding="utf-8")
    burst_source = (ROOT / "confetti_burst.py").read_text(encoding="utf-8")

    assert '"views/test_confetti_lab.py"' in app_source
    assert 'url_path="test-confetti-lab"' in app_source
    assert len(VARIANTS) >= 4
    assert "y:height+8" in burst_source
    assert "p.vy+=s.gravity" in burst_source

    app = AppTest.from_file(str(ROOT / "views" / "test_confetti_lab.py")).run()
    assert not app.exception
    assert app.title[0].value == "Confetti Lab"
    assert app.selectbox[0].value == "garden"
    assert next(button for button in app.button if button.label == "Burst again")
