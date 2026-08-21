"""Validate and compile the checked-in agentic protocol registry snapshot."""

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from agentic_registry import compile_registry, default_registry_path, write_compiled_artifacts


if __name__ == "__main__":
    result = compile_registry(default_registry_path())
    paths = write_compiled_artifacts(result, ROOT / "agentic_registry" / "generated")
    for name, path in paths.items():
        print(f"{name}: {path}")
