# Independent working-V10 input-halfspace review

Result: **PASS; no mathematical acceptance defect found** in the reviewed
implementation. The reviewer did not author or edit the production change.
This is source/semantic review plus finite byte tests, not a formal correctness
proof. Source hashes and executed test evidence are recorded in
`audit/CONDITIONAL_WIRE_REVIEW.json` and `audit/CONDITIONAL_WIRE_TESTS.log`.

The new caller field is an explicit restriction of one directional input set:
the complete actual model intersected with `H(x)<=0`. It is not an assertion
that H is globally valid. The claim/certificate equality includes H, and H is
validated against the original directional input dimensions before construction;
for a reverse claim that is the actual target model. Original coordinates,
bounds, rows and objective remain intact. `RowUpper` of the appended row is H;
`RowEq` cannot turn a one-sided inequality into an equality.

`prepare_restricted_domain` performs one model copy and appends the optional
objective-level equality before the halfspace row. Each Expr is copied exactly,
including its constant. An empty intersection is a valid vacuous conditional
claim and supplies no nonemptiness or optimum assertion. Continuous coordinates
retain real-valued semantics; a halfspace adds no integrality predicate. Every
Return still proves every actual output bound, requested integer condition,
row, objective relation and projection. Output models are not silently restricted.

Top-level claims each start from the actual model and fresh proof state.
Restrictions do not leak to siblings, points or improvement blocks. Feasible
and ImageExclusion points continue to use complete actual models. Both the
`verify_request` precheck and the direct point-checker entry reject restricted
Strictness/FiberStrictness inclusions. Whole-model V7 bijections reject either
restricted direction. Legacy inverse references reject if either participating
claim has a halfspace: composition alone would not establish membership in the
other restricted domain. Existing objective-level-only inverse membership
obligations are unchanged.

The original objective-level API is retained as a wrapper. With a level and no
halfspace, the generated row, name prefix, exact coefficient expression and
budget formula remain the previous ones. Combined domains fix the row order as
original rows, objective equality, halfspace. Input model validation, original
Expr validation, row/term limits, checked sizes, allocation accounting and name
generation precede returning the extension. Construction is charged against the
request's remaining work and then added to the same statistics; nested proof
work receives no reset. New counters are omitted when zero, preserving previous
receipt statistics. Restrictions are not a new existence theorem.

The V10 Claim byte extension is exactly flag bit 3 plus one Expr after the
existing objective-level option, without an extra option byte. The writer
selects V10 whenever H is present. The decoder rejects bit 3 in versions 1–9,
all bits 4–7, nonzero reserved bytes, malformed scalar/expression data and
trailing bytes. The text version check likewise rejects a present H under an
older header. With H absent, the prior flag byte and payload are unchanged.
`docs/FORMAT_V10_DRAFT.md` agrees with these semantics and the row/wire layout.

Independent `struct`-written files in `tests/vectors/conditional-*` exercise
continuous `x in [0,1]`, the conditional identity inclusion into `x<=1/2`, its
exact objective and coordinate observation, and its conjunction with objective
level `15/2`. A third manually encoded V10 fixture contains a real unrestricted
Claim plus ImageExclusion, so the None compatibility test exercises the Claim
record rather than only an empty claim array. Its exact bytes also match the
preserved pre-halfspace V10 executable; see
`audit/validation/conditional-old-none-baseline/receipt.json`.

The three new integration tests pass. They check 354 exhaustive truncations,
2,520 forbidden flag/reserved-byte values, 44 old/unsupported text and binary
version changes, and 16 persisted malformed examples. They check both directions
of RPA/RPX correspondence and exact MCM round trips, caller condition binding,
unchanged witness rejection after changing H, and unchanged old None bytes.
The bytes originate in `tests/vectors/generate_conditional_vectors.py`, which
uses only standard Python struct/Fraction/JSON and never calls a Rust encoder.
The root-authored domain tests provide additional semantic coverage and are
separate from these independent tests; this reviewer did not rerun the full suite.

The missing test36 property still requires its additional actual conditional
projection certificate. Strict improvement on P>0 and a complete equal-objective
projection on P<=0 jointly cover every attained source minimizer, but neither
may be labelled as the compound property alone. The small verified request-scope
counterexample in `audit/fixtures/test36_request_scope_counterexample/` explains
why the previous request was insufficient without asserting that the actual
test36 transformation is wrong. This report does not itself certify a revised
test36 request or freeze V10; those require their own complete execution receipts.
