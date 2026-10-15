# C9 test70 supplied-proof regression (prepared, not executed)

This checks a performance fix on the completed Agent's **provided mathematical
proof**. It is not fresh autonomous acceptance, a new reformulation, a solver
comparison, or evidence of Agent wall-time improvement.

The independent C9 quality timing must finish and the root controller must
authorize execution first. Preparation has not imported the compiler package,
invoked native code, run tests, or executed either regression arm. The raw
114 MB Certificate is deliberately left unread until execution. No frozen C9
workspace file is changed.

The separate workspace is
`/Users/bhz/Code/reform_test/runs/compiler-provided-witness-test70-20261015`.
It contains an exact 12-module package snapshot from
`8ebcc97673f752a5be549ade0d6b25c02109929c`, its file hashes, this driver, and
`prepared.json`. It does not contain copies of the large original artifacts.
The original C9 native binary (SHA `5775d6a67b78493ce30a1b6d44b76af7dd264f3cb29371081652e881776839f4`)
is reused read-only and guarded at execution.

## Given witnesses and fixed scope

The original `output/structural_audit.json` saves all 1,202 aggregate groups
with their packing-row names, all 1,679 tightened gates with their controller,
old/new coefficient and full ordered cover members, all 301 zero
reconstructions, all 298 leaf-controller reconstructions, and the two forced
ones. This witness file's SHA is
`909d765a5bddd797027254dbee53347a8ff8d62e7ba62b792de1d8fb0b668e6a`.
The covers have 9,813 groups and refer to 82 named packing rows. The original
public basis-reading loop constructs 173 packing facts from declared source
equalities (unit sum, or one binary-definition equality plus its controller's
upper bound). The driver reproduces only that basis-reading loop. It does not
rerun the Agent's greedy cover construction, duplicate-column classification,
leaf/free-variable analysis, target construction, or any mathematical search.

Both arms load the **actual original source and target MCM files**, reconstruct
the complete original forward/reverse maps from these saved named witnesses,
and require exact equality with the original complete Request. The scope stays:

- integer source -> integer target, objective NonIncreasing;
- integer target -> integer source, objective Equal;
- continuous target -> continuous source, objective Equal;
- 45,017 coordinate observations in each direction, no inverse and no forward
  continuous claim;
- all 522,056 native Return obligations.

`handwritten` reproduces the Agent's final subset-containment parents and
shared dyadic lower sums. `helper` replaces only the construction of the same
requested subset upper Facts with `Builder.subset_bounds`. Both retain the
given aggregate lower proofs, objective proof, all 1,679 gate Cases and all
reverse feasibility proofs. The user-given dyadic lower routine is retained
for aggregate lower bounds in both arms; the helper also owns its separate
scope-safe cancellation cache. No private cache is injected between them.

The exact public proof-cell evidence is
[`C9-test70-public-proof-cells.py`](../../compiler-agent/C9-test70-public-proof-cells.py),
SHA `e69f9c47d6577b654f2955b5ad6b8549f5810e9b31f033e6424c1deab9371482`.
The final manual subset derivation is the public cell SHA
`ff83e058180287c732e466570643ea00266d83a85353b9e75ccb6e0797e82c83`.
The driver adapts its persistent namespace into functions; no public code
containing cover search is executed.

## Execution after authorization

Use two fresh processes, sequentially, with the same interpreter. Do not start
either command during independent solver/quality timing. For example, from
the repository root, with the controller's chosen interpreter:

```sh
python3 audit/compiler-performance/C9-test70-provided-witness-20261015/benchmark.py --arm handwritten --execute
python3 audit/compiler-performance/C9-test70-provided-witness-20261015/benchmark.py --arm helper --execute
```

Each arm refuses to overwrite an existing output directory. The helper arm
requires the completed handwritten `result.json` as its reference. The default
directories are `handwritten/` and `helper/` under the separate workspace.
All generated large model/proof files stay there, outside the Git audit.

The driver checks all 6,887 distinct supplied subset/root Facts for their exact
inequality, kind, visibility and identity of the input root scope. It compares
their canonical expression digest across arms. Each arm independently compiles
and verifies the full proof, requires 522,056 obligations, and performs the
complete native readback audit of the original committed MPS. The serialized
source, target, Request and committed-MPS hashes must equal the original run.
After native verification it reads the original Certificate and compares every
entry of all three original Return maps, including every output coordinate.
No map is merely sampled. Different Lin sharing may change Certificate/RPX
bytes and work statistics; those differences are recorded rather than treated
as mathematical scope changes.

Phase times separate canonical model loading, witness/map reconstruction,
packing/fixed substitution, subset elaboration, remaining aggregate/objective/
case proofs, reverse proofs, completion, serialization/binding and native
verification. Native subprocess walls are recorded under their containing
phase. Initial hash guards and the final full original-map oracle are outside
the measured authoring total; the latter has its own time field. These are
supplied-proof costs, not end-to-end autonomous Agent costs. If peak RSS is
recorded it is the Darwin Python parent's process-lifetime value, including
the post-measurement oracle, not a process-tree peak and never an acceptance
gate.

Both `result.json` files must report `VERIFIED`; until then this preparation
claims no successful replay or speedup. The root controller will copy compact
results into the audit after execution. No further memory-only rounds are
planned.
