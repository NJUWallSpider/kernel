# Actual test78 certificate construction in progress

Owner draft_audit. No production change planned. Complete source-to-target Equal
and target-to-source NonIncreasing MI claims; preserve all 1,424 auxiliary binary
coordinates in both directions. No raw original-source projection or LP equality
claim. Report says 3,472 source binaries (2,048 objective -1 choices +1,424 aux),
16 capacity groups of 128 choices, cap9; 768 single-aux choices aggregate into
16 continuous pools. Target has 1,280 retained continuous choices and binary aux.

Use actual source row classification and audit pools only as checked hints. All
4,528 implications x-z<=0, 16 capacities and 89 aux packing rows must be covered.
Forward map retains coordinates and replaces each pool with sum48 original
members: bounds from source bounds, aggregate from sum individual implications,
capacity identical, objective identical. Complete output model obligations.

Reverse existing-rule construction:

1. Every old source choice has availability a=AND(its 1..6 aux). Single-factor
   availability is the actual aux. For 1,280 multi-factor choices use one joint
   IntervalLift: lower[0,sum factors-n+1], upper[each factor]. Compatibility from
   aux bounds. Short-circuit binary Cases give INT a and old continuous x<=a:
   first factor zero closes with actual implication x<=factor; all-one leaf uses
   interval lower a>=1 and old x<=1. Store a>=0,a<=1,a<=eachaux,INT a.
2. In each capacity group choose the 128 original choices in source-index order.
   Prefix S_i=sum a_1..a_i has 0<=S_i<=i, INT S_i. Prefixes i<=9 have C_i=S_i.
   For every i=10..128, one joint MenuLift after availability with activation1,
   index S_i, maximum_index=i. There are 1,904 menus and 133,280 menu bits.
   Define C_i=sum_j min(j,9)*menu_i[j]. Count is integer, 0<=C_i<=9.
3. Define returned binary choice w_i=C_i-C_(i-1), C_0=0. For i<=9 use a_i.
   For i>=10 Cases on INT(S_prev-8): left S_prev<=8, right S_prev>=9.
   Left: S_i<=9 follows S_prev<=8 and a_i<=1. Prove C_prev=S_prev and C_i=S_i,
   so w_i=a_i. Right: S_i>=9 from S_prev>=9 and a_i>=0; both C's equal9, w=0.
   Export separate LE(-w), LE(w-a); INT(w) is ordinary integer linear sum of
   count facts. Then w<=1 and all w<=aux follow. Capacity telescopes to C_128<=9.
4. Actual target capacity gives T=sum retained x+pool<=9. Actual pool aggregate
   plus all retained x<=availability gives T<=S_128. Cases on INT(S_128-9):
   left S<=9 yields C=S, right S>=10 yields C=9. Thus T<=C in either branch.
   Sum 16 such facts proves complete reverse objective nonincrease. Aux rows and
   projections remain exact, all original bounds/Int/rows/objective are checked.

Generic menu clamp facts use ordinary Lin/EqPair/Round, not a new theorem:

For menu with K>=10, S=Σj*m_j, Σm_j=1 and C=Σmin(j,9)m_j:

- Given S<=U with U<=9, tail B=Σ_{j>=10}m_j. From moment and nonnegative bounds,
  B-S/10<=0. Add (S-U)/10, Round using INT B: B<=0 (ceil(-U/10)=0). Weighted
  tail D=Σ(j-9)m_j<=max(K-9)*B by nonnegativity. This proves both C-S<=0 and
  S-C<=0, hence EQ(C-S). For i<=9 C=S identically and no fact is needed.
- Given S>=L>=9 (L<=K), low B=Σ_{j<=8}m_j. K*sumEQ-momentEQ plus lower bounds
  gives (K-8)B+S-K<=0. Divide K-8 and add (L-S)/(K-8), Round INT B to B<=0,
  since (L-K)/(K-8) lies in(-1,0]. Use weights (9-j)<=9 to prove 9-C<=0;
  C-9<=0 follows menu sum and lower bounds. EqPair yields EQ(C-9). Previous
  prefix K=9 without a menu uses its known S<=9 and branch S>=9 directly.

A new helper must mimic Menu builder layout: append K+1 binary[0,1] variables per
menu, then two rows per menu (sum=1, moment-S=0), preserving old prefix. Interval
layout helper is tools/prepare_test23.py::extend. Branch helper is Proof from
prepare_test48.py; pass old lookup to new extended Proof to avoid building a
large redundant fact dictionary. A Round helper should independently check
LE expression minus INT expression is constant and ceil it using Fraction.

Current supporting status: test21 complete VERIFIED +6 attacks, README/receipt
saved. test77 complete VERIFIED +6 attacks on old/new binaries with same bytes/
statistics; model_layer independently reviewed bounds/recurrences. Arithmetic
benchmark independent review passed 1176 processes; root corrected both reporting
notes and merged shortcuts plus two resource fixes. Stable binary is
target/validation-checkpoint-v7-rational/release/rpx, SHA de58aded8f26a600576a87ac16bdf7e4328397cd469959146bb3271c231a53b0.
