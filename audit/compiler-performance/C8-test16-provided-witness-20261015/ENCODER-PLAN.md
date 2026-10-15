# Third arm: encoder regression, prepared but not run

Status: **NOT RUN**. Wait for the controller to provide a tested commit and
immutable package snapshot. Do not use the working checkout. The original
`benchmark.py`, both results and all prior large artifacts remain unchanged.

`encoder_benchmark.py` requires explicit `--package` and full `--checkpoint`
arguments. The package must contain `snapshot.json`; every listed file digest
is checked before import. Native5775d6… is reused from the existing independent
working directory. No new package snapshot is constructed by this script.

The helper-author function, original ordered zero/alias witnesses, maps, target
and four complete MI/LP inverse claims are unchanged. Explicit mappings mean
the unrelated `Proof.correspondence` default-map convenience change is unused.
All previous phase timings, per-EQ expression/scope checks, and process RSS
measurements are retained. Output defaults to the new `encoder` directory; an
existing output directory is rejected so previous evidence is preserved.

After native verification and whole-artifact binding, outside the timed phases,
compare full bytes against old helpers for source MCM, target MCM, certificate
JSON, Request JSON, RPX, and the committed MPS. All must match, and complete
native verifier statistics must match. This guards format/serialization changes
as well as semantic theorem preservation. A mismatch remains a failed regression.

This is a third serial single sample on the same shared host. It cannot show
a stable runtime/memory change, fresh-Agent behavior or held-out generalization.
No test, native process, solver or Agent has been started for this plan.
