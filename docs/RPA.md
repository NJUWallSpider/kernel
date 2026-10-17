# RPA 12 line assembly

RPA 12 is the text assembly for an RPX 11 certificate. One logical instruction maps to exactly one wire `Step`, `End`, or `DerivationEnd`. The parser lowers the text directly to `Certificate`; the kernel still consumes only binary RPX, and only verification against the two actual complete models can establish optimization equivalence.

```text
RPA 12 text -> Certificate -> codec::encode_certificate -> RPX 11
```

RPA 12 replaces the former `RPA 11` JSON serialization and `RPA-S 1` source language. Both old text headers are rejected. Certificate JSON is not a production proof path.

## File structure

The first line is exactly `RPA 12`. The two proof directions follow in this order:

```text
RPA 12
.forward
  ...steps...
  ...one terminal...
.reverse
  ...steps...
  ...one terminal...
```

The reverse direction follows `.reverse`. A block contains zero or more steps and exactly one terminal. `.forward`/`.reverse`, block closers, branch headers, lift payload lines, comments and blank lines are not wire instructions.

## Lexical rules

- Comments begin with `;` and run to the end of the physical line.
- Blank lines are ignored. LF and CRLF line endings are accepted; a trailing newline is optional.
- A logical instruction starts on a nonempty line. It continues over following physical lines until parentheses are balanced. Indentation is insignificant.
- Parentheses group affine expressions and instruction lists. They do not create wire nodes or reorder evaluation.
- Rationals are exact integers or `p/q`; decimals and exponents are rejected. The denominator must be nonzero.
- ASCII is used for syntax. Comments may contain arbitrary UTF-8.

Canonical disassembly uses two-space indentation, one logical instruction per line, no comments, and a blank line before `.reverse`.

## Operands

| Form | Meaning |
| --- | --- |
| `fN` | Local fact/register `N` |
| `vN.lo`, `vN.hi`, `vN.int` | Variable lower bound, upper bound, actual integrality |
| `rN.lo`, `rN.hi`, `rN.eq` | Row lower side, upper side, equality |
| `aN` | Active branch assumption `N` |
| `exact` | Exact terminal tautology |
| `xN` | Output/input coordinate `N` |

`lin` accepts only facts and rational constants. Coordinates are illegal there. An affine expression `expr` accepts coordinates, rational constants and parentheses. Multiplication is only `rational * factor`; write `1/7*x0`, not `x0/7`, and expand coordinate products explicitly.

A leading `+` or `-` applies to the first term; later signs are binary separators. Thus `1 - 2*x0` is valid while `1 + -2*x0` is not.

`lin` stores terms in textual order, including repeated facts and zero multipliers. Constant terms are summed into the wire constant. Affine expressions are canonicalized (sorted coordinates, no zero coefficients).

Empty lists are `()`. Empty `drop` is the single word `drop`.

## Steps

| RPA 12 | Wire `Step` |
| --- | --- |
| `lin.le fN, linear` | `Lin` with kind `Le` |
| `lin.eq fN, linear` | `Lin` with kind `Eq` |
| `lin.int fN, linear` | `Lin` with kind `Int` |
| `round fN, le, int` | `Round` |
| `drop [fN, ...]` | `Drop` (empty vector allowed) |
| `eqpair fN, positive, negative` | `EqPair` |
| `cases.le fN, expr, split expr [, int ref]` | `Cases` with kind `Le` |
| `cases.eq fN, expr, split expr [, int ref]` | `Cases` with kind `Eq` |
| `cases.int fN, expr, split expr [, int ref]` | `Cases` with kind `Int` |
| `plotkin fN, bits=N, dist=N, vars=(xN:label,...), cliques=(...)` | `Plotkin` |

`cases.*` is followed by two derivations:

```text
  cases.le f0, x0, split x1
  left a0
    ...derivation steps...
    wit f0
  right a0
    ...derivation steps...
    absurd exact
  end
```

A derivation ends in `wit ref` or `absurd ref`; `wit` is illegal in a full block. `a0` is the absolute assumption index for the current branch scope. Nested branches increment it, and the same index is used by both siblings of one split.

`plotkin` carries `bits`, `distance`, `(coordinate,label)` pairs and checked clique references exactly once; the kernel checks the actual binary domains, labels and clique premises.

## Terminals

| RPA 12 | Wire `End` |
| --- | --- |
| `ret (map expressions) (checks)` | `Return` |
| `split expr [, int ref]` | `Split` |
| `absurd ref` | `Absurd` |
| `interval ... body ... end` | `IntervalLift` |
| `menu ... body ... end` | `MenuLift` |
| `signed ... body ... end` | `SignedLift` |
| `flow ... body ... end` | `FlowLift` |
| `subflow ... body ... end` | `SubflowLift` |

### Return

```text
  ret (x0) (
    v0.lo,   ; output lower bound
    v0.hi,   ; output upper bound
    r0.hi,   ; output row side
    exact,   ; objective nonincreasing
  )
```

The first list is the complete output map. The second list is positional and must contain exactly one reference for each kernel-generated obligation, in kernel order: each output variable's finite lower bound, finite upper bound, then actual integrality; each output row's equal side or finite lower then upper side; finally the objective nonincreasing inequality. The assembler does not know the models, does not validate check counts, and has no named checks or model binding. The kernel remains the only obligation authority.

### Split

```text
  split x0
  left a0
    ret (-x0) (a0, v0.lo, exact)
  right a0
    ret (x0) (a0, v0.hi, exact)
  end
```

Both branches are full blocks and must independently close all output obligations. `aN` names the branch assumption; the parser rejects an index that does not match the current absolute branch depth.

### Lifts

Lift payload lines describe the witness; they are not wire instructions. The `body` block executes in the same assumption scope but with the lifted input/extension model.

```text
  interval
    lower (x0) upper (x1) checks (f0)
    body
      ret (x0) (exact)
    end

  menu
    K=3 act=(x0) idx=(x1) checks=(f0, f1)
    body
      ret (x0) (exact)
    end

  signed
    C=1/2 flow=(x0) act=(x1) checks=(f0, f1)
    body
      ret (x0) (exact)
    end
```

Flow and subflow payloads contain the graph and groups before `body`:

```text
  flow nodes=2
    arc 0, 1
    group source=0 commodities=(0:1/2) flows=(x0) nonneg=(f0) balance=(f1)
    body
      ret (x0) (exact)
    end
```

All `arc` lines precede all `group` lines, matching the wire's two vectors. `subflow` uses `demands=` in place of `commodities=`. Empty interval/menu/signed witness vectors are allowed; flow/subflow always carry exactly one witness.

## Canonical disassembly

`disassemble` is deterministic:

- header, `.forward`, two-space indentation, one blank line before `.reverse`, trailing newline;
- one logical instruction per wire node;
- `Lin` term order, duplicate facts and zero multipliers preserved;
- affine expressions rendered with the constant first and prefix rational coefficients;
- `ret` inline when it fits in 100 columns including indentation, otherwise both lists one item per line with trailing commas;
- empty vectors rendered `()`, empty `drop` rendered `drop`;
- no comments, macros, aliases or named checks.

`assemble(disassemble(c)) == c` for valid certificates. The number of instruction lines equals the number of `Step` + `End` + `DerivationEnd` nodes.

## CLI

```sh
rpx assemble proof.rpa proof.rpx
rpx disassemble proof.rpx recovered.rpa
rpx verify source.mcm target.mcm proof.rpx
```

`assemble` is syntax and encoding only. `disassemble` is canonical text only. Neither establishes mathematics. The manual's complete examples are [redundant](rpx/examples/redundant/proof.rpa), [elimination](rpx/examples/elimination/proof.rpa) and [piecewise](rpx/examples/piecewise/proof.rpa).

## Limits and rejection

RPA 12 text is limited to 512 MiB, 20,000,000 instruction/expression nodes, and nesting depth 128. Failure to parse is `INVALID`; exceeding a documented limit is `RESOURCE_LIMIT`.

`RPA 11`, `RPA-S 1`, old property fields, `--models`, `disassemble-source`, macros and named checks do not exist in RPA 12. Historical files keep their old bytes and require an explicitly supplied old decoder and migration; changing only the header is invalid.
