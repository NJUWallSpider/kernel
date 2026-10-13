# test65: actual linear-redundancy certificate family

The actual committed model removes 52,554 inequalities from the 154,978-variable source and otherwise retains the complete model. Each deleted inequality is checked as the exact nonnegative combination

`(x - alpha*n <= 0) + alpha*(n-z <= 0) + (-y <= 0) + (B-alpha)*(-z <= 0)`.

The first two terms cite actual retained rows; the latter two cite actual lower bounds. The manifest supplies variable/row identities and coefficients as untrusted preparation hints. The RPX kernel checks all terms, complete model obligations and both identity maps. Four requested claims cover integer and continuous feasible-set equality, every original coordinate, objective equality and both inverse identities.

```sh
python3 tools/prepare_test65.py --kernel target/release/rpx
```

The compact generated RPA is large because every individual obligation is explicit. `preparation.json` records preparation cost separately from canonicalization, encoding and verification costs; single timings are not benchmark distributions.
