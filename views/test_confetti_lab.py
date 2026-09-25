"""Visible visual calibration page for receipt celebrations."""

from __future__ import annotations

import uuid

import streamlit as st

from confetti_burst import VARIANTS, render_confetti_burst


st.title("Confetti Lab")
st.caption("Every variant launches from the bottom, rises, loses momentum, and falls.")

variant = st.selectbox(
    "Burst style",
    options=list(VARIANTS),
    format_func=VARIANTS.__getitem__,
)
height = st.slider("Stage height", min_value=360, max_value=720, value=520, step=40)

if "confetti_lab_seed" not in st.session_state:
    st.session_state["confetti_lab_seed"] = uuid.uuid4().hex
if st.button("Burst again", type="primary"):
    st.session_state["confetti_lab_seed"] = uuid.uuid4().hex

with st.container(border=True):
    render_confetti_burst(
        variant,
        height=height,
        seed=str(st.session_state["confetti_lab_seed"]),
    )

st.info("The production receipt currently uses Garden burst.")
