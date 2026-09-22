"""Canonical visual tokens shared by the Probe surface and its Theme Lab."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from pathlib import Path
import subprocess
from typing import Any, Mapping

import yaml


PROBE_COLORS = {
    "ink": "#12211b",
    "paper": "#f3f0e8",
    "acid": "#d7ff48",
    "mint": "#b9ead7",
    "violet": "#a993ff",
    "coral": "#ff7b61",
}

TYPOGRAPHY_PRESET_NAME = "editorial-balanced-v2"
TYPOGRAPHY_TOKENS: dict[str, dict[str, float | int | str]] = {
    "display": {
        "min": 42,
        "max": 52,
        "fluid": "4vw",
        "line_height": 1.02,
        "weight": 800,
        "max_width": "none",
    },
    "section": {"size": 40, "line_height": 1.10, "weight": 750, "max_width": "none"},
    "question": {"size": 23, "line_height": 1.25, "weight": 700, "max_width": "none"},
    "lead": {"size": 20, "line_height": 1.5, "weight": 400, "max_width": "62ch"},
    "body": {"size": 18, "line_height": 1.55, "weight": 400, "max_width": "68ch"},
    "option": {"size": 17, "line_height": 1.4, "weight": 400, "max_width": "none"},
    "helper": {"size": 15, "line_height": 1.45, "weight": 400, "max_width": "68ch"},
    "validation": {"size": 15, "line_height": 1.45, "weight": 400, "max_width": "68ch"},
    "metadata": {"size": 14, "line_height": 1.4, "weight": 400, "max_width": "none"},
}


def typography_for_preset(name: str) -> dict[str, dict[str, float | int | str]]:
    """Return the one canonical typography preset used by every Probe surface."""

    if name != TYPOGRAPHY_PRESET_NAME:
        raise KeyError(f"Unknown typography preset: {name}")
    return deepcopy(TYPOGRAPHY_TOKENS)


def typography_css() -> str:
    """Return the exact shared CSS contract for editorial-balanced-v2."""

    return """
    :root {
      --type-display:clamp(42px, 4vw, 52px);
      --type-section:40px;
      --type-question:23px;
      --type-lead:20px;
      --type-body:18px;
      --type-option:17px;
      --type-helper:15px;
      --type-metadata:14px;
      --line-display:1.02;
      --line-section:1.10;
      --line-question:1.25;
      --line-lead:1.5;
      --line-body:1.55;
      --line-option:1.40;
      --line-helper:1.45;
      --line-metadata:1.40;
      --paragraph-spacing:1.25em;
      --measure-lead:62ch;
      --measure-body:68ch;
      --space-micro:4px;
      --space-tight:8px;
      --space-12:12px;
      --space-normal:16px;
      --space-related:24px;
      --space-question:36px;
      --space-major:48px;
      --space-section:64px;
      --control-min-height:52px;
      --control-text-offset:1px;
      --input-min-height:50px;
      --pill-min-height:2.4rem;
    }
    [data-testid="stMain"] button:not([data-testid="stBaseButton-pills"]):not([data-testid="stBaseButton-pillsActive"]) {
      min-height:var(--control-min-height);
    }
    [data-testid="stMain"] button:not([data-testid="stBaseButton-pills"]):not([data-testid="stBaseButton-pillsActive"]) p {
      transform:translateY(var(--control-text-offset));
    }
    [data-testid="stMain"] button[data-testid="stBaseButton-pills"],
    [data-testid="stMain"] button[data-testid="stBaseButton-pillsActive"] {
      min-height:var(--pill-min-height);
      height:auto;
      padding:0.55rem 0.85rem;
      white-space:normal;
      text-align:left;
    }
    [data-testid="stMain"] button[data-testid="stBaseButton-pills"] p,
    [data-testid="stMain"] button[data-testid="stBaseButton-pillsActive"] p {
      line-height:1.2 !important;
      white-space:normal;
      overflow:visible;
    }
    [data-testid="stAppViewContainer"] [data-baseweb="input"] > div,
    [data-testid="stAppViewContainer"] [data-baseweb="select"] > div {
      min-height:var(--input-min-height);
    }
    [data-testid="stAppViewContainer"] [data-baseweb="input"] input {
      min-height:var(--input-min-height);
      padding:12px 16px;
    }
    [data-testid="stAppViewContainer"] textarea {
      padding:12px 16px;
    }
    [data-testid="stAppViewContainer"] [data-testid="stRadio"] [role="radiogroup"] {
      gap:15px;
    }
    [data-testid="stAppViewContainer"] [data-testid="stRadio"] label {
      gap:11px;
      align-items:flex-start;
    }
    [data-testid="stAppViewContainer"] [data-testid="stRadio"] label p {
      line-height:1.4 !important;
    }
    [class*="st-key-probe_question_"]:not([class*="st-key-probe_question_row_"]) {
      margin-bottom:var(--space-question);
    }
    [class*="st-key-probe_question_row_"] [data-testid="stHorizontalBlock"] {
      display:grid;
      grid-template-columns:minmax(0, 1fr) auto auto;
      column-gap:24px;
      align-items:start;
    }
    [class*="st-key-probe_question_row_"] [data-testid="stHorizontalBlock"] > [data-testid="stColumn"] {
      width:auto !important;
      min-width:0 !important;
      flex:none !important;
    }
    [class*="st-key-probe_single_actions_"] [data-testid="stHorizontalBlock"] {
      display:grid;
      grid-template-columns:minmax(0, 1fr) auto auto;
      column-gap:24px;
      align-items:start;
    }
    [class*="st-key-probe_single_actions_"] [data-testid="stHorizontalBlock"] > [data-testid="stColumn"] {
      width:auto !important;
      min-width:0 !important;
      flex:none !important;
    }
    @media (max-width:700px) {
      [class*="st-key-probe_question_row_"] [data-testid="stHorizontalBlock"] {
        grid-template-columns:minmax(0, 1fr) auto;
        grid-template-areas:"answer answer" "skip flag";
        row-gap:12px;
      }
      [class*="st-key-probe_question_row_"] [data-testid="stHorizontalBlock"] > [data-testid="stColumn"]:nth-child(1) { grid-area:answer; }
      [class*="st-key-probe_question_row_"] [data-testid="stHorizontalBlock"] > [data-testid="stColumn"]:nth-child(2) { grid-area:flag; }
      [class*="st-key-probe_question_row_"] [data-testid="stHorizontalBlock"] > [data-testid="stColumn"]:nth-child(3) { grid-area:skip; }
      [class*="st-key-probe_single_actions_"] [data-testid="stHorizontalBlock"] {
        grid-template-columns:minmax(0, 1fr) auto;
        grid-template-areas:"continue continue" "skip flag";
        row-gap:12px;
      }
      [class*="st-key-probe_single_actions_"] [data-testid="stHorizontalBlock"] > [data-testid="stColumn"]:nth-child(1) { grid-area:continue; }
      [class*="st-key-probe_single_actions_"] [data-testid="stHorizontalBlock"] > [data-testid="stColumn"]:nth-child(2) { grid-area:skip; }
      [class*="st-key-probe_single_actions_"] [data-testid="stHorizontalBlock"] > [data-testid="stColumn"]:nth-child(3) { grid-area:flag; }
    }
    """.strip()


@dataclass(frozen=True)
class RepositoryRevision:
    commit: str
    updated_at: str


def repository_revision(root: Path | None = None) -> RepositoryRevision:
    """Return the current commit and ISO timestamp, with safe fallbacks."""

    repository = root or Path(__file__).resolve().parent
    try:
        output = subprocess.run(
            ["git", "-C", str(repository), "log", "-1", "--format=%h%n%cI"],
            check=True,
            capture_output=True,
            text=True,
            timeout=2,
        ).stdout.splitlines()
        return RepositoryRevision(commit=output[0], updated_at=output[1])
    except (OSError, subprocess.SubprocessError, IndexError):
        return RepositoryRevision(commit="unavailable", updated_at="unknown")

PALETTES: dict[str, dict[str, str]] = {
    "Palette A · acid signal": {
        "background": "#f3f0e8", "surface": "#fffdf6", "text": "#12211b", "muted": "#647068",
        "primary": "#d7ff48", "primary_text": "#12211b", "secondary": "#fffdf6", "secondary_text": "#12211b",
        "tertiary": "#fffdf6", "selected": "#d7ff48", "focus": "#7157d9", "success": "#2f7d5a",
        "warning": "#a65a00", "error": "#b73232", "checkpoint": "#b9ead7", "disabled": "#d8d9d2",
    },
    "Palette B · quiet violet": {
        "background": "#f4f1eb", "surface": "#fffefd", "text": "#17201d", "muted": "#68706d",
        "primary": "#d4f45a", "primary_text": "#17201d", "secondary": "#e9e4f3", "secondary_text": "#312c3d",
        "tertiary": "#fffefd", "selected": "#cfc3ff", "focus": "#6650c6", "success": "#39785d",
        "warning": "#a55f13", "error": "#b33a45", "checkpoint": "#dcebdc", "disabled": "#dcdcd8",
    },
    "Palette C · violet action": {
        "background": "#f5f2e9", "surface": "#fffdf7", "text": "#15231d", "muted": "#66736b",
        "primary": "#9f86ef", "primary_text": "#171020", "secondary": "#fffdf7", "secondary_text": "#15231d",
        "tertiary": "#fffdf7", "selected": "#d7ff48", "focus": "#4f35a5", "success": "#2e7b59",
        "warning": "#aa6411", "error": "#b33742", "checkpoint": "#b9ead7", "disabled": "#d9dad4",
    },
    "Palette D · mineral": {
        "background": "#edf0ed", "surface": "#fbfcf9", "text": "#10231f", "muted": "#5f706a",
        "primary": "#93e6bd", "primary_text": "#10231f", "secondary": "#dde6e1", "secondary_text": "#17312a",
        "tertiary": "#fbfcf9", "selected": "#c8f078", "focus": "#176f75", "success": "#227454",
        "warning": "#9b650a", "error": "#aa3942", "checkpoint": "#b8ded5", "disabled": "#d5dbd7",
    },
}


def theme_config(typography: Mapping[str, Mapping[str, Any]], palette: Mapping[str, str]) -> dict[str, Any]:
    """Return a detached, compact config suitable for preview/export."""
    return {"typography": deepcopy(dict(typography)), "palette": dict(palette)}


def dump_theme_config(config: Mapping[str, Any]) -> str:
    return yaml.safe_dump(dict(config), sort_keys=False, allow_unicode=True)


def relative_luminance(hex_color: str) -> float:
    channels = [int(hex_color.lstrip("#")[index:index + 2], 16) / 255 for index in (0, 2, 4)]
    linear = [value / 12.92 if value <= 0.04045 else ((value + 0.055) / 1.055) ** 2.4 for value in channels]
    return 0.2126 * linear[0] + 0.7152 * linear[1] + 0.0722 * linear[2]


def contrast_ratio(foreground: str, background: str) -> float:
    bright, dark = sorted((relative_luminance(foreground), relative_luminance(background)), reverse=True)
    return (bright + 0.05) / (dark + 0.05)


def css_variable_declarations() -> str:
    return "; ".join(f"--{name}:{value}" for name, value in PROBE_COLORS.items()) + ";"
