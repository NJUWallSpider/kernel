Use mapping branches for case-dependent maps and Cases for a common derived conclusion.

## Split
`left, right = scope.split(expr, at=0)` gives assumptions expr<=0 and expr>=0. With kind="integer", require an integer threshold and `because` proving expr integral; the right assumption is expr>=at+1. For a single declared integral variable, because may be omitted to use its base integrality fact. Both scopes expose assumption and accept map/prove/finish. Complete every leaf, or explicitly close a contradictory branch. The parent becomes fixed after installation.

## Cases
`cases = scope.derive.cases(expr, kind="Le", expect=goal_expr)` creates left/right derivation scopes. Supply matching conclusions with `cases.left.conclude(fact)` and `cases.right.conclude(fact)`, or close_absurd in a contradictory branch. `cases.finish()` returns one Fact in the parent. For integer branching pass `integer=scope.integer(x)`. There are no primitive callbacks.

## Executable example
Run `python -m rpx._help.examples.branches` for continuous splits, integer splits and explicit Cases, each followed by complete verification.
