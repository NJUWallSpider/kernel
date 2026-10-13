# Independent completion-wave review — 2026-10-11

Scope: **the 21 cases completed on 2026-10-11 and VERIFIED in audit/acceptance.json at the time of review**: test8,24,29,31,41,45,51,52,55,56,61,62,64,66,67,73,81,82,83,85,86.
Test36/test58 (documented gaps), test46/test72/test74 (not complete at cutoff), and the V10 capability proposal are **OUT of the review scope**. The gap/proposal notes below are context, not additional review verdicts.
Result after metadata amendments: **21 PASS; zero P1/P2 findings; four corrected P3 labeling defects**. These are case-certificate review results, not a formal proof of kernel soundness.

## Method and evidence identity

Four campaign reviewers of record: `ReviewWave1a`, `ReviewWave1b`, `ReviewWave1c`, and `AllOptima`; AllOptima additionally used read-only subordinate reviews for test24/55/64/81. Sources are their terminal review reports, current case receipts/requests, original committed reports, and `audit/remaining_requirements.json`.
For each case: mechanical receipt validation mirroring the acceptance-ledger rebuild; two fresh assemblies byte-compared with committed RPX; two verifies compared on **all non-timing JSON fields**, including complete execution statistics; deterministic reconstruction of every recorded negative mutation; and at least one exact-rational semantic spot-check against independently parsed original model text.
All **72/72 recorded mutations across 21/21 cases** were reconstructed, assembled successfully, and verified INVALID with exact recorded RPA/RPX SHA-256, exit code, and full rejection payload (including an obligation id where present). Replays used temporary directories, removed afterward. No syntax/decoding-only negative was found; inverse/observation omissions are separately recognized as obligation-completeness checks, not algebraic deductions.
AllOptima filled the initially incomplete mutation-replay coverage for test24/55/64/81. ReviewWave1c independently replayed test83's four mutations; thus every case's mutation replay was performed by an agent other than its author. Test83's original author AllOptima performed its fresh model-arithmetic spot-check and deterministic positive replays; that author overlap is disclosed, not presented as independent authorship.

| Identity | SHA-256 |
|---|---|
| Reviewed executable `target/release/rpx` | `4acaf2484f7444975bdcc792d7a9a8ff6532f8848ab7070150ceabb4f2d6ae8d` |
| Mechanical validator `/tmp/validate_receipts.py` | `f8202d57e02749fe23e96fdb621a643b84d5d635ebcc9eccbe26c3d680180b43` |
| Model inventory `audit/corpus_inventory.json` | `a277cf8b47928309fcb384ff330eed63e18e839ffb6405432dcf85a8aef1591c` |
| Requirements `audit/remaining_requirements.json` | `cd56de88234b1480b2ab12ce89a5c0b31c6ec796b096663c30f6235c28d2f2f1` |

## Per-case verdicts

Coverage **R** means every recorded mutation was independently reconstructed and its assembled hashes/full rejection result matched the receipt. **I** would mean recipe inspection plus receipt-result checks only: **R=21, I=0**. Reviewer column names the campaign reviewer; `+A` denotes AllOptima's later mutation-gap fill, and `C mutations` denotes ReviewWave1c's independent test83 replay.

| Case | Verdict | Reviewer / coverage | Exact semantic spot-check summary | `proof.rpx` SHA-256 |
|---|---|---|---|---|
| test8 | PASS | ReviewWave1a / R | Resource Lin0 gives C0001≤3; full fractional witness violates only tight_R10750 by15/8. | `067765b202e58712a598f2fbb263981f3783be95c6ead6d615ca79c6eadb5d45` |
| test24 | PASS | AllOptima / R | Reverse Lin0 = −RowEq2307 gives 1−sum(cover)≤0; deleted R0006 becomes −y≤0. | `a848ca778482e94be2b87ebc8d9745baecc6ca4c555a58f8560edd1739589b36` |
| test29 | PASS | ReviewWave1a / R | Actual quotient equalities and nonnegativity recover EQ7265: b8_012−b22_001≤0. | `65e2cfeddda2ad1858ea52f77257ecb21b993862b9ef1397df634688c0d91eb6` |
| test31 | PASS | ReviewWave1a / R | Leaf-cut Int Lin2145 cancels four integer arcs and proves Atr_10_178tp_184_li1 integral. | `11da4304e11264229ca97e577160c380b7ab0a5b6ee263d8d9eabbd2c219936a` |
| test41 | PASS | ReviewWave1a / R | Four balances and entering-arc lower bounds give VAR290−167/25≤0. | `8abc61f08e0cb06ed56453f860ea4a2d15ea6aa1837031b090b516385899c4b4` |
| test45 | PASS, P3 fixed | ReviewWave1a / R | Lin188 cancels −17000C1302 using17000(C1302−1), exactly target R1323. | `c9a54be472bda39e74e3e45a5a7fc2b7f0735f4c12dae040b180c72d051a827e` |
| test51 | PASS | ReviewWave1b / R | Lin1225 plus active branch reduces to positive δ=145007/1250000000, excluding x0=1. | `1e352811450cdaf518cd1ab1a9d5b256b47f1c66754d426384068f675005aa3b` |
| test52 | PASS | ReviewWave1b / R | Lin13300's exact gap bound reduces in the active branch to δ=21852497/2500000000>0. | `69aa6f8155bfc871b1ac63056d9fa4ec5811106ab408d166684881b58af512a2` |
| test55 | PASS | AllOptima / R | Lin1280: (x−338u)/480+(71/240)(−u)=x/480−u; capacity338=400−62. | `5d6f50cd55e2f2506994571d7dabd15bfc47e7d15144090775866c6fff200a31` |
| test56 | PASS | ReviewWave1b / R | c2257:2x11828−x97411=0 and x97411≤1 imply x11828≤1/2, then integer zero. | `2123712ac0947305e75828b934012a27d538311d1924d6bf3c367fd0f3c77b2e` |
| test61 | PASS | ReviewWave1b / R | Lin30708 cancels eight auxiliaries in c536…c544, giving exactly target x41≤0. | `f0ff6eb9363a952c00e1d3d50ac1d7f55daff4fd6e55d7ca07a60578c7f46612` |
| test62 | PASS | ReviewWave1b / R | First Cases proof's30 branch endpoints rechecked; q1 lower side = −x0−x536+x706≤0. | `50964fcdba988fe2a8bb2842dc37df5588cb8a9e0561d950b0d665559cdb4f53` |
| test64 | PASS, P3 fixed | AllOptima / R | Lin19952 restores assignTimes via coefficients−1×6,−2×2; RHS−5+5=0. | `dac2759ae7b9a8134ffbf4fa7b02fa05b3fba848b305ab2135933e0ccb8f5f04` |
| test66 | PASS | ReviewWave1c / R | Half-sum of five cycle rows/spoke bounds gives sum(cycle)−5c0/2≤0; full point gap1/2. | `53ff41159ab8e32b659af39c7dc0c786d9c4d1a134f0cb1fe28bdeaed87880ef` |
| test67 | PASS | ReviewWave1c / R | Four local lower bounds give4−Σc≤0; complete original point attains objective4. | `0f835e2df79488b5f9adea4d96cd8777b05c61725f0fdc95d3067a96ba0d5168` |
| test73 | PASS, P3 fixed | ReviewWave1c / R | Reverse Lin0 restores UnderCapLowercap216 exactly from two uppers and two lowers. | `0b3c664ee8f26ea80ec6d8f7053074785733613f5651df842243268ecb46d480` |
| test81 | PASS | AllOptima / R | Actual windows give T41−T40+91≤0; full source fractional point has zero violations. | `693826ab70b4aa46f3c0c33a781f84c1d2f45b7b61a78bf5e02dabbbef5ae57d` |
| test82 | PASS | ReviewWave1c / R | Distinct82 windows give T41−T40−2545≤0; active zero-arc contradiction196593061828613/10¹⁰. | `9abb235c787e0045460bfd79f27e59c0e60b26f312541f0b993cfd5407d9f6f5` |
| test83 | PASS | AllOptima; C mutations / R | Source c16 plus nonnegativity yields Local70: x1578+x42804−1≤0. | `2e9c8bbb1f156391cce214d04ca32340aa430a343f1470b1a52e47d9b4364d6c` |
| test85 | PASS, P3 fixed | ReviewWave1c / R |97 actual target equalities recover NOD0: constant−1 and184 coefficients+1. | `cea3c460055453ead923f919d2fb9ff4bc0ca50f57ebe7abcbb0b2e29d8a1d02` |
| test86 | PASS | ReviewWave1c / R | −balance+link+nonnegativity+737·inactive assumption gives16−x150−16x51≤0. | `e144a1b4e0d2fab1495ce2cf1457719cce0435876978597149cac1ca8b3c4c69` |

## Findings and amendments

**Zero P1/P2 findings.** The four P3 findings concern labels, not proof mathematics. Owners regenerated amended receipts and confirmed **all five artifact hashes stayed byte-identical**: `source.mcm`, `target.mcm`, `proof.rpa`, `proof.rpx`, `request.json`. Only metadata/preparer identities and new execution observations changed; negative mutation hashes/results remained unchanged.
- **test64 — AffineAlias fixed:** `missing_linear_premise` claimed an alias equality/source-row normalization; actually removes VarUpper21874 from saturation-fixing Lin70307 (RowEq9286 plus24 endpoint bounds), consumed by EqPair70308. Current reason names the last saturation endpoint premise; independent post-amendment replay matches both hashes and INVALID equality pair.
- **test45 — AffineAlias fixed:** `missing_capacity_bound` claimed reverse capacity implication; actually removes VarLower378 from reverse Lin0, losing the C0379 contribution to reconstructed slack C0505≥0. Current reason names reconstructed-slack nonnegativity; original rejection is obligation504.
- **test73 — CliqueColor fixed:** `missing_reverse_nonnegativity` claimed edge restoration; actually removes VarLower8380 from deleted box-redundant UnderCapLowercap216 restoration, reverse-LP Lin0. Current reason names the bound-redundant row; rejection is obligation28436.
- **test85 — QuotientTrio fixed:** counts `reciprocal_classes=1908` / `omitted_classes=144` counted paired reciprocal blocks, not3816 directional classes. Current keys are `reciprocal_blocks` / `omitted_blocks`. Shared-helper amendment also corrected test29's corresponding labels without changing its five artifacts.
Amendment confirmations: AffineAlias's before/after comparisons, CliqueColor's `all_five_byte_identical`, QuotientTrio's before/after comparisons, and the four amended `cases/test{45,64,73,85}/preparation.json` receipts. Current RPX identities are fixed above.

## Evidence coverage limitations and explicit non-claims

Coverage distinguishes independently reconstructed/hash-compared mutations from recipe/receipt-only inspection; the latter gaps were filled before publication, so final counts are21 reconstructed cases /0 recipe-only cases. A mutation missing an inverse/observation obligation exercises completeness, not the omitted expression's algebra.
The semantic guarantee here is **one spot-check per case, not every obligation**; some reviewers additionally checked complete points, multiple dependencies or counts. Preparation scripts remain untrusted. This campaign is **not formal verification of the Rust kernel** and **does not re-derive the lift builders' premise-to-generated-rows existence lemmas**. See `LIFT_TRUST_REVIEW.md` for that trusted boundary.
Reviewers did not modify model, certificate, request or receipt artifacts. Authors made only the separately recorded P3 amendments; this consolidation writes only this document. No solver optimum, runtime improvement or omitted LP relation follows from a review PASS.
Contract exclusions remain material: test83 does not separately certify all-optimizer dominated-column exclusion; test62's seven-clause exclusion is a documented non-claim, not established by its Feasible point; local witnesses in test61/73 are not promoted to full-model strictness.

## Out-of-scope gap/proposal context

- **test36 remains BLOCKED:** universal all-optimizer exclusion is not expressible by the current caller contract. `cases/test36/attempts/strong_request.json` is rejected for unknown field `all_source_optimizer_coordinates_zero`. Reverse Equal recovery and objective6425 source feasibility are VERIFIED subsets; a source-feasible terminal1/4850 at objective6426 refutes unrestricted terminal integrality/zero-fixing. Forward minimum-preservation is explicitly **not certified** in that subset. Evidence is under `cases/test36/attempts/` and the BLOCKED receipt.
- **test58 remains BLOCKED:** reverse direction is VERIFIED; naive forward local merging fails obligation1372, with merged capacity164 versus82. The missing constructive step is a jointly demand-bounded subflow, not a bound on arbitrary circulation-bearing source flow. Fixtures and exact failures are under `cases/test58/attempts/`; this is not a proof of fundamental ISA impossibility.
- `CAPABILITY_PROPOSAL_NOTES.md` (SHA-256 `b92dc02e2e958f98cccf38037056132ba586c29488c67817f025f79ff8dd6c84`) proposes caller-bound strict-improvement exclusion (tentative V10) and joint demand-bounded subflow lift (tentative V11). **Proposal only: neither implemented nor frozen; no acceptance or new supported header is asserted.**

## Reproduction

Run from the repository root. `/tmp/validate_receipts.py` is a **temporary machine-local artifact**, not a permanent repository tool; its identity is above. It mirrors source/target inventory binding, artifact sizes/hashes, RPA identity, passing final verify and request claim/point/bijection counts without rewriting the ledger:
```sh
python3 /tmp/validate_receipts.py test8 test24 test29 test31 test41 test45 test51 test52 test55 test56 test61 test62 test64 test66 test67 test73 test81 test82 test83 test85 test86
```
One positive replay, to a caller-chosen temporary directory, uses exactly:
```sh
d=$(mktemp -d); target/release/rpx assemble cases/test83/proof.rpa "$d/proof.rpx" && cmp cases/test83/proof.rpx "$d/proof.rpx" && target/release/rpx verify cases/test83/source.mcm cases/test83/target.mcm "$d/proof.rpx" cases/test83/request.json; rm -rf "$d"
```
The following self-contained command reproduces one exact original-model Lin spot per reviewer (41/51/86/83); it was exercised with all four PASS. It imports no preparer/parser helper and writes no files:
```sh
python3 - <<'PY'
import json
from pathlib import Path
from fractions import Fraction as Q

def model(path, needed):
    names=[]; ids={}; rows=[]; terms={}; rhs={}; lower={}; section=None
    for line in Path(path).read_text().splitlines():
        if not line.strip() or line.startswith('*'): continue
        t=line.split()
        if not line[0].isspace():
            section=t[0]
            if section=='ENDATA': break
            continue
        if section=='ROWS' and t[0]!='N':
            rows.append(t[1])
            if len(rows)-1 in needed: terms[t[1]]={}
        elif section=='COLUMNS':
            if len(t)==3 and t[1].strip("'")=='MARKER': continue
            if t[0] not in ids: ids[t[0]]=len(names); names.append(t[0])
            for rn,c in zip(t[1::2],t[2::2]):
                if rn in terms: terms[rn][ids[t[0]]]=terms[rn].get(ids[t[0]],Q(0))+Q(c)
        elif section=='RHS':
            for rn,c in zip(t[1::2],t[2::2]): rhs[rn]=Q(c)
        elif section=='BOUNDS' and t[0] in ('LO','LI','FX'): lower[ids[t[2]]]=Q(t[3])
    return names,rows,terms,rhs,lower
jobs=[('ReviewWave1a','test41',0,Q('-167/25'),{'VAR290':Q(1)}),('ReviewWave1b','test51',1225,Q('145007/1250000000'),dict(zip(['x1225','x1226','x1227','x1228','x1229'],[-Q(n,10**10) for n in [137920007,150649994,63180029,27270019,1160056]]))),('ReviewWave1c','test86',1,Q(16),{'x150':Q(-1),'x51':Q(-16)}),('AllOptima','test83',70,Q(-1),{'x1578':Q(1),'x42804':Q(1)})]
for reviewer,cid,ident,want_const,want_terms in jobs:
    folder=Path('cases')/cid; cert=json.loads((folder/'proof.rpa').read_text().split('\n',1)[1]); block=cert['blocks'][0]; assumption=None
    if cid=='test86': case=block['steps'][0]['Cases']; assumption=case['split']; block=case['left']
    lin=next(s['Lin'] for s in block['steps'] if 'Lin' in s and s['Lin']['id']==ident)
    needed={i for ref,_ in lin['terms'] for typ,i in ref.items() if typ.startswith('Row')}
    receipt=json.loads((folder/'preparation.json').read_text()); names,rows,terms,rhs,lower=model(receipt['source']['path'],needed)
    constant=Q(lin['constant']); coef={}
    for ref,m in lin['terms']:
        typ,i=next(iter(ref.items())); scale=Q(m)
        if typ.startswith('Row'):
            rn=rows[i]; sign=-1 if typ=='RowLower' else 1; c=-rhs.get(rn,Q(0))*sign; a={j:v*sign for j,v in terms[rn].items()}
        elif typ=='VarLower': c=lower.get(i,Q(0)); a={i:Q(-1)}
        elif typ=='Assumption': assert i==0 and assumption is not None; c=Q(assumption['constant']); a={j:Q(v) for j,v in assumption['terms']}
        else: raise AssertionError(typ)
        constant+=scale*c
        for j,v in a.items(): coef[j]=coef.get(j,Q(0))+scale*v
    observed={names[j]:v for j,v in coef.items() if v}; assert (constant,observed)==(want_const,want_terms)
    print(reviewer,cid,'Lin',ident,'PASS',constant,{n:str(v) for n,v in observed.items()}); del cert,block
PY
```
