# Initial fixed benchmark and sparse accumulation optimization

These measurements are an early V1 milestone, not the final performance acceptance.
The fixed workload file is `bench/workloads.json`; each row has nine independent
fresh-process observations. Filesystem caches are warm after preparation. No cache
flush is claimed. Worker processes were idle for the two compared runs. OS and other
user activity are uncontrolled; raw minimum/median/maximum values are retained.
Hardware: Apple M5; 17179869184. Compile: `cargo build -p kernel-core --release`, Rust/dependency
versions and exact source hashes are recorded in each raw JSON.

| Workload | Before execute ms | After execute ms | Before process ms | After process ms | Before RSS MiB | After RSS MiB | RPX bytes |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| identity-1 | 0.009 | 0.015 | 2.007 | 2.605 | 1.81 | 1.88 | 120 |
| identity-1000 | 1.563 | 1.762 | 4.622 | 5.606 | 4.20 | 4.22 | 67053 |
| identity-10000 | 15.683 | 16.667 | 29.890 | 31.163 | 23.62 | 23.50 | 670053 |
| dense-100 | 0.359 | 0.152 | 2.213 | 2.429 | 2.14 | 2.11 | 5961 |
| dense-1000 | 20.582 | 1.545 | 23.759 | 4.844 | 3.45 | 3.45 | 59061 |
| dense-5000 | 475.208 | 6.974 | 481.567 | 13.184 | 8.56 | 8.61 | 295061 |
| rational-10 | 0.026 | 0.027 | 2.090 | 2.187 | 1.88 | 1.94 | 651 |
| rational-1000 | 22.873 | 1.586 | 26.142 | 4.532 | 3.45 | 3.45 | 59061 |

Execution timings include full semantic model validation plus proof execution;
model/proof decoding and file reads have separate measured fields. Process latency
also includes executable startup and JSON result output. RSS is a separate fresh
process observation from macOS `/usr/bin/time -l`, not a sample median. The RPX input
and logical mathematical claims are unchanged by the optimization. Counts for
substitution visits, linear visits, obligations, live facts and work are also stored;
work budget accounting no longer counts repeated sorting that was removed.

The change replaces repeated expression concatenation/canonicalization with a single
exact sparse accumulator and one final sort. Every product and intermediate sum is
still checked; hash buckets never decide mathematical equality. Static-reference
result validation and DROP/depth resource consistency were strengthened concurrently.
The 5,000-term row improves from about475ms to7ms execution, while the 10,000-variable
identity execution regresses from15.68ms to16.67ms (about6%). This regression is retained
and disclosed; no blanket speedup claim is made. Small process timings have noticeable
startup/OS noise and one optimized1000-term sample is an outlier; all samples remain.

The same representation defect made real test33 and test68 exceed the100million-work
budget. Their original RESOURCE_LIMIT receipts remain beside their later successful
runs. A failure-to-success change is not reported as a speed ratio.

`baseline-v1`, `baseline-v1-isolated`, and `baseline-v1-confirmed` are exploratory runs
with unconfirmed/background worker overlap. Their condition notes disqualify them
from the comparison. Only `baseline-v1-quiescent` and `sparse-v1-quiescent` are compared.

Preparation costs (MPS canonicalization and RPA assembly), physical MPS/MCM/RPA/RPX
sizes, and every command are in raw JSON. Python generation time is not yet separately
measured by this microbenchmark; real-case preparers record their own elapsed time.
The full benchmark requirement remains incomplete: shared chains, massive history,
big-integer pressure, branching/theorem workloads, actual-case distributions, repeated
RSS and finer CPU attribution still need fixed measurements. No throughput target has
been declared met.

Reproduce current measurements with `python3 tools/benchmark.py --label NEW_LABEL`.
The script refuses to overwrite a prior result. Baseline verifier source and a source
snapshot comparison live under `bench/baseline-source`; consult its reconstruction
notes before claiming bit-for-bit baseline reproduction.

## Controlled reconstruction replay

The original full historical model source could not be recovered bit for bit. A
new controlled replay instead builds two frozen workspaces with identical model,
codec and dependency sources, differing only in sparse accumulation in verify.rs.
Both variants passed their22tests before measurement. The reconstruction manifest
records source/binary hashes; the historical records above remain unchanged.

All three workers confirmed idle computation and held builds/tests during the
sequential before/after runs. Same workload matrix, numerical semantics, physical
proof sizes and nine fresh-process observations per workload.

| Workload | Before execute ms | After execute ms | Before process ms | After process ms |
| --- | ---: | ---: | ---: | ---: |
| identity-1 | 0.017 | 0.014 | 3.100 | 2.844 |
| identity-1000 | 1.674 | 1.607 | 5.142 | 7.148 |
| identity-10000 | 15.190 | 15.673 | 29.172 | 31.206 |
| dense-100 | 0.359 | 0.137 | 2.484 | 2.107 |
| dense-1000 | 20.486 | 1.273 | 23.261 | 4.056 |
| dense-5000 | 477.811 | 6.340 | 484.731 | 11.777 |
| rational-10 | 0.025 | 0.023 | 1.964 | 1.912 |
| rational-1000 | 23.658 | 1.484 | 26.581 | 4.272 |

Dense5000 improves477.811ms→6.340ms execution in this reconstruction. Identity10000
regresses15.190ms→15.673ms (about3.2%). Identity1000 process latency worsens despite
slightly lower internal execution; short-process OS/startup noise remains visible.
This corroborates the long-row improvement, not a claim of universally faster
verification. Raw distributions/RSS/preparation live in `reconstructed-v1-quiescent-before`
and `reconstructed-v1-quiescent-after`. Reproduce both builds and the unchanged
matrix with `python3 tools/reproduce_sparse_ab.py --run --label NEW_LABEL` during
a comparable idle-worker window.
