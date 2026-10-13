# Shared proof scopes: fixed A/B measurements

Actual test18 exhausted the work budget because every local Cases copied all inherited exact facts. The replacement borrows immutable ancestors and stores only local definitions and deletion masks. Mathematical rules, complete return obligations, RPA/RPX bytes and the default work ceiling are unchanged. Ancestor lookup probes remain charged.

The matrix in `scope_workloads.json` was fixed before implementation: establish n active facts, then execute n Cases with an inherited witness in both branches, drop each exported result, and check a complete binary identity map. This isolates the observed quadratic copying cost; it is not a universal kernel speed claim.

## Controlled results

Both variants use frozen V5 sources. Only production `verify.rs` differs; an unreferenced test-only audit module is additionally present in the candidate directory. Every one of 36 verifier processes (18 timing, 18 RSS) returned VERIFIED. All MCM, RPA, RPX and request hashes and all mathematical counters match. The work counter changes because actual copies are removed and lookup probes are counted.

| Active facts / Cases | RPX bytes | Execute median ms before → after | Process median ms before → after | Median RSS MiB before → after | Work before → after |
|---|---:|---:|---:|---:|---:|
| parent-256-branches-256 | 47984 | 3.439 → 0.425 | 5.984 → 2.424 | 2.953 → 2.828 | 267535 → 8720 |
| parent-1024-branches-1024 | 191600 | 51.413 → 1.605 | 55.439 → 4.249 | 5.109 → 4.797 | 4215823 → 34832 |
| parent-4096-branches-4096 | 766064 | 827.142 → 6.517 | 832.907 → 11.583 | 13.719 → 12.578 | 67194895 → 139280 |

For n=4096, execute samples range 817.548–859.372 ms before and 6.303–6.746 ms after. The approximately 127× execution ratio applies only to this copying-heavy workload. RSS falls about 8.3%; complete proof decoding remains resident. Small-scope and nonbranching regressions require the broader fixed matrix and are not assessed by this selected family.

## Reproduction and scope of evidence

```sh
python3 tools/benchmark_scopes.py --kernel target/validation-checkpoint-v5/release/rpx --source-root audit/checkpoints/v5-source --label scopes-v5-quiescent-before
python3 tools/benchmark_scopes.py --kernel bench/shared-scope-prototype/target/release/rpx --source-root bench/shared-scope-prototype --label scopes-v5-quiescent-after
```

Existing labels refuse overwrite; choose fresh labels when reproducing. Raw commands, all sample distributions, model/proof decode times, preparation generation/canonicalization/assembly costs, source/binary/lock hashes and compiler/platform are retained in the two raw JSON files. Timing and RSS are separate samples. The available machine was macOS arm64, Rust 1.96.0 release. All three workers paused computation for the sequential A/B window. Files were warm after preparation; each run was a fresh process. OS background activity and scheduler noise were not controlled.

Preparation emits exactly the same physical certificates. The fixed mathematical task contains n scalar linear facts and n exhaustive integer branches; it does not contain n² logical obligations. The old n² cost comes from copying live state. No work is moved into an untrusted preparation acceptance path.

The independent state audit uses copied BTreeMap reference states and checks 127,072 operations plus depth-64 regressions; see `audit/SHARED_SCOPE_REVIEW.md`. Existing V5 130 tests also pass. The private container relies on the Context duplicate and live-limit checks. Logical peak_live_facts differs from physically retained ancestor/mask storage; lookup depth is bounded and metered.

The original unmetered-probe prototype and overlapping diagnostic runs are preserved but excluded from these conclusions. Production V6 integration, unchanged actual test18 replay, and broader performance regression checks are recorded separately when completed.

## Broader fixed regression matrix

The unchanged `extended_workloads.json` matrix was then replayed on the same frozen V5 baseline and its scope-only candidate. All 23 workloads × (9 timing + 3 RSS samples) × 2 variants = 552 processes VERIFIED. Every artifact hash and non-work mathematical counter agrees. The three workers again paused computation for both sequential runs. Hardware and source/lock/compiler identities are in `scopes-extended-v5-quiescent-before/raw.json` and `scopes-extended-v5-quiescent-after/raw.json`; actual preparation receipts are copied into their `receipts/` directories.

| Workload | Execute median ms before → after | Process median ms before → after | RSS median MiB before → after |
|---|---:|---:|---:|
| history-64 | 0.052 → 0.053 | 1.992 → 1.883 | 2.172 → 2.156 |
| history-4096 | 2.498 → 2.529 | 5.784 → 5.427 | 5.359 → 5.344 |
| history-65536 | 39.825 → 41.092 | 56.908 → 58.489 | 53.281 → 53.266 |
| branch-1 | 0.009 → 0.009 | 1.938 → 2.148 | 2.062 → 2.016 |
| branch-64 | 0.078 → 0.072 | 2.019 → 2.206 | 2.234 → 2.203 |
| branch-1024 | 1.022 → 0.981 | 3.469 → 3.675 | 3.453 → 3.422 |
| chain-16 | 0.246 → 0.245 | 2.255 → 2.269 | 2.344 → 2.328 |
| chain-64 | 3.040 → 3.052 | 5.477 → 5.571 | 3.391 → 3.453 |
| chain-256 | 46.532 → 46.363 | 56.286 → 56.078 | 15.766 → 15.766 |
| local-1 | 0.009 → 0.009 | 1.967 → 1.908 | 2.062 → 2.031 |
| local-1000 | 2.606 → 2.616 | 6.054 → 6.059 | 5.688 → 5.688 |
| local-10000 | 26.773 → 26.818 | 44.259 → 44.200 | 35.484 → 35.516 |
| bigint-64 | 0.547 → 0.537 | 2.768 → 2.762 | 2.656 → 2.656 |
| bigint-512 | 0.542 → 0.547 | 2.762 → 2.779 | 2.750 → 2.750 |
| bigint-4096 | 0.646 → 0.646 | 2.995 → 3.057 | 3.531 → 3.547 |
| real-33 | 1166.426 → 1163.464 | 1383.389 → 1376.459 | 362.250 → 362.312 |
| real-40 | 6.889 → 6.790 | 10.311 → 10.149 | 3.969 → 4.000 |
| real-65 | 3690.334 → 3793.140 | 4216.889 → 4357.740 | 866.578 → 866.562 |
| real-68 | 688.199 → 712.410 | 753.693 → 780.808 | 90.406 → 90.438 |
| real-71 | 129.925 → 133.848 | 143.716 → 147.734 | 16.375 → 16.328 |
| real-79 | 266.539 → 271.474 | 304.647 → 310.794 | 54.938 → 54.938 |
| real-84 | 14.620 → 13.564 | 19.225 → 17.732 | 5.016 → 5.047 |
| real-88 | 182.553 → 120.189 | 211.046 → 148.478 | 51.250 → 50.641 |

The actual branching test88 improves from182.553 to120.189ms execute (34.2%),
and test84 from14.620 to13.564ms (7.2%). Several nonbranching workloads regress:
history65536 increases39.825→41.092ms (3.2%), real65 3690.334→3793.140ms (2.8%),
real68 688.199→712.410ms (3.5%), and real71 129.925→133.848ms (3.0%). These results
include metered hash probes and normal system variation; they are disclosed rather
than explained away as noise. The tiny branch-1 process median increases1.938→2.148ms
while its execution median remains0.009ms. No broad speed improvement is claimed.
The implementation is retained because it removes unnecessary quadratic copies,
materially improves actual branch-heavy certificates, and enables the unchanged
test18 certificate under the same work ceiling. Reported work units count chosen
operations and are not CPU instructions or formal bit-complexity bounds.

Production integration into V6 is independently reviewed in
`audit/scope_v6_merge.json`. A fresh frozen build passes154tests and all12complete
actual RPX cases (`audit/validation/checkpoint-v6-shared-scopes/run.json`). The test18
replay is the same complete RPX/MCM/request bytes as its original resource failure;
that failure is not a valid successful-runtime denominator or speed ratio.
