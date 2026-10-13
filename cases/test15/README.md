# Actual test15 singleton substitution

The complete source/final-target pair is **VERIFIED**, and all four deliberate mutations are **INVALID**. The actual transformation removes 32 integer singleton columns, changes their defining equalities to packing inequalities, and adds the continuous fixed-one objective column. It maps 4,516 variables to 4,485 variables with 32 rows in both models.

All four integer/LP directions preserve retained coordinates and exact objective values, and both complete affine inverse compositions are checked. Each eliminated singleton is reconstructed as one minus its row's retained sum. The target packing row proves its lower bound; nonnegativity of retained variables proves its upper bound; exact integer linear combination proves integrality. Actual source equalities establish the forward projected rows and objective substitution. The fixed offset is exactly `315640009/62500` (5050.240144), and its fixed bound is explicitly used in reverse objective and inverse obligations.

The proof has 81,074 obligations, 2,996,538 work units and no branches. RPX size is 5,799,694 bytes, SHA-256 `44675f0a8371e11792aa0e5bf65f9b62a9588f82bc919c752bb2957c2c7dde33`. Preparation took 6.15 seconds; the single recorded kernel execution took 0.613 seconds (0.671 seconds including read/decode). These are case receipts, not controlled benchmark measurements.

Negative checks change the fixed offset mapping, remove a required nonnegativity premise, alter an eliminated singleton's recovery constant and omit a full inverse coordinate. All are rejected.

```sh
python3 tools/prepare_test15.py --kernel target/validation-checkpoint-v7-rational/release/rpx
```

The exact source, final artifact, preparer, kernel and generated files are bound by hashes in `preparation.json`, with full commands and verification/mutation outputs. The corpus files remain read-only. The source report's exploratory integer-hull triangle observation is separate from the committed transformation and is not asserted by this request.
