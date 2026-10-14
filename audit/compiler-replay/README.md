# Direct compiler corpus regression

All 81 previously VERIFIED shipped cases (`test8` through `test88`) passed,
including the three independently complete pieces of the test46 delivery:

- 83/83 pieces produced byte-identical frozen RPX from raw Certificate JSON.
- 83/83 complete caller requests verified against the shipped actual MCM pair.
- Every Statistics field matched the explicit pre-compiler `c16fdaf` verifier.
- Actual corpus coverage includes every frozen RPX version, V1 through V10.

The replay processed 4,090,495,643 bytes of raw JSON and 2,906,200,909 bytes of
RPX. Direct compilation took 36.87 seconds and verification took 128.41 seconds
on this host. These timings measure replay of existing authored proofs and do
not measure autonomous Agent discovery or proof-authoring time.

The raw JSON fixture input was obtained by removing the version header from
the existing preserved `proof.rpa` files. The compiler itself calls neither
the RPA parser nor the assembler. It deserializes Certificate JSON and invokes
the frozen encoder. Source/target/proof/request hashes and each command's JSON
report appear in [results.jsonl](results.jsonl). [identity.json](identity.json)
binds the immutable release-binary snapshot, the Rust source tree, and the
separately built baseline revision. [summary.json](summary.json) binds the
results file's hash and reports counts and timings.

Eleven historical preparation receipts record different work counts because
they predate intervening accounting changes. These are retained as
`historical_receipt_statistics_identity: false`. They are distinct from this
change: all 83 pieces have `pre_compiler_statistics_identity: true` against the
explicit pre-compiler revision.

An additional [test46 merged replay](test46-merged.json) compiled the existing
432,885,906-byte merged Certificate JSON body in 5.20 seconds, then verified
its complete three-claim request in 25.06 seconds. The result has 1,105,551
obligations and work 551,077,751, equal to the shipped pieces' aggregate
statistics. The legacy RPA assembler had rejected the preserved merged fixture
at its 256 MiB text cap. The direct bridge's 512 MiB input policy accepts it.
Generated JSON/RPX outputs remained temporary; shipped fixtures were unchanged.

Reproduce the corpus and baseline comparisons from the repository root:

```sh
cargo build --release
python3 audit/compiler-replay/replay.py
python3 audit/compiler-replay/baseline.py
python3 audit/compiler-replay/merged.py
```

The first script selects existing preparations already marked VERIFIED and
validates their recorded artifact identities. The second uses `git archive
c16fdaf`, builds an isolated temporary release binary, and compares the complete
current statistics with that baseline. No solver or model exploration occurs.

The independent `authoring_bridge` Rust test suite checks all five existing
extension previews, rejection of appended-coordinate premise references in the
parent scope, rejection of false Exact witnesses, canonical model-prefix
preservation, resource/schema limits, and objective-level/halfspace row order.
This audit is regression evidence; autonomous Agent acceptance is tracked
separately by the live run harness.
