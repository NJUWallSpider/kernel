# Current repository tools

Run these from the repository root. The Rust `rpx` CLI performs verification;
the Python tools are auxiliary checks, not a second proof core.

| Task | Entry point |
| --- | --- |
| Manual examples and rejection checks | `check_rpx_manual.py` |
| Documentation link check | `check_docs.py` |
| Native API performance benchmark | `benchmark_compiler_api.py` |

Case deliverables are fixed current artifacts: `source.mcm`, `target.mcm`,
`proof.rpa`, `proof.rpx`, `delivery.json`, and `preparation.json`. The historical
LP-to-proof generators and their legacy model/expression bridge have been
removed. Existing proofs are verified with `rpx verify` or rebuilt from RPA 12
with `rpx assemble`; no LP input is required.
