# test46: integer marginals and exact real moment completion

The original model has 159,145 integer variables and 301 equality rows. The actual final model has 61,036 variables and 3,615 equality rows; only its 427 unary selectors retain integer declarations. The complete source and target are read from `runs/test46-nomf-B1`, without modifying either model.

The requested certificate contains three complete directions: source MI to target MI, target MI to source MI, and target LP to source LP. Every direction preserves all 61,036 retained coordinates and the exact objective. This establishes integer projection equality and LP inclusion in the reverse direction. It does not claim LP equality, strict LP strengthening, an optimum, or a general feasible-set bijection.

## Actual structure and proof

The source consists of 12 unary one-hot tables and 66 pair tables. Each pair table has one-hot normalization, two state-index moments, and an exact cost definition. The independent Fraction parser and classifier verify all source variables, bounds, rows, objective coefficients, every target marginal, and the target domains. There are no unmatched rows or coordinates. Hint files identify candidates but every claimed pattern is checked against actual model coefficients.

The positive forbidden-entry cost is 39,424, whereas the source objective has upper bound 39,423. Nonnegative costs and exact cost definitions give the total forbidden-selector sum at most 39,423/39,424. Its integer sum rounds down to zero. A balanced nonnegative sum tree proves all 80,785 forbidden selectors individually zero. For each retained marginal, both the pair-table aggregate and its unary table are integer one-hot sequences with equal state moment. Ordinary constant-depth Cases, integer prefix sums, linear combinations, and contradictions prove coordinate equality. All target rows and domains are then checked.

For the reverse MI direction, the actual target marginal equations and nonnegativity imply each surviving pair entry lies between max(0,x_a+x_b-1) and min(x_a,x_b). Since the unary selectors are binary, ordinary Cases prove all 60,608 continuous pair entries integer. A single joint IntervalLift supplies 17,234 AND entries for the 17 deleted constant-cost tables; subsequent Cases prove their integrality and both families of marginal equations. All source bounds, integrality declarations, rows, objective, and retained coordinates are explicit final obligations. In particular, the absent target objective upper bound is restored from the exact tablewise cost upper sum 39,389, below 39,423.

For the reverse LP direction, deleted constant tables require only normalization and their two moments. For normalized endpoint means α, β in [0,1], one interval parameter satisfies max(0,α+β-1) ≤ t ≤ min(α,β). Four actual corner entries receive t, α-t, β-t, and 1-α-β+t. All other entries are zero. This preserves both real moments and the table cost 17 exactly, using 17 joint intervals. No real product is introduced.

## Evidence and reproduction

`lp-only/` preserves the previously verified standalone LP certificate and its original binary identity. `mi-forward/` and `mi-reverse/` contain the standalone complete integer directions. `preparation.json` is the authoritative completed replay and negative-test receipt. All three directions are VERIFIED on the fixed binary and all six attacked certificates are INVALID. The full contract is delivered by `bundle.json`; no individual direction stands for the whole case.

The binary and pre-run identities are in `resume_identity.json`. Authoritative finalization uses the fixed `target/validation-wave-rpx-2026-10-11/release/rpx` path, SHA-256 `694b1083e2f960aa6e9002c0ce20e796b3bcf091a3397810f30aa43f0ec9f655`. `unpinned-finalizer-attempt/` preserves an interrupted attempt whose shared executable path was replaced during execution; that attempt is explicitly excluded from fixed-binary acceptance. The current permitted default work budget is 1,000,000,000. Finalization explicitly replays the same complete RPX at the former 100,000,000 work limit and records its result. Timings are functional replay timings and are not isolated benchmark measurements.

Reproduce from the repository root:

```sh
python3 tools/prepare_test46_full.py --phase forward
python3 tools/prepare_test46_full.py --phase reverse
python3 tools/oracle_test46.py
python3 tools/finalize_test46.py
```

The preserved standalone LP can be rebuilt separately with `tools/prepare_test46.py --kernel target/release/rpx`; doing so replaces its historical receipt, so use a different output directory if preserving that record.

`oracle.json` contains 10,657 independent Fraction checks over generalized state domains, integer marginals, exact real four-corner couplings, and cost cutoffs. These checks supplement complete kernel replay; they are not substituted for actual-model obligations. Initial rejected author attempts are retained separately. No production code or proof rule was changed for this case.

## Final measured result

The three fixed-binary replays discharge 1,105,551 complete output obligations, with 96,947 branches and peak 344,878 live facts. Their work totals are 391,209,842 (MI forward), 152,443,790 (MI reverse), and 7,424,119 (LP reverse), summing to 551,077,751. Each integer direction returns RESOURCE_LIMIT under the former 100,000,000 work policy; LP reverse still verifies there. All three verify under the current 1,000,000,000 policy.

The combined RPA is 432,885,912 bytes and its assembly correctly returns RESOURCE_LIMIT at the unchanged 256 MiB text limit. `combined-attempt.rpa` and its raw failed-assembly receipt are preserved. The accepted delivery is the three-part bundle, each part independently under the text limit and binding the same exact model pair. The manifest includes artifact hashes and the complete directional request paths.

The six negative cases cover an unrelated rounding integer fact, a missing target obligation, LP borrowing of source integer declarations, an omitted interval premise, an incorrect removed cost helper, and a perturbed LP corner. Raw mutant RPA/RPX files and fixed-binary command receipts are in `attacks/`. The supplemental independent read review is `audit/test46_read_review.md`; the only subsequent preparer change was pinning its default executable path.
