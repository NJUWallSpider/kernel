# Joint integer menu construction

The menu extension remains in RPX 11. Complete-domain bijection and injectivity certification have been removed. See [FORMAT](FORMAT.md#constructive-witness-payloads).

## Menu extension

`menu::prepare_unchecked_extension(input, menus, limits)` returns an
`UncheckedMenuExtension { model, premises, statistics }`. Each MenuWitness has
`maximum_index: u32`, `activation: Expr`, `index: Expr` and exactly six references.
The corresponding MenuPremise records carry `kind`, `expression` and `reference`,
in menu order, then this order:

1. LE(-A)
2. LE(A-1)
3. INT(A)
4. LE(-I)
5. LE(I-K*A)
6. INT(I)

Every expression is validated against the *old* input dimension. The proof engine
must use actual model integrality and prove every premise in the old live/path
scope before exposing the candidate model. The helper intentionally can return a
false premise or invalid Ref: preparation does not establish those premises.
Its premise formulas and generated model nevertheless belong to the trusted
inference implementation; checking the premises does not independently prove
the joint-existence lemma. In particular A=2,I=1
can admit two selected options in the candidate model; only the required A<=1
premise makes using that extension sound.

The input model's name, variable/row prefixes, domains and complete objective are
preserved. For each menu append K+1 integer variables with exact bounds [0,1],
in index order, then two equality rows in this order:

```
sum(j=0..K) z[j] - A = 0
sum(j=0..K) j*z[j] - I = 0.
```

Both bounds on each row are zero. Constants are retained in the expression as
-A.constant and -I.constant. A singleton K=0 still has both rows; its second row
is -I=0, with no coefficient for z[0]. Generated names avoid all original names;
their spelling has no proof significance. All menus extend the same original
point simultaneously. An empty family returns the original model unchanged.

At a point satisfying the premises, A is 0 or 1. If A=0, I=0 and all z are zero.
If A=1, the integer I is in [0,K], and z[I]=1 with all other z zero. This proves
total simultaneous existence over arbitrary real old coordinates. Binary domain
and the two equations also make this menu vector unique. That local uniqueness
does not independently establish any inverse of the complete actual model map.
Every actual output domain, row and nonincreasing-objective obligation still belongs
to the ordinary proof engine.

The helper preflights sum(K+1), row/reference counts, model dimensions and combined
old/generated/premise support with checked arithmetic. It charges copying and
expression work before reserving expanded buffers, uses fallible reservations,
checks all rational intermediates (including K*A before subtraction), and validates
the final model. Premise and link differences use sorted sparse merging, not
repeated whole-expression accumulation. `MenuStatistics` records `work`,
`generated_variables`, `generated_rows` and `generated_terms`; terms count actual
new row terms after zero-coefficient removal. These are logical counters, not
measured physical allocation sizes or a wall-clock guarantee.
