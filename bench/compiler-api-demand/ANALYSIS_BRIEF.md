# Brief: per-case compiler-API demand analysis

You are analysing **one** case out of 81. Your output feeds the design of the compiler
layer that will sit on top of the RPX exact-reformulation kernel (repo `/Users/bhz/Code/kernel`,
your cwd). That compiler must turn a *justified reformulation finding* — the kind the
solver-blind analysis agent produced — into a kernel certificate set: `source.mcm`,
`target.mcm`, `request.json` (the caller claims) and `proof.rpa` → `proof.rpx`.

Question to answer for your case: **which API capabilities does the compiler most need so
that proving this case is natural and efficient?** That is, what should the API *look like*?
Answer with evidence, not opinion.

## Evidence sources for your case (all paths relative to cwd unless noted)

1. **The domain agent's trajectory** — what the reformulation required mathematically, and
   what the agent had to do by hand.
   - Pre-generated digest, read this first and fully: `/tmp/rpx-digests/<case>.md`.
     It holds: the agent's final report **verbatim**, the evaluation row (turns, tool calls,
     failures, tokens, wall time), its commentary, every `eval` Python snippet in order, its
     failing tool results, and a census of the framework members it touched.
   - Raw transcript if the digest is not enough: `/Users/bhz/Code/reform_test/runs/<case>-nomf-B1/session.jsonl`
     (JSONL; `read("<path>?q=<jq filter>")` works; 200 KB – 500 KB). Two earliest cases,
     `test8` and `test9`, use a root-level session export instead — the digest header names it.
   - The agent's independent audit script: `.../output/verify.py` or `verify_audit.py`
     (this is mechanical verification the agent had to invent), plus `output/audit.json`.
   - Input and reformulated model: `.../input/model.mps`, `.../output/reformulated.mps`
     (up to hundreds of MB — never read wholesale; `rpx inspect-model`/`export-model` exist
     and are cheap-to-moderate, and `python3 tools/digest_reform_run.py <case>` regenerates the digest).
2. **The kernel-side case** — `cases/<case>/`.
   - `README.md`: the delivered certificate — claims, construction, resource policy, attacks,
     preserved attempts. Read it fully.
   - `preparation.json`: authoritative commands, kernel work counts, limits, binary hash.
   - `request.json`: the caller contract (claims/improvements and their obligations) — can be
     MBs; summarise with `read("<path>?q=...")`/jq-style queries, never dump.
3. **Today's compiler prototype for this case** — the Python RPA generator that actually built
   the certificate: `tools/prepare_<case>*.py` (and whatever it imports from sibling preparers,
   e.g. `tools/prepare_affine.py`). This is the most direct missing-API evidence: every helper
   it defines by hand, every RPA JSON shape it assembles, every `rpx` subprocess call it makes
   is a capability the compiler layer must own. Report its size, its `def` inventory, its
   imports, and the shapes it emits.

## Kernel API baseline (today)

- CLI: `rpx canonical <mps|lp> <mcm>`, `assemble <rpa> <rpx>`, `disassemble <rpx> <rpa>`,
  `inspect-model <mcm>`, `export-model <mcm> <json>`, `verify <source.mcm> <target.mcm> <proof.rpx> <request.json> [--work N --live-facts N]`.
  Statuses: `VERIFIED`/`CANONICALIZED`/`ASSEMBLED`/`DISASSEMBLED`/`INSPECTED`/`EXPORTED` exit 0;
  `INVALID` exit 2; `RESOURCE_LIMIT` exit 3; `IO_ERROR` exit 4. Failure reports carry
  `code` and `location{claim,point,block,step,obligation}` (recent addition). Doc: `docs/API.md`.
- Rust façade `kernel_core::api`: `canonicalize_path`, `assemble_paths`, `disassemble_paths`,
  `inspect_model_path`, `export_model_paths`, `verify_paths`, `verify_bytes`,
  `read_input`/`read_text`/`write_output`, `Error{status,message,code,location,limits}`,
  `Status`, `Timings`, `limits_json`, plus `model::to_json` for the canonical model JSON.
- **There is no public proof-construction API.** Trusted constructors live only in test files
  (`crates/core/tests/*_builder.rs`) and crate-private test support (`crates/core/src/build_support.rs`).
  Production callers must emit RPA text/JSON by hand — which is why 90 hand-written Python
  preparers exist under `tools/`.
- Rule families by minimum version (`docs/CURRENT_FORMAT.md`, "Capability history"): 1 whole-model
  affine direction proofs, Lin/Round/Drop, Return/Split/Absurd; 2 EqPair + local Cases; 3 Plotkin,
  objective lower bounds, feasible/strictness points; 4 common-source joint FlowLift; 5 independent
  IntervalLift + affine observations; 6 complete-fiber strictness + point refutation payload;
  7 optional MenuLift + explicit complete-domain bijection pairs; 8 activated signed real
  decomposition; 9 (unfrozen) caller-declared objective-level input domains; 10 (unfrozen,
  implemented) strict improvement, complete-image exclusion, explicit affine input restrictions
  (input halfspace / objective level), joint bounded subflow.
- Budgets: default work 1,000,000,000 (historical 100,000,000), live facts 1,000,000, depth 64,
  RPA/request text 256 MiB, CLI file read 512 MiB, model 2,000,000 vars / 2,000,000 rows /
  20,000,000 terms, exact arithmetic 65,536 bits, proof nesting 64. Exceeding a budget yields
  `RESOURCE_LIMIT`, which is neither verification nor refutation.

## Capability vocabulary (use these IDs; add `NEW:<name>` only if none fits, and justify)

| ID | gloss |
|---|---|
| `MODEL_READBACK` | canonical model → typed structure (vars, bounds, objective, rows, terms, kinds) for the compiler |
| `SCOPE_QUERIES` | scope / fiber / incidence / degree / prefix / chain queries without materialising the model |
| `TARGET_CONSTRUCTION` | apply a structured edit (delete column, substitute value, tighten bound, add row/halfspace) to source → target model |
| `EDIT_AUDIT` | the edit list as data (per-record diff, source line refs) binding target to claim |
| `RULE_BUILDERS` | typed constructors for the rule families (Flow/Interval/Menu/Injective/Signed/Point/Fiber/Subflow/Level/State) with precondition checks |
| `BATCH_TEMPLATES` | loop/template generation of thousands of homogeneous obligations; compact representation to fit the 256 MiB text limit |
| `CLAIM_PLANNING` | given source/target + intended contract, enumerate the obligations to prove and which rule discharges each |
| `INCREMENTAL_VERIFY` | verify per claim / re-verify only what changed; partial acceptance |
| `DIAGNOSTICS` | structured failure `code` + `location{claim,point,block,step,obligation}` |
| `WORK_PREFLIGHT` | estimate work / bytes / depth / live facts before assembling; choose a cheaper representation |
| `ORACLE_CHECKS` | independent honest oracle for a builder or construction (cross-implementation agreement) |
| `COUNTEREXAMPLE_TESTING` | mutate claim/proof, require `INVALID` (bound the claim, attack harness) |
| `WITNESS_CHECKING` | check a specific source point / assignment / halfspace against source and target rows exactly |
| `PROJECTION_BINDING` | bind a projected or restricted claim to caller-supplied coordinates (e.g. `P<=0` halfspace, objective level) |
| `OBJECTIVE_ALGEBRA` | exact objective difference / slack / margin arithmetic over canonical rationals |
| `MULTI_PART_ASSEMBLY` | split one certificate across parts when a text limit binds; verify all parts as one contract |
| `REUSE_LIBRARY` | named reusable facts/lemmas across cases (no cross-file references exist today) |
| `MODEL_SHAPE_STATS` | cheap exact statistics/fingerprints (counts, degrees, coefficient multisets, distinct scopes) to form hypotheses |
| `EXACT_ARITHMETIC` | exact rational utilities (parse, compare, canonical form) exposed to the compiler |
| `LIMIT_POLICY` | resource-policy knobs and their interaction (`RESOURCE_LIMIT` vs. proof failure) |

## Rules

- Every `api_needs[].evidence` must name a real file with a location (`tools/prepare_test36_full.py:126`,
  `cases/test36/README.md`, `/tmp/rpx-digests/test36.md` transcript event, `.../output/verify.py:40`).
  Every factual statement about the case must be traceable there. Never invent a fact, number,
  helper name or quote.
- `sketch` is the point of the exercise: give the concrete API shape (a Rust signature line, a CLI
  form, a small JSON fragment). Example: `Mcm::load(path) -> Model`, or
  `fn flow_lift(m:&Model, group:&Scope, support:&[Ref], mode:Mode) -> Result<Step, BuildError>`.
- `scope`: `case_only` | `shared` (name the sibling cases if you know them) | `universal`.
- 2–6 needs, ranked by how much **this case** needs them (`priority` 1 = highest). Do not pad with
  generic wishes, and do not restate the same need twice.
- Read-only: never modify files, never run `cargo`, never re-verify a multi-MB RPX. Cheap commands
  (`python3 tools/digest_reform_run.py`, `rpx inspect-model` on a small MCM, `read` with ranges) are fine.
- Strings must be self-contained: the aggregator sees only your JSON, never your reasoning.
- If a need is genuinely universal (nearly every case wants it), say `universal` and keep it; if you
  cannot tie it to this case's evidence, drop it.

## Case index (look up your row)

Sizes: `orig v/r` = original variables/rows, `new v/r` = reformulated. `rpa`/`rpx`/`req` are this case's
delivered artifact sizes in MB/KB (`cases/<case>/`). `preparer` = the Python RPA generator(s) that built the
certificate (under `tools/`); `lines` = their combined line count. `turns/fail` = the analysis agent's turns
and failing tool calls. `report title` = the agent's own headline for the reformulation.

| case | prep_lines | orig v/r | new v/r | rpa MB | req KB | turns/fail | preparer | report title |
|---|---:|---|---|---:|---:|---|---|---|
| test8 | 123 | n/a | n/a | 8.4 | 166.7 | ?/? | prepare_test8 | Final committed formulation |
| test9 | 94 | n/a | n/a | 0.8 | 64.7 | ?/? | prepare_test9 | Final committed result |
| test10 | 247 | 190402/2303 | 190201/2105 | 104.8 | 8267.1 | 14/0 | prepare_test10 | Final commitment: exact load elimination, selector projection, and bud |
| test11 | 86 | 62529/121161 | 40488/90561 | 39.2 | 2127.8 | 16/0 | prepare_test11 | Final commitment: exact alias elimination and redundancy removal |
| test12 | 96 | 7195/426 | 6200/310 | 5.8 | 282.6 | 15/0 | prepare_test12 | Final committed result: exact set-partitioning reduction |
| test13 | 114 | 10399/14589 | 5677/14571 | 4.6 | 258.0 | 19/1 | prepare_test13 | Final commitment: exact projection of 18 private one-hot encodings |
| test14 | 92 | 1166/2295 | 1046/1804 | 0.6 | 31.1 | 27/2 | prepare_test14 | Final commitment: exact cleanup and binary-conflict disaggregation |
| test15 | 94 | 4516/32 | 4485/32 | 5.8 | 202.2 | 15/1 | prepare_test15 | Final commitment: exact singleton elimination |
| test16 | 91 | 228350/126512 | 198848/100518 | 109.7 | 11667.7 | 17/0 | prepare_test16 | Final commitment: exact forced-zero reduction |
| test17 | 74 | 57756/3757 | 57756/1765 | 22.0 | 2304.1 | 15/0 | prepare_test17 | Final commitment: exact redundancy removal and binary order-chain refo |
| test18 | 129 | 20617/2147 | 1146/929 | 38.0 | 40.8 | 17/1 | prepare_test18 | Final committed reformulation |
| test19 | 155 | 1462/1655 | 1459/1668 | 0.7 | 45.2 | 15/0 | prepare_test19 | Final commitment: exact projection and mixed-integer strengthening |
| test20 | 97 | 13873/3202 | 13849/3138 | 4.9 | 2402.3 | 18/1 | prepare_test20 | Final commitment: exact affine elimination and redundancy removal |
| test21 | 661 | 87482/36 | 46168/35 | 56.6 | 0.5 | 17/1 | prepare_affine,prepare_test21,prepare_test40 | Committed solver-blind reformulation of test21 |
| test22 | 122 | 397/171 | 213/171 | 0.2 | 8.6 | 21/0 | prepare_test22 | Final commitment: exact affine size reduction |
| test23 | 163 | 24793/10112 | 5826/5177 | 16.0 | 1036.2 | 19/1 | prepare_test23 | Final commitment: exact signed-difference reformulation |
| test24 | 201 | 10100/10180 | 2407/2487 | 160.3 | 2.8 | 19/1 | prepare_test24 | Final commitment: exact optimality-preserving reduction |
| test25 | 107 | 11659/18442 | 11064/16193 | 5.0 | 391.0 | 17/0 | prepare_test25 | Final committed result |
| test26 | 87 | 11717/10460 | 11717/10460 | 4.9 | 1514.4 | 16/0 | prepare_test26 | Final committed reformulation |
| test27 | 120 | 3040/1920 | 1520/1919 | 3.0 | 558.2 | 17/1 | prepare_test27 | Final commitment: signed-flow / shared-activation reformulation |
| test28 | 150 | 2550/1062 | 850/302 | 2.9 | 12.9 | 24/3 | prepare_test28 | Final commitment: exact common-source aggregation |
| test29 | 143 | 17680/69608 | 15924/2624 | 97.8 | 591.5 | 17/0 | prepare_test29 | Final commitment: exact support-class reformulation |
| test30 | 144 | 35378/16516 | 32337/14717 | 15.5 | 1691.2 | 18/0 | prepare_test30 | Final commitment: exact projected reformulation |
| test31 | 192 | 364417/14733 | 334717/14026 | 119.0 | 10043.4 | 21/4 | prepare_test31 | Final commitment: exact projected reduction of `s100` |
| test32 | 138 | 18380/576 | 4792/382 | 16.2 | 170.8 | 18/1 | prepare_test32 | Final commitment: exact choice-and-row reduction |
| test33 | 233 | 6250/160633 | 6250/70633 | 38.9 | 284.7 | 16/1 | prepare_affine | Final commitment: exact transitive row deletion |
| test34 | 119 | 53593/106954 | 53593/53824 | 176.8 | 2133.4 | 15/1 | prepare_test34 | Final commitment: grouped bounds on z |
| test35 | 87 | 4456/1667 | 3510/675 | 2.0 | 157.2 | 19/0 | prepare_test35 | Final commitment: exact all-binary elimination |
| test36 | 244 | 37816/37617 | 37616/37617 | 254.8 | 990.3 | 16/1 | prepare_test36_full | Final commitment: exact terminal-penalty elimination |
| test37 | 1554 | 322/396 | 317/392 | 0.4 | 46.4 | 17/0 | prepare_affine,prepare_test23,prepare_test37,prepare_test40,prepare_test44,prepare_test48,prepare_test88 | Final committed result |
| test38 | 206 | 5282/20346 | 3388/13037 | 26.0 | 1.9 | 14/0 | prepare_test38 | Final commitment: exact shared-DAG reformulation |
| test39 | 79 | 242736/322248 | 242736/313956 | 83.1 | 10727.5 | 14/0 | prepare_test39 | Final commitment: exact binary clique reformulation and certified row  |
| test40 | 207 | 274/498 | 154/258 | 0.5 | 25.1 | 17/1 | prepare_test40 | Final committed result |
| test41 | 123 | 11096/6064 | 10768/5456 | 7.2 | 379.1 | 23/2 | prepare_test41 | Final committed result |
| test42 | 128 | 167056/169576 | 167056/3076 | 145.9 | 7180.1 | 16/0 | prepare_test42 | Final committed reformulation |
| test43 | 85 | 33242/49565 | 26625/37573 | 14.6 | 1370.3 | 16/0 | prepare_test43 | Final commitment: exact projection of `uccase9` |
| test44 | 138 | 4161/1446 | 4161/1447 | 3.1 | 628.3 | 22/1 | prepare_test44 | Final commitment: exact reduction and binary-design strengthening |
| test45 | 104 | 1533/1848 | 693/357 | 0.6 | 27.3 | 19/0 | prepare_test45 | Final commitment: exact projection and redundancy removal |
| test46 | 472 | 159145/301 | 61036/3615 | 0.0 | 0.0 | 20/0 | prepare_test46,prepare_test46_full | Final committed result |
| test47 | 273 | 151/13 | 118/13 | 21.1 | 5.2 | 13/1 | prepare_test47 | Committed result: dominance reduction and identical-column aggregation |
| test48 | 330 | 1747/2107 | 1502/1860 | 27.2 | 8.9 | 19/0 | prepare_test48 | Final committed result |
| test49 | 119 | 2013/233 | 2013/252 | 0.7 | 301.2 | 16/0 | prepare_test49 | Final commitment: exact node-cut strengthening and one redundant-row d |
| test50 | 105 | 28926/23294 | 28926/20024 | 45.6 | 1495.5 | 14/0 | prepare_test50 | Final committed result |
| test51 | 313 | 2480/4926 | 159/289 | 5.8 | 4.7 | 19/0 | prepare_test51 | Committed result |
| test52 | 318 | 26871/53467 | 1271/2326 | 74.5 | 43.9 | 29/2 | prepare_test51,prepare_test52 | Final committed result |
| test53 | 89 | 156/161 | 156/160 | 0.3 | 4.3 | 20/2 | prepare_test53 | Final committed result |
| test54 | 203 | 48738/21732 | 32793/20252 | 20.1 | 1709.2 | 23/1 | prepare_test54 | Final commitment: exact simplification of test54 |
| test55 | 120 | 3872/3904 | 2848/2880 | 3.6 | 94.0 | 17/2 | prepare_test55 | Committed result: exact auxiliary projection with certified activation |
| test56 | 60 | 147912/17245 | 146248/16811 | 59.3 | 6205.2 | 21/2 | prepare_test56 | Committed exact reformulation |
| test57 | 103 | 114240/29904 | 97368/13032 | 80.8 | 5238.4 | 17/0 | prepare_test57 | Final commitment: exact elimination of bounded binary-sum auxiliaries |
| test58 | 267 | 2500/1750 | 607/785 | 2.0 | 0.2 | 23/1 | prepare_test58_full | Final commitment: exact optimal-value network reduction |
| test59 | 51 | 16021/1128 | 5437/3956 | 123.3 | 2693.2 | 13/0 | prepare_menu_cases | Final commitment: exact arithmetic-progression menu compression |
| test60 | 51 | 13640/717 | 2508/2016 | 117.3 | 1789.3 | 12/0 | prepare_menu_cases | Final commitment: exact option-index compression |
| test61 | 340 | 3600/5614 | 400/2070 | 116.5 | 12.2 | 17/0 | prepare_test61 | Final commitment: exact local-hull reformulation |
| test62 | 174 | 4500/7029 | 500/2539 | 87.4 | 28.6 | 17/1 | prepare_test62 | Final commitment: exact Boolean auxiliary elimination |
| test63 | 111 | 1456/111 | 1546/111 | 1.1 | 61.1 | 16/0 | prepare_test63 | Final commitment: exact sparse slack-difference reformulation |
| test64 | 177 | 23968/14646 | 6846/3175 | 17.1 | 171.9 | 18/1 | prepare_test64 | Final commitment: exact integer-equivalent reformulation |
| test65 | 233 | 154978/277594 | 154978/225040 | 87.2 | 8818.5 | 14/0 | prepare_affine | Final committed result |
| test66 | 135 | 73728/67583 | 73728/88067 | 51.9 | 2959.3 | 14/1 | prepare_test66 | Final commitment: five-cycle matching strengthening |
| test67 | 184 | 36864/33791 | 36864/33791 | 15.0 | 964.9 | 15/0 | prepare_test67 | Final commitment: exact fixing and substitution |
| test68 | 233 | 16392/3520 | 16392/3520 | 7.1 | 810.1 | 14/0 | prepare_affine | Final committed result |
| test69 | 139 | 11697/16381 | 8697/8885 | 10.4 | 246.9 | 22/1 | prepare_test69 | Final commitment: exact normalized-interval reformulation |
| test70 | 149 | 48417/2187 | 48417/2187 | 61.1 | 1921.1 | 18/0 | prepare_test70 | Final commitment: certified aggregate-gate coefficient tightening |
| test71 | 126 | 1024/1024 | 1024/1025 | 1.6 | 150.4 | 13/0 | prepare_test71 | Final committed result |
| test72 | 443 | 17264/21235 | 5528/5799 | 218.2 | 85.5 | 18/1 | prepare_test72 | Committed solver-blind reformulation |
| test73 | 108 | 10863/14038 | 10863/10551 | 6.4 | 380.8 | 19/2 | prepare_test73 | Final commitment: exact conflict-clique reformulation |
| test74 | 159 | 48950/98021 | 31482/71479 | 187.0 | 834.0 | 19/1 | prepare_test74 | Final commitment: exact binary-auxiliary projection and certified redu |
| test75 | 132 | 48950/98021 | 38001/72968 | 35.5 | 1993.3 | 21/0 | prepare_test75 | Final committed result |
| test76 | 97 | 1758/351 | 1682/301 | 0.9 | 53.0 | 18/0 | prepare_test76 | Final committed result |
| test77 | 1363 | 1536/351 | 1486/259 | 1.0 | 61.4 | 16/0 | prepare_affine,prepare_test23,prepare_test40,prepare_test48,prepare_test77,prepare_test88 | Final commitment: exact substitution and redundancy removal |
| test78 | 1714 | 3472/4633 | 2720/3881 | 100.7 | 33.6 | 22/1 | prepare_affine,prepare_test21,prepare_test23,prepare_test40,prepare_test48,prepare_test78,prepare_test88 | Final commitment: count aggregation and one-sided integrality relaxati |
| test79 | 233 | 13873/3202 | 13873/3187 | 4.8 | 672.3 | 16/1 | prepare_affine | Final commitment: exact sparse row reformulation |
| test80 | 175 | 14387/10765 | 2801/175 | 12.0 | 0.5 | 17/0 | prepare_test80 | Final commitment: exact optimal-face reformulation |
| test81 | 187 | 11090/4630 | 7749/972 | 23.0 | 935.2 | 18/2 | prepare_test81 | Final committed result: exact time-window reformulation |
| test82 | 9 | 11090/4630 | 7775/1001 | 23.0 | 930.8 | 20/2 | prepare_test82 | Final commitment: exact reduction and pairwise strengthening |
| test83 | 127 | 65832/100 | 65671/100 | 86.5 | 24046.4 | 15/0 | prepare_test83 | Committed result |
| test84 | 115 | 200/100 | 1/1 | 2.1 | 0.3 | 14/0 | prepare_test84 | Final commitment: exact singleton reformulation |
| test85 | 5 | 10404/40962 | 8560/1923 | 47.1 | 296.1 | 17/0 | prepare_test85 | Final commitment: exact binary support-block reformulation |
| test86 | 53 | 990/550 | 990/800 | 0.4 | 28.7 | 12/0 | prepare_test86 | Final commitment: 250 incoming-flow cover inequalities |
| test87 | 198 | 63009/507 | 20342/440 | 96.8 | 0.2 | 19/1 | prepare_test87 | Committed result: exact set-cover optimization reduction |
| test88 | 233 | 784/5998 | 432/2298 | 7.9 | 35.3 | 15/0 | prepare_test88 | Final commitment: exact mixed-integer alias reduction |

Two cases (`test8`, `test9`) predate `results.csv` and the per-run `session.jsonl`; their digests are built
from root-level session exports and their evidence also includes `reform_test/playground/<case>/`.

## Wire format for `api_needs` in your output JSON

`api_needs` is an array of strings, one per need, fields separated by ` || ` in this exact order:

    capability || scope || priority || why || sketch || replaces || evidence

- `capability`: an ID from the vocabulary above (or `NEW:<name>`).
- `scope`: `case_only` | `shared` | `universal`.
- `priority`: `1` (highest) .. `9`.
- `why`: <=240 chars, tied to this case's evidence.
- `sketch`: <=240 chars, the concrete API shape (Rust signature line, CLI form, or JSON fragment).
- `replaces`: <=160 chars, what it replaces (a named helper, a manual step, or `nothing`).
- `evidence`: `path:line` or a named digest/case section. Use ` / ` to separate two references.

Use ` || ` nowhere else in your JSON strings. Bounded lists: `claims`, `proof_encoding`,
`agent_manual_work`, `preparer_helpers`, `friction` at most 5 items each.

## Deliverable plumbing

Write your final JSON object **verbatim** to `/tmp/rpx-digests/out/<case>.json` (the directory
exists; `mkdir -p` if needed). That file is the aggregator's input. Your structured tool output
must be the same object, and your final chat message must be at most three lines. Do not write
anything else anywhere.
