"""Protocol Laboratory atlas and Experiment 01 participant route."""

from pathlib import Path

import streamlit as st

from protocol_lab import load_atlas, load_experiment
from protocol_lab.laboratory_ui import render_atlas_landing, render_laboratory
from storage import get_repository
from track_ui import participant_uuid


ROOT = Path(__file__).parents[1]
SPEC_DIRECTORY = ROOT / "protocol_lab" / "specs"
EXPERIMENT_PATH = SPEC_DIRECTORY / "tcp_handshake_v1.yaml"

experiment = load_experiment(EXPERIMENT_PATH)
atlas = load_atlas(SPEC_DIRECTORY)
repository = get_repository()
participant = participant_uuid()
stage_key = f"protocol_lab_stage_{experiment.id}"
stage = str(st.session_state.get(stage_key) or "atlas")

if stage == "experiment":
    render_laboratory(
        experiment=experiment,
        repository=repository,
        participant_id=participant,
    )
else:
    render_atlas_landing(atlas=atlas, active_experiment=experiment)
