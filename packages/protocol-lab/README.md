# protocol-lab

`protocol-lab` turns authored protocol definitions into deterministic,
inspectable executions. It has no dependency on Streamlit, Protocol Hack, TCP,
or `trajectory-engine`.

```python
from protocol_lab import Command, ProtocolEngine, load_experiment

definition = load_experiment("protocol.yaml")
engine = ProtocolEngine(definition)
engine.apply(Command.transition("open"))
session = engine.replay()
print(session.replay_hash, engine.evaluate_invariants())
```

## Replay contract

The SHA-256 replay hash covers the definition identity and version, the ordered
serialised commands, the ordered semantic events, and final participant states.
Presentation, wall-clock time, observations, interpretation, and object memory
addresses do not contribute. Any nondeterminism must enter as an explicit
command or authored definition value.

An `Observation` references replay evidence but never changes engine state.

See `examples/minimal_protocol` for a tiny artificial protocol and
`examples/tcp_handshake` for TCP as content rather than architecture.
