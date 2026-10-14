# Supplied C3 test16 proof performance rescue

This is a deterministic replay of the mathematical choices already supplied by
the failed C3 Agent. It is **not autonomous Agent acceptance**, model discovery,
a fresh quality comparison, or a replay of a historical case preparer. The
original failed run remains failed. Fresh acceptance Agents receive neither
these archived choices nor this script.

[rescue.py](rescue.py) reconstructs the supplied analysis prefix in a separate
workspace, pins the current Python package and release binary, and replaces only
the failed `fill_missing` equality-residual loop with the public
`Builder.substitution(builder, definitions, goals=...)` helper. The selected
source, `modelA`, maps, event equations, pivots, ordering, retained-coordinate
projections, objective equality, MI/LP flags, inverse contracts, and explicit box
proofs are preserved. The base public method is called with the original compact
missing-goal set. At this measured snapshot the `ClaimBuilder` convenience
override still inspected full-plan equality goals; a later checkpoint uses
only compact missing Eq goals. The record pins the actual measured package
hashes. The old slow loop was not executed again. The helper
also elaborates affected model facts from these same supplied equations; no new
equations, pivots, target, or mathematical search are introduced.

[record.json](record.json) reports `VERIFIED_SUPPLIED_PROOF_DIAGNOSTIC`:

| Item | Result |
| --- | --- |
| Preserved exact target | 155,866 variables; 57,537 rows; 243 integer variables; 316,535 nonzeros |
| Verified contracts | Four MI/LP forward/reverse affine inverse claims, objective `Equal`, all 155,866 retained-coordinate projections |
| Kernel obligations | 2,892,181 |
| Kernel work / peak live facts | 36,678,549 / 394,395 |
| Complete observation wall time | 462.68 s, including fresh setup, supplied-prefix reconstruction and artifact hashing |
| Supplied-prefix reconstruction | 243.47 s |
| Four-claim proof authoring | 153.80 s |
| MI / LP forward sparse substitution | 25.94 s / 29.67 s |
| Raw JSON -> RPX compilation phase | 41.59 s, including delivery serialization and exact target binding |
| Kernel verification phase | 4.53 s |
| Sampled worker + native process-tree RSS peak | 5,534,302,208 bytes (5.15 GiB) |
| Python / native-child individual high-water RSS | 3,900,194,816 / 1,289,535,488 bytes |
| Guard | 8 GiB sampled process-tree RSS, 1,500 s total wall; neither reached |
| Certificate / RPX sizes | 181,639,214 / 122,500,613 bytes |

The original C3 authoring cell was interrupted after 858.78 s while handling its
first 61,965 missing equality goals. The rescue discharges that same set and
finishes both MI and LP proofs. These are different-revision observations and
different phase boundaries; they do not establish a controlled speedup ratio or
nomf timing parity. No solver was run. The later supplied dominance targets
`modelB` and `modelC` were reconstructed, but this receipt verifies only the
first exact stage `source -> modelA`.

Heavy artifacts remain under
`/Users/bhz/Code/reform_test/runs/test16-supplied-C3-exact-stage-sparse-rescue-02-20261015`.
The tracked record binds the pristine input, pinned code/binary, archived cells,
source/target MCM, raw certificate, RPX and Request by SHA-256. The supervisor
samples RSS once per second and sums live descendants; shared pages can be
counted twice and this is not an OS-enforced memory limit. Its process-tree peak
must not be confused with the independent per-process high-water counters.

Reproduce with a new workspace and new record path:

```sh
python3 audit/compiler-performance/C3-test16-sparse-rescue/rescue.py \
  --workdir /absolute/path/to/a/fresh/diagnostic-workspace \
  --record /absolute/path/to/a/new-record.json
```

An initial instrumentation attempt failed before reconstruction due to a
duplicate Python event parameter, after 1.08 s. It was corrected before this
fresh observation; [setup-failure.json](setup-failure.json) and
[setup-failure.log](setup-failure.log) preserve that setup failure separately.

The independent [wire-capacity probe](wire-capacity-probe.rs) and
[receipt](wire-capacity.json) also distinguish existing limits. RPX scalars have
1,700-byte (13,600-bit) numerator/denominator capacity, at most 4,095 canonical
decimal digits, covered by the unchanged 4,096-digit proof-input parser.
Kernel-derived intermediates and untrusted Fact metadata use the larger
65,536-bit bound. A supplied 6,001-digit Lin multiplier verifies through the
typed Rust API but is rejected by the frozen RPX encoder, while a 6,001-digit
**derived fact** can arise from small encodable multipliers. No RPX scalar limit
or Certificate scalar profile was widened.
