# Actual test48 conditional-simplex proof

The immutable source is `input/model.mps` and the final target is
`output/reformulated.mps` under `/Users/bhz/Code/reform_test/runs/test48-nomf-B1`.
The files and their recorded identities, not historical solver or audit results,
are the verification inputs. `preparation.json` records the latest actual status;
proof generation alone is not certification.

The completed run is **VERIFIED**, with all five mutations rejected as **INVALID**.
The release kernel checked 26,660 terminal obligations and 20,325 local branches,
charging 5,865,336 work units. The RPX certificate is 15,369,641 bytes. The recorded
run took 436.525 ms including input and proof decoding, with 376.424 ms in proof
execution; this is a single replay observation, not an isolated benchmark.
`preparation.json` binds these results to the exact model, request, proof and
kernel-binary hashes and records each rejection reason.

Four requested directions match the original report's commitment:

- Mixed-integer forward map with equal objective.
- Mixed-integer reverse construction with nonincreasing objective.
- Both relaxed directions with equal objective and both full affine inverse identities.

Every direction explicitly preserves all 150 selector observations: 144 retained
coordinates and six eliminated selectors observed as zero. The mixed-integer
claims preserve selector feasibility and optimal value. They do not assert that
all fractional child tuples or nonoptimal objective levels survive reconstruction.
No global feasibility or numeric optimum is claimed.

The preparer checks the real alias equalities and exact fixed-zero consequences.
It maps every original coordinate, including both free coordinates using their
complete actual defining equations. In the mixed-integer reverse direction,
1,357 real intervals choose priority children jointly. Their bounds encode the
AND of residual capacity, eligibility and the absence of earlier eligible choices.
The 475 blocks are sorted by actual exact objective coefficient, not by audit
array order. Ordinary binary Cases prove every choice integer, every packing
inequality and each block's nonincreasing cost. All original variable bounds,
integer requirements, rows and the complete objective remain terminal kernel
obligations. No new production rule or instance-specific trusted theorem is used.

The independent full-model structural audit is
`audit/normalization_47_48_inventory.json`; it is preparation evidence, not an
acceptance authority. `tools/prepare_test48.py` independently checks each generated
linear expression and Cases leaf with Python Fraction before emitting RPA 5.

Reproduce all preparation, actual canonicalization, assembly, verification and
five targeted rejection tests from the repository root:

```sh
python3 tools/prepare_test48.py --kernel target/release/rpx
```

The rejection tests remove an interval compatibility reference, supply a continuous
integrality witness, return an unrounded fractional child, reverse an objective
multiplier and change a removed zero selector. Each must return INVALID against
the unchanged complete request and actual model inputs.
