"""Read-only operational dashboard for the Montréal Commons probe."""
from __future__ import annotations

from datetime import datetime, timezone
import hmac
import json
import os

import pandas as pd
import streamlit as st
from probe_engine import ProbeRuntime, trajectory_from_dict

from protocol.probe_results import audit_probe_submissions, load_audited_trajectories


def authenticate_host() -> bool:
    if st.session_state.get('host_authenticated'):
        return True
    expected = os.getenv('PROTOHACK_HOST_CODE', '').strip()
    if not expected:
        try:
            expected = str(st.secrets.get('app', {}).get('host_access_code', '')).strip()
        except Exception:
            expected = ''
    if not expected:
        st.error('Host access is not configured. Add app.host_access_code to secrets.')
        return False
    with st.form('montreal_host_login'):
        supplied = st.text_input('Host access code', type='password')
        submitted = st.form_submit_button('Open host view')
    if submitted:
        if hmac.compare_digest(supplied, expected):
            st.session_state.host_authenticated = True
            st.rerun()
        st.error('Access code not recognised.')
    return False


def _text(value):
    if value is None:
        return ''
    return value if isinstance(value, str) else json.dumps(value, ensure_ascii=False)


def load_snapshot(repository, registration, probe):
    # Scope before auditing: no other event's rows or diagnostics reach this view.
    rows = [row for row in repository.list_probe_response_audit_rows()
            if row.get('event_id') == registration.session_code
            and row.get('probe_id') == probe.id]
    audit = audit_probe_submissions(rows, event_id=registration.session_code, probe_id=probe.id)
    trajectories = load_audited_trajectories(
        repository, audit, event_id=registration.session_code, probe_id=probe.id)
    participants, field, details, events, timeline = [], [], [], [], []
    for index, (record, raw) in enumerate(zip(audit.included, trajectories), 1):
        trajectory = trajectory_from_dict(raw)
        runtime = ProbeRuntime.hydrate(probe, trajectory,
            participant_id=trajectory.participation.participant_id,
            scope_id=registration.session_code)
        resolutions = {q.id: runtime.resolution(q.id) for q in probe.questions}
        answers = {key: value.event.value for key, value in resolutions.items()
                   if value.state.value == 'answered' and value.event is not None}
        label = _text(answers.get('name')) or f'P{index:02d}'
        identity = str(record.get('player_page_id') or record.get('participant_id'))
        participant = {'Participant': label, 'Participant ID': identity,
            'Email': _text(answers.get('email')), 'Institution': _text(answers.get('organisation_name')),
            'Reported location': _text(answers.get('base_location')),
            'Submission': record['submission_id'], 'Last contribution': record['integrated_at']}
        participants.append(participant)
        cells = {'Participant': f'{label} · {identity}'}
        for question in probe.questions:
            resolution = resolutions[question.id]
            state = resolution.state.value
            cells[f'{question.id} · {question.prompt}'] = (
                {'answered': '●', 'skipped': 'S', 'deferred': 'D', 'ineligible': '—'}.get(state, '○')
                + (' ⚑' if resolution.flagged else ''))
            details.append({'Participant': label, 'Participant ID': identity,
                'Question ID': question.id, 'Question': question.prompt,
                'Answer / response': _text(answers.get(question.id)),
                'State': state, 'Flagged': resolution.flagged,
                'Reason codes': ', '.join(resolution.event.reason_codes) if resolution.event else '',
                'Note': resolution.event.reason_note if resolution.event else ''})
        field.append(cells)
        # Explicit allowlist: credentials and arbitrary event metadata never render.
        for event in trajectory.events:
            events.append({'Participant': label, 'Participant ID': identity,
                'Timestamp': event.timestamp, 'Event': event.kind.value,
                'Question ID': event.question_id, 'Question revision': event.question_revision})
        timeline.append({'timestamp': record['integrated_at']})
    return dict(participants=participants, field=field, details=details, events=events,
                timeline=timeline, counts=audit.counts,
                loaded_at=datetime.now(timezone.utc).isoformat(timespec='seconds'))


def _table(rows, empty):
    if rows:
        st.dataframe(pd.DataFrame(rows), hide_index=True, width='stretch')
    else:
        st.info(empty)


def render_dashboard(registration, repository, *, test_mode):
    probe = registration.load()
    st.selectbox('Session / event', [registration.session_code],
                 format_func=lambda _: registration.title, key='montreal_host_session')
    refresh = st.button('Refresh data', icon=':material/refresh:')
    key = f'montreal_host_snapshot:{registration.probe_id}:{test_mode}:{id(repository)}'
    if refresh:
        st.session_state.pop(key, None)
    if key not in st.session_state:
        try:
            st.session_state[key] = load_snapshot(repository, registration, probe)
        except Exception as exc:
            st.error('Host data could not be loaded. Use Refresh data to retry.')
            with st.sidebar.expander('Host · data diagnostics'):
                st.write({'error_type': type(exc).__name__})
            return
    snapshot = st.session_state[key]
    st.caption(f"{registration.session_code} · refreshed {snapshot['loaded_at']}")
    with st.container(border=True):
        st.markdown('**Needs attention**')
        columns = st.columns(3)
        columns[0].metric('Access recovery requests', 'Unavailable')
        columns[1].metric('Participants missing contact', sum(not p['Email'].strip() for p in snapshot['participants']))
        columns[2].metric('Identity claims', 'Unavailable')
        st.caption('Access recovery and identity claims are not configured for this probe.')
    view = st.segmented_control('Host view', ['Overview', 'Participants', 'Access & Recovery',
        'Question set', 'Submissions', 'Event log'], default='Overview', key='montreal_host_view')
    if view == 'Overview':
        columns = st.columns(4)
        columns[0].metric('Participants', len(snapshot['participants']))
        columns[1].metric('Completed submissions', len(snapshot['participants']))
        columns[2].metric('Questions answered', sum(d['State'] == 'answered' for d in snapshot['details']))
        last = max((p['Last contribution'] for p in snapshot['participants']), default='—')
        columns[3].metric('Last contribution', last[:10])
        st.caption(f'Latest contribution: {last}. Latest valid submitted revision per participant; drafts are excluded.')
        st.subheader('Response Field')
        st.caption('Operational coverage only: density is not a measure of answer quality. ● answered; ○ unresolved; ⚑ flagged; S skipped; D deferred; — ineligible.')
        _table(snapshot['field'], 'No response field is available yet.')
        st.subheader('Response Timeline')
        if snapshot['timeline']:
            frame = pd.DataFrame(snapshot['timeline'])
            frame['timestamp'] = pd.to_datetime(frame['timestamp'], utc=True)
            frame = frame.groupby('timestamp').size().sort_index().cumsum().reset_index(name='cumulative')
            st.line_chart(frame, x='timestamp', y='cumulative', y_label='Participants with a latest completed submission')
        else:
            st.info('No completed submissions have timestamps yet.')
        st.subheader('Spatial Context')
        _table([{'Participant': p['Participant'], 'Reported location': p['Reported location']}
                for p in snapshot['participants'] if p['Reported location']], 'No participant locations have been reported.')
        st.subheader('Recent participants')
        _table(sorted(snapshot['participants'], key=lambda p: p['Last contribution'], reverse=True)[:10], 'No submitted participants yet.')
    elif view == 'Participants':
        _table(snapshot['participants'], 'No submitted participants yet.')
    elif view == 'Access & Recovery':
        st.subheader('Access & Recovery')
        st.info('No access recovery or identity-claim workflow is configured for Montréal Commons.')
    elif view == 'Question set':
        columns = st.columns(4)
        columns[0].metric('Questions', len(probe.questions))
        columns[1].metric('Shared questions', sum(bool(q.shared_dimension) for q in probe.questions))
        columns[2].metric('Event-specific questions', sum(not q.shared_dimension for q in probe.questions))
        columns[3].metric('Modes', len(probe.authoring.flow_modes))
        st.code('\n'.join([f'questionnaire_id = {probe.id}', f'revision         = {probe.revision}',
            f'session_code     = {registration.session_code}', 'schema           = probe-authoring/v1',
            'source_kind      = yaml', f'source_path      = {registration.source_path}']), language='text')
        for section in probe.sections:
            st.markdown(f'**{section.title}**')
            for step_id in section.step_ids:
                for field_id in probe.step(step_id).field_ids:
                    question = probe.question(field_id)
                    st.write(f'{question.id} · {question.prompt}')
        with st.expander('Complete authored question set'):
            st.code(registration.source_path.read_text(), language='yaml')
    elif view == 'Submissions':
        st.subheader('Response details')
        st.caption('Latest valid submitted revision per participant. Structured responses retain their saved fields and values.')
        _table(snapshot['details'], 'No submitted responses yet.')
    elif view == 'Event log':
        st.caption('Canonical events from the latest valid submitted trajectories; credentials and event metadata are excluded.')
        _table(snapshot['events'], 'No submitted event log entries.')
