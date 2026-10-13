# V7 arithmetic shortcuts and resource-policy repairs

The narrow exact arithmetic prototype is accepted after independent review,
1,228 Python Fraction/gcd oracle vectors, 182 prototype tests, and both unchanged
fixed matrices. All 1,176 measurement processes returned VERIFIED, with identical
artifact bytes and complete mathematical statistics in each pair. The complete
distribution, RSS, regressions and separate preparation accounting are in
`bench/RATIONAL_SHORTCUTS_REPORT.md`; the independent measurement audit is
`audit/rational_benchmark_review.json`. Tiny process-latency regressions remain
visible. No major memory reduction or universal speedup is claimed.

The production changes preserve arbitrary-precision BigRational representation.
After the original numerator/denominator bit checks, denominator one is already
canonical for every integer. Multiplication by ±1 clones or negates a validated
rational. A vacant sparse slot stores its already checked product directly.
Occupied sums and all products retain their intermediate checks. The ordinary
mathematical rules, byte formats, work accounting and proof obligations do not
change. No new trusted theorem is introduced.

Two additional resource-policy repairs are separate from the measured prototype:

1. `Expr::add_scaled`, a public helper, checked its constant sum but omitted the
   temporary product check. With b=2^65535, (-b)+2*b finishes within 65,536 bits
   although 2*b exceeds that intermediate budget. A regression first failed on
   the old helper (it returned Ok), then passes after the product is checked
   before addition. The result was still mathematically exact; this was a budget
   enforcement gap. Existing production verifier/LP call sites pass scale −1,
   so no changed mathematical acceptance on actual certificates was identified.
2. serde_json's unchanged recursion limit of 128 formerly reported INVALID when
   exhausted. Both text entry points now classify that specific parser error as
   RESOURCE_LIMIT. Invalid syntax and unknown fields remain INVALID. The thin
   IntervalLift-chain regression crosses the JSON boundary below the kernel's
   depth limit and verifies the last parsable full certificate. The exact first
   test47 RPA now returns RESOURCE_LIMIT; its old INVALID receipt is preserved.
   The final test47 certificate already fits both limits and requires no waiver.

`audit/validation/v7-resource-repairs/pre-fix-regressions.json` preserves the
failing public-helper test and passing parser regressions. `merged-tests.json`
records all 185 production core tests passing. `deep-attempt-after.json` records
the historical full RPA's corrected status with unchanged input hash.

The immutable `audit/checkpoints/v7-rational-source` snapshot, manifest and
archive contain 498 source/specification/test files. A fresh locked build of that
snapshot passes all 185 tests and replays all 26 actual certificates enumerated
at its start (`audit/validation/checkpoint-v7-rational/run.json`). Test20 was
completed afterward and passes separately in `test20-late.json` using the same
fresh executable. Later cases need their own receipts. The merged executable
hash differs from the measured prototype because of the two explicit repairs;
benchmark numbers must continue to identify their measured source and binary.

The ordinary Rust implementation remains safe Rust with `forbid(unsafe_code)`.
These tests, measurements and reviews are reproducible engineering evidence,
not a formal correctness proof or completion of the 81-case corpus objective.
