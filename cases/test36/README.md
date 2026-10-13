# test36: minimum preservation and retained projection of every optimizer

The complete prepared request is **kernel VERIFIED** on the actual source and target. Independent review against the original report is pending; that review, not this author receipt, closes the corpus scope.

One certificate now binds all four required statements:

1. Every source-MI feasible point maps to a complete target-MI point with nonincreasing objective.
2. Every target-MI feasible point lifts to a complete source-MI point with equal objective and all 37,616 retained coordinates preserved.
3. On the caller-bound original-source halfspace P<=0, where P is exactly the sum of all 200 original nonnegative terminals, the source-MI point projects to a complete target-MI point with equal objective and every retained coordinate unchanged.
4. Whenever P>0, a complete source-MI point has a complete source-MI strict improvement.

Consequently the minima agree and every source integer optimizer has P=0, hence all 200 terminals zero. Claim 3 explicitly binds that optimizer's retained projection; claim 2 recovers every target optimizer with its retained coordinates unchanged. This does not claim unrestricted feasible-set equality, an LP relation, or that 6,425 is the optimum.

The actual source has 37,816 variables and 37,617 rows; the actual target has 37,616 variables and the same number of rows. All 200 original terminals are continuous. `inspect` checks every actual variable, bound, objective coefficient, chain row, the 195-of-200 cardinality equality, and the precise final zero substitution. No audit hint is used as a kernel fact.

## Complete construction

Both nontrivial roots build one common canonical chain tuple using existing SignedLift in 19 batches of ten prefix levels. The longest actual prefix has length 191. Each batch reads only original binaries and previously proved canonical anchors. Ordinary Cases prove required generated anchor/terminal integer properties, every canonical coordinate no larger than its original continuous counterpart, and every original chain inequality. Every output domain and row remains an actual-model obligation.

The original nonterminal objective lower bound is 2,433: its binary contribution is exactly 195, and the remaining 2,238 follows from actual chain rows at prefix layers 2 through 27. Actual layer frequencies and a continuous top-five box inequality bound the contribution of five missing binaries. The numerical bound is recomputed and proved.

The generated canonical terminal sum is integer. In its zero branch, deleting terminals gives the forward target map; the canonical source tuple improves the original objective by at least 4,850 P. In its positive branch, the original objective is at least 7,283, so a complete checked source point of value 6,425 gives constant strict saving 858. Original continuous terminals are never used as integer facts.

The additional conditional claim has no lift. The kernel appends exactly the caller-bound original-coordinate inequality P<=0 after all original source rows. Original terminal lower bounds give -P<=0; EqPair proves P=0. A balanced linear deduction tree proves each terminal upper bound zero. Adding that upper bound to the corresponding original row removes its -terminal term and obtains the actual target row. The objective difference is exactly -4,850 P. The map and every one of the 37,616 coordinate observations are retained identities. The reverse claim likewise supplies all 37,616 observations.

## Evidence and resource policy

The authoritative `preparation.json` records one full three-claim plus one-improvement replay and **15 INVALID attacks**. Its fixed executable is `target/conditional-domain-production/release/rpx`, SHA-256 `96a6d3048d1deb6681733ab8b7356875f5e76bd1991c26337fe6820726b9c8f8`. All 33 commands record the same binary hash before and after execution. These are working draft RPA/RPX 10 contracts, not a new release or protocol freeze.

The complete replay checks 529,636 terminal obligations, using 448,596,660 work under the authorized 1,000,000,000 policy. The identical certificate returns RESOURCE_LIMIT under the former 100,000,000 limit. Raw results are retained. Execution was 3,310,650 microseconds in this functional run; it is not an isolated performance benchmark.

The RPA is 267,140,625 bytes, below the unchanged 268,435,456-byte text limit. The RPX is 177,165,284 bytes. No text, codec, depth or live-fact limit was raised for this certificate.

`oracle.json` retains 5,257 independent Fraction checks covering generalized binary chains with nonminimal real lifts, signed zero ambiguity, exact top-five coefficient identities and fractional box samples. `audit/test36_read_review.md` records the earlier independent mathematical read review; `PROJECTION_REVIEW.md` records the additional conditional projection read review. These supplement, and do not replace, actual-model kernel verification.

Eight refreshed improvement attacks cover zero margin, an exaggerated gap, changed caller predicate, a continuous terminal used as INT, an omitted actual chain row, a new-scope premise, an infeasible constant output and an invalid positive-domain refutation. Six small complete actual-model claim attacks cover absent, reversed or incomplete input halfspaces, an omitted observation, an old row substituted for the domain row and a wrong reverse observation. The fifteenth attack uses the entire valid RPX with a changed complete caller request. Its mismatch must be rejected before any weaker request can stand in for the original contract.

The historical feasible source point with terminal 1/4850 and objective 6,426 is rechecked and remains VERIFIED. Strict improvement excludes positive terminals only from optimality, not from source feasibility.

## Preserved attempts and reproduction

`pre-projection-completion/` preserves the former proof, RPX, request, receipt, README, eight attacks, reverse part and author scripts. Their verified statements lacked the caller-bound optimizer projection and are explicitly marked as incomplete for the full report scope. `attempts/` preserves the original contract blocker and feasible points. `first-verbose-forward/` retains the earlier complete forward representation. The compact author representation reduced repeated sign facts to fit the existing text limit; it slightly increased forward logical work and is not a speed optimization.

Reproduce from the repository root using the fixed executable above:

```sh
python3 tools/prepare_test36_full.py --phase forward
python3 tools/prepare_test36_full.py --phase reverse
python3 tools/prepare_test36_full.py --phase improvement
python3 tools/prepare_test36_full.py --phase projection
python3 tools/oracle_test36.py
python3 tools/finalize_test36.py
python3 tools/check_test36_request_binding.py
```

No production kernel code, semantic version freeze or acceptance ledger was changed by these preparers.
