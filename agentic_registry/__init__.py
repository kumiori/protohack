"""Validated compiler boundary for the agentic protocol registry."""

from .compiler import (
    ARTIFACT_CONTRACT_VERSION,
    RegistryCompilation,
    RegistryValidationError,
    StrictDuplicateKeyError,
    compile_registry,
    default_registry_path,
    load_compiled_artifacts,
    load_registry_strict,
    write_compiled_artifacts,
)

__all__ = [
    "ARTIFACT_CONTRACT_VERSION",
    "RegistryCompilation",
    "RegistryValidationError",
    "StrictDuplicateKeyError",
    "compile_registry",
    "default_registry_path",
    "load_compiled_artifacts",
    "load_registry_strict",
    "write_compiled_artifacts",
]
