from importlib import metadata
from pathlib import Path

import probe_engine


ROOT = Path(__file__).parent.parent
PINNED_COMMIT = "5bd7d7dd04c2d294c9421d6f48923fcd3266e7fe"


def test_protocol_hack_uses_the_committed_probe_engine_integration_package() -> None:
    requirements = (ROOT / "requirements.txt").read_text(encoding="utf-8")

    assert metadata.version("probe-engine") == "0.3.0.dev2"
    assert Path(probe_engine.__file__).is_relative_to(ROOT / ".venv")
    assert f"probe-engine @ git+https://github.com/kumiori/ebabbd4ed0a438351e6ca71acb3e8ba8.git@{PINNED_COMMIT}" in requirements
    assert not (ROOT / "packages" / "probe-engine").exists()
