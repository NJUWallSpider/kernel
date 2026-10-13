# test57: bounded binary-sum elimination

The complete actual source/final MPS pair has passed the Rust kernel. The source
has 114,240 binary variables and 29,904 rows; the final model has 97,368 binary
variables and 13,032 rows. Source and final files are unchanged and their hashes
are recorded in `preparation.json`.

The RPA1 proof checks four complete directions: both directions for the original
integer domains, and both directions for the continuous relaxations. All retained
coordinates and objective values are preserved, and both affine compositions are
checked on every input variable. The resulting feasible-point correspondences are
bijections; the LP claim includes every original auxiliary bound.

Every eliminated variable is a sum of one to five retained variables. Its lower
bound follows from the summands, and its upper bound follows from an actual
retained gate row, the gate variable's upper bound and the other summands' lower
bounds. Integer sums use the actual retained integrality premises. Every original
definition and all consumer occurrences are checked, including rows containing
multiple eliminated variables. The proof has 1,956,604 terminal obligations and
59,995,996 RPX bytes.

Three modified certificates are rejected: an omitted gate upper bound, a changed
sum reconstruction, and an omitted inverse obligation. Exact command outputs and
all artifact hashes are in `preparation.json`. The untrusted Python preparer uses
Fraction arithmetic and accumulates substitutions without repeated large copies;
preparation cost is reported separately from the kernel verification.

Reproduce from the workspace:

```
python3 tools/prepare_test57.py --kernel target/release/rpx
python3 tools/prepare_affine.py --acceptance
```
