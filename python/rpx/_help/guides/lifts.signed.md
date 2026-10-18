Use the explicit SignedSpec contract for a signed construction.

## Premises and results
Read `python -m rpx help SignedSpec` for named fields and witness ordering, and `python -m rpx help Generated` for family-specific result fields. For flow/subflow also inspect the corresponding Group type. Every supplied Fact must be visible in the parent and belong to this Proof. None requests a literal Exact witness only. Generated variables belong to the extended child; unavailable fields raise AttributeError.

## Lifecycle
A successful lift fixes the parent and returns a LiftResult with .scope. Complete mappings and proofs in this child. Parent expressions remain usable there; child variables cannot escape back to parents or sibling extensions. Invalid premises fail before installation.

## Run the example
`python -m rpx._help.examples.lifts signed` builds all required models in memory, supplies ordered witnesses, inspects generated fields, finishes both directions and requires a fresh VERIFIED Kernel result. To read it offline:

```python
from importlib.resources import files
print(files("rpx._help.examples").joinpath("lifts.py").read_text())
```
