# Actual test42 activation aggregation and strict LP strengthening

The complete actual transformation is **VERIFIED**, with all five deliberate mutations **INVALID**. All 167,056 original binary coordinates remain; rows decrease from 169,576 to 3,076.

The request proves same-coordinate integer feasible-set equality, exact objective equality, both complete affine inverse identities, target-LP inclusion, and strict continuous-relaxation containment. Strictness uses a complete 167,056-coordinate exact rational point checked against every actual source constraint and bound, then against the actual target.

The fixed prefix follows from the exact capacity/equality combination and the actual activation chain. A binary split on the 189th activation refutes zero using the positive constant 1/4; preceding fixed activations follow by chain sums and bounds. For each of 1,101 strengthened groups, ordinary binary Cases derive the aggregate from original member links or the original group bound. Reverse proofs restore all 166,500 individual links. Shared divide-and-conquer subset facts avoid repeating every other group member for every link; each tree edge is an ordinary checked linear combination.

The strictness point follows the actual audit recipe: fixed activations are one, others are 9/10, the selected group is uniform 1/100, and the remaining assignment coordinates are completed exactly within their actual equalities. No unchecked local witness or feasibility assertion is used.

The proof has 1,102 branches, 2,513,959 obligations, 7,288,800 linear terms and 41,931,109 work units. RPX size is 101,943,635 bytes, SHA-256 `72d637d0aa3a3fcfd789314bcd139eb85911556711790c5b1dc45790460ea9f3`. Preparation took 46.41 seconds; the recorded single execution took 2.081 seconds (2.551 seconds including reads/decoding). These are case receipts, not controlled benchmarks.

Mutations remove prefix-split integrality, omit an aggregate link, omit a reverse subset premise, corrupt the complete strictness point and omit a full inverse coordinate. All are INVALID. Large attack artifacts are removed after checking; recipes, hashes and results remain in the receipt and are reproducible.

```sh
python3 tools/prepare_test42.py --kernel target/validation-checkpoint-v7-rational/release/rpx
```

`preparation.json` records exact source/final-artifact/preparer/kernel/generated-file hashes and full commands/results. Corpus files remain read-only. No integer feasible point or attained optimum is claimed.
