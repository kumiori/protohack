"""Protocol Laboratory Atlas route."""

from pathlib import Path

from protocol_lab import load_atlas, load_experiment
from protocol_lab.laboratory_ui import render_atlas_landing


ROOT = Path(__file__).parents[1]
SPEC_DIRECTORY = ROOT / "protocol_lab" / "specs"
EXPERIMENT_PATH = SPEC_DIRECTORY / "tcp_handshake_v1.yaml"

experiment = load_experiment(EXPERIMENT_PATH)
atlas = load_atlas(SPEC_DIRECTORY)
render_atlas_landing(atlas=atlas, active_experiment=experiment)
