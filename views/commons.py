"""Refined participant experience at /commons."""

from pathlib import Path
import runpy


runpy.run_path(
    str(Path(__file__).with_name("test_smokegun.py")),
    run_name="__commons_flow__",
)
