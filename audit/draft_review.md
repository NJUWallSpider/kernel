# D0 draft review and corpus-driven acceptance requirements

Review date: 2026-10-11. This is an audit of the starting design, not a statement that the implementation or any corpus transformation is verified. Reviewed sources: `docs/rpx/chapters/{model,execution,instructions,format,loader,assembly,performance,revisions}.tex`; textbook `foundations.tex`, `method_index.tex`, `synthesis.tex`, and relevant case sections in `/Users/bhz/Code/reform_test/docs/nomf_textbook/chapters`. At the start of this review, `crates/core/src/lib.rs` contained only FNV-1a and a hash-vector test.

## Findings that determine implementation order

1. **No existing trusted verifier.** Neither the FNV function nor a historical Agent `verify.py` success establishes a model relation. Every accepted case needs actual source and final target models, an independently checked canonical import, complete mapped obligations, and the requested contract.
2. **D0 deliberately leaves the trusted import undefined.** Model open question O-01 and revision questions O-01/O-02 leave MCM bytes, digest coverage, and MPS dialect semantics unspecified. The task expressly includes these in the TCB. Freeze a distinct implementation version and an exact MPS-to-MCM conversion before claiming an end-to-end path.
3. **D0's contracts are too narrow for the stated corpus claims.** Feasibility equivalence and two objective-nonincreasing maps correctly prove equality of extended infima, but do not prove equality of retained coordinates, a bijection, an LP projection relation, or strict LP inclusion. The corpus inventory must state the precise relation being certified. Do not silently relabel a stronger stated contract as `opt-equivalent`.
4. **Affine mappings plus finite splits are a useful core, not a guaranteed compact representation.** Ordinary elimination, redundant rows, fixed variables, and binary conditional bounds fit it. Common-source flow decomposition, repeated switch DAGs, retained-alternative exchanges, and conditional simplex rounding put pressure on proof size or require a constructive relation theorem. These are explicit completion work, not out-of-scope examples.
5. **The D0 branch rules are sound in outline and worth preserving.** DONE is intersected, all siblings start from one parent state, dead/local facts cannot leak, and a varying map can be sealed only after every dependent obligation is done on every live branch. The implementation and adversarial tests must maintain these together.

## Exact contracts to represent

Write a contract as a conjunction of independently checked directional claims. A direction needs an input-domain mode (MILP or continuous relaxation), an output-domain mode, an objective relation NONE/EQ/LE, and any specified observable equalities. Every direction always checks all output rows and finite bounds and, in MILP mode, every output integrality obligation. Relaxation mode removes integrality only, retaining binary effective bounds.

For observable maps `P_S` and `P_T`, a forward claim additionally proves `P_T(F(x)) = P_S(x)` for every source feasible point; reverse proves its counterpart. Observables may be retained coordinates, total flow by arc, or affine counts, and must be declared by the caller's requested contract, bound to actual model IDs. Two such maps give equality of attainable observable values. With EQ objective relations they also preserve objective levels jointly with the observables. With LE they preserve optimal values at each preserved observation, subject to the requested directions.

| Corpus wording | Required checks beyond ordinary feasibility |
| --- | --- |
| Original-coordinate integer sets equal | Same-coordinate observables for every variable, both MILP directions |
| Integer projection equal | Declared retained-coordinate observables, both MILP directions |
| LP projection equal | The corresponding two relaxation directions; MILP proof alone is insufficient |
| LP no weaker | One relaxation direction from target to source preserving declared observables |
| LP strictly stronger | Inclusion plus a fully exact old-LP witness whose projection cannot belong to new LP; if target has auxiliaries, use a checked separating inequality or an infeasibility certificate for that fixed projection |
| Every reachable objective value preserved | EQ objective relation in both directions; inverse maps are not required |
| Feasibility and optimum preserved | EQ or LE objective relation in each direction; nonempty status follows from the two maps |
| Affine bijection | Above feasible maps plus verified compositions equal the identity on both feasible sets, or a checked uniquely defining eliminated-variable subsystem |
| Selected projection and optimum preserved | Selection observables in both MILP directions and EQ/LE objective relations as appropriate |

A point that violates a target row after one chosen lift refutes that lift, not necessarily target projection membership. A local fractional gadget point need not extend to the whole old model. Record the exact scope of counterexamples.

Infeasible models need both directions checked even when one closes at a contradiction. Extended infima include `+infinity` for empty feasible sets and `-infinity` for nonempty unbounded objectives. Nonincreasing maps establish equality in both cases without requiring attained optima. Model-import rejection is different from mathematical infeasibility: D0 rejects inverted finite bounds as structurally invalid; if implementation accepts them instead, define and test their empty-domain meaning explicitly.

## Trust boundary and canonical model

The trusted path comprises file reading, MPS parsing, exact decimal conversion, canonicalization, MCM decoding, RPX decoding, exact arithmetic, model binding, proof rules, state transitions, and final contract checking. RPA authors, assemblers, script-generated witnesses, solvers, textual reports, and textbook proofs are untrusted inputs. If assembly produces embedded models, the verifier still checks their bytes and requested identities.

Freeze these import decisions and reject unsupported features deterministically:

- Ordinary columns' default lower bound, absent upper bound, integer marker semantics, and binary's simultaneous integrality and `[0,1]` intersection.
- `LO`, `UP`, `FX`, `FR`, `MI`, `PL`, `BV`, `LI`, and `UI`; bound ordering and duplicate entries; conflicting bounds; unknown bound types and nonlinear/semi-continuous constructs.
- Fixed/free MPS card interpretation and continuation lines; duplicate names; repeated coefficient entries; marker placement; row types; objective-row selection; multiple N rows; unknown section names.
- Chosen RHS, range, and bounds vectors when multiple names occur. Reject ambiguity rather than merging unrelated scenarios.
- Missing RHS as zero; exact signed RANGES semantics for E/L/G rows; implicit objective constant under the chosen objective-row RHS convention.
- Default minimization; explicit objective-sense extension; sign conversion of both variable coefficients and objective constants for maximization.
- Decimal/scientific notation as exact rationals, including negative exponents and negative zero; unsupported NaN/Inf spellings; checked exponent and digit resource limits.

Canonical MCM must include every mathematical variable domain, bound, row side, coefficient, objective coefficient, and constant. Names may remain metadata but IDs must remain tied to the actual supplied files; a name-based map must be checked for injectivity and completeness. Combine duplicate terms exactly and remove zero terms before canonical ordering. Do not parse with floating point and later rationalize the approximation.

Cryptographic digests are useful provenance and binding metadata. They must never replace exact comparison for an identity fast path or a theorem precondition. If all facts and all output obligations are checked against the actual loaded models, a hash is not being used as a mathematical equality oracle. A cache may reuse an exact checked identity only while the associated model bytes/objects remain immutable and the cache identity cannot alias different contents.

## Core rules and execution invariants

D0's local rules are valid over rational coefficients and real coordinates with the stated preconditions:

- LE combinations require nonnegative multipliers on LE premises; EQ premises permit any rational multiplier.
- EQ combinations use only EQ premises. Pairing inequalities requires exact opposite expressions.
- BOX uses finite input bounds selected by each nonzero coefficient's sign.
- INT affine combinations require integral offset and multipliers on INT premises; rational EQ multiples are sound because they equal zero.
- Integer rounding uses mathematical floor/ceil, including negative fractions. It requires the same affine integer expression, including its constant, as in the bound.
- False closure requires a positive constant LE or nonzero constant EQ; no variables may remain.
- Binary splits require checked binary input domain; integer threshold/range splits require checked INT facts and complete coverage; sign splits check both overlapping branches.

Suggested invariant: for every point satisfying the input model and the current path assumptions, every visible live fact holds, all assigned output variables have their declared values, all completed obligations hold under that one joint mapping, and a closed branch has no such point.

Maintain the following state rules as one unit:

1. A fact ID is defined once, belongs to one scope, and never becomes valid again after DROP or scope exit. Ancestor facts survive child rollback; siblings never see each other's local facts.
2. Output maps are assigned once on each path. No boundless/unconstrained output variable may remain unmapped at return.
3. Every output obligation is generated by the kernel, completed once per path, and matched against a kernel-built expression. Certificate-selected subsets are insufficient.
4. All live children begin with the exact parent mapping, fact visibility, and DONE set. Their final states are merged only after sibling evaluation finishes.
5. Yield facts must have identical kind and exact expression across all live children. A fact number, a hash, or scaled equivalence is insufficient.
6. Parent DONE is the intersection over live children. A contradictory child is excluded only after a checked contradiction. All contradictory children make the parent contradictory.
7. Distinct child maps can be sealed only when every obligation depending on each differing output variable is done in each live branch, including objective and observable obligations. Subsequent substitution through a sealed variable is forbidden.
8. Sealed variables retain a *joint* branch witness. Do not treat individually established existence of each coordinate as permission to assemble incompatible coordinates. Finite branch selection in encoded order defines one output tuple.
9. Every syntactic instruction, even in a dead block, is decoded, range-checked, capability-checked, and included in logical ID allocation. Mathematical execution may be skipped in dead blocks but cannot conceal an unknown theorem/opcode or malformed terminal.

An implementation with simpler complete leaf branches can avoid sealed-state complexity initially, while acknowledging possible duplication. If adding shared mappings or lazy substitution, preserve exact dependency sets and branch identity in caches. An acyclic expression reference structure may share storage; it does not automatically share expansion work.

## Workload-driven extensions

The textbook index describes 41 teaching cases, test8–test48; it is not the full runs inventory and not independent acceptance evidence. The actual model files and final target identities must govern case status.

| Family and evidence | Generic direction | Potential compact extension and complete preconditions |
| --- | --- | --- |
| Affine elimination, aliases, complements: test9/11/15/20/22/35/40/43/45 | Complete affine maps plus linear/box/INT proofs | Shared affine DAG nodes only if cycle-free and exact; every original occurrence, bound, and objective contribution still checked |
| Redundant rows, fixed zeros, paths: test12/16/25/32/33 | Linear combinations of final retained rows and domains | Batch of independent scalar checks; test33 has 90,000 deleted rows with retained-edge paths, not paths using simultaneously deleted edges |
| Conditional bounds and one-hot strengthening: test8/10/17/19/26/34/37/39/41/42/44 | Local binary split plus linear/rounding proofs; separate relaxation inclusion direction | Fused finite choice certificate can enumerate local support only after all external dependencies are included; preserve complete leaf coverage |
| Finite interval selector projection: test13/29 | Integer-range branch or shared finite choice table | Check complete attainable values, not only min/max; `{0,2}` is not the integer interval `[0,2]`; costs and external appearances must factor through retained observables |
| Positive/negative decomposition: test23/27/30 | Sign split, `max(f,0)`/`max(-f,0)` defined jointly | Check every appearance and cost; test27 intentionally decreases old costs, including a full cycle witness, so two EQ objective directions would overclaim |
| Common-source flow aggregation: test28 | Forward affine sum; reverse deterministic path-plus-cycle decomposition | Check common directed graph, continuous nonnegative detailed flows, per-commodity balance and positive demand, no private upper bounds, all external coupling and cost through total arc flow; retain all cycles in one commodity to preserve total flows and objective |
| Recursive switches: test38 | Node equality induction with local binary branches and reverse copies | Check a topological order, terminals, every four-row switch definition, rational parameters, actual switch IDs, and every external occurrence; signatures are exact structurally checked records, not unverified hashes; LP inclusion only in the documented direction |
| Retained-alternative exchange and equal-column count: test47 | Deterministic exchanges followed by disjoint count groups | Each removed binary has K distinct retained dominators, cardinality at most K, matching costs/domains/cardinality coefficients, and domination in every permitted coverage row; no unexamined other occurrence; count groups include all column entries |
| Conditional simplex rounding: test48 | Preserve selector tuple; round each disjoint eligible child block to a minimum-cost unit vector or zero | Check binary parents, integral residual capacity in `{0,1}`, nonnegative child simplex, no cross-block child coupling, all objective contributions after exact elimination; output is one joint feasible tuple, with LE objective relation when rounding can improve cost |

No trusted theorem should accept an instance name or historical audit digest. A theorem must have a finite witness schema, a checked full-model match, exact statement, deterministic constructive semantics, complexity/resource limit, and negative tests for every omitted premise. Structural recognizers should fail closed on any extra row, bound, objective term, or shared auxiliary that violates the theorem's occurrence assumptions. Theorem results cannot discharge unrelated obligations.

The flow decomposition algorithm is deterministic witness construction, not general MILP search: residual path extraction preserves balances and decreases either the number of positive residual arcs or remaining demands; cycles are allocated without deleting them. For real input points its mathematical construction establishes a universal lifting relation; finite numeric test points alone do not establish that relation. A trusted structure theorem must justify that construction for all feasible real flows.

## Binary and resource requirements

Preserve or replace D0 wire layout explicitly; do not call a different implementation D0/v0.1. Define magic, version, byte order, field widths, header size, lengths, count units, all reserved bytes, and exact termination. Decoder code must use checked arithmetic before slicing or allocation. Validate every nested range and every section, including unused expression/scalar data. Unknown logical extensions are rejected even inside unreachable code. Optional opaque metadata cannot discharge obligations.

Canonical scalar encoding needs a positive nonzero denominator, reduced gcd, unique zero, minimal big-integer magnitudes, valid sign, and explicit size budgets. Resource results must differ from malformed proofs; arbitrarily large valid rationals can hit declared budgets but must never wrap or approximate. Check instruction counts, nesting, coefficients visited, total expanded expression work, retained facts, and big-integer bit lengths. Bound allocations before calling reserve/collect; avoid recursion under untrusted nesting unless depth is checked first.

Required final states are VERIFIED, INVALID, RESOURCE_LIMIT, and IO_ERROR, with UNSUPPORTED allowed separately. INVALID means this input/certificate violates a rule, not that the underlying reformulation is false.

## Acceptance attacks and independent evidence

Minimum semantic regressions: wrong objective constant; max objective converted without negating its constant; missing binary bound; continuous variable treated as integer; rational integer multiplier; negative floor/ceil; huge intermediate values; lost eliminated-variable bound; incomplete/duplicate mapping; omitted output row; one missing branch; sibling fact reference; use after DROP; ancestor deletion; OR instead of AND at merge; objective dependency forgotten while sealing; incompatible theorem outputs; silently discarded cycles; fewer than K retained dominators; fractional selector used to justify simplex rounding.

Minimum byte regressions: every truncation of a valid small file; unknown opcode/theorem in live and dead blocks; wrong exact payload length; trailing data; bad reserved bits; oversized count; add/multiply/alignment overflow; pool reference outside range; zero/negative/nonreduced denominator; duplicate or unsorted term; branch extending past its parent; wrong terminal context; duplicate section or overlap where sections are used. Mutations that remain legal are not presumed invalid.

Independent arithmetic and rule checks should use a separate exact oracle such as Python `fractions.Fraction`, without importing the Rust normalization implementation. Compare batch to scalar semantics including middle elements. Use deterministic seeds and report actual executions, not merely configured fuzz targets. Model/column permutations and rational rescalings should preserve applicable contracts while invalid coefficient or domain changes must fail.

Freeze initial benchmark sizes and metrics before optimizing. Include small true end-to-end cases; large identity and local edits; long sparse linear derivations; repeated shared maps; many historical/few live facts; integer/rational/bigint stress; branch and actual theorem workloads. Separately report certificate preparation, complete model import/binding/load, decoding/execution phases, actual term visits, logical expanded work, physical RPX bytes, and peak RSS. A large identity path must examine complete actual data at least once, even when later immutable caching is allowed.

## Scope of this review

The mathematical draft has a credible generic core and unusually explicit state rules. This review did not prove an implementation correct, certify any corpus pair, or establish performance. New implementation decisions should be recorded with their version, exact accepted claims, changed TCB, tests, and measured costs. Completion remains contingent on actual corpus certificates and tests, including the difficult families above.

## Version 1 implementation review follow-up

The implemented v1 codec is now specified separately in `docs/FORMAT_V1.md`. It has a 16-byte versioned header, complete model records, exact minimal sign/magnitude rationals, explicit claim records, and recursively bounded proof blocks. It deliberately does not claim byte compatibility with D0. All blocks are decoded before execution; generic affine leaf maps and complete obligations avoid D0's sealing and join-state implementation. Batch and theorem support remain absent rather than reserved acceptance paths.

The v1 contract includes independent MILP/LP domain modes, projection-coordinate equalities, objective NONE/EQ/LE, and optional affine inverse composition claims. Reusable register semantics intentionally revise D0: after DROP an ID can be redefined by a fresh checked derivation; a child can drop an inherited register in its copied state without changing its sibling. There is no post-split continuation. These changes are mathematically sound with the implemented state discipline; they must not be described as D0's never-reused SSA IDs or current-scope-only DROP.

An independent review of the new `verify.rs` found a resource-limit escape in intermediate static-row expressions: deriving a row-side fact could produce a larger rational than the configured arithmetic cap, then close a contradiction without revalidating that derived expression. This did not fabricate a false mathematical relation, but violated the published resource policy. The root implementation now validates every retrieved expression, charges each DROP element, and counts root nesting at depth one to match the codec. The `malformed_public_values_and_resource_arithmetic_cannot_accept` regression exercises the former escape through the public API and now rejects with RESOURCE_LIMIT.

Executed evidence on 2026-10-11:

- `cargo test -p kernel-core codec:: --lib`: 8 tests passed, including exact byte vectors, canonicality, every truncation of nested/model fixtures with both original and adjusted header lengths, independently constructed depth-overflow bytes, all nested types, six systematic byte substitutions per fixture byte, and 2,048 seeded random payloads.
- `cargo test -p kernel-core --test adversarial_review`: 13 tests passed. These independently construct model/proof objects and attack requested-claim binding, wrong objective offsets, both inverse compositions, binary bound/integrality omissions, continuous-to-integer assumptions, EQ-to-INT transfer, sign rules, zero-weight invalid references, every leaf's obligations, joint map consistency, sibling references/assumptions, dead/redefined registers, negative floor/ceil, empty-domain directionality, malformed public rationals, and arithmetic budgets.

No mathematical false acceptance was observed in this bounded review. These tests do not establish exhaustive coverage, formal implementation correctness, or certification of the textbook's complex theorem families.
