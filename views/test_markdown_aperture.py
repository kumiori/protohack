"""Experimental Markdown document with one native protocol aperture."""

from pathlib import Path
import uuid

import streamlit as st

from protocol.aperture import load_document, load_question_registry
from protocol.aperture.renderer import render_document


ROOT = Path(__file__).parents[1]
CONTENT_DIRECTORY = ROOT / "content" / "experiments"
REGISTRY_PATH = ROOT / "protocol" / "specs" / "aperture_questions.yaml"
RESPONSE_DIRECTORY = ROOT / "data" / "responses"


documents = {path.stem: path for path in sorted(CONTENT_DIRECTORY.glob("*.md"))}
if not documents:
    st.error("No aperture documents are available.")
    st.stop()

requested = str(st.query_params.get("document") or "first_aperture")
selected = requested if requested in documents else next(iter(documents))
if len(documents) > 1:
    selected = st.selectbox("Document", documents, index=list(documents).index(selected))
    st.query_params["document"] = selected

participant_id = st.session_state.setdefault("aperture_participant_id", str(uuid.uuid4()))
document = load_document(documents[selected])
registry = load_question_registry(REGISTRY_PATH)

render_document(
    document=document,
    registry=registry,
    participant_id=participant_id,
    response_path=RESPONSE_DIRECTORY / f"{document.page_id}.jsonl",
)

with st.expander("How this page is made"):
    st.markdown(
        f"The authored source is `{documents[selected].relative_to(ROOT)}`. Git records "
        "changes to that Markdown; interactions are stored separately as response events."
    )

