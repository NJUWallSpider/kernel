# test13: complete private one-hot projection

The actual source and final MPS have passed four complete claims: integer and
continuous-relaxation correspondence in both directions, preserving all 5,677
retained original coordinates and the objective. The source has 10,399 variables
and 14,589 rows; the target has 5,677 variables and 14,571 rows. All 4,722 removed
indicators are reconstructed together, including blocks sharing a trigger.

Forward inequalities are exact nonnegative combinations of the actual one-hot
sum, moment and link rows and original nonnegativity bounds. Integer recovery
uses 18 simultaneous MenuLift witnesses with activation one and index x-L.
Ordinary local Cases then prove each distinguished indicator dominates its
original trigger. In the active trigger branch, the actual target inequalities
force x=c; if the distinguished indicator were zero, a split on the integer
sum of lower-index choices contradicts either the sum or the moment equation.
The complete source domains and all three removed rows per block are checked.

For LP recovery, the distinguished indicator is g and the endpoint masses are
`(U-x-(U-c)g)/(U-L)` and `(x-L-(c-L)g)/(U-L)`. The actual target inequalities
prove their nonnegativity. The masses sum to one and have moment x; every
original upper bound and link is checked as well. Other indicators are zero.

`preparation.json` binds the full request and actual model files to successful
kernel execution. Four mutated certificates are rejected: a missing menu bound,
an integer split premise taken from a continuous coordinate, a wrong fractional
mass, and an omitted retained-coordinate observation. Noncommitted redundancy
and alias candidates in the corpus audit remain untouched in the actual models.

Reproduce from the workspace:

```
python3 tools/prepare_test13.py --kernel target/release/rpx
python3 tools/prepare_affine.py --acceptance
```
