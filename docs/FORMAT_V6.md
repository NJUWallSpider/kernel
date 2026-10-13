# RPX / RPA 6: strictness under partial affine observations

Version 6 adds `PointClaim::FiberStrictness` with an exact output point and a proof that its full input fiber is infeasible. This extends the types of requested statements, not the scalar inference rules. The original V3 Strictness rule remains unchanged and still requires a complete coordinate permutation. RPX/RPA 1–5 retain their layouts and semantics; MCM remains version 1.

The motivating actual test18 removes continuous coordinates while claiming strict LP strengthening under the retained observations. Evaluating just part of an input tuple cannot establish that no assignment to the removed coordinates exists. The new variant constructs every observation equality from actual models and the checked output point, then requires an ordinary exact LP refutation of that entire fiber.

## Requested statement

```
PointClaim += { "FiberStrictness": { "inclusion_claim": u32 } }
PointWitness = { "claim": PointClaim, "values": exact-scalar-string[],
                 "refutation": null | Block }
```

`refutation` defaults to null for old witnesses. FiberStrictness requires a refutation. Feasible and the old Strictness variant reject a surplus refutation; the presence of unused proof data cannot silently change their meaning. As always, all certificate point-claim variants and indices must match the separately supplied caller request exactly.

The referenced inclusion claim must already have passed complete model verification and must have both input/output integrality flags false. Its observations are its ordered coordinate projection pairs followed by its ordered affine-projection pairs. Write them as input expressions `a_i(x)` and output expressions `b_i(y)`. A successfully verified total map/extension then proves

```
{a(x): x satisfies the actual input LP}
    subset of
{b(y): y satisfies the actual output LP}.
```

The witness `values` supplies every actual output coordinate. All its exact values, finite variable bounds and row sides are checked. The checker evaluates each `b_i(y)` exactly and copies the complete actual input model, preserving its old variable/row indices and objective. It appends one equality row for **every** observation, in the order above:

```
a_i(x) = b_i(y).
```

The appended row keeps `a_i`'s full affine constant and coefficients, with the evaluated scalar on both row bounds. No observation, original model bound or original row can be omitted by the certificate. Observation dimensions are validated against the original directional models. Repetition, affine dependence and empty observation lists are allowed; they do not justify skipping any declared row.

## Refutation checking

`verify::verify_lp_refutation(model, block, limits)` validates the entire supplied model and starts a fresh proof context with LP input/output modes false, no live facts and no path assumptions. It executes the existing exact scalar rules. Only Absurd and Split endpoints are permitted. Local Cases/EqPair steps retain their earlier semantics. Every Split branch must establish its own contradiction. A Return endpoint, FlowLift or IntervalLift endpoint is rejected even when the model happens to be infeasible; this initial refutation language does not include existential extensions.

Absurd requires an exactly variable-free positive LE or nonzero EQ fact. Input VarInt is unavailable, including when original variables were declared integer, because the statement concerns the LP relaxation. Inherited map-proof registers, dead registers, sibling-local facts and prior point-refutation state are unavailable. Every new refutation starts fresh. Ordinary depth, live-fact, exact arithmetic and work rules apply.

The point checker receives only the budget remaining after all requested mapping proofs. Point feasibility, exact observation evaluation, copying/generating the full fiber model, and refutation execution consume that same remaining budget. A refutation never restarts an independent full default budget. The helper is an explicit proof checker, not a solver or proof search routine.

### Soundness

The checked output point proves that `b(y)` belongs to the output observation image. The exact refutation proves the actual input model together with all `a_i(x)=b_i(y)` equalities is infeasible, so no input point has that observed value. Consequently `b(y)` lies outside the input observation image. Combined with the already verified inclusion, this proves strict containment.

The argument does not require observations to be injective, surjective or linearly independent. With no observations, both images live in a zero-dimensional observation space; a checked nonempty output and an infeasible input still give strict containment. A nonempty input with no observations cannot be refuted merely by dropping the observation rows. An infeasible output point or failed inclusion proof invalidates the whole request, regardless of an independently successful refutation.

## Binary and text layout

The RPX version bytes are `06 00`. The V5 Claim layout is unchanged. PointClaim tag 2 has payload `u32 inclusion_claim`; tags 0 Feasible and 1 Strictness keep their previous payloads. In V6, **every** PointWitness has this layout:

```
PointClaim
array<Q> values
u8 refutation_present
[Block refutation, only when refutation_present is 1]
```

Only optional tags 0 and 1 are legal. V1–V5 contain neither this presence byte nor a refutation block. A V1–V5 header rejects PointClaim tag 2. A non-null refutation on an older point-claim variant still requires V6 syntax and is subsequently rejected by the mathematical point checker.

Each refutation is a fresh root block at depth one. Its nested Split and Cases bodies share the same maximum depth 64 as ordinary proof roots. Count and byte budgets remain cumulative across the entire file, including all point values and all refutations. Version discovery visits every refutation and uses the highest needed version; an unsupported endpoint inside a refutation is still fully decoded and checked for structure before semantic rejection. Unknown tags, reserved fields, malformed scalars, counts, truncation or trailing bytes reject throughout the file.

RPA 6 is exact header `RPA 6\n` followed by the strict JSON schema. Exact scalar strings and Block syntax remain unchanged. A FiberStrictness variant or non-null refutation under RPA 1–5 rejects. The request object contains only the point claim, not its candidate values or proof; the caller binds the intended statement while the certificate supplies independently checked evidence.

## Implementation and evidence

`proof.rs` defines the new claim and optional proof. `codec.rs` separately reads/writes the versioned payload and traverses all proof roots. `rpa.rs` gates text versions. `verify.rs` exposes the fresh LP refutation entry point and enforces endpoint restrictions in the recursive context itself, so nested branches cannot bypass them. `point.rs` binds the already verified inclusion, complete output point, all observation equalities and shared resource budget.

The core suite `crates/core/tests/refutation.rs` covers exact contradiction requirements, disabled input integrality, forbidden Return/existential endpoints, all Split children, sibling and cross-call isolation, local Cases, work/depth limits, point-refutation byte/version round-trips, every adjusted-header truncation, four byte substitutions at every payload position, and nested version discovery. These five core tests were executed successfully. The eleven dedicated point tests additionally check complete fibers and 120 independent Fraction observation-image cases (80 strict, 40 non-strict), as specified in [FIBER_POINT_V6.md](FIBER_POINT_V6.md). The full V6 core suite passed 147 tests. Independent Python-generated byte vectors (92-byte source MCM and 289-byte RPX) exercise a fixed-zero input LP strictly contained in `[0,1]`, using an exact input-fiber contradiction at output point one. A correctly laid-out V5 downgrade rejects the new point variant.

The extension does not add a trusted infeasibility oracle. Acceptance depends on the full existing exact proof rules, their model binding, and the kernel-generated fiber equations. Rule arguments and executable regression evidence are not a formal implementation proof.

The original complete test18 V6 candidate currently reaches RESOURCE_LIMIT with
the whole-live-fact-copy branch representation. Its exact files and bindings are
preserved in `cases/test18/preparation.naive-resource-baseline.json` for a controlled
replay after optimization. This is an unfinished case, not a false-transformation
finding or a certification. The `work` statistic includes all point-refutation
execution; mapping `branches`/`linear_terms` counters exclude these refutations,
and `point_coefficient_terms` records point/observation evaluation visits.
