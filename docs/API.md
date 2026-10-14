# Kernel interfaces for programmatic callers

This document describes the current public Rust façade and CLI in
`crates/core/src/{api,main}.rs`. They use the frozen MCM 1 and RPX/RPA V1–V10
contracts in [FORMAT.md](FORMAT.md). The façade provides file-based operations
and filesystem-free verification with machine-readable reports.
[POST_DELIVERY_CHANGES.md](../audit/POST_DELIVERY_CHANGES.md) records its
introduction relative to the historical delivery snapshot.

## Rust façade

Crate `kernel_core`, module `api`. Operation entry points return
`Result<serde_json::Value, api::Error>`; the CLI serializes reports as single-line
JSON. I/O helpers and shared types have the separate return types shown below.

| Entry point | Input | Report |
| --- | --- | --- |
| `canonicalize_path(input, output)` | trusted MPS/LP file | `CANONICALIZED` + dimensions, byte count and phase timings |
| `compile_certificate_json(text)` | raw structured Certificate JSON | RPX bytes, no filesystem or RPA assembly |
| `compile_certificate_paths(input, output)` | raw Certificate JSON file | `COMPILED` + RPX version, byte count and total time |
| `plan_return_paths(input, output, plan, obligations)` | current oriented MCM scopes + Return plan JSON | `PLANNED` + ordered proposition array written to JSON |
| `prepare_injectivity_paths(input, output, plan, result)` | oriented MCM models + full affine map | `PREPARED` + complete paired model, equality goals and builder statistics |
| `assemble_paths(input, output)` | frozen JSON RPA or readable RPA-S file | `ASSEMBLED` + byte count and total time |
| `assemble_paths_with_models(input, output, source, target)` | RPA-S and actual LP/MPS/MCM models | as `assemble_paths` |
| `disassemble_paths(input, output)` | RPX file | `DISASSEMBLED` |
| `disassemble_source_paths(input, output)` | RPX file, readable RPA-S output | `DISASSEMBLED` |
| `disassemble_source_paths_with_models(input, output, source, target)` | RPX and actual models, named checks and file declarations in output | `DISASSEMBLED` |
| `inspect_model_path(input)` | MCM file | `INSPECTED` + name, variable/row counts, integer count, nonzeros |
| `export_model_paths(input, output)` | MCM file | `EXPORTED` + dimensions and written bytes |
| `verify_paths(source, target, proof, request, limits)` | four files | `VERIFIED` + contract counts, statistics, limits, timings |
| `verify_bytes(source, target, proof, request, limits)` | bytes + text, no filesystem | as `verify_paths`, without the `read_us` phase |
| `read_input` / `read_text` / `write_output` | one file | bytes / UTF-8 text / unit |
| `limits_json(limits)`, `Status`, `Error`, `Timings` | — | shared building blocks |

`Status` carries both the status word and its process exit code, so a caller
never re-derives either from the report text.

The lower-level `model`, `proof`, `codec`, `rpa`, `rpa_source`, `verify`, `point`, `flow`,
`interval`, `menu`, `injectivity`, `signed`, `subflow` and `level` modules are
also public. Callers can construct `proof::Certificate` / `proof::Request` values
directly, encode them with `codec`, or verify them with `verify::verify_request`.
Joint-extension preparation helpers return unchecked premises; they are not
acceptance entry points. The `compiler` module accepts structured Certificate
JSON directly and exposes `ReturnPlan` / `plan_return` for the verifier's own
ordered terminal propositions. It performs no proof search or synthesis.
[Compiler API demand](COMPILER_API_DEMAND.md) motivates the Python authoring
layer built on these operations.

`rpa_source::assemble(&str)` and `rpa_source::disassemble(&Certificate)` provide
filesystem-free readable proof assembly. The independent `RPA-S 1` source grammar
lowers to the existing frozen Certificate/RPX types; it supplies no proof search
or implicit witnesses. See the [readable source tutorial](RPA_SOURCE.md).
The existing `rpa` module remains the strict JSON RPA V1–V10 codec.
Named obligation checks use `rpa_source::assemble_with_models` and
`disassemble_with_models`; the filesystem-free APIs take two complete `Model`
values. File APIs load optional `models { source: "...", target: "..." }`
declarations relative to the source file. Explicit `--models` parameters override
the declaration. Models select and validate obligation names; the verifier still
checks every supplied reference independently.

## Statuses and exit codes

| Status | Exit | Meaning |
| --- | ---: | --- |
| `VERIFIED` | 0 | proof verification succeeded |
| `CANONICALIZED` | 0 | model canonicalization succeeded |
| `ASSEMBLED` | 0 | RPA text assembled |
| `COMPILED` | 0 | structured Certificate JSON encoded to RPX |
| `PLANNED` | 0 | terminal propositions enumerated, without accepting evidence |
| `PREPARED` | 0 | candidate proof domain constructed, without accepting evidence |
| `DISASSEMBLED` | 0 | RPX disassembled |
| `INSPECTED` | 0 | model inspected |
| `EXPORTED` | 0 | model exported as JSON |
| `INVALID` | 2 | input rejected: malformed, mismatched or mathematically invalid |
| `RESOURCE_LIMIT` | 3 | a documented budget was exhausted; neither verification nor refutation |
| `IO_ERROR` | 4 | input/output failure |

## Failure reports

Failure reports carry a status and message, with machine-readable `code` and
optional `location` / `limits`:

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
rpx canonical input.lp output.mcm
rpx compile certificate.json proof.rpx
rpx plan-return input.mcm output.mcm plan.json obligations.json
rpx prepare-extension input.mcm spec.json output.json
rpx prepare-injectivity input.mcm output.mcm spec.json result.json
rpx assemble input.rpa output.rpx
rpx assemble input.rpas output.rpx
rpx disassemble input.rpx output.rpa
rpx disassemble-source input.rpx output.rpas
rpx assemble --models source.mcm target.mcm input.rpas output.rpx
rpx disassemble-source --models source.mcm target.mcm input.rpx output.rpas
rpx inspect-model model.mcm
rpx export-model model.mcm output.json
rpx verify [--work <u64>] [--live-facts <usize>] source.mcm target.mcm proof.rpx request.json
```

`export-model` writes the canonical model as JSON (below). `verify` accepts the
options anywhere after the subcommand and reports the effective work, live-fact
and depth budgets in `limits`, including on failures after argument parsing.

## Direct structured proof compilation

`compile` deserializes raw `proof::Certificate` JSON and calls
`codec::encode_certificate` directly. It needs neither an RPA header nor an
intermediate source file. The encoder chooses the lowest necessary RPX version
and preserves all frozen schema, scalar, canonical expression and wire limits.
The direct JSON bridge uses the façade's 512 MiB input-file policy, avoiding
the legacy RPA assembler's separate 256 MiB text cap.
For example, a real-domain identity map without an objective contract has this
shape (its checks depend on the actual output model):

```json
{"claims":[{"reverse":false,"input_integers":false,"output_integers":false,
            "objective":"None","projection":[],"inverse":null}],
 "blocks":[{"steps":[],"end":{"Return":{
     "map":[{"constant":"0","terms":[[0,"1"]]}],
     "checks":[{"VarLower":0},{"VarUpper":0}]}}}]}
```

Compilation establishes schema and wire validity. The independently supplied
models and caller request remain required for correctness verification. RPX
contains no model hash or model content; `verify` checks the complete actual
source and target models against the caller's requested contracts.

`plan-return` takes the already-oriented current input and output scopes, then a
JSON object `{claim, map, inverse_map?, inverse_level?, compositions?}`. The claim
uses the existing `proof::Claim` schema; maps contain exact `Expr` objects.
`inverse_map` is the opposing affine map when `claim.inverse` is present,
`inverse_level` is its requested objective level when relevant, and
`compositions` lists opposing forward maps required by bijections. The output
file is an ordered array of `{kind, expression, origin}`; `kind` is `Le`, `Eq` or
`Int`, and the expression is normalized to `e <= 0`, `e = 0` or `INT(e)`.
`origin` identifies variable/row constraints by dotted `kind`, zero-based
`index` and `name`, or contract obligations by `kind` and optional index/group.

The planner shares the verifier's streaming terminal walker, including bound,
row, objective, projection, inverse, objective-domain and bijection composition
order. It creates no witnesses. When a current input scope comes from an
unchecked extension builder, every returned premise must still be proved in
the parent scope before the verifier permits that extension.

For V10 strict-improvement proofs, the Return plan may include
`improvement: {claim: {target, integers, positive}, margin: {Constant: "q"}}`
or a `{Predicate: "q"}` margin. Its ordinary `claim` must match the verifier's
improvement context: `reverse: false`, identical input/output integer modes,
`objective: "NonIncreasing"`, and no projections, inverse or domain restriction.
The output is the complete original same model, while the current input may
include checked extensions. The positive expression is always validated in the
original output coordinates. The same margin builder is used when planning and
when verifying; both require a strictly positive scalar.

`prepare-injectivity` accepts `{map: [Expr, ...]}` and returns
`{model, equalities, statistics}`. The model is the kernel's complete paired
input domain with the full specified affine map equated between its two copies.
Each equality goal requires fresh-scope evidence; preparation also succeeds for
noninjective maps and does not prove injectivity. Input integer declarations are
preserved, and the eventual proof must use the original directional integer mode.

## Semantic handles for prepared extensions

`prepare-extension` returns `{model, premises, statistics, layout}` for all five
constructive extension families. `layout` is an array in witness/group order;
every variable/row handle is a zero-based index in the complete returned model.
Names are obtained from that actual model, so collisions and nested extensions
require no caller arithmetic or generated-name assumptions.

| Family | One layout entry | Meaning of generated rows |
| --- | --- | --- |
| Interval | `{variable, lower_rows, upper_rows}` | each bound in caller order: `variable - bound >= 0` or `<= 0` |
| Menu | `{options, sum_row, moment_row}` | `sum(options) = activation`; `sum(j * options[j]) = index` |
| Signed | `{positive, negative, positive_activation, negative_activation, flow_row, activation_row, positive_capacity_row, negative_capacity_row}` | `positive - negative = flow`; activation parts sum to activation; each flow part is bounded by capacity times its activation |
| Flow | `{source, commodities: [{sink, demand, flows, balance_rows}], recovery_rows}` | each commodity's node balances, followed by equality of each original arc flow with its commodity sum |
| Subflow | `{source, flows, balance_rows, remainder_nonnegative_rows}` | retained flows' node balances; each retained arc flow is at most its original flow |

Commodity `demand` is an exact rational string. Flow arrays follow the caller's
arc order; balance arrays follow node order. Rows for interval bounds preserve
the order of their corresponding lower/upper expression arrays. Menu options
follow index order `0..maximum_index`. These handles describe the existing frozen
builder layout after preparation; they are metadata only. Prefixes and final
variable/row cursors are checked against the actual prepared model, and neither
verification decisions nor builder work charges depend on this metadata.

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
