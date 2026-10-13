# Independent current-format review

Reviewed 2026-10-11 by the model-layer agent. This was a read-only production-source audit plus corrections to `docs/CURRENT_FORMAT.md`; no Rust source, schema, rule, version registration or test fixture was changed. File identities are in `audit/current_format_review_identity.json`.

**Conclusion:** the consolidated reference matches the implemented MCM 1 / RPX-RPA 1–8 layouts and separately describes the working, unfrozen objective-level draft 9. No codec or acceptance bug was found. This review does not freeze V9, reinterpret old bytes, or independently formalize the implementation.

## Scope checked against actual code

- `codec.rs` writer and reader, independently in both directions: 16-byte framing, four-byte record tags, one-byte option tags, exact u32/u64 widths, claim flags and objective relation, reserved bytes, counts and trailing-payload rejection.
- Canonical Q sign/minimal magnitude/zero/denominator rules; 13-byte minimum; affine term order and nonzero requirements. Stored magnitudes (1,700 bytes) are distinct from the larger exact-arithmetic intermediate bit budget (65,536 bits).
- MCM variable/row/objective fields and model validation. Codec names permit UTF-8 up to 1 MiB at preflight; accepted model names are nonempty ASCII with no control bytes and at most 1,024 bytes, independently for the model, each variable and each row. Model name uniqueness is per variable/row namespace, as documented.
- Exact Claim layout and version gates: inverse follows projection; lower-bound option begins in V3; affine observations begin in V5; draft level option follows them only in V9. Point arrays begin in V3, their refutation option in V6, bijection arrays in V7. Absent old-version fields do not consume option/count bytes.
- Separate Step, End and DerivationEnd tag spaces. All payload orders match both codec sides, including four-byte Kind, Cases' optional Ref, Plotkin's u64 labels, the FlowGroup arrays, and Signed's capacity/flow/activation order. Version discovery inspects nested Blocks, Cases, refutations and equality proofs and emits the minimum needed version.
- Actual Return obligation order in `verify.rs`: variable bounds/integrality; row equality or lower/upper; requested objective; coordinate then affine observations; inverse coordinates; opposing draft level; input lower bound; selected V7 compositions. Missing and surplus checks reject.
- Ref::Exact's narrow `check_fact` rules, including constant INT in LP mode; equality facts discharging a matching LE/INT proposition; distinction from raw instruction operand kinds.
- Point feasibility, old full-coordinate strictness, complete-fiber strictness and its fresh LP-only refutation scope; surplus/missing refutation rejection; caller-bound request arrays.
- Externally tagged serde representations, scalar strings, optional defaults, unknown-field handling, and the distinction between DerivationEnd `{"Absurd":Ref}` and End `{"Absurd":{"fact":Ref}}`.
- Parser/CLI/codec/model/proof resource layers, exact header syntax, JSON recursion classification, full request matching and auxiliary command success labels.

## Documentation corrections made

1. V7 composition order now explicitly selects pairs whose `reverse_claim` is the current direction, preserves the Request's bijection-array order, and iterates the **forward map's output** coordinates. Those are the reverse direction's original **input** coordinates, not the current Return's output vector. The old phrase “complete output-coordinate order” was ambiguous and could cause an independently written assembler to order checks incorrectly.
2. Legacy inverse contracts now explicitly require both the current and opposing Blocks to have root Returns. A Split or lift endpoint is not accepted by that contract even if all its leaves contain affine maps.
3. Exact now lists its actual contextual uses and explicitly cannot be consumed by Lin/Round/EqPair/Plotkin, a split integer operand, or Absurd. Even a zero-weight Lin operand is resolved and type checked. The existing correction permitting constant INT in LP mode was verified against the vacuous all-terms predicate.
4. Point documentation now states the exact missing/surplus policy: FiberStrictness requires a refutation; Feasible/Strictness reject one.
5. CLI success text now distinguishes relation verification (`VERIFIED`) from `CANONICALIZED`, `ASSEMBLED`, `DISASSEMBLED` and `INSPECTED`, all exit 0. Failure statuses and exit codes are unchanged.

The previously corrected 1,024-byte actual model-name limit and constant-INT LP exception were both confirmed. Other wire tables required no field/tag/width/version corrections in this pass.

## Evidence and limitations

This review compared production source and the final document directly. It did not run a new test suite, replay or performance experiment; existing executed binary vectors and receipts remain the independent runtime evidence. `audit/current_format_review_identity.json` records the exact source/document hashes read at completion so later source changes cannot silently inherit this conclusion.

The standalone consolidated document links rule-specific mathematical arguments rather than claiming its field tables prove the trusted theorems. Its explicit statement that premise checks and generated-model validation do not independently prove existential lift correctness remains accurate after the shared-helper extraction.
