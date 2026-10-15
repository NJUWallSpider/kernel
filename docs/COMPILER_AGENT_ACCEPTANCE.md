# Independent agent acceptance runs

Final cutoff: C10 formal and bounded solver reviews are complete. C6 solver
quality remains unmeasured. C5–C10 contains 37 formally accepted Compiler runs,
37 fresh nomf controls and 16 distinct previously tested inputs; early failures
remain part of the project record. Work stopped after the last authorized C10
round and documentation. Earlier sections retain their round-specific cutoffs.

`tools/run_compiler_agents.py` launches fresh `omp` agents on previously tested
MPS cases from `~/Code/reform_test/data`. It gives the compiler arm only the
original input, a snapshot of the generic Python API/native kernel, and generic
API documentation. It never copies old reports, reformulations, audits,
case-specific preparers, or certificates into the agent workspace.

The matched `nomf` arm uses the original `NO_MIPFRAME.md` protocol. Both arms use
the same interpreter, model (`gpt-6.1-sol`), thinking (`high`), tool selection
(`eval,read`), and 30 minute limit as the existing baseline. The compiler arm
adds proof expression and kernel verification; its protocol explicitly retains
the original reformulation objective and records unsupported ambitious targets.
The executable, protocol, compiler source, model inputs, invocation and session
are retained with hashes for each run. A fresh model catalog lookup is not proof
that an authenticated model call will succeed; launch failures are recorded.

The initial coverage plan used affine elimination (`test9`), integer case-based
strengthening (`test86`), and mixed-integer affine/product aliases (`test88`),
with constructive scopes and larger cases added as real feedback supported
them. These are strata from the measured demand corpus, not hints supplied to
the agents. The commands below illustrate the harness; they are not a plan to
launch additional rounds after C10.

```sh
python3 tools/run_compiler_agents.py --cases test9,test86,test88 --prepare-only
python3 tools/run_compiler_agents.py --cases test9,test86,test88 --arms compiler,nomf --jobs 2
```

Each invocation creates only new directories under `reform_test/runs` and
refuses to reuse a pre-existing batch or workspace. Agents may read only their
own workspace by protocol. This is the same instruction boundary as the nomf
baseline, not an operating-system filesystem sandbox. A transcript audit marks
explicit attempts to read old outputs or paths outside the workspace.

After each agent finishes, the harness independently canonicalizes the original
input and selected committed LP/MPS. Before reading either model, it checks the
input against its trusted pristine digest captured outside the agent workspace
and retained in process memory before launch. It anchors each source canonical model to that
original, checks the delivered canonical target against the standard artifact,
and verifies every submitted RPX/request with the copied kernel. Agent-reported
success alone cannot pass. Model-order-independent comparisons use exact named
coefficients and bounds, so a writer that reorders coordinates can still be
audited. Missing or inconsistent artifacts are failures with concrete reasons.

New harness versions also recognize explicit `composition.ordered_chain=true`
deliveries. They verify each stage against its own canonical source/target,
require exact named formulation joins, and anchor only the first and last
endpoints to the pristine input and committed solver artifact. When
`composition.claim_paths` is present, every path is independently checked and
only its selected maps are composed. Restrictions remain stage-local;
`None` does not imply objective preservation, and individual inverse requests
do not imply an inverse for the whole chain. The report retains the selected
claim paths and named observation relations. Legacy manually assembled chains
without `claim_paths` use an explicitly labeled conservative selection rule.
The evaluator sources are snapshotted outside the agent workspace before launch.

These checks describe the mature harness. Earlier versions had different
source-order and chain-entry checks. Historical claims use each retained
version's records: the C1–C3 pristine-input revalidation is retrospective, and
C4's original chain rejection remains a failure of that entry point. Current
checks are not retroactively attributed to the original earlier launches.

`assessment.json` records source and target dimensions, integer counts,
nonzeros, complete request claim descriptors, kernel results, transcript metrics,
and final feedback. `comparison.json` pairs fresh compiler/nomf measurements and
provides separately labeled historical baseline metadata. It does not treat
certificate replay, model size alone, or a single accepted directional claim as
equivalent to the requested acceptance goal. Reformulation quality and precise
claim coverage must be assessed together with time and any proof-expression
limitation; stronger targets that cannot yet be certified remain visible.

No solver runs during agent analysis. Optional independent post-run solver
evaluation belongs after the final commit, outside the agent workspace, with
matched host/load/settings if runtime comparisons are needed.

## Measured status after C1 and C2

The two batches produced six fresh compiler runs and six fresh matched nomf
controls across five previously tested cases. All six compiler requests were
independently **VERIFIED**, with original-input anchoring and exact committed
artifact comparison. Running each agent's own proof-construction script in a
separate fresh workspace reproduced its source MCM, target MCM, RPX, request,
and standard model byte for byte. This establishes delivered proof correctness
and reproducibility; **the model-quality and near-nomf time goal is not yet met**.

The [C1 summary](../audit/compiler-agent/C1-summary.json) records agent wall
ratios of 1.35–1.99. Its test9 target has a slightly stronger LP bound but a
2.10 times slower matched three-run median MIP solve; its test88 target has a
weaker time-limited dual bound than nomf. The [C2 summary](../audit/compiler-agent/C2-summary.json)
records improved agent time ratios for test13 (1.27) and test84 (0.96), with
successful constructive MenuLift and parity proofs. Its remaining concrete
failure is test88: the compiler target's LP objective is 27 versus nomf's 227;
nomf solves to its configured MIP tolerance in about 44 seconds while the
compiler target reaches the 120-second limit. These are post-commit numerical
quality measurements, separate from the formal equivalence claims.

Iteration continues on generic proof ergonomics and measured quality/time.
Fresh runs receive no previous case reports, reformulations, certificates,
discovered cuts, or case-specific solver feedback. Compact summaries retain
the declared claim scopes, artifact hashes, measurement settings and raw-result links;
large transcripts remain in their isolated external run directories.

## C3: stronger small targets and a large proof-construction failure

The [C3 summary](../audit/compiler-agent/C3-summary.json) records fresh paired
runs on test9, test16, and test88 from checkpoint `354ef66`. Test9 and test88
were independently **VERIFIED**, and their own Python construction scripts
reproduced all five artifacts byte for byte. Test9's compiler target has a
stronger LP bound and a three-run MIP median of 18.13 seconds versus nomf's
20.44 seconds. Test88's compiler target reaches a time-limited dual bound of
224 versus fresh nomf's 127, with incumbent 230 in both. Its LP bound remains
27, so the earlier C2 nomf LP227 opportunity remains unresolved.

Test16 is a real failure: the compiler agent reached its 30-minute limit inside
its first certificate-construction cell and saved no committed target or proof.
It had selected an ambitious target with 154,517 variables, compared with
nomf's delivered 177,881, but dimensions do not establish either correctness or
quality. The [preserved failure](../audit/compiler-agent/C3-test16-failure/failure.json)
includes the exact cell, preceding mathematical recipe, deadline, and observed
memory use for diagnosis. Repeated immutable-expression subtraction while
filling the wide objective is a performance suspect, not an established cause.

Full final agent wall ratios are 1.99 for test9, 1.91 for the failed test16 run,
and 1.66 for test88. Test9 had verified the exact final artifacts at 427 seconds,
before nomf finished at 484 seconds, but then spent another 537 seconds on
audit, replay, numeric inspection, and reports; the acceptance measurement
counts all of that time. **C3 does not meet the complete acceptance goal.**
Generic iteration addresses sparse proof construction and avoids forcing agents
to rewrite the API's valid absolute delivery paths. Fresh subsequent agents
receive no preserved mathematical recipe or previous solver feedback.

## C4: large proof delivered, ordered-chain limitation isolated

The [C4 summary](../audit/compiler-agent/C4-summary.json) records fresh paired
runs on test9, test16, and test88 from checkpoint `418bab7`. Test9 and test16
passed the original independent harness. Test88 delivered three verified RPX
stages, but the original harness rejected the intermediate first target because
it expected every piece to connect the original input directly to the final
artifact. That strict failure remains unchanged. A separate versioned
[ordered-chain review](../audit/compiler-agent/C4-test88-staged-review-v1/staged-review.json)
independently verifies all stages, exact named joins, pristine first endpoint,
and committed last endpoint. It establishes unrestricted MI forward
NonIncreasing/reverse Equal maps preserving 176 named observations. It derives
neither a full-model bijection nor a composite LP correspondence. The original
reviewer and imported comparison source are retained with matching hashes;
later generic chain-writer improvements are not credited to this run.

All three agents' own construction scripts reproduced their standard models,
Requests and RPX files byte for byte in fresh workspaces. Test16's previously
failed large construction now completes: four MI/LP Equal direction claims
check inverse compositions on 143,114 retained observations, for a target
with 143,114 variables and 56,444 rows; no full-model Bijection is requested.
Its three-repeat median
MIP solve is 26.62 seconds versus nomf's 30.16 seconds; all LP objectives match.
Nomf's 91 additionally removed integer coordinates are zero by real-valid
homogeneous witnesses, so its smaller integer count does not imply an
integer-only strengthening. Different MIP incumbents fall within the recorded
0.01% termination tolerance and are not exact-optimum equality evidence.

Test88's compiler target solves to objective and dual bound 230 in 18.68 seconds;
fresh nomf reaches 120 seconds with incumbent 230 and dual bound 32.40. All LP
bounds remain 27, leaving the earlier C2 nomf LP227 opportunity unresolved.
Test9's matched three-repeat MIP median remains about 2.02 times slower than
nomf, with equal LP bounds. Full Agent wall ratios are 1.25, 2.29 and 1.95.
The [phase record](../audit/compiler-agent/C4-phase-diagnostics.json) shows another
269 seconds after first verification for test16 and 381 seconds for test88,
mostly model time for audit/report and manual staged delivery. This cannot be
attributed solely to native compilation. **C4 still does not meet the complete
quality-and-near-nomf-time acceptance goal.**

## C5: six formally verified constructions, remaining time and quality losses

The [C5 summary](../audit/compiler-agent/C5-summary.json) records six fresh
compiler/nomf pairs from checkpoint `aa90b09`: test9, test16, test88, test58,
test63, and test51. All six compiler deliveries passed the independent harness,
including explicit ordered claim paths. Actual endpoints all have MCM magic;
the [parser records](../audit/compiler-agent/C5-parser-binding) found no
same-SHA cross-reader-family use of the later-discovered library defect.
The evaluator verified every stage separately. Fresh agents received no prior
solutions, mathematical witnesses, solver feedback, or performance reports.

The [serial post-commit quality record](../audit/compiler-agent/C5-quality/quality.json)
shows that test88 now reaches LP bound **227**, versus 27 for source and fresh
nomf, and solves to objective/dual bound 230 in 14.51 seconds while both controls
reach 120 seconds. Thus the earlier missed LP227 opportunity was independently
recovered with complete MI certification. Test9 retains integer capacity cuts:
its three-run MIP median is 15.14 seconds versus nomf's 13.57 seconds, with a
0.203 higher LP bound. Test51 has a stronger LP bound and a 0.166-second MIP
median versus nomf's 0.445 seconds. Test63 independently expresses a sparse
extension with 91 unique slacks and MI/LP inverse-linked direction claims at
the declared observations; its LP and
time-limited MIP results match fresh nomf.

There are material failures against the overall goal. Test16's single bounded
MIP measurement is 95.07 seconds versus nomf's 30.77 seconds, with equal LP
bounds. Test58 uses SignedLift and IntervalLift to deliver the same LP bound
as nomf, but both reformulations reach 120 seconds while the pristine source
solves in 10.35 seconds. Both test63 reformulations also have worse
time-limited incumbent/bound evidence than the pristine source. Agent wall
ratios for test9/16/88/58/63/51 are **1.496/3.106/2.214/1.340/0.924/1.786**.
The [phase record](../audit/compiler-agent/C5-phase-diagnostics.json) retains
119–332 seconds after first observed verification for scope and remaining-hypothesis
checks, reporting, author-program preservation, and audit work. Observed transform choices and corrected proof
errors do not establish that agents retreated because of an expression limit;
these timing and numerical quality losses still count against acceptance.

Independent author-program replays verify all six constructions. Test9, test16,
test63, and test51 reproduce every checked artifact byte for byte. Test58
reproduces all models, Requests and final MPS, but one RPX differs in author-step
order while still verifying the same theorem with identical native statistics;
the [difference record](../audit/compiler-agent/C5-proof-reproduction/test58-proof-difference.json)
preserves both hashes. Test88's empty-output replay first fails because its
script reads the saved target MCM as an expected-model comparison. A separate
replay explicitly retains that reference, regenerates all outputs, and verifies
with byte-identical artifacts; the initial failure remains preserved. These
are distinct reproducibility outcomes. **C5 does not establish the complete
quality-and-near-nomf-time acceptance goal.**


## Prompt-only follow-up controls

The [C6 public-event diagnosis](../audit/compiler-agent/C6-phase-diagnostics.json)
contains completed paired runs for test9 and test16; it is not a final C6
quality result. Test16 has four independently accepted MI/LP inverse-linked
claims. Its first complete final-artifact verification is at 508.17 seconds,
while the Agent ends at 704.36 seconds. The subsequent 196.18 seconds include
saving authoring code, scope checks and reporting. These visible intentions
support a packaging-cost hypothesis; they do not assign every second to the
prompt or prove a causal improvement.

Inspection found that the compiler protocol concatenates the shared nomf
instructions with a second complete analysis/report workflow. The C6 compiler
prompt is 14,422 bytes, compared with the 5,970-byte nomf protocol. The added
workflow also requires a standalone proof-construction program, whereas nomf
explicitly encourages persistent interactive work. That requirement is an
extra delivery burden, separate from constructing and verifying the proof.

The revised supplement keeps the shared mathematical task once and adds only
compiler-specific contract, verification and delivery instructions. Independent
source anchoring, complete target/artifact binding, every submitted Request,
ordered claim-path checks and failure transparency remain required. A separate
authoring script is optional; the actual Python construction calls, canonical
models, RPX, Request and successful receipt remain preserved. Serialized-proof
replay is not a substitute for fresh autonomous proof construction.

The [C7 controls](../audit/compiler-agent/C7-prompt-controls.json) fix the
compiler package and API at the same `231e6f4` snapshot as C6, with the same
kernel, model, budgets, six cases and fresh nomf controls. The new package/path
selection flags allow this prompt experiment to exclude ongoing library
changes. Compare actual reformulations, claim scopes, quality, full wall time
and work after verification together; shorter time from a weaker target is
not a successful result. Launch and outcome are recorded separately.

## C6–C8: completed prompt controls and mixed mathematical outcomes

The [C6 formal summary](../audit/compiler-agent/C6-summary.json) records six
independently accepted Compiler deliveries, including SignedLift with two
MenuLift scopes on test58 and MI/LP inverse pairs at the declared observations
on test16 and test63. These inverse links are not full-model Bijection claims.
It contains no solver evaluation. That missing C6 quality measurement prevents
an old-prompt/new-prompt quality attribution.

The [C7 summary](../audit/compiler-agent/C7-summary.json) and
[C8 summary](../audit/compiler-agent/C8-summary.json) each record six accepted
Compiler deliveries and six fresh nomf controls. C6, C7 and C8 use the same
`231e6f4` package/API and native binary; the prompt supplements change. Their
mathematical targets and contract scopes also change, so the experiment does
not isolate a causal prompt effect at equal reformulation quality.

| Round | Compiler total Agent wall s | nomf total Agent wall s | Ratio of totals | Median paired ratio |
|---|---:|---:|---:|---:|
| C5 | 4582.558 | 2516.589 | 1.821 | 1.641 |
| C6 | 3141.919 | 2427.598 | 1.294 | 1.205 |
| C7 | 2106.979 | 2391.847 | 0.881 | 0.859 |
| C8 | 2163.575 | 2296.619 | 0.942 | 0.898 |

These are complete-round sums, not parallel batch makespan or a selection of
the fastest case from each round. Work after first complete verification has
total/median 974.259/147.239 s in C6, 490.456/83.210 s in C7 and
487.852/81.425 s in C8. Different targets, spontaneous mathematical choices
and reporting work remain material. C7 test16 still spends 200.008 s in a
self-authored repeated-set construction, despite the frozen API guide already
advising membership-set reuse. The public phase records preserve this failure.

The [C7 quality review](../audit/compiler-agent/C7-quality-review.json) and
[C8 quality review](../audit/compiler-agent/C8-quality-review.json) are separate
post-run, solver-blind measurements. Positive C8 evidence includes test51's
22 additional convex-pair dominance fixings and MI inverse checks on 137
retained observations plus
reverse-LP proof: MIP medians are 0.452504/0.707976 s for Compiler/nomf,
with objective/dual −3, while the Compiler LP objective is −3.9755418241
versus −4.9592575252. The absolute MIP difference is only 0.255472 s.
The manual point smoke check is outside the actual Request, whose points
array is empty.

Material exploration differences remain. C8 test58 retains bridge
canonicalization and integer rounding but omits nomf's signed-flow/path
contraction. Its one bounded MIP solve is better (9.696697 s at 754 versus
nomf's 120 s limit with incumbent 763/dual 653), but that does not establish
equal exploration ambition. C8 test63 uses 90 continuous slacks and MI/LP
inverse pairs at the declared observations, whereas nomf adds 91 slacks, deletes a fixed coordinate, and
proves an extra integer window bound. All LP objectives are 51.59; the
time-limited source/Compiler/nomf incumbents are 54/55.999999/56.999999.
Equal numerical objectives do not establish equal relaxation sets or excuse
missing mathematical candidates. Overall acceptance remains false.

## C9: eight different previously tested cases, complete formal delivery

The frozen [C9 formal summary](../audit/compiler-agent/C9-summary.json) records
eight new pairs on test28, test38, test60, test62, test70, test80, test65 and
test85. All sixteen Agents exit normally without harness errors, and all eight
Compiler deliveries pass native verification, pristine anchoring and complete
committed-artifact matching. C9 uses package `539c146`; the later
`subset_bounds` helper is excluded from its frozen inputs. The summary retains
its original pre-quality cutoff and exact bytes. Completed quality is recorded
separately in the [final review](../audit/compiler-agent/C9-quality-review.json)
and [small-record manifest](../audit/compiler-agent/C9-quality-raw-sha256.json).

The actual scopes include constructive MenuLift reconstruction of 13,550
one-hot variables on test60; test62's two-stage MI chain with 2,029 reverse
IntervalLift variables and 30,888 case branches; and test80's one-coordinate
objective-image formulation with full MI/LP maps. These differ from a theorem
that preserves every original coordinate or proves a full-model bijection.
Test85 naturally uses `zero_sum` and batched `rewrite_many` on its supplied
zero/alias witnesses. Every scope is described by the actual Request rather
than inferred from model dimensions.

Compiler/nomf Agent totals are 3435.519/3023.927 s (ratio 1.136; median paired
ratio 1.118). Test70 costs 858.989/350.247 s: its initial 639,796,634-byte
certificate hits the old input cap, then the Agent preserves its target/maps
and three claims while hand-sharing the supplied subset proof down to
114,694,805 bytes. The final native verifier takes 3.551523 s; this is not
evidence that native verification consumed the whole delay. Later generic
helper and budget changes are separate supplied-witness/test evidence.

Quality is mixed. Test38 has stronger measured LP objective
96.677882487 versus nomf's 82.619689331 and single MIP observations
53.688467/62.735951 s, both reporting Optimal at 204.081749241. Its
additional proportional-sharing candidate still has 197 unproved
reconstruction bounds; a failed box sufficient condition is not mathematical
impossibility. Test70's stronger LP bound does not establish MIP efficiency:
all three variants time out in presolve without incumbents. Test85's Compiler
LP median is 20.396031 s versus nomf's 12.941298 s. The full review preserves
no-incumbent and partial-LP outcomes rather than treating them as optima.

C5–C9 is a continuous mature-stage cohort of **32/32 formally accepted
Compiler runs, 32 fresh matched nomf controls and 14 distinct cases**. It is
not the whole project's success rate, not 32 independent cases, and not a
proof of unseen-case generalization. Early C1–C4 failures remain above.
The joint near-nomf time, mathematical ambition and model-quality acceptance
criterion is still unmet.

## Final C10 results and stop

C10 was the last authorized fresh batch, on test70, test38, test58, test55 and
test69, with source `9822358` and native `cf9941c2…`. Its frozen generic package
includes `subset_bounds` and the Certificate-JSON-only compile budget; later
documentation was not part of those Agent inputs. All ten arms ended normally;
5/5 Compiler deliveries and six proof pieces passed independent native
verification, pristine-input anchoring and complete committed-model readback.
The historical [formal cutoff](../audit/compiler-agent/C10-formal-summary.json)
remains unchanged; the [final results](../audit/compiler-agent/C10-results.json)
add the completed quality review and phase/pair records.

| Case | Compiler / nomf Agent wall s | Actual expression |
|---|---:|---|
| test70 | 547.476 / 647.851 | 7029 subset facts from 82 author-selected premises; MI NI/Equal, 48096 observations |
| test38 | 659.548 / 555.455 | Two stages, final MI Equal both ways plus reverse LP, 3250 observations; no inherited global inverse |
| test58 | 551.340 / 383.939 | Two Menu lifts and 305 Signed witnesses; MI NI/Equal, 625 affine netflow observations |
| test55 | 302.993 / 625.990 | New case: projection of 1024 auxiliaries, 512 requested subset bounds; MI Equal both ways plus reverse LP |
| test69 | 469.392 / 374.934 | New case: 1499 exact eliminations and 1500 integer cuts; MI observed-coordinate inverse pair plus reverse LP |

Totals are **2530.749/2588.169 s**, ratio **0.977814**; median paired ratio is
**1.187401**, with Compiler faster on **2/5** cases. The total alone does not
establish equal per-case time or quality. Test58 corrected three proof-input
errors while preserving the original 610-variable target and all observations;
the complex reconstruction was not abandoned.

Serial HiGHS 1.15.1 quality measurements use one thread, parallel off, seed 0,
120 s, with MIP n=1 and LP n=3 per variant under the fixed repeat policy.
Compiler/nomf LP objectives are respectively: test70 997784.95132/991730.67069;
test38 82.619689331/82.303925238; test58 237.98780488/40.426829268;
test55 3378.0041667/3975.4029888; test69 250/250. These numerical comparisons
do not prove LP polyhedral inclusion. All MIPs reach the time limit except
the source test58 and both reformulations of test38, which report Optimal
under solver tolerances. Test70 has no source/Compiler incumbent while nomf
has one. Test55's Compiler has a better incumbent but a worse dual bound than
nomf; test69's Compiler has a better incumbent and the same dual bound.
Both test58 reformulations solve worse than its source in this measurement.

Test70 explicitly cites extra reconstruction/fiber-contract work when deciding
not to aggregate, whereas nomf aggregates. Test55's nomf also performs stronger
common-gate capacity aggregation. These are material feedback on the requested
no-sacrifice criterion, not proof that the API cannot express those operations.
The overall near-nomf ambition/quality/time goal is **not established**.
The [paper preparation report](PROJECT_RESULTS_FOR_PAPER.md) records the positive
project results and limitations. No C11 or further implementation loop follows.
