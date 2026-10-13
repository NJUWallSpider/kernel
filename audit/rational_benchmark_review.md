# Independent review of the arithmetic experiment report

Read `tools/report_rational_shortcuts.py`, both benchmark runners and all four
raw result files. `rational_benchmark_review.json` binds their hashes and records
an independent recalculation; no measurement or source file was modified.

All 882 ordinary timing processes and all 294 separate RSS processes returned
VERIFIED with exit zero. For each RSS sample, its recorded byte count agrees
with the positive maximum-resident-set figure in the preserved `time` stderr.
All 49 paired workloads have identical complete artifact hashes and mathematical
statistics. Every reported execution and process min/median/max was recalculated
from all nine samples and matched. The report script explicitly rejects a failed
RSS run or a statistics mismatch; neither is silently excluded from summaries.

The four process-median increases (flow-1, injectivity-1, injectivity-64 and
branch-1) remain visible in the report. RSS increases and timing outliers likewise
remain visible. The earlier isolated theorem baseline, later experiment window,
warm caches and sequential ordering are described, so the report does not imply
a randomized simultaneous A/B experiment.

Preparation is separate: all 198 recorded synthetic canonicalization/assembly
commands succeeded, and all 16 extended actual-case receipt copies match their
bound hashes. Actual theorem preparation is in archived receipt files and the
earlier theorem report, while its raw `preparation` field is empty and generation
time is zero. The report's phrase claiming all preparation times are “in each
raw run” should identify that distinction. This is a presentation correction,
not a hidden failure or changed cost total. Also prefer existing archived receipt
copies when regenerating an old report: requiring a current live case receipt
will fail after a legitimate later revalidation updates that receipt.

No false success, removed workload, omitted RSS failure or changed mathematical
task was found. Later production changes require their own validation and must
not inherit this candidate's measured executable identity.

Follow-up: the report owner implemented both presentation/reproduction fixes.
Read-back confirms actual theorem preparation now explicitly uses archived
historical receipts, with empty/zero fields identified as unmeasured sentinels.
Report regeneration prefers the archived receipt and verifies its bound hash.
The original audit JSON intentionally retains the pre-correction file hashes.
