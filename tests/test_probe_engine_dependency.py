from importlib import metadata
from pathlib import Path

import probe_engine


ROOT = Path(__file__).parent.parent
PINNED_COMMIT = "ee367a6d096a2e3d1a578ee5c024faa3c7024f43"


def test_protocol_hack_uses_the_committed_probe_engine_integration_package() -> None:
    requirements = (ROOT / "requirements.txt").read_text(encoding="utf-8")

    assert metadata.version("probe-engine") == "0.3.0.dev5"
    assert Path(probe_engine.__file__).is_relative_to(ROOT / ".venv")
    assert f"probe-engine @ git+https://github.com/kumiori/ebabbd4ed0a438351e6ca71acb3e8ba8.git@{PINNED_COMMIT}" in requirements
    assert not (ROOT / "packages" / "probe-engine").exists()
