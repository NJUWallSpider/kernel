# test40: actual complementary-binary elimination

The certificate relates the original corpus `input/model.mps` to its actual committed `output/reformulated.mps`. Their full paths and observed SHA-256 identities are in `preparation.json`; the corpus is never modified.

For each of 120 disjoint original equations `x+y=1`, the target retains `x` and removes `y`. The forward map retains every target coordinate. The reverse map reconstructs each removed coordinate as `1-x`. Every changed target inequality is an exact combination of its original inequality and the defining equality. All removed-variable bounds and integer conditions, all original and target rows, both objectives, every retained coordinate, and both affine inverse identities are checked.

The four requested claims cover both directions over the mixed-integer feasible sets and both directions over their continuous relaxations. They establish the claimed affine bijections and pointwise objective preservation. No feasibility or boundedness assumption is used.

Reproduce from the kernel repository after building `rpx`:

```sh
python3 tools/prepare_test40.py --kernel target/release/rpx
```

`proof.rpa` is complete reviewable RPA source; `proof.rpx` is its executable encoding. `source.mcm` and `target.mcm` come from the Rust trusted canonicalizer. `request.json` is the independently supplied required contract. `coordinate_index.json` names every coordinate and row. `preparation.json` records actual execution results, identity hashes, sizes and commands. It also records two required-rejection cases: a wrong complement constant and a missing inverse obligation. Single recorded timings are execution evidence, not benchmark distributions.
