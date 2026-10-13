# Independent integration review of frozen V3

Reviewed production source is snapshotted in `audit/checkpoints/v3-source`, with
SHA-256 manifest and archive. This review supplements executed tests; it is not a
formal verification claim. The reviewer did not implement the Plotkin/point modules.

- Plotkin binds every selected coordinate to actual integer domains within [0,1].
  Each supplied at-most-one fact is checked exactly, including nonnegative lower
  bounds for padding variables. All close pairs are checked, including duplicate
  labels. The bound follows by double counting pair distances; it is a single
  scoped LE fact, never an unchecked output map.
- The input objective lower bound is requested externally, validated, and appended
  to every Return after ordinary, projection and inverse obligations. Split
  branches preserve the same responsibility; checked contradiction endpoints
  discharge an empty input domain. Attainment uses a separate complete point.
- Feasibility witnesses bind dimension, all bounds, requested integrality, every
  row and the actual objective constant. Strictness is enabled only after a
  proved LP inclusion with a complete coordinate permutation. The separating
  witness satisfies the full inclusion output and actually violates its input
  after reconstruction; an arbitrary point alone cannot certify containment.
- Request equality includes all supplementary point claims. Shared work budget
  cannot be reset between map proofs and point checks. Source/target models
  remain authoritative. Unknown fields, reserved tags and truncated records
  reject in the actual binary path, including structurally unreachable payloads.
- V1/V2 layouts remain distinct and unchanged. V3 carries new options and points
  only in its versioned layout; required-version discovery visits nested Cases.
- During review a temporary constant-product bit-limit inconsistency was fixed
  and given a regression. Arithmetic had remained exact; this was a resource
  policy gap, not a demonstrated incorrect mathematical acceptance.

Known restrictions remain: strictness supports complete coordinate permutations,
not arbitrary auxiliary projections; full proof decoding and branch-state clones
remain in memory; not every dependency allocation is fallible. The requested
complete corpus delivery remains unfinished, and existing tests cannot establish
unconditional soundness of the entire implementation.

Fresh build/test/replay evidence is recorded separately in
`audit/validation/checkpoint-v3/run.json` when that run completes. It must be read
for the actual result; this review does not assert an unexecuted run succeeded.
