"""Landing-page study built from primitive Streamlit elements only."""

from pathlib import Path

import streamlit as st


STYLESHEET = Path(__file__).parent.parent / "styles" / "test_landing_primitives.css"


def orbit_marker(key: str) -> None:
    with st.container(key=key):
        st.caption("●")


def orbit_ring(key: str):
    return st.container(key=key)


st.html(STYLESHEET)

about_was_opened = st.session_state.setdefault("primitive_landing_about", False)

with st.container(key="primitive-landing-canvas"):
    brand, spacer, about, explore = st.columns(
        [5, 4, 1, 1],
        gap="small",
        vertical_alignment="center",
    )

    with brand:
        with st.container(key="primitive-brand"):
            st.caption("COMMONS SIMULATOR")

    with about:
        with st.container(key="primitive-about-action"):
            if st.button("ABOUT", type="tertiary", width="stretch"):
                about_was_opened = not about_was_opened
                st.session_state.primitive_landing_about = about_was_opened

    with explore:
        with st.container(key="primitive-explore-action"):
            st.page_link(
                "views/commons_map.py",
                label="EXPLORE",
                width="stretch",
            )

    copy, visual = st.columns(
        [4, 5],
        gap="large",
        vertical_alignment="center",
    )

    with copy:
        with st.container(key="primitive-hero-copy"):
            st.title("Commons")
            st.title("Playground")
            st.write("Strategy for shared systems and collective decision-making.")

        with st.container(key="primitive-enter-action"):
            st.page_link(
                "views/commons.py",
                label="Enter the playground  →",
                width="stretch",
            )

    with visual:
        with st.container(key="primitive-orbit-stage"):
            with orbit_ring("primitive-orbit-outer"):
                orbit_marker("primitive-dot-outer-top")
                orbit_marker("primitive-dot-outer-left")
                orbit_marker("primitive-dot-outer-right")

                with orbit_ring("primitive-orbit-middle"):
                    orbit_marker("primitive-dot-middle-top")
                    orbit_marker("primitive-dot-middle-left")

                    with orbit_ring("primitive-orbit-inner"):
                        orbit_marker("primitive-dot-inner-left")
                        orbit_marker("primitive-dot-inner-right")

                        with st.container(key="primitive-orbit-center"):
                            st.caption("●")

    if about_was_opened:
        with st.container(key="primitive-about-panel"):
            st.subheader("One situation. One strategic move.")
            st.write(
                "Choose how you would act when a shared resource reaches a "
                "threshold, explain why, and add your anonymous trajectory "
                "to the Commons Map."
            )

st.caption(
    "TEST SURFACE · native Streamlit text, columns, containers, buttons, "
    "links and one external stylesheet"
)
