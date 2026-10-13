# Actual test39: full large balance-clique model

The unchanged actual model pair is certified for equality of mixed-integer feasible sets in all 242,736 original coordinates, pointwise objective equality, and both complete identity inverses. The certificate also proves target LP inclusion into source LP. The original audit supplies only a local fractional witness, so global strictness is not claimed.

Every one of the 322,248 original rows and 313,956 target rows is covered. The proof replaces 1,152 packing rows using actual signed balance equalities. In the 192 unbalanced cases it additionally uses the extra binary upper bound and ordinary exact integer rounding; the reverse direction uses the extra variable's lower bound. It reconstructs all 6,564 deleted equalities as the negative sum of eleven retained component equalities and restores all 1,728 duplicates from retained rows. Both reverse directions check the recovered balance equalities even when a packing witness names a deleted row. Every domain, objective term, projection, and inverse coordinate is checked.

Observed result: **VERIFIED**, 2,941,863 obligations, 29,341,771 work units, no branches, 53,838,719 RPX bytes. Preparation took 17.663 seconds. The recorded verification took 1.381 seconds execution and 2.037 seconds complete. These are single observations, not benchmark distributions.

Five corruptions returned **INVALID**: omitted extra binary upper bound, invalid rounding integrality premise, omitted component equality, omitted reverse nonnegativity premise, and omitted inverse obligation. Large mutated files were removed after exact hashes and outcomes were recorded; the generator retains the deterministic mutation recipes.

Reproduce from the repository root:

```sh
python3 tools/prepare_test39.py --kernel target/validation-checkpoint-v7-rational/release/rpx
```

`preparation.json` binds the original corpus source/target, untrusted generator, complete proof source, binary proof, canonical models, request, verifier binary, and execution receipts by exact hashes. No trusted model recognizer or clique theorem was introduced.
