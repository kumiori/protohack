"""Persistence adapters for Protocol Hack."""

from .base import Repository
from .context import get_repository, repository_mode
from .memory import InMemoryRepository

__all__ = ["InMemoryRepository", "Repository", "get_repository", "repository_mode"]
