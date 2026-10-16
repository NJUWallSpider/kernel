# Compiler author protocol

RPX certifies only optimization equivalence of complete MILPs. Develop a useful reformulation, commit its exact target model, and provide one complete RPX 11 certificate. The kernel's goal cannot be selected or weakened by the author.

Use `Proof(source, target)`, then author `proof.forward` and `proof.reverse`. Each direction must map every feasible input to a feasible output with a nonincreasing objective. Include every bound, row, integer declaration and objective constant. Supply explicit nontrivial derivations; planning and completion are mechanical authoring aids, not proof search.

Maps may be affine, piecewise, or use Interval, Menu, Signed, Flow and Subflow scopes. A reverse recovery map need not invert the forward map. There are no additional property declarations, LP modes, point proofs, inverse identities or standalone improvement witnesses.

Write the final target as a supported LP/MPS artifact and call:

```python
result = proof.verify("output/proof", committed_model="output/reformulated.mps")
```

Require `status == "VERIFIED"` and `artifact_audit.status == "MATCHED"`. Keep the generated model/proof files, delivery manifest and verification receipt together. A single model pair has one complete certificate. For successive stages, `write_chain` and `verify_bundle` verify every complete stage plus exact named joins and endpoint binding.

If certification fails, retain the intended target and failing proof/call and report the concrete unproved obligation. Do not substitute a weaker property, drop model fields or treat a resource limit as success. See the [current API](COMPILER_API.md).
