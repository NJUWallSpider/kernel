# RPA exact JSON assembly

RPA is an exact textual representation of the RPX certificate. Current files begin with `RPA 11` and LF, followed by an object with exactly two required fields: `forward` and `reverse`.

```text
RPA 11
{
  "forward": {"steps": [], "end": {"Return": {"map": [], "checks": ["Exact"]}}},
  "reverse": {"steps": [], "end": {"Return": {"map": [], "checks": ["Exact"]}}}
}
```

This proves equivalence of two feasible zero-dimensional models with equal constant objectives. Every nonempty model additionally requires complete output coordinates and witnesses for all its bounds, rows and integrality.

```sh
rpx assemble proof.rpa proof.rpx
rpx verify source.mcm target.mcm proof.rpx
rpx disassemble proof.rpx recovered.rpa
```

Numbers used as exact rationals are strings, for example `"-3/7"`; coordinate and fact ids are unsigned integers. An expression is `{"constant":"0","terms":[[0,"1"]]}`. Terms are sorted by coordinate and nonzero. A fact reference is an externally tagged enum such as `{"VarLower":0}` or `"Exact"`.

A Block has `steps` and one `end`. A Return has a complete `map` and exactly one reference per kernel-generated obligation. Lin has `id`, `kind`, string `constant`, and `[Ref, string multiplier]` terms. Remaining variants and the exact checking order are defined in [FORMAT](FORMAT.md) and [SEMANTICS](SEMANTICS.md).

There are no Claim, Request, integer-mode, objective-mode, projection, inverse, point, bijection or improvement fields. Unknown fields are rejected. The objective inequality is always required; equality evidence is accepted for the identical inequality.

[Runnable examples](rpx/examples/) provide redundant-row insertion, affine elimination and a piecewise construction. The [readable source language](RPA_SOURCE.md) lowers to the same Certificate without changing its semantics. Historical RPA 1–10 must be migrated rather than merely relabeled.
