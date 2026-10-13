# Explicit objective-level domains: test80 design

Status: proposed after V8; no production implementation or full test80 certificate is claimed here. The actual source and target remain the original corpus MPS files. `tools/audit_test80.py` and `cases/test80/optimal_face_structure.json` record the separate complete structural audit.

## Actual requested relation

The committed test80 report promises a bijection between **all original integer optimizers** and all feasible integer points of its actual final model, with minimum −160. It explicitly excludes suboptimal original points and does not claim preservation of the original LP relaxation. Source: `test80-nomf-B1/input/model.mps` (14,387 variables, 10,765 rows); target: `output/reformulated.mps` (2,801 variables, 175 rows). Replacing the source input by an externally cropped model would leave the main claim unproved.

The source consists of 470 binary assignment vectors X of length 16, 221 binary Y vectors of length 16, 221 binary P vectors of length 15, and 16 binary B coordinates. Eight B coordinates already have bounds [1,1]. Its entire objective is `f = sum(P) − 10 sum(B)`, with constant zero. All coordinates, all row families and all target fields must be checked from the actual bytes; names serve only as indices to candidate identities.

The exact lower-bound identity is `f + 160 = sum(P) + 10 sum(1−B) >= 0`. A full feasible point selecting position zero in every X/Y vector, P=0 and B=1 attains −160. Consequently the optimizer set is exactly the feasible objective level `f=−160`. On that level the nonnegative identity forces every P=0 and B=1. This implication uses bounds and exact linear arithmetic, not a new optimality axiom.

## Minimal contract addition

Add one default-absent exact scalar field to a directional claim:

```
input_objective_level: Option<Q>
```

When absent, the domain is the complete actual input feasible set with the requested integrality mode, exactly as before. When present with L, the domain is the intersection of that same complete feasible set with `{x : f_input(x)=L}`. A level is not by itself claimed optimal or nonempty. In particular an empty level supports only a vacuous direction, and cannot establish attainment.

The kernel constructs the restricted proof domain itself: preserve the original variable, row, bound, name and objective prefixes and append one equality row whose expression is the full actual input objective and whose two bounds are L. The new row index is the original row count. No input variable is removed, no bound is replaced, no original row is omitted, and no supplied expression may stand in for the actual objective. `RowEq` therefore denotes `f_input−L=0`, including the original objective constant. References in other claims start afresh and cannot see this equality.

Each Return still checks every actual output-model obligation. Projection and affine-observation dimensions are checked against the original models before this internal construction. Existing Flow/Interval/Menu/Signed extensions may operate inside the declared restricted scope after their ordinary premises, but still cannot be used with the legacy affine inverse field. Integer-mode restrictions remain unchanged.

### Essential inverse-domain closure

Existing full-coordinate composition alone is insufficient when the opposing map has a restricted domain. If claim C references opposing claim D through `inverse`, and D has level L, **every Return of C must additionally prove**:

```
EQ(f_actual_output(map) − L)
```

This proves that C's output actually belongs to the domain where D was verified. It is a separate obligatory equality even if C has no objective-preservation request. Existing direction/mode checks, root-affine requirements and all-coordinate inverse equalities remain unchanged. The output's original bounds/rows already supply every other part of D's input domain. The row must use D's caller-bound level, not a certificate-local replacement.

Define the new obligation after the existing inverse-coordinate equalities and before the existing input-lower-bound obligation. If there is no restricted opposing inverse, no obligation is added and old versions keep their ordering. For two reciprocal verified claims, complete domain closure and both compositions prove a bijection between the stated domains. A restricted map never implies a bijection on the unrestricted actual source.

Initially reject any V7 `BijectionClaim` whose forward or reverse directional claim has a level restriction. The current paired-domain builder represents the whole actual input, and adapting its advertised semantics is unnecessary for test80. Likewise reject V3 `Strictness` and V6 `FiberStrictness` when their referenced inclusion claim has a level restriction: their present meaning is about the actual whole LP domains. Ordinary `Feasible` point witnesses remain checks against the complete actual model. Refutation and direct injectivity helper synthetic claims have no restriction.

The existing `input_objective_lower` obligation is evaluated over the direction's declared domain. To certify a global lower bound for the actual model, its claim **must be unrestricted**. Documentation and any result presentation must preserve that distinction.

## Complete test80 request using existing arithmetic

Use three directional claims and one complete point witness:

1. Unrestricted source → target, integer modes enabled, a constant target feasible point, objective `NonIncreasing`, and `input_objective_lower = −160`. The global lower bound follows directly from the actual P lower bounds and B upper bounds. The constant map must satisfy every actual target obligation.
2. Source restricted to objective −160 → target, integer modes enabled, objective `Equal`, affine inverse claim 2 (zero-based index), and a complete affine map F.
3. Unrestricted target → source, integer modes enabled, objective `Equal`, affine inverse claim 1, and complete affine reconstruction G. The inverse-domain closure obligation proves `f_source(G(y))=−160` independently of its composition checks.
4. A complete source integer feasible point whose checked objective is −160.

Items 1 and 4 prove global optimality and attainment on the original source. Items 2 and 3 prove `F: argmin(source) ↔ feasible_integer(target):G`. This compound caller request exactly expresses the committed claim without a new trusted optimum recognizer or a model whitelist. The constant map in item 1 is only a device to use the existing directional bound contract; it must not be presented as the parameterization.

An alternative top-level `OptimalFace` claim could package these checks, but would introduce more request indexing and aggregation code. The generic exact-level field plus mandatory inverse closure is the smaller auditable change. No new scalar inference, optimizer, sign test, search procedure or existential theorem is needed.

## Complete forward proof plan

On the appended objective equality, derive P=0 and B=1 from the sum of nonnegative quantities. Prefix/suffix sums avoid quadratic repetition when isolating the 3,315 P terms and 16 B terms. All 300 linked assignment groups have actual rows, for every position j and nonempty set S of size k:

```
sum(t in S) Y[t,j] − X[i,j] <= k−1
sum(t in S) Y[t,j] − k X[i,j] >= 0
```

For a member t, combine the second row with upper bounds of the other k−1 Y terms, divide by k, and add `(1−1/k)` times the lower-bound fact `−Y[t,j]<=0`. The result is

```
X[i,j] − Y[t,j] − (k−1)/k <= 0.
```

`INT(X[i,j]−Y[t,j])` and existing Round give `X[i,j]<=Y[t,j]`, including k=1. Sum these inequalities and the actual X assignment equality. The actual passon upper row, together with P=0, gives the opposite inequality on the Y sum. Thus each covered Y vector has sum one. For every coordinate, subtract the remaining-coordinate implications from the two sum equalities to obtain the reverse inequality, and use EqPair to derive `X[i,j]=Y[t,j]`.

Every Y group is covered. Build a graph from **all** actual linked sets; along each witnessed edge the complete vectors agree. Its five components have representatives/sizes `(0,183), (1,18), (60,18), (68,1), (195,1)`. A spanning forest suffices for concise equality propagation, but the reverse proof checks every actual link row, not just forest edges.

F takes the five representative Y vectors and all 170 unlinked X vectors, and sets the actual target `obj_constant` to one. G restores linked X and Y from their component vector, unlinked X from its retained target vector, P=0 and B=1. F/G compositions cover every one of the original 14,387 coordinates and every one of the 2,801 target coordinates. No arbitrary one-hot choice replaces a free unlinked X vector.

The reverse proof substitutes G into all 10,765 source rows, bounds and integer domains. Group equalities plus actual target bounds prove each row; residual bounds are 0, −1, −310 or −61. The full source objective becomes −160. Target checks include all 175 equality rows and the fixed objective coordinate. There is no LP claim because the forward coordinate-rounding step uses integrality.

## Format, resource and rejection requirements

Reserve a new RPX/RPA version after V8; do not change old-version claim bytes or semantics. In that version append `option<Q>` to each claim's existing fields, with ordinary canonical scalar and optional-tag checks. Older decoders reject the new version and RPA headers below it reject a nonempty restriction. Version discovery considers the restriction even in claims whose proof immediately closes by contradiction. Caller request equality includes the exact level; changing −160 to −159 is a contract mismatch.

The kernel-created equality uses checked row-count/term-count arithmetic, validated canonical Q values, fallible controlled buffers and the remaining shared work budget. Copy work and added objective support are charged before expansion. The modified proof domain is validated, including collisions in generated row names, and preserved original rows retain their exact indices. No extra proof depth is needed: the restriction is a caller-declared domain, not a theorem endpoint. Any implementation may avoid full copying later only with the same logical row and budget behavior.

Required adversarial tests include:

- Nonzero objective constants and normalized maximization; the full canonical objective must define the level.
- A correct restricted map whose image misses the opposing inverse's level; composition identities alone must reject it.
- Different levels in otherwise equal requests; absent versus present zero; malformed/noncanonical or over-budget scalars.
- Missing/surplus closure equality, incorrect row index, a sibling or another claim attempting to use the restriction row, and unknown fields.
- Empty or unattained levels; proof of a level bijection alone must never produce an optimality/attainment result.
- A source with a better feasible point: restricted bijection can hold but the unrestricted global bound claim must fail.
- A wrong constant reconstruction of an unlinked source coordinate; complete inverse checks must fail.
- Missing middle original bound/row or target equality; all ordinary obligations remain mandatory.
- Filtered V7 bijection and both existing strictness types must reject explicitly until their domain semantics are separately extended.
- Shared work exhaustion, row/term limits, input prefixes, renamed/permuted models, nested existing extensions and old-version byte regression.

This proposal is motivated by the fully indexed actual case, but its semantics apply to arbitrary exact objective levels. Only a completed versioned implementation, adversarial tests and full actual-model RPX replay can move test80 from an audited design to certified coverage.
