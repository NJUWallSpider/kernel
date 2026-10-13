# Working V9 objective-level extension

Status: implemented locally and exercised by the complete actual test80 certificate and nine rejection tests, but not frozen or released. V8 is the last frozen version. See `OBJECTIVE_LEVEL_DESIGN.md` for the actual-case motivation and full mathematical argument, and `cases/test80/README.md` (relative to the repository root) for the precise receipt and internal baseline identity.

V9 adds no theorem endpoint and no scalar inference. A caller may explicitly restrict a directional claim to an exact level of the full actual input objective:

```
Claim.input_objective_level: Option<Q>
```

The JSON field defaults to absent and uses the same exact rational strings as other optional scalars. Absent means the complete input feasible domain, with the existing requested integrality mode. Present with L means its intersection with `f_input=L`. This does not assert that L is optimal, feasible, attained, or a bound. The separate requested contract must exactly match the field.

The kernel copies the actual input model and appends one equality row with the original objective expression and both bounds L. The original variable/row/objective prefixes remain unchanged. The appended row index is the original row count. Its normalized fact is `f_input−L=0`, including the objective's constant. A generated fresh name avoids all original row-name collisions; names carry no proof authority. Each directional claim starts with fresh facts and assumptions, so this equality is local to that direction. Original-coordinate observations remain validated against the original input/output dimensions.

All existing actual output obligations execute unchanged. If an opposing affine claim referenced by `inverse` has a level L, each Return additionally proves `EQ(f_output(map)−L)`. This check occurs after all inverse coordinate identities and before `input_objective_lower`. It is required even when objective preservation was not requested. Ordinary output constraints and modes prove the rest of the opposing domain membership. Both complete inverse identities together with both directions' domain membership establish a bijection of the declared domains.

The existing lower-bound obligation applies to the declared input domain. With a restriction it is conditional, so a global actual-model lower bound must be requested in a separate unrestricted direction. A complete original-model point with checked objective L can establish attainment separately. In particular an empty level may close by Absurd without establishing a minimum.

V7 `BijectionClaim` pairs reject if either indexed direction has a level restriction. Existing whole-model `Strictness` and `FiberStrictness` reject restricted inclusion claims before directional execution, and the public point helper also rejects them. Their whole-model meaning is not reinterpreted. Ordinary feasible points still check the actual complete model. Synthetic injectivity and refutation claims use no restriction. Flow/Interval/Menu/Signed proof endpoints may operate inside a restricted direction under their existing rules; legacy `inverse` still requires affine root Returns.

## RPX/RPA layout

The RPX header version is 9 and RPA header is `RPA 9\n`. MCM remains version 1. The complete V8 outer layout remains, except each V9 claim appends `option<Q> input_objective_level` immediately after its affine-projection array. Option tags, canonical Q encoding, counts, exact total length, reserved bytes and recursion limits are unchanged. V1–V8 readers set this field to absent and consume no extra claim bytes. Encoding any certificate with all levels absent chooses the same lowest version as before; re-encoding old canonical bytes remains identical. A nonempty level requires V9 even if its proof closes by contradiction.

Return check order is:

1. All actual output variable lower/upper/integer obligations.
2. All actual output row lower/upper/equality obligations.
3. Requested objective relation, coordinate and affine observations.
4. All legacy affine inverse coordinate equalities.
5. Opposing inverse objective-level membership, when present.
6. Requested input objective lower bound, when present.
7. Existing V7 bijection compositions (filtered pairs are rejected).

No missing or surplus reference is allowed. A correct composition alone cannot stand in for item 5.

## Trusted boundary and checks

`level::prepare_domain` is a structural model operation. Its guarantee is the exact set identity `Feasible(prepared)=Feasible(actual_input) intersect {f_input=L}`; it does not discover or prove L. The map checker verifies the caller-bound contract over that declared domain. No external preparer, solver, corpus name or model digest is an acceptance authority.

Expanded dimensions and combined term support are checked before copying; canonical Q and the normalized equality constant are bit-bounded. Copying, validation, generated support and fresh-name probes use the same remaining work limit as the surrounding proof. Controlled vectors and strings use fallible reservation. The constructed model is validated. Standard bigint/internal allocation limitations remain unchanged.

Statistics add `objective_level_domains`, `objective_level_generated_rows` and `objective_level_generated_terms`; work includes domain preparation. These counters are not an optimality result.

Current dedicated evidence comprises five builder tests and seven integration tests. The independent Fraction oracle has 25 objective/level cases and 5,525 complete point-domain checks. The independently written 465-byte V9 fixture, source/target MCMs, malformed optional tag and every truncation prefix exercise the wire format. Integration cases cover global-bound/attainment plus reciprocal restricted maps, valid compositions with invalid opposing-domain closure, exact request matching, original-objective changes, scope isolation, empty levels, filtered old-contract rejection, nested extensions and shared budgets. These execution results are test evidence, not a formal verification of the implementation. Actual test80 now has a complete 9,130,685-byte RPX proving all requested original-optimizer/target relationships, a global lower bound and attainment; all nine targeted corruptions reject. The receipt preserves the unfrozen protocol status.
