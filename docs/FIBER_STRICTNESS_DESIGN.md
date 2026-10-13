# Proposed strictness of a partial affine projection (not implemented yet)

The V3 `Strictness` shortcut only handles a complete coordinate permutation.
Actual test18 drops four budget-only binary coordinates (relaxed in the LP),
alongside other eliminated variables; its claimed strict projected LP
relation needs a more general proof. Do not relax the V3 rule or count a partial
point check as a separation proof.

A proposed V6 `PointClaim::FiberStrictness { inclusion_claim }` refers to an already
verified LP-to-LP directional claim. The observations of that claim are the ordered
coordinate projection pairs followed by its affine projection pairs. Write their
input expressions as a(x) and output expressions as b(y). The verified total map
proves a(P_input) is contained in b(P_output).

Its PointWitness supplies a complete output-model point y and a refutation Block.
The checker first checks every output LP bound and row at y, and evaluates b(y)
exactly. It copies the actual input model and appends one equality for EACH
observation: a_i(x)=b_i(y). It then checks that this complete fiber model is
infeasible by existing proof rules, using LP mode (VarInt is unavailable).

The refutation must have only Absurd leaves, with ordinary Split internal ends.
Return and existential extension ends reject in this initial scope; local Cases
steps remain allowed with their established semantics. Absurd still requires a
checked constant-positive LE or nonzero constant EQ. No solver or hidden search
is involved. Every expression, row and reference is checked normally. The copied
input rows and variables retain their original indices; fiber equalities are
appended in observation order.

Soundness: y proves b(y) belongs to the output projection. Fiber infeasibility
proves no input x has a(x)=b(y), so b(y) is outside the input projection. Combining
this with the already-verified inclusion gives strict containment. Observations
need not be injective, surjective or independent. With no observations, this is
still sound exactly when the input is empty and the output is nonempty.

PointWitness can gain a versioned optional `refutation: Block`; FiberStrictness
requires it, and other point variants reject surplus refutations. Earlier wire
versions decode the field as None. Required-version discovery, structured decode
and depth limits must traverse every refutation even before point execution.
Caller request equality must bind the exact point-claim variant and claim index.

Before constructing the fiber, validate coordinate/affine observation dimensions
against the original pair, require both LP mode flags, and require that inclusion
proof has already succeeded. Exact point evaluation, model copy, generated rows,
refutation execution and nesting consume the SAME request-wide remaining budget.
The fiber helper returns no acceptance on its own. Every refutation starts fresh
with no map-proof live facts or branch assumptions. It may reference only actual
input facts and the appended, kernel-computed equalities.

Required attacks: failed inclusion with otherwise valid separator; infeasible
output point; omitted/mutated fiber observation; wrong affine sign or constant;
integer-only contradiction used for an LP fiber; Return used instead of Absurd;
invalid/dead/sibling reference; cross-witness state leakage; unsupported end;
wrong claim index; new payload under old wire version; missing and surplus
refutations; nested byte/count/depth/work limits. Independent small rational
polytope examples must confirm positive and negative projection strictness. Actual
test18 must check its entire source point and complete real model pair.
