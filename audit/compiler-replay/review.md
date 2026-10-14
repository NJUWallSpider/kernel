# Compiler and authoring boundary review

The direct compiler preserves all frozen proof constructs: independently
encoded V1–V10 vectors round-trip byte for byte, and every shipped case delivery
recompiles to its original RPX. The bridge uses typed Certificate deserialization
and the existing encoder; malformed scalars, unknown fields, noncanonical
expressions, claim/block mismatch and parser nesting exhaustion remain rejected.
Compilation alone does not accept a mathematical proof. A deliberately false
Exact witness compiles structurally and is rejected by the independent verifier.

Return formulas and order now come from one streaming Kernel walker. Its
verification callback checks evidence immediately, preserving the original
interleaving of substitution charges, fact checks, error locations and budgets.
All Statistics fields match pre-compiler `c16fdaf` on 83 shipped pieces. Planning
metadata is never read on the acceptance path. Improvement planning shares the
actual margin helper, retains the immutable root positive predicate, rejects
ordinary-claim mismatch, and validates the positive expression against original
coordinates even when the current input scope includes extensions.

The unchecked extension API returns the exact candidate scope and explicit
parent-scope premises. Four additional adversarial Rust tests cover all five
builders. Valid parent witnesses verify after direct compilation; references to
a newly appended variable may appear in a successful structural preview, but
the verifier rejects them before entering its child scope. A false interval
premise with an Exact reference is similarly rejected. Malformed check counts,
new-coordinate expressions, unknown references, floating point capacity and
work exhaustion retain the expected failure categories. Restricted domains
preserve original prefixes and append the objective level before the halfspace.

Python `session.py` and `proof.py` were inspected for complete maps, caller-bound
requests, branch/extension scope ownership, dropped facts, integer-mode checks,
trivial completion, constructive bijections and strict improvement authoring.
Two concrete review findings were reported and repaired by the implementation
owner:

1. `Builder.lift` initially rejected trivial Exact premise references. It now
   accepts them only when `find(kind, expression)` implements the same exact
   tautology rule; nontrivial raw references still require visible Fact handles.
   This restores routine zero-balance and constant interval/menu proofs.
2. The declared Python 3.9 compatibility initially conflicted with
   `hashlib.file_digest`. `_digest` now streams SHA-256 through the supported
   standard-library API. The owner tested on the host Python 3.9 runtime.

Delivery binding was also raised during review. `verify_bundle` now checks the
recorded artifact digests, compares a supplied committed solver model with each
canonical proof target, and verifies every complete piece. Kernel acceptance
continues to rely on complete actual models and the independently supplied
Request, rather than an edit ledger, preview metadata or Python calculations.

Targeted validation completed after this review:

```text
cargo test --test compiler_bridge --test authoring_bridge
12 passed; 0 failed
```

The corpus replay and 432 MB merged test46 check are regressions of existing
proofs. They establish preserved expressiveness, byte compatibility and
verification behavior for those artifacts. They do not establish autonomous
Agent reformulation quality or end-to-end proof-authoring overhead; live Agent
experiments must supply that evidence separately.
