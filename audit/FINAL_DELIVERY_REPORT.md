# Complete corpus delivery and acceptance

The final functional ledger contains **81/81 VERIFIED**, covering all **11
transformation families**. There are no remaining material-missing,
proof-incomplete or capability-gap cases in this supplied corpus. Acceptance is
against the actual complete models and original report contracts, including the
additional properties discovered during independent scope review. This is not
a claim that every possible MILP reformulation has a compact certificate.

## Final implementation and executed evidence

- Pure safe Rust core, trusted exact MPS/LP import and MCM encoding, versioned
  RPX decoder/verifier, and RPA assembler. Production core forbids unsafe code;
  no Python, solver or dynamic theorem callback participates in acceptance.
- Immutable source/spec/test checkpoint: `checkpoints/v10-complete-source`,
  manifest `checkpoints/v10-complete-source.json`.
- Fresh locked release build and **262 passing core tests**:
  `validation/v10-complete-cold-build.json`. Reproducible collector:
  `../tools/cold_checkpoint.py`.
- Final binary: `../target/validation-v10-complete/release/rpx`, SHA-256
  `96a6d3048d1deb6681733ab8b7356875f5e76bd1991c26337fe6820726b9c8f8`.
- Final corpus replay: **81 complete cases, 83 successful kernel invocations**,
  `validation/v10-complete/run.json`. Test46 deliberately uses three independent
  complete directions on the same actual model pair. Its delivery conjunction
  is not presented as one kernel call and permits no cross-file proof state.
- Original 78 submitted requests: regenerated RPX bytes and complete non-timing
  results are unchanged under the final binary, **78/78 PASS** in
  `validation/v10-complete-old-78-compatibility.json`.
- Final ledger reconstruction: `validation/acceptance-final-81.log` and
  `acceptance.json`. `contract_scope_gates.json` binds the independently reviewed
  corrected requests. A successful replay alone cannot close an open scope gate.

The final replay took 190.343 seconds summed across complete invocations during
concurrent acceptance work. This is a functional diagnostic, not an isolated
performance measurement. Performance has its own fixed matrices and receipts.
The raw replay's conservative `functional_delivery_complete:false` is intentional:
that collector checks enumerated requests only. The separately reconstructed
81-case ledger establishes complete original-contract coverage.

## Acceptance findings and completed repairs

The user's submitted 78 requests independently regenerated and verified. The
original-report audit found two omitted properties; both have now been added
without changing the actual source/target models or dropping previous claims.

| Case | Complete original property now checked | Evidence |
|---|---|---|
| 62 | Previous MI relation/bijection plus a full feasible source LP point whose caller-bound complete target image violates an actual target row/bound | `validation/completed-46-62-83-independent.json`, `IMAGE_EXCLUSION_REVIEW.md`, case comparison receipt |
| 83 | Previous complete minimum/recovery directions plus strict improvement whenever any of the 61 dominated nonnegative original coordinates is positive | `TEST83_STRICT_REVIEW.json`, `STRICT_IMPROVEMENT_REVIEW.md` |
| 46 | Full MI projection/objective equality in both directions and full LP target-to-source projection/objective inclusion | `DELIVERY_BUNDLE_REVIEW.md`, `TEST46_BUNDLE_BINDING_REVIEW.json`, independent five-piece replay above |
| 58 | Complete MI forward NonIncreasing and reverse Equal maps, with one jointly feasible demand-bounded subflow tuple | `TEST58_COMPLETE_REVIEW.md`, `SUBFLOW_PRODUCTION_REVIEW.md`, `validation/completed-58-independent.json` |
| 36 | Minimum preservation/recovery, exclusion of all 200 continuous terminals from every source optimum, and all-optimum projection onto all 37,616 retained coordinates | `TEST36_COMPLETE_REVIEW.md`, `validation/completed-36-projection-independent.json` |

For test36, strict improvement on P>0 alone did not bind the reported optimal
projection. A retained synthetic counterexample demonstrates that logical gap.
The final request additionally checks an Equal map preserving all retained
coordinates on the explicit original-coordinate halfspace P<=0, and the reverse
projection. Every attained source minimizer belongs to that halfspace by the
strict-improvement contract. Both halfspace and strict predicate bind exactly the
sum of all 200 original terminals. Continuous terminals remain real-valued; a
positive value 1/4850 is an independently tested control, not rounded to one.
The final test36 certificate checks 529,636 obligations and 448,596,660 work.
Its RPA is 267,140,625 bytes, below the unchanged 268,435,456-byte limit. Fifteen
documented negative mutations reject, including an unchanged complete RPX against
a weakened caller request. The old partial-contract artifacts remain archived.

The historical acceptance report is `DELIVERY_ACCEPTANCE.md`; its 76/81 count
records the initial scope correction. This final report and the live ledger
supersede that status, without rewriting the historical findings.

## Response to the design review

1. **The lift-builder trust criticism was correct.** Old-scope premise checks
   and model validation do not independently prove that the generated extension
   has a simultaneous witness. Builders remain trusted inference code. The
   misleading comments and trust explanation were corrected. Each lemma retains
   a separate mathematical argument, implementation correspondence, independent
   finite oracle and adversarial review. No second universal lemma checker or
   machine-checked implementation proof is claimed.
2. **Case-driven format growth was a real maintenance cost.** The current
   reference consolidates the inherited layouts, and the remaining needs share
   one V10 working draft: strict improvement, complete-image exclusion, jointly
   bounded subflows and a general affine conditional input domain. There is no
   V11 case plugin, case-ID whitelist or dynamic theorem loader. Existing valid
   bytes retain their meaning. Generic expression/mapping DAGs and dedicated
   batches remain possible future representation work, not prerequisites used
   to excuse missing actual cases. V9/V10 remain explicitly unfrozen protocols;
   the delivered implementation and checkpoint are fully specified and tested.
3. **Duplicated mechanics were extracted.** Shared bounded arithmetic/counting,
   naming, allocation and exact prefix copying live in `build_support.rs`; the
   lemma-specific construction stays in separate files. The extraction removed
   401 net source lines. Before/after suites, independent construction/state
   comparisons and actual-case byte/stat equality are preserved in
   `BUILDER_SUPPORT_REVIEW.md` and `builder_support_extraction.json`.

## Correctness and format evidence

The 262-test cold run extends the submitted 213-test suite with 49 tests for the
new capabilities and their integration. It retains exact arithmetic/reference
oracles, scope and branch attacks, complete model/tuple obligations, canonical
number checks, bounded decoding, resource failures and earlier byte vectors.
The new conditional-domain vectors are independently authored with Python
struct/Fraction, not emitted by the Rust encoder: 354 prefix truncations, 2,520
forbidden flag/reserved-byte values, 44 old/unsupported version changes and 16
persisted malformed files are covered. Existing valid V10 absent-field bytes
also match the pre-halfspace executable.

Subflow has a constructive real-valued path argument, 983 independent exact
construction fixtures, and 14 production tests. Its generated variables jointly
satisfy all demanded balances and bounds; local witnesses are not combined into
an unchecked global tuple. See `../docs/SUBFLOW_DRAFT.md` and the production review.
Delivery bookkeeping additionally has 24 adversarial fixtures, including missing
bundle directions, changed requests/hashes, nonzero exit with VERIFIED text, and
Python optimized mode. See `DELIVERY_BUNDLE_FIXTURES.json`.

All this is executed testing and review evidence. It does not establish an
unconditional formal correctness theorem about the Rust implementation or its
dependencies. Trusted importers, rational libraries, compiler/runtime and
builder lemmas remain in the documented TCB. Finite work/byte/depth limits can
still produce RESOURCE_LIMIT. Work counts are not CPU instruction counts, and
logical live facts are not peak process RSS. Owned decoding and some library
allocations also limit peak-memory guarantees.

## Reproduction

From the repository root, use a fresh output label rather than overwriting the
recorded checkpoint:

```sh
cargo test --manifest-path audit/checkpoints/v10-complete-source/Cargo.toml -p kernel-core --locked --target-dir target/validation-reproduce-final
cargo build --manifest-path audit/checkpoints/v10-complete-source/Cargo.toml -p kernel-core --release --locked --target-dir target/validation-reproduce-final
python3 tools/run_acceptance.py --label reproduce-final --skip-build --source-root audit/checkpoints/v10-complete-source
python3 tools/check_delivery.py --case test36 --case test46 --case test58 --case test62 --case test83 --kernel target/validation-reproduce-final/release/rpx --out audit/validation/reproduce-completed-cases.json
```

Each case directory retains actual model identities, full RPA/RPX/request files,
preparation scripts, negative recipes and receipts. Original corpus files remain
under their inventory-bound paths. Independent reviewers and canonicalizers
validate these inputs; file names and hashes are provenance, never proof axioms.

## Performance evidence

The final measurements are reported separately in
`../bench/V10_REGRESSION_REPORT.md` and
`../bench/NEXT_CAPABILITY_DRAFT_BASELINE.md`. Fixed matrices, complete raw
observations, byte identities, preparation/assembly costs, decoder/verification
timings and RSS are preserved. Newly supported tasks have an absolute baseline,
not a speed ratio against an executable that cannot prove the same statement.
Historical scope-sharing and exact-arithmetic optimization evidence remains in
the earlier benchmark reports. Raising the default work budget from 100M to 1e9
was the already-approved resource policy, not an optimization or semantic change.

The new-capability baseline contains **22 fixed workloads, 264 successful
verification/RSS processes and 63 separately timed synthetic author/assembly
preparations**. All task-owned builds, case preparation and acceptance work were
idle. The exact final cold binary was used throughout. For the complete actual
test58 request, median execution is 18.369 ms, full process 28.749 ms and peak RSS
31.891 MiB. The 1,024-node/four-group subflow workload takes median 56.732 ms to
execute and 69.141 MiB RSS, while complete Python preparation takes 9.154 seconds.
That preparation includes the simple O(nm) author construction; it is explicitly
not hidden in a constant-time theorem claim. Complete min/median/max values and
decoder, generator and assembler components remain in the linked report.

The unchanged old-workload comparison retains **31 paired workloads and 712
successful verification/RSS processes**, with identical artifacts and complete
non-timing results. The candidate's execution median rises in 19 workloads and
full-process median rises in 23. The largest absolute execution increase is
test65, 1,792.479 to 1,864.392 ms (+4.0%); test79 and test71 show about +8.3% and
+8.2%. The largest relative execution increase is rational-1000, 0.792 to
0.972 ms (+22.7%, or 0.180 ms). Peak RSS changes are small: the largest increase
is 0.03125 MiB on test65. The added capabilities therefore must not be described
as a general speedup or a regression-free update. The fixed sequential order
and uncontrolled OS activity limit causal attribution.

A single predeclared alternating-order follow-up retains another **72 timed
calls and eight excluded warmups** on four affected tasks. Its paired execution
median differences are rational-1000 +0.003 ms, test65 +82.552 ms (about +4.52%),
test71 -0.038 ms and test79 -0.005 ms. Thus the larger original differences for
the other three tasks did not persist in this round; the positive test65 cost
remains and is explicitly accepted as a measured limitation of this delivery.
Substantial spread and within-pair order effects prevent attributing a precise
causal percentage to the implementation. The candidate was not changed, the
original matrix was not replaced, and this follow-up makes no new RSS claim.
See `../bench/results/v10-order-sensitivity/ORDER_SENSITIVITY_REPORT.md` and its
complete raw evidence. No general speedup or regression-free performance promise
is part of this acceptance.
