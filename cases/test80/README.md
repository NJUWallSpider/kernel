# Actual test80: every original optimizer, with a complete inverse

The full requested contract is **VERIFIED** on the actual source and final target. This receipt uses the **working, unfrozen objective-level protocol (RPA/RPX 9)** from the internal pre-refactor snapshot `bench/builder-support-baseline`. It is an actual kernel acceptance, not a protocol release or a claim that the entire corpus is complete.

Source `/Users/bhz/Code/reform_test/runs/test80-nomf-B1/input/model.mps` has 14,387 integer coordinates, 10,765 rows and 64,073 constraint coefficients. SHA-256: `53f3a9f91f1304e855792eb54e528be9c7ef9dac702fc590efdca9186611ee22`.

Target `/Users/bhz/Code/reform_test/runs/test80-nomf-B1/output/reformulated.mps` has 2,801 integer coordinates and 175 rows. SHA-256: `e9ed1eebeab13231d6a5b84d0caf2ca8370ec9820a7963e656c2f54f87ea3905`.

Neither corpus file was changed. The canonical MCMs were independently decoded and compared field by field with the Fraction source parser in `optimal_face_structure.json`.

## Exact accepted contract

`request.json` binds three directional claims and a complete original-source point:

1. On the **unrestricted actual source**, a constant feasible target map is nonincreasing in objective and proves the global source lower bound −160.
2. On the actual source restricted explicitly to objective −160, the complete affine map F is target-feasible, objective-equal, and inverse to claim 2 (zero-based).
3. On the complete actual target, the affine reconstruction G is feasible in the complete original source, objective-equal, and inverse to claim 1. A separate mandatory equality proves its image lies in the opposing source objective level −160.
4. The complete original-source integer point attains −160; every original domain and row is checked.

The first and fourth checks prove global optimality and attainment. The two reciprocal full-coordinate affine inverse checks then prove a bijection between **all original integer optimizers** and **all actual target integer feasible points**. The original source was not replaced by an externally trimmed model. No suboptimal-point, attainable-objective-set or LP-equivalence claim is made. A separate exact source feasible point of objective −159 is retained in the structural audit to demonstrate this distinction.

The statistic `bijections=0` counts the separate V7 paired-domain bijection mechanism, which is deliberately unused here. This certificate's bijection is established by the two caller-bound reciprocal `inverse` fields, checking all 14,387 source coordinates and all 2,801 target coordinates, together with the opposing-domain membership equality.

## Proof construction and full model scope

The actual objective is `sum(P)−10 sum(B)`. Actual P lower bounds and B upper bounds prove

```
objective + 160 = sum(P) + 10 sum(1−B) >= 0.
```

In the restricted forward direction, a balanced sum tree and ordinary Lin/EqPair prove every one of the 3,315 P coordinates is zero and all 16 B coordinates equal one. No new fixing theorem is used. Actual linking lower rows, binary bounds, INT and Round derive `X[i,j]<=Y[t,j]`; assignment/passon rows and the fixings give one-hot Y vectors and exact equality of each required linked X/Y vector. The proof checks 528 complete vector pairs and all 221 Y sums. A spanning forest propagates equalities through the five actual components while preserving all 170 unlinked assignment vectors.

F keeps each representative component vector and every unlinked assignment vector; it sets the target's fixed objective coordinate to one. G reconstructs every original X/Y coordinate from those vectors, P=0 and B=1. Every actual source bound, integer declaration and all 10,765 source rows are checked in G. The forest never substitutes for those complete output obligations. The source objective reconstructs to −160 and every coordinate composition is checked.

## Retained evidence

- `proof.rpa`: complete 12,630,928-byte RPA; `proof.rpx`: complete 9,130,685-byte RPX.
- `request.json`: exact 494-byte caller contract; `preparation.json`: commands, hashes, timings, complete verifier outcome and nine rejection outcomes.
- `optimal_face_structure.json`: full indexed maps, all row families, every reverse-row identity, complete domain/objective checks, 23 complete actual point roundtrips and 1,788 finite AND truth checks.
- `baseline-working-v9/`: saved debug/release executables and identity records. The release executable SHA-256 is `dfadf56afe6c023bbf3a51eb5f4f1de1a4bb1bcf0c8cbe001c3ffcb35013eb5c`; its complete source manifest records the internal snapshot, which is not a protocol freeze.
- `../../audit/optimal_face80_oracle.json`: independent Fraction checks of 3,937 objective/fixing patterns, 20,500 local assignment patterns, 1,464 rounding values and 510 nonuniform rational zero-sum patterns. These finite tests supplement the complete kernel proof.
- `attempts/initial-preparer/`: the initial untrusted preparation failed before producing an RPA or invoking the kernel because its lookup did not automatically scale the fixed objective-coordinate equality. The retained script and result explain the explicit existing-Lin scaling correction. It was not a failed kernel proof or a mathematical counterexample.

The successful proof has 88,275 terminal obligations, 848,557 linear terms, 70,752 substitution terms, 79,429 peak live facts, zero branches and 4,881,992 total work units. One kernel-created objective-level row has 3,331 terms. All use default limits. The single development replay reported 125.920 ms execution and 170.877 ms total; preparation took 30.087 s. These are diagnostic timings, not an isolated comparative benchmark.

Nine deterministic attacks all return INVALID: a negative global-bound multiplier, a mismatched rounding integrality expression, a removed requested level, an omitted original inverse coordinate, an omitted opposing-level obligation, a changed unlinked reconstruction, a suboptimal attaining point, a missing middle original row, and an RPA version downgrade. Exact recipes, outcomes and mutated artifact hashes are retained; the large temporary mutant files are removed after rejection. Positive artifact bytes remain unchanged.

## Reproduce

From this repository, build the retained internal snapshot into a separate target directory, then prepare and verify the complete actual case:

```
cd bench/builder-support-baseline
CARGO_TARGET_DIR=/Users/bhz/Code/kernel/target/test80-baseline cargo build --locked --release -p kernel-core --bin rpx
cd ../..
python3 tools/audit_test80.py --kernel target/test80-baseline/release/rpx
python3 tools/prepare_test80.py --kernel target/test80-baseline/release/rpx
python3 tools/attack_test80.py --kernel target/test80-baseline/release/rpx
python3 audit/optimal_face80_oracle.py
```

The source/target MCM format remains V1. Future shared-helper or protocol changes need separate replay and receipts; this record does not silently substitute a new binary for the recorded one.
