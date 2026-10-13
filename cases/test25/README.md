# Actual test25 constant-threshold and gate elimination

The complete transformation is **VERIFIED**, with all four deliberate mutations **INVALID**. The source has 11,659 variables and 18,442 rows; the final target has 11,064 variables and 16,193 rows.

The request proves the integer constant-extension affine bijection, all retained-coordinate observations, exact objective equality and both complete inverse compositions. It also proves objective-preserving target-LP inclusion. Forward LP equivalence is not claimed.

Nineteen constants follow from actual fixed domains. For each of 487 binary threshold constants, a local binary split retains the allowed value and refutes the other value using an actual original row and domain bounds. No finite truth-table or enumeration result is trusted. Eighty-nine gate-output constants then follow from actual gate rows, previously checked constants and ordinary bounds. Reverse reconstruction checks all 2,249 removed rows using the actual target box, plus every retained original row and every original variable domain.

The proof has 487 branches, 200,434 obligations and 1,308,401 charged work units. RPX size is 3,149,846 bytes, SHA-256 `c112e7cc5ab1dd3ab785e6fab5c529bd6581a6cae225cc81ba57293ac6186c39`. Preparation took 2.55 seconds; the recorded single verification executed in 65.8 ms (98.7 ms including read/decode). These are case receipts, not controlled benchmarks.

Mutations remove split integrality, omit a domain bound in an impossible branch, corrupt a fixed-coordinate recovery and omit a full inverse coordinate. All are rejected.

```sh
python3 tools/prepare_test25.py --kernel target/validation-checkpoint-v7-rational/release/rpx
```

`preparation.json` records all actual source/target/preparer/kernel/artifact hashes and complete commands/results. The corpus files remain read-only.
