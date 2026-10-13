# test33: actual transitive implication-row deletion

The committed artifact deletes 90,000 inequalities and retains all source variables, domains, objective and other constraints. For each deleted row, the audit supplies a path of 3–7 retained inequalities. Summing those actual inequalities reconstructs the complete deleted row exactly. The certificate checks every path and all remaining model obligations; no graph search or external verifier result is trusted by the kernel.

Four claims cover both directions over integer and continuous domains, pointwise objective equality, all original coordinates and both identity-map inverses.

```sh
python3 tools/prepare_test33.py --kernel target/release/rpx
```

`preparation.json` records actual current acceptance. `preparation.resource-baseline.json` preserves the initial work-budget rejection, before sparse substitution was optimized. That rejection was a verifier resource outcome and did not establish that the model relation was false. The same actual certificate subsequently passed.
