# test68: actual invertible balance-row differences

The actual committed target replaces consecutive balance equalities by differences. Every other variable, bound, integer declaration, objective and row is checked unchanged.

For each ordered block, the forward proof derives `new[k] = old[k] - old[k-1]`. The reverse proof derives `old[k] = new[k] + old[k-1]`, reusing the previously derived local fact. This keeps the inverse proof linear in block length without expanding every prefix independently. Complete obligations cover integer and continuous feasible sets, original coordinates, objectives and both identity-map inverses.

```sh
python3 tools/prepare_test68.py --kernel target/release/rpx
```

`preparation.json` records actual current acceptance. `preparation.resource-baseline.json` preserves the initial implementation's work-budget rejection; it does not refute the model transformation. The same generated certificate passed after the sparse substitution optimization. The compact generated RPA and its deterministic generator are retained.
