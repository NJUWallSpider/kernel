# Kernel interfaces for programmatic callers

This document describes the surface added after the delivered snapshot
(see [POST_DELIVERY_CHANGES.md](../audit/POST_DELIVERY_CHANGES.md) for the exact
divergence). Wire formats, verification rules and the resource policy are
unchanged: MCM 1, RPX 1–10, RPA text and the status vocabulary documented in
[CURRENT_FORMAT.md](CURRENT_FORMAT.md) still apply. What is new here is a named,
machine-readable interface for callers that are not a shell script.

## Rust façade

Crate `kernel_core`, module `api`. Every entry point returns a single-line JSON
`serde_json::Value` report or an [`Error`].

| Entry point | Input | Report |
| --- | --- | --- |
| `canonicalize_path(input, output)` | trusted MPS/LP file | `CANONICALIZED` + dimensions, byte count and phase timings |
| `assemble_paths(input, output)` | RPA text file | `ASSEMBLED` + byte count and total time |
| `disassemble_paths(input, output)` | RPX file | `DISASSEMBLED` |
| `inspect_model_path(input)` | MCM file | `INSPECTED` + name, variable/row counts, integer count, nonzeros |
| `export_model_paths(input, output)` | MCM file | `EXPORTED` + dimensions and written bytes |
| `verify_paths(source, target, proof, request, limits)` | four files | `VERIFIED` + contract counts, statistics, limits, timings |
| `verify_bytes(source, target, proof, request, limits)` | bytes + text, no filesystem | as `verify_paths`, without the `read_us` phase |
| `read_input` / `read_text` / `write_output` | one file | bytes / UTF-8 text / unit |
| `limits_json(limits)`, `Status`, `Error`, `Timings` | — | shared building blocks |

`Status` carries both the status word and its process exit code, so a caller
never re-derives either from the report text.

## Statuses and exit codes

| Status | Exit | Meaning |
| --- | ---: | --- |
| `VERIFIED` | 0 | proof verification succeeded |
| `CANONICALIZED` | 0 | model canonicalization succeeded |
| `ASSEMBLED` | 0 | RPA text assembled |
| `DISASSEMBLED` | 0 | RPX disassembled |
| `INSPECTED` | 0 | model inspected |
| `EXPORTED` | 0 | model exported as JSON |
| `INVALID` | 2 | input rejected: malformed, mismatched or mathematically invalid |
| `RESOURCE_LIMIT` | 3 | a documented budget was exhausted; neither verification nor refutation |
| `IO_ERROR` | 4 | input/output failure |

## Failure reports

Successful reports are unchanged from the delivered CLI. Failure reports gained
two machine-readable keys:

```json
{"status":"INVALID",
 "message":"INVALID obligation mismatch: expected Eq; obligation 3",
 "code":"obligation_mismatch",
 "location":{"claim":0,"block":5,"step":12,"obligation":3},
 "limits":{"work":1000000000,"live_facts":1000000,"depth":64}}
```

- `code` — `snake_case` rendering of the failure phrase drawn from the documented
  message vocabulary, so the common cases are switchable without parsing prose:
  `obligation_mismatch`, `missing_obligation`, `proof_work_budget`,
  `requested_contract_mismatch`, `empty_request`, `io_error`, `usage`. Layers that
  prefix their detail with a single namespace token keep it as a prefix and add
  the first two detail words (`INVALID point: strictness witness violates …` →
  `point_strictness_witness`). The message vocabulary is not frozen, so a
  consumer that needs a hard guarantee should switch on `status` plus `location`
  and treat `code` as a diagnostic aid.
- `location` — present when the verifier could attribute the failure. Fields are
  omitted when unknown; all indices are 0-based.
- `limits` — present once the caller has effective limits: for the CLI after
  argument parsing, for library callers after `Error::with_limits`.

## Verifier diagnostics

| Field | Meaning |
| --- | --- |
| `claim` | index into `Request::claims` |
| `point` | index into `Request::points` |
| `block` | index of the top-level certificate block under verification |
| `step` | 0-based index of the step executing inside the innermost active block |
| `obligation` | 0-based index of the terminal obligation being checked, in the order the verifier checks them |

Diagnostics are best-effort: they are recorded while walking the proof and are
only meaningful on the error path. They never feed a decision, a counter or a
budget, and a successful call leaves them unspecified. Library callers that want
the location of a failure call `verify::verify_request_with_diagnostics` and
inspect the `Diagnostics` value they passed in; `api::verify_bytes` and
`api::verify_paths` do this for you and attach the location to the `Error`.

## Command line

```
rpx canonical input.mps output.mcm
rpx assemble input.rpa output.rpx
rpx disassemble input.rpx output.rpa
rpx inspect-model model.mcm
rpx export-model model.mcm output.json
rpx verify [--work <u64>] [--live-facts <usize>] source.mcm target.mcm proof.rpx request.json
```

`export-model` writes the canonical model as JSON (below). `verify` accepts the
options anywhere after the subcommand and reports the effective work, live-fact
and depth budgets in `limits`, including on failures after argument parsing.

## Canonical model JSON

`export-model` (and `model::to_json`) emits exactly the loaded MCM content, in
the model's own canonical order:

```json
{"name": "test84",
 "variables": [{"name": "x1", "integer": true, "lower": "0", "upper": "1"}],
 "rows": [{"name": "c1", "expr": {"constant": "0", "terms": [[0, "1"], [3, "-2"]]},
           "lower": null, "upper": "5"}],
 "objective": {"constant": "-1/2", "terms": [[2, "3/4"]]}}
```

- Every rational is a string. The grammar is the one `parse_q` already accepts —
  integer, `n/d`, decimal or scientific — and the emitter writes the canonical
  `BigRational` form: an integer as `"3"`, anything else as `"n/d"`.
- `terms` are `[variable index, coefficient]` pairs in ascending coordinate order
  with non-zero coefficients, as guaranteed by the wire format's canonicality.
- JSON object key order is whatever `serde_json` emits (alphabetical with this
  build's feature set); consumers must read by key, not by position. Array order
  — variables, rows, terms — is the model's own canonical order.
- `lower`/`upper` are `null` when the side is unbounded.
- Missing optional sides, empty expressions and unbounded variables are
  preserved; a model read back through the documented scalar grammar re-encodes
  to the identical MCM bytes.
- `Model`'s own `Serialize` derive is **not** canonical for the four bound
  fields: without `rpa::option_scalar` they serialize as nested rational pair
  arrays. Use `model::to_json` (or the `export-model` command) for any
  interchange; the derive stays for internal use only.
