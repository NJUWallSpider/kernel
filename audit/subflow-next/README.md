# Isolated joint subflow candidate

This directory is an **unregistered candidate**, not a production rule, protocol
release, complete test58 certificate, or performance result. No production
proof/codec/verifier file is changed by this crate. Its mathematical review is
[`../CAPABILITY_CLOSURE_REVIEW.md`](../CAPABILITY_CLOSURE_REVIEW.md).

The crate uses the preserved `delivery-78-working-source` core for exact model
types/validation and directly includes that same snapshot's `build_support.rs`.
The dependency is an internal working snapshot, not a claim that V9 is frozen.
`receipt.json` binds source, fixture, dependency manifest, and execution log.

## Interface and exact layout

`prepare_unchecked_extension(input, witness, limits)` returns
`UncheckedSubflowExtension { model, premises, statistics }`. The local types are:

```text
SubflowWitness { nodes:u32, arcs:Vec<(u32,u32)>, groups:Vec<SubflowGroup> }
SubflowGroup {
    source:u32, demands:Vec<(u32,Q)>, flows:Vec<Expr>,
    nonnegative:Vec<Ref>, balances:Vec<Ref>
}
```

For each group in order, let `B=sum(demand)`. The group returns m nonnegativity
premises `LE(-flow[e])`, then n balance premises `EQ(div(flow)[v]-b[v])`, where
divergence is **outgoing minus incoming**. It appends m continuous variables in
arc order, each with `[0,B]` bounds, then n equality rows `div(g)=b` in node order,
then m inequality rows `g[e]-flow[e]<=0` in arc order. New groups have disjoint
coordinate blocks. Every original model field remains an exact prefix.

Require n>=1 and at least one group. Empty arcs and empty demands are allowed.
Every demand is nonnegative and its sink must differ from its group's source,
**including a zero demand**. Duplicate sinks aggregate exactly. Loops and parallel
arcs are allowed. All flow expressions refer only to the old input scope.

The caller must establish **every** returned premise in that old scope before
using any generated variable or row. The helper deliberately does not resolve
references or declare acceptance. The joint-existence lemma, including the
appended domain formulas, is trusted inference logic; the shared helper supplies
only checked mechanical operations. No path search runs in the candidate builder.

## Independent evidence

The Python Fraction oracle uses adjacency-list supersink path extraction,
records simple paths and exact weights, and independently computes all expected
premise and generated-row fields. It includes 983 cases: 244 rebased legacy
cases, 5 explicit edge cases, 374 exhaustive small-flow cases selected by balance,
and 360 random graphs with shared arcs, cycles, permutations and rational scaling.
Every case checks one **common** retained flow, not separate row witnesses. Rust
also checks each recorded path, complete demand delivery and the extraction bound.
Rational sampling supplements the mathematical proof for all real feasible flows;
it does not replace that proof.

Nine test functions cover all oracle fields and paths, multiple simultaneous
groups and affine constants, full prefix/name preservation, empty/zero demands,
source/sink rejection, invalid middle groups and future-coordinate references,
false premise propagation, two positive supplies, wrong incidence/negative flow,
independent-clipping failure, intermediate arithmetic limits, and exact work limits.
The old prototype's failed classification test is retained in its historical log.
The new candidate normalizes malformed direct-API errors to `INVALID` and budget
errors to `RESOURCE_LIMIT`.

Reproduce from the repository root:

```sh
python3 audit/subflow-next/generate_oracle.py
cargo test --manifest-path audit/subflow-next/Cargo.toml --target-dir target/subflow-next --offline --locked
```

No new binary record exists here. Whole-context old-scope discharge, sibling/dead
references, nesting, request binding, byte attacks, full actual test58 replay and
measured multi-scale costs remain production-integration responsibilities.
