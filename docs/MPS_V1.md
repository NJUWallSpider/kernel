# Exact canonical MILP model and MPS input, version 1

`rpx canonical input.mps output.mcm` uses `crates/core/src/model.rs`. This parser and the MCM codec are trusted code. The input file is never modified. Names and declaration order are preserved for subsequent exact model binding; a hash is not a mathematical equality check. The resulting model is a rational-data MILP whose continuous coordinates range over the reals.

## Mathematical representation

A model contains variables in first COLUMNS occurrence order, constraint rows in ROWS order excluding the objective row, and one affine minimization objective. Expressions consist of an exact rational constant and sorted, distinct, nonzero `(variable_id, coefficient)` terms. Variable and row lower/upper bounds are optional rationals; absent bounds represent the corresponding infinity. Integer flags constrain variable coordinates to integers. A row expression includes its constant. Upper bounds smaller than lower bounds are retained: they describe an infeasible model, not invalid syntax. Zero-variable, zero-constraint and constant/infeasible rows are allowed. Exactly one N objective row is required, including for a constant objective.

Every rational has positive denominator and coprime numerator/denominator. Equality and sign tests are exact. Supported numeric literals are signed decimal integers, decimals (`.1`, `1.`, `-1.25`), scientific decimals with `e`, `E`, `d`, or `D`, and signed integer fractions (`-1/3`). Fractions are an explicitly defined exact extension to ordinary decimal MPS. NaN, infinity literals, hexadecimal floats, whitespace inside a number, and zero denominators are rejected. Infinite bounds use FR/MI/PL cards. No binary floating point interpretation occurs.

Maximization negates every objective coefficient and its constant to obtain a minimization objective. An RHS value `b` on the objective row gives objective constant `-b`, before sense normalization. Missing RHS values are exactly zero.

## Supported MPS dialect

Section headers start in column one. Data records are indented. NAME is followed by optional OBJSENSE and OBJNAME, then ROWS and COLUMNS. RHS, RANGES and BOUNDS are optional in that order, followed by mandatory ENDATA. OBJSENSE/OBJNAME may supply their single value on the header or on the following indented card. Objective senses are MIN/MINIMIZE and MAX/MAXIMIZE; default MIN. NAME without a name uses `MODEL`. Headers, keywords and senses are case-sensitive.

The reader accepts whitespace-delimited free MPS and ordinary fixed-column cards with whitespace-free names. A fixed-column COLUMNS, RHS or RANGES continuation may omit the vector/column name only when the first fourteen characters are spaces; a preceding corresponding card is required. Fixed cards with embedded-space names are rejected; column alignment alone does not select a fixed interpretation when its required variable/value fields are absent. Names are ASCII, nonempty and bounded. A first-column `*` begins a comment. A separate token beginning `$` starts an inline comment; consequently names beginning `$` are outside this dialect. Empty lines are ignored. Extra noncomment content after ENDATA is invalid. Coefficient cards contain one or two `(row, value)` pairs.

There must be exactly one N row. E, L and G rows are supported. OBJNAME, if present, must name the sole N row. Repeated row names, unknown row/variable references, unmatched or nested integer markers, and noncontiguous column declarations are rejected. Duplicate coefficient entries on the same column/row are added exactly, including exact cancellation. A column with only zero entries still declares a variable.

There is at most one named vector each for RHS, RANGES and BOUNDS; multiple vectors are rejected, even when another implementation might silently choose the first. Repeating an RHS or range value for a row is rejected.

### Bounds and integrality

Ordinary continuous columns default to `[0,+infinity)`. Columns enclosed by `'MARKER' 'INTORG'` and `'MARKER' 'INTEND'` are integer. A marked integer column with **no explicit bound card** defaults to `[0,1]`. Once a variable has any explicit bound card, the generic `[0,+infinity)` defaults apply to unspecified sides. Thus LI alone declares a general integer variable with an unlimited upper bound; PL on a marked integer also explicitly removes the implicit upper bound of one.

LO and UP set one finite side; FX sets both equal. FR sets both sides infinite; MI removes the lower side; PL removes the upper side. LI and UI set the corresponding side and integer flag, and require an integral bound value. LO/UP/FX may use rational values, including on integer variables. A negative explicit upper bound without any explicit lower card changes the default lower bound to negative infinity; an upper bound of zero retains default lower zero. An explicit lower bound always takes precedence over this negative-upper default. This convention is documented rather than inferred from feasibility.

BV declares the integer domain `{0,1}`. It is intersected with all explicit lower/upper bounds regardless of card order. For example BV plus LO 2 retains `[2,1]` and is infeasible. BV with FR becomes `[0,1]`; BV plus UP -1 retains `[0,-1]`. The optional BV numeric field must be exactly one. FR/MI/PL may not have numeric values. Same-side repeated bound definitions must be identical; conflicting overrides such as LO 1 followed by LO 2 are rejected. Opposite-side contradictory bounds remain valid.

### Ranges

Let `b` be the RHS and `r` the signed range. L rows become `b-|r| <= a*x <= b`; G rows become `b <= a*x <= b+|r|`. E rows with nonnegative range become `[b,b+r]`; E rows with negative range become `[b+r,b]`. Missing range leaves the original one-sided constraint/equality. A zero range produces equality. Ranges on the objective are invalid.

## Explicitly unsupported input

Multiple objective/free N rows; multiple vectors; embedded-space fixed-format names; blank-name initial vectors; noncontiguous columns; conflicting repeated bound overrides; SOS, quadratic, conic, indicator, semicontinuous or semiinteger extensions; unknown sections and bound types. These return INVALID and do not authorize a weakened interpretation. Rejection is a parser capability limitation, not evidence that two models are inequivalent. Particular named solver dialects are not claimed to be interchangeable.

The integer-marker fallback follows the condition described in [IBM's integer-MPS documentation](https://www.ibm.com/docs/en/icos/22.1.1?topic=extensions-integer-variables-in-mps-files): a marked variable with no bound cards has a binary range. LI/UI integrality and the negative-upper default follow [IBM's MPS records documentation](https://www.ibm.com/docs/en/icos/22.1.2?topic=standard-records-in-mps-format). Objective-offset sign and standard marker/range conventions are also documented in [Gurobi's model format reference](https://docs.gurobi.com/projects/optimizer/en/current/reference/fileformats/modelformats.html). Exact rational fractions, order-independent BV intersections, strict rejection of ambiguous vector selection and repeated overrides are explicitly chosen local rules. Primary references guide the declared dialect; solver acceptance is never proof authority.

## Resource behavior

Current implementation constants, separately from mathematical format semantics:

| Resource | Limit |
|---|---:|
| Input MPS bytes | 512 MiB |
| One input line | 32,768 bytes |
| One model/row/variable name | 1,024 bytes |
| Variables | 2,000,000 |
| ROWS records, including objective | 2,000,000 |
| Coefficient entries and final model terms | 20,000,000 |
| Digits per decimal mantissa or fraction component | 4,096 |
| Absolute decimal exponent and effective power of ten | 4,096 |
| Rational numerator/denominator bit length | 65,536 each |

Counts are checked before dimension growth; decimal exponents are bounded before exponentiation. Expression sums/products check operands and result bit budgets, and thus individual temporary rational operations have bounded-size operands. Oversized numbers and accumulated values return RESOURCE_LIMIT; no wraparound or approximate fallback is allowed. Important expression allocations use `try_reserve`; input budgets additionally cap collection growth. As elsewhere in Rust, internal library allocations and host termination are not promised to yield a recoverable error. The MCM/RPX codec has independent size budgets that may reject a model which the text parser alone can represent.

`audit/mps_parse_sweep.py` reproduces the all-corpus canonicalization sweep, records SHA-256 input identity and per-file outcome/timing, and reuses a temporary MCM output. `audit/mps_parse_sweep.json` is its machine-readable measured result. Parser success means only exact model ingestion; it is not reformulation certification. Unit tests in the module cover exact numbers, objective offset/sense, range signs, binary intersections, integer fallback, negative upper bounds, conflicting bounds, zero-variable models, fixed continuations, unsupported syntax and resource status preservation.

Measured corpus result: all **159 / 159** discovered MPS files canonicalized successfully in the final sweep. The initial sweep rejected two valid free-format bound cards because of an overly broad fixed-format ambiguity guard; `mps_parse_sweep_initial.json` retains those results, and `fixed_free_ambiguity_regressions` covers the correction. The input corpus was unchanged. The model test suite contains 13 passing tests, including 2,000 deterministic ASCII mutation cases with seed `0x5250584d505331`. Sweep timings are diagnostic measurements, not isolated performance claims.
