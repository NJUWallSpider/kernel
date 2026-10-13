# test88: mixed-integer alias reduction with local case proofs

The certificate binds the actual 784-variable, 5,998-row source to its actual committed 432-variable, 2,298-row target. It proves the reported objective-preserving bijection of mixed-integer feasible sets, identity on every retained coordinate, and both inverse identities. It does not assert equivalence of the continuous relaxations.

The 96 affine aliases follow by subtracting original defining equalities. The remaining 256 product aliases use RPA/RPX version 2 local cases, with no product theorem:

1. Split on each involved original binary variable using its checked integer declaration.
2. Combine the branch assumption with the opposite binary bound to obtain its exact fixed-value equality.
3. When both bits of one signed pair are one, its original magnitude definition and upper bound yield an exact contradiction.
4. When a factor is zero, two actual magnitude inequalities force each product copy to zero, so later pairs need no split.
5. Otherwise, the original signed-factor definitions, actual interval inequalities and variable bounds force both product copies to the same value. Two opposite inequalities yield their alias equality.

Each product alias uses 21 binary case nodes and 22 leaves. Branch-local facts remain local; only the common checked alias equality is exported. The final forward proof substitutes these equalities into every target row. The reverse proof copies retained representatives and checks every source row, including all deleted duplicate rows. All bounds, integer conditions, objective terms, projections and inverse equations are kernel obligations.

```sh
python3 tools/prepare_test88.py --kernel target/release/rpx
python3 tools/prepare_affine.py --acceptance
```

`proof.rpa`, `proof.rpx`, both canonical models, the exact requested contract and full execution receipt are retained. `preparation.json` records the binary used; the first successful run used a debug build, so its timing is not a release benchmark. The two negative files test a continuous variable cited as an integer split witness and a Cases conclusion inconsistent with its children. Both must return `INVALID`.
