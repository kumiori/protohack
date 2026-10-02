"""Offline route harness; never connects to Notion."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
import streamlit as st
st.set_page_config(initial_sidebar_state="collapsed", layout="wide")
import event_ui
from protocol.probe_registry import resolve_event
from storage.memory import InMemoryRepository

event_ui.get_repository = lambda: InMemoryRepository()
event_ui.get_test_repository = lambda: InMemoryRepository()
event_ui.repository_mode = lambda: 'notion'
event_ui.render_event(resolve_event(slug='commons-montreal'))
