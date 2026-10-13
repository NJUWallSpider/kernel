# Exact linear LP importer, version 1

`rpx canonical input.lp output.mcm` dispatches to `crates/core/src/lp.rs` when the input extension is `.lp`, case-insensitively. Other extensions retain the MPS path. The LP parser is trusted code; Python reference/generation scripts and any solver are outside the acceptance boundary. Original files are read without modification.

The importer produces the same `Model` and MCM v1 representation as the MPS canonicalizer. It uses exact `BigRational` arithmetic throughout. Its supported grammar is deliberately explicit rather than a claim that all vendor LP dialects have identical semantics.

## Meaning and canonical order

All objectives are minimized internally. Maximization negates the entire affine objective, including its constant. Affine terms are summed exactly, sorted by variable identifier, and exact zeros are removed. Every variable occurrence declares that variable, including a zero coefficient such as `0 x`; a declaration is not lost when its coefficient subsequently cancels. Variable order is first textual occurrence across objective, rows, bounds and type lists. Constraint order follows the input. Variable and constraint names are case-sensitive.

LP files contain no problem-name field in this subset, so the model name is the fixed string `LP`. An optional objective label is checked syntactically but has no mathematical effect or separate field in `Model`. Named constraint labels are retained. Unnamed constraints receive `_lp_row_0`, `_lp_row_1`, and so on. Duplicate constraint labels are rejected. Names, dimensions, exact data and all declared variables are consequently available for MCM binding.

Continuous and general integer variables initially have bounds `[0,+infinity)`. Explicit bounds replace the default on the stated side. A negative upper bound does **not** silently remove the default lower zero: `x <= -1` without an explicit lower card is an infeasible interval. This LP rule differs from the separately documented MPS negative-upper convention. Contradictory finite variable or row bounds remain valid representations of an empty feasible set.

A Binary declaration means the integer domain `{0,1}` intersected with explicit bounds. For example, binary `x` with `2 <= x <= 7` is retained as `[2,1]`; binary `x free` becomes `[0,1]`. General declarations impose integrality without an implicit upper bound of one. There is no rounding of rational bounds on integer variables, so the LP relaxation remains precisely specified.

## Text grammar

Input is ASCII. A backslash begins a comment extending to the end of that physical line. Blank/comment-only lines are ignored, including after End. Control characters other than line endings and tabs are rejected. Keywords are case-insensitive; each section header must occupy its own line. Whitespace may surround a header.

Required section order is objective, constraints, then End. Optional Bounds follows constraints. Binary, General and Semi type sections follow constraints or Bounds, may appear in any order, and each may occur at most once. Bounds cannot appear after a type section.

| Section | Accepted header aliases |
|---|---|
| Minimization | Minimize, Minimum, Min |
| Maximization | Maximize, Maximum, Max |
| Constraints | Subject To, Such That, St, St., S.t. |
| Bounds | Bounds, Bound |
| Binary | Binary, Binaries, Bin |
| General integer | General, Generals, Gen |
| Empty semicontinuous marker | Semi, Semis, Semi-Continuous |
| End | End |

The empty Semi section is accepted because the observed HiGHS source file emits it even when no semicontinuous variables exist. **Any member in this section is rejected.** This does not enable semicontinuous semantics.

Names begin with an ASCII letter or underscore. Subsequent characters may be letters, digits, or `_.$#(),;!?@{}~%&`. Exponent-ambiguous names consisting of `e`/`E` alone or followed by a digit or another `e`/`E` are rejected. Names cannot equal a reserved section/type keyword, `free`, `inf`, `infinity`, or the explicitly reserved unsupported extension keywords. Quoting, square-bracket names and names beginning with numbers or punctuation are unsupported. The name limit is 1,024 bytes; names are never truncated. Parentheses inside a name remain literal name characters, not expression grouping.

Expressions contain signed terms: an optional numeric coefficient followed by a variable, or a numeric constant. Every term after the first requires `+` or `-`. Coefficients and variable names require separating whitespace (`2 x`); `2x` is rejected. Operators do not themselves require whitespace (`x-y` is accepted). A sign may be separated from its magnitude. Coefficient and variable tokens may be separated across lines in the objective or a named constraint. No multiplication symbol, power, bracketed quadratic block, grouping parentheses or function-call semantics is interpreted.

Numeric literals use the exact scalar parser shared with MPS: decimal integers, decimal fractions, `e/E/d/D` scientific notation, or integer numerator/denominator fractions. An exponent's sign is part of its numeric token. Signed denominators such as `1/-2` are allowed. Rational fractions and affine expressions on both sides are expressly defined local extensions. NaN and infinity are not affine coefficients or constants.

An optional `label:` precedes the objective. Its body must contain an expression; a zero objective is written `0`. If the first constraint is named, a new constraint begins only with a new `label:` at the beginning of a data line; intervening lines continue the current constraint. If the first constraint is unnamed, every physical constraint line must contain one complete unnamed relation. A later named constraint in that mode is rejected. This rule eliminates inference about whether an unlabelled line ends or continues a row.

One-relation constraints have the form `affine <= affine`, `affine >= affine`, or `affine = affine`. The reader subtracts the right expression, then moves the resulting constant into the bound. Thus `x + 1 <= y + 3` becomes `x - y <= 2`. Strict `<` and `>` are rejected.

Ranged rows use `constant <= affine <= constant` or `constant >= affine >= constant`. Both relation directions must match, and both endpoints must simplify exactly to constants. The middle expression's constant moves into both bounds. For example, `1 <= x + 2 <= 3` becomes `-1 <= x <= 1`. Every stored row expression has zero constant. A named ranged row may span physical lines.

Each Bounds record occupies one physical line and supports:

```text
0 <= x <= 3
3 >= x >= -2
x <= 4
-2 <= x
x >= -2
4 >= x
x = 1
1 = x
x free
-inf <= x <= +infinity
```

A bound constrains exactly one unscaled variable. Infinity keywords are case-insensitive and allowed only for a negative infinite lower bound or positive infinite upper bound. An infinite equality bound, positive infinite lower bound or negative infinite upper bound is rejected. The parser does not approximate infinity by a finite constant. Same-side repeated bounds must be identical; conflicting overrides are rejected rather than made order-dependent. Type lists contain whitespace-separated variable names; repeated or conflicting type declarations are rejected. Variables appearing only in bounds or type lists are retained.

## Rejection and resource limits

Unknown sections, SOS, indicators, scenarios, quadratic/nonlinear syntax, nonempty semicontinuous sections, unknown tokens, missing mandatory sections/End, trailing noncomment content and unsupported dialect ambiguities return INVALID. Rejection describes importer capability or invalid syntax, not an inequivalence result.

The importer shares model/numeric limits with [MPS v1](MPS_V1.md): 512 MiB input, 32,768 bytes per physical line, 1,024-byte names, two million variables, two million rows, twenty million coefficient entries/final terms, scalar text/exponent budgets, and a 65,536-bit numerator/denominator arithmetic-result budget. Additionally, an LP file is limited to twenty million lexical tokens. Dimension/token counts and important collection reservations are checked. Resource failures preserve the RESOURCE_LIMIT prefix through line context. Internal arbitrary-precision library allocation failure and forced host termination are not claimed to be recoverable. MCM's independent encoding budgets still apply.

## Evidence and reproduction

The rules were checked against primary format descriptions: [IBM's LP introduction](https://www.ibm.com/docs/en/icos/22.1.2?topic=problem-using-lp-format), [IBM's LP naming rules](https://www.ibm.com/docs/en/icos/22.1.2?topic=representation-variable-names-in-lp-file-format), and [Gurobi's LP format documentation](https://docs.gurobi.com/projects/optimizer/en/current/reference/fileformats/modelformats.html). These references document the common linear vocabulary; differing vendor conventions are not silently imported. In particular, this subset declares its own operator whitespace, repeated-bound/type rejection, binary intersection and range behavior above.

`audit/lp_parse_sweep.py` contains two independent test mechanisms:

1. A Python `fractions.Fraction` reference parser for the precise syntax observed in all three corpus LP files, plus a separately written MCM byte decoder. It compares **every** model field—variable order/domain/bounds, row labels/order/all coefficients/bounds, and complete objective—against the trusted importer's MCM output. It neither calls a solver nor uses the Rust LP parser to construct expectations.
2. A deterministic generator (seed `20261011`) constructing 160 mathematical models with Python Fraction before rendering their LP text. Checked-in expectations exercise both objective senses, exact decimals/exponents/fractions, large integers, affine right sides, ranged rows, multiline layout, duplicate/zero terms, binary/general/free/fixed/rational/contradictory bounds. Rust reconstructs expected rationals directly from their integer numerator and denominator without invoking the production numeric text parser.

Reproduction:

```sh
python3 audit/lp_parse_sweep.py --generate-oracle
cargo test -p kernel-core --test lp
cargo build --release -p kernel-core --bin rpx
python3 audit/lp_parse_sweep.py --corpus /Users/bhz/Code/reform_test/runs
```

Measured result: all **3 / 3** actual LP files canonicalized, and all three full models matched the independent Fraction reference exactly. The immutable-file SHA-256 identities, executable hash and individual outcomes are in `audit/lp_parse_sweep.json`.

| Actual file | Variables | Integer variables | Rows | Nonzero coefficients, including objective |
|---|---:|---:|---:|---:|
| test8 input/model.lp | 4,914 | 2,457 | 13,206 | 134,316 |
| test8 output/reformulated.lp | 4,914 | 2,457 | 12,450 | 127,512 |
| test60 output/reformulated.lp | 2,508 | 2,508 | 2,016 | 36,002 |

The LP integration suite has ten passing tests, including the 160 Fraction vectors and 2,000 deterministic ASCII mutations (seed `0x5250584c5031`). Mutations assert total parsing without panic; legal mutations are permitted to parse. Specific negative tests exercise required rejection rules. Corpus import success is **not** certification of the source/target reformulation relation. Sweep timings are diagnostic, not isolated benchmark claims.
