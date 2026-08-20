# Trajectory feature registry

| Feature | Route | Status | Owning module | Acceptance test | Dependencies | Class |
|---|---|---|---|---|---|---|
| Independently installable deterministic protocol engine | Build artifact | Implemented | `packages/protocol-lab` | `packages/protocol-lab/tests/test_public_api.py` | PyYAML only | Required |
| Independently installable trajectory reasoning engine | Build artifact | Implemented | `packages/trajectory-engine` | `packages/trajectory-engine/tests/test_public_api.py` | PyYAML only | Required |
| Plan → Now → Goal → Landing → Time onboarding | `/test-sketch-plan` | Implemented | `views/test_sketch_plan.py`, `protocol/timeline_plan.py` | `tests/test_sketch_plan.py` | Streamlit, Plotly | Required |
| Validated landing/time choice gates and Guided value + unit | `/test-sketch-plan` | Implemented | `views/test_sketch_plan.py`, `protocol/timeline_plan.py` | `tests/test_sketch_plan.py` | Streamlit session state | Required |
| Non-uniform qualitative and proportional calendar time axes | Both planning routes | Implemented | `protocol/timeline_plan.py`, planning views | `tests/test_sketch_plan.py` | Plotly | Required |
| Primitive glyph + authored title plot labels | `/test-timeline-game` | Implemented | `protocol/timeline.py`, `views/test_timeline_game.py` | `tests/test_timeline_game.py` | Plotly | Required |
| Release, Event, Gateway, Action, Update, Milestone | `/test-timeline-game` | Implemented | `protocol/timeline.py`, `views/test_timeline_game.py` | `tests/test_timeline_game.py` | Hermite geometry | Required |
| Merge, Share resources, Acquire resources, Delegate, Wait, Prepare, Get intelligence, Synchronise | `/test-timeline-game` | Implemented | `protocol/timeline.py`, `views/test_timeline_game.py` | `tests/test_sketch_plan.py` | Event vocabulary | Required |
| Local, Structural and Dominant influence | `/test-timeline-game` | Implemented | `protocol/timeline.py` | `tests/test_timeline_game.py` | Hermite geometry | Required |
| Gradually and Abruptly direction | `/test-timeline-game` | Implemented | `protocol/timeline.py` | `tests/test_timeline_game.py` | Hermite geometry | Required |
| Continuation and binary Branching topology | `/test-timeline-game` | Implemented | `protocol/timeline.py`, `views/test_timeline_game.py` | `tests/test_timeline_game.py`, `tests/test_sketch_plan.py` | Plotly branch traces | Required |
| Progressive Bifurcation controls | `/test-timeline-game` | Implemented | `views/test_timeline_game.py` | `tests/test_sketch_plan.py` | Streamlit reruns | Required |
| Shared responsive planner type scale | All planning routes | Implemented | planning views | `tests/test_sketch_plan.py` | CSS | Required |
| Named binary branch persistence | Both planning routes | Implemented | `protocol/trajectory_schema.py`, planning views | `tests/test_sketch_plan.py` | YAML, localStorage | Required |
| Optional move description | `/test-timeline-game` | Implemented | `views/test_timeline_game.py`, `protocol/trajectory_schema.py` | `tests/test_sketch_plan.py` | Streamlit forms | Required |
| Local balanced, expanding and contracting uncertainty | `/test-timeline-game` | Implemented | `protocol/timeline.py`, `views/test_timeline_game.py` | `tests/test_timeline_game.py` | Plotly Mesh3d | Required |
| Inspect, edit, remove, undo and integrate | `/test-timeline-game` | Implemented | `views/test_timeline_game.py` | `tests/test_timeline_game.py` | Streamlit session state | Required |
| Local autosave and latest-plan recovery | Both planning routes | Implemented | `protocol/trajectory_schema.py`, planning views | `tests/test_sketch_plan.py` | browser localStorage | Required |
| YAML export, import and migration defaults | Both planning routes | Implemented | `protocol/trajectory_schema.py` | `tests/test_sketch_plan.py` | PyYAML | Required |
| Camera persistence and portable camera | `/test-timeline-game` | Implemented | `views/test_timeline_game.py`, `protocol/trajectory_schema.py` | `tests/test_timeline_game.py` | Plotly, sessionStorage | Required |
| Collective convergence | Benchmark editor | Simulated | `views/test_timeline_game.py` | existing timeline tests | simulated traces | Experimental |
| Branch-specific moves, arbitrary branch trees, merges and probabilities | — | Deferred | — | — | future model work | Experimental |
| Anisotropic/global uncertainty and soft attractors | — | Deferred | — | — | future model work | Experimental |
