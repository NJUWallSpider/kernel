# Historical and reconstructed baseline

`verify.rs` exactly matches the pre-optimization verifier hash in
`baseline-v1-quiescent/raw.json`. Six of seven source files in the workspace snapshot
match that historical source manifest; `model.rs` was further hardened during the
session and its old complete source was not recovered. This mismatch is explicitly
recorded in `source-comparison.json`. No bit-for-bit historical rebuild is claimed.
The historical raw measurements and binary hash remain preserved.

To make the representation comparison independently reproducible,
`python3 tools/reproduce_sparse_ab.py --run --label NEW_LABEL` builds two frozen V1
workspaces using the identical later model/codec/dependency source. Only the sparse
accumulator change differs. It runs each crate's tests before building, verifies all
other source hashes agree, and runs the unchanged fixed workloads/repetition counts.
This is a new controlled replay of the old/new algorithm, not replacement history.

These V1 source snapshots are performance evidence, not the maintained verifier.
Current acceptance uses the production crate and current adversarial/resource tests.
