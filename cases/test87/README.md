# Actual test87 staged set-cover normalization

The complete certificate is **VERIFIED** against the immutable actual source and
final target under `/Users/bhz/Code/reform_test/runs/test87-nomf-B1`. All six targeted
full-certificate mutations are **INVALID**. `preparation.json` records the exact
model, request, proof and kernel hashes, raw replay result, and every rejection.

The source has 63,009 binary variables, 507 covering rows and positive costs one
or two. The final target has 20,342 integer variables and 440 rows, including nine
original variables fixed to one. The required contract has two integer directions:
forward preserves feasibility with nonincreasing cost; reverse preserves objective
exactly. Thus feasibility and minimum are preserved. The certificate does not
claim equality of all original assignments, nonoptimal objective values or LP sets.

All three actual reduction stages are bound to complete source coefficients and
domains in `independent_structure.json`. The preparer checks the ten singleton-row
witnesses, nine distinct fixed choices, 23 covered-row deletions, 44 containment
witnesses, three empty-column deletions and 42,664 terminal column replacements.
Every retained target row, bound, integer declaration and objective coefficient is
compared to the resulting full model.

For each affected survivor w, one joint interval defines
`y[w]=OR(old[w], old[v] for all replacements v->w)` by lower bounds equal to each
old binary and upper bounds one and their sum. Every compatibility premise is
proved in the old scope. Ordinary integer Cases search factor sums in a balanced
tree and prove the new coordinate is zero or one. This handles simultaneous
many-to-one replacement without assuming the survivor was previously unselected.

For each retained covering row, actual old inequalities and the new lower rows
imply `1-sum(m[w]*y[w])<=0`. Divide by M=max(m), add nonnegative-domain inequalities,
and round using INT(-sum y) to obtain `1-sum y<=0`. This preserves the original
integer covering obligation even when many old columns merge into one survivor.
Cost improvement follows from the actual OR upper row and each checked difference
`cost[v]-cost[w]>=0`, together with fixed-one equalities and empty-column bounds.
The complete current vector, row facts and cost bound pass jointly through all
three stages. Reverse reconstruction restores all removed nonfixed variables as
zero and retains the actual final fixed variables; all original rows and domains
are checked individually.

The proof uses 16,355 intervals in three batches, adding 91,729 rows. It checks
251,002 terminal obligations and 59,019 branches, charges 46,145,966 work units and
peaks at 93,668 live facts, within default limits. RPA is 101,461,019 bytes and RPX
is 70,526,292 bytes. Preparation took 116.625 seconds; the recorded replay took
2.185 seconds end to end, including 1.644 seconds of proof execution. These are
single development observations, not isolated benchmarks or solver speed claims.
Preparation and verification costs are deliberately reported separately.

The independent exact oracle in `audit/setcover87_oracle.json` checks all 8,190
Boolean assignments for local OR groups of sizes one through twelve with varied
fractional positive costs, plus 18 complete actual-model forward/reverse points.
It checks stagewise cost improvement, every actual bound and row, and exact reverse
objective equality. These are supplemental checks; the full RPX certificate proves
the requested universal relation. A separate agent also read the balanced OR,
rounding, cost and reverse-row construction without finding a mathematical issue.

The first preparer attempt stopped before emitting a complete RPA because it used
the Exact sentinel as a linear premise for a zero remainder. Its code and failure
record are preserved under `attempts/initial-preparer/`. No kernel was invoked for
that failed preparation. The corrected preparer uses exact sparse accumulation to
avoid repeated whole-expression copies and handles the zero remainder explicitly.
No production rule, parser limit or verification budget was changed.

Reproduce the complete proof and all rejection checks:

```sh
python3 tools/prepare_test87.py --kernel target/validation-checkpoint-v7-rational/release/rpx
python3 tools/attack_test87.py --kernel target/validation-checkpoint-v7-rational/release/rpx
python3 audit/setcover87_oracle.py
```

The attacks omit an interval premise, cite a continuous variable as integer, alter
the integer expression used by Round, negate an inequality cost multiplier,
restore a deleted source variable as one and omit a middle original-row check.
Each uses the unchanged full caller request and actual models. Large mutated RPA
and RPX files are temporary: `attack_test87.py` deterministically recreates them,
and the receipt retains their hashes and exact rejection reasons.
