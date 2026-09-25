"""Developer-only, minimally coupled Notion CREATE + READ BACK instrument."""

from __future__ import annotations

from importlib.metadata import version as package_version
import json
import platform
from urllib.parse import urlparse
import uuid

import streamlit as st

from probe_theme import repository_revision
from storage.context import notion_token
from storage.notion_smoking_gun import NotionSmokingGun


def _deployment() -> str:
    try:
        hostname = str(urlparse(st.context.url).hostname or "")
    except Exception:
        hostname = ""
    return "local" if hostname in {"", "localhost", "127.0.0.1", "::1"} else "remote"


def _abbreviate(value: str) -> str:
    return f"{value[:8]}…{value[-4:]}" if len(value) > 14 else value


def _service(environment: str) -> NotionSmokingGun:
    return NotionSmokingGun(token=notion_token(), environment=environment)


def _save(service: NotionSmokingGun) -> None:
    if service.trace and service.trace[0].get("step") == "RUN":
        revision = repository_revision()
        service.trace[0].update(
            {
                "deployment": _deployment(),
                "git_revision": revision.commit,
                "python": platform.python_version(),
                "notion_sdk": package_version("notion-client"),
            }
        )
    st.session_state["notion_smoking_gun_trace"] = list(service.trace)
    st.session_state["notion_smoking_gun_raw"] = service.raw_traceback
    st.session_state["notion_smoking_gun_page_id"] = service.last_page_id
    st.session_state["notion_smoking_gun_name"] = service.last_name
    st.session_state["notion_smoking_gun_integration"] = service.integration
    st.session_state["notion_smoking_gun_environment"] = service.target.environment


def _render_trace() -> None:
    trace = list(st.session_state.get("notion_smoking_gun_trace") or [])
    st.sidebar.title("NOTION SMOKING GUN")
    if not trace:
        st.sidebar.caption("No operation has run in this session.")
        return
    for entry in trace:
        step = str(entry.get("step") or "OPERATION")
        success = bool(entry.get("success"))
        marker = "✓" if success else "✗"
        st.sidebar.markdown(f"### {step}")
        st.sidebar.caption(f"{marker} {entry.get('operation') or entry.get('result') or ''}")
        st.sidebar.code(json.dumps(entry, ensure_ascii=False, indent=2), language="json")
    raw = str(st.session_state.get("notion_smoking_gun_raw") or "")
    if raw:
        with st.sidebar.expander("Raw traceback · sanitized", expanded=False):
            st.code(raw, language="text")


st.title("Notion Smoking Gun")
st.caption(
    "Developer-only diagnostic: Streamlit → configuration → Notion → target → "
    "CREATE → READ BACK. This page is not a Probe."
)

message = st.text_input("Message de test", value="smoke test 2026-09-24")
environment = st.radio(
    "Environment",
    options=["TEST", "PRODUCTION"],
    format_func=lambda value: f"{value} DATABASE",
    horizontal=True,
    index=0,
    key="notion_smoking_gun_environment_choice",
)
service = _service(environment)
revision = repository_revision()

with st.container(border=True):
    st.markdown("### Runtime fingerprint")
    st.code(
        json.dumps(
            {
                "git": revision.commit,
                "python": platform.python_version(),
                "notion_sdk": package_version("notion-client"),
                "deployment": _deployment(),
                "target": f"{environment} / {_abbreviate(service.target.data_source_id)}",
                "manifest": service.target.source,
                "token_hash": service.token_fingerprint,
            },
            indent=2,
        ),
        language="json",
    )

with st.container(border=True):
    st.markdown("### TARGET")
    st.code(
        json.dumps(
            {
                "environment": service.target.environment,
                "database": service.target.database,
                "database_id": service.target.database_id,
                "data_source_id": service.target.data_source_id,
                "source": service.target.source,
                "integration": str(
                    st.session_state.get("notion_smoking_gun_integration")
                    or "fuckthesystem (expected; verified during run)"
                ),
                "repository": service.target.repository,
                "operation": service.target.operation,
                "token_configured": service.token_configured,
            },
            indent=2,
        ),
        language="json",
    )

acknowledged = True
if environment == "PRODUCTION":
    st.warning("PRODUCTION DATABASE selected · This will create one real diagnostic record.")
    acknowledged = st.checkbox(
        "I understand this writes to production",
        value=False,
        key="notion_smoking_gun_production_ack",
    )

run_label = "RUN SMOKE TEST" if environment == "TEST" else "RUN PRODUCTION SMOKE TEST"
if st.button(
    run_label,
    type="primary",
    width="stretch",
    disabled=not acknowledged or not service.token_configured,
):
    passed = service.run_all(message, run_id=uuid.uuid4().hex[:8])
    _save(service)
    st.session_state["notion_smoking_gun_result"] = "PASS" if passed else "FAIL"
    st.rerun()

result = str(st.session_state.get("notion_smoking_gun_result") or "")
if result == "PASS":
    st.success(
        f"{environment} SMOKE TEST: PASS · ACCESS ✓ · CREATE ✓ · "
        "READ BACK ✓ · VALUE MATCH ✓ · REVERT ✓\n\n"
        "No active diagnostic record remains."
    )
elif result == "FAIL":
    trace = list(st.session_state.get("notion_smoking_gun_trace") or [])
    final = trace[-1] if trace else {}
    remaining = str(final.get("created_record_id") or "")
    if remaining:
        st.error(
            f"{environment} SMOKE TEST: PARTIAL FAILURE\n\n"
            f"Created record remains: `{remaining}`"
        )
    else:
        st.error(f"{environment} SMOKE TEST: FAIL · inspect the sidebar trace")

st.markdown("### Separate operations")
access_col, create_col, read_col, delete_col = st.columns(4)
if access_col.button("Test access", disabled=not service.token_configured):
    service.begin_run(uuid.uuid4().hex[:8])
    service.instantiate_client()
    try:
        service.test_access()
        service.read_schema()
        service.trace.append({"step": "RESULT", "result": "ACCESS PASS", "success": True})
    except Exception:
        service.trace.append(
            {"step": "RESULT", "result": f"FAIL AT {service.trace[-1]['step']}", "success": False}
        )
    _save(service)
    st.rerun()

if create_col.button(
    "Create record",
    disabled=not service.token_configured or (environment == "PRODUCTION" and not acknowledged),
):
    service.begin_run(uuid.uuid4().hex[:8])
    service.instantiate_client()
    try:
        service.test_access()
        service.read_schema()
        prefix = "SMOKE TEST" if environment == "TEST" else "SMOKE TEST — SAFE TO DELETE"
        service.create_record(f"{prefix} {uuid.uuid4().hex[:8]} · {message.strip()}")
        service.trace.append({"step": "RESULT", "result": "CREATE PASS", "success": True})
    except Exception:
        service.trace.append(
            {"step": "RESULT", "result": f"FAIL AT {service.trace[-1]['step']}", "success": False}
        )
    _save(service)
    st.rerun()

last_page_id = str(st.session_state.get("notion_smoking_gun_page_id") or "")
last_environment = str(st.session_state.get("notion_smoking_gun_environment") or "")
same_target = last_environment == environment
if read_col.button("Read last created record", disabled=not last_page_id or not same_target):
    service.begin_run(uuid.uuid4().hex[:8])
    service.last_page_id = last_page_id
    service.last_name = str(st.session_state.get("notion_smoking_gun_name") or "")
    try:
        matched = service.read_back(last_page_id)
        service.trace.append(
            {"step": "RESULT", "result": "READ PASS" if matched else "VALUE MISMATCH", "success": matched}
        )
    except Exception:
        service.trace.append(
            {"step": "RESULT", "result": f"FAIL AT {service.trace[-1]['step']}", "success": False}
        )
    _save(service)
    st.rerun()

if delete_col.button("Revert smoke record", disabled=not last_page_id or not same_target):
    service.begin_run(uuid.uuid4().hex[:8])
    try:
        service.archive(last_page_id)
        service.trace.append({"step": "RESULT", "result": "REVERT PASS", "success": True})
    except Exception:
        service.trace.append(
            {"step": "RESULT", "result": f"FAIL AT {service.trace[-1]['step']}", "success": False}
        )
    _save(service)
    st.session_state.pop("notion_smoking_gun_page_id", None)
    st.rerun()

if not service.token_configured:
    st.info("No Notion credential is configured for this runtime.")

_render_trace()
