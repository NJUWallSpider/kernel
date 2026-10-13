# Actual test47 exchange normalization

The complete certificate is **VERIFIED** against the immutable actual source and
final target under `/Users/bhz/Code/reform_test/runs/test47-nomf-B1`. All seven
mutated certificates are rejected as **INVALID**. `preparation.json` records the
exact input, proof, request and release-kernel hashes, command outputs and rejection
reasons. Source has 151 variables and 13 rows; target has 118 variables and 13 rows.

The two requested integer directions preserve the exact objective, original
continuous coordinate `x151`, and total number of selected binaries (counting each
aggregate coordinate by its value). They therefore preserve every attainable
objective value. Individual binary identities, a feasible-set bijection, relaxed
feasible sets and a numerical optimum are not claimed.

The forward construction normalizes all 31 removed binaries successively. For
each current binary v, it uses its 20 distinct retained dominators and prefix ANDs
to transfer v to the first unselected dominator. The cardinality bound 20 ensures
such a dominator exists when v is selected. One joint IntervalLift batch per stage
introduces the 20 continuous prefixes; ordinary integer Cases prove their Boolean
values. The complete current vector retains binary domains, total cardinality and
all 12 covering inequalities at each exchange. Coefficient improvements are exact
nonnegative differences from the actual source rows. The final map aggregates two
identical-column pairs and maps every target variable.

The reverse construction uses two menus with activation one, maximum index two
and index equal to the target aggregate count. Their three binary states give the
original pair `(q1+q2,q2)`. Removed variables become zero. Ordinary terminal checks
cover every original bound, integer flag, row, objective and observation. Neither
direction trusts the corpus audit or a solver as a proof authority.

The final certificate uses existing V7 rules only: 31 interval batches introduce
620 continuous variables and 8,370 rows, and one menu batch introduces six binary
variables and four rows. Verification checks 837 terminal obligations and 8,959
local branches, charges 38,691,982 work units and peaks at 12,274 live facts, all
within default limits. RPA is 22,149,067 bytes; RPX is 20,219,652 bytes. The recorded
latest replay took 2.630 seconds end to end, with 2.537 seconds in execution. This
is a single replay observation during development, not an isolated benchmark.

An earlier complete version used a linear search for a zero AND factor. Its
logical proof depth was 53, but JSON container depth was 186 and assembly reached
the fixed serde nesting limit 128. Its unchanged RPA, preparer, request and raw
failure receipt are preserved under `attempts/linear-and/`. The receipt originally
classified this as INVALID; the failure was an importer resource limitation,
not evidence that the model relation is false. The final proof uses balanced
integer-sum splits to locate a zero factor, giving logical depth 38 and JSON depth
126. No parser or verification limit was increased.

`audit/normalization_47_48_inventory.json` contains the independent complete matrix,
domain and dominance audit. `audit/normalization47_oracle.json` supplements the
certificate with an independent exact point-level check: 952 points across ten
varied cardinality families with fractional and negative row coefficients, plus
289 points checked against both complete actual models. These include all-zero,
full-cardinality, late transfer and multiple-removal selections. This sampling is
supplemental evidence; universal acceptance comes from the full RPX proof.

Reproduce preparation, canonicalization, assembly, complete verification and all
seven rejection checks from the repository root:

```sh
python3 tools/prepare_test47.py --kernel target/release/rpx
python3 audit/normalization47_oracle.py
python3 audit/audit_normalization_47_48.py
```

The attacks omit an interval premise, cite a continuous coordinate as integer,
negate a genuine inequality multiplier, alter the objective multiplier, omit the
count observation, change a menu maximum and incompletely reconstruct an aggregate
pair. Each is checked against the unchanged actual models and full caller request.
