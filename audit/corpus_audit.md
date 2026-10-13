# Reformulation corpus audit

This is an artifact and proof-demand audit, not a certification report. No existing report, Python verifier result, solver claim, or model hash is treated as mathematical authority. All source runs were read only.

Observed **81 runs**, test8–test88, with **81 source/final model pairs**. Format pairs: lp->lp: 1, mps->mps: 79, mps->lp: 1.
Status at inventory generation: **81 proof not completed; 0 kernel-verified; 0 refuted by this audit**. These remain the coverage denominator. Artifact availability is not evidence that the claimed transformation is correct.
Hashed 1203 files (2,487,477,246 bytes), including source/final models, side audits, standalone scripts and hidden trajectory material. 46 cases have a persisted output verifier. No legacy verifier was executed by this tool.

The textbook method map covers test8–test48. Its historical count predates test49–test88 and is not the current corpus count. Reports are preserved as exact paragraph excerpts with source line numbers in the JSON inventory; each model and witness file has an observed SHA-256.

## Model and reproduction boundaries

- test8 is LP → LP and has an additional native artifact directory. test60 is MPS → LP. Their actual final targets must be preserved; an exact trusted LP path or checked conversion is needed.
- test8 and test9 lack persisted full execution trajectories in these run directories. Their source/final models and reports are present, and test9 also has audit data and a standalone verifier. Missing trajectory is distinguished from missing model input.
- Every acceptance target is the physically present final model named in its report. Rejected hypotheses, local witnesses and uncommitted alternatives are recorded separately. They are not counted as successful committed transformations.
- Legacy output scripts can overwrite verification files. Reproduce them only in a disposable copy of the complete run directory. A passing legacy script is still not RPX kernel certification.
- The inventory does not execute generation code extracted from trajectories. Case preparation still needs complete RPA/RPX plus the actual canonical source/target models.
- MPS parsing is part of the trusted boundary. Actual files include widened numeric fields, free-format/long names, two coefficient pairs per line, integer markers, LI bounds, empty RANGES and objective constants. Unsupported semantics must be rejected explicitly.

## First complete-model candidates

- **test40**: Smallest simple affine case: 120 complementary pairs; 274 source / 154 target variables. audit.substitutions gives y=1-x, and all changed rows are enumerated.
- **test79**: 181 row identities modulo retained equalities plus 15 duplicate pairs; audit.modifications has both equality multipliers. Same coordinates/domains/objective.
- **test68**: Consecutive equality differences with explicit prefix-sum inverse; audit.row_transformations and audit.inverse identify both directions.
- **test33**: 90,000 redundant implication rows; audit.certificates lists each retained path of length 3--7. Straight nonnegative sum certificates, useful throughput baseline.
- **test65**: 52,554 redundant inequalities; redundancy_certificates.tsv supplies two retained rows plus two nonnegative bound terms for every deletion.

These are candidates for real end-to-end certification, not certified cases. Their model pair and witness availability make them useful before implementing harder reconstruction rules.

## Hard requirements that cannot be excluded

- **test28 — Joint multi-commodity reconstruction**: Flow aggregation must distribute the complete aggregate, including cycles, to all original commodities while preserving shared capacities and every objective value. Independent existence per output coordinate is insufficient.
- **test38, test57, test59, test60 — Shared expressions and finite-domain reconstruction**: Shared DAG recursion and menu/index compression require complete incidence/domain binding and avoid expanding shared affine expressions repeatedly. test60 final target is LP.
- **test47, test48, test58, test69, test72, test78, test80, test83, test87 — Contract distinctions and non-affine normalization**: Dominance, sorting/counting, interval normalization, conditional simplex completions and optimal-face restriction do not all preserve full feasible sets or attainable objectives. Prove exactly the committed contract.
- **test66, test67, test71 — Graph and coding-theoretic structure**: Odd-cycle cuts, coloring activation and Plotkin cardinality need exact coefficient-to-graph/label binding. test71 has 1,024 labels and 523,776 distinct pair relations.
- **test84, test88 — Integrality-specific identities**: test84 uses 100 mod-2 original-row certificates to force a singleton. test88 alias equalities depend on mixed-integer product blocks, not just duplicate rows.

## Complete final-target ledger

Family letters are defined below. Every row has status **proof not completed** until actual kernel evidence supersedes it. Contract text summarizes source claims; the JSON retains the original excerpts.

| Case | Families | Actual final artifact | Claimed contract |
|---|---|---|---|
| test8 | B, D, E | `output/reformulated.lp` | 整数点相同；LP 严格强化 |
| test9 | A, B | `output/reformulated.mps` | 仿射双射；LP 投影相同 |
| test10 | A, C, D | `output/reformulated.mps` | 整数投影；LP 严格强化 |
| test11 | A, B | `output/model_reformulated.mps` | 仿射双射；LP 投影相同 |
| test12 | B | `output/reformulated.mps` | 零提升双射；LP 投影相同 |
| test13 | C | `output/reformulated.mps` | 整数与 LP 投影相同 |
| test14 | B, E | `output/reformulated.mps` | 整数对应；LP 不弱化 |
| test15 | A | `output/reformulated.mps` | 仿射双射；LP 投影相同 |
| test16 | B | `output/reformulated.mps` | 零提升双射；LP 投影相同 |
| test17 | B, E | `output/reformulated.mps` | 整数点相同；LP 不弱化 |
| test18 | A, B, C | `output/reformulated.mps` | 整数投影；LP 严格强化 |
| test19 | A, B, D | `output/reformulated.mps` | 整数投影；LP 严格强化 |
| test20 | A, B | `output/reformulated.mps` | 仿射双射；LP 投影相同 |
| test21 | A, B, H | `output/reformulated.mps` | 保可行性和最优值 |
| test22 | A, B | `output/reformulated.mps` | 整数与 LP 投影相同 |
| test23 | A, B, F | `output/reformulated.mps` | 整数与 LP 投影相同 |
| test24 | B, H | `output/reformulated.mps` | 保可行性和最优值 |
| test25 | B, C | `output/reformulated.mps` | 整数投影；未断言 LP 相同 |
| test26 | B, D | `output/model_reformulated.mps` | 整数点相同；LP 不弱化 |
| test27 | B, F, H | `output/reformulated.mps` | 保可行性和最优值 |
| test28 | B, F | `output/reformulated.mps` | 保整数决策与全部目标值 |
| test29 | B, C | `output/reformulated.mps` | 整数对应；LP 不弱化 |
| test30 | A, B, F | `output/reformulated.mps` | 整数与 LP 投影相同 |
| test31 | B, C, D | `output/reformulated.mps` | 整数投影；未断言 LP 相同 |
| test32 | B, C | `output/reformulated.mps` | 整数对应；未断言 LP 相同 |
| test33 | B | `output/model_reduced.mps` | 原坐标整数与 LP 集相同 |
| test34 | B, E | `output/reformulated.mps` | 整数点相同；LP 严格强化 |
| test35 | A, B, G | `output/reformulated.mps` | 整数与 LP 投影相同 |
| test36 | A, B, H | `output/reformulated.mps` | 保可行性和最优值 |
| test37 | B, D | `output/reformulated.mps` | 整数投影；LP 严格强化 |
| test38 | B, C, D, G | `output/model_shared_dag.mps` | 整数投影；LP 不弱化 |
| test39 | B, E | `output/reformulated.mps` | 整数点相同；LP 不弱化 |
| test40 | A | `output/reformulated.mps` | 仿射双射；LP 投影相同 |
| test41 | A, B, C, D | `output/reformulated.mps` | 整数投影；LP 不弱化 |
| test42 | B, C, D | `output/reformulated.mps` | 整数点相同；LP 严格强化 |
| test43 | A, B | `output/reformulated.mps` | 整数与 LP 投影相同 |
| test44 | B, E | `output/reformulated.mps` | 整数点相同；LP 严格强化 |
| test45 | A, B | `output/reformulated.mps` | 整数与 LP 投影相同 |
| test46 | A, B, C | `output/reformulated.mps` | 整数投影；LP 不弱化 |
| test47 | B, H | `output/reformulated.mps` | 保每个可达目标值 |
| test48 | A, B, C, H | `output/reformulated.mps` | 保选择投影与最优值 |
| test49 | B, D | `output/reformulated.mps` | Same integer points and objective; strict LP strengthening |
| test50 | B, C | `output/model_reformulated.mps` | Same feasible vectors and objective in original named variables; LP geometry unchanged |
| test51 | A, B, C, D | `output/reformulated.mps` | Objective-preserving integer projection; LP strengthened |
| test52 | A, B, C, D | `output/reformulated.mps` | Objective-preserving unique integer lifting; LP need not coincide |
| test53 | A, B, D | `output/reformulated.mps` | Same mixed-integer points and objective; strict LP strengthening |
| test54 | A, B, H | `output/reformulated.mps` | Same retained-coordinate projection and attainable objective values; not bijective on monotone auxiliaries |
| test55 | B, C, D | `output/model.mps` | Same integer projection and objective with simultaneous lift; projected LP not weaker |
| test56 | B, D, E | `output/reformulated.mps` | Integer feasible-set projection and objective preserved; see report for individual LP claims |
| test57 | A, B | `output/reformulated.mps` | Objective-preserving affine bijection; original auxiliary bounds must be implied |
| test58 | B, F, H | `output/reformulated.mps` | Feasibility and minimum objective preserved; objective-preserving final-to-original lift |
| test59 | A, C, I | `output/reformulated.mps` | Integer option correspondence and objective preservation; aggregate LP projection correspondence |
| test60 | A, C, I | `output/reformulated.lp` | Objective-preserving integer bijection; aggregate LP projection unchanged |
| test61 | B, C | `output/reformulated.mps` | Integer projection and objective preservation; local hull strengthening |
| test62 | B, C | `output/reformulated.mps` | Integer projection with complete Boolean reconstruction; see report for LP scope |
| test63 | A, B, F | `output/reformulated.mps` | Objective-preserving affine feasible-set correspondence; LP correspondence |
| test64 | A, B, C | `output/reformulated.mps` | Integer-equivalent projection and objective; LP equality not assumed |
| test65 | B | `output/model_reformulated.mps` | Same feasible sets in original coordinates, objective and LP relaxation |
| test66 | D, E | `output/model_odd5.mps` | Same integer points and objective; strict LP strengthening |
| test67 | B, C, D, E | `output/model.mps` | Same integer feasible assignments in original variables and objective |
| test68 | B, G | `output/reformulated.mps` | Same original-coordinate feasible set, objective and LP relaxation |
| test69 | A, B, D, H | `output/reformulated.mps` | Same projection onto all original binaries and every objective value; endpoint assignments not all retained |
| test70 | B, D | `output/reformulated.mps` | Same integer points and objective; valid gate strengthening |
| test71 | E, J | `output/reformulated.mps` | Same integer points and objective; strict LP strengthening; exact optimum -12 |
| test72 | B, C, E, H | `output/reformulated.mps` | Same primary binary projection and minimum completion cost; objective epigraph equivalence |
| test73 | B, E | `output/reformulated.mps` | Same integer assignments and objective; LP contained in source LP |
| test74 | B, C | `output/reformulated.mps` | Exact integer projection and objective; per-block simultaneous lifting |
| test75 | A, B, C | `output/reformulated.mps` | Exact integer projection with unique reconstruction and zero objective |
| test76 | A, B | `output/reformulated.mps` | Objective-preserving feasible-point bijection |
| test77 | A, B | `output/reformulated.mps` | Same feasible projection and objective including LP; unique reconstruction |
| test78 | B, C, H | `output/reformulated.mps` | Same minimum; source-to-target objective preservation and no-worse reverse reconstruction |
| test79 | B | `output/reformulated.mps` | Same feasible set, LP relaxation and objective in original variables |
| test80 | B, C, H | `output/reformulated.mps` | All original optimal solutions bijectively parameterized; optimum -160; suboptimal points excluded |
| test81 | B, D | `output/reformulated.mps` | Zero-extension integer bijection and objective; strict LP strengthening |
| test82 | B, C, D | `output/reformulated.mps` | Zero-extension integer projection and objective; LP contained in source LP |
| test83 | A, B, H | `output/reformulated.mps` | Same minimum and optimal recovery; not all source feasible points |
| test84 | B, K | `output/reformulated.mps` | Feasible-set singleton bijection and objective 37; LP equality not asserted |
| test85 | B, C, E | `output/reformulated.mps` | Binary feasible-set zero-extension bijection and pointwise objective |
| test86 | B, D | `output/model_strengthened.mps` | Same integer points and objective; strict LP strengthening |
| test87 | B, H | `output/reformulated.mps` | Feasibility and optimal value; non-increasing-cost source map and objective-preserving reverse lift |
| test88 | A, B, C | `output/model_reformulated.mps` | Objective-preserving integer feasible-set bijection; LP equivalence explicitly not claimed |

## Family definitions

- **A** (34 cases): affine elimination, aliases, complementary coordinates.
- **B** (73 cases): forced values, bounds, exact row implication and redundancy.
- **C** (30 cases): finite-domain, one-hot and Boolean projection.
- **D** (22 cases): conditional bounds, big-M and integer rounding.
- **E** (13 cases): one-hot aggregation, conflict cliques and packing.
- **F** (6 cases): signed differences, network flow and aggregation.
- **G** (3 cases): shared DAG, rank and repeated expression compression.
- **H** (14 cases): dominance, normalization and conditional integrality.
- **I** (2 cases): arithmetic-progression menu/index encoding.
- **J** (1 cases): combinatorial geometry/cardinality theorem.
- **K** (1 cases): modular parity and unique feasible-point certification.

Family memberships overlap. Instance coverage and family coverage must both be reported; a supported family does not certify every member automatically.

## Rebuild this inventory

Run from the kernel repository:

```sh
python3 tools/inventory_corpus.py
```

The tool deterministically hashes and reads the supplied corpus, then writes only `audit/corpus_inventory.json` and `audit/corpus_audit.md`. It intentionally does not turn previous PASS fields into verified status. Re-running it returns the inventory baseline; keep kernel certification evidence in a separate acceptance ledger until explicitly merged.
