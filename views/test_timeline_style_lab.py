"""Visual-only variants of the shared trajectory interaction."""

from __future__ import annotations

from pathlib import Path
import runpy


runpy.run_path(
    Path(__file__).with_name("test_timeline_game.py"),
    init_globals={"TIMELINE_STYLE_LAB": True},
    run_name="timeline_style_lab_runtime",
)
