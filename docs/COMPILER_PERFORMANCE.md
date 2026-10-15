# Compiler API plumbing measurements

This document separates early identity plumbing, actual public Agent phases,
and later fixed-witness regressions. RSS and the old benchmark's optional
memory guard are retained as historical metadata; memory is not a current
Agent-acceptance gate. The final C10 batch and bounded quality measurements
are complete; their separate workflow interpretation is recorded at the end.

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

The [C5 test16 phase diagnosis](../audit/compiler-agent/C5-test16-diagnostic/report.json)
uses the completed fresh Agent's retained public events, without replaying its
proof. Its measured cells total 247.75 s: three caller-written candidate-model
constructions account for 175.93 s, proof construction for 26.72 s, and final
commit/verification for 17.57 s (native verification total 2.37 s). The first two
model-construction cells repeatedly rebuild large membership sets inside a
definition loop; the third changes that code and completes in 17.17 s. This is
visible call-path evidence, not an internal profiler or a controlled speedup.
There is no observed recurrence of the C3 wide immutable-expression loop,
stale completion cache, or repeated full planner.

Complete Agent wall is 1325.07 s, with 1074.64 s recorded assistant duration.
Grouping that duration by the next visible tool intention attributes 85.32 s
to seven package-source lookups; this does not reveal hidden reasoning or
exclusive semantic costs. After the first visible verification, another
248.06 s remains, almost entirely assistant duration for scope/hypothesis
accounting and reporting. The Agent also reads a 4.7 MiB Request whose output is
truncated. The public batch-helper index and bounded `contract_summary()` /
receipt `request_summary` address these observed interface frictions. Their
effect on fresh Agent wall and reformulation quality remains to be measured;
neither this diagnosis nor a supplied-proof replay is autonomous acceptance.

The later [supplied C3 test16 proof diagnostic](../audit/compiler-performance/C3-test16-sparse-rescue/README.md)
reconstructs that failed Agent's existing mathematical choices in a separate
workspace. Its unchanged first exact-stage target and four MI/LP inverse claims
verified: 2,892,181 obligations, 36,678,549 work, 394,395 peak live facts. Sparse
Eq completion took 25.94 / 29.67 s; four-claim authoring took 153.80 s, compile
41.59 s, and native verify 4.53 s. Total observation was 462.68 s including
243.47 s of supplied-prefix reconstruction; sampled process-tree RSS peaked at
5.15 GiB. The original 858.78 s interrupted Eq loop was not repeated.
This is a supplied-proof performance regression, not autonomous acceptance;
the failed C3 run remains failed, and its later dominance stages are unverified
by that receipt. Exact measured hashes and different phase boundaries remain
in the record. Fresh Agents receive no archived equations, maps, or case hints.

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

## Exact MCM readback

The [stream-readback record](../audit/compiler-performance/model-load-stream-20261015/report.json)
compares the old `231e6f4` package with the preserved stream-reader package on
the same pristine test16 source: 228,350 variables and 126,512 rows. Three
fresh processes per arm run serially in interleaved order. Median `Model.load`
wall time is **5.137581/3.837865 s** (old/stream). All six Python re-encodings
equal the native canonical MCM bytes; once per arm, every loaded Python field
also matches the native JSON oracle. The native binary remains unchanged.

The new path reads the 28,974,956-byte MCM rather than round-tripping an
84,143,968-byte exported JSON model. It preserves the prior file-reader cap
and exact input interpretation. There is no OS cache flush, and oracle setup
reads the input first. This is a load microbenchmark, not Agent latency or a
global resource-isolation result. See its [script and reproduction notes](../audit/compiler-performance/model-load-stream-20261015/README.md)
for pinned package/input/native identities and all samples.

## Same complete test16 proof: zero/alias helpers and leaf encoding

The [provided-witness comparison](../audit/compiler-performance/C8-test16-provided-witness-20261015/summary.json)
fixes the original C8 source, target, complete maps and four MI/LP Equal
direction claims, each with inverse checks on 178,164 retained observations;
no separate full-model Bijection is requested. Both authoring arms use the
same frozen `5c42197` package and native binary. The only intended change is
replacing the supplied zero/fixed/alias derivation with `zero_sum` and batched
`rewrite_many`; no closure, target or proof is searched.

Each forward scope checks all **50,186** generated equations for exact
expression, scope and visibility, covering 29,502 zeros, 20,683 aliases and
one declared nonzero fixing. Both complete proofs verify **3,118,120** native
obligations and match the original committed MPS. Source/target/Request/MPS
bytes agree. The helper intentionally changes proof steps, so its RPX and
work count differ; validity and full theorem scope are the preserved checks.

| Measured interval, s | Original supplied author function | Helpers |
|---|---:|---:|
| Zero/fixed/alias derivation, both forward scopes | 12.382171 | 4.613508 |
| Forward author functions including substitution | 49.840015 | 41.691923 |
| Serialization + compile + whole-artifact binding | 41.636519 | 45.299733 |
| Native verifier process wall | 6.124031 | 5.314956 |
| Full measured execution | 147.734220 | 139.443656 |

This is one serial baseline-first sample per arm on a shared host, not a
fresh Agent or solver comparison. Serialization is slower in the helper arm;
the favorable derivation observation is not a stable whole-pipeline speedup
estimate or isolated attribution to a single repeated-set line. The original
two-arm scripts and results remain unchanged.

A third, separately preserved [leaf-encoder arm](../audit/compiler-performance/C8-test16-provided-witness-20261015/encoder-summary.json)
uses frozen `539c146`. The supplied helper proof is unchanged: all six
source/target/Certificate JSON/Request/RPX/committed-model artifacts are
**byte-identical**, as are all native statistics and the 3,118,120 obligations.
The Certificate and RPX sizes are 149,703,351 and 98,008,826 bytes. Recorded
serialization/compile/whole-binding time falls from 45.299733 to 17.498845 s;
full execution is 139.443656/99.930259 s. Non-serialization phases also vary,
so the entire 39.513397 s total difference is not assigned to the encoder.
It is one final serial regression sample, with no additional memory rounds
or RSS gate. The [encoder notes](../audit/compiler-performance/C8-test16-provided-witness-20261015/ENCODER-RESULTS.md)
bind the exact package, original helper reference, script, native and outputs.

## Same complete test70 proof: subset DAG authoring

The [test70 provided-witness comparison](../audit/compiler-performance/C9-test70-provided-witness-20261015/comparison.json)
uses frozen `8ebcc97` after C9 and after its solver process has stopped. Both
arms preserve the original author's chosen 1,202 aggregate groups, 1,679 gate
covers, all complete maps, three directional claims and 45,017 observations
per claim. No cover selection, mathematical discovery or reformulation search
is rerun. `subset_bounds` replaces the supplied hand-written sparse/dyadic
sharing code using the same author-selected premises and subsets.

All **6,887** subset facts match in exact expression and root-scope visibility.
The 114,694,805-byte Certificate JSON and 110,074,809-byte RPX are byte-identical
to the hand-written proof, with identical full native statistics:
522,056 obligations, 1,679 branches and work 81,652,500. Source, target,
Request and committed MPS also preserve the original identities.

| Interval, s | Hand-written DAG | Generic helper |
|---|---:|---:|
| Subset elaboration | 22.107202 | 34.170583 |
| Full measured execution | 140.771588 | 144.157521 |

The helper is slower in this single serial observation. The demonstrated
benefit is removing author-written proof DAG plumbing while preserving the
complete proof; it is **not** a runtime speedup or fresh-Agent improvement.
The original C9 large-certificate failure remains unchanged. C10 later
includes the helper and a separate configurable Certificate JSON budget,
but this fixed-witness record is not evidence of C10's autonomous result.
The budget does not relax downstream RPX/verification resource policies,
and resource rejection is not a mathematical counterexample.

## Agent-level interpretation and final cutoff

The [acceptance record](COMPILER_AGENT_ACCEPTANCE.md) and individual round
summaries give complete C5–C9 timing and quality rather than concatenating
the best measurements across rounds. In particular, C7 test16 repeats a
200.008 s self-authored large-set diagnostic; C8 lacks that cell, but chooses
a different target, so its shorter wall time is not an isolated prompt effect.
C9 test70's 858.989 s Agent wall includes a failed oversized Certificate and
re-authoring the same given proof, while final native verification takes
3.551523 s. Most pipeline or model time must not be labeled Kernel execution.

All supplied regressions above retain full actual contracts and independent
committed-artifact binding. They are distinct from the fresh Agent acceptance
criterion. C6 quality is unmeasured; C7/C8/C9 bounded quality is separately
complete and mixed. Final C10 has five formally accepted deliveries, six proof
pieces and ten normally ended arms. Its total Compiler/nomf Agent wall is
2530.749/2588.169 s (ratio 0.977814), but the median paired ratio is 1.187401
and Compiler is faster on only 2/5 cases. These different targets and contracts
are not a fixed-task causal prompt comparison.

The [final review](../audit/compiler-agent/C10-results.json) retains all quality
outcomes: test70 has a stronger Compiler LP bound but only nomf finds a MIP
incumbent; test55 has stronger nomf capacity aggregation/LP bounds but a better
Compiler MIP incumbent; test58 expresses complex Signed/series recovery yet
both reformulations solve worse than the source; test69 has equal LP bounds
and a better Compiler incumbent. Test38 reports Optimal in 66.161/71.355 s
for Compiler/nomf, each n=1. Optimal is the solver's numerical tolerance status,
not an exact optimum proof. Full n, objectives, dual bounds and time limits
remain in the raw review.

The test69 phase records a repeated 10198-coordinate dictionary construction
1499 times inside one mixed 41.274 s tool cell. This is an observed author-script
cost; the entire cell cannot be attributed to that loop. Test38's public
1.35/1.55/5.12 s values share one start time and are cumulative, not independent
compile/verify measurements. Final phase records preserve those distinctions.
No further profiling, optimization or experimental round follows C10. The
[project report](PROJECT_RESULTS_FOR_PAPER.md) collects historical and current
positive results without converting them into the unmet joint acceptance claim.
