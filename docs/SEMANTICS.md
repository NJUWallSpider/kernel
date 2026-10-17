# RPX optimization-equivalence semantics

RPX has one purpose: certify optimization equivalence between two complete rational MILPs. It does not accept caller-selected properties or a separate Contract/Request.

## Complete models

For a minimization model M, let P_M be its feasible set including every declared integer coordinate, finite variable bound, and row side. The objective f_M includes its constant. The trusted MPS/LP reader interprets decimals exactly; maximization is normalized by negating the entire objective. See [MPS](MPS_V1.md) and [LP](LP_V1.md).

Continuous variables remain real. Removing an integer-mode switch does not turn continuous coordinates into integers.

## Fixed proof obligation

A certificate contains exactly `forward: Block` and `reverse: Block`. The kernel requires:

- For every x in P_M, the forward proof constructs y in P_N with f_N(y) <= f_M(x).
- For every y in P_N, the reverse proof constructs x in P_M with f_M(x) <= f_N(y).

These total constructions imply simultaneous feasibility/infeasibility, equal extended infima, and preservation of objective unboundedness. If y is target-optimal, its constructed source point is source-optimal. The maps need not be inverses or preserve suboptimal objective values. LP relaxations may differ.

Both proof trees are mandatory, independently scoped, and share one work budget. `VERIFIED` is returned only after both complete trees pass. A valid proof of only one direction has no public certification entry point.

## Facts and scalar rules

The current scope contains affine facts `Le(e)` (e <= 0), `Eq(e)` (e = 0), and `Int(e)` (e is integer-valued). Input bounds, row sides and declared integrality provide the base facts. No objective cutoff, halfspace restriction or strict predicate is assumed at the root.

`Lin` combines supplied facts exactly. A Le combination permits arbitrary multipliers of Eq facts, nonnegative multipliers of Le facts and a nonpositive constant. An Eq combination uses Eq facts and zero constant. An Int combination uses arbitrary rational multiples of Eq facts, integer multiples of Int facts and an integer constant.

`Round` takes Le(a) and Int(z) with identical variable coefficients and derives Le(z + ceil(a.constant - z.constant)). `EqPair` derives Eq(e) from Le(e) and Le(-e). `Drop` removes a visible local fact; duplicate definitions, absent references and use-after-drop are rejected.

`Plotkin` checks actual binary domains and all supplied clique premises before deriving its code-distance bound. Labels do not themselves assert any constraint. See [the format](FORMAT.md#steps) and the independent exact test vectors.

## Scope and exhaustive branching

`Cases` proves one specified fact in both exhaustive child scopes and exports only that fact. `Split` supplies a complete output construction in both children. A real split covers e <= 0 and -e <= 0; a split supported by Int(e) covers e <= 0 and 1-e <= 0. Both branches are checked. Children inherit parent facts; sibling facts and assumptions never cross scopes.

`Absurd` closes a branch only using a checked constant-positive Le fact or a constant-nonzero Eq fact. It cannot close a feasible branch merely because no optimum exists.

## Joint construction rules

A lift checks every premise in the old scope, then introduces a simultaneous extension whose existence follows from a trusted constructive lemma. New variables and rows are fresh, the original coordinates remain a prefix, and the objective is unchanged. The child must still prove all actual output obligations.

| Lift | Joint construction |
| --- | --- |
| Interval | Choose a real value between all affine lower and upper bounds after every pairwise lower <= upper premise is checked. |
| Menu | Given binary activation A and integer index I with 0 <= I <= K A, choose binary q_0,...,q_K with sum q = A and sum j q_j = I. |
| Signed | Given C >= 0, binary Z and -C Z <= F <= C Z, construct p,n >= 0 and binary u,v with p-n=F, u+v=Z, p<=C u and n<=C v. |
| Flow | Decompose a nonnegative common-source aggregate flow into the supplied demand commodities, retaining all arc totals including circulation. |
| Subflow | Retain a simultaneous demanded flow g with the same balances, 0<=g<=f, and g_e<=total demand. Circulation may be discarded. |

The lift implementations and existence lemmas are trusted. Successful authoring preparation alone proves none of their premises. A generic solution-recovery executor is not currently exposed.

## Return obligation order

`Return` supplies one affine expression for every output variable. The kernel derives the following obligations from the complete output model, using that same tuple:

1. Each variable's finite lower bound, finite upper bound, then integrality if declared.
2. Each row in order: equality when its two finite sides agree; otherwise its finite lower then upper side.
3. The objective difference f_output(map) - f_input <= 0, always present, including zero objectives.

There is one reference per obligation, with neither missing nor surplus references. An Eq fact can discharge the identical Le or Int expression. `Exact` is allowed only for a literal tautology: zero constant equality, nonpositive constant inequality, or an affine integer combination of actual integer variables with integer constant. It is not an unchecked assertion.

Projection equalities, inverse identities, bijections, global objective bounds, restricted domains, LP relations, point witnesses and standalone improvements are absent from the proof schema and checker.

## Soundness and resource policy

Induction over the finite proof tree preserves validity of every visible fact. Exhaustive branches cover every input; each lift supplies a joint extension; each nonempty leaf returns one complete feasible output with nonincreasing objective. Applying this argument to both directions establishes the fixed guarantee.

Exact import, rational arithmetic, scalar rules, scope handling and the constructive lemmas belong to the trusted base. The Rust implementation is not mechanically verified. All decoder bytes, including both branches, are interpreted before proof execution. Work, live-fact, depth, item-count and rational-size limits produce `RESOURCE_LIMIT`, which certifies nothing. `INVALID` rejects the submitted proof; it does not establish that no valid reformulation proof exists.

## Historical formats

RPX 11 replaces the earlier configurable directional-claim format. Old RPX versions and their benchmark receipts retain their historical meaning; the current decoder rejects them. Historical migration is pinned to a pre-change commit and is not part of the current pipeline. Migration remains untrusted and cannot bypass verification.
