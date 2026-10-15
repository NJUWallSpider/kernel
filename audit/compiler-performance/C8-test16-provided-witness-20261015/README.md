# C8 test16: supplied-witness proof regression

This compares two elaborations of the **same proof supplied by the completed
C8 Agent**. It does not run a fresh Agent, discover a zero closure, choose new
aliases, construct a new target, or invoke a solver. It is not evidence about
nomf quality, reformulation discovery, or new-case generalization.

The original input, target MCM, committed MPS, ordered 25,842 zero witnesses,
20,683 alias witnesses, maps and four MI/LP inverse claims are preserved.
Every claim observes the same 178,164 coordinates. Outputs are written only to
`/Users/bhz/Code/reform_test/runs/compiler-provided-witness-test16-20261015`.
The completed C8 run is read without modification.

Both arms import the immutable generic package snapshot at
`/Users/bhz/Code/reform_test/runs/compiler-package-C9-5c42197-20261015/python`.
The script checks its complete 14-file snapshot manifest and the copied native
binary digest before running. Changes to the working checkout are excluded.

- `baseline` executes `original_author_forward.py`, extracted directly from the
  public Agent tool call. Its repeated `set(zfacts)` assertion remains intact.
- `helpers` consumes the same ordered row/sign/new-coordinate witnesses with
  `Builder.zero_sum`, then calls `rewrite_many` once for the complete explicit
  alias-row batch and checks the exact normalized alias expression.

Both arms preserve the original substitution and reverse bound-obligation
proofs. All 50,186 zero/fixed/alias EQ expressions are individually compared
with their exact expected source-coordinate expression in both MI and LP
claim scopes. Visibility, root scope and input model are checked per fact.
Expression digests are compared across the resulting arm records. The full
Request is compared structurally with the original Request before compilation.
The native verifier checks each resulting RPX, and exact committed-artifact
binding uses the original C8 MPS.

Run **serially**, with no other controlled timed workload:

```sh
PYTHONPATH=/Users/bhz/Code/reform_test/runs/compiler-package-C9-5c42197-20261015/python \
  /Users/bhz/miniforge3/envs/bigdata/bin/python -u benchmark.py --arm baseline
PYTHONPATH=/Users/bhz/Code/reform_test/runs/compiler-package-C9-5c42197-20261015/python \
  /Users/bhz/miniforge3/envs/bigdata/bin/python -u benchmark.py --arm helpers
```

Only one execution per arm is planned. Loading, supplied-witness/map setup,
forward derivation, substitution, exact expression/scope checks, completion,
certificate/Request materialization, serialization/binding/compile, and native
verification are recorded separately. Native subprocess calls are timed within
their parent phase. Thus the encompassing Python compile/binding interval is
not mislabeled as native verification time. A single serial sample cannot
establish a stable speedup or isolate the cost of one particular assertion.

`baseline-result.json` and `helpers-result.json` are compact evidence records;
large generated models, Requests, certificates and RPX files stay in the
external working directory. Preserve a failed execution and its log rather
than rewriting it into a successful result.
