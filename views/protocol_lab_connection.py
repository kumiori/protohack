"""Experiment 01 · Connection participant route."""

from pathlib import Path
from uuid import UUID, uuid4

import streamlit as st

from protocol_lab import load_experiment
from protocol_lab.laboratory_ui import render_laboratory
from storage import get_repository
from track_ui import participant_uuid


ROOT = Path(__file__).parents[1]
EXPERIMENT_PATH = ROOT / "protocol_lab" / "specs" / "tcp_handshake_v1.yaml"


def _run_id() -> str:
    """Keep run identity in the URL without exposing participant identity."""
    candidate = str(st.query_params.get("run") or "").strip()
    try:
        value = str(UUID(candidate))
    except (ValueError, AttributeError):
        value = str(uuid4())
        st.query_params["run"] = value
    return value


experiment = load_experiment(EXPERIMENT_PATH)
st.session_state[f"protocol_lab_run_{experiment.id}"] = _run_id()
render_laboratory(
    experiment=experiment,
    repository=get_repository(),
    participant_id=participant_uuid(),
)
