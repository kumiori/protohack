# Probe Results landscape

`/<event-slug>?view=results` projects canonical integrated submissions through
Probe Engine trajectories and `evaluate_representation`. The consumer renderer
never reads Notion columns or response dictionaries. The engine remains the
source of observations, resolution states and population provenance.

## Boundaries

- `probe_results_ui.py` owns generic Streamlit distribution, grouped distribution,
  comparison, records and ordered composite renderers. Unknown types are explicit.
- `protocol/probe_structures.py` owns UI-independent derived structures under
  `probe-derived-structure/v1`: exact shared-taxonomy offer/need comparison,
  explicit record-to-actor edges, completeness, and authored actionability maps.
  These are downstream consumer transformations; this change does not release or
  modify the separately installed Probe Engine package.
- `protocol/probe_topology.py` renders an already-derived graph, with hover, focus,
  click and keyboard selection. Mobile uses a button list with the same details;
  the native actor-grouped disclosure remains available outside the iframe.
- Optional `<probe-source>.results.yaml` files supply presentation order, titles,
  record relation field IDs and public disclosure policy. They contain no response
  data. Unlisted representations still render, so a layout cannot hide new fields.

Montréal's `short.results.yaml` arranges the existing four collective
representations into five sections. `short.yaml` and its revision are unchanged.
Outcome/effect distributions have no invented causal edges. Record category,
details, legacy additional fields and actor associations are never repaired.

## Counts and provenance

Component and role denominators are displayed independently. A comparison's
parent counts sum field responses; a composite's parent resolution values are
engine placeholders. Neither is presented as a participant response fraction.
Technical disclosures preserve those canonical values verbatim.

A selected count is a selection count, including multiple selections per person.
No observation differs from observed zero selection. Skip, flag, defer and
unanswered retain their engine meanings; flags need not be mutually exclusive
with other states.

The integrity rail distinguishes exclusions inside the event/Probe from all
excluded physical repository rows. The 1 October 2026 read-only check found five
current trajectories and four collective representations. A follow-up diagnosis
corrected the initial false-empty portrait projections: all five participants
have sector and function events on their linked Player records (seven sector
selections, six function selections). There are seven action records, six missing
categories and seven missing
`details` fields. Two in-scope rows were excluded; fifteen physical rows were
excluded across the repository. Missing fields are reported, never synthesized.

## Privacy

The public default is `public_records: aggregate` and participant identity hidden.
No real free text is embedded in public cards, topology HTML, derived topology
JSON or provenance. Public records expose counts and explicit actor associations.
Synthetic test mode can display its generated verbatim text. An explicitly
reviewed layout policy can set `public_records: verbatim`; removing identities
alone does not anonymise that text. A developer URL does not grant prose access.
Individual-scope representations are explicitly reserved rather than publishing
the first person's trajectory. Existing synthetic generation, test audit and
cleanup controls remain available.

## Actionability

No mapping is asserted for the current free-text Montréal action categories.
A layout may explicitly supply:

```yaml
actionability:
  actions: some_records_representation
  contributions: some_distribution_representation
  category_field: category
  mapping:
    exact_authored_category:
      contribution: [exact_contribution_key]
```

Matching is exact and case-sensitive. Available quantities are **selections**, not
unique people across keys. The renderer does not claim coverage or readiness.

## Verification

- `tests/test_probe_results_landscape.py`: pure contracts and rendered AppTest
  coverage, including a new Probe without layout-specific Python.
- `tests/test_probe_results_live.py`: explicitly opt-in, read-only five-person
  acceptance check. Run with `PROBE_RESULTS_LIVE=1`; otherwise skipped. Only this
  opted-in test overrides the test suite's offline-storage fixture.
- `tests/browser/probe_results.cjs`: desktop/mobile screenshots, graph detail
  clicks and horizontal-overflow assertion against the offline fixture server.
  Uses `PLAYWRIGHT_PACKAGE`, optional `CHROME_EXECUTABLE`, and optional
  `RESULTS_PREVIEW_URL`; writes screenshots to `/tmp/probe-results-*.png`.

Start the offline browser fixture with:

```sh
.venv/bin/streamlit run tests/fixtures/probe_results_landscape_app.py --server.port 8517
```

The local production application shell was also exercised at
`/commons-montreal?view=results` with the live five-person cohort. Desktop and
390px mobile exchange layouts, graph detail selection, public aggregate records
and absence of horizontal overflow were checked in headless Chrome. The first
cold-start navigation produced a Streamlit page-not-found overlay; a fresh
navigation after registration completed passed without that overlay.

| Capability | IMPLEMENTED | WIRED | VERIFIED |
|---|---|---|---|
| Five sections and all canonical baseline components | Yes | Results route | AppTest and actual local route |
| Denominators, empty states, provenance and integrity | Yes | Each component and rail | AppTest; live cohort |
| Bilateral exchange and structural balances | Yes | Exchange section | Live counts; desktop/mobile browser |
| Public aggregate records and explicit actor topology | Yes | Paths section | Live route; desktop/mobile selection |
| Verbatim records under explicit disclosure policy | Yes | Synthetic preview / opted-in policy | Synthetic AppTest and browser; real public prose remains restricted |
| Authored actionability comparison | Yes | Conditional generic mapping surface | AppTest; no Montréal mapping asserted |

The regression selection passed 97 tests with one opt-in live test skipped; the
separate opted-in live test passed. The latest targeted landscape tests passed
11 tests after the final completeness adjustment.

No production writes, migration, commit, package release or deployment are part
of this change.


## Portrait hydration correction

The first Results implementation evaluated `audit.included` physical Response
trajectories directly. Production persistence separates stable profile events
onto Player records, so `sectors` and `functions` were absent from that input even
though all five people had answered them. This was a loading defect, not missing
responses or a representation calculation defect.

`load_audited_trajectories` now obtains canonical repository-hydrated trajectories
and matches the exact physical page/submission selected by the audit. It checks
submission, event, Probe revision, participant and Player relation consistency.
Missing or ambiguous hydration fails explicitly instead of manufacturing an
unanswered projection. No profile dictionaries are converted into new answers;
only existing canonical events are restored by the established repository loader.
The physical audit remains unchanged and excluded submissions remain excluded.

`tests/test_probe_portrait_projection.py` exercises the production Notion split
and hydration code through rendered AppTest. It failed with answered `[0, 0]`
before the fix and passes with `[1, 1]` for its one-person fixture. The opt-in live
acceptance now requires five answered sector/function observations and 7/6
selections. All checks for this correction use Python/AppTest, with no browser or
screenshot operation.

Correction validation: 94 targeted regression tests passed, plus the separately
opted-in live Results AppTest (5/5 sectors, 7 selections; 5/5 functions,
6 selections). No production data was modified.

## Paired Secteurs / Fonctions (2 October 2026)

The `distribution_pairs` layout hint opts two adjacent distribution components
into one responsive frame. Only the two portrait components opt in. Their panels
use Probe taxonomy labels and taxonomy order, including zero-count options.
Bars scale against each component's answered count. Summaries distinguish people
from selections; unanswered trajectories receive an explicit annotation; zero
answered observations retain the honest empty state. Native provenance
expanders expose the full canonical denominator and source identifiers.

No questionnaire, persistence, Player restoration or engine semantics were
changed. Public panels contain aggregate counts only, never Other specifications
or profile events. Unknown option keys are counted separately without exposing
potential free text.

IMPLEMENTED: paired panels with equal desktop tracks and a one-column rule below
700px. Flexible tracks, wrapping labels and nonshrinking numeric text avoid fixed
chart widths. Zero labels retain readable contrast and explicit zero counts.

WIRED: `participant_portrait.component.1` and `.2` are paired within
`01 · LE CHAMP` through `short.results.yaml` and `render_distribution()`.

VERIFIED: rendered route AppTests check labels/order, counts, zero/missing/empty
states, disclosure, privacy and the emitted responsive CSS contract. The live
read-only AppTest verified snapshot `fd708743f85473bf`: sectors 6 answered / 11
selections; functions 6 answered / 14 selections. These reference counts exist
only in acceptance tests, never in rendering code.

AppTest has no browser layout engine. Actual viewport geometry and horizontal
overflow were not measured for this redesign: no browser or screenshot was used,
in accordance with the user's instruction. The automated responsive checks
verify the emitted two-track/one-track rules and retention of the same content.

Redesign regression run: 98 passed, one opt-in live test skipped, one unrelated
existing source-text assertion failed because `probe_ui.py` already changed
“Intégrer mes réponses” to “Envoyer mes réponses” before this task. That file and
its copy were left untouched. The separate live six-person portrait check passed.

Delivery verification: the exact staged changes were exported into a clean
checkout and passed 111 tests, with the opt-in live test skipped. Unrelated local
questionnaire/copy and documentation edits were excluded from the delivery; the
previous stale button-copy failures do not occur in this staged version.
