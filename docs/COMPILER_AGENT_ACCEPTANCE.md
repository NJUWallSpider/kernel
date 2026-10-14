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
input and selected committed LP/MPS, anchors each source canonical model to that
original, checks the delivered canonical target against the standard artifact,
and verifies every submitted RPX/request with the copied kernel. Agent-reported
success alone cannot pass. Model-order-independent comparisons use exact named
coefficients and bounds, so a writer that reorders coordinates can still be
audited. Missing or inconsistent artifacts are failures with concrete reasons.

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
