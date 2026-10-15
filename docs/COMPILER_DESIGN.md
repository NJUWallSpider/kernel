# Compiler design and demand coverage

This describes the implementation at source checkpoint `9822358` (2026-10-15),
against [the 81-case demand catalogue](COMPILER_API_DEMAND.md). The catalogue is
an analysis of observed needs, not a mandatory ABI or a case-completion score.
The package now has historical-corpus compatibility, native-backed examples,
supplied-proof regressions and fresh real-Agent evidence. These evidence layers
have different meanings. **The overall goal of comparable reformulation ambition,
quality and time together with complete verification is not yet established.**
The final C10 fresh round and its bounded quality review have ended. Five of
five Compiler deliveries were formally verified; the joint acceptance goal
remains unestablished. Work stopped after this round at the user's request.

The usage contract and examples are in [COMPILER_API.md](COMPILER_API.md). Counts below are demand occurrences from catalogue §3, not numbers of cases passed by this implementation.

## Architecture and responsibility

The path is Python `Model` / `Expr` / proof handles → existing typed `Certificate` → existing RPX encoder → Kernel verification. `compile` reads structured Certificate JSON directly; it does not call the RPA assembler. Compilation prepares an encodable object. Only verification against the complete caller Request and actual model pair establishes the requested relation.

The author chooses the reformulation, proof, domain, observations, and recovery
maps. The compiler supplies exact sparse arithmetic, named references, scoped
proof handles, explicit model edits, and Kernel-owned obligation enumeration.
It automatically reuses identical facts and the Kernel's narrow tautologies.
Selected pivot cancellation, supplied row combinations, fixed-coordinate
equalities, `zero_sum`, `parity_fix` and `subset_bounds` are deterministic
elaborations of supplied evidence. Ordered pivot plans accumulate a sparse
residual and only visit active later positions; batch rewrites reuse validation
without selecting a pivot order. Earlier pivots reintroduced later remain
residual. Subset sharing changes a derivation DAG over a caller-selected premise
and subsets; it selects no packing cover, model row or new inequality. The
compiler does not discover aliases, select a dominance transformation, search
linear combinations, search for a refutation or find a feasible witness.

Kernel preparation owns generated model scopes for interval, menu, signed, flow, subflow, restricted-domain, and paired injectivity constructions. Preparation exposes the exact model and required old-scope premises; it accepts no premise as proven. The verifier repeats the checked construction and validates every premise in its original scope. Return planning uses the verifier's own obligation walk, including bounds, rows, integrality, objective gaps, observations, and applicable compositions. Python never maintains a separate guessed obligation order.

The Python authoring layer, direct compiler and planning metadata are not proof
authority. Kernel acceptance depends on the actual model pair, separately
supplied Request and RPX. The native parsers, codecs, exact arithmetic, proof
execution and constructive lemma instantiations remain trusted code. In
particular, the five extension builders implement joint-existence lemmas;
checking their output premises and Return obligations does not remove those
lemmas or builders from the TCB. [SEMANTICS.md](SEMANTICS.md) and the
[lift trust review](../audit/LIFT_TRUST_REVIEW.md) distinguish mathematical
arguments, finite independent oracles and implementation review. No Lean or
other mechanized verification of the complete Rust implementation is claimed.

Two full directional correspondences need not be pointwise inverses. Authors
can declare `correspondence()` without maps and supply each complete tuple at
a branch or constructive scope's `complete(scope=..., mapping=...)` terminal.
`bijection` and LP equality remain optional stronger contracts. A failed
`box_le` check means declared box bounds did not prove that expression; it is
not a counterexample on the complete constrained domain. Supplied rows,
residual proofs and cases remain available for those obligations.

## Coverage of the main demands

| Demand; catalogue occurrences | Implemented route | Material boundary |
|---|---|---|
| `RULE_BUILDERS`; 81 | `lin` / `le` / `eq` / `int`, `round`, `eqpair`, local `cases`, terminal `split` / `close_absurd` / `close_positive`, Plotkin, constructive extensions | The general rules are available; domain-specific proofs still need user-authored templates. This does not mean 81 ergonomic case proofs have been demonstrated. |
| `EDIT_AUDIT`; 60; `TARGET_CONSTRUCTION`; 26 | Explicit substitutions, deleted/added/replaced rows, variables, bounds, integrality, objective; edit ledger and named full-model diff | A ledger records construction, not proof. No serialized edit replay/audit oracle. Repeated single-row or single-bound edits copy/revalidate the model; bulk edits deserve further work. |
| `BATCH_TEMPLATES`; 56; `REUSE_LIBRARY`; 7 | Python functions, loops, `batch`, shared Fact handles, sparse pivot/rewrite batches, `zero_sum`, `subset_bounds`, author-selected `binary_cases` | Shared derivation DAGs still emit ordinary frozen rules. No new compressed wire template, cross-claim proof sharing, or semantic row/lemma/subset selection. |
| `CLAIM_PLANNING`; 55 | Directional claims, deferred-map `correspondence`, optional `bijection`, independent integer flags, Kernel plans, named goals, compact `complete` | No intent-to-contract inference or reconciliation of prose with every property. The author declares each intended claim; every terminal still supplies every output coordinate. |
| `SCOPE_QUERIES`; 34; `MODEL_SHAPE_STATS`; 2 | Named readback, row support, exact box activity, column incidence, binary-domain checks, basic counts, signed coefficient/magnitude summaries | No alias-component, containment, identical-column, dominator, or coefficient-class discovery library. These remain ordinary author-side analysis. |
| `PROJECTION_BINDING`; 31 | Name-derived identity/retained maps, explicit coordinate pairs, affine observations, full output maps, inverse and constructive composition goals | Convenience expands to complete frozen lists; wire/request duplication remains. Observations never replace recovery of every output coordinate. |
| `MODEL_READBACK`; 31; `EXACT_ARITHMETIC`; 5 | Kernel MPS/LP/MCM validation followed by bounded canonical MCM decoding; immutable sparse `Fraction` expressions; float rejection; MCM writer; explicit exact standard-MPS adapter | The full Python model remains resident. Ordinary MPS export requires finite decimals; an explicit adapter may add scaled rows/one objective coordinate with its own proof. Kernel limits still apply. |
| `WORK_PREFLIGHT`; 17 | JSON size/depth and step/check/map/premise counts; configurable Certificate JSON compile budget; native work/live-fact statistics | No complete work, RPX-size or peak-resource estimator, no streaming Certificate parser and no automatic partitioner. Raising a compile budget does not raise verifier or codec limits. |
| `WITNESS_CHECKING`; 17 | Exact `Model.check_point`, feasible point contracts, existing strictness/fiber/image point objects | Witness values and complex refutations are caller-supplied. Specialized point-domain preparation and point construction are not fully wrapped. |
| `COUNTEREXAMPLE_TESTING`; 16; `ORACLE_CHECKS`; 5 | Public sparse structural `mutate` / `attack` helpers retain the caller Request; author arithmetic is checked again by the Kernel | No independent whole-edit oracle. Test mutations cover selected failure modes, not the corpus's complete attack catalogue. |
| `DIAGNOSTICS`; 14 | Named obligation origins/labels, builder residual/kind/scope errors, native status/code/location retained | Native step locations are not yet uniformly mapped back to caller template instances or edit records. |
| `OBJECTIVE_ALGEBRA`; 5 | Exact objective substitution, user-proved equality/nonincrease, Kernel gap enumeration, strict improvement margins | No objective-combination synthesis or automatic objective-level/attainment claim selection. |
| `MULTI_PART_ASSEMBLY`; 3 | Separate compilations; `verify_bundle`; explicit `write_chain` with stage hashes, exact named joins and author-selected claim paths | No automatic partitioning or inference of every intended global property. Restricted paths remain local; inverse/bijection/point/improvement contracts are not automatically inherited. |

Scope and domain needs from test24/test35/test64 are represented explicitly by projection, inverse/bijection, integer flags, objective relation, objective level, and affine halfspace. Strict improvement and image exclusion use the frozen V10 contracts. Improvement scopes expose the verifier's weak root fact `-positive <= 0`; local Cases and terminal Split retain its assumption index. `close_positive` consumes a supplied proof of `positive <= 0` to close a branch under the actual strict domain. These facts do not establish domain nonemptiness. A restricted-domain theorem must not be reported as unrestricted equivalence or attainment.

## The complex families still require proof work

The catalogue's sharpest cases explain why a general builder alone is insufficient evidence of usability:

- **Recovery and constructive bijections** (test13, test28, test59–test63, test72): exact extension and paired domains expose native per-instance interval, menu-option, signed-component, commodity, recovery and remainder handles, avoiding manual coordinate/row offsets. Native-backed tests cover all five families and simultaneous instances with different shapes. Fresh C9 includes actual Menu and Interval use, separately from the tests. This is positive evidence for those workflows, not exhaustive large-case or complete-bijection usability coverage.
- **Dominance, exchange, and logical aggregation** (test24, test47, test51, test87): complete piecewise maps and supplied Cases/linear proofs can express the existing certificates. No packaged dominance or exchange proof template has yet replaced their specialized preparers. Small binary-strengthening tests do not validate these larger workflows.
- **Large elimination and homogeneous cut families** (test10, test16, test42, test57, test70, test74, test83): sparse pivot/rewrite batches, exact fact indexing, compact native Return resolution and revision-aware caches avoid previously observed copies and full-goal materialization. `zero_sum` uses supplied zero witnesses and `subset_bounds` shares cancellations for supplied subsets. Native-backed supplied-proof regressions preserve full targets/maps/claims; the subset helper removes manual DAG authoring but did not improve runtime over the same hand-shared proof. Large models, complete checks and expanded certificates still have substantial authoring/serialization costs.
- **Parity and bounded refutations** (test67, test84): an author can supply explicit case trees and exact existing-rule derivations. `parity_fix` now elaborates one supplied equality with an odd binary coefficient and even other integer coefficients into ordinary checked steps. It does not find parity equations, perform elimination modulo two, or enumerate a refutation. Larger modular and bounded proofs still require author-provided witnesses and templates.
- **Fixed-coordinate equality closure** (test23): `eq_on_fixed` covers explicitly supplied one-coordinate equality facts and variables fixed by their model bounds. More general affine definitions can be combined with `rewrite` / `combine_rows`; the compiler does not discover a closure.

`compile_certificate` exposes every frozen Certificate variant as a structured Python object fallback. This prevents a convenience wrapper from excluding an existing wire feature. It does **not** establish natural proof authoring, comparable time, or unrestricted mathematical expressivity: all supplied proofs must still fit the frozen Kernel rules and limits.

## Resource and delivery boundaries

Direct compilation removes the RPA intermediate and its separate text policy.
The current native Certificate JSON default is **1 GiB**, independently
configurable through `Kernel(compile_json_bytes=N)` or the native
`rpx compile --max-json-bytes N certificate.json proof.rpx` command.
The native success report and delivery manifest record
`compile_limits.certificate_json_bytes`. Both metadata size and actual reads are
bounded. This compile-only policy changes no proof rule or RPX encoding and
does not raise model/Request input, RPX byte/item/depth, scalar, verification
work or live-fact limits. A larger JSON budget is not a guarantee that the
original large C9 proof clears every subsequent limit. No such success is
claimed by the small budget-boundary tests.

Non-JSON `Model.load` keeps native format parsing/validation authoritative and
uses bounded MCM reads to populate exact Python objects, without a complete
intermediate JSON export. Each model owns a canonical snapshot, released by
`close()`, context exit or GC; the original input is never removed. The existing
JSON-first dispatch remains separate. Certificate serialization now encodes
typed Fact/Expr/Fraction leaves on demand instead of first duplicating every
container through `wire()`. The complete Python model/certificate, output JSON
string and native decoded proof still occupy memory; this is not a streaming
Certificate compiler. Memory measurements are informative, not an acceptance
gate or a reason to reduce mathematical scope.

For standard solver delivery, `standard_mps_adapter()` is an explicit exact
representation stage. It folds row constants, applies positive denominator
scales, moves nonterminating bound sides to rows and optionally defines a value
coordinate for the complete objective. Four MI/LP Equal inverse claims use
ordinary Lin steps; large scales are split into wire-sized factors. Actual
standard-MPS readback must match the complete generated target. The adapter
does not choose a new reformulation, round coefficients or predict solver
quality, and ordinary `write_mps` does not select it automatically.

The measurements have separate scopes:

- [Historical plumbing](COMPILER_PERFORMANCE.md): full-goal inspection on pristine
  test16 took 126.45 s of measured phases; compact completion later took
  34.61 s. Both preserve 1,852,166 identity obligations and identical RPX/Request
  bytes. They are different-revision single observations, not a controlled
  Agent speedup or a complex-proof estimate.
- [Model-load microbenchmark](../audit/compiler-performance/model-load-stream-20261015/README.md):
  three alternating fresh processes per arm compare the old `231e6f4` package with bounded MCM
  readback on the same pristine test16 input/native. Median load time is
  5.138→3.838 s; native MCM bytes, exact structures and statistics agree. This is
  only Model.load, with warm caches, not end-to-end Agent time.
- [Supplied test16 encoder regression](../audit/compiler-performance/C8-test16-provided-witness-20261015/encoder-summary.json):
  all six artifacts and native statistics match the old helper proof, including
  four full MI/LP claims, 178,164 observations per claim and 3,118,120 obligations.
  The serialization/compile/whole-artifact-binding interval is 45.300→17.499 s.
  It is one serial sample; other phases also vary, so the total difference is
  not attributed entirely to the encoder or to autonomous proof discovery.
- [Supplied test70 subset regression](../audit/compiler-performance/C9-test70-provided-witness-20261015/comparison.json):
  the generic helper reproduces all 6,887 supplied Facts, the complete three
  claims/maps, 522,056 obligations, identical Certificate/RPX and native
  statistics. Measured totals are 140.772 s handwritten versus 144.158 s helper.
  This validates replacement of manual derivation code, **not a runtime speedup**.

`compile_certificate(..., committed_model=...)` reads the actual submitted
artifact and requires complete `Model.same_formulation` with the proof target,
recording both hashes. MPS/LP/MCM readback uses the Kernel; canonical JSON uses
the Python exact reader and has a distinct audit method. The comparison retains
named variables/rows, bounds, integrality, objective and coefficients, while
allowing model NAME/order differences and exact folding of row constants.
Reserved output paths reject aliases to inputs/committed artifacts. RPX
publication uses a temporary output and atomic replacement; a compile failure
keeps an existing RPX and publishes no replacement delivery manifest. This is
not an atomic transaction across every generated file.

`verify_bundle` rechecks artifact digests and formulation binding. Parallel
bundles retain their independent-piece semantics. Explicit `write_chain`
manifests bind every stage's source/target/RPX/Request, optional original anchor
and final committed artifact, without copying large files. Each stage is
verified with its own actual coordinates; adjacent complete named formulations
must match. Reuse by identical bytes additionally requires the same reader
family, so renaming MPS to LP or MCM to JSON cannot bypass format dispatch.
Only author-selected unrestricted claim paths with exact integer-domain
handoffs are composed, with objective strength and coordinate observations
tracked conservatively. Restrictions remain local, and stage inverse/bijection,
affine observations, points and improvements are not automatically inherited.
Without selected paths, no final relation is derived. Joins and elementary
composition are compiler-side checks; the Kernel accepts each stage Request.

The real-run harness additionally anchors the first source in the run's actual
input and independently verifies every RPX piece. Artifact audit `MATCHED`
means the complete final target matches the committed artifact; it does not
replace proof status, establish the usefulness of a model or validate prose
outside the Request. Listed pieces and selected paths still need to cover the
author's intended properties.

Certificate JSON now has a string-aware 272-container preflight, covering every
frozen valid block depth rather than imposing serde's smaller default. Wide
computed Fact metadata uses the 65,536-bit Kernel intermediate bound; it does
not widen RPX's 1,700-byte integer scalar literals or establish a proof.

## Validation status and acceptance gate

The [latest preflight receipt](../audit/compiler-performance/C10-preflight-20261015/validation.json)
binds the exact tested source files and release native
`cf9941c2daf9ab1434090069cc5040f902229e7b2d6d56003bcb0d8568e09da1`:
**344 Rust tests**, **158 Python 3.9 tests** and **158 Python 3.14 tests** pass.
Coverage includes exact format/model roundtrips, all five extension families,
whole-model/scoped proof rules, deferred piecewise maps, complete injectivity,
strict improvement, levels/halfspaces, points, chains/reader dispatch, atomic
outputs, rational MPS adaptation, sparse proof batches and compile budgets.
These are finite mechanical/example checks, not 81-case Agent acceptance or
proof of universal usability. Tests are in [python/tests](../python/tests/)
and [crates/core/tests](../crates/core/tests/).

Historical evidence is separate. The Kernel's original completed corpus covers
81 cases/83 complete requests after original-contract scope review. The
[direct-compiler replay](../audit/compiler-replay/README.md) reproduces all
83 frozen RPX files byte-for-byte across versions 1–10, with complete statistics
equal to an independently built pre-compiler `c16fdaf` verifier. Those are
already authored proofs; they establish bridge compatibility, not fresh Agent
discovery or natural high-level authoring. The mathematical Kernel/codec
protocols remain frozen; later compiler resource policy is a separate layer.

`python/pyproject.toml` declares Python **>=3.9**, uses setuptools >=61 as its
build dependency, and adds no runtime dependency. The current suites use host
Python 3.9.6 and bigdata Python 3.14.6. Build-tool availability is separate: the
host's setuptools 58 does not satisfy the isolated-build requirement; normal
isolated installation must obtain the declared build dependency. Checkout use
through `PYTHONPATH=python` requires no package build.

Fresh real-run evidence now exists. [C9 formal acceptance](../audit/compiler-agent/C9-summary.json)
records eight different previously tested inputs, all eight Compiler deliveries
Kernel-verified, with 16 matched Compiler/Nomf runs ending normally and complete
source/committed-target bindings. That round used frozen `539c146` Python/API
and the older pinned native `5775d6a`; later subset/budget changes were not in
those inputs.
The [subsequent closed quality review](../audit/compiler-agent/C9-quality-review.json)
preserves all eight source/Compiler/Nomf comparisons under a serial bounded
solver protocol. It records useful stronger-bound and solve-time results,
alongside time limits, absent incumbents, different mathematical strategies and
a real LP slowdown. Sizes, equal single-objective LP values or a 13.6% aggregate
Agent-wall difference do not establish comparable model quality or identify an
API/prompt effect. The immutable formal summary's old PENDING field is its
pre-quality cutoff, not the current quality status.

C9 also records actual proof friction: an uncompleted alternative after 197
box-only checks and a 639,796,634-byte certificate rejected at the former JSON
input budget. Generic documentation, subset sharing and a separate configurable
compile budget respond to those observations without choosing weaker targets
or deleting claims. Tests and supplied-proof checks establish their stated
mechanical behavior; they do not retroactively turn an uncompleted candidate
or failed attempt into a successful fresh proof.

The final C10 batch used source `9822358` with five pairs (test70, test38,
test58, test55, test69), including two inputs not previously fresh Compiler-tested.
All ten arms ended normally and all five Compiler deliveries (six proof pieces)
passed independent native checks, pristine-source anchoring and complete
committed-model readback. Agents naturally used `subset_bounds` on test70,
test38 and new test55. Test58 retained series contraction, two Menu lifts,
Signed recovery and 625 affine observations after correcting three proof-input
errors. These are actual expression and generalization positives.

The [final results](../audit/compiler-agent/C10-results.json) retain mixed
quality and time: total Compiler/nomf Agent wall is 2530.749/2588.169 s, but
the median paired ratio is 1.187401 and only two Compiler arms are faster.
Test70 explicitly cites reconstruction/fiber-contract work when choosing not
to aggregate; nomf aggregates more and alone finds a finite MIP incumbent in
the 120 s measurement. Test55's nomf adds stronger common-gate capacity work.
Test58's stronger LP bound coexists with slower MIP solving than the source.
These findings do not prove an API expressiveness impossibility, but they
prevent declaring the requested no-sacrifice near-nomf joint goal achieved.
No implementation or fresh experimental round follows C10. The
[project report](PROJECT_RESULTS_FOR_PAPER.md) collects project-wide positive
results and their exact evidence boundaries.
