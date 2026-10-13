# Actual test17 positive redundancies and binary order chain

The full actual transformation is **VERIFIED**, and all four deliberate mutations are **INVALID**. Both models retain all 57,756 binary variables. Rows decrease from 3,757 to 1,765.

The request proves same-coordinate integer feasible-set equality, exact objective equality and both full affine inverse identities. It also proves target-LP inclusion into the source LP. Global strictness is not claimed; the report's local order-subsystem point is not promoted to a full-model witness.

Forty-four local binary splits establish the adjacent unweighted order chain from actual weighted order rows and bounds. Every one of 990 original order inequalities is restored by an explicit target chain sum plus a nonnegative-variable bound. The 1,046 removed positive rows follow from their actual retained activation or packing witness and explicit domain-bound combinations. Every model row, variable domain, coordinate observation, objective and requested inverse identity is checked.

The proof has 44 branches, 760,110 obligations and 9,432,985 work units. RPX size is 15,005,031 bytes, SHA-256 `f215da5cc3b46e20ef343614bfd2c0d314ee596f2f3f92ad8cae6636d43d67f6`. Preparation took 13.96 seconds; the recorded single execution took 963 ms (1.184 seconds including read/decode). These are case receipts, not controlled benchmarks.

Mutations remove split integrality, drop a weighted-order lower bound, omit a positive-row domain premise and omit a full inverse coordinate. All are rejected.

```sh
python3 tools/prepare_test17.py --kernel target/validation-checkpoint-v7-rational/release/rpx
```

`preparation.json` binds actual source/final-target/preparer/kernel/generated artifacts by hash and records full commands/results. Corpus files remain read-only.
