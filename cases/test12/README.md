# Actual test12 containment and equality reduction

The complete transformation is **VERIFIED**, with all four deliberate proof mutations **INVALID**. The source has 7,195 binary variables and 426 equalities; the actual final target has 6,200 variables and 310 equalities.

All four integer/LP directions prove retained-coordinate preservation, exact objective equality and both full affine inverse identities. Fifty-four distinct actual equal-RHS row differences establish nonnegative zero sums across the two fixing rounds. Each of the 995 removed variables is individually proved zero with its actual lower bound. Reverse reconstruction checks every original equality, including 83 duplicate rows and 33 exact signed dependencies on final retained rows. All domain, objective and inverse obligations are explicit.

The certificate has 120,041 obligations, 2,392,585 charged work units and no branches. Its RPX is 4,675,338 bytes, SHA-256 `b01ff1a50530e1de356065c6daa83c2284c5204ae63c0a8798b9b4dd8b51d594`. Preparation took 3.00 seconds; the recorded single verification executed in 99.2 ms (129.3 ms including reads/decoding). These are case receipts, not controlled benchmarks.

Mutations remove a containment-row premise, reconstruct a zero variable as one, omit a signed equality term and omit a requested inverse coordinate. Every mutation is rejected.

```sh
python3 tools/prepare_test12.py --kernel target/validation-checkpoint-v7-rational/release/rpx
```

`preparation.json` records all actual input/output/preparer/kernel/artifact hashes and complete commands/results. Corpus files remain read-only. The source report's separate rank observation is not used as a premise or asserted as an additional property of this transformation certificate.
