"""Execute a TCP definition supplied as content by the consuming project."""

import sys

from protocol_lab import Command, ProtocolEngine, load_experiment

definition = load_experiment(sys.argv[1])
engine = ProtocolEngine(definition)
engine.apply(Command.transition("client_active_open"))
print(engine.replay().replay_hash)
