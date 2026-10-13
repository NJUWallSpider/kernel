# Actual test44: finite design cuts and strict LP strengthening

The actual models retain all 4,161 coordinates, their domains and the objective.
The committed target removes 36 dependent balance equalities and adds 37 local
design cuts, changing 1,446 rows to 1,447. No source or target file is altered.

The RPA3/RPX proves complete integer feasible-set and objective equality through
both coordinate maps and affine inverse identities. A separate target-to-source
LP inclusion and complete 4,161-coordinate rational point prove strict LP
strengthening. One full integer point is also checked on both actual models.
Neither point is claimed optimal, and no LP objective improvement is asserted.

For each node, ordinary linear rules combine the actual capacity rows, signed
balance equalities and nonnegative-flow bounds. Local integer `Cases` examine
the incident three-option design groups. Each selected binary forces the other
two to zero using its actual packing row. A branch either proves the requested
cut from selected options and bounds or derives a positive constant contradiction
from insufficient capacity. Early successful branches need not enumerate remaining
choices. Thus the certificate uses 1,746 checked branches rather than trusting the
external enumeration report. No additional theorem or production rule is used.

```sh
python3 tools/prepare_test44.py --kernel target/validation-checkpoint-v7/release/rpx
```

The bound receipt in `preparation.json` records every command, model and witness
identity, executable and artifact hashes, and five rejected attacks. The complete
certificate passes 38,485 terminal obligations, 1,146,726 metered work units and
three full point checks. Corrupt capacity multipliers, continuous split witnesses,
false separating points, missing middle obligations and altered inverse coordinates
all return INVALID. Its first overlapping release observation was 165.112 ms of
execution and 185.271 ms internal total; these are not controlled benchmark results.
