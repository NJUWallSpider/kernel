# Independent agent acceptance runs

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

Start with affine elimination (`test9`), integer case-based strengthening
(`test86`), and mixed-integer affine/product aliases (`test88`). Add private
one-hot projection (`test13`), interval/menu extensions (`test78`), objective
level restrictions (`test80`), and large staged covering reductions (`test87`)
as the implementation and real feedback support them. These are strata from
the measured demand corpus, not hints supplied to the agents.

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
failed large construction now completes: its four MI/LP affine-bijection claims
certify a target with 143,114 variables and 56,444 rows. Its three-repeat median
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
