# Independent V8 SignedLift review

Reviewer: model_layer, 2026-10-11. This is a read-only source and mathematical review of the working V8 implementation, not a formal proof or an independent claim that its test suite ran. No production files were changed during this review.

Result: no soundness or format defect found in the reviewed change. The existing complete-output checker verifies the downstream contract conditional on the new joint existence step. The existence lemma, its required premise formulas and the generated extended model are trusted implementation code; premise/output checking does not independently prove that lemma or validate its builder. This clarification was added during the later architecture review, recorded in `LIFT_TRUST_REVIEW.md`.

## Mathematical and scope checks

The five required old-scope facts are exactly `-Z <= 0`, `Z-1 <= 0`, `INT(Z)`, `F-CZ <= 0`, and `-F-CZ <= 0`, with canonical rational `C >= 0`. They imply `Z` is zero or one and `|F| <= CZ`. For `Z=0`, all four new coordinates can be zero. For `Z=1`, choose `(p,n,u,v)=(F,0,1,0)` when `F>=0` and `(0,-F,0,1)` otherwise. This proves every generated row and domain, including active zero flow, zero capacity and nonintegral real flow. Each item depends only on the same fixed parent point, so all items have one simultaneous extension. The rule asserts existence, not uniqueness or bijectivity.

`signed.rs` checks the exact five-reference count for every item and validates both affine expressions against the original parent dimension. Thus an earlier generated coordinate cannot enter a later item's premises. The generated rows are precisely `p-n-F=0`, `u+v-Z=0`, `p-Cu<=0`, `n-Cv<=0`; variables and rows are ordered by item and all original model fields remain unchanged prefixes. Nonzero affine constants retain their correct signs.

`Context::run` requires integer input mode, rejects the legacy affine-inverse contract, obtains the remaining shared work budget, and checks every returned premise using the parent `Context` before constructing the child `Context`. No generated row or integer declaration can prove a premise of its own extension. The child retains `compositions`, the actual output, the caller-bound claim, shared statistics and limits, live facts and assumptions. Each ordinary Return still checks the complete output vector, every actual bound/row/integer obligation, objective and observation obligations, and all V7 bijection compositions. The separate paired-domain injectivity proof is unaffected. LP refutation mode rejects SignedLift before executing its steps.

## Arithmetic and resources

Capacity and parent expressions are validated before use. `C*Z` uses the checked scaling path, including each product before cancellation; both capacity-premise differences check constants and equal-index coefficient differences. Negation or cloning of already canonical bounded scalars preserves those properties. Subtracting one in the upper-activation premise is checked separately. Generated row validation provides an additional structural check.

Checked counts bound expanded variables/rows, five premises per item, copied terms and combined generated/premise support before controlled expansion. Work is charged for input copying/validation, witness supports, generated structures and name collision probes; the parent charges all preparation work and subsequent fact checks to the same budget. Controlled buffers and strings use fallible reservation. `first+offset` cannot overflow after the global variable limit and checked expansion have passed. The final dimensional and generated-term checks agree with the formulas: per item, `|F|+|Z|+8` generated terms for nonzero capacity and `|F|+|Z|+6` for zero capacity. Standard bigint and internal library allocation limitations remain those of the existing kernel; this review does not claim recovery from OS process termination.

## Wire and test review

The new terminal is tag 6 and is accepted only at version 8 or later. Writer and reader agree on `Q capacity`, `Expr flow`, `Expr activation`, `array<Ref> checks`, followed by the child block. The 51-byte minimum witness preflight is consistent with the existing minimum scalar/expression encodings. Version discovery uses `max(8)` for SignedLift and `max(7)` for MenuLift, so later visitation of a MenuLift cannot downgrade a signed certificate. RPA recognizes header 8, retains the bounded JSON parser, uses exact scalar strings, and rejects unknown witness fields.

Read tests cover all five premises and missing counts, old-scope coordinate/row references, dead facts, affine constants, zero capacity and active zero flow, intermediate bit limits, shared work/depth budgets, complete output attacks, older-version downgrades, nested MenuLift, sibling isolation and V7 composition propagation. The independent Python-generated binary fixture and Fraction oracle are present in the test paths. I did not rerun these tests, inspect every generated oracle value, or claim their execution results independently; the root agent owns the run receipts.

## Reviewed source identity

SHA-256 values at review time (later edits require a delta review):

| File | SHA-256 |
|---|---|
| `crates/core/src/signed.rs` | `bfb33d813075cb0510a18a86d5d8ebf75f8dd1f90071457d0bf32f83fc1c30ea` |
| `crates/core/src/proof.rs` | `15a3965978d1e6a1344a6f136f9e75d9155c317da1f75ced0d86988908347fff` |
| `crates/core/src/verify.rs` | `e75628192202e82436e5a4becbb02d76bdadcd633b60220ac2f8d0b96b8ba770` |
| `crates/core/src/codec.rs` | `8e771cebab6ea0559354cdced0033d7fec98617b992fe457f418cad422603f09` |
| `crates/core/src/rpa.rs` | `c264ba8ae1fb8c552d489bb1a4d6e850a88638d91bcbbe3df3070a7e92139b20` |
| `crates/core/tests/signed_builder.rs` | `3259a4c6f6df76e3a1d96cc249433673089f5afb5ce7352e10e4ba41a1771476` |
| `crates/core/tests/signed_lift.rs` | `3f55ae38ac29555ca072e0aa1575af0b769113ed606e90e5fad7e0abc7eda77f` |
| `docs/FORMAT_V8.md` | `aa274814bbdfe669b052ed55b482495341f7b8e3dc4e6814be9c6985a511ab84` |
