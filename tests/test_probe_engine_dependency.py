from importlib import metadata
from pathlib import Path

import probe_engine


ROOT = Path(__file__).parent.parent
PINNED_COMMIT = "f5bb61a121cd498fde97886c2d226a014d5d4255"


def test_protocol_hack_uses_the_committed_probe_engine_integration_package() -> None:
    requirements = (ROOT / "requirements.txt").read_text(encoding="utf-8")

    assert metadata.version("probe-engine") == "0.3.0.dev6"
    package_path = Path(probe_engine.__file__)
    assert ".venv" in package_path.parts
    assert "site-packages" in package_path.parts
    assert f"probe-engine @ git+https://github.com/kumiori/ebabbd4ed0a438351e6ca71acb3e8ba8.git@{PINNED_COMMIT}" in requirements
    assert not (ROOT / "packages" / "probe-engine").exists()
