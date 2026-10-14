# Compiler API plumbing measurements

These are fresh API identity-bijection measurements on 2026-10-14, with Python 3.9.6 and a pinned Kernel binary. They use no solver, historical proof, preparer, reformulated target, or Agent transcript. **They measure plumbing scalability, not reformulation quality or real-Agent acceptance.** Each workload has one fresh Python worker observation; concurrent Agent runs and warm filesystem caches prevent interpreting these as controlled latency distributions.

| Workload | Variables / rows | Total obligations, two MI claims | Load s | Plans s, forward + reverse | Complete s, forward + reverse | Compile s | Verify s | Python peak RSS |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| synthetic-1000 | 1,000 / 1,000 | 12,002 | 1.481 | 0.177 | 0.160 | 0.088 | 0.008 | 55.3 MiB |
| pristine test9 | 2,298 / 1,026 | 16,522 | 0.062 | 0.280 | 0.209 | 0.159 | 0.022 | 68.3 MiB |
| pristine test16 | 228,350 / 126,512 | 1,852,166 | 8.056 | 46.424 | 36.229 | 31.005 | 1.964 | 3.58 GiB |

All three complete Requests verified. The two claims have complete name-derived identity maps, exact objective preservation, retained-coordinate observations, and both affine inverse compositions. No nontrivial derivation steps are required. The sum of measured phases, including claim construction, cache checks, and artifact audit, is 1.925 s / 0.753 s / 126.451 s respectively. These sums omit worker startup and record-writing overhead.

Raw records retain every phase, native report, source/package/script/binary hash, artifact bytes/hashes, serialization count, and process high-water memory statistic:

- [synthetic-1000](../audit/compiler-performance/C1-plumbing-small/synthetic-1000/record.json)
- [test9](../audit/compiler-performance/C1-plumbing-small/test9/record.json)
- [test16](../audit/compiler-performance/C1-plumbing-test16/test16/record.json)

The test16 worker reached Python peak RSS 3,845,390,336 bytes; its largest native child reached 1,233,813,504 bytes. These are individual process high-water marks, not their sum or a sampled process-tree peak. The worker stayed below its 6 GiB Python guard. The source remained pristine and the package/binary hashes were unchanged during each successful observation. Large local certificate/request JSON and MCM/RPX artifacts are bound by the compact records and delivery manifests rather than committed to Git.

## Cache checks and native timing context

Repeated plans return the same goal-list object and perform zero additional map lowering, MCM serialization, or native calls. Cached test16 plans took 0.071 / 0.073 s. Mutation-safe contract fingerprinting still serializes the 3.89-million-character claim, taking about 0.030 / 0.032 s; this is explicitly counted. An initial preserved [calibration record](../audit/compiler-performance/C1-small/synthetic-1000/record.json) failed an overly strict benchmark guard that disallowed even contract fingerprinting. That guard failure was corrected in the benchmark, without changing the compiler.

Native CLI timings are explanatory components of the API phases, not equivalent alternative workloads. On test16, native `plan-return` processes took 1.811 / 1.750 s (Kernel internal totals 1.709 / 1.639 s), while their complete API phases took 18.356 / 28.067 s. Each plan also wrote two 28,974,956-byte MCM files, about 2 s each. Native `compile` took 0.313 s (internal 0.280 s), while `Proof.compile` took 31.005 s because it also refreshed complete returns and materialized/serialized the full certificate and Request. Native verification took 1.964 s (internal 1.914 s), with work 10,562,186, substitution terms 1,815,974, zero branches, and zero peak live proof facts.

The first synthetic native call to the copied macOS binary took 1.426 s despite a 0.006 s internal canonicalization total. The record retains this launch overhead; it was not charged as model parsing or hidden by rerunning the sample. Later native calls are much shorter. Source readback and native model preparation likewise retain both process-wall and internal timings.

The largest observation identifies a material remaining cost: complete Python goal/fact objects, whole-model serialization, and repeated complete-return refresh dominate the inexpensive identity proof's verifier cost. This motivates sharing/lazy materialization and reducing repeated complete-return construction while preserving exact caller contracts. It does not justify simplifying an Agent's reformulation, reducing requested obligations, or assuming a complex proof has the same cost.

## Compact completion follow-up

After native `resolve-return`, immutable Proof-owned model caching, and
revision-aware completed-check reuse were implemented, a fresh compact path
called `complete()` directly instead of asking for every goal expression first.
It preserves the same mathematical Request and checks every obligation. All
three fresh compact observations verified; **RPX and Request byte hashes, goal
counts, and every native verification statistic match the earlier observations**.
The [comparison record](../audit/compiler-performance/C3-comparison.json) binds
both sets of raw record hashes and derives the values below.

| Workload | Sum of measured phases s | Complete s, forward + reverse | Extra Certificate cache check s | Compile s | Verify s | Python peak RSS |
|---|---:|---:|---:|---:|---:|---:|
| synthetic-1000 | 1.157 | 0.038 | 0.013 | 0.058 | 0.009 | 32.7 MiB |
| pristine test9 | 0.294 | 0.076 | 0.019 | 0.092 | 0.021 | 40.5 MiB |
| pristine test16 | 34.609 | 8.671 | 2.314 | 10.888 | 1.922 | 2.07 GiB |

Compact raw records: [synthetic-1000](../audit/compiler-performance/C3-compact-small/synthetic-1000/record.json),
[test9](../audit/compiler-performance/C3-compact-small/test9/record.json),
[test16](../audit/compiler-performance/C3-compact-test16/test16/record.json).
Each issued exactly two `resolve-return` calls, zero `plan-return` calls, and
serialized its same immutable Model once into a Proof-owned cache. The extra
`certificate_cache` phase returned all complete checks without changing their
stored list objects or making any native/model-serialization call. Compilation
made no further resolver call. The full-plan inspection mode remains available.

On test16, Python peak RSS was 2,227,372,032 bytes; the largest native child was
877,019,136 bytes. The 34.61 s phase sum includes the extra 2.31 s Certificate
cache probe, which the 126.45 s baseline did not perform. Different revisions,
single samples, launch overhead, and concurrent work prevent treating their
ratio as a controlled speedup estimate. These observations isolate authoring
cost without weakening or omitting a proof obligation. They establish no LLM
timing, reformulation quality, or complete Agent acceptance result.

Each compact worker retained unchanged package/binary hashes during its run.
Subsequent fixes to reverse projection-pair orientation, index/label cache
selectors, and duplicate native assignment fields are outside the measured
snapshot. The records bind the earlier exact package/binary hashes rather than
claiming timings for every later revision.

## Reproduction

```sh
python3 tools/benchmark_compiler_api.py --cases synthetic-1000 test9 \
  --output audit/compiler-performance/fresh-small
python3 tools/benchmark_compiler_api.py --cases test16 \
  --output audit/compiler-performance/fresh-test16 --max-rss-gib 6
python3 tools/benchmark_compiler_api.py --compact-only --cases synthetic-1000 test9 \
  --output audit/compiler-performance/fresh-compact-small
python3 tools/benchmark_compiler_api.py --compact-only --cases test16 \
  --output audit/compiler-performance/fresh-compact-test16 --max-rss-gib 6
```

The script refuses to overwrite preserved outputs, pins the current binary, records implementation hashes, checks cache behavior, and stops on a failed verifier outcome or memory guard. Its default sources are the pristine input files from previously tested runs. Full-plan mode inspects every goal and tests plan caching; compact mode counts the Kernel resolver's obligations and completed checks without materializing goal expressions. New implementation changes can justify a new observation; these clear passing samples were not repeated to improve their reported timing.
