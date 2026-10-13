# Actual test32: one-hot choice exclusion and zero extension

The unchanged actual source and final target are certified for an objective-preserving integer affine bijection, all 4,792 retained coordinate observations, and both complete inverse identities. A third claim proves objective-preserving inclusion of the target LP relaxation into the source LP relaxation. Forward LP equality or strictness is not asserted.

The source has 18,380 integer variables and 576 rows. The target has 4,792 variables and 382 rows; its 60 continuous time coordinates are proved integer from their actual defining equations and the remaining binary choices.

The proof derives 7,282 original fixed-zero coordinates from bounds and another 6,306 zeros with ordinary exhaustive binary `Cases`. Each impossible selected choice contradicts its actual one-hot equation, time definition, and time bound. Shared weighted nonnegative subset facts reduce the repeated certificate references; each fact is an ordinary `Lin` derivation from actual variable lower bounds. The reverse proof restores all 168 deleted capacity rows by componentwise dominance and all 26 deleted precedence rows by retained paths and proved nonnegative durations. Every variable bound, row, objective, projection, and inverse coordinate is checked by the kernel.

Observed verification: **VERIFIED**, 145,301 obligations, 6,306 branches, 17,552,874 work units; 11,492,509 RPX bytes. Preparation took 4.734 seconds; this single recorded verification took 633 ms execution and 696 ms including input loading and decoding. These are individual observations, not benchmark distributions.

Five deliberate corruptions were rejected: weakened binary split, omitted actual time bound, omitted duration contribution used by a path, omitted time-integrality premise, and omitted inverse obligation. `valid_unused_fact_mutation.json` separately records an initially proposed mutation that correctly remained accepted: it changed a sound duration fact that no obligation used. The final rejection attack targets a consumed duration fact instead. Large mutated files are deterministically reproducible and were removed after recording their hashes and exact outcomes.

Reproduce from the repository root:

```sh
python3 tools/prepare_test32.py --kernel target/validation-checkpoint-v7-rational/release/rpx
```

`preparation.json` binds the original corpus inputs, generator, complete RPA, RPX, canonical models, request, kernel binary, and observed executions by exact hashes. The Python preparer and original audit are untrusted inputs to certificate construction.
