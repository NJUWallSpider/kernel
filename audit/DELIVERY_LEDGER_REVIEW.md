# Delivery ledger review — 2026-10-11

The submitted **78 requested certificates pass the independent file-identity and receipt audit**. This does **not** establish completion of the original 81-case goal: test62 and test83 omit explicit original-report properties, in addition to test36, test46 and test58 already recorded as incomplete. The two missing properties are disclosed in the current receipts, so this is a contract-coverage finding, not an accusation of incorrect kernel acceptance.

The acceptance ledger and all case/model/proof/request files were left unchanged. This review adds only its audit program and reports. It preserves the submitted 78-case baseline for subsequent supplementation or ledger correction.

## Findings requiring resolution

### P2 — test62 does not certify exclusion of its fractional witness

The original [report, line46](/Users/bhz/Code/reform_test/runs/test62-nomf-B1/output/report.md:46) explicitly states that a complete original LP-feasible point has retained coordinates violating seven generated unit clauses. Line70 repeats that the original data and written artifact were checked and exactly seven new rows were violated. It expressly **does not claim LP containment**, so a containment premise must not be invented to repair this gap.

The current [request](/Users/bhz/Code/kernel/cases/test62/request.json) certifies both objective-preserving integer maps, all500 retained-coordinate observations, unique reconstruction through a V7 bijection, and the full source point's LP feasibility. Its only point claim is `Feasible { target:false, integers:false, objective:null }`. That does not bind or check exclusion from the target. The [receipt](/Users/bhz/Code/kernel/cases/test62/preparation.json) explicitly records `ancillary_point_contract.certified=false` and describes the seven residual calculations as untrusted evidence.

The certified integer reformulation remains valid. Full original-contract completion additionally requires a caller-bound, complete source LP point, its complete image in the actual target coordinates, and at least one checked target bound/row violation. The seven claimed violated target rows are q529, q2026, q2137, q2306, q2368, q2534 and q2535, each with reported residual1/2. This review does not promote those preparer calculations to kernel proof.

### P2 — test83 does not certify exclusion from every original optimum

The original [report, line74](/Users/bhz/Code/reform_test/runs/test83-nomf-B1/output/report.md:74) explicitly concludes, “No optimum can select A,” from the strict-saving replacement for every one of61 removed columns. This is stronger than existence of an equally good or better canonical representative.

The current [request](/Users/bhz/Code/kernel/cases/test83/request.json) certifies a forward integer `NonIncreasing` map and reverse integer `Equal` map, with152 affine observations. These establish minimum preservation and recovery of an original optimum. They do not bind strict improvement when an original dominated coordinate is nonzero. In particular, a non-increasing relation allows equality. The [receipt](/Users/bhz/Code/kernel/cases/test83/preparation.json) acknowledges `DOCUMENTED_NON_CLAIM_NOT_CALLER_BOUND`; its negative objective coefficients and equality multipliers are ancillary evidence rather than a checked exclusion contract.

Full original-contract completion requires a caller-bound all-original-optimizer exclusion with checked positive saving and feasibility of the improvement map. It must not be replaced by a narrower “main transformation” completion criterion. The existing maps and certificates need not be discarded.

## Mechanical audit: 78/78 pass

The permanent, independent [audit program](/Users/bhz/Code/kernel/audit/delivery_ledger_review.py) imports no preparer/parser helper. Its [machine receipt](/Users/bhz/Code/kernel/audit/DELIVERY_LEDGER_REVIEW.json) records every checked file identity, actual request summary, command, result and discrepancy note.

For each of78 VERIFIED entries it checked:

- Actual original source and committed final target bytes against both immutable corpus inventory and submitted receipt/ledger identities.
- Actual `source.mcm`, `target.mcm`, `proof.rpa`, `proof.rpx` and `request.json` hashes/sizes against the receipt and ledger.
- Exact equality of the actual request with the ledger's request and of the final verification payload with the ledger's payload.
- A successful canonicalization command binding each original model to its reviewed MCM; an assembly command binding the reviewed RPA/RPX; and a final successful verification command naming the reviewed MCM/RPX/request files.
- Final exit code0, status VERIFIED, and claim/point/bijection counts matching the actual request.
- Receipt hash and recorded kernel identity agreement with the ledger. A historical binary hash is not confused with the current executable at a mutable path.

All81 ledger IDs match the inventory, status counts match, and the ledger/inventory remained unchanged during the audit. There were zero global or case-level mechanical failures. The three ledger-incomplete entries are36,46,58.

| Reviewed input | SHA-256 |
|---|---|
| Acceptance ledger | `ed0a867ab0db0081b61648247ec0fda25a24c6c81dc4204bbe6453d79ef67af0` |
| Immutable inventory | `a277cf8b47928309fcb384ff330eed63e18e839ffb6405432dcf85a8aef1591c` |
| Independent auditor | `f428aa7c41ce4ecc67445220544876f2f063b4bb501071529e57f155145fe01e` |

Five older receipts point to preparer hashes different from the current working generator: test33,65,68,79 use an earlier `prepare_affine.py`, and test71 an earlier `prepare_test71.py`. Their frozen proof and model identities all pass. This is generator provenance drift, not a failed proof; reproduction from the exact historical generator requires retaining that version. None of the23 current-wave preparers has this mismatch. This review does not infer that all generator changes were cosmetic.

The root reviewer independently performed all78 fresh original-model canonicalizations, fresh assemblies and verifies on executable SHA `694b1083e2f960aa6e9002c0ce20e796b3bcf091a3397810f30aa43f0ec9f655`. Its [separate acceptance receipt](/Users/bhz/Code/kernel/audit/validation/delivery-acceptance-2026-10-11/result.json) records PASS78, byte-identical reconstructed artifacts and matching non-timing results, with `functional_delivery_complete=false`. This audit inspected that receipt but did not rerun those78 jobs.

## Original-contract scope check

All78 request summaries were compared with the frozen inventory's original-contract summaries. The23 current-wave original reports received a direct scope review; the [contract machine report](/Users/bhz/Code/kernel/audit/DELIVERY_CONTRACT_REVIEW.json) binds each report and actual request by hash. No additional contract gap was identified in those23 beyond62/83. This is not a new derivation of every original-report ancillary observation or every proof obligation for the other55 cases. For example, test38's inventory shorthand mentions LP non-weakening, whereas its actual report promises integer projection/unique reconstruction and only a **local** fractional strengthening example; no full LP claim is inferred from that shorthand.

| Cases | Original scope compared with actual caller request |
|---|---|
| 8,66,86 | Original-coordinate integer bijection/objective; LP inclusion plus a complete strictness point. |
| 24 | Minimum-preserving maps with100 retained observations; no all-source-point bijection promised. |
| 29,56,85 | Integer zero-extension bijection; LP inclusion, without invented strictness. |
| 31 | Integer retained projection and objective; nonunique eliminated auxiliaries allowed. |
| 41,51,52 | Integer affine bijection and LP inclusion, including the actual objective constants. |
| 45 | Integer and LP retained projection and objective; nonunique completions allowed. |
| 55 | Integer projection/objective and reverse LP inclusion. |
| 61 | Integer unique reconstruction bound by a V7 bijection; reverse LP inclusion. Local witnesses are not claimed as global strictness. |
| 62 | Integer bijection and source LP point certified; target exclusion missing. |
| 64 | Integer affine bijection; no LP equivalence promised. |
| 67 | Integer identity bijection and exact optimum4 through a bound and full attainment point. |
| 72 | All2608 primary observations with objective-preserving forward and non-increasing reverse MI maps establish per-primary minimum-completion/epigraph equivalence. No auxiliary bijection promised. |
| 73 | Integer identity bijection and LP inclusion; the report's fractional example is local. |
| 74 | Integer retained projection/objective with simultaneous private-auxiliary lifting; no LP equality promised. |
| 81 | Integer zero-extension bijection, explicit removed-coordinate observations, LP inclusion and full FiberStrictness. |
| 82 | Integer zero-extension bijection and LP inclusion; no full strictness promised. |
| 83 | Minimum and original optimal recovery certified; all-original-optimizer exclusion missing. |

Test72 and test74's final default-limit verification runs are recorded. Test72 consumed156,483,074 work units and also passed an explicit180,000,000-work run; its final run uses the actual current default1,000,000,000. Test74 consumed37,545,628. No silently missing command-line override is needed to explain their final VERIFIED status.

## Review-wave evidence and P3 amendments

[WAVE_REVIEW_2026-10-11.md](/Users/bhz/Code/kernel/audit/WAVE_REVIEW_2026-10-11.md) reviews **21**, not23, cases. Its scope expressly excludes72/74. It acknowledges62/83's excluded properties. Consequently its “zero P1/P2” result for the submitted certificate requests cannot establish full original-goal completion.

This audit independently checked all21 RPX hashes in its table against current artifacts and executed its four self-contained exact original-MPS linear spot checks for41/51/86/83; all four passed. [Execution evidence](/Users/bhz/Code/kernel/audit/DELIVERY_WAVE_SPOT_REVIEW.json) preserves the code hash and complete stdout. The temporary validator's current SHA matches the report, as do its inventory and requirements identities. Its source was inspected: it checks bookkeeping but does not determine original-report completeness. The permanent auditor above additionally checks exact ledger payloads and command-path binding.

The report's historical executable SHA `4acaf2484f7444975bdcc792d7a9a8ff6532f8848ab7070150ceabb4f2d6ae8d` differs from the current release hash. This is a historical-versus-current identity distinction, not evidence of an erroneous replay; the root's new receipt explicitly binds the current executable. The report attributes72 mutation replays and42 positive replays to reviewer terminal reports and says temporary directories were removed. It does not link a persistent raw machine record containing those entire runs. This audit did not independently reproduce those72 attacks and does not relabel the narrative as a retained full transcript.

The four P3 amendments are **metadata labels, not literally source comments**:

- [test45 generator](/Users/bhz/Code/kernel/tools/prepare_test45.py:103): mutation-reason text now describes loss of reconstructed-slack nonnegativity, rather than a reverse capacity implication.
- [test64 generator](/Users/bhz/Code/kernel/tools/prepare_test64.py:176): reason text names the last saturation endpoint upper-bound premise, rather than an alias equality.
- [test73 generator](/Users/bhz/Code/kernel/tools/prepare_test73.py:105): reason text names the deleted bound-redundant row restoration, rather than edge restoration.
- [test29 shared generator](/Users/bhz/Code/kernel/tools/prepare_test29.py:116), imported by85: count keys are `reciprocal_blocks`/`omitted_blocks`, correctly distinguishing paired blocks from directional classes.

The current labels and code locations support that characterization. However, no persistent before/after artifact manifest or prior-version generator diff was available to this audit, and the root confirmed it has no additional such evidence. Current receipts and current hash tables alone cannot independently prove that all five artifacts and all negative hashes/results were unchanged by those amendments. The wave report's byte-identity statement remains an attributed owner confirmation. This is a reproducibility-evidence limitation; no proof-mathematics change was established by this review.

## Reproduction and disposition

Run `python3 audit/delivery_ledger_review.py` from the repository to regenerate only the mechanical JSON; it does not change the ledger or certificate files. Contract findings and the independently executed four spot checks are preserved separately so a bookkeeping rerun cannot erase them.

Accept the78 submitted requested-contract identities and successful fresh replays as evidence. Do not mark the original goal complete or treat62/83's disclosed non-claims as full-case completion. Supplement the missing properties, preserve the old artifacts and receipts, and then update the ledger under the root reviewer's control.
