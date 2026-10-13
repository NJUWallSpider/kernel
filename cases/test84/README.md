# test84: generic exact parity and rounding proof

The actual source has 100 binary variables, 100 nonnegative integer auxiliaries and 100 equalities. The actual committed target has one continuous coordinate fixed to 37. The certificate proves a bijection of their integer-feasible sets, objective equality and both inverse identities. It makes no LP-equivalence claim.

For each binary coordinate, the audit identifies original equality rows whose sum has an odd coefficient on that coordinate and even coefficients elsewhere. The preparation tool computes the complete sum from the actual source. A generic `Lin Int` step combines half the equality sum with integer multiples of original integer coordinates to prove that `(x-v)/2` is integer, where `v` is the forced parity. A binary bound, exact rounding and `EqPair` then prove `x=v`. Each auxiliary is fixed by its original equality and the established binary values.

No parity theorem or GF(2) rank report is trusted by the kernel. The forward map is the constant 37; the reverse map supplies all 200 proved values. Complete source and target rows, bounds, integer conditions, objectives and inverse equations are checked. The source assignment is therefore proved unique rather than merely exhibited.

```sh
python3 tools/prepare_test84.py --kernel target/release/rpx
python3 tools/prepare_affine.py --acceptance
```

`preparation.json` records actual canonicalization, assembly and verification. The first execution used a debug binary. Both a damaged modular row multiplier and a damaged reconstruction coordinate must return `INVALID`; their full RPA/RPX files and results are retained.
