# Compact Cases representation experiment

This isolated prototype boxes the uncommon Cases payload, reducing the Step enum
slot from208to96bytes on the measured target. It changes Rust in-memory layout
only; binary RPX and RPA schemas, mathematical fields and rules stay identical.
The prior frozen V3 sources remain untouched. Reproduction is in
`tools/prepare_boxed_cases_experiment.py`; the source delta and101passing tests
are preserved under `bench/boxed-cases-prototype`.

The acceptance threshold was recorded before the candidate measurements in
`bench/boxed-cases-experiment.json`: at least20%RSS reduction for history65536,
and review any branch1024execution regression above15%. Both criteria were met.
All23workloads have exactly equal MCM/RPA/RPX/request hashes and mathematical
counters before/after. All207verification samples and69separate RSS processes
returned VERIFIED. Workers explicitly held builds/tests/preparation; external
OS/user activity remains uncontrolled.

| Workload | Before execute ms | After execute ms | Before RSS MiB | After RSS MiB |
| --- | ---: | ---: | ---: | ---: |
| history-64 | 0.057 | 0.089 | 2.12 | 2.12 |
| history-4096 | 2.668 | 2.387 | 5.31 | 4.42 |
| history-65536 | 39.694 | 39.207 | 53.25 | 39.25 |
| branch-1 | 0.010 | 0.010 | 2.03 | 2.03 |
| branch-64 | 0.075 | 0.076 | 2.20 | 2.22 |
| branch-1024 | 1.041 | 1.029 | 3.41 | 3.42 |
| chain-16 | 0.235 | 0.236 | 2.28 | 2.28 |
| chain-64 | 3.019 | 3.027 | 3.27 | 3.28 |
| chain-256 | 46.447 | 46.004 | 15.45 | 15.59 |
| local-1 | 0.010 | 0.010 | 2.03 | 2.03 |
| local-1000 | 2.598 | 2.580 | 5.62 | 5.55 |
| local-10000 | 26.838 | 27.061 | 35.45 | 34.39 |
| bigint-64 | 0.540 | 0.528 | 2.59 | 2.61 |
| bigint-512 | 0.563 | 0.541 | 2.66 | 2.72 |
| bigint-4096 | 0.663 | 0.644 | 3.47 | 3.50 |
| real-33 | 1170.078 | 1164.245 | 362.25 | 343.06 |
| real-40 | 6.910 | 6.818 | 3.91 | 3.89 |
| real-65 | 3757.004 | 3691.935 | 865.27 | 854.09 |
| real-68 | 693.559 | 686.596 | 90.08 | 89.91 |
| real-71 | 130.559 | 127.976 | 16.23 | 16.28 |
| real-79 | 267.719 | 263.639 | 54.77 | 54.81 |
| real-84 | 13.682 | 13.721 | 4.89 | 4.83 |
| real-88 | 185.197 | 180.370 | 51.12 | 43.22 |

History65536peakRSS falls53.25→39.25MiB (26.3%); actualtest88falls51.125→43.219MiB
(15.5%). Actualtest65improves onlyabout1.3%because model/maps dominate its memory.
Branch1024execution is1.041→1.029ms with essentially unchanged RSS, so the extra
allocation for each Cases payload produced no material regression in that workload.
Tiny history64execution is0.057→0.089ms and its full-process latency2.207→2.785ms;
this noisy small-case regression is retained, not silently discarded. The change
is justified principally by memory reduction, not a universal latency claim.

No historical file/index or streaming claim follows from this layout change.
Whole-file decoding still retains every Step. Integrating into later versions
requires their complete tests and corpus replays before accepting new coverage.

Raw before: `bench/results/extended-v3-quiescent/raw.json`; raw after:
`bench/results/boxed-cases-v3-quiescent/raw.json`. Both retain distributions,
preparation costs, hashes and environment metadata.
