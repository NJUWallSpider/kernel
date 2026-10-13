# Remaining capability review

Review date: 2026-10-11. This is a mathematical/interface review, not a release or acceptance result. It reads the actual final reports, `CAPABILITY_PROPOSAL_NOTES.md`, test36/test58 probe receipts, the earlier isolated subflow builder, and its saved test log. No production rule, header, codec, verifier or ledger was changed for this review.

## Recommendation

Proceed with **one next-version draft and one final freeze**, with independent, narrowly scoped capabilities. Do not freeze a version for test36 and another for test58. Keep the two mathematical responsibilities distinct even if their bytes share one new header:

1. A caller-bound strict-improvement request for one positive affine predicate, needed by the complete test36 contract and test83's explicit all-optimizer exclusion.
2. A joint demand-bounded subflow lift, needed by the uncompleted forward test58 proof.
3. A point-image exclusion claim without an inclusion prerequisite, needed to finish the actual test62 fractional-point claim.

The third is a missing result contract, not another existence theorem. Existing rules still handle the actual model rows, objectives, binary reasoning and complete maps. Tentative V10/V11 numbers in earlier notes should become historical proposal labels; decide one new header only after the joint schema/byte/negative-test review. Previously supported headers and already interpreted V9 records must retain their meanings. No feature should silently change V4 FlowLift into circulation removal.

## Exact remaining contracts and evidence

| Case | Complete committed relation | What the recorded kernel evidence establishes | Still missing |
|---|---|---|---|
| 36 | Minimum objective preserved; **every** source integer optimizer has all 200 terminal coordinates zero. No LP claim and no known numerical optimum. | Reverse recovery and the full objective-6425 feasible point; a full positive-terminal source point of objective 6426; the stronger requested field is rejected. | Caller-bound universal exclusion and the complete forward dominance map. A positive terminal is not globally integer or globally impossible. |
| 58 | Source-to-target complete MI map with nonincreasing objective; every target feasible point has an equal-objective source lift. No all-point bijection or LP relation. | Complete reverse map: 303 SignedLift items, 6,751 terminal obligations. The local forward merge fails obligation 1372; an exact circulation fixture invalidates its capacity inference. | One joint bounded rerouting/subflow construction and the complete forward output proof. |
| 62 | Integer projection equivalence, unique Boolean lifting and equal objective, **plus** a complete source-LP point whose retained image violates seven actual target unit clauses. The report explicitly disclaims LP containment. | The integer relation/bijection and source-point feasibility. Its receipt explicitly leaves target exclusion uncertified. | The caller-bound exclusion of that full target-coordinate image. Do not label a feasible source point alone as this complete result, or substitute LP strict containment. |
| 83 | Minimum preservation and optimal recovery, with the report's exact strict-dominance argument that no optimizer selects any of the 61 removed columns. | Complete NonIncreasing/Equal maps; the receipt explicitly excludes a separately caller-bound all-optimizer statement. | Bind the positive dominated-column sum to the strict objective decrease. |

The incomplete whole-case statuses must remain distinct from successful subclaims. The failed test58 map is not a counterexample to the transformation. Test36's feasible terminal `1/4850` is a counterexample to an unconditional terminal-zero or terminal-integrality premise, not to the report's optimizer exclusion.

## Subflow lemma: precise statement

Let a finite directed multigraph have `n>=1` vertices and `m>=0` arcs. Loops and parallel arcs are legal. Fix a source `s` and a finite demand list `(t_i,d_i)` with `t_i != s` and exact rational `d_i>=0`. Repeated sinks aggregate by addition; an empty list is legal. Define

`B = sum_i d_i`, `b_s=B`, and `b_v=-sum_{i:t_i=v}d_i` for `v!=s`.

For **every real** vector `f` satisfying `f_e>=0` and `div(f)=b`, there is **one real vector** `g` such that

`div(g)=b`, `0<=g_e<=f_e`, and `g_e<=B` for every arc.

The lemma concerns real feasible points. Rational coefficient storage does not make their coordinates rational. The proof below uses only finite paths, real minima, nonnegativity and exact equalities, so it does not rely on integrality or a rational lattice.

The suggested candidate types are `SubflowWitness { nodes, arcs, groups }` and `SubflowGroup { source, demands, flows, nonnegative, balances }`. Require at least one group, exactly `m` flow expressions/nonnegative references and `n` balance references per group. Compute B internally, checking every intermediate rational addition. All flow expressions are in the same pre-extension scope. All new group variables are continuous and have zero objective coefficients.

Choose the new notes' simpler demand semantics: **even zero demands at the source are rejected; empty demands mean B=0**. The old isolated `FlowWitness` prototype instead permits source-equal commodities, counts them in a loose B, and rejects an empty list. Both mathematical formulations can be sound, but they are different APIs. The candidate must not accidentally inherit the old one. No existing V4 schema semantics change is needed.

## Constructive proof and finite termination

Add a fresh supersink `t*` and one demand arc `t_i -> t*` of flow `d_i` for each positive demand-list entry. Let `k+` be the number of such entries. The augmented vector has divergence B at s, -B at t*, and zero elsewhere. Keep residual R equal to this vector and initially set g=0 on original arcs.

While residual divergence at s is positive, find a **simple** directed s-to-t* path using only positive-residual arcs. Such a path exists: if t* were not reachable, let U be the positive-residual reachable set from s. There is no positive residual arc leaving U. Hence the sum of divergences over U is at most zero (outgoing residual is zero and incoming residual is nonnegative). But its only nonzero divergence is the positive residual source supply, a contradiction.

Subtract the minimum positive residual on the path from every path arc and add that amount to g on the original arcs of the path. A simple path uses each arc at most once. At least one residual arc becomes zero. No residual arc ever increases or becomes positive again. Thus there are at most `m+k+` extractions, even for irrational inputs or arbitrarily small positive values; there is no limiting/infinite cycle-cancellation argument.

Every extraction preserves internal divergences and reduces source supply and supersink demand by the same positive amount. On termination their residual values are zero. Because the supersink has no outgoing arcs, every residual demand arc is then zero. The extracted original-arc vector therefore has exactly the original demanded divergence b. It is nonnegative and no larger than f, since only residual subtraction was used. The path weights sum to B, and an original arc appears at most once in each path, so **all** coordinates simultaneously satisfy `g_e<=B`. Residual original circulation is discarded.

If B=0, choose g=0 without searching. Loops cannot occur in a simple source-to-distinct-supersink path and can be discarded. Source-entering circulation, cycles visiting sinks, disconnected circulation and isolated vertices do not change the argument. Empty arcs with positive B cannot satisfy all premises; empty arcs with B=0 yield a valid zero-dimensional extension. Repeated sinks are equivalent to repeated supersink arcs or one exactly aggregated arc.

For finitely many groups, perform this construction separately on their common old point. Their fresh coordinate sets are disjoint, so the constructions coexist in one extended tuple. This does not authorize independent choices for separate output rows or preserve arbitrary extra flow-side constraints: the child must prove **every** actual output obligation from the entire extended domain.

## Complexity and trusted boundary

An independent constructive oracle with adjacency lists can run each BFS/path extraction in `O(n+m+k+)` graph operations and use `O(n+m+k+)` memory. At most `m+k+` extractions give `O((m+k+)*(n+m+k+))` graph/arithmetic operations. Exact rational bit complexity is additional; this is not a constant-time arithmetic or wall-clock bound. An oracle that scans every arc for each popped vertex, as the old Python prototype does, has a worse `O(n*m)` search bound and must not be described by the adjacency-list complexity.

The production verifier should **not perform this path search**. It implements the lemma by constructing and checking its exact premises, then appending the conditional domain:

- per group, m continuous variables with bounds `[0,B]`;
- n equality rows `div(g)=b`, in node order;
- m inequality rows `g_e - flows[e] <= 0`, in arc order.

Old variables, integer designations, every row, names and objective remain exact prefixes. Premise order is m `LE(-flows[e])`, then n `EQ(div(flows)-b)`. Establish every premise with the ordinary proof checker in the old scope **before** executing the child. Construction alone is not premise verification.

For G groups, generated counts are `G*m` variables and `G*(n+m)` rows. If `T_g` is total old-flow expression support in group g and `m0` counts nonloop arcs, generated row support is `2*m0 + m + T_g`. Precanonical premise support is at most `3*T_g` (loop terms occur only in nonnegativity premises). Divergence merging additionally costs the sum of per-node sparse sorting/merging costs; a claim of purely linear CPU complexity must not hide those sorts or BigRational operations. Prefix copying/validation and all names, constants, demands, terms, probes, bounds, generated rows, premises and child work share the request budget. Use checked counts, preflight before allocation and fallible reservation from existing `build_support`, retaining intermediate scalar checks.

This builder is trusted inference code because its appended domain embodies the lemma. The untrusted author finds the graph/flow representation and supplies references. A helper called `prepare_unchecked_extension` does not move the existence theorem outside the TCB. Neither a successful helper call nor an oracle test proves all premises at an arbitrary input point.

## Applying the lemma to the actual test58

Use the already checked 199 bridge cut equalities and 121 series-internal identities. The actual residual has a single supply of 82 and nonnegative demands totaling 82. The old balance-row convention is in-minus-out; the witness uses out-minus-in, so negate/reorient the supplied linear combinations explicitly.

Choose joint nonnegative directional representatives of each residual path's signed flow using existing SignedLift and checked path activations. Only then merge the two expensive paths into their cheaper parallels, consistently with orientations. The resulting old-scope aggregate may have capacity 164, which is allowed as an input f to the new lemma. The lift yields a common g bounded by 82 and by the supplied nonnegative aggregate.

Keep the checked activation of each retained path. Its inactive branch forces the supplied directional aggregate, hence both g directions, to zero; its active branch uses g<=82. The final signed coordinate is the difference of those two directional g coordinates, so both signed capacities hold with the same activation. All demand balances hold jointly. Prove activation-cost domination separately from the actual positive path costs, and carry `OBJFIX=1` with cost 205. Pruning grants no objective or activation theorem by itself.

Retain the complete existing reverse proof, including zero-flow but activated target paths. It returns exactly the target objective, not just a lower-cost source point. The old attempted local merge must continue to fail: `(82,82,82)` on `s->t,s->t,t->s` has net demand82, but merging gives `(164,82)`. Independent clipping to `(82,82)` loses the required divergence; `(82,0)` is a valid joint bounded subflow.

## Strict improvement: smaller sufficient contract

Replace the proposed DNF by one caller-bound affine expression P in the **original actual input coordinates**. The request states:

`forall x in S: P(x)>0 => exists y in S: f(y)<f(x)`.

For the current cases S is the complete actual source MI domain and f its normalized minimization objective. The request must bind model side and integer mode explicitly, compare all fields to the certificate, and introduce no implicit objective-level restriction. The two ordinary source/target mapping claims remain separate.

At the root, the proof may use the weak closure `LE(-P)`. An improvement leaf supplies one complete source-dimensional tuple y, all actual source bounds/integer/row checks, and one of:

- constant margin `h=q`, checked exact `q>0`;
- scaled predicate margin `h=q*P(x)`, checked exact `q>0`.

Check `LE(f(y)-f(x)+h)` against actual objectives including constants. This proves strict decrease on P>0 even when arbitrarily small positive P has no uniform gap. Margins are proof witnesses, not hidden changes to the requested condition. A dedicated positive-domain refutation leaf may prove `LE(P)` and combine it only with this root's P>0. Ordinary Absurd may close an inconsistent weak domain. Each whole-map Split leaf must improve or refute; ordinary Return must not silently count as an improvement leaf. Local Cases continue to export only ordinary facts.

Preserve the original P across existential extensions as an old-coordinate expression. No sibling/root/ordinary-claim scope may borrow positivity. An equality-boundary point P=0 may be in the weak closure but is outside the requested strict domain; its treatment must not establish false strict decrease at the boundary. This design is sound for empty, unbounded or nonattaining models without claiming that an optimizer exists.

### Concrete sufficiency for test36

Take `P=sum(all 200 original terminal coordinates)`. Their actual nonnegative bounds make P>0 exactly the required union of positive-terminal events. No noncanonical-lift predicate or DNF is necessary.

Jointly construct the canonical prefix AND coordinates c from the same 200 original binaries and prove each `0<=c_i<=old_i`, every canonical source row, and integrality of these canonical coordinates. This is existing-rule work, not a trusted chain theorem. One candidate representation is SignedLift on `sum(prefix bits)-(prefix_size-1)`; its positive part is the prefix AND. This is only a proposed representation until its width/work are measured.

Split once on the **canonical** terminal total, which is integer and nonnegative:

- Canonical total zero: use the complete canonical source tuple. All canonical terminals are zero. The checked objective change is at most `-4850*P`, since all nonterminal coordinates also decrease and have positive cost. Use predicate margin 4850.
- Canonical total at least one: prove the actual binary contribution195 and intermediate lower bound2238, plus terminal contribution at least4850. The original objective is at least7283. Return the already checked complete source point of objective6425 with constant margin858.

The same two branches produce a complete target-feasible map with nonincreasing objective after deleting zero canonical terminals, or using the target 6425 point. The reverse zero-terminal lift remains independently checked. Thus strict improvement is sufficient for the full stated optimizer exclusion while the ordinary maps establish minimum preservation. Do not round arbitrary old continuous terminal values; the recorded feasible value1/4850 must remain accepted.

### Concrete sufficiency for test83

Take `P=sum(all 61 dominated original columns)`. Compose the already available complete forward dominance map and reverse singleton recovery to obtain one full **source** tuple y. Its exact objective saving is `sum(delta_i*x_i)`, where every checked rational delta_i is strictly positive. Set q to any checked positive lower bound on all deltas, for example their exact minimum. Then `f(y)-f(x)+q*P<=0` follows from the same exact saving identity and original nonnegative bounds. This closes the all-optimizer exclusion without changing the minimum-preserving maps or asserting a full feasible-set bijection.

## Test62 point exclusion

Do not relax Strictness or FiberStrictness's inclusion prerequisites. Add a distinct result. The smallest interface sufficient here binds a full source feasible point and a caller-requested affine image for **every target coordinate**, then exactly checks that this complete image violates a selected actual target bound/row in LP mode. Test62's image is its 500 retained coordinates, so no unknown target auxiliary coordinate remains.

If a more general partial observation image is selected, one violated arbitrarily completed target point is insufficient; use the existing V6 complete fiber construction plus an LP refutation, without asserting inclusion. Either interface has exact point/model checks, not a new optimization theorem. For the current scope prefer the complete-image form and test it against all seven reported unit-clause exclusions. It asserts that one source point maps outside the target, and neither asserts global containment nor global integer feasibility.

## Existing prototype evidence and required additions

The old isolated helper plus 244 Fraction construction vectors is useful reusable material. Its saved five-test log has **four passes and one failure**, so it is not an all-pass integration baseline. The failing assertion occurs after `unwrap_err()` and concerns an expected error prefix: the malformed input did return an error. It still needs repair under the new schema and shared helper path. It has no production End/codec/context integration and cannot count test58 as accepted.

Retain the old corpus as historical evidence, then add a new isolated oracle set with:

1. Adjacency-list supersink extraction, recorded paths/weights and the `m+k+` extraction bound; independently recompute every divergence, `0<=g<=f`, `g<=B`, and generated model field.
2. Random exact path-plus-circulation graphs with shared physical arcs (aggregate equal endpoints sometimes), parallel arcs, node/arc permutations and rational scaling. The old generator frequently creates a fresh parallel arc per path; it should not be the only overlap test.
3. Bounded exhaustive small multigraph flows filtered by the premise, and separate rejection fixtures with two positive supplies, wrong demands, negative flows and wrong incidence. These test input-premise rejection, not a path-search implementation in production.
4. Empty demands/arcs, positive demands with no arcs, zero demands at a non-source sink, repeated sinks, source-sink demand rejection, loops, disconnected cycles and source-entering cycles. Preserve the 82/164 regression and reject independent clipping.
5. Nontrivial affine flow expressions/constants, multiple groups sharing old coordinates, name collisions and exact prefix preservation. Check every returned premise is discharged before any generated coordinate is referenceable.
6. Count/depth/work/term/bit limits, intermediate demand-sum overflow, cancellation-hidden large scalars, malformed canonical rationals, stale/sibling references and missing middle node/arc checks. Full-context rejection and byte tests remain root integration responsibilities.

For strict improvement, independently enumerate small integer domains and rational boundary points, including P=0, arbitrarily small P>0, zero/negative scales, changed objective constants, false source mode, missing output checks, incompatible tuples and positivity leakage. Reuse test36's positive-terminal point as an unconditional-fixing regression and test83's full map rather than a toy-only proof. Test new-record downgrades, all truncations and unknown tags alongside canonical older-header roundtrips.

The combined draft should freeze only after complete actual36/58 certificates, the missing62/83 claims, independent mathematical/implementation reviews, old-byte compatibility, full resource attacks, and a fixed multiscale performance/size/preparation baseline all pass. Formal proof of the implementation is not claimed by these tests.

## Isolated implementation follow-up

After the read-only review, the parent authorized a separate candidate crate at
`audit/subflow-next/`; production schemas and the ledger remain untouched by
that work. The exact proposed Subflow types, shared mechanical support, builder,
983-case independent Fraction fixture, and nine passing tests are recorded in
`audit/subflow-next/receipt.json`. The builder uses the preserved internal
`delivery-78-working-source` snapshot; every dependency source matches its
original manifest. The new tests check all premise/generated-row fields and
joint path traces as well as malformed inputs and resource boundaries.
This is conditional-builder evidence only. It does not establish production
scope/codec integration, full actual test58 acceptance or a performance result.
