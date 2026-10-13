# Lift premise-to-model trusted-path review

Read-only review by model_layer, 2026-10-11, responding to the first architecture-review concern. Source locations below identify the initial review snapshot including the unfrozen objective-level work. The root agent subsequently corrected comments and documentation; that wording delta was independently reread as recorded below. No production files were changed by this reviewer.

Conclusion: no concrete soundness defect was found in the inspected lift implementations. There is a material wording problem: several statements that the structural helper is “not a proof authority” can imply a smaller trusted boundary than the implementation actually has. The helper does not validate its supplied proof references, but **its generation of the required propositions and of the entire extended model is trusted mathematical code**. Parent-scope reference checks and complete output obligations do not independently establish that generation is correct.

## Exact logical obligation

Let D be the current actual input domain, including its integrality mode, all inherited extension laws and current branch assumptions. Let P be all required lift premises. The scalar checker establishes `forall x in D: P(x)`. For the specific rule, a mathematical lemma establishes

```
forall x in D with P(x): exists z: E(x,z),
```

where E must be **exactly** the new domains and rows emitted by the implementation. Prefix preservation gives the converse projection implication: any point in the extended model has its old coordinates in D. Thus the generated domain projects exactly onto D after the premises pass. Joint existence is essential: there is one z satisfying every new row for the same parent x, not separate witnesses for separate obligations.

The child proof establishes the requested output relation for every point of this extended domain. Existence then lets the kernel conclude an output exists for every original x. The old objective must remain unchanged so the objective relation has the advertised original-input meaning. This argument depends on both the abstract lemma and the builder implementing its precise premise and conclusion schemas.

## What each layer actually checks

| Layer and source evidence | Established fact | Not established by that layer alone |
|---|---|---|
| `verify.rs:268`–`280` Signed; `282`–`294` Menu; `296`–`309` Interval; `311`–`326` Flow | Structural preparation is bounded; every returned premise reference is checked in the old Context before the child uses the new model; required mode/inverse/depth guards remain | Whether the returned premise formulas are the correct sufficient hypotheses for the generated model |
| `verify.rs:146` (`check_fact`) | Required exact expression and proposition kind match a valid old-scope fact, or satisfy the narrowly defined Exact rule | A relation between that expression and any separately generated row |
| `interval.rs:278`–`285` and `296`–`311` | Builder emits all lower-major `lower−upper` premises and all `z−bound` rows | No second implementation compares those paired formulas; their signs, coordinate indices and row sides are trusted here |
| `menu.rs:260`–`330`; `signed.rs:212`–`243`; `flow.rs:302` onward | Rule-specific premise, domain and row construction, plus structural model validation | The universal extension theorem is not derived as an ordinary RPX scalar proof at runtime |
| `model.rs:299` (`Model::validate`) | Dimensions, names, canonical scalars/expressions and supported model structure | Feasibility, extension totality, prefix equality with some other model, or meaning of a generated theorem row; inconsistent bounds/rows may be valid infeasible models |
| `verify.rs:328` and `339` onward, Absurd/Return | A valid contradiction or every actual output bound/row/integrality/objective/observation/composition obligation follows in the supplied extended domain | That this domain has an extension for every old feasible point |

All four builders validate witness expressions against the pre-extension input dimension. All premises of all items pass before any child use. Integer-generating Menu/Signed rules require integer input mode; Interval/Flow introduce only continuous coordinates. Complete original model prefixes and the unchanged objective are explicitly copied. These are soundness-critical checks, not merely formatting conveniences. The current implementations and existing independent reviews check their intended signs, ordering and simultaneous construction; this review found no contrary actual path.

## Why final-output checking is not a second proof of lift soundness

Consider a hypothetical faulty interval builder: its valid request is lower 0, upper 1, so the parent proves `−1<=0`. Suppose an implementation bug nevertheless emits `z>=2` and `z<=1`. Both rows are individually well formed and `Model::validate` should accept the resulting infeasible model. A child can add their two normalized inequalities to obtain `1<=0` and close by Absurd. That would prove any target relation on the incorrectly empty extension, while the original parent could be nonempty.

This is an explanatory mutation, **not a bug observed in the current builder**. It demonstrates the missing logical implication: successful checks of the stated premises plus a valid conditional child proof do not protect against a wrong conclusion schema. Likewise, corrupting an old bound during copying can invalidate preservation of inherited facts. Replacing ordinary output checking with a second output checker would not repair either issue.

## Four distinct mathematical lemmas

- Interval: finite affine lower/upper families on one fixed real parent point admit a value iff every lower is at most every upper; choose maximum lower, minimum upper or zero. Different new coordinates refer only to the same old point, so all choices coexist. The exact generated domains must remain continuous.
- Menu: the checked A and I are integers with `0<=A<=1` and `0<=I<=K*A`. A=0 gives all zeros; A=1 selects exactly the index I. The emitted binary tuple satisfies both sum and moment equations. The local menu tuple is unique, but the complete model map is not thereby a bijection; the separate complete contract is still required.
- Signed: checked binary Z and `|F|<=C*Z`, C>=0, admit one joint tuple of nonnegative real p,n and binary u,v with the two split equalities and capacity inequalities. Active zero flow still requires u+v=1. F need not be integral.
- Flow: nonnegative arc flows and complete common-source balances admit a simultaneous commodity decomposition by finite positive-path extraction followed by assigning residual circulation to an existing commodity. The graph, demand signs, source/sink cancellation, loops, every commodity balance and every arc total are part of the exact conclusion schema.

These are reusable generic rules, but they remain trusted lemmas with trusted instantiations. Calling them “structural helpers,” “unchecked extensions,” or “no new scalar inference” does not remove that responsibility.

## Could a second checker supply independent assurance?

There are several different proposals, with different guarantees:

1. **Repeat `Model::validate` or the complete output checker.** This improves detection of some structural/data corruption. It does not check universal projection totality and is not an independent semantic guarantee of a lift.
2. **Reconstruct the exact expected premise/domain/row schema independently and compare every field.** This can detect builder implementation mistakes, provided the second implementation independently checks complete old prefixes, new variable domains, all constants/coefficient signs, indices, row sides, coverage and rule parameters. Then the schema checker plus the mathematical rule, rather than the original builder alone, is the acceptance authority. The second checker itself remains TCB. Shared formula helpers or copied implementation logic substantially reduce independence; matching two implementations is not a formal proof of the common formula.
3. **Independent Fraction constructions and model evaluation in tests.** Current oracle tests do this for many finite generated instances and points, and exercise different implementation paths/languages. They provide valuable defect-finding evidence. Finite tests, even exhaustive over selected bounded cases, do not prove all rational parameters and real input points.
4. **Proof-producing expansion or formal verification.** If an untrusted generator emits a finite piecewise construction whose coverage and full common output tuple are checked by already trusted rules, the specialized builder can leave the acceptance boundary. Its proof size and construction cost must be measured; a symbolic “exists” claim without such a checked construction cannot replace the trusted lemma. Alternatively a mechanically checked proof can cover the theorem and implementation refinement. Neither route is currently implemented merely by having two ordinary checkers.

A useful short-term audit target is therefore a small, explicit rule contract: exact premise formulas, exact generated schema, a quantified joint-existence argument, all original-prefix obligations, checked construction code, and independent mutation/oracle tests. A semantic schema checker should be introduced only with a clear claim about which component it makes untrusted and evidence that it is actually independent enough to justify its cost. Duplicating the same builder is not automatically a sounder architecture.

## Initial wording findings and correction review

- `verify.rs:317` says “The model builder is deliberately not a proof authority.” Read literally this is false: the builder determines which additional constraints become available. Better: “The builder is trusted to instantiate the extension theorem, but does not validate proof references; every returned premise must be proved in the old scope before use.”
- `docs/MENU_V7.md:27`–`30` uses “it is not a proof authority.” Replace the same way, while retaining the important distinction that a returned false premise has not been accepted.
- `docs/INTERVAL_V5.md:5`–`8` correctly says preparation alone is insufficient, but should explicitly say premise/model construction still belongs to TCB.
- `docs/FORMAT_V8.md:89`–`93` calls the candidate unchecked and says the split is not a delegation of authority. The intended distinction is between external untrusted preparation and the **trusted Rust theorem builder**, not between the builder and a fully independent semantic checker.
- `audit/TRUST_REPORT.md:14`–`17` correctly lists all lift modules in the trusted path. That accurate table should be the consistent terminology used throughout the rule documents and code comments.
- `audit/V8_REVIEW.md` currently says the “complete-output checker remains the proof authority after the new joint existence step.” It should clarify that output checks are conditional on the trusted existence theorem and its correct generated model, rather than suggesting those checks independently validate the theorem.

Recommended concise guarantee: “The kernel checks every lift premise exactly in the parent scope, applies an audited trusted joint-existence rule whose builder is part of the TCB, and then checks the complete actual output contract. Independent reference constructions and attacks provide implementation evidence; the Rust implementation has not been formally verified.”

After the initial findings were sent, the root agent revised all four lift-module headers, the Flow Context comment, the Menu/Interval/V8 rule descriptions and the trust report. I reread those revisions. They now accurately distinguish (a) unchecked proof references, (b) trusted generation of P and E, (c) the existential joint-extension lemma, and (d) conditional child checking. The trust report explicitly states `M(x) and P(x) => exists z. E(x,z)` and explains that an incorrectly overconstrained/empty extension could compromise soundness despite structural, premise and child checks. Those corrections resolve the substantive wording concern; they do not alter the implementation or purport to add a formal proof. The original line-number findings above are retained as the history of the review, not as claims that the corrected text still contains them.

The reviewer's own `audit/V8_REVIEW.md` opening was clarified in the same way: the complete-output checker checks the downstream contract conditional on the trusted existence step. No production code, theorem schema, arithmetic or architecture was changed by this review.
