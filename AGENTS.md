# Repository working agreement

## User-facing regression rule

No existing user-facing capability may be removed, hidden, renamed into ambiguity,
or simplified away unless the change is explicitly named and justified in the
task. Any intentional capability change must also update the relevant acceptance
test and the feature registry. New onboarding may progressively reveal a feature,
but the complete capability must remain discoverable in the active editor.

## UI completion evidence

For every requested UI capability, report three separate states:

- **IMPLEMENTED** — the code exists;
- **WIRED** — it is reachable from the requested application surface;
- **VERIFIED** — it has been exercised on that surface with the requested behavior.

Do not call UI work complete until all three are true. Code inspection alone proves
only IMPLEMENTED. Prefer rendered Streamlit/AppTest assertions (or browser evidence
when available) for WIRED and VERIFIED.
