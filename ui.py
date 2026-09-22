"""Shared presentation helpers. No persistence or protocol decisions live here."""

from __future__ import annotations

from collections import Counter
from datetime import datetime
import html
from typing import Any

import streamlit as st

from protocol import Protocol
from probe_theme import (
    PROBE_COLORS,
    TYPOGRAPHY_PRESET_NAME,
    css_variable_declarations,
    repository_revision,
    typography_css,
)
from storage.context import repository_mode


COLORS = PROBE_COLORS


def apply_theme() -> None:
    st.markdown(
        f"<style>:root {{ {css_variable_declarations()} }} {typography_css()}</style>",
        unsafe_allow_html=True,
    )
    st.markdown(
        """
        <style>
        @import url('https://fonts.googleapis.com/css2?family=DM+Mono:wght@400;500&family=Manrope:wght@400;600;700;800&display=swap');
        *, *::before, *::after { box-sizing:border-box; }
        html, body, .stApp { overflow-x:hidden; }
        .stApp { background: var(--paper); color: var(--ink); }
        .block-container { width:100%; max-width:1280px; }
        html, body, [class*="css"] { font-family: "Manrope", sans-serif; }
        h1, h2, h3, h4 { color:var(--ink) !important; }
        [data-testid="stAppViewContainer"] h1 {
          font-size:var(--type-display) !important;
          line-height:var(--line-display) !important;
          font-weight:800 !important;
        }
        [data-testid="stAppViewContainer"] h2 {
          font-size:var(--type-section) !important;
          line-height:var(--line-section) !important;
          font-weight:750 !important;
        }
        [data-testid="stAppViewContainer"] h3,
        [data-testid="stAppViewContainer"] h4,
        [data-testid="stAppViewContainer"] details summary {
          font-size:var(--type-question) !important;
          line-height:var(--line-question) !important;
          font-weight:700 !important;
        }
        [data-testid="stAppViewContainer"] [data-testid="stMarkdownContainer"] > p,
        [data-testid="stAppViewContainer"] [data-testid="stMarkdownContainer"] > ul,
        [data-testid="stAppViewContainer"] [data-testid="stMarkdownContainer"] > ol {
          max-width:var(--measure-body);
          font-size:var(--type-body);
          line-height:var(--line-body);
        }
        .editorial-lead,
        .editorial-lead p,
        .st-key-editorial_lead [data-testid="stMarkdownContainer"] > p {
          max-width:var(--measure-lead) !important;
          font-size:var(--type-lead) !important;
          line-height:var(--line-lead) !important;
        }
        [data-testid="stAppViewContainer"] [data-testid="stWidgetLabel"] p {
          font-size:var(--type-option) !important;
          line-height:var(--line-option) !important;
          font-weight:400 !important;
        }
        [data-testid="stAppViewContainer"] input,
        [data-testid="stAppViewContainer"] textarea,
        [data-testid="stAppViewContainer"] button p {
          font-size:var(--type-option) !important;
          font-weight:400 !important;
        }
        [data-testid="stAppViewContainer"] [data-testid="stCaptionContainer"],
        [data-testid="stAppViewContainer"] [data-testid="stCaptionContainer"] p {
          max-width:var(--measure-body);
          font-size:var(--type-helper) !important;
          line-height:var(--line-helper) !important;
        }
        .eyebrow, .editorial-metadata {
          font-size:var(--type-metadata) !important;
          line-height:var(--line-metadata) !important;
        }
        [data-testid="stPlotlyChart"], [data-testid="stDataFrame"],
        [data-testid="stHorizontalBlock"], .editorial-wide {
          max-width:none;
        }
        code, .mono { font-family:"DM Mono", monospace; }
        [data-testid="stHeader"] { background:transparent; }
        [data-testid="stSidebar"] { background:#12211b; }
        [data-testid="stSidebar"] * { color:#f3f0e8; }
        .eyebrow { font-family:"DM Mono", monospace; text-transform:uppercase; letter-spacing:.12em; font-size:var(--type-metadata); }
        .hero { padding:3.2rem 0 1.5rem; max-width:1000px; }
        .hero p { max-width:var(--measure-lead); font-size:var(--type-lead); line-height:var(--line-lead); overflow-wrap:anywhere; }
        .scenario { border:2px solid var(--ink); border-radius:22px; padding:clamp(1.2rem,3vw,2.4rem); background:#fffdf6; box-shadow:9px 9px 0 var(--ink); margin:1rem 0 2rem; }
        .notice { background:var(--acid); border-radius:999px; padding:.55rem .9rem; display:inline-block; font-weight:700; margin-top:1rem; }
        .pilot-badge { display:inline-flex; align-items:center; gap:.35rem; border:1px solid rgba(18,33,27,.45); border-radius:999px; padding:.25rem .58rem; font-family:"DM Mono",monospace; font-size:var(--type-metadata); letter-spacing:.08em; text-transform:uppercase; }
        .compact-masthead { display:flex; align-items:center; justify-content:space-between; gap:1rem; padding:1.25rem 0 .3rem; border-bottom:1px solid rgba(18,33,27,.2); }
        .compact-masthead strong { font-size:var(--type-question); line-height:var(--line-question); letter-spacing:-.02em; }
        .review-card { border:2px solid var(--ink); border-radius:22px; padding:clamp(1.5rem,4vw,3.2rem); background:#fffdf6; margin:1rem 0 1.5rem; }
        .review-action { font-size:var(--type-display); font-weight:800; letter-spacing:-.055em; line-height:var(--line-display); text-transform:uppercase; max-width:1050px; margin:.5rem 0 1.35rem; overflow-wrap:anywhere; }
        .review-description { max-width:var(--measure-body); color:rgba(18,33,27,.7); font-size:var(--type-body); line-height:var(--line-body); }
        .review-because { margin-top:2rem; }
        .review-rationale { font-size:var(--type-lead); line-height:var(--line-lead); max-width:var(--measure-lead); margin-top:.4rem; }
        .reward { text-align:center; border:2px solid var(--ink); border-radius:24px; background:#fffdf6; padding:clamp(1.5rem,4vw,3rem); margin:1rem 0 1.2rem; }
        .reward-check { width:4.2rem; height:4.2rem; border-radius:50%; display:grid; place-items:center; margin:0 auto 1rem; background:var(--acid); border:2px solid var(--ink); font-size:2.2rem; font-weight:800; }
        .reward h2 { font-size:var(--type-section) !important; line-height:var(--line-section) !important; margin:.45rem auto; max-width:820px; }
        .privacy { border-left:5px solid var(--ink); background:var(--mint); padding:1rem 1.2rem; margin:1.2rem 0; max-width:100%; overflow-wrap:anywhere; }
        .draft { background:#fff0be; border:1px solid #12211b; padding:.65rem .9rem; border-radius:10px; }
        div.stButton > button, div.stFormSubmitButton > button { border:2px solid var(--ink); border-radius:999px; background:var(--acid); color:var(--ink); font-weight:800; min-height:var(--control-min-height); box-shadow:4px 4px 0 var(--ink); }
        div.stButton > button:hover, div.stFormSubmitButton > button:hover { border-color:var(--ink); color:var(--ink); transform:translate(2px,2px); box-shadow:2px 2px 0 var(--ink); }
        [data-testid="stMetric"] { background:#fffdf6; border:2px solid var(--ink); border-radius:16px; padding:1rem; }
        [data-testid="stMetric"] * { color:var(--ink) !important; }
        [data-testid="stAlert"] { border-radius:14px; }
        .footer { margin-top:4rem; padding:1.2rem 0 2rem; border-top:1px solid rgba(18,33,27,.35); font-family:"DM Mono",monospace; font-size:var(--type-metadata); }
        @media (max-width: 640px) {
          .block-container { padding-left:1rem; padding-right:1rem; }
          .hero { padding-top:1rem; }
          .scenario { box-shadow:5px 5px 0 var(--ink); }
          h1 { overflow-wrap:anywhere; }
          .privacy { padding:.9rem 1rem; }
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def revision_badge() -> None:
    """Show repository provenance without exposing configuration or runtime state."""

    revision = repository_revision()
    try:
        updated = (
            datetime.fromisoformat(revision.updated_at)
            .astimezone()
            .strftime("%d %b %Y · %H:%M")
        )
    except ValueError:
        updated = revision.updated_at
    st.markdown(
        '<div class="editorial-wide" style="display:flex;justify-content:flex-end;margin:.15rem 0 .65rem">'
        '<span class="probe-revision-badge editorial-metadata" style="font-family:\'DM Mono\',monospace;'
        "letter-spacing:.04em;border:1px solid rgba(18,33,27,.3);border-radius:999px;"
        'padding:.38rem .68rem;background:#fffdf6;color:var(--ink);white-space:nowrap">'
        f"✦ Version · {html.escape(updated)} · {html.escape(revision.commit)}</span></div>"
        f'<span style="display:none">{TYPOGRAPHY_PRESET_NAME}</span>',
        unsafe_allow_html=True,
    )


def header(
    protocol: Protocol,
    *,
    eyebrow: str,
    title: str,
    copy: str,
    pilot_display: str = "banner",
    show_storage_warning: bool = True,
) -> None:
    st.markdown(
        f"""
        <div class="hero">
          <div class="eyebrow">{html.escape(eyebrow)}</div>
          <h1>{html.escape(title)}</h1>
          <p>{html.escape(copy)}</p>
        </div>
        """,
        unsafe_allow_html=True,
    )
    if protocol.status.startswith("draft") and pilot_display == "banner":
        st.markdown(
            '<div class="draft"><b>Pilot content.</b> The smoking-gun scenario is provisional; its wording can be replaced without changing the data architecture.</div>',
            unsafe_allow_html=True,
        )
    elif protocol.status.startswith("draft") and pilot_display == "badge":
        st.markdown(
            '<span class="pilot-badge" title="The scenario wording is provisional.">Pilot</span>',
            unsafe_allow_html=True,
        )
    if show_storage_warning and repository_mode() == "demo":
        st.info(
            "Preview storage is active. Records remain in this running app only; Notion is not being written.",
            icon="🧪",
        )


def compact_masthead(protocol: Protocol) -> None:
    pilot = (
        '<span class="pilot-badge" title="The scenario wording is provisional.">Pilot</span>'
        if protocol.status.startswith("draft")
        else ""
    )
    st.markdown(
        f'<div class="compact-masthead"><strong>Question the commons.</strong>{pilot}</div>',
        unsafe_allow_html=True,
    )


def participant_refinement_styles() -> None:
    """Reduce default button weight on the participant surface."""

    st.markdown(
        """
        <style>
        div.stButton > button, div.stFormSubmitButton > button {
          background:#fffdf6;
          box-shadow:none;
          min-height:2.65rem;
        }
        div.stButton > button:hover, div.stFormSubmitButton > button:hover {
          transform:none;
          box-shadow:none;
          background:#fff;
        }
        button[data-testid="stBaseButton-primary"] {
          background:var(--ink) !important;
          color:#fffdf6 !important;
          box-shadow:none !important;
        }
        .st-key-enter_scenario button {
          background:var(--acid) !important;
          color:var(--ink) !important;
          box-shadow:4px 4px 0 var(--ink) !important;
          min-height:3.35rem;
        }
        .st-key-enter_scenario button:hover {
          transform:translate(2px,2px) !important;
          box-shadow:2px 2px 0 var(--ink) !important;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def privacy_note() -> None:
    st.markdown(
        """
        <div class="privacy">
        <b>Two separate records.</b> Your strategy is stored under a random participant code,
        separately from any contact details. You may delete your contact details; your anonymous
        strategy remains part of the Commons Map. For this pilot, coordination only records interest.
        Future introductions are still being discussed with Nathalie, and no email is shared automatically.
        </div>
        """,
        unsafe_allow_html=True,
    )


def footer(protocol: Protocol) -> None:
    st.markdown(
        f'<div class="footer">PROTOCOL {html.escape(protocol.version)} · {html.escape(protocol.session_code)}</div>',
        unsafe_allow_html=True,
    )


def action_counts(profiles: list[dict[str, Any]]) -> Counter[str]:
    return Counter(
        str(profile.get("action_label") or profile.get("action_id"))
        for profile in profiles
    )


def tag_counts(profiles: list[dict[str, Any]]) -> Counter[str]:
    counts: Counter[str] = Counter()
    for profile in profiles:
        counts.update(str(tag) for tag in profile.get("semantic_tags") or [])
    return counts


def strategic_graph_dot(profiles: list[dict[str, Any]]) -> str:
    lines = [
        "graph commons {",
        'graph [bgcolor="transparent", overlap=false, splines=true];',
        'node [fontname="Helvetica", style="filled", color="#12211b"];',
        'edge [color="#708077"];',
    ]
    tag_nodes: set[str] = set()
    for index, profile in enumerate(profiles):
        alias = str(profile.get("participant_alias") or f"P-{index + 1:02d}")
        participant_node = f"participant_{index}"
        lines.append(
            f'{participant_node} [label="{alias}", shape=circle, fillcolor="#d7ff48"];'
        )
        for tag in profile.get("semantic_tags") or []:
            safe_id = "tag_" + "".join(
                character if character.isalnum() else "_" for character in str(tag)
            )
            if safe_id not in tag_nodes:
                safe_label = str(tag).replace('"', "'")
                lines.append(
                    f'{safe_id} [label="{safe_label}", shape=box, fillcolor="#b9ead7"];'
                )
                tag_nodes.add(safe_id)
            lines.append(f"{participant_node} -- {safe_id};")
    lines.append("}")
    return "\n".join(lines)
