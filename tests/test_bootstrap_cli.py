from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "bootstrap_protohack_notion.py"


def test_direct_verify_resolves_repository_packages(tmp_path: Path) -> None:
    """The documented direct-file invocation must import the application."""

    manifest = tmp_path / "manifest.json"
    manifest.write_text(json.dumps({"databases": {}}), encoding="utf-8")
    environment = os.environ.copy()
    for name in ("NOTION_TOKEN", "PROTOHACK_NOTION_TOKEN"):
        environment.pop(name, None)
    environment["HOME"] = str(tmp_path)

    completed = subprocess.run(
        [sys.executable, str(SCRIPT), "verify", "--manifest", str(manifest)],
        cwd=tmp_path,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )

    assert completed.returncode == 1
    assert "NOTION_TOKEN is required" in completed.stderr
    assert "No module named 'storage'" not in completed.stderr


def test_cli_uses_only_the_selected_token_environment(
    tmp_path: Path,
) -> None:
    source = SCRIPT.read_text(encoding="utf-8")
    assert "from storage.context import notion_token" not in source
    assert 'default="NOTION_TOKEN"' in source

    environment = os.environ.copy()
    environment.pop("NOTION_TOKEN", None)
    environment["CUSTOM_NOTION_TOKEN"] = ""
    completed = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "verify",
            "--manifest",
            str(tmp_path / "missing.json"),
            "--token-env",
            "CUSTOM_NOTION_TOKEN",
        ],
        cwd=tmp_path,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )
    assert completed.returncode == 1
    # Manifest validation happens before any credential read for verify.
    assert "Manifest not found" in completed.stderr
