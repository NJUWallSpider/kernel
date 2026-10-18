# Kernel API

`VERIFIED` has one meaning: optimization equivalence of the two complete MILPs. A certificate has exactly two proof trees, `forward` and `reverse`. Both use actual integer declarations and must construct a feasible output with a nonincreasing objective. There is no Request, profile, relation selector, or public one-direction verifier.

## CLI

```sh
rpx canonical source.mps source.mcm
rpx canonical target.lp target.mcm
rpx assemble proof.rpa proof.rpx
rpx verify source.mcm target.mcm proof.rpx
rpx verify --work 1000000000 --live-facts 1000000 source.mcm target.mcm proof.rpx
```

Exactly three paths follow `verify`; flags may occur anywhere after the subcommand. The work budget covers both proof directions. `--depth`, additional proof paths and former Request operands are rejected. Defaults are work=1,000,000,000, live_facts=1,000,000, depth=64. Depth is format-coupled and not a CLI option.

Other commands:

```sh
rpx inspect-model source.mcm
rpx export-model source.mcm source.json
rpx disassemble proof.rpx proof.rpa
```

`assemble` performs RPA 12 syntax and RPX encoding only; `disassemble` emits canonical RPA 12. The old `RPA 11` JSON and `RPA-S 1` headers, `--models`, and `disassemble-source` are rejected. Proof planning and extension preparation are native Python API operations, never CLI commands or certification.

## Rust

```rust,ignore
verify::verify(&source_model, &target_model, &certificate, &limits)?;
api::verify_bytes(&source_mcm, &target_mcm, &proof_rpx, &limits)?;
api::verify_paths("source.mcm", "target.mcm", "proof.rpx", &limits)?;
```

`verify_with_diagnostics` additionally takes caller-owned `Diagnostics`. Library and CLI use the same checking path. Low-level fact and proof-tree execution remains private. The raw object verifier validates both models before using them; byte entry points also enforce canonical encoding.

## Reports and errors

Successful verification returns `status: "VERIFIED"`, `guarantee: "MI_OPT"`, statistics, effective limits and phase timings. Removed claim, point, bijection and improvement counts are absent. Core statistics include obligations, linear/substitution terms, branches, peak live facts, work and the retained constructive-rule counters.

| Status | CLI exit | Meaning |
| --- | --- | --- |
| VERIFIED | 0 | Complete optimization equivalence certified |
| INVALID | 2 | This input or proof is rejected |
| RESOURCE_LIMIT | 3 | A finite resource budget was exceeded |
| IO_ERROR | 4 | File operation failed |

Authoring commands return distinct statuses such as ASSEMBLED; none grants certification. An invalid certificate does not establish inequivalence.

Failures report `message`, a diagnostic `code`, and available location fields `direction` (`forward` or `reverse`), `step`, `obligation`. Locations never affect acceptance. Library callers may attach limits with `Error::with_limits`; the CLI does so after parsing verification flags.

## Authoring plans

Proof planning, witness resolution and constructive extension preparation are
native operations of the Python package (`rpx`). The CLI exposes
only stable artifact operations: canonicalization, assembly, disassembly,
verification, inspection and export. Planning never grants certification.

## Model JSON

Model export uses `name`, `variables`, `rows`, `objective`. A variable has `name`, `integer`, `lower`, `upper`; a row has `name`, `expr`, `lower`, `upper`. Affine expressions contain string `constant` and sorted `[index, string coefficient]` terms. Missing bounds are null. Export preserves the exact canonical model including objective constants and coordinate order.

## Limits and binding

Path reads and generated RPA text are capped at 512 MiB. RPX encoding and verification retain their independent byte, item, depth and rational limits.

Each invocation binds the owned model/proof bytes it reads. It is not a multi-file filesystem transaction. Call `verify_bytes` on already acquired bytes when the caller needs a coordinated snapshot. See [the format](FORMAT.md) and [semantics](SEMANTICS.md).
