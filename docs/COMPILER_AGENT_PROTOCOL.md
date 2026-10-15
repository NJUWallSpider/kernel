Compiler proof tools and delivery (supplement to the shared analysis protocol)

The supplied `kernel_compiler` Python package and RPX kernel are available. Import them in the persistent Python environment; read `compiler/API.md` as needed for the public API. They perform exact model bookkeeping, proof elaboration and verification. You supply the reformulation, maps and nontrivial mathematical witnesses. No additional environment setup is needed.

Keep the mathematical objective and autonomous exploration in the shared protocol. Choose the strongest justified reformulation; express its proof using the available builders and explicit witnesses. A difficult certificate is a reason to report a concrete compiler limitation, not to weaken the target or its required correctness relation. If certification fails, preserve the intended target and failing call and state what remains unproved.

`Model.load("input/model.mps")` uses the Kernel's exact reader. Use bounded structural inspection to understand the model and establish the representation needed for your reasoning. Build the target and proof in the same persistent session. A standalone authoring script is optional: the evaluation retains your actual Python calls. Keep useful witness/edit data as part of the ordinary analysis audit.

Declare the actual relation in your Request: integer or continuous domains, objective comparison, observations, restrictions, and inverse identities when intended. Each directional map covers every output coordinate and all its feasibility obligations. Use the contract matching your mathematical argument; acceptance of a restricted or one-direction claim does not establish a broader relation.

For the completed proof, write a separate final standard LP/MPS under `output/` and invoke the Kernel yourself:

```python
target.write_mps("output/reformulated.mps")
receipt = proof.verify("output", committed_model="output/reformulated.mps")
```

The API saves the canonical source/target, RPX, Request, certificate input, delivery manifest and verification receipt. Successful delivery requires `receipt["status"] == "VERIFIED"` and `receipt["artifact_audit"]["status"] == "MATCHED"`. The latter checks every named variable, bound, integrality declaration, row and objective against the committed artifact. Keep the generated artifact paths unchanged. For successive stages, use `write_chain` with explicit `claim_paths`, then `verify_bundle`; see the API example. Only the checked composed paths establish the final relation.

Use the successful receipt as evidence for the submitted theorem and serialization audit. `receipt["request_summary"]` describes a single Proof's scope; `proof.contract_summary()` previews it during authoring. For a chain, use `composition` and its stage `parts`. Link these records instead of recounting all obligations or observations. A second parser, repeated proof replay or another full serialization audit is needed only for a concrete mismatch or a claim outside the verified Request.

Complete the shared protocol's report concisely in `output/report.md`: explain the mathematical argument, final scope, important findings and limitations, and link the existing witness/edit audit and verified artifacts. Once the investigation is complete and the intended final proof and artifact are verified, summarize the recorded results and finish. Further exploration is appropriate when it can improve the reformulation; rebuilding already accepted evidence or converting the session into a separate program is not an additional delivery requirement.
