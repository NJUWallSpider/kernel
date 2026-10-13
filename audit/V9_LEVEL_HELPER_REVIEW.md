# Independent objective-level helper review

Root read-only review,2026-10-11, before V9 verifier integration. No finding in the
reviewed model-domain helper. This does not claim that V9 is implemented or that
its integration/actual80 proof passed. Test execution is recorded separately.

The proposed exact-level contract has ordinary set-intersection semantics. The
helper preserves every original variable, bound, row, objective and name prefix,
then adds exactly the actual full objective equal to the caller level. Constants
and negative objective coefficients are preserved. An empty or infeasible level
remains empty; construction makes no optimum or attainment assertion.

Checked expansion and combined term counts precede allocation. Capacity/work
checks include old model validation/copy and new row support; collisions consume
additional work. Exact scalar canonicalization and the normalized objective
constant-minus-level are magnitude checked before copying. Controlled buffers use
fallible reservation. Existing general bigint/library allocation caveats remain.

The design requires an extra actual-output objective equality whenever the opposing
affine inverse has a restricted domain. Composition alone would be unsound for
such a pair; this essential closure still needs implementation review. A global
lower bound must use an unrestricted claim, with a complete point independently
establishing attainment. Initially filtered V7 pairs and both strictness contracts
must reject because their original domain semantics have not been extended.

Read-only review identities:

- crates/core/src/level.rs: 975d49fc938f9286b0f7115f64ec47f47682e04e922c090f6244de2c6574f433
- crates/core/tests/level_builder.rs: 60aabb97720ac09086ac14fb0a3a2251c49925b15b87e8d288b0f6b105bdc691
- docs/OBJECTIVE_LEVEL_DESIGN.md: ed4e03ad0c989ae34a348a20b17ac8e3e6211fb1c2142b2d866098e7302f840d
