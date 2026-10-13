# Actual test63 sparse slack-difference bijection

The complete actual-model certificate is **VERIFIED**. All five targeted mutated
certificates are rejected as **INVALID**. The immutable inputs are
`/Users/bhz/Code/reform_test/runs/test63-nomf-B1/input/model.mps` and its actual final
`output/reformulated.mps`. The latest model/proof/request/kernel hashes and raw
command results are in `preparation.json`.

The source has 1,456 variables and 111 rows. It includes 1,454 binaries partitioned
by 20 assignment equalities, a nonnegative continuous height h, a fixed-zero x2,
and 91 inequalities `A[t]x-h<=0`. The target removes x2, adds 91 nonnegative
continuous slacks, and replaces the inequalities with sparse difference equalities:

```
A[0]x + S[0] - h = 0
(A[t]-A[t-1])x + S[t] - S[t-1] = 0   (t=1,...,90)
```

The forward map is `S[t]=h-A[t]x`, with every retained named coordinate copied.
The reverse map copies retained coordinates and restores x2=0. Summing target
rows through t yields `A[t]x+S[t]-h=0`, proving every original inequality from
S[t]>=0 and determining every slack uniquely. Both directions preserve objective
h+x2=h, including the fixed-zero term.

Four requested claims prove both directions in mixed-integer and LP modes. All
1,455 retained named coordinates and x2=0 are explicit observations. Both pairs
also require full affine inverse compositions for every original and target
coordinate, so the result is a feasible-point bijection in each mode. This uses
the existing affine `inverse` contract; it does not need the separate V7 generic
bijection extension or any new production rule.

The untrusted preparer checks every actual source/target domain, row, objective
and slack difference with Python Fraction. It independently checks all 1,454
interval-supported source columns. Complete indexed structure evidence is in
`independent_structure.json`. Every actual bound, integrality requirement, row,
objective, observation and inverse coordinate remains a terminal kernel obligation.
The kernel does not trust the preparer or the historical corpus audit.

Verification checks 27,006 obligations, charges 997,904 work and peaks at 273 live
facts. RPA is 1,188,224 bytes; RPX is 1,257,380 bytes. The recorded single replay
took 182.941 ms end to end, including 171.304 ms proof execution. These timings
are development observations, not an isolated benchmark or a solver-speed claim.

The five rejection checks reverse a slack's sign, break a middle prefix identity,
change x2=0 to one, omit the last LP inverse obligation, and introduce a nonzero
constant in the objective equality proof. Each is checked against unchanged actual
model files and the full caller request.

The supplemental `audit/slack63_oracle.py` checks 103 complete exact points against
both actual model files: 102 integer assignment points and one fractional point.
It checks both coordinate round trips and objective equality, and verifies that
setting h one half below the true peak creates a negative slack. Point sampling
is additional evidence; universal acceptance comes from the complete RPX proof.

Reproduce from the repository root:

```sh
python3 tools/prepare_test63.py --kernel target/release/rpx
python3 audit/slack63_oracle.py
```
