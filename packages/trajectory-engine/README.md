# trajectory-engine

`trajectory-engine` represents intended and realised paths in
time–energy–uncertainty space. It preserves influence, direction, topology,
uncertainty, authorship, and time semantics as distinct concepts.

```python
from trajectory_engine import build_trajectory_document, trajectory_yaml

document = build_trajectory_document(plan=plan, primitives=moves, uncertainty=[])
portable_yaml = trajectory_yaml(document)
```

The package has no UI, Plotly, Streamlit, Protocol Hack, or `protocol-lab`
dependency. `trajectory-plan/v2` is canonical. Unversioned and v1 records use
the documented compatibility normaliser; unknown versions fail explicitly.
Realisation history is append-only, and comparison never manufactures consensus.
