# Supplied C4 proof: reverse substitution helper

This is a mechanical check of the proof supplied by the completed C4 test9
agent, **not another autonomous acceptance run**. Only its hand-written ordered
objective cancellation loop was replaced by `derive_substitution`; its target,
maps, equations, residual witness, and other proof steps are unchanged.

The Kernel verified all four original MI/LP correspondence claims. Source MCM,
target MCM, RPX, Request, and committed MPS are byte-identical to C4. The exact
script hashes, verifier hash, API checkpoint, and file comparison are retained
in [check.json](check.json). The modified script and complete generated outputs
remain in the external run directory recorded there.

The single invocation took 0.87 seconds. It was not a matched timing experiment;
no speedup estimate follows from that measurement. This check establishes that
the new helper preserves this caller-supplied derivation and artifact binding.
