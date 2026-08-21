The package’s essential value is this:

> It turns complex social or technical processes into inspectable, executable, evidence-bearing models—without silently collapsing ambiguity, agency, or history.

It is less a conventional application than a collection of semantic engines.

## The core engine

The package repeatedly applies the same underlying logic:

```text
Authored definition
        ↓
Validation and normalisation
        ↓
Deterministic state transitions
        ↓
Inspectable evidence and history
        ↓
Multiple views without multiple truths
        ↓
Explicit human interpretation or coordination
```

That pattern appears in four important engines.

### 1. Protocol execution engine

The Protocol Laboratory converts a protocol definition into a deterministic experiment:

- participants have explicit states;
- commands produce transitions, messages, timers, failures, and events;
- invariants are evaluated against the resulting history;
- identical definitions and commands produce reproducible replays;
- each replay receives a stable hash;
- human observations remain linked to the events they interpret.

The important abstraction is not TCP. TCP is merely the first experimental content. The reusable product is a protocol-neutral laboratory for reconstructing, executing, breaking, and interpreting negotiations.

The clearest implementation boundary is [protocol_lab/engine.py](/Users/kumiori3/Documents/WIP/Society/app_protocol_hack/protocol_lab/engine.py), supported by definition-driven scenarios and privacy-safe Field Notes.

### 2. Trajectory reasoning engine

The trajectory system turns intention into a structured path through:

\[
(\text{time},\ \text{energy},\ \text{uncertainty})
\]

Its distinctive contribution is the separation of three meanings that planning tools commonly mix together:

- **Influence:** how extensively an event changes the trajectory.
- **Direction:** whether the change is gradual or abrupt.
- **Topology:** whether the future continues or branches.

It also separates:

- the plan from what actually happened;
- uncertainty from the best-estimate path;
- qualitative time from calendar time;
- private editing from explicit social sharing;
- a shared goal from independently authored contributions.

This creates a planning engine that preserves authorship and disagreement. History annotates the plan through append-only realisation records; it does not silently rewrite the original trajectory. The conceptual contract is documented in [TRAJECTORY_MODEL.md](/Users/kumiori3/Documents/WIP/Society/app_protocol_hack/TRAJECTORY_MODEL.md), while portability and migration are handled by [protocol/trajectory_schema.py](/Users/kumiori3/Documents/WIP/Society/app_protocol_hack/protocol/trajectory_schema.py).

### 3. Evidence compiler

The agentic protocol map demonstrates another powerful best practice: renderers are not allowed to invent meaning.

A single compiler owns:

- terminology and identity;
- reference validation;
- temporal normalisation;
- evidence resolution;
- institutional regimes and transitions;
- unknown or disputed information;
- provenance hashes;
- rejection of stale or incompatible artifacts.

The timeline and graph can present different readings, but they consume the same compiled facts. Governance, maintenance, implementation, adoption, funding, endorsement, and convening remain separate relation layers.

That makes the compiler an **epistemic boundary**: presentation may filter or style a claim, but it cannot strengthen, merge, or manufacture it. See [docs/agentic_protocol_map_model.md](/Users/kumiori3/Documents/WIP/Society/app_protocol_hack/docs/agentic_protocol_map_model.md) and [agentic_registry/compiler.py](/Users/kumiori3/Documents/WIP/Society/app_protocol_hack/agentic_registry/compiler.py).

### 4. Participation and coordination engine

The package distinguishes several actions that many platforms accidentally conflate:

- answering is not consenting to contact;
- saving locally is not publishing;
- publishing is not joining;
- sharing a goal is not sharing a timeline;
- contributing is not surrendering authorship;
- comparison is not consensus.

This is extremely valuable. It makes participation explicit and reversible while protecting the identity and semantics of each contribution. Shared trajectories are compared on a normalised Now → Landing horizon, but they are not averaged into a synthetic collective plan.

## The package’s best-practice essence

I would pinpoint five principles worth extracting:

1. **Meaning before interface**
   Concepts receive explicit definitions, valid states, and boundaries before they become controls or graphics.

2. **One semantic authority, multiple representations**
   Different views can answer different questions, but they must not generate different facts.

3. **Every transformation remains inspectable**
   Commands, events, revisions, source references, hashes, and migration rules make the system auditable.

4. **Human agency occurs at explicit gates**
   Integrate, share, join, revise, challenge, or coordinate are deliberate actions—not side effects of autosave or navigation.

5. **Uncertainty and difference are preserved**
   Unknown dates remain unknown; separate relation types remain separate; independent trajectories remain independent; actual history does not erase intention.

## The value proposition

I would describe the package this way:

> **Protocol Hack is an engine for making coordination inspectable. It converts protocols, plans, institutional evidence, and participant contributions into versioned state machines and portable semantic records, then lets people execute, compare, challenge, and interpret them without losing provenance or individual agency.**

Or, more compactly:

> **A semantic laboratory for revealing how intentions become transitions, how transitions create histories, and how independent histories can be compared without being falsely unified.**

The most reusable asset is therefore not the current Streamlit interface. It is the collection of contracts underneath it:

- definition-driven content;
- deterministic transition engines;
- canonical portable schemas;
- append-only histories;
- compiler-owned semantics;
- evidence and provenance linkage;
- explicit privacy and sharing boundaries;
- UI-independent acceptance contracts.

Those contracts are what should become the foundation of a “best practices” tool. The existing surfaces should serve as demonstrations of the engine, rather than defining what the engine is.
