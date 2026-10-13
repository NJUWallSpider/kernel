# Independent test36 review: complete original contract passes

**PASS_COMPLETE_ORIGINAL_CONTRACT.** The revised certificate was independently
replayed against MCM files freshly canonicalized from both actual corpus MPS
files. All three directional claims and the strict-improvement contract are
VERIFIED, with 529,636 obligations and 448,596,660 work. The non-timing statistics
exactly match the author's final receipt. Exact identities, commands, raw
results and request are recorded in `audit/TEST36_COMPLETE_REVIEW.json`;
`audit/review_test36_complete.py` reproduces this review.

## Original promise and exact checked scope

The original `test36-nomf-B1/output/report.md`, lines 5–14, commits the actual
target and promises minimum preservation, retention of every original optimum
in the surviving coordinates, zero recovery of every target feasible point,
and zero eliminated terminals at every source optimum. It explicitly excludes
unrestricted feasible-set equivalence. Lines 231–236 also disclaim an LP-bound
improvement and optimality of the exhibited feasible point.

The submitted request now specifies:

1. An unconditional source-MI to target-MI map with nonincreasing objective.
2. An unconditional target-MI to source-MI map with equal objective and all
   37,616 retained coordinates preserved.
3. A source-MI to target-MI map on the explicit original-coordinate halfspace
   `P <= 0`, with equal objective and all 37,616 retained coordinates preserved.
4. A strict improvement within the complete source-MI model whenever `P > 0`.

Here `P` is exactly the sum of **all 200 original continuous terminal
coordinates**, each with coefficient one. The halfspace and the strict
predicate are equal expressions in the caller request. Their variable indices
were independently reconstructed from the actual source, rather than accepted
from an auxiliary list.

These checked claims close the original scope. A source minimizer cannot have
`P > 0`, because the strict-improvement contract would give a better source
point. Therefore the conditional claim applies to every source minimizer and
produces one complete target point with its same objective and every retained
coordinate unchanged. The unconditional directions equate the minimum values.
The reverse claim recovers each target minimizer as a source minimizer with all
retained coordinates unchanged. Its checked complete map appends zero at every
eliminated coordinate. No original continuous terminal is assumed integer or
rounded from positive to at least one.

## Preserved finding and repair

The earlier two-direction/one-improvement request omitted the coordinate
observations. Those statements alone did not bind optimal-point projection.
The earlier review remains in `audit/TEST36_SUBCONTRACT_REVIEW.{md,json}`, and
`audit/fixtures/test36_request_scope_counterexample/` preserves an independently
checked synthetic counterexample to that incomplete inference. This was a
contract-coverage gap, not an invalid kernel acceptance or a counterexample to
the actual test36 transformation.

The repair adds claim 3 above and the complete reverse observations; it retains
the original unconditional direction and strict predicate. Thus the conclusion
now follows from explicit kernel-verified contracts. The external complete
matrix comparison below is supplementary evidence, not a replacement for the
missing request assertion.

## Independent model and proof checks

An independent standard-library `Fraction` parser checked all 37,816 source
variables, 37,616 target variables and 37,617 rows on each side. Source and
target paths and hashes match the immutable inventory. Every surviving bound,
integrality flag, matrix coefficient, row sense, right-hand side and objective
coefficient was compared. The target is exactly the source's zero-terminal
face in retained coordinates. Every eliminated terminal is an original
nonnegative, unbounded-above continuous variable.

The structure audit reconstructs all 200 chains, every continuous coordinate,
distinct binary inputs within each chain, and the 26 positive layer bounds.
Those bounds sum to 2,238; the binary contribution 195 gives a nonterminal
lower bound of 2,433. A positive generated canonical terminal implies original
objective at least 7,283; the complete feasible point of value 6,425 gives
strict saving 858. In the zero canonical-terminal branch, the strict saving is
at least 4,850 times the original continuous terminal sum. Generated integer
canonical anchors are kept distinct from the original continuous coordinates.

All submitted model, RPA, RPX, request and preparer identities were checked.
Fresh canonical MCM bytes match the submitted bytes. The independently
replayed full request checks every terminal output obligation and both sets of
37,616 observations. A separate count of variable domains, rows, objectives,
leaves and observations agrees with all 529,636 recorded obligations.

The historical complete source point with terminal sum `1/4850` and objective
6,426 was evaluated against every actual bound and row using `Fraction`, then
reassembled to identical RPX and independently VERIFIED. Positive original
terminals remain feasible; the claim excludes them only from optimality.

All 15 saved negative receipts were checked for request binding, binary hash,
nonzero exit and INVALID status. Six conditional/projection attacks were also
independently executed: absent, reversed and incomplete halfspaces, a missing
observation, use of an original row instead of the appended domain row, and a
wrong reverse observation. All six returned INVALID.

## Reproducibility and limits

The reviewed request SHA-256 is
`49b598940e7a2877e03b84fa04fc63cb06df5cb000065de640f790efe622dd82`.
The final author receipt SHA-256 is
`29681560e84828663650cf5afbfc1ed45f9951a94e3b7d9db83fec5d62e040a4`.
The fixed executable is `target/conditional-domain-production/release/rpx`,
SHA-256 `96a6d3048d1deb6681733ab8b7356875f5e76bd1991c26337fe6820726b9c8f8`.
No production code, actual case artifact or acceptance ledger was edited by
this final review.

This review repeated one complete certificate, the fractional positive control
and six small negative certificates. It checked the bindings and saved results
of the other nine large negatives without repeating their execution. The
267,140,625-byte RPA was hash-bound but not independently reassembled here;
the author recorded successful assembly, and the parent performs the cold
delivery check. This is working draft V10, not a protocol-freeze announcement.
No numerical optimum of 6,425, LP equivalence, unrestricted feasible-set
bijection or isolated performance result is asserted.
