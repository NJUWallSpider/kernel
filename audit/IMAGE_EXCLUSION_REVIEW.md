# Independent ImageExclusion implementation review

Root reviewed `point.rs` after implementation by corpus_audit. No soundness
finding was identified. Root authored the surrounding proof/codec integration,
so independent-author review here covers the point helper; the independent
Python wire implementation and separate Rust tests cover the codec delta.

The precise result is an existential separating image: there is a complete LP
point of the selected actual model whose caller-specified full affine image is
outside the opposite actual LP model. It asserts neither containment nor the
nonexistence of completions of partial observations. The map is part of the
separately supplied caller request, and `verify_request` compares every field.

The public helper checks both complete models, every witness scalar, exact point
and map dimensions, and every map expression against original input coordinates.
All expressions are validated before separation can return. It checks complete
input feasibility with integrality relaxed, evaluates every coordinate of the
same full image with checked intermediate products and partial sums, and then
requires an actual opposite-model row or bound violation in LP mode. A merely
fractional value cannot establish exclusion. Surplus refutation blocks reject.

Early exit on the first opposite-model violation is sound: all actual model
data and all image coordinates have already been validated, and that one
violated constraint suffices to prove nonmembership. Later unused row evaluations
need not be performed. This does not certify an exact number of violated rows.

Support arithmetic, total map terms, complete point counts and fallible image
reservation have explicit bounds. Every validation/evaluation charge shares the
remaining request work limit; there is no reset between points. Existing
Strictness/FiberStrictness prerequisites remain unchanged. Public helper calls
with no points return zero statistics but do not purport to verify any model
relation; the full verifier still validates actual models separately.

Evidence: twelve dedicated image tests, including a 1,875-point scaled-integer
oracle, malformed dimensions/order/scope and exact work boundaries; the combined
V10 independent wire fixture; and root's full actual test62 regeneration/replay
in `audit/validation/completed-46-62-83-independent.json`. The original two MI
blocks, bijection witness, all 4,500 point values and actual MCM bytes were
preserved. The 500 image expressions equal the existing retained-coordinate map.
All six new actual-case corruptions reject in the recorded author receipt.
This review is not a formal proof of the implementation or its dependencies.
