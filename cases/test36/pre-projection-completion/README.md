# test36: minimum preservation and all-optimizer terminal exclusion

The **complete contract is VERIFIED** in one certificate: a complete source-MI to target-MI map with nonincreasing objective, an equal-objective target-MI to source-MI recovery, and a separately caller-bound strict-improvement statement whenever the sum of all 200 original terminal variables is positive. Since their original bounds are nonnegative, this proves that every source integer optimizer has all 200 terminals zero. It does not claim feasible-set equality, an LP relation, or that 6,425 is the optimum.

The actual source has 37,816 variables and 37,617 rows; the actual target has 37,616 variables and the same number of rows. All 200 original terminals are continuous. `inspect` checks every actual variable, bound, objective coefficient, chain row, the 195-of-200 cardinality equality, and the precise final zero substitution. No hint is treated as a proof fact.

## Complete construction

Both nontrivial roots build one common canonical chain tuple using existing SignedLift in 19 batches of ten prefix levels. The longest actual prefix has length 191. Each batch refers only to original binaries and already proved canonical anchors. Ordinary Cases prove every required anchor/terminal integer property, each canonical coordinate no larger than its original continuous counterpart, and every original chain inequality. The complete final output is checked against the actual model.

The original nonterminal objective has lower bound 2,433. Its binary contribution is exactly 195. The remaining 2,238 is derived from the actual chain rows in prefix layers 2 through 27: layer frequencies and the continuous top-five box inequality bound the contribution of five missing binaries. The audit's numerical bound is recomputed and proved rather than accepted as authority.

The canonical terminal sum is a generated integer expression. In its zero branch, deleting those coordinates gives a complete target-feasible map, while the complete canonical source tuple improves the original objective by at least 4,850 times the caller-bound original terminal sum. In its positive branch, the original objective is at least 7,283, so the independently checked complete feasible tuple of value 6,425 gives constant strict saving 858. Both branches supply all actual variable domains and rows.

## Evidence and resource policy

`preparation.json` records the authoritative full request replay and eight INVALID attacks. The fixed executable is `target/next-contracts-initial/release/rpx`, SHA-256 `a0875d7e7f7577bf328c2a6a7cb8db4b7bd8e0aaa6c3dc673dc067ceebaba875`; each command records the same hash before and after execution. The certificate uses **working draft RPA/RPX 10**, not a new release or freeze.

The final replay checks 378,770 output obligations, two directional claims and one strict-improvement claim. It uses 444,910,457 work under the currently authorized 1,000,000,000 policy. The identical certificate returns RESOURCE_LIMIT with the former 100,000,000 limit; that raw result is preserved. Timings are functional verification measurements, not isolated benchmarks.

`oracle.json` records 5,257 independent Fraction checks: generalized binary chains with nonminimal real lifts, signed zero ambiguity, exact top-five coefficient identities, and fractional box samples. `audit/test36_read_review.md` records an independent read-only mathematical review. All actual-model conclusions still come from the kernel.

The eight attacks cover zero strict margin, an exaggerated constant gap, a changed caller predicate, an original continuous terminal used as INT, an omitted original chain row, a new-scope extension premise, an infeasible constant return, and misuse of the weak `-P<=0` assumption as a positive-domain refutation. The historical source point with terminal `1/4850` and objective 6,426 is rechecked and remains VERIFIED; it is not excluded from source feasibility or falsely declared integer.

`attempts/` preserves the original caller-contract blocker and feasible points. `first-verbose-forward/` preserves an earlier complete successful forward representation. The compact author representation removes repeated intermediate sign facts to keep the complete RPA within the unchanged 256 MiB text limit; it does not change the inference rules. It slightly increases forward arithmetic work and is not claimed as a speed optimization.

Reproduce from the repository root:

```sh
python3 tools/prepare_test36_full.py --phase forward
python3 tools/prepare_test36_full.py --phase reverse
python3 tools/prepare_test36_full.py --phase improvement
python3 tools/oracle_test36.py
python3 tools/finalize_test36.py
```

No production kernel code, semantic version freeze or acceptance ledger was changed by these preparers.
