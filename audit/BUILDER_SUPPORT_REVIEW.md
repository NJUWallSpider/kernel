# Independent review of shared builder mechanics

Review date: 2026-10-11. Reviewer: model-layer agent, independent of the extraction author. Scope: read-only comparison of `bench/builder-support-baseline/crates/core/src` with the current production files recorded in `audit/builder_support_review_identity.json`. No production edits or additional builds were performed for this review.

## Conclusion

No semantic or resource-threshold regression was found in the extraction. Complete original model fields, generated variable domains, generated row expressions/bounds, premise expressions/order, validation order and successful work statistics are preserved. This conclusion comes from source comparison; the separately executed differential evidence below supplements it and is not a universal proof.

The extraction centralizes trusted implementation mechanics. It does **not** turn the existential lift builders into untrusted code, independently prove their joint-extension lemmas, or add a second semantic checker. Rule-specific premise generation, domains and rows remain part of the trusted inference implementation. `build_support` is private to the crate and does not introduce a public unchecked acceptance path.

## Checked invariants

### Full model prefix and domains

`build_support.rs:80-113` copies the model name, complete objective including its constant, every variable's name/integer flag/lower/upper, and every row's name/expression/lower/upper. Vector iteration preserves coordinate and row indices. It neither normalizes bounds nor drops redundant, zero, free, contradictory or constant rows. Its new capacity guard rejects an undersized internal request; every current caller preflights capacities at least as large as the original model. The helper adds no work charge because each caller already charged the same scan/copy policy before invoking it.

The generated domains remain rule-local and unchanged:

- Flow (`flow.rs:219-223`) appends nonnegative continuous commodity flows.
- Interval (`interval.rs:140-146`) appends free continuous coordinates, with their lower/upper affine rows added separately.
- Menu (`menu.rs:142-149`) appends integer coordinates with bounds `[0,1]`.
- Signed (`signed.rs:102-115`) appends continuous nonnegative `p,n` and integer `[0,1]` coordinates `u,v`, with the same four joint rows.
- Fiber (`point.rs:246-274`) adds no variables and retains every original domain. Coordinate equalities precede affine observation equalities, as before.
- Level (`level.rs:61-67`) adds no variables and appends the unchanged full actual objective expression with both bounds equal to the requested level.

Injectivity deliberately builds a new paired domain instead of using `copy_prefix`. `injectivity.rs:106-168` still creates two complete copies of the actual input bounds, integer declarations and rows, shifts only coordinate indices in the second copy, and keeps row constants and both bounds. The two evaluations of each *same* forward map have equal constants, so the observation equality constant remains exactly zero. Every original coordinate still gets an equality goal. Synthetic names use distinct left/right/observation prefixes; no inherited names can collide with them.

### Exact arithmetic and sparse differences

`build_support.rs:115-154` is the same sorted sparse subtraction removed from interval/menu/signed. It checks the newly formed constant immediately, and checks each same-coordinate rational subtraction before zero coefficients are omitted. Nonmatching copied or negated coefficients were validated by the caller; these operations cannot enlarge numerator/denominator bit length. Term order, zero elimination and allocation upper bound are unchanged.

The callers still validate all witness expressions against the **old** input dimension before constructing any extension. Menu's `K*A`, signed's `C*Z`, signed's `-F`, all scalar bounds/capacities and their intermediate checks remain outside the helper and unchanged. Flow's checked demand arithmetic and sparse divergence accumulation are likewise unchanged. Level still checks `objective.constant - level` after input validation and before copying. Point still checks each exact evaluation product and accumulator through its original evaluator.

### Work and collision policy

`build_support.rs:64-77` exactly reproduces the common scan:

```
terms = objective.term_count + sum(row.term_count)
work = model_name_bytes + objective.term_count + 1
     + sum(variable_name_bytes + 3)
     + sum(row_name_bytes + row.term_count + 4)
```

Dimension/term ceilings and multipliers remain at their former call sites. Flow/interval/menu/signed retain the original `2 * copy_work`, witness checks and generated-data precharges. Injectivity retains `3 * input_work + output_work` followed by the same map and generated-data charges. Level retains `3 * model_work + 4 * (objective.term_count + 1) + 32`. Fiber retains its original observation additions, `2 * copy_work` and shared point/refutation budget.

The common charge (`build_support.rs:156-170`) performs checked conversion and checked addition, then rejects exactly when `used > limit`; equality at the limit is still permitted. Mutation of the internal counter before a failing comparison is unchanged. `Budget::sort` (`221-224`) is identical to flow's former `n * (bit_length(n) + 1)` charge, including `n=0`.

`Names::fresh_with` (`240-252`) charges one unit **before every attempted suffix**, including collisions, increments the suffix with checked arithmetic, and tests the inherited name set. The starting count and prefix passed by every caller are unchanged. Monotonically increasing suffixes preclude generated/generated collisions without inserting generated names. Point's callback continues to charge the request-wide point statistics; it does not create a separate reset budget. HashSet order is irrelevant because only membership is observed.

### Validation and trusted context

The helper does not validate models implicitly or move validation across a rule boundary. All former caller preflight/validate/build/final-validate sequences remain in place. In point/fiber, source/target validation still occurs at `verify_points` entry; the completed fiber is validated by the unchanged fresh LP-refutation entry point. No new integer reasoning is enabled in that LP proof.

`verify.rs`, `proof.rs`, `codec.rs` and `rpa.rs` are byte-identical to the baseline by direct hash comparison. Thus this extraction did not change pre-extension premise checking, actual output checking, composition/level closure, scope management, version detection, wire layout, integer-mode gates or caller-bound contracts.

## Actual implementation differences

These differences are not mathematical changes and should not be described as a byte-for-byte source refactor:

1. Error details now use shared wording. Point's former `fiber count overflow`, `fiber allocation`, `fiber string allocation`, `fiber name index allocation` and `work count width` can become generic count/allocation/string/name/width wording with the same `RESOURCE_LIMIT point` category. Level's name-budget failure becomes `preparation work budget` rather than `name work budget`; its copied-string allocation detail also changes. No threshold or successful work statistic changes.
2. Flow, interval and fiber formerly created generated names with `format!`; they now preflight the string buffer with `try_reserve_exact` and return a resource error on a recoverable reservation failure. This is a failure-handling improvement, not a new mathematical input restriction. Big-rational clone allocation behavior was not changed and is not claimed to become wholly fallible.
3. Menu/signed generated names now use checked `prefix.len() + 32`; their prefixes are unchanged compile-time strings. Level's generated-name reserve changes from fixed 48 bytes to `prefix.len() + 32` (46 bytes for its prefix). Both exceed the actual prefix plus a 64-bit `usize` decimal suffix; name bytes and charged attempts are identical. Allocator/OOM behavior need not be identical.
4. `copy_prefix` adds a defensive undersized-capacity error; no current caller can reach it after its unchanged dimension calculation.
5. `lib.rs` registers a private module. There is no format or contract addition.

## Recorded execution evidence (not run by this reviewer)

I inspected `audit/validation/builder-support-differential-v2/result.json`: seed `1112885580`, 576 complete prepared fixtures, 456 invalid models, and 1,728 boundary calls per implementation. It reports no complete-output/work mismatch and 96 same-category error-detail changes, all the level name-budget wording above. The probe explicitly excludes point/fiber from its constructor comparison; those paths must be supported by integration and actual-case replay evidence, not counted among these 576 constructor fixtures.

The parent separately reported both complete core suites passing 210 tests each. At the time of this review, the parent's complete actual-case dual replay was still running; this report does not claim its eventual completion. No additional performance claim follows from source consolidation.

The initial differential probe failed before constructing a baseline model because its readable-rational fixture representation and non-ASCII names did not match the model input format. The parent preserved that attempt and corrected only the audit fixture machinery. That failed attempt is not a kernel differential pass or a kernel rejection counterexample.

## Review limits

This review establishes no unconditional formal correctness guarantee. It specifically audits the extraction against the preserved working baseline, which already included the **unfrozen** objective-level implementation. It does not endorse that draft as a frozen protocol release. It does not re-prove every lift theorem, replace the independent Fraction oracles, or infer correctness from aggregate test counts. The remaining trust boundary documented in `audit/LIFT_TRUST_REVIEW.md` is unchanged.
