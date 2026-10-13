# Unified draft capability baseline

Absolute measurements for newly supported complete mathematical tasks. There is no speed ratio against an older version that does not support these tasks. Each row reports min / median / max unless marked otherwise.

## fixed-subflow-functional-and-performance-v1

Raw evidence: `bench/results/subflow-v10-complete-quiescent/raw.json` (SHA-256 `6fa16f9e58dd14c7d5f2eaa836e5eb6fb426eb16a50a16f1689da4ccf14fae0f`). Binary `96a6d3048d1deb6681733ab8b7356875f5e76bd1991c26337fe6820726b9c8f8`. Isolation declaration: Root explicitly cleared formal sampling after cold 262 tests, old 78 compatibility, 81-case replay, test36 regeneration and ledger refresh completed. Corpus reported no heavy process; model only edits small reports. Root and other workers remain computationally idle during these three sequential matrices.

Host: {'machdep.cpu.brand_string': 'Apple M5', 'hw.memsize': '17179869184', 'hw.ncpu': '10'}. Cache policy: Warm after generation/assembly, independent process per sample, no cache flush.

| Workload | Source / target vars | MCM total KiB | RPA / RPX KiB | Prepare process ms | Execute ms | Kernel total ms | Process total ms | RSS MiB |
|---|---:|---:|---:|---|---|---|---|---|
| subflow-n2-g1-w1 | 4 / 8 | 1.502 | 1.627 / 1.116 | 39.241 / 40.042 / 42.634 | 0.042 / 0.047 / 0.140 | 0.144 / 0.160 / 0.362 | 2.625 / 3.179 / 4.330 | 2.344 / 2.344 / 2.344 |
| subflow-n64-g1-w1 | 190 / 380 | 64.111 | 62.360 / 45.981 | 83.505 / 86.164 / 173.617 | 0.714 / 0.724 / 2.352 | 1.275 / 1.298 / 3.018 | 3.147 / 3.309 / 5.943 | 4.062 / 4.094 / 4.094 |
| subflow-n1024-g1-w1 | 3070 / 6140 | 1053.920 | 1053.479 / 740.669 | 7340.641 / 7379.169 / 7391.029 | 10.935 / 11.357 / 11.725 | 18.682 / 19.199 / 19.517 | 21.338 / 21.817 / 22.227 | 24.438 / 24.438 / 24.469 |
| subflow-n2-g4-w1 | 4 / 20 | 3.482 | 4.915 / 3.413 | 36.385 / 36.805 / 37.430 | 0.101 / 0.103 / 0.109 | 0.204 / 0.209 / 0.240 | 1.974 / 2.094 / 2.292 | 2.484 / 2.484 / 2.516 |
| subflow-n64-g4-w1 | 190 / 950 | 157.562 | 207.744 / 147.091 | 110.074 / 110.475 / 110.578 | 2.866 / 2.963 / 3.127 | 4.429 / 4.609 / 4.740 | 6.424 / 6.818 / 6.967 | 7.000 / 7.031 / 7.031 |
| subflow-n1024-g4-w1 | 3070 / 15350 | 2597.215 | 3521.631 / 2371.778 | 8954.718 / 9153.946 / 9188.612 | 55.090 / 56.732 / 60.381 | 80.592 / 82.759 / 85.326 | 85.338 / 87.707 / 90.217 | 69.141 / 69.141 / 69.172 |
| subflow-n2-g1-w4 | 16 / 20 | 3.158 | 2.846 / 2.237 | 37.376 / 37.399 / 40.147 | 0.102 / 0.107 / 0.123 | 0.213 / 0.224 / 0.255 | 2.241 / 2.347 / 3.008 | 2.453 / 2.453 / 2.484 |
| subflow-n64-g1-w4 | 760 / 950 | 150.992 | 124.704 / 99.233 | 114.713 / 115.254 / 123.717 | 3.472 / 3.590 / 4.887 | 5.095 / 5.260 / 6.587 | 7.428 / 7.674 / 9.436 | 5.578 / 5.609 / 5.609 |
| subflow-n1024-g1-w4 | 12280 / 15350 | 2482.305 | 2137.142 / 1601.108 | 8521.269 / 8523.464 / 8630.630 | 58.496 / 64.151 / 69.966 | 83.654 / 91.997 / 97.833 | 88.548 / 98.199 / 102.994 | 45.094 / 45.125 / 45.141 |
| test58 | 2500 / 607 | 376.435 | 2024.862 / 1290.418 | archived author 3161.638; not remeasured | 18.035 / 18.369 / 18.958 | 25.155 / 25.525 / 26.040 | 28.234 / 28.749 / 29.443 | 31.875 / 31.891 / 31.922 |

| Workload | Model decode ms | Proof decode ms | Generation internal ms | Assembly ms | Logical work | Terminal obligations | Generated vars / rows |
|---|---|---|---|---|---:|---:|---:|
| subflow-n2-g1-w1 | 0.032 / 0.034 / 0.112 | 0.021 / 0.022 / 0.030 | 0.860 / 0.914 / 1.252 | 0.132 / 0.190 / 0.517 | 856 | 25 | 4 / 6 |
| subflow-n64-g1-w1 | 0.365 / 0.374 / 0.413 | 0.135 / 0.143 / 0.153 | 44.256 / 44.663 / 118.982 | 0.592 / 1.046 / 1.261 | 38964 | 1079 | 190 / 254 |
| subflow-n1024-g1-w1 | 5.507 / 5.627 / 5.805 | 1.947 / 1.985 / 2.078 | 7293.973 / 7329.953 / 7340.181 | 6.788 / 6.946 / 7.644 | 646468 | 17399 | 3070 / 4094 |
| subflow-n2-g4-w1 | 0.042 / 0.044 / 0.046 | 0.023 / 0.024 / 0.026 | 1.474 / 1.475 / 1.564 | 0.160 / 0.174 / 0.181 | 2779 | 67 | 16 / 24 |
| subflow-n64-g4-w1 | 0.903 / 0.930 / 1.041 | 0.550 / 0.571 / 0.654 | 72.352 / 72.552 / 72.800 | 1.878 / 1.886 / 1.897 | 131499 | 2981 | 760 / 1016 |
| subflow-n1024-g4-w1 | 15.642 / 16.078 / 16.698 | 8.621 / 9.179 / 9.627 | 8869.987 / 9072.008 / 9107.640 | 29.421 / 29.935 / 32.572 | 2166115 | 48101 | 12280 / 16376 |
| subflow-n2-g1-w4 | 0.043 / 0.048 / 0.055 | 0.023 / 0.027 / 0.030 | 1.339 / 1.367 / 1.417 | 0.162 / 0.171 / 0.177 | 1584 | 49 | 4 / 6 |
| subflow-n64-g1-w4 | 1.066 / 1.112 / 1.160 | 0.447 / 0.475 / 0.499 | 72.961 / 73.325 / 75.179 | 1.431 / 1.554 / 1.597 | 80802 | 2219 | 190 / 254 |
| subflow-n1024-g1-w4 | 17.141 / 18.985 / 20.702 | 6.766 / 7.732 / 8.311 | 8445.113 / 8451.259 / 8563.770 | 20.506 / 21.352 / 22.777 | 1371358 | 35819 | 3070 / 4094 |
| test58 | 1.924 / 1.954 / 2.007 | 4.756 / 4.951 / 5.034 | archived receipt | archived receipt | 2029879 | 8448 | 3557 / 5324 |

All 10 fixed workloads retain every verification and RSS sample. The report checks exact statistics equality and archived artifact hashes. It refuses failed/missing RSS samples or any non-VERIFIED result.

Synthetic preparation includes complete exact author generation and assembly, including independent nonempty-point checks; direct MCM authoring does not imply measured MPS canonicalization. The subflow author currently scans arcs per node, so its preparation cost includes that simple O(nm) construction. No preparation or scalar cost is represented as constant-time theorem logic. The actual test58 receipt retains separate source/target canonicalization and prior author/assembly times; its empty preparation array means unmeasured here, never zero cost.

## fixed-strict-improvement-and-full-image-performance-v1

Raw evidence: `bench/results/strict-image-v10-complete-quiescent/raw.json` (SHA-256 `9fb1e9ee56d67016d34d2c62fca4440ae179af3f4b0e3b3a01d05ad821938c81`). Binary `96a6d3048d1deb6681733ab8b7356875f5e76bd1991c26337fe6820726b9c8f8`. Isolation declaration: Continuation of the root-cleared sequential capability window after subflow completed. Root and corpus remain computationally idle; model edits small reports only. No other owned heavy task overlaps these samples.

Host: {'machdep.cpu.brand_string': 'Apple M5', 'hw.memsize': '17179869184', 'hw.ncpu': '10'}. Cache policy: Warm after generation/assembly, independent process per sample, no cache flush.

| Workload | Source / target vars | MCM total KiB | RPA / RPX KiB | Prepare process ms | Execute ms | Kernel total ms | Process total ms | RSS MiB |
|---|---:|---:|---:|---|---|---|---|---|
| strict-n1 | 1 / 1 | 0.230 | 0.278 / 0.135 | 35.314 / 36.188 / 37.003 | 0.006 / 0.007 / 0.046 | 0.066 / 0.068 / 0.159 | 1.825 / 1.999 / 2.220 | 2.156 / 2.156 / 2.156 |
| strict-n64 | 64 / 64 | 7.352 | 3.530 / 2.780 | 37.797 / 37.802 / 38.679 | 0.041 / 0.042 / 0.063 | 0.151 / 0.159 / 0.191 | 1.822 / 2.012 / 2.200 | 2.391 / 2.391 / 2.391 |
| strict-n4096 | 4096 / 4096 | 477.957 | 219.144 / 172.093 | 134.121 / 137.628 / 141.256 | 2.015 / 2.046 / 2.108 | 4.609 / 4.679 / 4.827 | 6.783 / 6.897 / 7.796 | 7.766 / 7.766 / 7.766 |
| image-n1 | 1 / 1 | 0.229 | 0.155 / 0.100 | 36.256 / 36.674 / 37.429 | 0.004 / 0.005 / 0.007 | 0.066 / 0.070 / 0.083 | 1.907 / 1.965 / 2.160 | 2.172 / 2.172 / 2.172 |
| image-n64 | 64 / 64 | 7.350 | 2.730 / 3.114 | 37.365 / 37.376 / 38.787 | 0.043 / 0.044 / 0.046 | 0.181 / 0.190 / 0.207 | 1.991 / 2.118 / 2.225 | 2.438 / 2.438 / 2.438 |
| image-n4096 | 4096 / 4096 | 477.955 | 175.031 / 196.052 | 112.911 / 114.626 / 114.694 | 2.223 / 2.294 / 2.362 | 6.176 / 6.261 / 6.397 | 8.336 / 8.526 / 8.776 | 8.875 / 8.875 / 8.891 |

| Workload | Model decode ms | Proof decode ms | Generation internal ms | Assembly ms | Logical work | Terminal obligations | Generated vars / rows |
|---|---|---|---|---|---:|---:|---:|
| strict-n1 | 0.012 / 0.012 / 0.063 | 0.012 / 0.013 / 0.015 | 0.432 / 0.446 / 0.489 | 0.096 / 0.100 / 0.386 | 11 | 3 | 0 / 0 |
| strict-n64 | 0.043 / 0.045 / 0.055 | 0.030 / 0.031 / 0.034 | 2.002 / 2.093 / 2.127 | 0.143 / 0.151 / 0.157 | 452 | 129 | 0 / 0 |
| strict-n4096 | 1.605 / 1.642 / 1.689 | 0.871 / 0.892 / 0.970 | 96.302 / 97.752 / 100.998 | 1.727 / 1.763 / 1.769 | 28676 | 8193 | 0 / 0 |
| image-n1 | 0.015 / 0.016 / 0.020 | 0.011 / 0.012 / 0.015 | 0.380 / 0.410 / 0.438 | 0.105 / 0.111 / 0.112 | 10 | 0 | 0 / 0 |
| image-n64 | 0.047 / 0.049 / 0.057 | 0.052 / 0.055 / 0.061 | 1.656 / 1.705 / 1.865 | 0.164 / 0.173 / 0.178 | 577 | 0 | 0 / 0 |
| image-n4096 | 1.615 / 1.660 / 1.673 | 2.137 / 2.198 / 2.306 | 73.302 / 74.910 / 75.515 | 2.932 / 3.043 / 3.058 | 36865 | 0 | 0 / 0 |

All 6 fixed workloads retain every verification and RSS sample. The report checks exact statistics equality and archived artifact hashes. It refuses failed/missing RSS samples or any non-VERIFIED result.

Synthetic preparation includes complete exact author generation and assembly, including independent nonempty-point checks; direct MCM authoring does not imply measured MPS canonicalization. The subflow author currently scans arcs per node, so its preparation cost includes that simple O(nm) construction. No preparation or scalar cost is represented as constant-time theorem logic. The actual test58 receipt retains separate source/target canonicalization and prior author/assembly times; its empty preparation array means unmeasured here, never zero cost.

## fixed-conditional-input-domain-performance-v1

Raw evidence: `bench/results/halfspace-v10-complete-quiescent/raw.json` (SHA-256 `e9f9d7de9a89ecc4477b5e4e767b1ab803e12524d1cbea3b0c7fe1b3ba45cc82`). Binary `96a6d3048d1deb6681733ab8b7356875f5e76bd1991c26337fe6820726b9c8f8`. Isolation declaration: Final matrix in the root-cleared sequential capability window, after subflow and strict-image completed. Root and corpus remain computationally idle; model edits small reports only. No other owned heavy task overlaps these samples.

Host: {'machdep.cpu.brand_string': 'Apple M5', 'hw.memsize': '17179869184', 'hw.ncpu': '10'}. Cache policy: Warm after generation/assembly, independent process per sample, no cache flush.

| Workload | Source / target vars | MCM total KiB | RPA / RPX KiB | Prepare process ms | Execute ms | Kernel total ms | Process total ms | RSS MiB |
|---|---:|---:|---:|---|---|---|---|---|
| halfspace-n1 | 1 / 1 | 0.238 | 0.329 / 0.165 | 35.019 / 35.111 / 37.012 | 0.010 / 0.011 / 0.049 | 0.074 / 0.076 / 0.177 | 1.868 / 1.928 / 2.162 | 2.234 / 2.234 / 2.234 |
| halfspace-n64 | 64 / 64 | 7.359 | 5.998 / 5.148 | 37.005 / 37.771 / 39.290 | 0.084 / 0.090 / 0.922 | 0.209 / 0.233 / 1.139 | 1.972 / 2.778 / 11.517 | 2.547 / 2.562 / 2.562 |
| halfspace-n4096 | 4096 / 4096 | 477.965 | 413.740 / 324.086 | 126.034 / 126.458 / 126.667 | 4.337 / 4.646 / 8.844 | 7.444 / 7.791 / 15.424 | 9.861 / 10.470 / 21.259 | 10.422 / 10.516 / 10.594 |
| level-halfspace-n1 | 1 / 1 | 0.250 | 0.356 / 0.179 | 37.878 / 39.507 / 50.641 | 0.012 / 0.013 / 0.018 | 0.080 / 0.090 / 0.115 | 1.959 / 2.254 / 3.377 | 2.250 / 2.250 / 2.250 |
| level-halfspace-n64 | 64 / 64 | 7.371 | 6.025 / 5.162 | 39.259 / 40.852 / 41.497 | 0.088 / 0.090 / 0.098 | 0.221 / 0.233 / 0.290 | 2.143 / 2.227 / 2.429 | 2.547 / 2.547 / 2.547 |
| level-halfspace-n4096 | 4096 / 4096 | 477.977 | 413.768 / 324.100 | 126.664 / 132.561 / 132.909 | 4.392 / 4.601 / 4.915 | 7.492 / 7.759 / 8.581 | 10.024 / 10.453 / 13.690 | 10.703 / 10.703 / 10.703 |

| Workload | Model decode ms | Proof decode ms | Generation internal ms | Assembly ms | Logical work | Terminal obligations | Generated vars / rows |
|---|---|---|---|---|---:|---:|---:|
| halfspace-n1 | 0.014 / 0.015 / 0.067 | 0.013 / 0.013 / 0.022 | 0.379 / 0.425 / 0.661 | 0.094 / 0.103 / 0.335 | 133 | 4 | 0 / 1 |
| halfspace-n64 | 0.047 / 0.051 / 0.115 | 0.039 / 0.042 / 0.050 | 1.803 / 1.901 / 1.968 | 0.166 / 0.170 / 0.185 | 2503 | 193 | 0 / 1 |
| halfspace-n4096 | 1.624 / 1.666 / 3.434 | 1.297 / 1.389 / 2.816 | 84.666 / 85.828 / 86.315 | 2.953 / 2.955 / 3.013 | 177001 | 12289 | 0 / 1 |
| level-halfspace-n1 | 0.016 / 0.017 / 0.019 | 0.014 / 0.016 / 0.017 | 0.425 / 0.434 / 0.435 | 0.102 / 0.111 / 0.112 | 192 | 4 | 0 / 2 |
| level-halfspace-n64 | 0.048 / 0.050 / 0.060 | 0.039 / 0.041 / 0.044 | 1.888 / 2.017 / 2.181 | 0.184 / 0.184 / 0.197 | 2814 | 193 | 0 / 2 |
| level-halfspace-n4096 | 1.619 / 1.657 / 1.760 | 1.323 / 1.360 / 1.562 | 84.433 / 85.224 / 85.720 | 2.890 / 2.924 / 3.173 | 193440 | 12289 | 0 / 2 |

All 6 fixed workloads retain every verification and RSS sample. The report checks exact statistics equality and archived artifact hashes. It refuses failed/missing RSS samples or any non-VERIFIED result.

Synthetic preparation includes complete exact author generation and assembly, including independent nonempty-point checks; direct MCM authoring does not imply measured MPS canonicalization. The subflow author currently scans arcs per node, so its preparation cost includes that simple O(nm) construction. No preparation or scalar cost is represented as constant-time theorem logic. The actual test58 receipt retains separate source/target canonicalization and prior author/assembly times; its empty preparation array means unmeasured here, never zero cost.

Total successful measured fresh verification/RSS processes: 264. Separately, 63 fresh synthetic preparations each include one author process and one assembler process. Actual test58 preparation is archived and not remeasured. These measurements establish an absolute draft baseline, not an optimization claim, formal correctness proof, protocol freeze or proof that all possible workloads fit the resource policy.
