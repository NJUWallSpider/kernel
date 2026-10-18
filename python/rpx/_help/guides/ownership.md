Coordinate identity, exact values, and scope state are explicit contracts.

## Model edits
ModelBuilder variables belong to the builder immediately and survive build. build seals the builder. Immutable Model edits return a fresh space: use `edited.vars["x"]`, not the old x in a new proof. Model.read twice also creates distinct spaces, even for identical files. Model.substitute supports explicit variable elimination; StandardMPSAdapter handles exact standard-MPS preparation.

## Arithmetic
Use Q, integer, exact string, Fraction, or finite Decimal. Float, bool, NaN and infinity are rejected at scalar entry points. `Q("1/3")` is exact; `1/3` is a Python float and is not accepted. Expr and VarRef arithmetic describes affine expressions; Fact arithmetic produces a LinCombination, requiring an explicit derivation to become a Fact. Multiplying two affine expressions is not linear algebra supported by this API.

## Scope and mapping lifecycle
A scope is editable, a fixed split/lift container, or sealed. Successful finish prevents editing. A failed derivation/lift/finish leaves no partial proof steps. split shares the coordinate space; lift extends it. Parent expressions embed in descendants; generated variables cannot escape to ancestors or siblings. Facts and goals also carry Proof identity. Dropped facts are no longer reusable.

## Stale goals
Every map call replaces the mapping and invalidates prior Goal handles. Save labels if needed, then reacquire `scope.obligations[label]` after remapping. A new mapping never silently rebinds an old Goal.

## Recover
Run `python -m rpx._help.examples.errors` and inspect `python -m rpx help troubleshooting` for executable corrections.
