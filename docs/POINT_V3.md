# Exact point witnesses in RPX/RPA V3

V3 adds requested, exact point statements to the existing directional-map
contracts. The production implementation is `crates/core/src/point.rs`; types
and wire representation are defined by `proof.rs` and `codec.rs`. This is a
deterministic witness checker, with no search or solver invocation.

V6 separately adds strictness for partial affine observations through complete
fiber refutations; see [FORMAT.md](FORMAT.md#complete-point-witnesses) and `FIBER_POINT_V6.md`. The V3 rule described
below retains its complete-coordinate-bijection requirement. V10 also adds
caller-bound complete affine ImageExclusion points; their current contract is in
[FORMAT.md](FORMAT.md#complete-point-witnesses). These version numbers identify
when each variant was introduced; all remain supported by the current verifier.

## Requested statements and interpretation

`PointClaim::Feasible { target, integers, objective }` selects the actual source
model (`target=false`) or target model (`target=true`). Its witness supplies one
rational value for **every** model variable in canonical model order. The checker
verifies every finite variable bound and every finite constraint-row bound on
that same vector. If `integers=true`, variables declared integer must have
integral coordinates; continuous variables remain real-valued. With
`integers=false`, integer declarations are relaxed, but all bounds remain,
including the canonicalized binary interval. An optional objective value must
equal the complete affine objective evaluated at the witness, including its
constant and the canonical minimization normalization of an original maximum.
This is a feasibility/value statement; it does not independently claim optimality.

`PointClaim::Strictness { inclusion_claim }` refers to a directional map claim
that the full verifier has already proved. Write its input LP as P and output
LP as Q; `reverse` determines which actual bound model plays each role. Both
integer-domain flags of that claim must be false, and it must have neither an
objective-level nor a halfspace restriction. The claim's projection pairs
`(i,o)` must be a bijection covering every input and every output coordinate.
In particular, both models must have the same dimension. The witness is an
output vector y in the canonical order of Q. The checker establishes:

1. y satisfies all actual bounds and rows of Q.
2. The single reconstructed vector x, with `x[i]=y[o]` for each projection pair,
   violates at least one actual bound or row of P.

A partial projection, repeated input/output coordinate, invalid coordinate,
non-LP inclusion claim or absent claim index is invalid. A difference in integer
membership or objective value is insufficient for LP separation. No auxiliary
coordinate is guessed, independently chosen or omitted.

## Soundness argument and integration invariant

The mapping verifier proves that for every x in P there is its certified common
output vector F(x) in Q, and that `F(x)[o]=x[i]` for each selected projection
pair. Because all coordinates are covered bijectively, those equations force
F(x) to be the coordinate permutation pi(x). Thus pi(P) is a subset of Q.
The supplementary witness proves y is in Q and pi-inverse(y) is outside P;
therefore y is outside pi(P), proving proper inclusion pi(P) is a strict subset
of Q. Branching map proofs are allowed: projection obligations still apply to
each feasible terminal branch. An empty input domain can be proved by the
existing contradiction rule; a nonempty output point then also establishes
strict inclusion, including dimension zero.

The public `verify_request` entry point checks that all requested contract
arrays exactly match the certificate. It proves every mapping claim and any
requested independent bijection injectivity proofs before calling `verify_points`
with the remaining shared work budget. Requested improvements are checked
afterward, with the same budget.
Successful `verify_points` alone proves only its point checks: its strictness
conclusion requires that mapping-proof precondition. It intentionally does not
re-run or replace the mapping verifier. Points-only feasibility requests are
allowed; a strictness claim necessarily needs a referenced mapping claim.
No certificate is accepted merely because its own declarations are internally
consistent: the caller provides the required request independently.

## Exactness, limits and complexity

Models and witness values must be structurally valid with canonical rationals.
Each numerator/denominator is limited by the shared `MAX_Q_BITS` budget. Every
coefficient-coordinate product and every partial affine sum is checked before
it can affect a mathematical result; crossing the budget is RESOURCE_LIMIT,
even if later cancellation could reduce the final value. Comparisons and
integrality use exact rational arithmetic. Contradictory model bounds are
valid descriptions of an empty feasible set and cannot acquire a feasibility
witness.

Point count is limited to 1,000,000 and total supplied coordinates to
`MAX_TERMS` (20,000,000). Projection-index and uniqueness buffers use checked,
fallible reservation and dimension limits inherited from the validated models.
All counters use checked addition. The work budget charges one unit for each
witness, supplied coordinate, variable examined, expression initialization and
row comparison; two units per expression coefficient (multiply and add); and
one per strictness projection pair. Statistics report verified point count,
coefficient visits and supplementary work. The full verifier adds this work to
mapping-proof work, so splitting a request into several witnesses cannot reset
the budget. Structural model validation is additionally bounded by the shared
model limits, independently of that arithmetic work counter.

Feasibility uses O(number of variables + visited row/objective coefficients)
exact operations; strictness adds O(number of variables) projection storage and
checks at most both complete LPs. A detected violation may stop the scan early,
but every model and every witness scalar was validated beforehand. Large-number
arithmetic has the underlying arbitrary-precision cost; the operation count is
not a bit-complexity estimate. OS-enforced process termination is outside the
structured resource-error guarantee, as for the rest of the kernel.

## Executed evidence and reproduction

Run `cargo test -p kernel-core --test points`. The suite covers common-coordinate
consistency, row and variable bounds, integer versus LP domains, binary bounds,
objective constants and maximum normalization, model selection, zero dimensions,
contradictory bounds, strictness in both directions, coordinate permutations,
partial/duplicate/out-of-range projections, false separating points, malformed
rationals, large products and partial sums, and shared work limits. Full-request
tests establish a real inclusion map before strictness, and reject a valid
separating point paired with an invalid map proof.

`audit/generate_point_oracle.py` independently evaluates rational models using
Python's `fractions.Fraction`. It writes 480 deterministic semantic vectors
(240 accepted, 240 rejected, seed 5264435) to
`tests/vectors/point_oracle.json`: 240 feasibility/value vectors and 240 complete
permutation/separation vectors with varied dimensions, coefficients and signs.
The Rust suite consumes the checked-in expected decisions without invoking the
generator or a solver. Reproduce with `python3 audit/generate_point_oracle.py`.
These tests provide executable cross-checks, not a formal proof of the Rust
implementation.
