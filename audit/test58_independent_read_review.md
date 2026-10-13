# test58 independent read review

Reviewer: sibling agent `/root/model_layer`, communicated after reading `tools/prepare_test58_full.py`. This note records that independent read; it does not claim the reviewer executed the preparer or verifier. Reviewed preparer SHA-256: `87bf2aa998f3df730d8d435dfafa6542febf53adcddac8105decd19bdf059929`.

The reviewer found no mathematical issue in these concrete paths:

- A complete bridge net cut equality, its actual capacity row and the other flow's nonnegativity yield the correctly signed positive lower bound on the binary activation; exact rounding forces that activation to one.
- Path AND zero branches use the corresponding original edge capacity. The all-one branch uses the unconditional 82 bound and the proved AND equality.
- Parallel activation cost is exactly the kept-cost multiple of the OR sum upper bound, plus the nonnegative removed-cost-minus-kept-cost multiple of the removed activation lower bound.
- SignedLift and SubflowLift supply common tuples. Node balances are replaced through all relevant Signed equalities; the new inequalities `g<=f` and `g<=82` serve distinct proof obligations.
- A merged inactive-capacity branch uses both OR containment inequalities and its fixed-zero activation equality. The active branch uses the actual generated upper bound 82 and its activation guard.
- The old invalid inference that a two-path sum already has capacity 82 is not reused. The kernel still checks the complete actual output rows, domains and objective.

Functional evidence is separate: `cases/test58/preparation.json` records the full two-direction acceptance and eight rejected complete-certificate mutations, on the dedicated binary identified there.
