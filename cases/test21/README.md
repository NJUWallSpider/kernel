# Actual test21: complete dominance maps

**VERIFIED**, including all six negative tests returning INVALID. The certificate
uses the complete actual source and committed target under
`/Users/bhz/Code/reform_test/runs/test21-nomf-B1`: 87,482 source binary variables
and 36 equalities become 46,168 target binary variables and 35 equalities.

The four requested directions establish source-to-target feasibility with
nonincreasing objective and target-to-source feasibility with equal objective,
for both the mixed-integer models and their continuous relaxations. This preserves
feasibility existence and minimum objective. The reduction can discard original
choices and nonoptimal objective values; no bijection, original-coordinate
projection, global feasible point or numerical optimum is claimed.

The untrusted preparer checks the entire support and actual cost of each of
41,292 duplicate-column eliminations. Each of 21 further replacements consists
of surviving columns with disjoint supports whose full union equals the deleted
support and whose total cost is no greater. The forward map sums every original
contribution into its final representatives. A replaced column contributes to
both members of its disjoint replacement. All target coordinates are constructed
together. The exceptional removed `x600` is handled by the actual equality
`c1-c2`, whose exact expression is `x599-x600`.

All forward aggregates are nonnegative sums. For their upper bounds, 29,500
multiple-contributor groups are assigned to 26 actual source partition rows.
Within each assigned row their source contributor sets are disjoint. The source
row and lower bounds on unused variables first prove an upper bound on the total
selected sum. A balanced tree then proves each child's upper bound by adding the
sibling's nonnegative lower bound. Single-contributor coordinates use their
original variable bounds. This avoids copying a large source row into every
individual upper-bound proof. Integrality follows from exact integer sums in
the mixed-integer direction; the same affine bounds also prove the relaxed maps.

After substituting the complete forward map, every target equality matches an
actual source row. The full objective difference is the cost-weighted
`x599-x600` equality plus nonnegative multiples of original variable lower
bounds. The reverse map restores `x600=x599`, assigns every dominated deleted
variable zero and retains other coordinates. It restores row `c2` using target
`c1`, satisfies every original domain and row, and preserves the entire objective
exactly. Every one of these obligations is checked against the actual models.

The proof uses only RPX/RPA 1 linear rules and complete affine Return maps. No
production code or trusted theorem was added. `tools/prepare_test21.py` checks
all proof expressions and terminal obligations with independent Python Fraction
arithmetic, using sparse accumulation to avoid repeated large dictionary copies.
Preparation hints and historical verification outcomes are not trusted premises.

The actual kernel checked 668,396 terminal obligations, 7,367,782 linear terms
and 2,202,386 substitution terms, charging 29,294,258 work units. The certificate
has 44,328,546 RPX bytes. Preparation took 56.217 seconds; a single release replay
took 2.665 seconds including decoding, with 2.243 seconds in execution. These
are preparation observations, not an isolated benchmark. The full source,
target, request, proof, helper and binary identities and command outputs are
preserved in `preparation.json`.

Six attacks respectively omit a contributor, omit a sibling lower bound,
reverse a partition equality multiplier, lose the alias cost correction,
incorrectly zero the reverse alias and weaken the objective claim while keeping
the caller request. All are recorded with exact rejection messages and hashes.

Reproduce the complete actual path and attacks:

```sh
python3 tools/prepare_test21.py --kernel target/validation-checkpoint-v7-rational/release/rpx
```
