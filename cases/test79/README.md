# test79: actual sparse row rewriting

The certificate binds the original corpus source and actual committed target identified in `preparation.json`. It checks equality of feasible sets in every original coordinate, with pointwise objective preservation, in both integer and continuous domains. Identity maps also have their inverse identities checked.

Exactly 181 inequalities are rewritten with signed combinations of retained balance and degree equalities; the reverse direction uses the opposite multipliers. Exactly 15 deleted duplicate rows are recovered from their retained counterparts. The complete remaining models, including all variable bounds and integer declarations, are obligations of the kernel.

```sh
python3 tools/prepare_test79.py --kernel target/release/rpx
```

The shared untrusted preparation tool independently parses exact rational MPS data and checks every proposed row identity before emitting `proof.rpa`. This preparation is not accepted as proof authority: Rust canonicalization, actual RPX assembly and the complete verifier path still run. `preparation.json` retains commands, hashes, counts and observed results. The larger generated RPA is compact JSON; its deterministic generator is the reviewable source for the repeated structure.
