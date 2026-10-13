# RPX/RPA 7: optional menus and complete affine-map bijections

V7 adds one existence endpoint and an explicitly requested bijection contract.
MCM remains V1. RPX/RPA V1–V6 retain their bytes, mathematical rules and existing
Return-obligation order. Internal scope sharing and boxed Cases are independent
representation changes, not V7 features.

## Request and proof schema

RPA starts with `RPA 7\n`, followed by the strict JSON certificate object. Exact
scalars and all older objects retain their prior syntax. New objects are:

```text
MenuWitness      { maximum_index: u32, activation: Expr, index: Expr, checks: Ref[] }
End              { "MenuLift": { menus: MenuWitness[], body: Block } }
BijectionClaim   { forward_claim: u32, reverse_claim: u32 }
EqualityProof    { steps: Step[], checks: Ref[] }
BijectionWitness { claim: BijectionClaim, injectivity: EqualityProof }
Request          { claims: Claim[], points: PointClaim[], bijections: BijectionClaim[] }
Certificate      { claims: Claim[], blocks: Block[], points: PointWitness[],
                   bijections: BijectionWitness[] }
```

The new `bijections` field defaults to empty when omitted; all unknown fields are
rejected. The legacy request array still means directional claims with no point
or bijection claims. `verify` with its legacy claim slice rejects a certificate
containing point or bijection witnesses. `verify_request` compares every ordered
point and bijection claim with the caller's request before execution. Certificate
metadata cannot weaken, remove or add a requested pair. An empty request remains
invalid. Pair indices must be distinct and in range, with opposite orientations
and mutually matching input/output integer modes. Duplicate ordered pairs reject.

## MenuLift semantics

For each witness write K=`maximum_index`, A=`activation`, I=`index`. Both
expressions are canonical and use current parent coordinates. Exactly six
references prove these parent-scope propositions, in order:

1. LE(-A)
2. LE(A-1)
3. INT(A)
4. LE(-I)
5. LE(I-K*A)
6. INT(I)

`Exact` follows its existing rule; an INT expression of already enabled integer
variables with integral coefficients can legitimately use it. All premises for
all menus pass before the child receives any new integer declaration or row.
The current directional input mode must be integer-enabled. The existing affine
`Claim.inverse` restriction remains unchanged and excludes MenuLift.

Append K+1 integer variables z[0],...,z[K], each bounded [0,1], then two rows
per menu: `sum z-A=0` and `sum j*z[j]-I=0`. Variables are ordered by witness,
then ascending j; rows by witness, sum before moment. The second row is present
also for K=0. Original variables, rows and objective remain unchanged prefixes.
All menus use disjoint new variables and the same fixed parent point; an empty
menu array is an identity extension subject to the same mode/depth restrictions.
The complete actual output model is checked by the ordinary child proof.

Soundness: the premises force A in {0,1}. When A=0, I=0, and the all-zero tuple
satisfies the generated model. When A=1, I is an integer in [0,K]; choose precisely
z[I]=1. All menus' choices coexist. Thus every parent point has a joint extension.
This uses no search and makes no assertion that an arbitrary output map is
bijective. The trusted implementation and construction-oracle details are in
[MENU_V7.md](MENU_V7.md).

## Complete bijection obligations

For a requested pair let F be the exact `Return.map` of its indexed forward
claim, and let G be the complete mapping relation proved by its indexed reverse
claim. The forward block must have a root Return. Its steps may establish facts,
but there is one affine F, with exactly one expression per actual forward output
coordinate. Both directional claims are verified normally.

Every Return of G receives additional obligations after all V6 obligations. For
each pair targeting that reverse claim, in request order, then for each actual
forward output coordinate j in ascending order, check

```text
EQ(F[j](G.Return.map) - original_reverse_input[j]).
```

The same complete G tuple discharges its actual output model and all compositions.
Original reverse input coordinates remain prefixes through nested menu, interval
and flow extensions. All Split leaves check their own compositions; only a checked
Absurd leaf is vacuous. F constants remain in these substitutions.

After all directional proofs pass, the kernel constructs a fresh paired domain for
each requested F. It contains two full copies of the actual forward input S:
variables x then x', all old bounds and declared integer flags; original rows then
shifted rows with all constants and both finite sides; finally one equality
F[j](x)-F[j](x')=0 for every actual forward output coordinate. F constants cancel
in these last rows. The synthetic objective is zero: objectives are not domain
constraints. Fresh unique internal names carry no acceptance authority.

The paired proof uses the forward input's integer mode, fresh facts and fresh
assumptions at depth one. Its `steps` use existing scalar rules, including Cases;
there is no mapping endpoint or existential extension in an EqualityProof. It
then checks exactly every `EQ(x[i]-x'[i])`, i=0,...,dim(S)-1. Continuous and
unobserved coordinates are included. Missing or surplus checks reject. The helper
`verify_injectivity` validates actual models and the full map itself; acceptance
of a bijection additionally requires the indexed directional proofs and their
full compositions, which `verify_request` establishes.

The paired domain is exactly pairs of S points sharing F's full value. Proving
all coordinates equal establishes injectivity. The reverse proof and compositions
give, for every t in T, some s in S with F(s)=t, establishing surjectivity. For
any s in S, every reverse output at F(s) has the same F value as s; injectivity
forces that output to equal s. This proves the requested full-set bijection and
inverse relation even if G uses existence extensions. Objective preservation is
only what the constituent directional claims separately request and prove; the
pair contract itself adds no objective relation. Empty domains follow the same
quantified reasoning. No menu-specific injectivity axiom is trusted.

## Binary format

All V1–V6 primitives, little-endian integers, four-byte tags with zero reserved
fields, canonical rational encoding, arrays and depth conventions remain in force.
The header uses RPX magic, u16 version 7, zero u16 flags and exact u64 file length.

A V7 certificate consists of the complete V6 layout followed by:

```text
array<BijectionWitness>
BijectionWitness = u32 forward_claim | u32 reverse_claim | EqualityProof
EqualityProof    = array<Step> | array<Ref>
```

Each equality proof begins at depth one; Cases children increment that depth.
Counters are cumulative across directional, point-refutation and equality roots.
V7 still includes the V6 optional-refutation byte after every point's values.
There is no extra field in the ordinary Claim record.

MenuLift is endpoint tag 5 (the four-byte tag includes its reserved zero bytes):

```text
MenuLift = tag(5) | array<MenuWitness> | Block(body)
MenuWitness = u32 maximum_index | Expr activation | Expr index | array<Ref> checks
```

Its child increments the combined proof nesting depth by one. Earlier RPX
versions reject endpoint 5; they contain no trailing bijection array. A V7 file
with no bijections still ends with the zero array count. Encoders select the
lowest required version by traversing every block, every point refutation and
every equality-proof step tree, including logically contradictory branches.
Any MenuLift or nonempty bijection array selects at least V7. RPA version gating
uses that same bounded discovery. Unknown tags, flags, fields, trailing bytes,
truncation and excessive counts/depth reject as in earlier versions.

## Resources and executed evidence

The menu builder preflights expanded variables, rows, all six premises and total
support; validates old-coordinate expressions; checks exact intermediate products
and sums; charges copied and generated data; and reserves controlled buffers
fallibly. The paired builder similarly bounds two complete model copies, all F
rows and all coordinate goals. Directional proofs, model builders, paired proofs
and point witnesses consume one shared remaining work budget. Each proof root
starts fresh logical state, not a fresh work allowance. `menu_generated_*` counts
added menu data. `injectivity_generated_*` counts the complete synthetic paired
model; `injectivity_coordinates` counts all checked source coordinates. Overall
obligation, branch and linear counters include injectivity proofs.

The integration suite in `crates/core/tests/menu_bijection.rs` covers caller and
mode binding, missing and false middle premises, old-scope references, LP-mode
rejection, complete actual output obligations, original inverse restrictions,
full compositions at both Split leaves, nested Menu/Interval/Flow prefixes,
noninjective free coordinates, affine constants, multiple pair contracts and fresh
pair state, bounded counts/work/depth, truncations and systematic byte mutations.

`tests/vectors/generate_vectors.py` independently writes the 441-byte
`menu-v7.rpx` using Python's exact Fraction and struct primitives, without calling
Rust encoding. It proves a singleton menu and full bijection on the separately
written 117-byte `identity.mcm`. The K=0 second row is retained. Additional bytes
exercise V6 downgrade rejection and oversized V7 pair counts. V1–V6 positive
vectors remain byte-identical after decode/re-encode. These tests and independent
oracles are executable evidence, not a formal implementation proof. Full-run
receipts and actual-case certification are recorded separately.
