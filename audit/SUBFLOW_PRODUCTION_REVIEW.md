# Independent production subflow review

Reviewer: root, distinct from the isolated/production builder author. Date:
2026-10-11. Scope: `subflow.rs`, its integration in `proof.rs`, `codec.rs`,
`verify.rs`, and the correspondence to `docs/SUBFLOW_DRAFT.md`. Root authored
the integration, so review independence applies to the builder and its lemma,
not to root's own integration; integration additionally has the author's tests.

Result: no P1/P2 issue found in this review. This is a source/math review and
finite execution evidence, not a formal correctness proof.

The finite supersink path-extraction argument applies to real coordinates, not
only rational flows. A positive source residual implies a positive path by the
reachable-cut divergence contradiction. Each simple path subtraction eliminates
at least one positive residual arc permanently. Termination is bounded by the
original arcs plus positive demand arcs, without a minimum rational decrement.
Path weights sum to B and each arc occurs once per simple path, giving the
simultaneous upper bound B. Demand-arc saturation proves every sink balance;
remaining circulation and loops can be discarded. Multiple groups share an old
point and have disjoint new coordinates, so joint existence follows.

The implementation rejects source-equal sinks even for zero demand, aggregates
duplicate sinks exactly, permits empty/zero demands and zero arcs, and requires
nonempty node/group lists. It creates exactly m continuous [0,B] coordinates,
n divergence equalities and m subflow inequalities per group, in documented
order. Incidence terms are emitted in increasing edge-coordinate order; loops
cancel on both old and new divergence sides. All affine constants are included
in old nonnegativity/balance premises and in g-flow rows. The original variable,
row and objective prefixes remain unchanged, and names have no logical role.

Preflight checks bound total dimensions and combined old, generated and premise
support before allocating the extension. Sparse divergence merges are charged;
every accumulated demand/RHS/divergence constant is checked, as are canonicalized
coefficient sums. Remaining work is passed into the builder and then charged
into the caller's shared statistics. Depth and old-scope reference resolution
occur before child execution; the construction does not discharge its own
premises. No old flow expression can capture a simultaneously appended variable.

The builder's finite test evidence is nine isolated tests including 983 Fraction
fixtures; production currently has fourteen dedicated tests, adding full proof
execution, complete output/caller binding, old-scope rejection, nested/sibling
scopes, all truncations, old-header rejection and work/depth boundaries. The
full core log `audit/subflow-next/production-full-tests.log` records 250 passes
at this working snapshot. Later new tests can increase that count. Actual test58
is a separate integration obligation and was not yet counted in this review.

Known trust limit: this builder implements a mathematical existence theorem.
`check_fact`, `Model::validate` and the child verifier do not independently prove
that its generated rows are the intended jointly satisfiable extension. Shared
support, exact arithmetic libraries and runtime infrastructure remain trusted.
