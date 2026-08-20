"""Source-tree adapter for the independently installable trajectory engine."""

from pathlib import Path

_PACKAGE_SOURCE = (
    Path(__file__).resolve().parent.parent
    / "packages"
    / "trajectory-engine"
    / "src"
    / "trajectory_engine"
)
if _PACKAGE_SOURCE.is_dir():
    __path__.append(str(_PACKAGE_SOURCE))

from .public import *  # noqa: F401,F403,E402
