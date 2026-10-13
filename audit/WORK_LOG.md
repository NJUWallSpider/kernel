# RPX kernel development record

Objective: `/Users/bhz/.codex/attachments/1964a347-684e-42a2-bc83-824d29db5b44/goal-objective.md`.

2026-10-11: repository initially contains an FNV hash stub, Python shim, and D0 RPA/RPX draft; no verifier implementation. Working directory has no Git metadata. Original materials remain untouched. Corpus snapshot is being inventoried; runs may be added externally, so inventory records timestamp and hashes.

## Completion discipline

The complete task is not finished until every correct, input-complete target is certified, actual binary RPX execution is tested, specifications match code, and clean acceptance/measurement is reproducible. A certificate failure does not refute a reformulation. Existing agent verifier PASS reports are untrusted evidence, never kernel acceptance.

## Current work

- Audit all runs and record source/target identity and contract claims.
- Audit D0 mathematical and decoding semantics.
- Implement exact rational model import and a minimal real bidirectional proof path.
- Freeze baseline workloads before measured optimizations.

## Initial architectural decisions (provisional)

- Pure safe Rust, mature arbitrary-precision rational arithmetic; no float acceptance.
- Kernel reads actual complete model data and derives every output obligation itself.
- Version 1 implementation will be explicitly distinct from unimplemented D0/v0.1 draft.
- First implementation prioritizes a sound, inspectable path; coverage limitations stay visible.

## First acceptance milestone

- All81 runs (1203 files,2,487,477,246bytes) inventoried and hashed. All models present; test8/test60 involve LP text. Full MPS sweep159/159 successful after two fixed/free-bound parser regressions were repaired; original157/159 sweep retained.
- Actual immutable MPS pairs certified: test40 complementary-variable affine bijection; test79 equality-based row rewrite; test68 invertible equality differences; test33 transitive reduction; test65 redundant inequalities. Integer and LP claims, objective equality, requested original/retained-coordinate projections, and inverse-map obligations explicitly checked. Ledger5/81,76 unfinished.
- Binary RPX/MCM V1 and RPA1 implemented; safe Rust exact BigRational arithmetic. No theorem/batch/host plugin accepted. Caller request cannot be weakened by certificate.
- Independent Python Fraction oracle4000 vectors; semantic and adversarial checks;2000 MPS mutation inputs; codec truncation/canonical/random malicious-byte tests. Seeds retained. Test totals evolving; rerun before final report.
- Fixed baseline and optimization measured. `bench/results/baseline-v1-quiescent` vs `sparse-v1-quiescent` are comparison runs; earlier overlapping worker measurements are explicitly excluded. Sparse accumulation removes quadratic long-row cost: dense5000 median475.208ms→6.974ms execution; identity10000~6% regression disclosed. Source baseline snapshot exact model-layer reconstruction still pending.
- Fifteen generated affine-elimination variants with independent names/row/column permutations and bounds1,2,17 passed actual MPS→MCM→RPA→RPX→kernel. They do not count as extra corpus coverage.

## Active next work

- draft_audit agent owns proof/verify/codec/rpa: V2 local Cases proof of a fixed scalar fact (and EqPair antisymmetry), preserving V1 byte meanings and rejecting V2 opcodes under V1. Must be fully tested/versioned.
- corpus_audit agent owns case preparation and acceptance: real test88 integrality-dependent aliases via local Cases; unchanged target, full bijection, no unclaimed LP relation.
- model_layer agent owns exact LP importer for test8/test60 and baseline-model source reconstruction; no model relation certification from parsing alone.
- Root owns performance/reporting/generalization and integration. No final functionality completion claimed. Remaining75+ cases, stronger LP strictness witness checker, shared mappings, joint constructive theorems, full performance suite, clean rebuild and full final audit remain.

The original read-file goal was completed after reading; the active goal now explicitly
contains the full kernel delivery objective from the supplied objective file. This
administrative transition did not mark the implementation objective complete.

## V2 clean checkpoint and continuation

Seven real targets now certified: 33,40,65,68,79,84,88. Test88 uses 352 exact aliases
and 5,376 local binary branches, full integer objective-preserving bijection; no LP
claim. Test84 uses 100 checked modular combinations, generic integer linear facts,
rounding and antisymmetry to force all 200 original variables; no trusted parity
theorem was needed. Negative mutations rejected in both cases.

All three actual LP files parse and independently match every canonical-model field
via a separate Python Fraction parser/MCM decoder. All159 MPS remain canonicalized.
Pointwise import evidence does not upgrade unresolved model relations.

`python3 tools/run_acceptance.py --label checkpoint-v2` completed a fresh locked debug
test build and release build, then replayed all seven actual RPX files successfully.
Raw commands/output and binary/artifact hashes are in its JSON. V2 code, tests/vectors
and current specs are snapshotted at `audit/checkpoints/v2-source.tar.gz` with hashes.
Fifteen renamed/permuted/parameterized affine cases passed the clean release binary.
LP exponent-name hardening was finalized just after this checkpoint; it has its own
passing tests/full three-file independent sweep and must be included in the next
clean integration run.

### Active V3 work (not accepted coverage yet)

- draft_audit owns generic Plotkin step, versioned codec/RPA, optional per-claim input
  objective lower bound, extended request/certificate witness types and integration.
- model_layer owns exact feasible-point/strict-inclusion witness checker and tests.
- corpus_audit owns test71 complete certificate: integer identity bijection, LP
  containment, strictness witness, source MIP optimum -12 and target LP optimum -12.
- Full target requires every obligation/witness checked by the kernel. Independent
  Python test71 evidence is preparation only. No solver search or float acceptance.

V3 must preserve V1/V2 bytes and semantics, reject its new logical tags under older
versions, and rerun the previous seven cases. Explicit next mathematical gaps include
joint flow disaggregation (test28), shared mapping DAGs (test38/57/59/60), optimal-face
and projection contracts (test48/72/78/80/83/87), further valid inequalities, and strict
LP witnesses with non-bijective auxiliary projections. The corpus denominator stays81.

Remaining performance work: finish a fully reproducible baseline reconstruction
(model snapshot mismatch is disclosed), freeze/measure required chain/history/branch/
big-integer/theorem families, optimize small-case regressions and actual RPX scale,
record all certificate preparation costs and actual-case time/RSS distributions.

## V3 frozen integration and V4 continuation

All101tests passed in a clean locked build of the frozen V3 workspace; all eight
actual RPX certificates replayed VERIFIED. Raw commands, hashes and timings live in
`audit/validation/checkpoint-v3/run.json`, source snapshot and per-file hashes in
`audit/checkpoints/v3-source*`. Test71 includes integer equivalence, strict LP
strengthening, source integer optimum and target LP optimum −12; its5attacks reject.
Root independently reviewed theorem/domain coverage, complete point checks, request
binding, budget composition and version isolation; see `audit/V3_REVIEW.md`.

Coverage is8/81;73remainuncompleted. Every actual model remains in the denominator.
FlowLift V4 is being implemented for test28: common-source nonnegative flow has a
joint constructive commodity decomposition, retaining every arc total and all
circulation. The checker must first prove every aggregate flow premise, then append
all commodity variables/laws together and verify every actual output obligation
with ordinary proof rules. This is not accepted coverage until a real RPX passes.
Draft proof/schema in `docs/FLOW_LIFT_DESIGN.md`; other agents independently checked
its real-flow path termination and residual circulation construction.

Additional benchmark matrix `bench/extended_workloads.json` frozen before further
representation changes: history/live-state, branches, explicit affine chains, local
row edits, 64/512/4096-bit arithmetic, and all eight actual certificates. Fixture
checks are diagnostic, not performance distributions. Reconstructed controlled A/B
uses identical frozen model/codec sources with only the sparse verifier changed;
source-root metadata now records the exact variant rather than current production.

## V4 acceptance and full V3 performance measurements

Frozen V4 source rebuilt independently with114passing tests and all9actual RPX
certificates replayed VERIFIED (`audit/validation/checkpoint-v4/run.json`). Test28
jointly reconstructs2350commodity flow coordinates,1593laws, retaining circulation,
all150integer decisions and all attainable objective values;4attacks reject.
Coverage9/81;72remainunfinished. V5 interval extension and affine observations for
actual test23 are now being implemented by draft/model/corpus workers; no coverage
until the complete RPX contract executes.

Controlled identical-source sparse A/B completed and archived. Dense5000 executes
477.811ms→6.340ms; identity10000regresses15.190ms→15.673ms. Historical measurements
remain unchanged. V3 extended fixed matrix completed23loads×9fresh-process samples
plus3RSS samples each, all276processes VERIFIED. Report `bench/EXTENDED_REPORT.md`
discloses process/execute distributions,physical bytes,work,livefacts,RSS and missing
fine CPU attribution. Realcase65 median3757ms execute,4284ms fullprocess,865MiB RSS.
History65536has only2livefacts yet53MiB RSS due complete decoded proof storage.

Root is testing an isolated boxed-Cases layout prototype copied from frozen V3,
not modifying production. It preserves wire/serde/math; existing101tests pass.
The fixed workloads and source/binary hashes must be compared before accepting it.

## V5/V6 and measured representation work

V5 frozen source clean-built and replayed all10actual cases successfully. Its130tests
include complete interval extension and explicit affine observations. Actualtest23
jointly restores2467continuous variables in each reverse direction and preserves
all requested signed relations;181296terminal obligations,4negative attacks.

V6 original-scope source is frozen under audit/checkpoints/v6-original-scopes-source,
147tests passed in worker run; root clean build/replay pending/results are in
checkpoint-v6-original-scopes. V6 uses complete output point plus ordinary exact LP
fiber refutation to prove strictness under partial coordinate/affine observations.
Actualtest18naive completeRPX actually hits RESOURCE_LIMIT with old cloned scopes.
Its certificate/models/request/binary hashes and raw receipt are preserved in
preparation.naive-resource-baseline.json. It remains a resource gap, NOT certified
or refuted. Denominator81:10verified,1resourcegap,70uncompleted proofs.

BoxedCases isolated experiment met predeclared memory target: Step208→96bytes,
history65536 RSS53.25→39.25MiB, test88RSS51.125→43.219MiB; branch1024no material
execution regression. All23artifact hashes and math counters unchanged across
207verification+69RSS candidate runs;101existingtests pass. Full evidence in
bench/BOXED_CASES_REPORT.md. draft agent integrating layout into V6 after snapshot.

Root also froze scope_workloads.json before implementing borrowed parent scopes.
Candidate bench/shared-scope-prototype changes only verify.rs from frozenV5:
immutable parent borrow+local facts+tombstone masks, logical livecount; ancestor
lookup probes charged. Existing130tests pass; model_layer independently audits
DROP/reuse/siblings/deep scopes and cloned-map reference traces. Original simpler
unmetered-probe draft is retained in shared-scope-prototype-initial, NOT production.
Fixed A/B measurements and actualunchangedtest18replay still pending.


## Shared scopes accepted; unchanged test18 now verified

The fixed V5 A/B scope matrix is complete, with 36/36 verifier processes VERIFIED,
identical model/RPA/RPX/request hashes and identical non-work math counters. At
4096 live facts and branches, median execute cost falls827.142→6.517ms and RSS
13.719→12.578MiB. This selected copying-heavy family is not an overall speed claim;
broader fixed regression matrix is next. Source-only change and all distributions,
preparation costs, and conditions are in bench/SHARED_SCOPE_REPORT.md.

Independent state audit:7tests,127072operations in128seeded copied-BTreeMap oracle
trees plus64-level boundary/probe regressions. Precise V6 merge retains boxed Cases,
refutation endpoint guard and both fresh root initializations; proof/codec bytes
unchanged. All154coretests pass. Whole-workspace wrapper tests cannot start due
missing libpython3.13.dylib, preserved explicitly in scope_v6_merge.json; production
Rust verification tests and release build succeed.

Frozen v6-shared-scopes-source snapshot/manifest/tar contains187files. Fresh locked
build and all12preparedrealcase replays pass in checkpoint-v6-shared-scopes. Test18
uses the exact RPX/MCM/request from its original RESOURCE_LIMIT receipt; same bytes
now verify with18444branches,96720obligations and8266292work. Test19 is newly certified
with full integer bijection and strict LP projection relationship. Coverage12/81;
69remainunfinished. No denominator changes or claim weakening.

59/60 actual menu full-field structural audits passed but are NOT kernel acceptance.
They require optional integer MenuLift plus independently proved injectivity to
support actual bijection. A generic duplicated-domain proof is being designed;
old affine-inverse semantics must remain unchanged. Remaining families, including
shared DAG and normalization transformations, remain active work.


## Extended scope regression matrix and further real-case coverage

Both scope-only frozenV5 variants ran the complete unchanged23-workload matrix,
9timing+3RSSsamples each:552processes VERIFIED. All artifact hashes and all nonwork
math counters match. Test88execute182.553→120.189ms, but nonbranching workloads
show about3%regressions, fully disclosed in bench/SHARED_SCOPE_REPORT.md. This is
not a broad speedup claim. The copied-state quadratic cost and actualtest18resource
failure are removed without changing its certificate or resource ceiling.

Test57 complete4MI/LP affinebijection claims pass1956604obligations with16872
eliminated sums reconstructed. Test38 full2MI inverseclaims pass59669obligations,
14556localCases,5031oldDAGnodes→3281sharednodes;5attacksreject. The untrusted proof
uses source representatives and scalar aliases rather than recursive map expansion
or a trusted DAG theorem. Twelve shared-switch metamorphic serialized model pairs
vary names,row/column orders,weights1/8,3/10,7/8 and sizes1,4,16,64;all12pass both
inverseclaims plus24independent Fraction completepoint checks. Evidence is in
audit/shared_switch_generalization.json. Coverage14/81;67stillunfinished.

V7 MenuLift and full affine-map BijectionClaim implemented by workers,177coretests
pass. Root independently reviewed generated menu premises, complete paired source,
alltarget composition, modes/freshscope/sharedbudget, and version layout with no
finding. Actual59/60fullcertificates are now being executed;partial3claimresults
remain explicitly uncompleted until full4claims+injectivity+rightinverse pass.
Fresh frozenV7 build/replay still required. Next hard normalization family47/48 is
under read-only mathematical/actual-model audit, not yet supported or certified.


## V7 fresh checkpoint and16actualcase milestone

Fresh frozen v7-source snapshot has284files plus hashmanifest/archive. It passes177
coretests and replays15actualcertificates; the same freshbinary subsequently passes
test59 in checkpoint-v7/test59-late.json because that RPX was not yet present when
the first replay enumerated inputs. Actual59/60 full4claims+bijectivepair bothpass,
all5attacks percase INVALID. Their partial3claim receipts remain separately marked.
Coverage16/81,65unfinished; no functional-delivery claim.

The additional frozen theorem_workloads_v7 matrix contains18syntheticloads across
menuK0/2/12, interval, loop-flow and paired injectivity scales, plus8actual full
certificates. Diagnostic26/26pass; those overlapping one-shot times are not a
performance result. Isolated9timing+3RSSsamples perworkload are running with all
workers holding computation. No additional representation/numeric optimization
was made before fixing this matrix. tools/profile_verifier.py is prepared for
external OS sampling of our own verifier after the benchmark, not run yet.

Next work proceeds in parallel without new trusted rules so far:47 priority
dominance normalization using interval ANDs/telescoping swaps;48 conditional
priority normalization using interval ANDs/local Cases;54 monotone endpoint,
forcedzero,aliases and leaf elimination. Full real certificates still pending.


## Completed V7 fixed baseline and normalization coverage

All26fixed theorem/realcase workloads completed9fresh-process timings+3separateRSS
runs:312/312 VERIFIED, allartifactsidenticaltofixturecheck and allmathcountersstable.
Workersheldcomputationthroughout. Fulltimedistributions,RSS,read/model/proofdecode,
physicalRPA/RPXsizes,logicalwork,generateddomains,andseparateprepcostsarepreserved
in bench/THEOREM_V7_REPORT.md and raw.json. Actual59/60executemedian4247.703/4846.733ms;
thisisabaseline,notaspeedupclaim. Historicalprepreceiptsincludemixeddebug/release
buildsandaredisclosedassingleobservations,notcontrolledcomparisons.

ExternalOSsample57completedwithVERIFIED,1519mainthreadsamples. Inclusiveaccumulator,
substitution,validationstacksandbigintgcd/divisiontopofstackidentifyrepeatedexact
arithmeticcost. Profiletimesexcludedfrombench;overlappingcountsnotCPUpercentages.
Nextnumericalexperimentwillpreservecanonicalchecksandintermediateresourcechecks.

Actual48and54fullcertificatesnowVERIFIEDwithtargetedcorruptionsINVALID. Ledger18/81,
63unfinished. Test54fourMI/LPclaims619558obligations,7098328work,13491092RPXbytes,
32793retainedcoordinatespreserved. Monotoneendpointsarenotassertedforcedorbijective.
Test47stillinprogress. Nochangeinproductionrulesrequiredfor48/54.


## Further exact cut and normalization certificates

Actual49 completed using existing Lin/Int/Round only:20capacitycuts,3fullclaims,
all2013coordinates and both MI inverseidentities,completeLPstrictnesspoint plus
4MI feasible tree/circulation pointchecks.25060obligations212771work,579820RPXbytes;
5attacksINVALID. Actual44 completed3claims+3completepoints,37localdesigncuts via
1746scalarCases,38485obligations1146726work;5attacksINVALID. No network theorem or
trusted enumeration. Original49/44MPSmodelsandobjectivesunchanged.

Actual47 transformed the proof representation rather than relaxing parserpolicy:
balanced integer-sum zero search lowers coredepth53→38andJSONdepth186→126. Original
complete candidate and recursionfailure preservedunderattempts/linear-and. Final
fullcandidateVERIFIED,7attacksandindependentnormalizationoraclebeingcompleted.
Actual69simultaneous1500intervals+6446CasesalsoVERIFIEDwith4attacksINVALID.


## Exact arithmetic merge, resource repairs, and further actual certificates

The fixed 26-workload theorem matrix and 23-workload extended matrix completed
both arithmetic variants with nine fresh-process timings plus three separate RSS
runs: 1,176/1,176 VERIFIED, identical artifact bytes and mathematical counters.
Independent review recomputed the paired distributions. All execution medians
improve, while small whole-process regressions and unchanged memory remain
explicit in bench/RATIONAL_SHORTCUTS_REPORT.md. Prototype182tests include1,228
independent exact vectors. Production adds two separate resource-policy fixes:
check Expr::add_scaled temporary constant product, and classify unchanged JSON
recursion exhaustion as RESOURCE_LIMIT. The original failing regression and old47
candidate remain preserved. All185production tests pass; frozen498-file snapshot
freshly builds and replays26actualcases, plus late20 with the same binary. The
measured prototype and final production executable have distinct recorded hashes.

Further complete real certificates include9,13,20,50,63,75,77 in addition to44/47/49/69.
29/81actualtargets now have full successful receipts;52 remain unfinished. Test20
proves24 nonzero demand offsets from full actual balances, test50 proves relaxed
integrality of11,935 coordinates and full original bounds, and test77 proves50
weighted choice substitutions plus42 completion redundancies and58 removed bounds.
All include complete contracts and targeted corruptions. No new trusted rules were
introduced for these cases. Cases70,87,21 and16 are active work and are not counted.


## V8 signed real-flow decomposition and34actualcases

Actual26 is VERIFIED with179202obligations,38scalar gate Cases,4502actual-row
integrality recoveries,6INVALIDattacks. Actual16,21,87 are also complete with
full contracts and negative cases. Actual27 now verifies2complete MI directions:
forwardNonIncreasing/reverseEqual and760signed-flow observations. Its forward ORs
use760Interval choices+2280Cases; reverse uses newV8SignedLift. No false claim of
full feasible-set bijection or preservation of dominated original objectives.

V8 adds five checked old-scope premises per signed/binary pair,4jointvars/4rows,
with nonnegative rational capacity and an explicit real sign construction. Full
statement/binarytag6/docs and independent source review are saved. All198coretests
pass including13newtests,72Fraction vectors/6batches and independent673byteRPX.
A new test initially expected premises in final-output-obligation counts; corrected
that expectation to13 with no production change. FreshV8checkpoint is next.
70full ordinary-rule attempt remainsRESOURCE_LIMIT, nowunderproof-size/work
optimization;78and80are in progress. Coverage34/81;47remainunfinished.

## User architecture review and consolidation checkpoint, 2026-10-11

The V8 frozen rebuild completed: 198 core tests and the 34 actual certificates
enumerated at snapshot start pass. Later cases have separate receipts and the
live acceptance ledger remains authoritative for current coverage. The fixed
V8 signed baseline completed 120/120 successful processes with raw distributions,
preparation costs and memory recorded in bench/SIGNED_V8_REPORT.md. No speedup
claim is made for that new baseline.

The user identified three design issues: trusted lift existence/construction is
not independently checked, successive capability-driven formats have not yet
converged, and model builders duplicate mechanical helpers. Root and two agents
reviewed these separately. The first and third observations are valid; the
second exposes real audit/maintenance costs, although the implemented rules do
not use case IDs or whitelist model identities and DAG/batch sharing cannot by
itself replace an existence lemma.

Corrected lift module comments, verify.rs, MENU_V7/INTERVAL_V5/FORMAT_V8 and the
trust report to distinguish old-scope premise checking from trusted generation
of a simultaneously satisfiable extension. This is a documentation correction,
not an independent checker, formal proof or soundness repair. No runtime
acceptance behavior was changed by root in this review. No extra tests were run
for comments alone. Shared-helper extraction and format consolidation remain
unimplemented; do not report them as complete.

V9 objective-domain code is currently buildable and locally tested but remains
unfrozen and has no actual test80 certificate. New common production-rule work
and version freezing were paused for architecture review. Flow-pruning work is
an isolated unfinished prototype, not a released next-version capability.
Existing-rule actual-case certification continues independently. Next consolidate
the remaining mathematical requirements and mechanical helpers before freezing
additional formats; keep fixed old bytes, receipts and benchmark baselines.

## Shared builder mechanics implemented and checked

Extracted build_support.rs and migrated flow/interval/menu/signed/point/injectivity/
level. Checked counts, allocation, complete prefix copying, old-model scan cost,
canonical sparse difference, work budgets and generated-name collision handling
now share one implementation. Each inference lemma and its exact generated rows
remain local. Including the shared module, production source shrank by401lines.
No public API, accepted theorem, model semantics or RPX/RPA encoding changed.

The immutable internal baseline is bench/builder-support-baseline with521files
recorded in audit/builder_support_baseline.json; it includes the already working
but unfrozen objective-level draft. Both old/new core suites pass210tests. The
audit probe compares576 complete builder results,456 rejected malformed models,
and1728 work-boundary calls per executable with zero result/model/statistic
differences. The96 objective-level exhausted-name cases differ only in error
detail text. Initial harness-only serialization/name mistakes failed before a
builder and are retained separately; no production fix was made for that failure.

All48 actual certificates enumerated for the before/after run pass on both
executables with identical complete statistics; all48 RPA files reassemble to the
existing byte-identical RPX. This includes the newly complete test80 optimizer
bijection with global bound/attainment, restricted forward input and reverse image
closure, while its protocol stays unfrozen. Its nine attacks reject. Current
accepted-case additions since the V8 enumeration include70,11,15,12,43,78,35,30,
14,25,17,42,22and80; the live ledger records exact contracts and remaining cases.

Primary evidence: audit/builder_support_extraction.json,
audit/validation/builder-support-differential-v2/result.json and
audit/validation/builder-support-corpus/result.json. Timings are diagnostics,
not a controlled speed comparison. Full task and final-format convergence remain
unfinished. Independent source review is complete in BUILDER_SUPPORT_REVIEW.md
with exact identities; it found no semantic or resource-threshold regression.

## Consolidated format and remaining-needs review

docs/CURRENT_FORMAT.md now provides one complete MCM/RPX/RPA reference for
versions1-8 and a separately marked, unfrozen V9 appendix. Independent comparison
with both codec directions corrected five specification ambiguities, including
composition-coordinate order and valid Exact operand contexts, without production
changes. audit/CURRENT_FORMAT_REVIEW.md and current_format_review_identity.json
record the scope and exact file identities. This does not freeze a new format.

audit/REMAINING_REQUIREMENTS.md and remaining_requirements.json record all37
unfinished cases at an immutable44/81 snapshot, actual model/report hashes,
contracts, candidate ordinary-rule routes and resource risks. Later successes
are separate from the baseline; the live acceptance ledger is authoritative.
The inventory identifies one presently justified additional existence candidate
(common-source bounded subflow for58), separately from stronger contract gaps
and representation costs. It does not claim impossibility in the current ISA or
authorize a new frozen theorem from a report's argument alone.

## Parallel completion wave (2026-10-11, 12 agents)

25 of the then-unfinished corpus cases were prepared concurrently by twelve
agents following the existing prepare/receipt conventions; the acceptance
ledger moved from 48 to 78 VERIFIED. Landed VERIFIED: test8,24,29,31,41,45,51,
52,55,56,61,62,64,66,67,72,73,74,81,82,83,85,86. Two cases remain documented
gaps: test36 (universal all-optimizer exclusion is not expressible by the
current caller contract; the probe request is rejected for unknown field
`all_source_optimizer_coordinates_zero`, and a source-feasible positive-terminal
point at objective 6426 rules out unconditional zero-fixing) and test58 (the
joint demand-bounded subflow lemma; the reverse direction is VERIFIED, the naive
forward local merge fails obligation 1372 with capacity 164 versus 82). Both
have BLOCKED receipts plus attempts/ evidence including machine-checked fixtures.

Heaviest completions: test31 (2,781,613 obligations, 36,590,838 work, child RSS
1.42 GB), test72 (RPA 228,760,321 bytes, RPX 196,622,652 bytes, work
156,483,074, preparer RSS 3.37 GB, depths 7/17/22), test74 (RPX 109,356,997
bytes, 4,532 shared AND intervals, depths 9/9), test24 (RPX 109,252,236 bytes).

Independent adversarial review covered the 21 cases completed in this wave:
72/72 recorded negative mutations were reconstructed, assembled and verified to
their exact recorded RPA/RPX hashes and INVALID payloads by an agent other than
the case author; 17 PASS, four P3 metadata-labeling defects (test64, test45,
test73, test85) were fixed with all five artifact hashes byte-identical, and no
P1/P2 finding exists. Report: audit/WAVE_REVIEW_2026-10-11.md.

Resource policy change (owner-approved, policy not semantics): `rpx verify`
gained `--work <u64>` and `--live-facts <usize>`; the default work limit rose
from 100,000,000 to 1,000,000,000; the effective limits are echoed in every
verification JSON result. docs/SEMANTICS_V1.md updated; 213 tests pass (210
existing plus three new CLI-limit tests); binary sha256
694b1083e2f960aa6e9002c0ce20e796b3bcf091a3397810f30aa43f0ec9f655. test72
verifies flag-free under the new default; the explicit 180,000,000 override run
is recorded beside it.

Two capability proposals for the remaining gaps are drafted in
audit/CAPABILITY_PROPOSAL_NOTES.md (caller-bound strict-improvement exclusion;
joint demand-bounded subflow lift). Proposal only: not implemented, not frozen,
no acceptance asserted.

Final acceptance replay: audit/validation/wave-rpx-2026-10-11/run.json — cold
locked build, 213 tests across 26 suites, 78/78 prepared cases replayed
VERIFIED in 204 s wall (88.4 s summed execution). Remaining unfinished at
cutoff: test36 and test58 (documented gaps), test46 (separate pipeline).

## Delivery acceptance and consolidated next draft (2026-10-11)

Root reread the complete goal and independently accepted the submitted wave:
78/78 original requests were regenerated from actual source/target models and
actual RPA; all MCM/RPX hashes and complete non-timing JSON statistics matched.
Receipt: audit/validation/delivery-acceptance-2026-10-11/result.json (176.29s
functional wall time, not an isolated performance comparison). The exact source
checkpoint is audit/checkpoints/delivery-78-working-source, explicitly internal
and unfrozen. The submitted 733MB ledger is preserved as compressed snapshot.

Independent original-report review found two P2 completeness gaps, distinct from
proof unsoundness: test62 lacked caller-bound exclusion of its complete point
image; test83 lacked all-source-optimizer exclusion. The submitted requests were
valid, but full original-contract coverage was 76/81. The original summary and
scope correction are preserved in audit/DELIVERY_ACCEPTANCE.md and
archive/identity evidence linked there. Four earlier P3 metadata repairs cannot
be retroactively called independently byte-identical without before identities.

One unfrozen V10 draft now groups strict improvement, complete-image exclusion
and joint demand-bounded subflow, with separate responsibilities and no V11.
Strict improvement proves same-actual-model feasible decrease on a caller-bound
P>0 domain, using positive constant or predicate-scaled margins. Point exclusion
checks every original/image coordinate and an actual LP bound/row violation.
Subflow appends one simultaneous g with div(g)=b and 0<=g<=min(f,B), after every
old-scope premise. Its real-valued finite path argument and builder remain TCB;
finite oracles and independent reviews are not formal implementation proofs.
Specifications: docs/FORMAT_V10_DRAFT.md and docs/SUBFLOW_DRAFT.md.

Test62 now includes the complete caller-bound image; 6 new attacks reject and
all original MI/bijection blocks, point values and actual MCM bytes are retained.
Test83 now includes all 61 dominated coordinates in an exact strict-improvement
contract and a 65,832-coordinate source tuple; 8 new attacks reject, with minimum
exact saving 161497/1000000. Independent source/support/objective review passes.
Test46 completes both MI directions and reverse LP direction under unchanged
rules. Combined RPA 432,885,912 bytes correctly exceeds 256MiB; three complete
standalone proofs form one explicitly same-model-pair bundle. All 6 attacks reject;
fixed-binary final replays preserve identity before/after every invocation.
Root independently regenerates/replays all five pieces of these three cases in
audit/validation/completed-46-62-83-independent.json. Ledger is now 79/81, with
36 unfinished and new58 awaiting independent scope closure at this cutoff.

The subflow candidate has 983 independent Fraction construction vectors and
14 production tests; its complete core snapshot passed 250 tests. Later strict/
image byte-vector additions include an independently packed 386-byte RPX,
all truncations, downgrade/unknown-version attacks and 5601 illegal-field
checks. Reviews and immutable identities are in audit/STRICT_IMPROVEMENT_REVIEW.md,
audit/CONTRACT_V10_VECTOR_REVIEW.json and audit/SUBFLOW_PRODUCTION_REVIEW.md.
Root also reassembled and replayed all 78 historical requests on fixed V10
binary 5cb441c3b38ab7b3aea01ca880ef720207001cad9e253b5256b714946c9b1c38:
78/78 old RPX bytes and all non-timing statistics unchanged, 153.88s functional
wall, audit/validation/v10-old-78-compatibility.json. New statistical counters
are omitted when zero. No new resource default was raised.

Full original-report scope is now recorded separately in
 audit/contract_scope_gates.json. The bookkeeping loader binds each current
request and artifact, checks all bundled directions, and counts improvement
claims; a successful subrequest cannot automatically close an identified
missing original-report property. Final all-case cold replay and controlled
new-feature/regression performance measurements remain outstanding.

### 2026-10-11 — Complete original contracts, final cold checkpoint

Closed test58 after independent actual-model replay and joint-subflow review.
The test36 canonicalization/minimum and strict-improvement proof passed, but its
first request still omitted the original report's all-optimum retained-coordinate
projection. The independent reviewer constructed a verified small logical
counterexample to treating those subcontracts as that stronger property. This
was a scope omission, not a wrong kernel acceptance; the partial request and
review remain archived.

Added a general original-coordinate affine input halfspace to the same unfrozen
V10 draft, encoded only when previously reserved Claim bit3 is present. Existing
valid bytes remain unchanged. A single complete model copy appends optional
objective-level EQ then halfspace LE; restricted whole-model strictness and
bijection claims reject, as do legacy inverses touching a halfspace. No new
existence lemma is introduced. Independent source/wire review, 7 root semantic
tests and 3 independent wire tests pass; see CONDITIONAL_DOMAIN_REVIEW.md and
CONDITIONAL_WIRE_REVIEW.json.

The final test36 request adds complete Equal/37,616-coordinate projection on
P<=0, adds every reverse coordinate observation, and retains both unconditional
minimum/recovery directions plus strict improvement on P>0. P binds exactly all
200 original continuous terminals. The complete RPX checks 529,636 obligations,
448,596,660 work; 15 negative variants reject. RPA267,140,625 bytes fits the
unchanged256MiB limit. Independent source/report/continuous-control review and
root full recanonicalization/reassembly pass. The original-contract gate is now
closed, with no case-specific production logic or hidden policy increase.

Final ledger: 81/81 VERIFIED, all11 families; no incomplete supplied case remains.
Final cold source checkpoint: audit/checkpoints/v10-complete-source.262 tests
pass; release SHA96a6d3048d1deb6681733ab8b7356875f5e76bd1991c26337fe6820726b9c8f8.
The final replay verifies81 cases in83 complete kernel calls (46 has3 explicit
directions), audit/validation/v10-complete/run.json. All78 historical requests
also reassemble to identical RPX and reproduce every non-timing result under
this final binary. Their source/target models and caller requests are unchanged.

Formal capability baseline:22 loads,264 verification/RSS samples,63 separately
timed synthetic generation/assembly preparations, all passing. Actual58 executes
at median18.369ms; the1024-node/four-group subflow synthetic executes56.732ms but
its complete Python preparation costs9.154s. Preparation is explicitly reported,
not hidden in verification. All task workers held computation for measurements.

The original8+23 fixed A/B matrices retain all712 passing timing/RSS processes
with exact paired artifact/statistics equality. Measured execution medians rise
in19 loads and full-process medians in23; test65 +71.913ms/+4.0%, and test79/71
about+8% execution. These regressions are retained in V10_REGRESSION_REPORT.md.
A bounded alternating-order follow-up on four affected original tasks is being
collected separately to assess order sensitivity; it cannot replace those data.

Final scope, reproduction, trust limitations and evidence index are consolidated
in audit/FINAL_DELIVERY_REPORT.md. Builders remain trusted mathematical inference
code; none of this testing or review is claimed to formally verify their Rust
implementation. V9/V10 protocol status remains explicitly unfrozen.

Final performance follow-up completed once as predeclared:72 timed verifier calls
and8 excluded warmups, all VERIFIED on identical original tasks/artifacts/stats.
Paired execute median deltas(new-old):rational1000 +0.003ms, test65 +82.552ms
(+4.52%), test71 -0.038ms, test79 -0.005ms. The earlier31-load report remains
unchanged. The test65 positive cost remains a disclosed delivery limitation;
wide spreads and order effects prevent a precise causal attribution. No source
change, RSS resampling or repeated attempts to obtain a favorable result followed.
See bench/results/v10-order-sensitivity/ORDER_SENSITIVITY_REPORT.md.

All required functional implementation, actual-case certificates, independent
reviews, cold tests/replay, fixed performance evidence and reproduction material
are now delivered. Final report: audit/FINAL_DELIVERY_REPORT.md. This completion
does not freeze the draft ABI, eliminate the documented TCB, or claim a formal
implementation proof or universal performance guarantee.
