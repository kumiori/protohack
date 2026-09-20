"""Small, explicit Markdown aperture contract."""

from .directives import ApertureDocument, Directive, load_document, split_directives
from .registry import QuestionDefinition, load_question_registry
from .responses import append_response, build_response

__all__ = [
    "ApertureDocument",
    "Directive",
    "QuestionDefinition",
    "append_response",
    "build_response",
    "load_document",
    "load_question_registry",
    "split_directives",
]

