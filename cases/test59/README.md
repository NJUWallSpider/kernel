# test59: complete menu bijection and LP aggregate correspondence

The actual source and final MPS have passed the complete V7 contract.
The source has 16,021 variables and 1,128 rows; its final MPS has 5,437 variables
and 3,956 rows. `menu_structure.json` binds both original files by SHA-256 and
records every menu, packing group, resource definition and final row index.

`tools/audit_menus.py` independently reconstructs every actual target domain,
row and objective coefficient using Python Fraction. It covers all 15,806 source
binary options, 2,738 menus, 913 packing groups and 215 continuous definitions.
There are 39 singleton menus; these omit the index variable. The audit checks
3,398,290 complete resource and objective coefficient identities, including zero
coefficients and every option. No original option is discarded.

The verified contract is an objective-preserving **integer bijection**, together
with equal LP image in group usage, frequency, capacity and objective coordinates.
Each target menu has activation A and, when non-singleton, integer index I with
0 <= I <= K*A. One simultaneous MenuLift supplies all 15,806 binary choices and
5,476 exact sum/moment equations, including all-zero inactive choices and the 39
singleton menus. The complete original model, all auxiliary bounds and all
objective coefficients are checked after the lift.

The explicit bijection also checks every target coordinate under the composed
maps, and a separate proof checks that two complete source points with equal
forward values agree on all 16,021 original coordinates. Its ordinary local
Cases proof includes all 215 continuous auxiliaries through both original
definitions; no unchecked audit assertion establishes uniqueness.

For the LP reverse map, the explicit endpoint weights x[0]=A-I/K and x[K]=I/K
preserve all aggregate expressions. Singleton menus use x[0]=A. This is an affine
section of the aggregation map, not an LP feasible-point bijection.

The certificate has 160,289 terminal obligations, 78,835 local case splits and
91,698,522 RPX bytes. `preparation.json` binds the original files, canonical
models, complete request, RPA and RPX to the successful release replay. All five
mutations are rejected: a missing menu premise, a duplicated recovered option,
a missing continuous injectivity goal, a continuous variable used as an integer
split, and a missing target right-inverse goal.

Reproduce from the workspace:

```
python3 tools/audit_menus.py
python3 tools/prepare_menu_cases.py 59
python3 tools/replay_menu_cases.py 59 --kernel target/release/rpx
python3 tools/prepare_affine.py --acceptance
```

The earlier `partial.*` files remain development evidence; they alone do not
establish the complete integer bijection.
