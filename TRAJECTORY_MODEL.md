# Trajectory geometry model

> **Shared-goal invariant:** A shared goal does not own a shared trajectory. It
> owns a collection of independently authored trajectory contributions.
> Convergence is a possible later operation on that collection, never an
> assumption made at ingestion.

The centreline is a piecewise cubic Hermite trajectory in

\[
\text{Trajectory space}=(\text{time},\ \text{energy},\ \text{uncertainty}).
\]

Time orders the path, energy expresses mobilisation, and uncertainty expresses
what the author does not yet know about the state or its continuation. Unlike
entropy, uncertainty is directly discussable and authorable. A primitive is
anchored by a stable time parameter or date; nobody places an arbitrary point
in 3D.

The representation is generally irreversible. Confirmed nodes obey the
one-sided ordering `t[i+1] > t[i]`; uncertainty magnitude obeys `u(t) >= 0`; and
realisation history is append-only. A path may be inspected backwards, but that
reverse trace is not an admissible evolution of the plan. This is a modelling
constraint, not a claim that every social process is physically irreversible.

Confirmed primitives are hard interpolation nodes. Three independent choices
govern their effect:

- Influence sets scale. Local is approximately ε-scale and creates a compact
  deformation. Structural is approximately order one and visibly changes the
  whole plan. Dominant is approximately 1/ε-scale and can reorganise what
  follows. The selected scale sets both energy displacement amplitude and
  temporal influence radius.
- Direction sets regularity. Gradually preserves one continuous tangent through
  the node. Abruptly preserves position while using distinct incoming and
  outgoing tangents, producing a kink.
- Topology sets uniqueness. Continuation keeps one trajectory. Branching keeps
  the shared trajectory before the node and creates two outgoing stems.

The RC0 branch record lives on the branching move. `topology_mode` is
`branching`; `branch_labels` contains exactly two children with stable IDs,
`parent_id` equal to the move ID, and editable labels. A later branch-specific
move may use `branch_parent`, but assigning moves to branches is not enabled in
RC0.

Spline generation first constructs the ordinary Hermite centreline from all
confirmed moves. With continuation it renders that centreline. With branching it
renders the centreline only through the first branch point, then samples two
outgoing futures. Gradual branching uses a smoothstep separation so the stems
share the initial tangent; abrupt branching uses linear separation so outgoing
tangents differ immediately. The influence radius sets their visible separation.

The uncertainty state and its envelope are distinct. A chunk does not insert a
centreline node: it defines a local interval and a smooth non-negative radius
profile around the current best-estimate state. Balanced uncertainty enters
and exits as a compact bump. Expanding uncertainty grows monotonically from zero
at the interval start to full radius at its end; contracting uncertainty does the
inverse. The field renders nested isotropic meshes with decreasing opacity plus
one crisp incoming centreline. Arbitrary branch trees, branch merging, global
uncertainty and anisotropy are deferred.

The default camera shows Time–Energy as the dominant plane with Uncertainty as
depth. Axis bounds expand only when geometry exceeds them and do not contract
during an editing session.

The Horizon coordinate supports two mappings. Qualitative mode uses the ordered,
non-uniform anchors Now (0.00), Soon (0.12), Later (0.35), Sometime (0.58),
Eventually (0.80), and Landing (1.00). Linear mode maps elapsed dates onto
`(date - start) / (end - start)` and labels the axis with elapsed or calendar
ticks. A Guided landing derives its end interval from the required authored
duration value and unit. Plot markers carry both semantic glyph and move title;
alternating label offsets provide the RC0.1 overlap mitigation.

Shared comparison does not rewrite either mapping. Every contributed trajectory
retains its own temporal mode, anchors, dates, landing mode, primitives,
uncertainty and geometry. The comparison field uses the intrinsic trajectory
parameter `s ∈ [0,1]`, where `s=0` is Now and `s=1` is Landing. Intermediate
differences in temporal representation remain observable information.
