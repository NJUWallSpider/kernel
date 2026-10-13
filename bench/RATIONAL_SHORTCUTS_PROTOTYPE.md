# Exact rational shortcuts: isolated V7 candidate

The candidate in `rational-shortcuts-prototype/` is derived from the frozen
`audit/checkpoints/v7-source`. Production is unchanged. The narrow change is
motivated by the exact-arithmetic stacks in the fixed V7 test57 profile; it adds
no numeric representation, trusted theorem, wire format or mathematical rule.

The candidate has passed all 177 frozen core tests and five new tests. A single
test57 diagnostic shows enough potential benefit to justify the parent's fixed
matrix experiment. It is **not yet adopted**, and its repeatable performance,
small-case regression and resident-memory effects remain unmeasured.

## Semantic equivalence and budget preservation

`check_q` first performs the unchanged numerator and denominator bit checks.
If the denominator is exactly one, any signed BigInt numerator is already
coprime to it, including zero, so canonicality needs no gcd. All other values
follow the unchanged positive-denominator and gcd checks.

`Expr::scaled` still validates the scale and the whole expression before its
zero shortcut. For scale one it clones each coefficient; for negative one it
negates it. General products still use `BigRational`. Every resulting coefficient
and constant passes the same check as before. Thus malformed raw rationals do
not gain a public fast path, and the arithmetic domain is unchanged.

`Accumulator::add` chooses the same unit-multiplier paths, then checks each
product before any addition. A previously vacant sparse coordinate stores that
checked product directly; its result is exactly the same rational. Occupied
coordinates retain addition, result validation and exact cancellation removal.
Zero constant addition can become assignment or no operation, but product and
result validation remain. Term-count limits, reservations, proof work accounting
and all checks on oversized intermediate values remain unchanged. In particular,
a product that exceeds 65,536 bits still fails even when a subsequent sum would
cancel it. The private accumulator continues to receive previously validated
expressions from the checker.

## Independent exact checks

`audit/generate_rational_shortcuts_oracle.py` imports only Python standard-library
`fractions.Fraction` and `math.gcd` for arithmetic. Seed `0x52505837` generates 779
scaling cases, 429 accumulator sequences and 20 raw canonicality cases. They
cover zero, both unit signs, arbitrary rational multipliers, cancellation,
127–65,536-bit values, constant and coefficient product/result overflow, and
denominator budgets. Integer payloads are hexadecimal so direct-API bit-boundary
tests do not accidentally test the smaller decimal-input limit instead.

Five test functions consume the independent outputs, attack malformed public
expressions/scales and check that cancellation leaves no retained zero entry.
The frozen byte-format, semantic, state, resource and actual-derived tests also
pass. `validation.json` binds the 182-test result, compiler, lockfile, build,
binary, source diff and oracle hashes. `test.log` and `build.log` retain output.
The original production `model.rs` and `verify.rs` still equal frozen V7 byte
for byte. Independent read review is recorded separately in
`audit/rational_shortcuts_review.md` and binds the exact source diff.

## Single diagnostic, not the fixed benchmark

`diagnostic.json` retains both complete process results, executable hashes and
unchanged actual test57 MCM/RPX/request hashes. Both runs returned VERIFIED;
every mathematical statistic agrees, including 1,956,604 obligations and
35,551,444 work units.

| One fresh process per binary | Baseline | Candidate |
|---|---:|---:|
| Execute ms | 5,489.054 | 2,570.375 |
| CLI total ms | 6,165.978 | 3,136.059 |
| Whole process ms | 6,201.518 | 3,606.954 |

The candidate observation is 53.2% lower in execution time and 41.8% lower in
whole-process time. The baseline ran first, files were warm, caches were not
flushed, and other workers/apps were not isolated. The candidate's gap between
CLI and process elapsed time also illustrates why these are not controlled
distributions. No observations were discarded. Do not replace or combine these
values with the archived V7 baseline. The fixed 26-workload and earlier matrices
must be repeated under the parent's isolated conditions before adoption.

## Reproduction and preserved evidence

The preparation script refuses to overwrite an existing prototype. Preserve
the present evidence and use a fresh checkout/directory for reproduction:

```sh
python3 audit/generate_rational_shortcuts_oracle.py
python3 tools/prepare_rational_shortcuts_experiment.py
cargo test --manifest-path bench/rational-shortcuts-prototype/Cargo.toml -p kernel-core --locked
cargo build --manifest-path bench/rational-shortcuts-prototype/Cargo.toml -p kernel-core --release --locked
python3 tools/diagnose_rational_shortcuts.py
```

The diagnostic likewise refuses to replace its receipt. The tested binary is
`bench/rational-shortcuts-prototype/target/release/rpx`, SHA-256
`cd638f766bb278be097305ac6202bfce7b4a3876333017d7b48b72aa15deb6a0`.
The candidate changes only `model.rs` and `verify.rs` at runtime; its two added
files are test-only. `source.diff` and `experiment.json` describe every change.
