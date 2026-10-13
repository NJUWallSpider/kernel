#!/usr/bin/env python3
"""Read-only corpus analysis; writes only the two remaining-requirements reports.

Assessments below are manually reviewed proof routes, not kernel certificates.
The immutable compressed acceptance snapshot fixes the denominator.  Later
receipts are supplemental evidence and never replace the snapshot's status.
"""
import gzip
import hashlib
import json
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SNAPSHOT = ROOT / 'audit/remaining_requirements_acceptance_snapshot.json.gz'
RAW_SHA = 'cf999d2018b0120c1f85733cf3ff87dcce3750aca4a67a367ea6baf10b45fe5c'
EXPECTED = [8,10,17,22,24,29,31,32,34,36,37,39,41,42,45,46,51,52,53,55,56,58,61,62,64,66,67,72,73,74,76,80,81,82,83,85,86]
ROWS = []

def case(n, contract, lp, rules, route, resource, confidence='high',
         gap=None, caveat='', clusters=()):
    ROWS.append(dict(case_id=f'test{n}', actual_contract=dict(integer=contract, lp=lp),
        existing_composable_rules=rules.split(', '), minimal_proof_route=route,
        representation_or_resource_risk=resource,
        new_mathematics_or_contract_gap=gap or dict(kind='none_identified', statement='No additional trusted mathematical rule is presently justified by the reviewed route.'),
        confidence=dict(mathematical_route=confidence, implementation='not_yet_executed',
            interpretation='A route assessment is not a soundness proof or VERIFIED status.'),
        material_or_error_risk=caveat or 'Actual final model pair is present. No refutation of the committed transformation was found in this report audit; the proposed certificate still must check every actual bound, row, integrality and objective obligation.',
        capability_clusters=list(clusters)))

case(8,
 'Same complete integer vectors and objective, in both directions.',
 'Target relaxation is a strict subset of source relaxation, on the same coordinates.',
 'Lin, Cases, inverse, Strictness',
 ['Prove the 441 redundant gates by actual resource-row containment and 315 cardinalities by disjoint-pair sums.',
  'For each of 2,457 x<=8y links, split binary y and combine unconditional x<=3 with x>=0; similarly tighten 2,016 gates from 1200 to the actual 6/9/12 cover bounds.',
  'Use complete identity maps, check every unchanged row too, and verify the full fractional witness with x_C0001=3 and y_C2458=3/8.'],
 'Extract and share exact resource-cover facts; avoid repeating whole capacity rows for each link. Actual LP importer is already supported.',
 caveat='The full historical execution trajectory is absent, but the actual LP pair and final report are present. Rediscover exact cover multipliers if they were not persisted; never use the report as a premise.',
 clusters=['conditional_bounds','linear_elimination','point_contracts'])

case(10,
 'Retained integer projection and every objective value; deleted loads/selectors need complete joint reconstruction.',
 'Target projected relaxation is strictly stronger; the natural lift and full fractional exclusion witness must be checked.',
 'Lin, Round, Cases, IntervalLift, affine_projection, FiberStrictness',
 ['Substitute all 200 eliminated loads exactly and enumerate only the four retained selector bits for conditional fixed-charge budgets.',
  'For sorted weights use t=w_(M+1) and the exact box consequence sum(w_i*x_i)>=t*sum(x_i)-sum(max(0,t-w_i)); combine the conditional budget, then Round the integer count to each of 170 M bounds.',
  'Reconstruct the deleted integer selector by a bounded Boolean AND; for the LP direction use a continuous interval satisfying its actual two selector inequalities.',
  'Build the complete fractional assignment described in the report, then refute the target observation fiber using a violated retained activation bound.'],
 '190,402 source variables and a 190,200-term budget make repeated full-row copies expensive. Share budget/one-hot sums and keep sparse substitution; no resource result is claimed before construction.',
 confidence='medium_high', clusters=['conditional_bounds','bounded_boolean_completion','wide_affine','point_contracts'])

case(17,
 'Same-coordinate integer bijection, objective equality and explicit affine inverse maps.',
 'Target-to-source inclusion only; the report gives a local fractional example, not a full-model strictness claim.',
 'Lin, Cases, inverse',
 ['Delete 1,046 positive rows using exact conic combinations.', 'Prove 44 adjacent binary orders by local Cases and restore all 990 longer weighted orders by chain sums.', 'Check complete identity maps in both integer directions and the LP reverse direction.'],
 'Use shared chain facts rather than one proof for each full order path.', clusters=['conditional_bounds','linear_elimination'])

case(22,
 'Both integer and LP observation images and objective values agree: all 211 retained coordinates plus x142+x145 match the target aggregate.',
 'Equality of these projected LP images, not a bijection of all original coordinates.',
 'Lin, affine_projection',
 ['Eliminate 171 private continuous pivots and 13 fixed-zero integer coordinates by exact affine formulas.', 'Lift the aggregate g in [0,8] as g/2,g/2 into the two equal-cost [0,4] source coordinates.', 'Decode both endpoints of all 171 ranged rows and preserve the encoded tiny RHS and objective offset exactly.'],
 'The missing RANGES support was in an untrusted preparer, not a core semantic gap. No interval theorem is needed for the equal split.', clusters=['linear_elimination'])

case(24,
 'Preserve feasibility, minimum objective and every retained y choice; forward objective NonIncreasing and reverse Equal. No bijection of all source feasible points.',
 'No equality or strict-inclusion claim for the full LP relaxations is required by the report.',
 'Lin, Cases, IntervalLift, affine_projection',
 ['Set the 7,693 unused nonnegative-cost binaries to zero without changing y.', 'For each of 79 disjoint covers, select the first active old binary through shared prefix AND/priority witnesses. Every new x is at most its old value, so capacity and linking inequalities remain valid.', 'Reverse by zero extension; account for the full objective and all 100 integer y domains.'],
 'Cover sizes 15..40 favor balanced local Cases and shared prefix facts. Do not branch the whole model over all covers.',
 caveat='Unused zero-cost variables need not be zero in every optimum. Canonicalization is a dominance map, not a forced-fixing proof. Total aggregate capacity alone does not establish feasibility.',
 clusters=['monotone_completion','bounded_boolean_completion'])

case(29,
 'Zero-extension integer bijection and exact objective values.',
 'Target-to-source inclusion; no global strictness is committed.',
 'Lin, Cases, EqPair, inverse',
 ['Derive all 1,756 zero binaries using local head=1 contradictions, one-hot exclusions and previously established zeros.', 'Turn the 2,604 reciprocal binary-support classes into equalities with exhaustive local Cases.', 'Recover the 180 omitted class equalities from endpoint one-hots minus retained classes; restore every one of the original 69,608 rows.'],
 'Use balanced sums and shared class facts; a complete wide row per variable would create avoidable quadratic work.', clusters=['binary_relation_quotient','wide_affine'])

case(31,
 'Preserve the retained integer projection and every objective value; retyped tree flows require integer reconstruction. No full bijection for canonicalized free auxiliaries.',
 'No LP equivalence is asserted.',
 'Lin, Round, EqPair, Cases, affine_projection',
 ['Force 20,320 oversize binaries to zero by rounding actual 21,600 versus 20,600 capacity bounds.', 'Prove 9,221 unreachable DAG arcs zero through balance-row induction, 18 ones through saturated rows, and the c213 integer count bound by rounding 21,600*sum(H)<=27,300.', 'Use exact component-row identities and group maxima for deleted rows.', 'Prove all 13,984 continuous tree-flow coordinates integer by signed cut sums in the actual tree; reconstruct the 141 zero-cost auxiliaries canonically without claiming they were forced.'],
 '364,417 source variables and about 1.8 million nonzeros. Export shared subtree/cut facts rather than materializing each large cut independently. Size/work limits are unmeasured, not yet a demonstrated RESOURCE_LIMIT.',
 confidence='medium_high', clusters=['linear_elimination','wide_affine','integer_rounding'])

case(32,
 'Unique zero/affine integer reconstruction and exact objective values; 60 target time variables are continuous but must reconstruct integer source coordinates.',
 'No LP equality is asserted.',
 'Lin, Round, Cases, inverse',
 ['Establish 7,282 explicit zeros and 6,306 impossible one-hot choices from actual start/completion bounds.', 'Use componentwise capacity domination and positive-duration precedence paths for 168 capacity and 26 precedence deletions.', 'Derive time integrality from integer-coefficient one-hot definitions and check both complete maps.'],
 'Share one-hot weighted interval facts and path prefixes; the actual proof is owned by corpus_audit.', clusters=['linear_elimination','conditional_bounds'])

case(34,
 'Same complete integer vectors and exact objective.',
 'Strict target subset on the same coordinates.',
 'Lin, Cases, inverse, Strictness',
 ['For each of 231 one-hot groups, prove the aggregate epigraph inequality by balanced local Cases selecting its unique active member.', 'Recover every individual inequality by nonnegativity and the group upper bound.', 'Validate the full fractional point with x=1/231, y=13/231 and the exact maximum distance epigraph value.'],
 'Each group has 231 choices; share one-hot search facts and avoid copying all 53,131 original epigraph rows in each leaf.', clusters=['conditional_bounds','wide_affine','point_contracts'])

case(36,
 'Minimum objective is preserved AND every source integer optimizer has all 200 terminal coordinates zero. The latter is stronger than feasible dominance maps.',
 'No LP-relaxation claim.',
 'Lin, Cases, IntervalLift, Round, Feasible',
 ['Construct the componentwise-minimum chain lift: every prefix is the AND of its original binary scope. Positive auxiliary costs make any noncanonical lift strictly improvable.', 'Prove the universal intermediate lower bound 2,238 by the 26 layer incidence inequalities and exact top-five box/count bounds.', 'Check the complete objective-6,425 feasible point. A canonical lift with an active terminal costs at least 7,283.', 'A minimum-preserving map can choose that fixed point in the active-terminal branch; proving that EVERY optimizer has zero terminals additionally needs strict-improvement/optimality-exclusion semantics.'],
 '37,616 prefix auxiliaries, chains up to roughly 190. Naive sequential lifts exceed nesting limits; balanced scopes/shared prefix expressions are a separate representation problem.',
 confidence='medium', gap=dict(kind='contract_semantics', statement='Caller-bound exclusion of noncanonical or positive-terminal source points from ALL optimizers, via an exact strictly improving feasible witness/map. Unknown optimum prevents replacing this by a fixed objective-level restriction.', new_trusted_mathematical_rule_required='not_established', frozen_v8_support='ordinary NonIncreasing/Equal maps alone do not assert this property'),
 caveat='A positive continuous terminal need not be >=1 at an arbitrary feasible point. The report derives integrality only for a minimum lift. Treating it as a global integer fact would be unsound.',
 clusters=['monotone_completion','optimality_contract','wide_affine'])

case(37,
 'Integer zero/fixed-coordinate affine bijection and equal objective.',
 'Strict projected inclusion, with complete source point and target observation-fiber refutation.',
 'Lin, Cases, inverse, FiberStrictness',
 ['Prove the four impossible selector binaries zero and the fixed coordinate.', 'Build 72 actual path bounds and the 262 strengthened M implications using local binary Cases; retain all 12 nearly balanced decimal rows exactly.', 'Check both integer maps, LP reverse inclusion, and the full fractional fiber strictness witness.'],
 'The complete receipt produced after the snapshot checks 5,269 obligations and 262 local branches. Mathematical path sharing keeps the proof bounded.', clusters=['conditional_bounds','linear_elimination','point_contracts'])

case(39,
 'Same complete integer vectors and objective.',
 'Target-to-source inclusion; local examples do not establish global strictness.',
 'Lin, Round, EqPair, inverse',
 ['Normalize 960 balanced packings by exact equality scaling.', 'For the 192 rows 2*sum(D)-z<=2 combine z<=1 and Round integer sum(D) to <=1.', 'Remove 1,728 duplicates and 6,564 component equalities by explicit exact row sums; use complete identity maps.'],
 '242,736 variables and more than 313,000 rows make complete identity checking and repeated component sums the main cost, not a missing graph theorem.', clusters=['integer_rounding','linear_elimination','wide_affine'])

case(41,
 'Unique integer affine/zero reconstruction with exact objective.',
 'Target-to-source inclusion; no global strictness claim.',
 'Lin, Cases, EqPair, inverse',
 ['Use actual balance-row suffix cuts on the eight-node DAG to establish the 28 flow lower bounds.', 'Force indicators to one, identify d=t and 84 binary aliases, then derive 160 zero selectors and 148 tighter conditional M bounds.', 'Derive nonempty selection from the actual weighted lower bound and binary count; retain all 21 nontrivial weighted caps.'],
 'The graph only proposes row multipliers; the kernel can check them with scalar rules. Preserve encoded repeating decimals, not idealized 2/3 coefficients.', clusters=['conditional_bounds','linear_elimination','integer_rounding'])

case(42,
 'Same-coordinate integer bijection and equal objective.',
 'Strict inclusion on complete original coordinates.',
 'Lin, Round, Cases, inverse, Strictness',
 ['Round the actual total-capacity requirement to at least 189 ordered activations and propagate the binary prefix.', 'Prove the 1,101 gated group reductions with local Cases.', 'Restore all 166,500 original links by divide-and-conquer sums and verify the full fractional strictness point.'],
 'Shared sum trees avoid repeated whole partition rows.', clusters=['conditional_bounds','wide_affine','point_contracts'])

case(45,
 'Retained integer and LP projections and every objective value agree; single-use zero-cost binaries are completed canonically, not uniquely.',
 'Both projected directions hold with affine maps.',
 'Lin, affine_projection',
 ['Reconstruct 378 continuous slacks affinely and prove their nonnegativity.', 'Set the 462 single-use zero-cost binaries to one and use actual capacity implications for their removed rows.', 'Account for 651 duplicates and 21 equality-implied rows; leave all 42 coupled mutually exclusive binaries intact.'],
 'Pure affine completion; no interval/Boolean existence rule is needed.', clusters=['linear_elimination'])

case(46,
 'Retained integer projection with unique complete pair-selector reconstruction and equal objective; verify all 60,608 retyped selectors integer.',
 'Target-to-source inclusion; the 17 deleted constant factors require a genuine continuous lift as well.',
 'Lin, Cases, IntervalLift, affine_projection',
 ['Use the actual objective cap to eliminate 80,785 forbidden high-cost selectors and derive complete marginals for the remaining 49 factors.', 'For integer inputs, local unary one-hot Cases force every continuous pair selector to its unique Boolean product.', 'For each deleted complete Cartesian factor, retain its exact constant cost and use a four-corner LP coupling: normalized means alpha,beta and t in [max(0,alpha+beta-1),min(alpha,beta)] satisfy normalization and both original index moments.', 'Check the objective offset 289 and every deleted source row; no unchecked product of real variables is necessary.'],
 '159,145 original variables and many pair selectors. Reuse one-hot branch facts; a full endpoint Cartesian branch product is unnecessary. Four-corner construction must be checked against actual corner availability and coefficients.',
 confidence='medium_high', clusters=['bounded_boolean_completion','continuous_local_completion','wide_affine'])

case(51,
 'Unique integer affine reconstruction and every objective value; score/minimum-selector elimination.',
 'Strengthened LP direction may be proved; no full strictness point is committed.',
 'Lin, Cases, EqPair, inverse',
 ['Use the actual five-weight simplex to prove 1,094 dominated selectors zero, retaining all four sub-epsilon lower rows.', 'Substitute all score equalities and the forced zero-score threshold.', 'For each conditional comparison bound, use exhaustive local Cases over a selected minimum candidate; permit ties rather than assuming one-hot selectors.'],
 'Share five-dimensional simplex extreme-value facts across the 25 groups and 130 conditional comparisons.', clusters=['conditional_simplex','conditional_bounds','linear_elimination'])

case(52,
 'Unique integer affine reconstruction and every objective value across 266 minimum-score blocks.',
 'LP equality is not claimed; any containment direction still needs complete checks.',
 'Lin, Cases, EqPair, inverse',
 ['Prove 12,190 zeros and 55 ones using exact simplex dominance and epsilon=1/100000.', 'Eliminate 13,300 scores and 55 thresholds by their actual equalities, keeping four sub-epsilon inequalities.', 'Prove the 1,055 conditional M bounds through selected-minimum Cases, including all tied candidates.'],
 'Fifty candidates per block make naive pairwise repeated dense expressions costly. Cache exact score differences and balanced selected-candidate facts in the untrusted generator.', clusters=['conditional_simplex','conditional_bounds','wide_affine'])

case(53,
 'Same complete integer feasible vectors and objective.',
 'Strict target subset on the same coordinates.',
 'Lin, Cases, inverse, Strictness',
 ['Shift the 130 epigraph rows using exact equalities and remove the dependent assignment row.', 'For each of 26 continuous z bounds, branch over the five INTEGER loads: either one load reaches ceil(S/5), or all are <=ceil(S/5)-1 and contradict their sum.', 'Verify the full 156-coordinate rational strictness point.'],
 'Five-way local pigeonhole proofs are small. Never apply Round directly to continuous z.', clusters=['integer_rounding','bounded_boolean_completion','point_contracts'])

case(55,
 'Retained integer projection and objective values, with a continuous completion rather than a full bijection.',
 'Target-to-source inclusion.',
 'Lin, Cases, affine_projection',
 ['Delete 1,024 private continuous y variables and reconstruct each as x/480.', 'For each strengthened 120/338/348 link, split only the one or three actual binary activations: any zero forces x=0, all ones activate the exact capacity bound.', 'Check all original y bounds, links and the objective.'],
 'Small local activation patterns suffice; apparent flow-like incidence does not require a flow theorem.',
 caveat='The actual final target is output/model.mps, not the usual reformulated.mps. Model identity is taken from inventory and verified against the file.', clusters=['conditional_bounds','linear_elimination'])

case(56,
 'Zero-extension integer bijection and exact objective.',
 'Target-to-source inclusion; no strictness claim.',
 'Lin, Round, EqPair, inverse',
 ['Round the 48 binary relations 2u-v=0 to force their 96 coordinates zero and propagate actual nonnegative rows.', 'Round both endpoints of 78 integer-cardinality intervals and combine by EqPair.', 'Use the actual 350-partition sum to subtract common coefficients from eight dense inequalities, then Round; certify the 120 subset deletions.'],
 'The partition covers 101,656 variables. Repeatedly reconstructing that sum would dominate proof size; one shared fact and sparse residuals suffice mathematically.', clusters=['integer_rounding','wide_affine'])

case(58,
 'Preserve feasibility and minimum objective, with complete MI forward NonIncreasing and reverse Equal maps; no all-point bijection.',
 'No full LP relation is committed.',
 'Lin, Cases, SignedLift, FlowLift',
 ['Use actual cut equalities for 199 bridges, retaining fixed signed flows and objective constant 205; reconstruct 121 series paths in reverse.', 'Reverse the final signed flows jointly with existing SignedLift, then restore every original activation, flow, capacity and objective term.', 'Forward, merge the deleted parallel contributions but DO NOT assume their sum still has capacity B=82.', 'A proposed common-source bounded subflow construction discards circulations while preserving all demands and 0<=g<=old aggregate, g<=B; local binary Cases can then establish g<=B*y. This joint existence step is not yet certified.'],
 'A naive whole-map split over edge signs is exponential. Existing SignedLift handles signs but not capacity-preserving rerouting after parallel merging.',
 confidence='medium', gap=dict(kind='joint_existence_candidate', statement='Given a common-source nonnegative flow with nonnegative sink demands of total B, jointly choose g with the same node balances and 0<=g_e<=f_e and g_e<=B on every arc, including loops and disconnected circulations.', candidate_proof='Decompose into source-to-demand paths and circulations; retain only demand paths. Every simple path uses each arc at most once and total path weight is at most B.', necessity='No compact derivation using current rules has been established. This is a practical proof gap, not a theorem that the ISA cannot express it.', status='PAUSED_DESIGN_ONLY; no new version or production rule'),
 caveat='The source report uses global rerouting/connectivity. Replacing it by local parallel capacity arithmetic is unsound. Isolated draft/oracle work is not a certificate; no final transformation counterexample is known.',
 clusters=['common_source_flow','monotone_completion'])

case(61,
 'Unique Boolean reconstruction and equal objective after 3,200 private auxiliaries are removed; cyclic/self-dependent retained variables stay in the same common model.',
 'Projected target-to-source containment is also claimed. The report supplies only local strict examples, not full global strictness.',
 'Lin, Cases, IntervalLift, affine_projection',
 ['For integer modes, prove each local relation by exhaustive Cases over at most four retained bits and reconstruct exact pattern indicators through joint old-scope intervals.', 'For the LP direction, attempt exact elimination/completion of at most eight private continuous auxiliaries per block, producing IntervalLift lower/upper pairs and explicit Farkas multipliers from the actual 2,070 hull rows.', 'Use at most eight synchronized extension waves across 400 groups; every original row still receives an explicit terminal obligation.'],
 'Local Fourier-Motzkin bounds can grow despite small dimension. Measure certificate width/work before introducing a trusted polyhedral-extension theorem; enumerated hull metadata is not authority.',
 confidence='medium_low', gap=dict(kind='existing_rule_route_unfinished', statement='Continuous local completion must still be reduced to checked interval premises. No new mathematics is known to be necessary, but this route has not been constructed or measured.'),
 caveat='The actual decimal 0.333 is not 1/3. Cycles among retained bits do not invalidate local equivalence, but independently choosing incompatible retained assignments would.', clusters=['bounded_boolean_completion','continuous_local_completion'])

case(62,
 'Unique Boolean reconstruction and exact objective after 4,000 auxiliaries are removed.',
 'Only an explicit full source-LP point whose retained image violates seven target unit clauses; the report expressly does NOT claim global LP containment.',
 'Lin, Cases, IntervalLift, affine_projection, Feasible',
 ['Prove all 500 local relations through bounded truth-table Cases over their actual pattern inputs; use jointly compatible Boolean completions and check all original 7,029 rows.', 'Check the complete source fractional point: all retained bits 1/2 and each of k active pattern auxiliaries 1/(2k).', 'Separately bind its retained coordinates to the seven violated actual target rows. Existing Strictness/FiberStrictness cannot assert this exclusion alone without an established LP inclusion claim.'],
 'There are 7,968 audited local assignments; repeated Boolean expression templates are a representation opportunity, not a license to trust their truth tables.',
 confidence='medium_high', gap=dict(kind='ancillary_point_contract', statement='A complete feasible point whose observation lies outside the other model, without asserting relaxation containment. Current Strictness variants require an inclusion claim.', new_trusted_mathematical_rule_required=False, main_integer_relation='Existing rules suffice; this gap concerns the report\'s additional fractional-exclusion evidence.'),
 caveat='Do not upgrade exclusion of one source point to strict containment. The actual report explicitly disclaims whole-relaxation containment and global feasibility/optimality.', clusters=['bounded_boolean_completion','point_contracts'])

case(64,
 'Unique complete integer affine bijection and exact objective.',
 'No LP equality or full strictness claim.',
 'Lin, Cases, EqPair, inverse',
 ['Prove 6,875 x1+x2=2y binary aliases by local Cases, 275 opposite pairs by antisymmetry, and 550 w=u equalities.', 'Use actual assignment equations for the 69 dependent rows and six integer cost coordinates.', 'Replay all 680 ordered saturation deductions to establish 2,816 fixed variables, then prove all 2,546 bound-entailed deletions.'],
 'Order-dependent fixed facts should be shared, with old scoped facts dropped when no longer needed. The large alias count does not require a new alias theorem.', clusters=['binary_relation_quotient','linear_elimination'])

case(66,
 'Same complete integer vectors and objective after 20,484 conditional five-cycle cuts are added.',
 'Strict target subset on the same coordinates.',
 'Lin, Round, Cases, inverse, Strictness',
 ['For each of 5,121 five-cycles and four labels, sum the five actual vertex rows, remove nonnegative spokes and divide by two.', 'In the active binary gate branch Round the integer cycle sum to <=2; in the zero gate branch use nonnegativity and the original gate rows.', 'Check the full fractional cycle-half witness and all other graph coordinates.'],
 '20,484 repeated short derivations could benefit from a measured scalar-equivalent batch, but no trusted odd-cycle rule is mathematically necessary.',
 caveat='The final artifact is output/model_odd5.mps. Graph metadata proposes row incidences; every actual row and binary domain must be checked.', clusters=['integer_rounding','bounded_boolean_completion','point_contracts'])

case(67,
 'Same integer feasible vectors and objective after four activations are fixed to one. The report additionally asserts feasibility and minimum value 4.',
 'No full LP relation is committed.',
 'Lin, Cases, inverse, Feasible, input_objective_lower',
 ['For each activation=0 assumption, export a finite exact local coloring refutation on the actual 17-edge/68-binary subgraph using scalar propagation and Cases.', 'Use those facts to justify every bound and roughly 24,000 substituted row terms.', 'Construct an explicit full four-edge-coloring outside the kernel and check it as a complete integer point of objective 4; the four activation facts give the matching lower bound.'],
 'Naive 2^68 search is not a proof plan. An untrusted constrained search should export a compact bounded branch tree; color symmetry may only prune when its renaming argument is itself justified.',
 confidence='medium', caveat='Do not import Vizing or an external perfect-matching enumeration as trusted authority. The optimum/feasibility claim needs an actual full-model coloring witness, not only the local lower-bound gadget.', clusters=['finite_refutation','bounded_boolean_completion','point_contracts'])

case(72,
 'Preserve all 2,608 primary binary observations and the minimum completion cost for EACH primary assignment (objective epigraph). Forward Equal, reverse NonIncreasing; auxiliary choices need not be unique.',
 'The report also proves equality of each eliminated fractional capacity-block epigraph, not equality of the entire model LP relaxation.',
 'Lin, Round, Cases, IntervalLift, MenuLift, affine_projection',
 ['Forward set each new q to the exact old weighted lambda cost and derive every threshold cut by linear combinations.', 'For reverse integer completion, sort costs descending and allocate the K free units to the first active primaries: prefix counts w=min(prefix,K), then lambda=y-(w_i-w_(i-1)). Use bounded menus/intervals and Cases to prove the threshold cost bound.', 'Construct day-OR, integer shortfall and isolation penalties jointly using actual primary variables; restore all 2,645 retyped integer coordinates. Prove every clique of size <=6 by local Cases.', 'For the separate fractional capacity-block statement, construct the continuous greedy fill by exact interval completion and prove its cost from threshold rows; this additional route remains to be built.'],
 'Actual audit has 275 capacity blocks, maximum 78 terms and K in [6,19]. Reusing the test78 prefix/menu expansion could become large: measure preparation, bytes, work and RSS; prefer shared capped-prefix facts before a new exchange rule.',
 confidence='medium_high', gap=dict(kind='existing_rule_route_unfinished', statement='Integer ordered completion has an explicit existing-rule route. The ancillary continuous epigraph completion still needs a compact exact interval proof; no new trusted greedy/exchange theorem has been justified.'),
 caveat='Do not mistake preservation of minimum completion cost for preservation of every original auxiliary point or every objective value. Use the actual costs and retained threshold rows, not a family label.', clusters=['monotone_completion','continuous_local_completion','wide_affine'])

case(73,
 'Same complete integer vectors and objective.',
 'Target-to-source inclusion, with no full strictness claim.',
 'Lin, Cases, inverse',
 ['For each actual clique of size <=8, prove at most one selected binary by local Cases and the supplied pairwise conflict rows.', 'Restore all 4,802 original edges from the 1,339 clique rows and nonnegative bounds, and justify the 24 remaining deletions.'],
 'At most 128 Boolean leaves per clique before propagation. Summing all pairwise rows alone only gives a weaker count bound, so do not silently replace Cases by one rounding step.', clusters=['bounded_boolean_completion'])

case(74,
 'Retained integer projection and zero objective; private auxiliary reconstruction need not be globally unique.',
 'No LP equality or strictness claim.',
 'Lin, Cases, IntervalLift, affine_projection',
 ['Prove every local retained assignment admitted by the new clauses has a valid private binary witness, using the actual two source inequalities and at most seven retained bits.', 'Build joint private completions from bounded Boolean decision functions/AND intervals in synchronized layers.', 'Restore all 1,328 fixed variables and account for 26,544 duplicates and 10,486 bound-implied rows.'],
 '16,140 private variables and 123,344 audited local assignments make template sharing worthwhile. Do not form the product of all local branch trees or assume the retained graph is acyclic.', confidence='medium_high', clusters=['bounded_boolean_completion','wide_affine'])

case(76,
 'Unique integer zero/affine bijection and exact objective.',
 'No LP equality is asserted.',
 'Lin, Round, inverse',
 ['Combine actual prefix resource rows and five one-hot lower bounds to obtain 21+5*x<=25 for the 26 impossible choices; Round their binary values to zero.', 'Eliminate all 50 start coordinates by exact weighted one-hot formulas and restore every retained chain row.'],
 'The completed test77 provides a similar untrusted proof pattern; it is not a premise or substitute for checking this actual model.', clusters=['conditional_simplex','integer_rounding','linear_elimination'])

case(80,
 'ALL source integer optimizers are in a complete bijection with target integer feasible points, at minimum objective -160; suboptimal source points are outside the claim.',
 'No LP relation is claimed.',
 'Lin, Cases, inverse, Feasible, input_objective_lower, working_input_objective_level',
 ['Prove the unrestricted lower bound f+160=sum(p)+10*sum(1-b)>=0 and verify a complete source point attaining -160.', 'Within the caller-bound actual objective level -160, infer all p=0 and b=1 and certify the full affine inverse pair for the actual source and target.', 'Check opposing objective-level domain membership as well as map compositions; never infer optimum or nonemptiness solely from a restricted-domain claim.'],
 'The working V9 proof is already complete; preserve its unpublished protocol status separately from mathematical acceptance.',
 gap=dict(kind='contract_semantics_implemented_working', statement='Objective-level restricted domains and inverse-domain closure were absent from frozen V8; working V9 implements them. This is a contract feature, not a new scalar inequality theorem.', status='WORKING_VERSION_9_NOT_FROZEN'),
 clusters=['optimality_contract','linear_elimination'])

case(81,
 'Zero-extension integer bijection and exact objective.',
 'Strict projected inclusion with a full-model source fractional witness.',
 'Lin, Cases, inverse, FiberStrictness',
 ['Prove all 3,341 deleted time arcs zero from the actual one-hot/window conditions.', 'Derive 762 conditional M bounds and 57 automatic rows, move 65 windows to bounds, and prove the 130 domain-implied deletions.', 'Verify the complete 2x2-switch fractional point and refute its target observation fiber using the deleted positive arc and/or actual retained violated row.'],
 'Share window/path bounds across repeated indicators. All original observations can be expressed with target constants for removed variables.', clusters=['conditional_bounds','linear_elimination','point_contracts'])

case(82,
 'Zero-extension integer bijection and exact objective for this distinct time-window instance.',
 'Target-to-source inclusion; no full strictness claim.',
 'Lin, Cases, inverse',
 ['Derive this model\'s 3,315 zero arcs and 792 tightened M rows from its actual windows.', 'Certify all 53 automatic rows and the c209 dependent equality deletion.', 'Restore all source bounds/rows and compare exact objective constants.'],
 'Reuse proof-generation patterns from 81 only after rebinding every coefficient and row; the fixed sets differ.',
 caveat='The report explicitly rejects an earlier sign hypothesis and does not fix the 51 diagonal variables. That rejected exploration is not a counterexample to the final model, nor a valid proof premise.', clusters=['conditional_bounds','linear_elimination'])

case(83,
 'Preserve feasibility, minimum objective and optimal-solution recovery; forward NonIncreasing and reverse Equal, not a bijection of all feasible source points.',
 'No LP relation is required by the committed scope.',
 'Lin, affine_projection',
 ['For each of 61 dominated columns, aggregate its value into two retained columns with disjoint support and strictly lower cost.', 'Use balanced contributor-sum upper bounds from actual partition rows to keep every target binary in [0,1].', 'Eliminate the 100 singleton coordinates as 1 minus their row sums, preserve the exact encoded objective constant 4989.422626, and reverse by zero extension.'],
 'Like completed test21, shared partition contributor trees avoid a wide row copy for every representative. Strictly dominated-column exclusion from ALL optima is an ancillary stronger property, not implied by an unqualified NonIncreasing claim alone.',
 gap=dict(kind='contract_semantics', statement='The report explicitly states that no optimum selects a dominated column. Main minimum-preservation/recovery maps use existing rules, but this additional all-optima exclusion needs caller-bound strict improvement if it is separately machine-certified.', new_trusted_mathematical_rule_required=False, primary_relation='Existing Lin maps suffice for the committed minimum-preservation and recovery relation.'),
 caveat='The report\'s section 4 explicitly proves no optimum can select a deleted dominated column. Record that ancillary strict-improvement exclusion rather than silently relabeling a minimum-preserving map as the stronger result.', clusters=['monotone_completion','wide_affine','optimality_contract'])

case(85,
 'Zero-extension integer bijection and exact objective.',
 'No stronger LP assertion is needed; any additional reverse inclusion must be independently proved.',
 'Lin, Cases, EqPair, inverse',
 ['Derive all 1,844 zeros from actual nonnegative row propagation.', 'Prove 1,908 reciprocal support-class equalities by local binary Cases.', 'Restore the 144 omitted class equations, three dependent original equations and every original row.'],
 'Use shared support-class sums and local facts; this is the same mathematical quotient pattern as 29 with different actual zero deductions.', clusters=['binary_relation_quotient','wide_affine'])

case(86,
 'Same complete integer vectors and exact objective after 250 cover cuts.',
 'Strict target subset on the same coordinates.',
 'Lin, Cases, inverse, Strictness',
 ['For each actual cover incoming+d*y>=d, split binary y. If y=0 the original link forces production zero and node balance plus outgoing nonnegativity yields the cut; if y=1 use nonnegativity.', 'Keep complete identity maps and verify the full fractional point p=d, y=d/D, flows=0 on all five blocks.'],
 '250 small scalar proofs; no new flow existence theorem is involved.', clusters=['conditional_bounds','point_contracts'])

def sha(path):
    h = hashlib.sha256()
    with path.open('rb') as f:
        for b in iter(lambda: f.read(1 << 20), b''):
            h.update(b)
    return h.hexdigest()

def main():
    inventory_path = ROOT / 'audit/corpus_inventory.json'
    inventory = json.loads(inventory_path.read_text())
    inventory_by_id = {c['case_id']: c for c in inventory['cases']}
    raw = gzip.decompress(SNAPSHOT.read_bytes())
    assert hashlib.sha256(raw).hexdigest() == RAW_SHA
    snapshot = json.loads(raw)
    del raw
    assert sorted(int(c['case_id'][4:]) for c in ROWS) == EXPECTED
    # Acceptance schema is inspected rather than inferred from the live ledger.
    baseline_cases = snapshot.get('cases', snapshot.get('runs', []))
    baseline_by_id = {c['case_id']: c for c in baseline_cases}
    assert all(baseline_by_id[c['case_id']]['status'] == 'PROOF_NOT_COMPLETED' for c in ROWS)
    owners = {'test37': 'model_layer (root delegated)', 'test32': 'corpus_audit', 'test76': 'corpus_audit', 'test80': 'model_layer'}
    update_ids = {17,22,32,37,42,80}
    for row in ROWS:
        cid = row['case_id']; inv = inventory_by_id[cid]
        base = Path(inv['run_directory'])
        row['baseline_status'] = baseline_by_id[cid]['status']
        row['run_directory'] = str(base)
        row['model_identity'] = {}
        for k in ['source_models', 'final_target_models']:
            row['model_identity'][k] = []
            for m in inv[k]:
                p = base / m['path']
                assert p.is_file() and p.stat().st_size == m['bytes']
                actual_hash = sha(p)
                assert actual_hash == m['sha256'], (cid, p)
                row['model_identity'][k].append(dict(m, absolute_path=str(p), sha256_rechecked=True))
        report = inv['target_selection_evidence']['report']
        if report is None:
            candidates = [f for f in inv['files'] if f['path'].lower() == 'output/report.md']
            assert len(candidates) == 1
            report = candidates[0]
        rp = base / report['path']
        assert sha(rp) == report['sha256']
        headings = [dict(line=i, text=s) for i,s in enumerate(rp.read_text().splitlines(),1) if s.startswith('#')]
        row['report_evidence'] = dict(report, absolute_path=str(rp), sha256_rechecked=True, section_index=headings)
        row['evidence_depth'] = 'Actual final report proof/limitations read and all actual model/report bytes rebound by SHA-256; proposed routes are not independent full-matrix certificates.'
        row['historical_material_notes'] = inv.get('missing_material', [])
        row['owner_at_cutoff'] = owners.get(cid)
        row['status_after_snapshot'] = dict(status='PROOF_NOT_COMPLETED', owner=owners.get(cid), evidence='Read-only route assessment; no complete RPX success claimed here.')
        if int(cid[4:]) in update_ids:
            p = ROOT / f'cases/{cid}/preparation.json'
            rec = json.loads(p.read_text())
            assert rec['status'] == 'VERIFIED'
            row['status_after_snapshot'] = dict(status='VERIFIED', receipt=str(p.relative_to(ROOT)), receipt_sha256=sha(p), attack_count=len(rec['negative_checks']), protocol_status=rec.get('protocol_status','existing_version'), evidence='Existing complete preparation receipt inspected; no rerun performed for this inventory.')
            row['confidence']['implementation'] = 'complete_certificate_verified_after_snapshot'
        if cid == 'test72':
            ap = base / 'output/audit.json'; a = json.loads(ap.read_text())
            blocks = a['capacity_blocks']
            row['additional_actual_evidence'] = dict(path=str(ap), sha256=sha(ap), capacity_blocks=len(blocks), maximum_block_terms=max(len(b['terms']) for b in blocks), minimum_K=min(b['K'] for b in blocks), maximum_K=max(b['K'] for b in blocks))

    data = dict(schema='remaining-requirements-audit-1', assessment_date='2026-10-11',
        scope='All 37 PROOF_NOT_COMPLETED cases in the immutable 44/81 acceptance snapshot. Later completion receipts are supplemental; this file does not change acceptance.json.',
        acceptance_snapshot=dict(path=str(SNAPSHOT.relative_to(ROOT)), gzip_sha256=sha(SNAPSHOT), uncompressed_sha256=RAW_SHA, summary=snapshot['summary']),
        corpus_inventory=dict(path=str(inventory_path.relative_to(ROOT)), sha256=sha(inventory_path)),
        capability_baseline=dict(frozen='V8', working='V9 objective-level contracts; test80 VERIFIED but protocol not frozen', production_changes_by_this_audit=False, new_format_proposed=False),
        evidence_policy=['Reports and audit metadata are untrusted evidence used to propose proofs, never accepted premises.', 'High confidence does not imply VERIFIED. No failed candidate here is treated as a refuted transformation.', 'Every actual source/target model and report in these entries was rebound by full SHA-256, not merely a filename or family tag.', 'Resource risks are forecasts unless an entry links an actual RESOURCE_LIMIT receipt. This audit ran no new kernel certificate, benchmark or preparer.'],
        counts=dict(baseline_total=81, baseline_verified=44, baseline_remaining=37, verified_after_snapshot_in_this_set=6, still_uncompleted_at_cutoff=31,
                    later_verified_ids=['test17','test22','test32','test37','test42','test80']),
        conclusions=dict(
          mathematical_rule_candidate=[dict(name='common-source bounded subflow', cases=['test58'], status='paused isolated design; no production rule or frozen version', distinction='Existing FlowLift decomposes a fixed aggregate including circulation; SignedLift chooses signs. Neither by itself produces a smaller capacity-bounded aggregate with the same demands.')],
          contract_semantics=[dict(name='all-optimizer domain', cases=['test80'], status='working V9 implemented and actual case verified, not frozen'),dict(name='strict improvement / optimizer exclusion', cases=['test36','test83 (ancillary strict-dominance claim only)'], status='design requirement, not implemented'),dict(name='point exclusion without inclusion', cases=['test62 (ancillary fractional claim)'], status='possible minimal point-contract extension, not implemented')],
          unresolved_existing_rule_completions=[dict(cases=['test61'], requirement='actual continuous local hull completion by exact interval/Farkas witnesses'),dict(cases=['test72'], requirement='ordered integer completion and ancillary fractional epigraph completion; measure existing bounded-prefix expansion'),dict(cases=['test67'], requirement='compact finite local coloring refutations plus an explicit full coloring point')],
          not_justified_as_new_theorems=['Conditional simplex extrema (51/52/76): Lin plus selected-minimum Cases.', 'Top-k/weighted cardinality bounds (10/36): threshold box inequalities plus integer Round.', 'Five-cycle/clique/continuous epigraph bounds (66/73/53): bounded scalar Cases and Round on actual integer expressions.', 'Pair-selector LP completion (46): exact four-corner IntervalLift, not unchecked real multiplication.', 'Bounded Boolean existential completion (61/62/74): local truth Cases with joint old-scope intervals, not whole-model branch products.']),
        representation_priorities=[
          dict(cases=['test10','test31','test34','test39','test46','test56'], experiment='Shared sparse affine expressions/maps and balanced row/contributor trees', requirement='Compare exact same complete claims, bytes, expanded terms, actual work, decode/execute/total time, preparation time and RSS; retain full output checking.'),
          dict(cases=['test24','test36','test72','test74'], experiment='Shared prefix/capped-count/Boolean templates and synchronized interval layers', requirement='First measure a scalar existing-rule certificate. DAG sharing and scalar-equivalent batching can reduce representation cost but cannot establish an absent joint-existence theorem.'),
          dict(cases=['test66','test86'], experiment='Optional repeated local-proof batch', requirement='Only adopt after fixed A/B measurement and exact scalar-reference/negative tests; no case IDs or trusted metadata shortcuts.')],
        fixed_pressure_reference=dict(case='test78', receipt='cases/test78/preparation.json', rpx_bytes=92054445, rpa_bytes=105561392, work=55606781, branches=11344, obligations=28644, menu_generated_binary_variables=133280, kernel_execution_us=3071705, total_verification_us=3621032, preparation_wall_seconds=201.1718, preparation_pause_note='Wall time includes a root-requested stop. Observed paused interval 08:22:55..08:24:33 UTC was 98 seconds; actual stop slightly preceded first observation. No exact active-time subtraction is claimed.', measurement_status='single actual-case diagnostic, NOT isolated performance benchmark', pause_evidence='audit/test78_preparation_pause.json'),
        cases=ROWS)
    out = ROOT / 'audit/remaining_requirements.json'
    out.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n')
    rows = []
    for c in ROWS:
        cid=c['case_id']; after=c['status_after_snapshot']; gap=c['new_mathematics_or_contract_gap']['kind']
        short = {'none_identified':'现有规则路线','contract_semantics':'所有最优解合约','contract_semantics_implemented_working':'工作版 objective-level 合约','joint_existence_candidate':'共同源有界子流存在性','existing_rule_route_unfinished':'现有完成路线待构造','ancillary_point_contract':'整数路线现有；另有排除点合约'}[gap]
        status = '已在快照后认证' if after['status']=='VERIFIED' else ('进行中：'+c['owner_at_cutoff'] if c['owner_at_cutoff'] else '证明未完成')
        rows.append(f'| {cid} | {status} | {short} | {c["confidence"]["mathematical_route"]} |')
    md = '''# 剩余证明需求盘点

本盘点固定于 **44/81 已认证、37 项未完成** 的验收快照；原始快照压缩副本及 SHA-256 记在 [JSON](remaining_requirements.json)。37 项全部保留，逐项读取实际最终报告的合约、论证和限制，重新核对全部实际 source/target/report 的完整文件 SHA-256。没有修改验收账本、生产规则或格式，也没有把报告结论当作内核前提。

快照之后，**17、22、32、37、42、80 已有完整 VERIFIED receipts**，合计当前这组仍有 31 项未完成。80 明确是 `WORKING_VERSION_9_NOT_FROZEN`。37 已由 root 转交 model_layer 完成；corpus_audit 目前处理 76，76 没有计入成功。JSON 将历史状态、后续证据、负责人、实际模型身份和报告章节分开保存，因而不会随实时账本更新丢失分母。

## 收敛结论

大部分剩余案例有可组合的现有规则路线。报告使用的“条件 simplex”“组合界”“奇环”“hull”“交换”名称本身，不构成新增可信规则的理由。10 的排序容量界可以写成阈值箱约束加 Round；51/52 的条件最小值用 Lin 与局部 Cases；53 不可对连续 z 直接取整，但可对五个整数负载分支；66 的五环与 73 的小 clique 可导出普通标量证明；46 的 LP 双边矩可用四角耦合和一个区间参数，不必引入未经检查的实数乘积。

目前有依据保留的数学能力候选集中为 **58 的共同源有界子流联合存在性**：保相同节点需求，逐弧满足 `0 <= g <= f` 和 `g <= B`，通过去循环/保需求路径得到。现有 FlowLift 保持既定总流，SignedLift 只处理符号，二者没有自动完成这个结论。并行边流直接相加可能达到 2B，不能偷换成局部容量证明。这只是实用证明缺口；尚未证明现有 ISA 绝对不能表达，也没有冻结新版本或生产规则。

应与数学引理分开的合约问题有三类：

- 80 的所有最优解双射需要 caller-bound objective level、反向域成员义务，以及独立的全局下界与完整达到点；工作 V9 已实现并实证通过，仍待发布冻结。
- 36 的所有 optimizer 均无 terminal，比可行映射的 NonIncreasing/Equal 更强。未知最优值不能凭空用固定 level 替代；需明确严格改进/optimizer 排除责任。83 的严格支配解释若也作为独立 all-optima 承诺验收，同样应单列。
- 62 只承诺一个完整原 LP 点被目标排除，并明确不承诺全局 LP containment。不能冒用现有要求 inclusion 的 Strictness；主整数等价仍有现有规则路线。

61 的 LP 局部 hull 完成、72 的分数容量 epigraph 完成，以及 67 的有限着色 refutation 是尚未构造的现有规则候选路线。不能把这些写成“已支持”，也不应先判定需要新 theorem。72 的实际 audit 有 275 个容量块、最大 78 项、K=6..19，足以先建立有代表性的现有展开成本证据。

## 表示和资源优先项

10/31/34/39/46/56 的宽行、共享消元和完整大模型检查，应先消除每变量复制整行的平方展开；24/36/72/74 应用平衡局部 Cases、共享 prefix/capped-count 和分层共同区间，避免全模型分支笛卡尔积。DAG 或 batch 可优化相同标量语义的表达、解码和代换，不能替代联合存在性论证。

保留 test78 为真实压力参照：RPA 105,561,392 字节、RPX 92,054,445 字节、55,606,781 work、11,344 branches、28,644 obligations、133,280 个新增 menu 二元变量。单次执行约 3.072 秒、完整验证约 3.621 秒，**不是隔离 benchmark**；准备 201.1718 秒包含性能窗口暂停，不能把整段记作活跃计算成本。下一次表示优化必须固定同一数学合约，并同时报告准备、证书规模、实际访问、执行/总耗时和 RSS。

## 全部快照残余

下表仅供导航；完整合约、LP 边界、实际 proof 路线、材料风险、资源风险、证据和负责人在 JSON。置信度是路线判断，不是验收状态。

| 案例 | 快照后状态 | 主要缺口分类 | 路线置信度 |
|---|---|---|---|
'''+ '\n'.join(rows)+'''

## 证据与局限

本次没有发现足以推翻最终变换的反例，也没有把失败探索计作最终错误。全部最终模型存在；8 的历史完整执行轨迹缺失不等于模型材料缺失。各条目的 full-matrix 论证仍须由完整 RPX 检查实现，不能以本文件的路线分析替代。资源风险若尚未运行，均标为未测，未伪报 RESOURCE_LIMIT。

复现：`python3 audit/build_remaining_requirements.py`。它只读取已固定快照、语料和明确列出的六个后续 receipts，重写本说明与 JSON；不更改生产代码、案例准备器或验收账本。
'''
    (ROOT/'audit/REMAINING_REQUIREMENTS.md').write_text(md)
    print(json.dumps(dict(entries=len(ROWS), post_snapshot_verified=6, uncompleted=31, output=str(out), gap_kinds=Counter(c['new_mathematics_or_contract_gap']['kind'] for c in ROWS)),ensure_ascii=False))

if __name__ == '__main__':
    main()
