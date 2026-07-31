"""Protocol Hack — a smoke simulation for questioning the commons."""

import streamlit as st

from ui import apply_theme


st.set_page_config(
    page_title="Protocol Hack · Commons",
    page_icon="🧭",
    layout="wide",
    initial_sidebar_state="expanded",
)
apply_theme()

navigation = st.navigation(
    {
        "Commons": [
            st.Page(
                "views/home_redirect.py",
                title="Home",
                default=True,
                visibility="hidden",
            ),
            st.Page(
                "views/commons.py",
                title="Question the commons",
                icon="🧭",
                url_path="commons",
            ),
            st.Page(
                "views/commons_map.py",
                title="Commons Map",
                icon="🗺️",
                url_path="commons-map",
            ),
        ],
        "Tracks": [
            st.Page(
                "views/capacity.py",
                title="Capacity",
                icon="🧩",
                url_path="capacity",
            ),
            st.Page(
                "views/strategy.py",
                title="Strategy",
                icon="♟️",
                url_path="strategy",
            ),
            st.Page(
                "views/mosaic.py",
                title="Mosaic",
                icon="🧶",
                url_path="mosaic",
            ),
        ],
        "Operations": [
            st.Page(
                "views/commons_host.py",
                title="Host",
                icon="🔐",
                url_path="commons-host",
            )
        ],
        "Tests": [
            st.Page(
                "views/test_timeline_benchmarks.py",
                title="Timeline benchmarks",
                icon="🧭",
                url_path="test-timeline-benchmarks",
            ),
            st.Page(
                "views/test_timeline_game.py",
                title="Timeline game",
                icon="〽️",
                url_path="test-timeline-game",
            ),
            st.Page(
                "views/test_timeline_style_lab.py",
                title="Trajectory Style Lab",
                icon="🎨",
                url_path="test-timeline-style-lab",
            ),
            st.Page(
                "views/test_landing_primitives.py",
                title="Landing primitives",
                icon="🧱",
                url_path="test-landing-primitives",
            ),
            st.Page(
                "views/test_smokegun.py",
                title="Smoke gun",
                icon="🧪",
                url_path="test-smokegun",
            ),
            st.Page(
                "views/ui_lab.py",
                title="UI lab",
                icon="🎛️",
                url_path="ui-lab",
            ),
        ],
    }
)
navigation.run()
