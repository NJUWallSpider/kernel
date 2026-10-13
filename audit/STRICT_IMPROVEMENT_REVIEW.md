# Independent strict-improvement review — working V10

**No soundness finding identified** in the reviewed strict-improvement contract, verifier path, or RPA/RPX encoding. This is a review of the root-authored working implementation, not a protocol freeze or formal verification. Exact file identities and executable test results are in [STRICT_IMPROVEMENT_REVIEW.json](/Users/bhz/Code/kernel/audit/STRICT_IMPROVEMENT_REVIEW.json).

## Contract and mathematical argument

The caller specifies an actual model side, its integer/LP mode, and an affine predicate `p`. Acceptance establishes: for every point x feasible in that complete actual domain with p(x)>0, some point y is feasible in the same domain and has f(y)<f(x). Thus no attained global minimum can lie in that strict domain. No attainment, boundedness, nonemptiness, numerical optimum, or equality of all feasible sets is assumed.

The implementation preserves the strict information outside the ordinary fact system. Its only initial linear assumption is −p≤0. That weak fact holds at every strictly positive point, so all ordinary Lin/Round/Cases reasoning remains sound. A `PositiveRefutation` terminal must prove exactly p≤0 under the current assumptions, which excludes the branch from the root's p>0 domain. It does not create a reusable arbitrary contradiction fact or silently turn a weak zero boundary into a constant-positive contradiction.

An `ImproveReturn` terminal checks a complete tuple against every original variable bound, required integrality declaration and actual row. Its final objective obligation is either f(y)−f(x)+δ≤0 or f(y)−f(x)+εp(x)≤0, with the scalar strictly positive and exactly checked. Both imply strict improvement on the requested domain. The predicate form correctly allows arbitrarily small positive continuous savings; it does not impose an unjustified uniform gap. Complete output feasibility and the same actual objective prevent lower-cost tuples outside the model from being accepted.

## Implementation boundaries inspected

- `verify_request` compares the full ordered improvement claims with the caller's request before execution. Target/source selection, integer mode, affine coefficients and constants cannot be weakened by the certificate.
- The predicate is validated against the original model dimension before any extension. Each witness receives fresh local facts and its own initial assumption. Work is charged to the same request statistics/budget after map, bijection and point checks.
- Branches retain the immutable root predicate. `PositiveRefutation` compares the entire expression, not merely its sign or some split expression. A branch fact x≤0 cannot close a requested x+y>0 domain.
- Ordinary Return is rejected inside improvement context. ImproveReturn and PositiveRefutation are rejected in ordinary mappings and LP fiber-refutation contexts. Ordinary Absurd remains allowed only with its existing exact contradiction check.
- Every existing extension keeps the original model prefix and actual output model. The improvement context is propagated through Flow, Interval, Menu, Signed and newly added Subflow branches. This review checked that propagation; it does not re-prove those builders' joint-existence lemmas.
- The new scalar is validated before use, must be positive, and the derived predicate margin is checked through existing exact expression arithmetic. Objective offsets are retained and cancel as part of the actual model comparison.
- RPA version discovery sees improvements and both new terminal forms, including nested blocks. RPX gates them at10. Encoding retains exact predicates, flags, positive-scalar variant and complete blocks; reserved flag bits, unknown margin tags, old-version downgrades and truncation reject. Legacy requests default to an empty improvement vector and legacy certificates keep their prior byte layout.

The implementation theorem is existential when a valid lift is used; it does not promise a unique output or an affine map over the original coordinates alone. That is appropriate for the stated exclusion contract.

## Independent checks

The new [independent review tests](/Users/bhz/Code/kernel/crates/core/tests/improvement_independent_review.rs) do not modify production code. They add:

1. **1,000 full verifier calls** over two-coordinate binary/LP boxes, varied affine strict predicates and constant output tuples. Expected certificate validity is computed by exact integer box arithmetic. For every accepted certificate, an independent scaled-integer oracle exhausts the full binary domain or checks25 exact continuous grid points, including strict boundaries, and confirms the claimed objective decrease whenever the predicate is positive.
2. Different source and target objective functions, checking that a target-selected improvement uses its actual objective and fails when the selected model is swapped.
3. A root predicate x+y with a split on x, rejecting a false boundary refutation even though x≤0 is proved on that branch and x=0,y=1 is a feasible counterexample.

All three pass. The eight root-authored regression tests also pass, covering arbitrarily small rational margins, objective constants, integer and real strict boundaries, empty/unbounded domains, contract mutations, missing complete output obligations, old-scope predicates through an interval lift, shared resource limits, and version/format attacks. [The preserved execution log](/Users/bhz/Code/kernel/audit/STRICT_IMPROVEMENT_REVIEW_TESTS.log) contains the actual run results.

## Actual test83 application

The independent [review program](/Users/bhz/Code/kernel/audit/review_test83_strict.py) reads the complete original MPS using its own stdlib Fraction reader; it imports no preparer or model-parser helper. Its [machine result](/Users/bhz/Code/kernel/audit/TEST83_STRICT_REVIEW.json) is PASS. It checks the actual original source/target against the immutable inventory, checks current proof/request/receipt identities, and confirms the two previously certified directional claims and proof blocks are structurally unchanged.

The new strict predicate is exactly the sum of the61 removed original coordinates. The full tuple has65,832 coordinates. Each removed variable is zeroed and added to its two original retained replacements; all other coordinates retain their original value plus any such contributions. All61 replacement support pairs are disjoint with union equal to the removed column's actual support. For every sum-valued reconstructed coordinate, all its source terms share an actual unit-RHS partition equality. Nonnegativity and that equality imply its upper bound1, and its integer unit coefficients preserve integrality. Independent sparse substitution confirms **all100 original equalities remain exactly unchanged**.

Independent objective substitution yields precisely minus the61 recorded positive savings, on the61 original removed coordinates, and no other coefficients or constant. The minimum saving is exactly **161497/1000000**. The requested `Predicate` margin is that minimum times the sum predicate; every remaining saving-minus-minimum coefficient is nonnegative. Therefore the bound is sound for simultaneous replacements, not just isolated columns. Every original coordinate is nonnegative, so absence of positive sum at an attained optimum forces every one of the61 coordinates to zero.

The saved full receipt is VERIFIED with one improvement,592,612 total obligations and37,741,826 work units. All eight new recorded attacks are INVALID, including zero margin, a lost replacement, a missing partition premise, incorrect saving, incomplete tuple, a false positive refutation, weakened caller predicate and omitted requested improvement. This reviewer checked those recorded results and independently re-derived the tuple mathematics; it did not re-run the eight actual-case mutations.

## Independently encoded combined V10 fixture

[generate_contract_v10_vectors.py](/Users/bhz/Code/kernel/tests/vectors/generate_contract_v10_vectors.py) writes raw binary bytes using only Python `struct`, `Fraction` and standard file/hash utilities. It does not call a Rust encoder or any preparer. The saved source/target MCM, RPA, RPX, request and mutation fixtures are bound by [contract-v10-manifest.json](/Users/bhz/Code/kernel/tests/vectors/contract-v10-manifest.json).

The386-byte RPX simultaneously contains a complete image-exclusion point and two strict-improvement witnesses. The latter exercise both Predicate and Constant margins, an integer split, and a PositiveRefutation boundary leaf. Rust decoding, exact verification and byte-identical re-encoding all pass; the independently written RPA decodes to the same certificate and both independently written MCMs re-encode identically.

The [fixture tests](/Users/bhz/Code/kernel/crates/core/tests/contract_v10_vectors.rs) reject every one of386 truncations after updating the declared byte length, all11 tested old/unsupported versions for both RPA and RPX, and **5,601 exhaustive forbidden flag/reserved-byte mutations**. Twenty representative invalid binary files are permanently saved and compared with their raw-byte recipes. [The execution receipt](/Users/bhz/Code/kernel/audit/CONTRACT_V10_VECTOR_REVIEW.json) and log preserve the checks. Independence here means an independent wire-format implementation; this reviewer is also the author of the new ImageExclusion point helper, so this is not presented as an independent-author audit of that helper.

One integration detail is material for real-case preparation: the new weak root assumption occupies index0. Reusing a previously certified branch proof requires shifting its old Assumption references by1. The root author was notified; this is a preparer obligation, not a verifier defect.

No change to `proof.rs`, `codec.rs`, `rpa.rs` or `verify.rs` was made by this reviewer. This verdict is limited to the recorded working source identities; a later semantic change requires review of its delta.
