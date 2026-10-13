# test37 — complete indicator tightening and strict LP projection

Status: **VERIFIED** on the unchanged actual source and final target, using the frozen V8 verifier and an RPA/RPX 6 certificate. No production rule or parser was changed for this case.

The certificate proves equality of the complete mixed-integer feasible sets under the retained-coordinate projection and its fixed-coordinate inverse, preserving every objective value. It separately proves target-LP inclusion in the source LP and strict containment after projecting the source LP onto all 317 target coordinates. This is a set relation; no integer feasible point, optimum, LP objective gap, or solver speed improvement is asserted.

## Bound actual models

- Source: `/Users/bhz/Code/reform_test/runs/test37-nomf-B1/input/model.mps`, SHA-256 `5189af38fee754d9e35e6b6b7838fd55d496a447f794fdc8bfd4015bf5f67a1e`; 322 variables and 396 rows.
- Final target: `/Users/bhz/Code/reform_test/runs/test37-nomf-B1/output/reformulated.mps`, SHA-256 `5b96c086c4f542e4544506f2ecafc659a0ff1d4b9b8480341a1ad06dc905b1a8`; 317 variables and 392 rows.
- The source fixes the unused continuous `x20` to 1. Four binary selectors `x168,x183,x192,x286` are proved zero. All other coordinates are retained with their complete original bounds and integrality declarations.
- The target tightens exactly 262 rows and removes four redundant rows. Twelve rows with small nonzero sums of positional coefficients retain every encoded coefficient and RHS. Their decimal asymmetries are not rounded away.

The preparer independently reconstructs every target field from the actual edits and compares it against the complete target. Both canonical MCM models were independently decoded and compared, field for field, against the Python Fraction MPS parser. Audit JSON provides row/path locations only; none of its claimed numeric bounds or PASS assertions is accepted as a kernel premise.

## Complete proof

A source indicator row is `A - M*y >= r`, where the selector has actual bounds `[0,1]` and `M > 0` is read from the row.

1. For each removed selector, the actual continuous bounds imply `A <= U`. Combining them with the row gives `y - (U-r)/M <= 0`, with the exact fraction strictly between 0 and 1. `Round` and the actual `VarInt` give `y <= 0`; `EqPair` with its actual lower bound gives `y=0`. The two fixed bounds give `x20=1`.
2. Seventy-two original-row combinations derive positional difference bounds. Each uses the actual row, nonnegativity of its selector, and the exact upper box bound of its horizontal terms. Seventy-two supplied paths are checked by ordinary `Lin` combinations: every coefficient telescopes to the stated positional difference.
3. Each tightened row gets a certified lower bound `L-A <= 0` from those path facts and the actual horizontal lower box bounds. A two-way integer `Cases` proves the complete target row. At `y=0`, add the fixed-zero equality and the nonpositive constant `new_rhs-L`; at `y=1`, combine the original row with `(new_M-M)*(y-1)=0`. Every new RHS and coefficient comes from the actual target, with the active threshold checked exactly.
4. The forward map copies every retained coordinate. The reverse map copies them back and appends the five proved constants. Every output bound, integer declaration, row, objective, retained-coordinate observation and both full affine inverse identities is checked. The reverse LP direction uses only linear bounds and rows: an old tightened row follows from the new row plus `(M-new_M)*(y-1) <= 0`; the four deleted rows follow from complete continuous box bounds.
5. The complete rational source-LP point from the trajectory is checked against all source bounds and rows by the kernel. The kernel then forms a fiber in the actual target with an equality for **each of the 317 observations**. A single exact `Lin` combines actual target row `c22` and its fiber equalities, yielding `406000 <= 0`; `Absurd` closes the fiber. This proves strict projected LP containment. It does not misuse the older complete-coordinate permutation strictness rule across different dimensions.

The proof has 5,269 final obligations, 262 case splits, no existential lift, and one full point/fiber check. Statistics report 122,392 work units and a peak of 816 live facts. The `bijections: 0` counter refers to the separate V7 paired-domain mechanism; both required full affine inverse identities are proved by the older reciprocal inverse contract.

## Artifacts and checks

- `proof.rpa`: complete 402,791-byte readable certificate; no omitted repetitions or unchecked helper theorem.
- `proof.rpx`: 261,056 bytes; SHA-256 `7b6ce5cd35ec890a64abc1cafdfa99ece1d8db7e92fc532a48d8a2b72af0eb83`.
- `source.mcm`, `target.mcm`, `request.json`: canonical models and explicit requested claims.
- `preparation.json`: full process receipts, model/certificate/binary identities, timing, work counts and all attack results.
- `exact_structure.json`: independently recomputed exact bounds, preserved asymmetric rows and full separating point.
- `negative/`: all eight complete mutated RPA/RPX inputs and changed requests where relevant, retained for reproduction.
- `../../audit/test37_fraction_oracle.py` and `.json`: standalone Fraction checks with no preparer/kernel imports. Recorded PASS covers 28,000 indicator truth checks, 5,440 impossible-selector checks, 1,460 box corners, 200 path checks and 80,199 signed rounding checks. Finite checks supplement the algebraic argument and actual certificate; they are not universal verification of the implementation.

All eight deliberate attacks returned **INVALID**: wrong original-row scaling, wrong activity-bound scale, borrowing integrality in an LP claim, deleting a middle full-model obligation, corrupting the fixed-coordinate inverse, making the source separator infeasible, omitting a fiber cancellation, and falsely using complete-coordinate permutation strictness. A rejected certificate alone is not evidence that the two actual models are unrelated.

The first complete run prepared the proof in 0.200 seconds. The single development replay reported 6.680 ms execution and 8.792 ms total internal verifier time; attacks took 0.378 seconds. These are receipts, not an isolated performance comparison or a distributional benchmark.

## Reproduce

From the kernel repository:

```sh
python3 tools/prepare_test37.py --kernel target/validation-checkpoint-v8/release/rpx
python3 audit/test37_fraction_oracle.py
target/validation-checkpoint-v8/release/rpx verify cases/test37/source.mcm cases/test37/target.mcm cases/test37/proof.rpx cases/test37/request.json
```

The original corpus is read-only. The frozen executable hash is recorded in `preparation.json`; rebuilding a newer executable does not replace that historical measurement identity.
