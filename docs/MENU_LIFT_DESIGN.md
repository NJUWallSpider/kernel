# Optional menus and a complete bijection contract — design record

This design addresses the actual final models for test59 and test60. It does not
certify either case. The recommended design was subsequently approved for V7;
[MENU_V7.md](MENU_V7.md) documents the implemented model builders and their tests.
The structural evidence is in
`cases/test59/menu_structure.json`, `cases/test60/menu_structure.json` and
`audit/menu_structure.json`, produced by the independent, untrusted
`tools/audit_menus.py`. Production code and existing format semantics are unchanged
by this design record. The implemented V7 format document governs final accepted
syntax, tags and integration behavior.

## Actual obligation and independently checked structure

| Actual pair | Source variables / rows | Final variables / rows | Binary options | Menus | Packing groups | Continuous definitions |
|---|---:|---:|---:|---:|---:|---:|
| test59, MPS to MPS | 16,021 / 1,128 | 5,437 / 3,956 | 15,806 | 2,738 | 913 | 215 |
| test60, MPS to LP | 13,640 / 717 | 2,508 / 2,016 | 13,550 | 1,254 | 627 | 90 |

The audit reconstructs every actual target variable domain, row and objective and
compares all fields. It checks every original option coefficient, including zero
coefficients: 3,398,290 resource/objective progression comparisons for test59 and
1,219,500 for test60. These are preparation checks, not trusted premises.
The actual files and their SHA-256 identities are recorded in those artifacts;
the final LP of test60 must continue to be imported from its actual bytes.

Every original option is binary with bounds [0,1], belongs to exactly one menu,
and occurs in exactly one packing group whose row is the sum of its options
<= 1. Menus partition each group. Consequently each individual menu has at most
one active option; requiring exactly one would change the model. All other source
coordinates are continuous, each with one exact equality defining it as an affine
function of the options. Their actual bounds remain obligations. One such
coordinate defines the objective. The target contains only the menu coordinates.

For menu m, ordered options are x[m,0],...,x[m,K]. Its target coordinates are

```
A[m] = sum_j x[m,j]
I[m] = sum_j j*x[m,j].
```

A is binary; I is integer with 0 <= I <= K*A. Test59 has 39 singleton menus with
K=0 and no I coordinate; test60 has none. K denotes the contiguous option index,
not a capacity increment. Test60's physical increments of two do not create holes
in the allowed index sequence. Coefficients of every resource and objective are
`base + j*step`, hence their exact aggregate expression is `base*A + step*I`.
Equal resource or cost columns do not permit merging distinct option states.

The required result is an objective-preserving bijection between the *complete
integer feasible sets*, plus equality of the stated LP observation images.
Mutual preservation of resource totals alone does not establish the bijection.
The LP reverse section already has an affine formula, for K>0:

```
x[0] = A - I/K;  x[K] = I/K;  all other x[j] = 0.
```

For K=0 use x[0]=A. This preserves all menu sums and moments, and therefore all
audited affine resources. It is not an inverse on general fractional option
vectors. The existing ordinary checker must verify its complete source model,
objective and requested observations, just as for the forward affine map.

## Recommended minimum new existence rule: MenuLift

Proposed syntax, with exact field names still subject to implementation review:

```
MenuWitness { maximum_index: u32, activation: Expr, index: Expr, checks: Ref[] }
End::MenuLift { menus: MenuWitness[], body: Block }
```

Each expression uses only the current parent coordinates. A singleton uses the
constant zero index expression, even though the actual target has no I variable.
For each menu the kernel generates exactly six old-scope premises in this order:

```
LE(-A), LE(A-1), INT(A), LE(-I), LE(I-K*A), INT(I).
```

All six references, their types and expressions are checked before *any* new menu
domain or row is available. Premises for every menu use that same parent scope.
No certificate-supplied “binary” flag substitutes for bounds and integrality.
For an initial implementation, require `claim.input_integers == true`. This fits
the actual integer reverse claims and avoids making original integer declarations
active accidentally when a lift introduces integers during an LP proof. Supporting
that more general LP situation would require explicitly scoped integrality
permissions, not just flipping the existing input-mode bit.

Append K+1 integer variables z[0],...,z[K], each with bounds [0,1]. Append two
equality rows, in this order:

```
sum_j z[j] - A = 0
sum_j j*z[j] - I = 0.
```

Menus, variables and rows follow witness order; original variables, rows and
objective remain unchanged prefixes. The second row is retained for K=0: it is
the checked law -I=0. Zero coefficients are canonicalized normally. All menus
extend one parent point jointly. An empty menu list can be an identity extension;
it cannot supply a bijection proof by itself.

The child uses the complete actual output model. Every output bound, row,
required integrality, objective and requested observation remains an ordinary
obligation on one complete Return map. In particular, neither source packing,
resource bounds nor objective identities are accepted from the menu audit.
Premises may use valid current path assumptions. New variables and rows cannot
escape into a sibling. Existing affine `Claim.inverse` remains restricted to its
existing affine root-Return contract and rejects this endpoint.

### Soundness over real input coordinates

Fix any feasible current input point. The premises imply A is 0 or 1. If A=0,
I=0; choose all z=0. If A=1, I is one of the integers 0,...,K; choose z[I]=1
and every other z=0. This is a finite deterministic construction, with no solver,
search or rounding of input values. The ambient input can have real continuous
coordinates: only the checked expressions A and I must be integer-valued.
All menus have disjoint new coordinates and depend only on the fixed old point,
so the choices coexist.

The generated binary vector is also unique: sum z=0 forces all zero; sum z=1
forces exactly one 1, and its moment identifies its index. This mathematical fact
does **not** by itself establish a bijection of the actual models. An output map
could forget an original coordinate or impose further relations; its complete
model and inverse responsibilities still require proofs. The recommended design
below deliberately uses ordinary core rules to prove the needed injectivity,
without introducing a trusted one-hot equality theorem.

## Recommended complete contract: affine map, right inverse, injectivity

Let F:S->T be a previously requested and verified direction with a root affine
Return map, and let G:T->S be an opposing requested and verified total direction.
G may contain MenuLift or another admitted existence extension. Require matching
integer modes: F's input mode equals G's output mode, and F's output mode equals
G's input mode. Directional model orientations must be opposite.

A new caller-requested pair contract should state that this specific F is a
bijection and G is its inverse. The certificate must prove two additional facts:

1. F(G(t))=t on **every actual T coordinate**, using the same complete Return
   vector that proves G's output obligations, at every Return leaf of G.
2. F is injective on the complete actual S domain in F's input mode.

The first condition is generated by the kernel, not encoded as a partial list of
selected observations. For j=0,...,dim(T)-1 the obligation is
`EQ(F[j](G.map) - parent_original_coordinate[j])`. Its right-hand coordinate is
always in G's original input prefix, even after nested extensions. Constants in
F and G are substituted exactly. Absurd leaves remain vacuous only after their
normal checked contradiction. All leaves of a split must discharge their own
obligations. No independently supplied replacement for F or G is accepted.

The second condition can reuse the existing scalar rules through the following
generic construction. It adds no menu-specific mathematical axiom.

### Fresh paired domain and equality proof

Given the actual S model with n variables and r rows, construct a fresh model P:

- variables x[0..n] followed by x'[0..n], copying every actual bound and declared
  integrality flag; the proof context uses F's original input mode for both;
- all r actual rows on x, followed by all r rows with variable indices shifted
  by n, preserving all row constants and finite sides;
- one equality `F[j](x)-F[j](x')=0` for every actual target coordinate j, in order.

Use a zero objective for this domain-only proof: neither original objective is a
constraint, and their values are already covered by directional contracts.
Generated internal names must be unique. Names, certificate hints, input file
hashes and audit classifications never replace copying/checking actual fields.
F is taken directly from the same verified, indexed forward claim and block.
The kernel does not accept a separate list of observation expressions.

An `EqualityProof { steps: Step[], checks: Ref[] }` starts fresh live facts and
path assumptions at depth one. It executes existing Lin, Round, EqPair, Cases,
Drop and other already admitted scalar rules, then checks exactly n goals:

```
EQ(x[i] - x'[i]), i=0,...,n-1.
```

All coordinates are included, including continuous auxiliaries and coordinates
absent from F. Missing or surplus checks reject. No Return, existential endpoint
or unbounded proof search is part of this equality-proof root. Existing local
Cases can close an infeasible branch by Absurd. Shared work, depth and live-fact
limits apply, with no access to a directional proof's registers, sibling facts
or another pair proof. A direct helper must retain all original model validation
and mode checks rather than relying on a caller having performed them.

P is precisely the set of pairs of S points sharing the full F value. Proving
every coordinate equal on P therefore proves injectivity, including when S is
empty. F's totality and the checked right inverse give surjectivity: every t has
some G(t) with F(G(t))=t. For any s, G(F(s)) and s are both in S and have the same
F value, so injectivity gives G(F(s))=s. Thus F is a bijection. Even if an existence
lift had many witnesses, every resulting G output is the same actual S point.
Objective Equal on the directional claims supplies the requested pointwise
objective preservation; the pair contract must not silently invent that property
when its constituent directions requested Objective None.

For the actual forward maps, the paired domain would have 32,042 variables and
7,693 rows for test59, and 27,280 variables and 3,942 rows for test60, before proof
facts. These are derived dimensions, not measured memory or verification costs.

### Ordinary scalar proof of menu injectivity

The duplicated-domain proof need not enumerate a product of menu states. For each
menu, packing plus nonnegativity proves its sum <=1 on each copy. The copied
binary declarations supply integrality. Equality of the forward coordinates
supplies equal activation and, for K>0, equal moment. A singleton's one coordinate
already equals its activation, so its equality is immediate.

For each coordinate j of a non-singleton menu, apply integer Cases to x[j] and
x'[j]. The two equal-value branches prove x[j]-x'[j]=0 directly from their bounds.
Consider the mixed branch x[j]=1 and x'[j]=0; the opposite mixed branch is symmetric.
Packing and nonnegativity force the selected side's total A=1 and moment I=j.
For example, its moment is bounded below by j*x[j] and above by
`K*A-(K-j)*x[j]`, which both equal j. Thus the other copy has total 1 and moment j.

Put `L=sum_{k<j} x'[k]`. Derive INT(L) from the declared integer coordinates and
split into L<=0 and L>=1. On the first branch, nonnegativity, total=1 and x'[j]=0
give

```
I' >= (j+1)*(A'-L-x'[j]) >= j+1,
```

contradicting I'=j. On the second branch use

```
I' <= (j-1)*L + K*(A'-L)
   = K*A'-(K-j+1)*L <= j-1,
```

again contradicting I'=j. The inequalities are explicit weighted sums of
nonnegativity and the copied equalities; all multipliers of LE premises are
nonnegative. The j=0 branch has L=0 and its L>=1 side is immediately absurd;
j=K works as well. Every use of integrality is local and proved. Fractional
vectors do not satisfy this argument.

This is at most five binary Cases nodes per coordinate, depth three beyond the
root, with O(K+1) scalar references per coordinate. Across the menu it is
O((K+1)^2) references, not an exponential tree over menus. Existing fact sharing
can retain common packing and observation equations and drop temporary facts.
No new trusted one-hot inference is necessary for the observed K<=12 workload.

Finally each source continuous coordinate has a copied defining equation. Subtract
the two definitions and combine the already proved option-coordinate equalities
to derive its equality. This verifies uniqueness of *every* continuous auxiliary;
a free, duplicated or underdetermined auxiliary would leave an unprovable goal.
These checks use actual source rows, not the preparation audit's assertion of
unique definitions. The pair checker requires all n goals regardless of how the
certificate author classifies coordinates.

## Proposed contract and wire surface

One concrete minimal schema is:

```
BijectionClaim   { forward_claim: u32, reverse_claim: u32 }
BijectionWitness { claim: BijectionClaim, injectivity: EqualityProof }
Request.bijections: BijectionClaim[]           // default empty for old requests
Certificate.bijections: BijectionWitness[]     // default empty for old certificates
```

Match the complete ordered claim array to the separately supplied request before
execution. Reject invalid indices, equal indices, mismatched orientations/modes,
duplicate pairs and a forward block without a root affine Return. Both directional
claims must independently pass. Several pair contracts can refer to a direction;
all their composition obligations are generated in request order, then coordinate
order. They are appended after that Return's existing V6 obligations, leaving its
old obligation order intact. The decoder and validator must inspect every proof
root even if an earlier branch is infeasible. An empty ordinary claims/points
request must not become acceptable from an unbound proof-only payload.

The new version would add a distinct MenuLift endpoint tag, an explicitly versioned
trailing bijection-witness array, and the EqualityProof encoding (array of existing
Step followed by array of Ref). MenuWitness encodes u32 K, two Expr and array<Ref>.
Use a new RPA/RPX version; do not reinterpret the existing affine inverse field or
old Return witness counts. Old versions have no pair-array bytes and reject the
new endpoint/contract. Writers discover features in all nested endpoints and
equality proofs. Strict JSON rejects unused or unknown fields. Existing scalar,
count, byte, reservation and depth rules apply cumulatively across these roots.
No MCM change is needed. Final tag/version assignments belong in the implemented
format document, not in this unimplemented proposal.

## Alternative: unique-extension section proof

The parent's alternative avoids duplicating S. If G has exactly one MenuLift over
T followed by an affine Return H, let E(T) denote that *same* generated extension.
Its menu tuple is unique for every T point. Supply an ordinary affine section
J:S->E(T) whose old-coordinate prefix is F, prove every E(T) bound, integrality and
row, and prove H(J(s))=s on every actual S coordinate. Also prove F(H(e)) equals
the old T prefix on every feasible extension e. Then J(s) must be the unique
extension of F(s), so both compositions are identities. Original options provide
the section's menu coordinates in the actual cases; continuous source auxiliaries
are covered by the H(J(s)) identity obligations.

This is mathematically sound and potentially smaller. The implementation must bind
J to the *exact indexed reverse witness, generated model, body and Return*, not a
similar separately supplied extension or alternate map. Initially it would need
strict shape restrictions: root MenuLift with a root Return body, no branching,
nested FlowLift/IntervalLift or unproved uniqueness. An extension classified merely
as existential is insufficient. Supporting arbitrary unique-extension stacks later
requires composition of scope paths and uniqueness evidence for each stage.

Compared with the recommended paired-domain approach, it saves a duplicated model
and menu Cases proofs but adds trusted uniqueness use, section-model binding,
nonlinear inverse-path restrictions and an additional synthetic mapping proof.
The generic injectivity design adds a deterministic model copy and equality-goal
driver, using already tested scalar reasoning; it also applies to other affine
maps and arbitrary valid inverse existence proofs. That is the recommended first
implementation for the observed small K. If measurements show its proof or memory
cost is material, the section variant can be introduced separately after an equal-
contract comparison. A trusted batch one-hot equality theorem is another possible
later optimization, not currently justified by a demonstrated failure.

## Resource obligations

MenuLift must preflight sum(K+1), two rows per menu, generated support, all six
premise counts and the combined copied-model dimensions with checked arithmetic.
Charge scans and copies, including parent model data, before allocating expanded
buffers; use fallible reservations. Check every rational product and intermediate
constant when forming K*A, negative expressions and row laws. All expressions are
validated in the parent dimension before extension. Construction work is linear
in generated variables and expression support; charge that logical work even
though production need not evaluate a concrete input point.

For an injectivity proof preflight 2*n variables, 2*r+dim(T) rows and complete
support of both model copies plus every F difference. Check shifted indices fit
the existing index width and model limits. Copying, canonicalization, substituted
expressions, all scalar proof operations and all n terminal equality obligations
consume the same remaining request budget. Do not restart a fresh default budget
per direction, menu, pair or proof root. The repeated copied source must not be
silently omitted to meet a budget. Report generated dimensions, logical proof
work, physical certificate bytes and physical memory separately. This document
contains no measured speed or memory claim.

## Required positive, negative and independent evidence

Before certification, implement and run at least these checks:

- Independent Fraction construction for K=0,1 and varied K, A=0/1, every valid
  I, nontrivial affine A/I, real-valued other coordinates, and simultaneous menus.
  Check inactive all-zero, active index-zero and active endpoint states separately.
  For small K exhaust all binary vectors to check the existence/uniqueness claim.
- Reject negative or fractional I, I>K*A, noninteger A, absent upper/lower/INT
  premises, an omitted or false middle premise, and references to fresh/sibling
  coordinates. Refuse MenuLift in the unsupported relaxed input mode. Check all
  new binary domains and both rows, including K=0's second equality.
- Attack the ordinary body with wrong source packing, altered resource coefficient,
  missing original option, duplicate original assignment, wrong objective constant,
  omitted binary bound, an integer-valued-looking continuous variable and a new
  coupled constraint. No matrix audit, name or model digest may bypass these.
- For injectivity reject omitted/mutated paired-source rows or bounds, either copy
  in the wrong integer mode, an omitted middle F coordinate, unequal treatment
  of F's constant on the two copies,
  a map taken from another claim, incorrect index shifting, a missing continuous
  equality goal, and a surplus check. Construct a free original auxiliary which
  has identical F values but distinct values to prove the checker rejects an
  option-only “bijection.”
- Demonstrate that the LP aggregation for K>=2 is noninjective: with A=1,I=1,
  option 1 alone and half each of options 0 and 2 have the same aggregate value.
  A mixed-domain or incorrectly retained VarInt premise must not certify it.
- Check a genuine surjection with two original points per target point, and a
  genuine injection whose image misses a target point. They respectively falsify
  injectivity and the full right-inverse obligations. Neither may pass merely
  because both supplied directions are feasible maps with partial observations.
- Mutate the reverse map on one actual target coordinate, including a coordinate
  unused by its resources/objective. Omit an I coordinate or inactive A distinction;
  require failure even when all resource/cost values still coincide. Test a target
  with duplicate resource columns so objective equality alone cannot hide it.
- Test two equal-value and both mixed-value Cases branches for every j, endpoint
  j=0/K, singleton menus, empty domains, constants and zero-dimensional models;
  independently enumerate small paired integer domains and compare equality goals.
- Attack parent/sibling/previous-root fact leakage, ID reuse after Drop, wrong
  branch integrality and a contradiction from an unreachable *other* branch.
  Test nested MenuLift bounds, composite right-inverse obligations at every leaf,
  and rejection of the old affine inverse contract on the new endpoint.
- Exercise malicious K/count products, combined model/term caps, rational bit
  growth, cumulative work limits and maximum depth. Add independent wire vectors,
  truncation/version downgrades, unknown/reserved fields and payload mutations in
  nested menus and injectivity proofs, with exact request binding.
- Rebuild the actual test59/test60 RPA/RPX from their unchanged input/final files.
  Run forward integer, reverse integer with MenuLift, the new complete bijection
  pair, and both complete LP observation directions. Check all original options
  and auxiliaries. Keep prior partial receipts marked partial until this full
  contract passes, and record certificate preparation separately from verification.

The recommended new trusted mathematical content is the optional-menu existence
rule. The pair-domain construction and composition/equality drivers add trusted
binding code but use existing scalar inference. Their semantic arguments and
independent tests are bounded evidence, not a formal proof of the implementation.
