# test69: simultaneous interval normalization with complete binary projection

The actual source and final MPS have passed three complete mapping claims. Both
integer directions preserve all 7,196 original binary coordinates, the retained
`xx0` coordinate, and every attainable objective value. The reverse expansion
also maps every feasible target LP point to a feasible source LP point with the
same objective. Continuous endpoint assignments are normalized, so a continuous
bijection and global strict LP strengthening are not claimed.

The forward certificate uses one simultaneous IntervalLift for 1,500 intervals.
For original lower/upper endpoints l,u, anchor a and length L, it introduces t
with lower bounds 0 and l-a+L and upper bounds L and u-a. All four compatibility
obligations are checked against the actual containment/length rows or exact
constant inequalities. Thus every lifted point has endpoints a+t-L and a+t
inside the original interval. Each target row is derived using those endpoint
improvement bounds and exact anchor-component equalities from original pairs of
opposite inequalities. Cancellation of both origins is checked in each complete
row expression, rather than assumed from a translation-invariance audit.

Each of the 6,446 tightened gates is proved by a local split on its original
binary variable. The inactive branch uses the new interval bounds; the active
branch uses the original normalized row. The reverse affine expansion checks
every original coordinate bound, integer flag, removed row, retained row and
objective. Tightened rows imply their original counterparts using b<=1, which
also justifies the continuous reverse claim.

The certificate contains 141,812 terminal mapping obligations. Exact artifact
identities, kernel statistics and all executions are in `preparation.json`.
Four mutations are rejected: an omitted interval compatibility check, a
continuous variable used as an integer gate premise, a wrong endpoint expansion,
and an omitted original-coordinate observation.

Reproduce from the workspace:

```
python3 tools/prepare_test69.py --kernel target/release/rpx
python3 tools/prepare_affine.py --acceptance
```

All original corpus files are read-only inputs to preparation. The audit supplies
untrusted names and candidate formulas; complete actual model obligations remain
the kernel's acceptance criterion.
