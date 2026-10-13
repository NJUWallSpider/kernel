# Actual normalization cases 47 and 48: proof paths without new trusted rules

The source and final models are complete. Exact file identities, dimensions,
source/target row and variable indices, full target-field checks, and remaining
proof work are recorded in `normalization_47_48_inventory.json`. The reproducible
read-only audit is `audit_normalization_47_48.py`; its last receipt is
`normalization_47_48_run.json`. These audits are untrusted preparation evidence.
Neither an audit PASS nor matching optimization values is a kernel certificate.

Both cases can be expressed with existing affine maps, exact scalar rules,
local Cases and IntervalLift; test47's reverse aggregation can use MenuLift.
No new dominance, normalization or conditional-integrality axiom is necessary.

## Test47: every attainable objective, continuous value and cardinality

The actual source has 151 variables and 13 rows. Its 150 binaries satisfy
sum x<=20. Twelve covering rows have nonnegative binary coefficients and coefficient
one on a continuous y in [0,10^12]. The normalized objective is
`y + (1/100000)*sum x`. The final model has 118 variables and the same 13 rows:
31 binaries are removed and two identical-column pairs become counts in [0,2].

The exact required contract is two integer directions with Objective Equal,
preserving y and total selected-binary count as explicit observations. Individual
binary identities, feasible-set bijection and LP equivalence are not claimed.
The audit independently checks all 7,440 dominance inequalities, each witness's
20 distinct retained alternatives, complete identical columns and domains for both
pairs, and every target row, bound, integer flag and objective coefficient.

For each removed binary v, process its 20 retained dominators w[0..19] in witness
order. They are *current* binary expressions after earlier exchanges. All old
coordinates remain present, and a symbolic current vector is updated after each
stage. Maintain exact facts for its binary domains, cardinality equality with the
original vector, and nondecrease in every covering row.

One IntervalLift batch introduces prefix Boolean products

```
p[0] = v,
p[j] = AND(v,w[0],...,w[j-1]), j=1,...,20.
```

An AND of n old binary expressions b is represented by a new continuous p with
lowers `[0, sum b-(n-1)]` and uppers `[b[0],...,b[n-1]]`. All lower/upper pairs
follow from 0<=b<=1 and are proved in the parent scope. The interval admits every
old point. Ordinary integer Cases first split the factor sum at n-1. On the
all-one branch, actual upper bounds and the branch inequality force each factor
one. On the deficient branch, balanced sum splits locate a zero factor: if the
left half is full, add its branch inequality to total deficiency to derive right
half deficiency; otherwise recurse left. A zero leaf forces p=0 using its actual
upper and lower rows. Thus INT(p) follows with O(n) leaves and logarithmic depth.
This is ordinary exact proof execution,
not a trusted Boolean-product theorem. Every product in a batch depends only on
the same pre-stage current vector, never on another new product.

The current cardinality bound gives `v+sum w<=20`. Summing the 21 upper bounds
of p[20] gives `21*p[20]<=v+sum w<=20`; divide by 21 and Round using INT(p[20])
to obtain p[20]<=0. Its lower bound proves p[20]=0. For j=0,...,19 put

```
s[j] = p[j]-p[j+1],
v_new = 0,
w_new[j] = w[j]+s[j].
```

The prefix AND identities prove s[j]>=0, s[j]<=1-w[j], and integrality.
These facts can be obtained with local Cases on p[j], w[j] and their defining
interval inequalities; no whole-model case tree is needed. Telescoping gives
sum s=v. Each new w is binary, total cardinality is unchanged, y is unchanged,
and for covering row a the change is
`sum_j (a[w[j]]-a[v])*s[j]>=0`. All multipliers are exact nonnegative rationals
checked against the actual source columns. Thus all original covering inequalities
remain valid. Dominators are retained, so a stage never reactivates a previously
removed variable. Thirty-one stages finish the simultaneous restriction.

The final Return sums the two identical pairs and copies the other normalized
coordinates. It still must discharge every actual target obligation, objective
and requested observation. Source prefix data and all extension laws stay in one
joint model. This does not combine incompatible individual replacement witnesses.

For the reverse direction each target count t in [0,2] is integer. MenuLift with
A=1,I=t,K=2 introduces one-hot states q0,q1,q2. Set the original pair to
`(q1+q2,q2)` and all 31 removed binaries to zero. The moment law gives pair sum=t;
the actual complete equal columns then preserve every row, objective and count.
The rest of the original coordinates, including y, are copied. No injectivity
claim is made, since both aggregation and dominance deliberately forget identities.

The forward nesting has 31 interval stages plus its Return, within depth 64.
The longest factor proof has 21 factors. Its balanced search gives final core
depth 38 and JSON container depth 126. The preserved first linear-search version
had core depth 53 but JSON depth 186, exceeding the assembler's serde limit 128.
It was rejected before proof execution; the complete RPA and raw failure receipt
remain in `cases/test47/attempts/linear-and/`. No parser limit was relaxed. Twenty prefix variables per stage give 620 new continuous
coordinates. Each stage has 270 interval rows and 460 pair premises before
canonical cancellation. Work/certificate size must be measured on the *complete*
proof. If the first complete representation exceeds default resources, preserve
that receipt and optimize fact sharing/proof representation without removing rows,
observations or cases.

## Test48: selector projection and minimum, not all objective values

The actual source has 1,747 variables and 2,107 rows; the target has 1,502 variables
and 1,860 rows. There are 150 original binary selectors, 170 binary copies,
1,425 optional binary children and two free continuous defining variables.
After contraction/fixing the target keeps 144 binary selectors, 1,357 continuous
children and the free objective coordinate. The read-only audit independently
checks every source row and bound under the affine LP reconstruction, every actual
target field, every removed-row bound tautology, and every child’s complete four-row
incidence. It also checks the 30 selector one-hot rows and five capacity rows.

The four certified requested directions are:

- source integer to target mixed-integer, Objective Equal;
- target mixed-integer to source integer, Objective NonIncreasing;
- both LP directions, Objective Equal, with the existing full affine inverse
  identities (both flags false).

Preserve all selectors: 144 retained coordinate pairs and explicit affine
constant-zero observations for the six eliminated selectors. These directions
prove equal feasible selector projections and equal infimal objectives, without
claiming equal nonoptimal attainable objective sets. For these actual models,
bounded selectors/children and exact free-variable definitions also imply finite
attained optima whenever feasible; neither feasibility nor an optimum value is
asserted by the audit.

For each of 475 disjoint blocks, contract mandatory copies to their selectors and
write `r=1-sum mandatory`. Actual packing plus child nonnegativity proves r>=0;
selector nonnegativity proves r<=1. Since selectors are integer, r is integer.
Keep duplicate mandatory selector occurrences with their multiplicity. This is
important when contraction creates a coefficient greater than one. Define each
eligible bit y as its selector, except that a fixed-zero child has eligibility zero.

Sort the three children by their exact transformed cost, ascending. The costs are
-999,-998,-997, but **the audit's child array is not always in this order**.
For example R0000036 lists costs -999,-997,-998. A positional interpretation would
choose the wrong priority. The independent inventory supplies `children_by_cost`.

Use one simultaneous IntervalLift batch for priority choices:

```
z1 = AND(r,y1)
z2 = AND(r,y2,1-y1)
z3 = AND(r,y3,1-y1,1-y2).
```

Use the same standard AND interval above. For already fixed-zero children retain
constant zero instead of creating an unnecessary interval. All input bits are
proved in [0,1]; every lower/upper pair is an ordinary linear consequence.
For each block, Cases on at most r,y1,y2,y3 (or equivalent factored cases) prove
all z are integer, their packing relation and their objective improvement. These
are local reusable conclusions; no branching over all selector assignments or all
blocks is required. The children share no coordinates across blocks, so all
interval choices coexist, and the global actual-model Return binds the one tuple.

For r=0, all old and new children are zero. For r=1 with no eligible child,
again all are zero. Otherwise let p be the first eligible child and c_p<0 its
cost. The new block cost is c_p. For any old feasible child vector,

```
sum c_j*x_j >= c_p*sum x_j >= c_p,
```

because ineligible children are zero, all eligible costs are >=c_p and sum x<=1.
This is an exact linear combination of actual domains, links and packing. It
works for fractional old children. The local choice cannot be advertised as
preserving their nonoptimal objective value.

Reconstruct *every* original coordinate together: selectors, mandatory copies,
fixed zeros, the chosen children, `d=475-sum children`, and the objective-defining
free z from its complete original equality. The latter includes direct selector
weights as well as mandatory-copy and child weights; reconstruct it from the
actual substituted row, not a partial verbal classification. Its change is the
sum of block cost improvements, proving the requested NonIncreasing obligation.
All source domains, links, one-hot rows, capacities, packs and defining equalities
remain ordinary output checks. The LP inverse pair uses the unrounded current
children instead and is an affine substitution with exact objective preservation.

## Evidence boundaries and attacks

Both cases now have complete actual-model VERIFIED receipts and targeted
rejections: `cases/test47/preparation.json` and `cases/test48/preparation.json`.
The inventory validates their artifact identities before reporting this status.
Test47 uses 38,691,982 work, 837 complete terminal obligations and 8,959 branches;
test48 uses 5,865,336 work, 26,660 obligations and 20,325 branches. The original
model files and production kernel were unchanged by their preparers. Case READMEs
state each exact contract and distinguish these recorded single replays from
isolated performance measurements. The following remain useful broader attack
families; the exact executed mutations are recorded in those receipts.

For test47 attack a removed or repeated dominator, a dominator in the removal set,
a negative dominance difference, changed cardinality bound, a missing prefix
factor, omitted p20 zero proof, swapped current/original candidate state, wrong
aggregate column and dropped objective/count/y observation. Check both all-zero
and full-cardinality selections, multiple removed selections and both counts at
0,1,2. A test affecting only one selected binary does not establish all stages.

For test48 attack an incorrectly cost-sorted block, an eligibility bit for a
fixed-zero child, dropped mandatory multiplicity, absent r>=0, false child INT,
an extra child incidence/coupling row, missing source bound or selector observation,
and a missing direct selector objective coefficient. Fractional old children must
exercise genuine objective improvement rather than only integer identity points.
Check both LP affine inverse compositions and the two distinct integer objective
relations; a NonIncreasing proof cannot silently satisfy an Equal request.

Every theorem premise is bound to the old scope, every lifted tuple is joint,
and every complete actual target obligation stays checked. Independent exact
structure checks guide certificate preparation; they are not proof authorities.
