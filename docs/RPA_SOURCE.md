# Readable RPA-S source

`RPA-S 1` is a readable source grammar for RPX 11's fixed optimization-equivalence proof. Its grammar version does not select proof semantics. It lowers to the same exact two-block Certificate as [RPA JSON](RPA.md).

## Complete source

```text
RPA-S 1
models { source: "source.lp", target: "target.lp" }
certificate {
  forward: {
    steps: [],
    end: Return { map: [expr(x0)], checks: [lower(x0), upper(x0), exact] },
  },
  reverse: {
    steps: [],
    end: Return { map: [expr(x0)], checks: [lower(x0), upper(x0), exact] },
  },
}
```

For this example both models have one continuous variable bounded between zero and one and the same objective. The final `exact` proves objective nonincrease. Integer models additionally need their output integrality checks. Direction orientation comes from `forward` or `reverse`; there is no claims array.

The optional `models` declaration is resolved relative to the source file by the CLI. Explicit `--models source.mcm target.mcm` binds actual models for named checks. Library assembly receives already loaded models and performs no implicit file access.

## Syntax and exact expressions

Identifiers, strings, booleans, arrays, objects, comments and tagged variants lower directly to exact Certificate data. Trailing commas are accepted. `expr(1 - 2*x0 + x3/7)` writes an affine expression; nonlinear multiplication, unknown aliases and unsupported expressions are rejected. Rational values are exact.

Reference forms include `lower(x0)`, `upper(x0)`, `integer(x0)`, `row_lower(0)`, `row_upper(0)`, `row_eq(0)`, local `f0`, `assumption(0)` and `exact`.

Step notation includes `lin.le(f0, lower(x0) + 2*row_upper(0))`, `lin.eq`, `lin.int`, `round(f1, f0, integer(x0))`, `eqpair(f2, f0, f1)` and `drop(f0, f1)`. Explicit Cases, Split and lift records retain the same payloads as JSON.

Aliases and bounded array constructors (`range`, `repeat`, `identity`, `pairs`) are authoring conveniences; they expand before compilation. They neither create facts nor alter the fixed goal. Arithmetic, syntax depth, expanded nodes and output bytes are bounded.

## Named checks

With actual models, Return checks may be an object keyed by obligation names. Names select the independently generated obligations and must cover each exactly once. Variable/row names and numeric coordinates are both supported. The objective label is always `objective.non_increasing`.

```text
checks: {
  variable[0].lower: lower(x0),
  variable[0].upper: upper(x0),
  objective.non_increasing: exact,
}
```

Missing names, unknown names, duplicate obligation bindings and malformed model contexts are rejected. There are no projection, inverse or bijection check labels. Generated lift premises remain explicit old-scope references; the final Return still covers every original target coordinate and row.

## Toolchain and examples

```sh
rpx assemble proof.rpas proof.rpx
rpx disassemble-source --models source.mcm target.mcm proof.rpx recovered.rpas
rpx verify source.mcm target.mcm proof.rpx
python3 tools/check_rpx_manual.py --kernel target/release/rpx
```

Disassembly is deterministic and checked by reassembly. See the complete [redundant-row](rpx/examples/redundant/proof.rpas), [elimination](rpx/examples/elimination/proof.rpas), and [piecewise](rpx/examples/piecewise/proof.rpas) examples. Assembly validates syntax and structure; only verification certifies optimization equivalence.
