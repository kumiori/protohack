"""Public strategic map. It intentionally has no contact or rationale layer."""

from collections import defaultdict

import streamlit as st

from protocol import load_protocol
from storage import get_repository
from ui import action_counts, footer, header, strategic_graph_dot, tag_counts


protocol = load_protocol()
repository = get_repository()
profiles = repository.list_strategic_profiles(protocol.session_code)

header(
    protocol,
    eyebrow="Output A · Ecosystem map",
    title="The Commons Map",
    copy="A live view of strategic trajectories and the themes that connect them. Contact details and written rationales never appear here.",
)

total = len(profiles)
action_count = action_counts(profiles)
themes = tag_counts(profiles)
col1, col2, col3 = st.columns(3)
col1.metric("Trajectories", total)
col2.metric("First moves", len(action_count))
col3.metric("Shared themes", len(themes))

if not profiles:
    st.info("The map is waiting for its first trajectory.")
    st.page_link("views/commons.py", label="Enter the simulation", icon="🧭")
else:
    st.subheader("How the group moves first")
    st.bar_chart(dict(action_count), color="#a993ff", horizontal=True)

    st.subheader("Participant graph")
    st.caption("Connections are created by shared authored themes, not by email or similar answers alone.")
    st.graphviz_chart(strategic_graph_dot(profiles), width="stretch")

    st.subheader("Theme field")
    ordered = sorted(themes.items(), key=lambda item: (-item[1], item[0]))
    st.dataframe(
        [{"Theme": theme, "Trajectories": count} for theme, count in ordered],
        hide_index=True,
        width="stretch",
    )

    by_action: dict[str, list[str]] = defaultdict(list)
    for profile in profiles:
        by_action[str(profile.get("action_label") or profile.get("action_id"))].append(
            str(profile.get("participant_alias") or "Anonymous")
        )
    with st.expander("Read the strategic distribution"):
        for action, aliases in by_action.items():
            st.write(f"**{action}** · {', '.join(aliases)}")

st.page_link("views/commons.py", label="Return to the simulation", icon="🧭")
footer(protocol)
