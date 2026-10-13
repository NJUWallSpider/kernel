# Actual test71: Plotkin cardinality, strict LP strengthening, exact optima

The immutable corpus source has 1,024 binary coordinates, 1,024 packing rows,
and objective `min -sum(x)`. The actual final target adds exactly the row
`sum(x) <= 12`; all original coordinates, domains, rows, and objective remain.
Artifact paths and hashes are recorded in `preparation.json`.

`proof.rpa` requests all of the following together:

- Complete integer identity maps in both directions, with every coordinate
  preserved and both affine inverse identities checked.
- Complete relaxed target-to-source identity containment.
- A feasible source LP point with every coordinate `1/56` that violates the
  actual target row by exactly `44/7`, establishing strict containment.
- A universal source-integer objective lower bound of `-12` and a complete
  feasible source integer point attaining `-12`.
- A universal target-LP objective lower bound of `-12` and a complete feasible
  target LP point attaining `-12`.

The integer bijection and source optimum also imply the target integer optimum
is `-12`. The proof does not claim equality of the LP relaxations.

The generic Plotkin witness assigns distinct 11-bit labels to all binary
coordinates. Every pair at Hamming distance below 6 must be covered by an actual
checked at-most-one packing premise. For any feasible selection of `k` labels,
the sum of pairwise distances is at least `6*k*(k-1)/2`, and at most
`11*k*k/4`: each bit contributes `a*(k-a) <= k*k/4`. Thus `k <= 12`, including
the trivial `k=0` case. The kernel must check labels, binary domains, all clique
premises, and all close-pair coverage; the external geometry file is only an
untrusted witness source.

The independently checked feasible 12-coordinate selection is
`x1,x579,x474,x693,x537,x451,x409,x655,x776,x828,x621,x761`.
`independent_exact_checks.json` records the Python/Fraction cross-check and
explicitly does not substitute for kernel acceptance.

Reproduce from the workspace root with a V3-enabled kernel:

```sh
python3 tools/prepare_test71.py --kernel target/release/rpx
python3 tools/prepare_affine.py --acceptance
```

The preparer also requires rejection of absent clique premises, duplicate
labels, a false strictness witness, a feasible point with the wrong requested
objective, and an omitted universal objective-bound obligation. The latest
actual execution status and exact command results are in `preparation.json`;
generation of the RPA alone is not certification.
