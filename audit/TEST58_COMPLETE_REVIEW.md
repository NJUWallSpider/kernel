# Independent test58 complete-contract review

Result: **PASS** for the actual final model pair and the original report's full
directional contract. This is a review of the working V10 draft, not a protocol
freeze. Machine evidence and complete replay commands are in
`audit/TEST58_COMPLETE_REVIEW.json`; reproduce with
`python3 audit/review_test58_complete.py`.

The report explicitly promises feasibility and minimum preservation, with an
objective-preserving target-to-source lift (lines 5, 63, 65 and 67). It explicitly
allows discarding dominated original assignments. The two caller claims match:
source MI to target MI with `NonIncreasing` objective, and target MI to source MI
with `Equal` objective. No requested LP equivalence, coordinate projection or
full feasible-set bijection was omitted; none was promised by that report.
The reported smoke objective values are examples, not an asserted optimum.

An independent stdlib `Fraction` reader, importing no preparer/model helpers,
read all records of the two actual MPS files. It found the original 2,500
variables / 1,750 rows / 1,250 binary coordinates and final 607 variables /
785 rows / 303 binary coordinates. The complete terminal tuples contain all
607 and 2,500 output coordinates. Their 1,697 and 6,751 checks account for
every output bound, integer requirement, row and objective comparison, totaling
8,448. The original raw hashes match the immutable inventory and receipt.

The forward author constructs all activation choices together: 426 edge ORs,
91 path ANDs and two parallel ORs, each with ordinary local integrality proofs.
The 305 simultaneous signed decompositions precede a common 606-arc, 180-node
subflow. This order matters: before subflow extraction, merging the two parallel
paths can give a directional flow of 164. The proof does not pretend that this
already satisfies capacity 82. The common subflow preserves all balances and
has each arc bounded by both its old flow and total demand 82; the final binary
cases establish the actual retained activated capacities. The complete objective
comparison includes all original costs and the target's fixed 205 contribution.
All hints ultimately feed checked actual row/bound premises or final obligations.

The reverse signed lift handles all target points, including a zero-flow path
with activation one. It restores every original coordinate, zeroes the deleted
parallel alternatives, restores bridge flows and proves every original row and
bound. Its objective equality includes the actual `OBJFIX = 1` bound and the
205 bridge contribution. Historical reverse-only and failed local-merge proofs
remain explicitly non-acceptance attempts.

The recorded unchanged production executable was used independently to
recanonicalize both actual MPS files and reassemble the complete RPA. All three
outputs were byte-identical to the submitted MCM/RPX files. The complete proof
verified with both claims and identical non-timing statistics. All eight saved
negative certificates were hash-bound and independently rejected as `INVALID`.
The review also evaluated all seven original complete sample assignments against
every actual bound, domain and row using independent exact arithmetic; their
recorded objectives agree.

No production code, actual case artifact, original input or acceptance ledger
was modified by this review. The Subflow existence lemma remains part of the
trusted implementation; its mathematical/code review is recorded separately in
`audit/SUBFLOW_PRODUCTION_REVIEW.md`. Finite points and attacks support the
review but do not replace the universal kernel proof or constitute a formal
proof of the kernel. These replay timings are functional evidence, not benchmarks.
