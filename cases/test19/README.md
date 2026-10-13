# test19: complete integer bijection and strict LP projection

The actual source has 1,462 variables and 1,655 rows. The actual final MPS has
1,459 variables and 1,668 rows. All source/target identities, exact command outputs,
and proof/request hashes are in `preparation.json`; the corpus is read only.

The RPA6 certificate proves the objective-preserving integer affine bijection in
both directions, including every retained coordinate and both inverse identities.
It reconstructs the three eliminated free objective auxiliaries by their actual
defining equalities. For the source-to-target direction it proves every tightened
row: 28 production activation bounds and 182 resource bounds use integer case
splits, while 16 cycle inequalities use exact telescoping and integer rounding.
The reverse LP inclusion checks the complete original model without integrality.

The complete rational source LP witness is checked against every original bound
and row. Its projected point violates 226 actual target rows. The kernel's strict
fiber claim uses all 1,459 coordinate observations and derives the positive
constant 673/900 from target row CYC0001 and the generated fiber equalities.
Original and projected objectives agree at this point. No optimum or improvement
in the LP objective bound is claimed.

The independent preparer checks the full actual row edits, variable domains,
objective substitution, complete witness feasibility and its target violations
using Python Fraction. These checks are untrusted preparation evidence; only the
separate Rust verifier determines acceptance. Five mutated certificates are
rejected: a continuous split premise, a missing valid rounding premise, a wrong
auxiliary reconstruction, an infeasible source witness, and a canceled fiber
contradiction.

Reproduce from the workspace with:

```
python3 tools/prepare_test19.py --kernel target/debug/rpx
python3 tools/prepare_affine.py --acceptance
```

The first executed receipt uses the preserved original V6 executable. It checks
19,331 terminal obligations, 210 Cases and 16 Round instructions.
