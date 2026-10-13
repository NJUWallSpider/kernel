# RPA nesting resource classification review

The preserved first test47 attempt is at
`cases/test47/attempts/linear-and/preparation.json`. Its complete RPA has JSON
container depth 186 and mathematical proof depth 53. Assembly stopped with
`recursion limit exceeded` before mathematical checking and reported INVALID.
The logical proof fits the kernel depth limit 64; the fixed serde JSON limit 128
was the exhausted resource. This result should be classified RESOURCE_LIMIT.
It does not refute either the certificate mathematics or the model relation.

Keep the bounded parser policy unchanged. Classify serde's exact recursion-limit
error as RESOURCE_LIMIT in both certificate and request parsing; keep ordinary
syntax, unsupported fields and malformed scalars INVALID. Existing explicit byte
and exact-number budgets retain their resource classifications. Do not disable
recursion checking or infer successful parsing from a pre-scan.

Recommended regression cases construct thin, known-schema IntervalLift chains
on either side of the serde boundary while remaining below logical depth 64.
The lower chain assembles; the first over-limit chain returns RESOURCE_LIMIT.
Malformed JSON and unknown fields at shallow nesting still return INVALID.
The original historical receipt must remain unchanged after the correction.

The final test47 proof uses balanced sum splits and already assembles at JSON
depth 126 / mathematical depth 38. It requires no limit relaxation. This note is
an independent review and recommendation; production classification is owned by
the root agent and was not edited by this reviewer.
