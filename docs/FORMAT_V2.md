# RPX / RPA 2: local case derivations

RPX version 2 adds two generic rules to [version 1](FORMAT_V1.md): exact antisymmetry (`EqPair`) and local exhaustive case reasoning (`Cases`). The model format remains MCM version 1. All existing v1 fields and operations keep the same mathematical interpretation. A v1 header rejects either new step tag. The encoder emits v2 if any new step occurs, otherwise v1; a v2 file may contain only old steps and can then be disassembled to equivalent v1 text.

## Why this extension exists

The actual `test88` target removes aliases among bounded product/absolute-value auxiliary columns. Their equalities hold over the mixed-integer feasible set because a small group of binary sign coordinates fixes each local expression. The same equalities need not hold on the LP relaxation. Certifying each alias by branching the complete model proof would duplicate unrelated output obligations and potentially multiply branches across 256 aliases.

Cases instead proves one fixed input-coordinate proposition locally and exports it as an ordinary checked fact. Later affine substitutions can use that equality in the unchanged complete model checker. It creates neither a model-specific theorem nor an existential output-coordinate shortcut. Each child must prove the same fixed statement; all output variables still receive one simultaneous Return map.

The actual `cases/test88/` preparation reports 352 global aliases, 5,376 local branch points, and 12,906 terminal output obligations, checked on the full original and final MPS-derived models. Its accepted request is objective-preserving integer feasible-set bijection with both affine inverse compositions; it makes no LP-equivalence claim. The reproducible preparation source and receipt carry the exact counts and timings.

## Mathematical rules

`EqPair(id, positive, negative)` requires two visible live LE facts whose exact affine expressions are `e` and `-e`, including constants. It defines a fresh live local register containing EQ(e). This is antisymmetry of the real-number order. A positive scalar multiple is insufficient unless explicitly normalized by a prior Lin. An EQ or INT input is rejected rather than implicitly converted.

`Cases(id, kind, expression, split, integer, left, right)` proves one fixed proposition `kind(expression)` in the parent scope. `expression` and `split` are canonical input-coordinate affine expressions. Its guards are:

- `integer = null`: left `split <= 0`, right `-split <= 0`, covering all real values including overlap at zero.
- `integer = Ref`: the reference must prove INT(split) with exactly matching expression; left `split <= 0`, right `1-split <= 0`, covering all integers.

Each child starts with an isolated view of the parent's live facts and the same ancestor assumptions plus its own guard. It executes a finite Derivation and either produces a witness for the fixed parent proposition or proves its guard scope contradictory. Its local register writes/drops are rolled back on exit. No child facts are available to its sibling or to the parent except the one common Cases conclusion. A Cases ID cannot overwrite a live parent ID. V1's explicitly reusable register behavior after DROP remains in force.

Let P be the conjunction of the input model and existing path assumptions, C the common proposition, and G0/G1 the guards. The checked branches establish `P and G0 => C` and `P and G1 => C`; contradiction is a valid way to establish either implication. Guard coverage gives `P => C`. The result therefore has parent scope and can be used after Cases. If both children are contradictory, P is empty and any proposition follows; no arbitrary fact is accepted without those two contradictions.

A Witness normally refers to a fact of the same kind and exact expression. EQ(e) can also justify LE(e) or INT(e), since e=0. Exact is permitted only under the same checked sufficient conditions as terminal Exact: constant-zero EQ, constant-nonpositive LE, or an integer affine combination of input-declared integers when input integrality is enabled. An integer fact alone never proves equality or inequality.

An Absurd endpoint requires a fact with no variable terms and either positive LE constant or nonzero EQ constant. A variable inequality, INT fact, or EQ(0) cannot close a child. Every syntactic child is decoded and semantically checked before a parent fact is exported.

## Binary extension

The common 16-byte RPX header has version bytes `02 00` at offsets 4–5; other common fields are unchanged. Existing Step tags 0–2 retain their v1 payloads. New tags are:

| Tag | Payload after `tag(tag)` |
| --- | --- |
| 3 EqPair | `u32 id`, `Ref positive`, `Ref negative` |
| 4 Cases | `u32 id`, `tag(kind)`, `Expr expression`, `Expr split`, `option<Ref> integer`, `Derivation left`, `Derivation right` |

Kind tags retain 0 LE, 1 EQ, 2 INT. A Derivation is `array<Step>` followed by a DerivationEnd. A DerivationEnd has `tag(0)` followed by a Ref for Witness, or `tag(1)` followed by a Ref for Absurd. Other derivation terminal tags are invalid. These tags are a separate namespace from ordinary block End tags. A Derivation cannot contain a Return map or complete model-output checks.

Cases may occur in a root/ordinary block or in another Derivation's step array. Entering either child increments the same depth counter as an ordinary Split child; the shared maximum is 64 with root at one. Child steps, expression terms, scalar magnitudes, arrays and byte lengths use the existing budgets. Counts include all nested children. New tags under a v1 header are rejected before their payload is used; unknown tags under either version reject even in a branch that might close by contradiction.

## Text extension

RPA 2 is the exact header `RPA 2\n` followed by the existing strict JSON Certificate schema extended with these variants:

```
Step = existing variants
     | { "EqPair": { "id": u32, "positive": Ref, "negative": Ref } }
     | { "Cases": { "id": u32, "kind": "Le" | "Eq" | "Int",
          "expression": Expr, "split": Expr, "integer": null | Ref,
          "left": Derivation, "right": Derivation } }
Derivation = { "steps": Step[], "end": DerivationEnd }
DerivationEnd = { "Witness": Ref } | { "Absurd": Ref }
```

The notation above defines schemas, not a placeholder allowed in an executable proof. `cases/test88/proof.rpa` is a complete real RPA 2 certificate. Ref forms, rational strings and oldest-first assumption indices are unchanged. RPA 1 rejects either extension anywhere in its syntax; it cannot silently obtain v2 semantics. The RPA assembler still does no proof search, and the RPX verifier independently checks all mathematical premises.

## Implementation correspondence and tests

`proof.rs` defines Step, Derivation and DerivationEnd. `codec.rs` separately decodes every child and enforces version/depth/record rules. `rpa.rs` gates text versions. In `verify.rs`, `steps` handles each scalar rule, `split_facts` checks guard coverage prerequisites and both exact guard expressions, `derivation` checks Witness/Absurd, and Cases returns one validated parent Fact. `check_fact` is shared with output-obligation checking, but local lemma witnesses do not increment the output-obligation statistic. `Statistics.branches` includes both ordinary Split and local Cases points.

`crates/core/tests/local_cases.rs` contains nine executed tests: a binary-product alias with an independent fractional LP counterexample; inconsistent conclusions or types; sibling and parent-local reference attacks; transactional DROP; antisymmetry premise attacks; exact local contradiction; v1 downgrade rejection and immutable v1 vectors; combined depth/work budgets; and every adjusted-header truncation plus six byte mutations at every payload position. The reference `test88` certificate separately passes full real-model verification and targeted wrong-integrality/wrong-conclusion negative tests.

This is a soundness argument for the rules with implementation correspondence and bounded regression evidence. It is not a formal proof of the Rust compiler, arithmetic dependencies, decoder or implementation. No batch/theorem plugin, solver result, model name or hash can assert success through this extension.
