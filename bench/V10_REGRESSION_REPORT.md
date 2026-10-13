# V10 regression on unchanged old workloads

These measurements compare the same complete mathematical tasks and identical model, RPA, RPX and caller-request bytes. They are a performance regression check, not a correctness proof or a comparison against unsupported old capabilities.

Old executable: `target/validation-wave-rpx-2026-10-11/release/rpx`, SHA-256 `694b1083e2f960aa6e9002c0ce20e796b3bcf091a3397810f30aa43f0ec9f655`. Candidate: `target/validation-v10-complete/release/rpx`, SHA-256 `96a6d3048d1deb6681733ab8b7356875f5e76bd1991c26337fe6820726b9c8f8`.

Fixed plan: `bench/v10_regression_measurement_plan.json` (SHA-256 `5083d6e44380e4ca9a1499cee029cb84de790b70b1fee22fc23a539db969f2bc`). Both binary hashes agree before and after each matrix. The report verifies the fixed configs/drivers, source snapshots and lockfiles, every timing/RSS exit and VERIFIED status, exact complete mathematical statistics, claims/limits, and all paired artifact sizes and hashes.

Orchestration receipt: `bench/results/v10-regression-isolation.json` (SHA-256 `ccc20ded5bddbaebe1c8947a44c297acec271df9a586755ab2eb3cd232b9848a`), with all four fixed commands completed successfully. Recorded isolation declaration: All root acceptance, compatibility, ledger, build and test processes have completed. corpus_audit, draft_audit and model_layer confirmed no owned heavy computation; new capability sampling and report hashing finished before this run. Sequential old-initial, candidate-initial, old-extended, candidate-extended order; warm files; unrelated host and OS activity remain uncontrolled.

Nine fresh-process timing samples per workload; one separate RSS observation in the initial matrix and three in the extended matrix. Filesystem caches are warm after preparation, with no cache flushing. The fixed order is old initial, new initial, old extended, new extended; sampling is sequential, not randomized. Coordinator isolation does not control unrelated host or OS activity. Every observation and outlier is retained.

Times below are milliseconds, shown as min / median / max. Process includes startup and shutdown; execute is the internal verification stage. Changes are candidate minus old. Relative execute changes are suppressed below a 0.100 ms old median because tiny timings are easily dominated by timer resolution and scheduling. No confidence interval or universal speedup is inferred. RSS is median observed peak resident memory, in MiB; a single initial RSS observation is not a distribution.

## Initial matrix

Host: `{'machdep.cpu.brand_string': 'Apple M5', 'hw.memsize': '17179869184', 'hw.ncpu': '10'}`; platform `macOS-26.6.2-arm64-arm-64bit`. Toolchain: `rustc 1.96.0 (ac68faa20 2026-05-25)`.

Raw old: `bench/results/v10-regression-old-initial/raw.json` (SHA-256 `069a334594bdaaf08d12280864ee17bba1b1031c9d56b407a0efd4a060c20d2f`). Raw candidate: `bench/results/v10-regression-new-initial/raw.json` (SHA-256 `d08a9e5120b8748351c5c70410b708cf27485b37d54d020e8f72e810293e500a`).

| Workload | Execute old | Execute new | Execute median change | Process old | Process new | Process median change | RSS old → new MiB |
|---|---:|---:|---:|---:|---:|---:|---:|
| identity-1 | 0.011 / 0.013 / 0.076 | 0.009 / 0.010 / 0.042 | -3.000 µs; tiny baseline | 1.907 / 2.106 / 2.334 | 1.825 / 1.897 / 2.090 | -0.208 ms (-9.9%) | 2.203 → 2.172 |
| identity-1000 | 0.613 / 0.620 / 0.691 | 0.610 / 0.628 / 0.690 | +0.008 ms (+1.3%) | 3.357 / 3.529 / 3.913 | 3.393 / 3.513 / 4.765 | -0.016 ms (-0.4%) | 4.547 → 4.516 |
| identity-10000 | 6.315 / 6.514 / 7.070 | 6.381 / 6.500 / 6.803 | -0.014 ms (-0.2%) | 18.866 / 19.154 / 19.871 | 18.951 / 19.614 / 20.088 | +0.460 ms (+2.4%) | 23.828 → 23.781 |
| dense-100 | 0.053 / 0.059 / 0.078 | 0.057 / 0.059 / 0.070 | +0.000 µs; tiny baseline | 1.912 / 2.120 / 2.346 | 1.840 / 2.050 / 2.848 | -0.070 ms (-3.3%) | 2.469 → 2.438 |
| dense-1000 | 0.442 / 0.455 / 0.464 | 0.463 / 0.480 / 0.492 | +0.025 ms (+5.5%) | 2.776 / 2.925 / 2.969 | 2.943 / 3.124 / 3.549 | +0.200 ms (+6.8%) | 3.828 → 3.797 |
| dense-5000 | 2.216 / 2.246 / 2.429 | 2.258 / 2.328 / 2.391 | +0.082 ms (+3.7%) | 6.916 / 7.256 / 7.418 | 7.312 / 7.527 / 7.776 | +0.271 ms (+3.7%) | 8.969 → 8.953 |
| rational-10 | 0.017 / 0.019 / 0.024 | 0.016 / 0.019 / 0.020 | +0.000 µs; tiny baseline | 1.774 / 1.947 / 2.027 | 1.838 / 2.072 / 3.720 | +0.126 ms (+6.4%) | 2.281 → 2.219 |
| rational-1000 | 0.777 / 0.792 / 0.825 | 0.797 / 0.972 / 1.004 | +0.180 ms (+22.7%) | 3.386 / 3.578 / 4.677 | 3.400 / 3.710 / 4.010 | +0.132 ms (+3.7%) | 3.844 → 3.797 |

Physical artifact bytes and logical work are identical across the pair. Initial source and target name the same MCM file; its size is shown on both sides, not claimed as two distinct files.

| Workload | Source / target MCM bytes | RPA bytes | RPX bytes | Request bytes | Logical work | Obligations | Peak live facts |
|---|---:|---:|---:|---:|---:|---:|---:|
| identity-1 | 146 / 146 | 296 | 120 | 126 | 21 | 5 | 0 |
| identity-1000 | 99830 / 99830 | 102653 | 67053 | 126 | 20001 | 4001 | 0 |
| identity-10000 | 1017830 / 1017830 | 1074653 | 670053 | 126 | 200001 | 40001 | 0 |
| dense-100 | 5879 / 5879 | 8378 | 5961 | 126 | 1803 | 302 | 0 |
| dense-1000 | 58980 / 58980 | 85778 | 59061 | 126 | 18003 | 3002 | 0 |
| dense-5000 | 298980 / 298980 | 445778 | 295061 | 126 | 90003 | 15002 | 0 |
| rational-10 | 659 / 659 | 998 | 651 | 126 | 183 | 32 | 0 |
| rational-1000 | 58980 / 58980 | 85778 | 59061 | 126 | 18003 | 3002 | 0 |

### Read/decode and complete internal time

Each cell is old min / median / max → candidate min / median / max, in milliseconds.

| Workload | Read | Model decode | Proof decode | Kernel total |
|---|---:|---:|---:|---:|
| identity-1 | 0.033 / 0.036 / 0.055 → 0.031 / 0.035 / 0.043 | 0.012 / 0.015 / 0.033 → 0.012 / 0.013 / 0.030 | 0.008 / 0.009 / 0.011 → 0.008 / 0.009 / 0.012 | 0.064 / 0.076 / 0.158 → 0.063 / 0.070 / 0.119 |
| identity-1000 | 0.055 / 0.056 / 0.077 → 0.053 / 0.057 / 0.066 | 0.723 / 0.746 / 0.771 → 0.745 / 0.772 / 0.789 | 0.155 / 0.160 / 0.170 → 0.158 / 0.162 / 0.205 | 1.564 / 1.600 / 1.672 → 1.583 / 1.628 / 1.740 |
| identity-10000 | 0.206 / 0.239 / 0.289 → 0.221 / 0.247 / 0.268 | 7.606 / 7.697 / 8.217 → 7.644 / 7.896 / 8.140 | 1.539 / 1.576 / 1.646 → 1.559 / 1.636 / 1.673 | 15.811 / 16.102 / 16.546 → 15.869 / 16.300 / 16.696 |
| dense-100 | 0.036 / 0.040 / 0.071 → 0.037 / 0.040 / 0.144 | 0.057 / 0.064 / 0.067 → 0.058 / 0.061 / 0.153 | 0.023 / 0.025 / 0.034 → 0.024 / 0.025 / 0.043 | 0.172 / 0.196 / 0.218 → 0.180 / 0.183 / 0.395 |
| dense-1000 | 0.045 / 0.048 / 0.053 → 0.045 / 0.053 / 0.062 | 0.402 / 0.419 / 0.469 → 0.400 / 0.415 / 0.426 | 0.151 / 0.154 / 0.161 → 0.151 / 0.161 / 0.169 | 1.052 / 1.075 / 1.124 → 1.059 / 1.106 / 1.138 |
| dense-5000 | 0.092 / 0.096 / 0.106 → 0.088 / 0.093 / 0.120 | 1.980 / 2.024 / 2.185 → 1.956 / 1.986 / 2.152 | 0.706 / 0.752 / 0.776 → 0.718 / 0.737 / 0.765 | 5.024 / 5.136 / 5.324 → 5.083 / 5.176 / 5.360 |
| rational-10 | 0.032 / 0.039 / 0.057 → 0.031 / 0.045 / 0.108 | 0.023 / 0.023 / 0.026 → 0.023 / 0.023 / 0.026 | 0.008 / 0.010 / 0.011 → 0.011 / 0.012 / 0.014 | 0.081 / 0.092 / 0.111 → 0.083 / 0.101 / 0.165 |
| rational-1000 | 0.049 / 0.054 / 0.156 → 0.045 / 0.048 / 0.152 | 0.543 / 0.547 / 0.608 → 0.540 / 0.548 / 0.591 | 0.150 / 0.159 / 0.167 → 0.148 / 0.155 / 0.169 | 1.526 / 1.568 / 1.657 → 1.581 / 1.715 / 1.812 |

### Preparation recorded separately

Synthetic generation is one wall-time observation inside each benchmark driver, followed by independent canonical/assembler processes. These stages are outside verification timing and are not repeated preparation distributions. Canonical columns sum the one initial or two extended model conversions; assembly is separate. For actual cases no author, canonicalization or assembly cost was remeasured: receipt links mean unmeasured here, never zero cost.

| Workload / version | Generate ms | Canonical process / internal / parse ms | Assemble process / internal ms | Actual preparation receipt |
|---|---:|---:|---:|---|
| identity-1 / old | 0.400 | 3.204 / 0.449 / 0.150 | 2.895 / 0.390 | not applicable |
| identity-1 / new | 0.239 | 2.590 / 0.254 / 0.142 | 2.276 / 0.191 | not applicable |
| identity-1000 / old | 2.348 | 3.502 / 1.422 / 0.732 | 2.891 / 0.837 | not applicable |
| identity-1000 / new | 1.932 | 3.039 / 1.184 / 0.756 | 2.369 / 0.620 | not applicable |
| identity-10000 / old | 21.047 | 20.001 / 11.218 / 7.587 | 8.612 / 6.006 | not applicable |
| identity-10000 / new | 20.512 | 14.942 / 11.646 / 7.820 | 7.780 / 5.350 | not applicable |
| dense-100 / old | 0.663 | 2.674 / 0.348 / 0.072 | 2.262 / 0.340 | not applicable |
| dense-100 / new | 0.367 | 2.664 / 0.215 / 0.088 | 2.214 / 0.174 | not applicable |
| dense-1000 / old | 1.865 | 2.670 / 0.833 / 0.404 | 2.528 / 0.767 | not applicable |
| dense-1000 / new | 1.617 | 3.556 / 0.913 / 0.509 | 3.118 / 0.674 | not applicable |
| dense-5000 / old | 7.032 | 5.099 / 3.107 / 1.818 | 4.718 / 2.860 | not applicable |
| dense-5000 / new | 6.436 | 5.144 / 2.924 / 1.873 | 4.688 / 2.585 | not applicable |
| rational-10 / old | 0.230 | 2.213 / 0.098 / 0.033 | 2.073 / 0.120 | not applicable |
| rational-10 / new | 0.209 | 2.207 / 0.103 / 0.032 | 1.979 / 0.086 | not applicable |
| rational-1000 / old | 1.688 | 3.107 / 1.050 / 0.540 | 2.587 / 0.770 | not applicable |
| rational-1000 / new | 1.551 | 2.997 / 1.129 / 0.543 | 2.391 / 0.628 | not applicable |
## Extended matrix

Host: `{'machdep.cpu.brand_string': 'Apple M5', 'hw.memsize': '17179869184', 'hw.ncpu': '10'}`; platform `macOS-26.6.2-arm64-arm-64bit`. Toolchain: `rustc 1.96.0 (ac68faa20 2026-05-25)`.

Raw old: `bench/results/v10-regression-old-extended/raw.json` (SHA-256 `2c28c57e1b025f375d641ffa1e9bd88a511d9d85df345a18c604d59d13a085a1`). Raw candidate: `bench/results/v10-regression-new-extended/raw.json` (SHA-256 `3c426c7d598c18693338b570d8ba59204c2135cad4cc986ffe90dbb91b82c215`).

| Workload | Execute old | Execute new | Execute median change | Process old | Process new | Process median change | RSS old → new MiB |
|---|---:|---:|---:|---:|---:|---:|---:|
| history-64 | 0.021 / 0.023 / 0.028 | 0.022 / 0.023 / 0.058 | +0.000 µs; tiny baseline | 1.725 / 1.949 / 2.203 | 1.813 / 1.951 / 2.009 | +0.002 ms (+0.1%) | 2.297 → 2.281 |
| history-4096 | 0.638 / 0.645 / 0.694 | 0.664 / 0.672 / 0.681 | +0.027 ms (+4.2%) | 3.181 / 3.319 / 3.997 | 3.167 / 3.328 / 3.503 | +0.009 ms (+0.3%) | 4.625 → 4.609 |
| history-65536 | 10.693 / 11.155 / 11.324 | 10.619 / 10.874 / 11.526 | -0.281 ms (-2.5%) | 26.223 / 27.229 / 27.637 | 25.901 / 26.385 / 26.935 | -0.844 ms (-3.1%) | 39.438 → 39.422 |
| branch-1 | 0.008 / 0.010 / 0.012 | 0.008 / 0.009 / 0.013 | -1.000 µs; tiny baseline | 1.934 / 2.031 / 2.224 | 1.949 / 2.032 / 2.208 | +0.001 ms (+0.0%) | 2.203 → 2.172 |
| branch-64 | 0.031 / 0.035 / 0.037 | 0.030 / 0.031 / 0.039 | -4.000 µs; tiny baseline | 1.828 / 2.148 / 2.300 | 1.962 / 2.105 / 2.263 | -0.043 ms (-2.0%) | 2.406 → 2.344 |
| branch-1024 | 0.342 / 0.353 / 0.387 | 0.342 / 0.349 / 0.369 | -0.004 ms (-1.1%) | 2.814 / 2.903 / 3.069 | 2.681 / 2.779 / 2.873 | -0.124 ms (-4.3%) | 3.609 → 3.562 |
| chain-16 | 0.056 / 0.059 / 0.064 | 0.058 / 0.060 / 0.062 | +1.000 µs; tiny baseline | 1.863 / 2.051 / 2.207 | 1.889 / 2.000 / 2.085 | -0.051 ms (-2.5%) | 2.469 → 2.484 |
| chain-64 | 0.478 / 0.496 / 0.512 | 0.505 / 0.513 / 0.541 | +0.017 ms (+3.4%) | 2.838 / 2.912 / 3.149 | 2.905 / 3.062 / 3.134 | +0.150 ms (+5.1%) | 3.562 → 3.547 |
| chain-256 | 6.978 / 7.152 / 7.338 | 7.254 / 7.439 / 7.836 | +0.287 ms (+4.0%) | 15.857 / 16.052 / 16.768 | 15.906 / 16.305 / 16.629 | +0.253 ms (+1.6%) | 15.797 → 15.688 |
| local-1 | 0.009 / 0.010 / 0.014 | 0.008 / 0.009 / 0.013 | -1.000 µs; tiny baseline | 1.876 / 1.989 / 2.285 | 1.932 / 2.045 / 2.240 | +0.056 ms (+2.8%) | 2.219 → 2.172 |
| local-1000 | 1.289 / 1.318 / 1.357 | 1.289 / 1.312 / 1.377 | -0.006 ms (-0.5%) | 4.572 / 4.712 / 4.841 | 4.607 / 4.837 / 5.004 | +0.125 ms (+2.7%) | 5.750 → 5.734 |
| local-10000 | 13.491 / 13.725 / 14.310 | 13.517 / 14.064 / 15.523 | +0.339 ms (+2.5%) | 29.604 / 30.439 / 31.115 | 30.314 / 30.712 / 33.012 | +0.274 ms (+0.9%) | 34.594 → 34.578 |
| bigint-64 | 0.221 / 0.229 / 0.247 | 0.222 / 0.225 / 0.234 | -0.004 ms (-1.7%) | 2.354 / 2.563 / 2.763 | 2.448 / 2.579 / 2.722 | +0.015 ms (+0.6%) | 2.844 → 2.812 |
| bigint-512 | 0.220 / 0.227 / 0.233 | 0.228 / 0.232 / 0.238 | +0.005 ms (+2.2%) | 2.383 / 2.482 / 2.545 | 2.462 / 2.528 / 2.635 | +0.046 ms (+1.9%) | 2.938 → 2.922 |
| bigint-4096 | 0.277 / 0.282 / 0.299 | 0.283 / 0.289 / 0.302 | +0.007 ms (+2.5%) | 2.515 / 2.629 / 2.968 | 2.558 / 2.908 / 4.140 | +0.279 ms (+10.6%) | 3.719 → 3.688 |
| real-33 | 369.683 / 372.036 / 380.851 | 376.910 / 386.174 / 393.257 | +14.138 ms (+3.8%) | 566.572 / 570.185 / 581.149 | 576.883 / 586.152 / 599.274 | +15.967 ms (+2.8%) | 343.203 → 343.203 |
| real-40 | 2.116 / 2.205 / 2.250 | 2.121 / 2.227 / 2.328 | +0.022 ms (+1.0%) | 4.939 / 5.132 / 5.696 | 4.978 / 5.098 / 5.783 | -0.034 ms (-0.7%) | 4.078 → 4.062 |
| real-65 | 1741.469 / 1792.479 / 2697.136 | 1807.757 / 1864.392 / 1878.997 | +71.913 ms (+4.0%) | 2262.631 / 2365.817 / 3252.744 | 2350.707 / 2404.050 / 2496.344 | +38.233 ms (+1.6%) | 855.453 → 855.484 |
| real-68 | 349.243 / 353.671 / 359.534 | 352.873 / 357.597 / 370.066 | +3.926 ms (+1.1%) | 412.493 / 416.696 / 422.347 | 418.630 / 419.646 / 432.593 | +2.950 ms (+0.7%) | 90.188 → 90.125 |
| real-71 | 76.428 / 78.226 / 81.059 | 79.532 / 84.661 / 85.362 | +6.435 ms (+8.2%) | 88.662 / 90.147 / 93.414 | 92.110 / 97.329 / 98.515 | +7.182 ms (+8.0%) | 16.562 → 16.531 |
| real-79 | 91.706 / 92.846 / 94.025 | 96.413 / 100.561 / 105.853 | +7.715 ms (+8.3%) | 127.273 / 129.030 / 130.956 | 132.358 / 137.694 / 141.873 | +8.664 ms (+6.7%) | 54.969 → 54.953 |
| real-84 | 7.155 / 7.339 / 7.693 | 7.487 / 7.636 / 7.840 | +0.297 ms (+4.0%) | 11.208 / 11.624 / 11.895 | 11.700 / 12.075 / 12.428 | +0.451 ms (+3.9%) | 5.109 → 5.062 |
| real-88 | 30.377 / 30.735 / 31.130 | 31.080 / 32.077 / 33.590 | +1.342 ms (+4.4%) | 57.621 / 57.935 / 60.040 | 57.594 / 59.346 / 61.283 | +1.411 ms (+2.4%) | 42.750 → 42.734 |

Physical artifact bytes and logical work are identical across the pair. Initial source and target name the same MCM file; its size is shown on both sides, not claimed as two distinct files.

| Workload | Source / target MCM bytes | RPA bytes | RPX bytes | Request bytes | Logical work | Obligations | Peak live facts |
|---|---:|---:|---:|---:|---:|---:|---:|
| history-64 | 89 / 89 | 6372 | 4132 | 127 | 716 | 4 | 2 |
| history-4096 | 89 / 89 | 414718 | 258148 | 127 | 45068 | 4 | 2 |
| history-65536 | 89 / 89 | 6848205 | 4128868 | 127 | 720908 | 4 | 2 |
| branch-1 | 89 / 89 | 530 | 236 | 127 | 34 | 4 | 1 |
| branch-64 | 89 / 89 | 17900 | 8804 | 127 | 1357 | 4 | 2 |
| branch-1024 | 89 / 89 | 284756 | 139364 | 127 | 21517 | 4 | 2 |
| chain-16 | 3534 / 1796 | 6167 | 6605 | 129 | 1714 | 48 | 16 |
| chain-64 | 41694 / 7316 | 71567 | 87725 | 129 | 23770 | 192 | 64 |
| chain-256 | 609366 / 29708 | 1072523 | 1333805 | 129 | 365434 | 768 | 256 |
| local-1 | 146 / 146 | 367 | 171 | 127 | 29 | 5 | 1 |
| local-1000 | 99830 / 99830 | 178432 | 118053 | 127 | 28001 | 4001 | 1000 |
| local-10000 | 1017830 / 1017830 | 1852432 | 1180053 | 127 | 280001 | 40001 | 10000 |
| bigint-64 | 17143 / 17143 | 21794 | 15165 | 127 | 4611 | 770 | 0 |
| bigint-512 | 31535 / 31535 | 21794 | 15165 | 127 | 4611 | 770 | 0 |
| bigint-4096 | 146671 / 146671 | 21794 | 15165 | 127 | 4611 | 770 | 0 |
| real-33 | 13899228 / 6840780 | 40840280 | 27989684 | 291564 | 11299860 | 575036 | 90000 |
| real-40 | 58423 / 31423 | 563857 | 96420 | 25685 | 36932 | 4948 | 240 |
| real-65 | 32241762 / 27144024 | 91484236 | 57125072 | 9030156 | 22749544 | 2917586 | 52554 |
| real-68 | 4135128 / 2414540 | 7455486 | 4822420 | 829516 | 4448204 | 279140 | 1046 |
| real-71 | 1134477 / 1152951 | 1666672 | 304420 | 154037 | 2829485 | 16390 | 1 |
| real-79 | 1968520 / 1793666 | 5044716 | 3466070 | 688452 | 1942360 | 181792 | 196 |
| real-84 | 25256 / 192 | 2238283 | 400516 | 308 | 111095 | 805 | 838 |
| real-88 | 647130 / 260726 | 8313616 | 5395057 | 36164 | 2125553 | 12906 | 2573 |

### Read/decode and complete internal time

Each cell is old min / median / max → candidate min / median / max, in milliseconds.

| Workload | Read | Model decode | Proof decode | Kernel total |
|---|---:|---:|---:|---:|
| history-64 | 0.032 / 0.035 / 0.042 → 0.032 / 0.034 / 0.066 | 0.010 / 0.012 / 0.013 → 0.012 / 0.012 / 0.030 | 0.022 / 0.025 / 0.026 → 0.023 / 0.025 / 0.026 | 0.088 / 0.096 / 0.104 → 0.091 / 0.094 / 0.148 |
| history-4096 | 0.052 / 0.054 / 0.113 → 0.049 / 0.053 / 0.056 | 0.011 / 0.012 / 0.014 → 0.011 / 0.012 / 0.014 | 0.623 / 0.669 / 0.746 → 0.639 / 0.667 / 0.707 | 1.329 / 1.382 / 1.509 → 1.366 / 1.404 / 1.456 |
| history-65536 | 0.371 / 0.387 / 0.429 → 0.322 / 0.377 / 0.416 | 0.014 / 0.015 / 0.018 → 0.014 / 0.015 / 0.018 | 10.487 / 10.983 / 11.421 → 10.427 / 10.615 / 11.037 | 21.583 / 22.346 / 22.798 → 21.693 / 22.023 / 22.350 |
| branch-1 | 0.034 / 0.038 / 0.054 → 0.031 / 0.040 / 0.074 | 0.012 / 0.012 / 0.013 → 0.011 / 0.012 / 0.013 | 0.010 / 0.012 / 0.014 → 0.011 / 0.012 / 0.015 | 0.065 / 0.073 / 0.086 → 0.063 / 0.075 / 0.107 |
| branch-64 | 0.036 / 0.040 / 0.098 → 0.034 / 0.038 / 0.052 | 0.011 / 0.012 / 0.017 → 0.011 / 0.012 / 0.017 | 0.046 / 0.048 / 0.052 → 0.047 / 0.048 / 0.059 | 0.127 / 0.135 / 0.204 → 0.123 / 0.131 / 0.151 |
| branch-1024 | 0.044 / 0.047 / 0.051 → 0.042 / 0.045 / 0.094 | 0.011 / 0.012 / 0.015 → 0.011 / 0.012 / 0.013 | 0.460 / 0.478 / 0.539 → 0.469 / 0.484 / 0.494 | 0.861 / 0.894 / 0.991 → 0.866 / 0.892 / 0.951 |
| chain-16 | 0.033 / 0.035 / 0.042 → 0.032 / 0.033 / 0.036 | 0.042 / 0.043 / 0.044 → 0.041 / 0.042 / 0.044 | 0.026 / 0.028 / 0.030 → 0.029 / 0.029 / 0.031 | 0.160 / 0.168 / 0.178 → 0.162 / 0.165 / 0.171 |
| chain-64 | 0.045 / 0.047 / 0.054 → 0.045 / 0.048 / 0.055 | 0.196 / 0.200 / 0.230 → 0.198 / 0.202 / 0.219 | 0.267 / 0.278 / 0.308 → 0.272 / 0.277 / 0.304 | 0.988 / 1.017 / 1.085 → 1.026 / 1.045 / 1.099 |
| chain-256 | 0.178 / 0.197 / 0.243 → 0.167 / 0.177 / 0.218 | 2.199 / 2.231 / 2.405 → 2.140 / 2.181 / 2.284 | 3.919 / 4.000 / 4.326 → 3.839 / 3.903 / 4.018 | 13.324 / 13.642 / 14.186 → 13.458 / 13.792 / 14.041 |
| local-1 | 0.034 / 0.035 / 0.053 → 0.031 / 0.035 / 0.039 | 0.016 / 0.016 / 0.018 → 0.015 / 0.016 / 0.017 | 0.008 / 0.009 / 0.009 → 0.009 / 0.010 / 0.011 | 0.067 / 0.072 / 0.091 → 0.065 / 0.070 / 0.079 |
| local-1000 | 0.059 / 0.062 / 0.069 → 0.058 / 0.063 / 0.107 | 0.867 / 0.883 / 0.983 → 0.851 / 0.888 / 0.904 | 0.353 / 0.363 / 0.386 → 0.347 / 0.362 / 0.377 | 2.574 / 2.622 / 2.772 → 2.559 / 2.661 / 2.692 |
| local-10000 | 0.264 / 0.319 / 0.349 → 0.302 / 0.318 / 0.362 | 8.854 / 9.050 / 9.582 → 8.656 / 9.135 / 9.535 | 3.505 / 3.614 / 3.709 → 3.381 / 3.637 / 3.813 | 26.386 / 26.819 / 27.457 → 26.543 / 27.094 / 28.460 |
| bigint-64 | 0.041 / 0.044 / 0.075 → 0.041 / 0.046 / 0.066 | 0.174 / 0.178 / 0.226 → 0.175 / 0.180 / 0.190 | 0.045 / 0.047 / 0.052 → 0.045 / 0.047 / 0.050 | 0.488 / 0.497 / 0.577 → 0.488 / 0.501 / 0.528 |
| bigint-512 | 0.043 / 0.045 / 0.074 → 0.042 / 0.050 / 0.059 | 0.191 / 0.193 / 0.200 → 0.194 / 0.203 / 0.205 | 0.044 / 0.046 / 0.047 → 0.047 / 0.048 / 0.050 | 0.503 / 0.513 / 0.540 → 0.516 / 0.533 / 0.540 |
| bigint-4096 | 0.054 / 0.061 / 0.071 → 0.056 / 0.066 / 0.078 | 0.295 / 0.306 / 0.314 → 0.303 / 0.310 / 0.341 | 0.045 / 0.047 / 0.052 → 0.047 / 0.049 / 0.052 | 0.677 / 0.697 / 0.736 → 0.690 / 0.714 / 0.764 |
| real-33 | 4.422 / 4.576 / 6.934 → 4.315 / 4.543 / 7.128 | 104.783 / 106.214 / 113.265 → 104.225 / 105.308 / 111.389 | 68.257 / 68.850 / 70.168 → 69.622 / 70.706 / 78.623 | 548.426 / 552.629 / 562.403 → 556.887 / 569.826 / 580.972 |
| real-40 | 0.052 / 0.056 / 0.062 → 0.051 / 0.055 / 0.060 | 0.494 / 0.505 / 0.522 → 0.474 / 0.492 / 0.517 | 0.305 / 0.316 / 0.351 → 0.302 / 0.306 / 0.348 | 2.997 / 3.087 / 3.176 → 2.963 / 3.080 / 3.225 |
| real-65 | 11.353 / 11.739 / 32.710 → 11.261 / 11.580 / 36.291 | 313.323 / 323.725 / 399.672 → 315.323 / 323.073 / 349.525 | 156.957 / 161.718 / 245.701 → 160.504 / 163.311 / 193.662 | 2223.752 / 2322.758 / 3180.633 → 2309.716 / 2361.348 / 2457.424 |
| real-68 | 1.070 / 1.110 / 1.201 → 1.078 / 1.133 / 1.277 | 42.976 / 43.367 / 43.714 → 42.432 / 43.261 / 46.104 | 12.338 / 12.574 / 12.986 → 12.307 / 12.724 / 13.707 | 406.183 / 410.702 / 416.699 → 412.784 / 413.745 / 426.878 |
| real-71 | 0.273 / 0.284 / 0.373 → 0.264 / 0.285 / 0.319 | 7.751 / 8.092 / 8.369 → 7.776 / 8.617 / 8.711 | 0.845 / 0.882 / 0.918 → 0.847 / 0.912 / 0.958 | 85.780 / 87.335 / 90.314 → 89.128 / 94.203 / 95.225 |
| real-79 | 0.693 / 0.734 / 0.838 → 0.727 / 0.766 / 0.782 | 20.161 / 20.266 / 20.638 → 20.099 / 20.751 / 22.321 | 9.608 / 9.911 / 10.389 → 9.562 / 9.957 / 10.518 | 122.674 / 124.086 / 124.858 → 127.407 / 132.657 / 136.656 |
| real-84 | 0.063 / 0.070 / 0.077 → 0.064 / 0.066 / 0.079 | 0.120 / 0.126 / 0.128 → 0.128 / 0.131 / 0.138 | 1.829 / 1.899 / 1.937 → 1.939 / 1.978 / 2.033 | 9.172 / 9.444 / 9.809 → 9.641 / 9.819 / 10.090 |
| real-88 | 0.565 / 0.618 / 0.736 → 0.537 / 0.587 / 0.636 | 4.573 / 4.663 / 4.944 → 4.578 / 4.646 / 5.019 | 16.910 / 17.322 / 17.646 → 16.554 / 17.481 / 18.005 | 52.875 / 53.349 / 53.870 → 53.099 / 54.749 / 56.463 |

### Preparation recorded separately

Synthetic generation is one wall-time observation inside each benchmark driver, followed by independent canonical/assembler processes. These stages are outside verification timing and are not repeated preparation distributions. Canonical columns sum the one initial or two extended model conversions; assembly is separate. For actual cases no author, canonicalization or assembly cost was remeasured: receipt links mean unmeasured here, never zero cost.

| Workload / version | Generate ms | Canonical process / internal / parse ms | Assemble process / internal ms | Actual preparation receipt |
|---|---:|---:|---:|---|
| history-64 / old | 0.960 | 4.316 / 0.194 / 0.042 | 1.962 / 0.164 | not applicable |
| history-64 / new | 0.494 | 4.614 / 0.374 / 0.175 | 2.258 / 0.286 | not applicable |
| history-4096 / old | 7.287 | 4.112 / 0.185 / 0.035 | 5.167 / 2.784 | not applicable |
| history-4096 / new | 6.886 | 4.082 / 0.171 / 0.034 | 4.564 / 2.558 | not applicable |
| history-65536 / old | 158.406 | 8.489 / 0.693 / 0.041 | 46.350 / 40.953 | not applicable |
| history-65536 / new | 149.887 | 5.683 / 0.202 / 0.037 | 45.923 / 41.316 | not applicable |
| branch-1 / old | 0.338 | 4.481 / 0.187 / 0.035 | 1.946 / 0.104 | not applicable |
| branch-1 / new | 0.267 | 4.206 / 0.193 / 0.035 | 1.952 / 0.102 | not applicable |
| branch-64 / old | 0.761 | 4.142 / 0.186 / 0.033 | 2.306 / 0.467 | not applicable |
| branch-64 / new | 0.784 | 4.591 / 0.190 / 0.037 | 2.307 / 0.252 | not applicable |
| branch-1024 / old | 5.608 | 4.559 / 0.199 / 0.036 | 3.557 / 1.523 | not applicable |
| branch-1024 / new | 5.718 | 4.683 / 0.223 / 0.038 | 3.587 / 1.585 | not applicable |
| chain-16 / old | 0.522 | 4.287 / 0.301 / 0.129 | 2.025 / 0.174 | not applicable |
| chain-16 / new | 0.487 | 3.927 / 0.254 / 0.126 | 2.122 / 0.307 | not applicable |
| chain-64 / old | 2.622 | 5.129 / 1.230 / 0.576 | 3.145 / 1.171 | not applicable |
| chain-64 / new | 2.102 | 4.705 / 1.032 / 0.570 | 2.914 / 0.935 | not applicable |
| chain-256 / old | 33.456 | 13.908 / 8.741 / 6.047 | 14.703 / 12.081 | not applicable |
| chain-256 / new | 32.554 | 13.738 / 8.394 / 6.118 | 14.439 / 11.812 | not applicable |
| local-1 / old | 0.698 | 4.505 / 0.361 / 0.037 | 2.366 / 0.293 | not applicable |
| local-1 / new | 0.277 | 4.276 / 0.194 / 0.037 | 2.144 / 0.084 | not applicable |
| local-1000 / old | 5.322 | 7.212 / 2.937 / 1.828 | 3.507 / 1.330 | not applicable |
| local-1000 / new | 4.424 | 6.767 / 2.830 / 1.776 | 3.340 / 1.229 | not applicable |
| local-10000 / old | 48.793 | 32.277 / 25.732 / 18.561 | 13.369 / 10.357 | not applicable |
| local-10000 / new | 47.879 | 31.750 / 25.134 / 18.564 | 14.160 / 10.911 | not applicable |
| bigint-64 / old | 3.325 | 5.589 / 1.098 / 0.445 | 2.385 / 0.264 | not applicable |
| bigint-64 / new | 0.962 | 5.564 / 0.799 / 0.472 | 2.383 / 0.283 | not applicable |
| bigint-512 / old | 1.663 | 5.727 / 1.458 / 0.781 | 2.124 / 0.257 | not applicable |
| bigint-512 / new | 1.036 | 5.602 / 1.106 / 0.749 | 2.300 / 0.267 | not applicable |
| bigint-4096 / old | 8.048 | 8.006 / 3.747 / 3.107 | 2.329 / 0.273 | not applicable |
| bigint-4096 / new | 7.022 | 8.715 / 3.723 / 3.160 | 2.995 / 0.343 | not applicable |
| real-33 / old | unmeasured | unmeasured | unmeasured | `bench/results/v10-regression-receipts/real-33.json`; SHA-256 `cc2daffb96d65587350dfb7b3cd36715f6ad0f4903d26c8acdb936a5a209c2ac` |
| real-33 / new | unmeasured | unmeasured | unmeasured | `bench/results/v10-regression-receipts/real-33.json`; SHA-256 `cc2daffb96d65587350dfb7b3cd36715f6ad0f4903d26c8acdb936a5a209c2ac` |
| real-40 / old | unmeasured | unmeasured | unmeasured | `bench/results/v10-regression-receipts/real-40.json`; SHA-256 `2f667e822092eed0625d8f440917f627435bdd3d17417f241ca985a17fd18598` |
| real-40 / new | unmeasured | unmeasured | unmeasured | `bench/results/v10-regression-receipts/real-40.json`; SHA-256 `2f667e822092eed0625d8f440917f627435bdd3d17417f241ca985a17fd18598` |
| real-65 / old | unmeasured | unmeasured | unmeasured | `bench/results/v10-regression-receipts/real-65.json`; SHA-256 `f8b4ad3290de55963d70aa88fbde0efb00741d95fab2e1393cb0502dc593d34b` |
| real-65 / new | unmeasured | unmeasured | unmeasured | `bench/results/v10-regression-receipts/real-65.json`; SHA-256 `f8b4ad3290de55963d70aa88fbde0efb00741d95fab2e1393cb0502dc593d34b` |
| real-68 / old | unmeasured | unmeasured | unmeasured | `bench/results/v10-regression-receipts/real-68.json`; SHA-256 `47811b0dd8623be79e71106bcd135c231a1c048f4ab3a43526fbfa0f0de90909` |
| real-68 / new | unmeasured | unmeasured | unmeasured | `bench/results/v10-regression-receipts/real-68.json`; SHA-256 `47811b0dd8623be79e71106bcd135c231a1c048f4ab3a43526fbfa0f0de90909` |
| real-71 / old | unmeasured | unmeasured | unmeasured | `bench/results/v10-regression-receipts/real-71.json`; SHA-256 `1b031ce937fdb78e76d69e60539dd9a9c008f4688ec22fcd25a2e93d4e38a50c` |
| real-71 / new | unmeasured | unmeasured | unmeasured | `bench/results/v10-regression-receipts/real-71.json`; SHA-256 `1b031ce937fdb78e76d69e60539dd9a9c008f4688ec22fcd25a2e93d4e38a50c` |
| real-79 / old | unmeasured | unmeasured | unmeasured | `bench/results/v10-regression-receipts/real-79.json`; SHA-256 `cb2890efa099a10764ce6f3d87e07f3cf93f6eedda1ff1fe171b8479b2bfd34e` |
| real-79 / new | unmeasured | unmeasured | unmeasured | `bench/results/v10-regression-receipts/real-79.json`; SHA-256 `cb2890efa099a10764ce6f3d87e07f3cf93f6eedda1ff1fe171b8479b2bfd34e` |
| real-84 / old | unmeasured | unmeasured | unmeasured | `bench/results/v10-regression-receipts/real-84.json`; SHA-256 `f406e8d3b74994d2ba1ebe58c9c749ff41e7b7092c77661cbdceaee92af1f90f` |
| real-84 / new | unmeasured | unmeasured | unmeasured | `bench/results/v10-regression-receipts/real-84.json`; SHA-256 `f406e8d3b74994d2ba1ebe58c9c749ff41e7b7092c77661cbdceaee92af1f90f` |
| real-88 / old | unmeasured | unmeasured | unmeasured | `bench/results/v10-regression-receipts/real-88.json`; SHA-256 `0bba0b817faa704ac054ded3cdc05a985995b55157094245475cc53432e3f677` |
| real-88 / new | unmeasured | unmeasured | unmeasured | `bench/results/v10-regression-receipts/real-88.json`; SHA-256 `0bba0b817faa704ac054ded3cdc05a985995b55157094245475cc53432e3f677` |

## Interpretation and limits

All 712 measured verification/RSS processes passed on all 31 fixed paired workloads. No failed sample was discarded, no statistic key was normalized away, and no unsupported new task received an old/new speed ratio.

Candidate median execution is higher in 19 workloads; candidate median process time is higher in 23. Every such regression remains in the tables. These counts describe observations, not statistical significance.

Execution regressions: `identity-1000` (+0.008 ms), `dense-1000` (+0.025 ms), `dense-5000` (+0.082 ms), `rational-1000` (+0.180 ms), `history-4096` (+0.027 ms), `chain-16` (+0.001 ms), `chain-64` (+0.017 ms), `chain-256` (+0.287 ms), `local-10000` (+0.339 ms), `bigint-512` (+0.005 ms), `bigint-4096` (+0.007 ms), `real-33` (+14.138 ms), `real-40` (+0.022 ms), `real-65` (+71.913 ms), `real-68` (+3.926 ms), `real-71` (+6.435 ms), `real-79` (+7.715 ms), `real-84` (+0.297 ms), `real-88` (+1.342 ms).

Process regressions: `identity-10000` (+0.460 ms), `dense-1000` (+0.200 ms), `dense-5000` (+0.271 ms), `rational-10` (+0.126 ms), `rational-1000` (+0.132 ms), `history-64` (+0.002 ms), `history-4096` (+0.009 ms), `branch-1` (+0.001 ms), `chain-64` (+0.150 ms), `chain-256` (+0.253 ms), `local-1` (+0.056 ms), `local-1000` (+0.125 ms), `local-10000` (+0.274 ms), `bigint-64` (+0.015 ms), `bigint-512` (+0.046 ms), `bigint-4096` (+0.279 ms), `real-33` (+15.967 ms), `real-65` (+38.233 ms), `real-68` (+2.950 ms), `real-71` (+7.182 ms), `real-79` (+8.664 ms), `real-84` (+0.451 ms), `real-88` (+1.411 ms).

This is complete old-workload performance evidence for the fixed candidate, including startup, reads, decode, verification, memory and separately recorded preparation. It does not establish mathematical correctness, certify the entire corpus, freeze the working protocol, or measure the cost of newly supported contracts. Source changes and benchmark preparation are not hidden by reporting only inner verification time.

Recreate this report without running any workload: `python3 tools/report_v10_regression.py`. A missing, failed or inconsistent input is a report-validation error; raw evidence is never rewritten.
