# test60: complete menu bijection and LP aggregate correspondence

The actual source MPS and actual final LP have passed the complete V7 contract.
The source has 13,640 variables and 717 rows; the final LP has 2,508 variables
and 2,016 rows. The LP is imported directly from its original bytes. The
independent full-field LP/MCM comparison is also in `audit/lp_parse_sweep.json`.

Four complete mapping claims preserve every model constraint, bound, required
integrality, objective and every menu activation/index observation. The integer
reverse direction uses one simultaneous optional-menu lift for all 1,254 menus:
13,550 generated binary choices and 2,508 exact sum/moment equations. All original
continuous auxiliaries are restored and their bounds and definitions checked.

The explicit bijection contract adds two responsibilities beyond projection:
every target coordinate is recovered by the forward-after-reverse composition;
and two complete source points with identical forward values must agree on every
one of their 13,640 coordinates. The injectivity proof uses ordinary local Cases,
linear combinations and equality antisymmetry. All 90 continuous auxiliary
equalities use both copied original definitions. No trusted one-hot uniqueness
rule or unverified audit assertion establishes the bijection.

The LP reverse direction uses affine endpoint interpolation. It preserves every
menu sum and moment, hence every group usage, frequency, capacity and objective
expression. A bijection between fractional option vectors is not claimed.

The full certificate has 112,210 terminal obligations, 67,750 local case splits
and 90,516,456 RPX bytes. Its first debug replay and release replay use identical
RPA/RPX/model/request bytes. `preparation.first-v7-debug.json` preserves the first
result; `preparation.json` contains the complete release result and all five
rejected mutations. The mutations omit a menu premise, duplicate a recovered
option, omit a continuous injectivity goal, misuse a continuous split variable,
or omit a full target right-inverse obligation.

Reproduce from the workspace:

```
python3 tools/audit_menus.py
python3 tools/prepare_menu_cases.py 60
python3 tools/replay_menu_cases.py 60 --kernel target/release/rpx
python3 tools/prepare_affine.py --acceptance
```

The earlier `partial.*` files and `partial_preparation.json` are retained as
partial development evidence; they alone do not establish this full contract.
