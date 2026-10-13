# Actual test76: capacity-forced choices and affine substitution

The actual source and final target are certified for an integer affine bijection with equal objective values, all 1,682 retained coordinate observations, and both complete inverse identities. A third direction proves target LP inclusion into source LP. Forward LP equality and global strictness are not requested.

The certificate sums the actual resource-chain equalities through position 95, subtracts the five mandatory one-hot contributions, and uses the explicit resource upper bound. Each of 26 removed binary choices satisfies `x <= 4/5`; ordinary integer rounding and its actual lower bound prove `x=0`. The 50 eliminated continuous coordinates are recovered from their actual defining equations. Their bounds follow from the one-hot equations and nonnegative choices, and every replacement inequality is an exact checked row combination. All original and target bounds, rows, integer declarations, objective, projections, and inverse identities are covered.

Observed result: **VERIFIED**, 22,776 obligations, 282,306 work units, no branches, 709,068 RPX bytes. Preparation took 0.423 seconds; the recorded single verification took 19.6 ms execution and 24.8 ms complete. These are individual observations, not benchmark distributions.

All five deliberate corruptions returned **INVALID**: missing resource bound, continuous rounding premise, incorrect auxiliary recovery, missing one-hot bound premise, and missing inverse obligation.

Reproduce from the repository root:

```sh
python3 tools/prepare_test76.py --kernel target/validation-checkpoint-v7-rational/release/rpx
```

`preparation.json` binds the unchanged source/target corpus bytes, generator, complete RPA/RPX, canonical models, request, kernel binary, and execution receipts by exact hashes. The preparer and original audit are untrusted.
