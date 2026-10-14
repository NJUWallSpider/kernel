# Final commitment: exact equality/zero reduction

Committed formulation: `output/model.mps`. Original: `input/model.mps`, preserved.
No solver, presolver, LP relaxation, feasibility oracle, optimization routine,
Internet access, or solver-performance feedback was used.

## 1. Important structural facts

| Quantity | Original | Committed |
|---|---:|---:|
| Variables | 228,350 | 178,165 |
| Integer variables, including binaries | 334 | 152 |
| Constraints, excluding the objective row | 126,512 | 79,835 |
| Equality constraints | 122,128 | 75,694 |
| <= constraints | 2,414 | 2,171 |
| >= constraints | 1,970 | 1,970 |
| Constraint nonzeros | 463,941 | 362,582 |
| Nonzero objective coefficients | 215,696 | 171,300 |

Every variable has a nonnegative lower bound. The original contains 167 binary
variables and 167 other integer variables. Every nonzero objective coefficient
is positive; positivity is NOT used to justify any elimination.

There are 21,937 original singleton equalities: 21,921 have coefficient +1,
16 have coefficient -1, and all have RHS zero. There are 21,334 original
homogeneous two-variable equalities with exactly opposite coefficients.
These full-scope counts, not names or samples, motivated the reduction.

The original row-variable incidence graph has exactly two connected components:
one contains 228,349 variables and all 334 integer variables; the other is the
isolated variable `ID354863`, fixed to 1 with objective coefficient 103901250.
This rejects substantive decomposition of the original model by disconnected
constraint incidence. It does not reject other possible algebraic decompositions.

## 2. MPS interpretation and reliability

The entire file was parsed, not a sample. Its section sequence is exactly
NAME, ROWS, COLUMNS, RHS, BOUNDS, ENDATA. There are no RANGES, OBJSENSE,
OBJNAME, or additional extension sections. The one N row is `OBJ`; there is
one RHS vector, `RHS1`, and one bound vector, `BND1`. In the absence of an
OBJSENSE declaration, the usual MPS default minimization convention is retained.

Rows L/G/E mean <=/>=/=. Missing RHS entries are exactly zero. Missing lower
bounds mean zero; continuous variables with no upper bound are unbounded above.
All 94 INTORG/INTEND marker events were processed and their balanced state
checked. All 334 marker-declared integer variables have explicit bound records,
so no conclusion depends on an ambiguous implicit upper bound for an integer.
The original bound records consist of 114,018 UP, 167 BV, and one FX. BV means
integer with bounds [0,1]; FX sets both bounds. The fixed objective-only variable
remains explicit, so the committed MPS needs no objective-offset convention.

All encoded decimal and exponent coefficients were interpreted as exact
Fractions, including long decimal spellings that are close to short decimals
but not equal to them. Repeated matrix entries would be summed. Both legal
one-pair and two-pair COLUMNS/RHS records are handled; row references, bound
references, vector uniqueness, and marker states are checked. No coefficient
rounding was performed. Row names and variable names supplied identifiers,
not application semantics.

## 3. Hypotheses and tests

* **Forced-zero structure:** exhaustively inspected homogeneous rows after
  successive exact substitutions. For E rows with all coefficients strictly
  positive or all strictly negative, nonnegativity forces every participating
  variable to zero. The same applies to L rows with positive coefficients or
  G rows with negative coefficients. Singleton zero equalities are included.
  Every operation has an ordered exact row witness.
* **Variable identification:** exhaustively inspected homogeneous E rows after
  substitution and aggregation. Exactly two nonzero opposite coefficients
  imply equality of the two participating variables. Their bounds are
  intersected and their objective coefficients added. Every identification
  has an ordered exact row witness.
* **Joint closure:** both operations were applied until no applicable row
  remained. Zero substitutions can expose new identities; identities can
  expose new zero-forcing rows. The closure produced 24,041 zero-witness steps
  and 22,484 identification steps. Some identified classes were subsequently
  forced to zero; these step counts are not disjoint original-variable counts.
* **Proportional duplicate rows:** canonicalized every original row using an
  exact nonzero coefficient as scale, sorted complete supports, scaled RHS,
  and reversed L/G for negative scale. No duplicate signature occurred.
  This rejects exact proportional-row duplication, not general linear dependence.
* **Bound-only row redundancy:** for every row remaining after closure,
  computed the complete exact minimum/maximum over the inherited variable
  box, including infinite endpoints. Found and removed 61 redundant L rows.
  Example: `ID346789` becomes `-ID346788 <= 1700`, with
  `0 <= ID346788 <= 850`, hence its maximum LHS is 0.
* **Disconnected decomposition:** exhaustively built the original incidence
  components described above; no substantive original disconnected block found.

## 4. Rejected, inconclusive, and deliberately unclaimed possibilities

No exact proportional duplicate rows were found. No substantive disconnected
original constraint block was found. The exhaustive bound-interval scan found
no contradiction, but this is NOT a feasibility proof.

No claim is made about optimality, feasibility, general row rank, objective-based
fixing, general affine elimination, stronger inequalities, or solver speed.
The committed scope deliberately does not eliminate the 227 remaining
nonzero-RHS singleton equalities, nor other general affine relationships.
Their presence does not affect correctness of this reduction. The analysis
is not a certificate that no further simplification exists.

## 5. Claims supporting the commitment and their evidence

1. **Each zero substitution is forced at every original feasible point.**
   Ordered proof replay starts from the ORIGINAL matrix. At each step it
   reconstructs the cited row under all preceding proved substitutions,
   compares its complete exact terms to the witness, checks its sense and
   zero RHS, and checks nonnegative variable domains. A zero sum of strictly
   same-sign terms in nonnegative variables forces every term variable to zero;
   the stated one-sided inequalities have the same implication.
2. **Each identification is valid at every original feasible point.**
   Replay checks an E row with zero RHS and exactly two nonzero coefficients
   a and -a, so a(x-y)=0 implies x=y. It checks both names are current roots.
3. **Reduced domains preserve every original bound and integrality condition.**
   For every surviving class, the lower bound is the maximum original lower
   bound, the upper bound is the minimum finite original upper bound, and
   integrality is required if any member was integer. Independently rebuilt
   domains are compared exactly to the emitted artifact. All eliminated
   integer variables are fixed to zero; no nonzero integer is merged away.
4. **The complete objective is unchanged under reconstruction.**
   Zero variables contribute exactly zero; each surviving coefficient is the
   exact sum over its original class. The fixed objective contribution
   103901250 is preserved by retaining `ID354863=1`. All emitted coefficients
   were independently compared to these class sums.
5. **Removed rows add no restriction after the justified substitutions.**
   Every one of the 46,616 closure-removed rows independently rebuilds to a
   true constant constraint. The other 61 rows satisfy their original RHS and
   sense over their complete inherited bound box; exact interval witnesses
   are supplied and checked.
6. **Every retained row is the actual substituted original row.**
   Every original row was rebuilt independently from the final map, summing
   all coincident coefficients and deleting only exact zeros. All 79,835
   emitted rows match the rebuilt coefficients, original sense, and original
   RHS exactly. No RHS modification is needed because only zero-valued
   variables were substituted away.

Consequently projection to surviving root coordinates and reconstruction via
`audit.json` are inverse maps between the original and committed feasible sets,
with exactly equal objective values. This is feasible-set equivalence with a
specified reconstruction, not merely preservation of an optimum.

## 6. Final reformulation and exact scope

The single committed change combines the witnessed zero/equality closure and
its directly certified redundant-row removal:

* Remove 29,502 original variables proved zero, including 91 binaries and
  91 other integer variables.
* Identify 20,683 other deleted original variables with surviving roots.
  The surviving classes comprise 157,482 singletons and 20,683 pairs.
* Remove 46,616 constant-tautology rows and 61 box-redundant rows.
* Change bounds of 12,495 retained roots to exact class intersections.
* Change objective coefficients of 15,586 retained roots to exact class sums.
* Preserve every other retained row sense and RHS; write its fully aggregated
  substituted coefficients. Preserve objective sense and the fixed objective
  contribution. No extra cuts, approximate coefficients, artificial variables,
  application assumptions, or optimization-derived substitutions are introduced.

Net reduction: 50,185 variables (21.98%), 46,677 constraints (36.90%), and
101,359 constraint nonzeros (21.85%). These are size reductions, not measured
solver-performance improvements.

The output uses standard free-format MPS, exact terminating decimal coefficients,
explicit integer markers, BV records for binary roots, and explicit finite
upper bounds. No solver-reader invocation was performed under this protocol.

## 7. Artifact audit and exercised verification

`python3 output/verify.py` completed with exit code 0 and status PASS.
It uses only Python's standard library. The artifact reader is separate from
the analysis parser and interprets decimal tokens through Decimal -> Fraction.
It checks the exact complete original and generated models, not a sampled path.

The exercised checks cover input/output SHA-256 hashes, both complete MPS
parses, every ordered witness against original rows, the complete variable map,
all class domains and integrality, the complete objective identity, every
retained row, every removed row, and the changed-bound/changed-objective audit
tables. `output/verification.json` records the observed result.

Input SHA-256:
`d39273f74cdd8249ff459ae5c4056753ab11036d02624c09470b6949fbc071b4`

Committed output SHA-256:
`cb63c6125dd15c324e27bc1db55cc4486a976e3d97629f1a23c6397b1a8f024e`

## 8. Remaining uncertainty and limitations

The mathematical equivalence is supported by exact full-scope proof replay and
artifact comparison. No feasible point was computed, and no feasibility or
optimality conclusion is intended. Conventional free-MPS syntax was checked by
the independent reader but not by a particular optimization solver. Solver
performance and numerical behavior are unmeasured. Objective sums preserve the
exact decimal values encoded by the input, rather than inferred rounded values.
Further structure may exist outside the selected zero/equality/interval scope.

## 9. Final artifacts

* `output/model.mps` — single committed formulation.
* `output/audit.json` — hashes, counts, complete original-variable reconstruction
  map (null means zero), every removed row and its reason, every changed retained
  bound, and every changed retained objective coefficient.
* `output/proof.jsonl` — ordered zero and equality witnesses, followed by exact
  redundant-row interval certificates.
* `output/verify.py` — reproducible solver-free independent proof/artifact checker.
* `output/verification.json` — observed verification results.
* `output/report.md` — this report.

Reproduce the audit from the workspace root with `python3 output/verify.py`.
