# Boxed Cases payload: independent V6 merge review

The measured V3 prototype from `tools/prepare_boxed_cases_experiment.py` was reviewed and its internal representation change applied to the frozen V6 implementation. Production changes are limited to `proof.rs`, `codec.rs`, and `verify.rs`, plus Rust test constructors/patterns. Ordinary branch scopes still copy their live-fact maps. The separate shared-scope prototype has not been merged by this change.

`Step::Cases` now holds `Box<CasesStep>`. The payload has exactly the old fields and types. `CasesStep` retains strict unknown-field rejection, while serde's externally tagged newtype representation retains the same `{"Cases":{...}}` JSON. Codec field order, tags, version requirements, child-depth traversal and expression/ref validation are unchanged. The verifier destructures borrowed fields from the box and runs the same premise/child/conclusion checks. Mutable test patterns borrow the same fields. No facts, mappings, branches, limits or mathematical work charges have been removed.

The extra small allocation for each Cases payload is subject to Rust's standard Box allocator behavior, as were the existing boxed child derivations. The documented residual inability to recover from every allocator/OS failure still applies. The file/depth/count bounds remain enforced. This adds no unsafe code and creates no new inference rule or binary version.

The actual rebuilt V6 `Step` occupies 96 bytes on the current host, down from the baseline 208; the indirect CasesStep payload occupies 208 bytes. Sparse Cases-heavy workloads therefore pay the payload allocation only for that variant, while ordinary Lin/Drop/etc. slots become smaller. Performance conclusions are supported by the parent's isolated prototype evidence in `bench/boxed-cases-experiment.json`, not by type size alone.

Validation executed after the merge:

- All 147 core tests passed, including state/resource attacks and independent V1–V6 binary vectors.
- All 11 current real RPA files, including the original RESOURCE_LIMIT test18 candidate, were reassembled with the rebuilt V6 CLI. Every output matched the existing RPX byte-for-byte and by SHA-256. This checks the textual Cases schema as well as binary layout on actual nested proofs, rather than relying only on decoding existing bytes.
- Before/after hashes of the six changed Rust files and measured host layout are in `audit/boxed_cases_v6_merge.json`; per-case compatibility receipts are in `audit/boxed_cases_v6_compatibility.json`.

No mathematical or wire-compatibility issue was found. This merge does not by itself certify test18 or remove the existing branch-copy work limit.
