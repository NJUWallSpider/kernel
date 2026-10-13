# V8 signed-decomposition baseline and generalizations

All10 fixed workloads completed nine fresh-process timings and three separate RSS measurements: **120/120 VERIFIED**. All physical artifacts match the earlier diagnostic run byte-for-byte. This establishes a baseline for the new rule, not an optimization speedup. No failed sample was discarded.

The fixed matrix combines three sizes (1,16,512) and capacities0,2/7,212 with renamed and permuted input/output variables and rows, affine flow shifts/scales, complemented binary activations, rational costs and nonzero objective constants. Full mapped domains, rows, objective and all flow/activation observations are checked. The tenth workload is the unchanged complete actual27 certificate. These nine serialized variants add generalization evidence to72 independent Fraction cases and six joint batches.

All three case workers held computation during the measurement. The78preparer was paused and resumed without losing progress; its receipt separately discloses that pause. The root checkpoint had finished before timing began. OS and unrelated app activity remain uncontrolled. Warm files, no cache flushing, fresh process for every sample. Source is the frozen `audit/checkpoints/v8-source`, locked release build, rustc1.96.0, AppleM5/10cores/16GiB, macOS26.6.2. Raw files retain exact hardware, source, lock, binary and artifact hashes. Diagnostic run timings overlapped other work and are excluded.

```sh
python3 tools/benchmark_signed.py --kernel target/validation-checkpoint-v8/release/rpx --source-root audit/checkpoints/v8-source --label signed-v8-quiescent
python3 tools/report_signed.py
```

Use a new label to repeat; existing evidence is never overwritten. Times below are min/median/max in milliseconds. Process includes startup, read/decode/check, verification, output and shutdown; execution is the CLI verification phase. RSS is median peak resident size from three separate processes.

| Workload | RPA/RPX bytes | Execute ms | Process ms | RSS MiB |
|---|---:|---:|---:|---:|
| signed-1-c0-s811 | 1035/670 | 0.026/0.029/0.075 | 1.991/2.105/2.228 | 2.219 |
| signed-16-c0-s811 | 11752/9067 | 0.197/0.206/0.220 | 2.369/2.413/2.538 | 2.797 |
| signed-512-c0-s811 | 390910/286685 | 4.878/5.032/5.163 | 10.518/10.769/11.300 | 10.906 |
| signed-1-c2_7-s812 | 1037/671 | 0.026/0.027/0.031 | 1.824/1.930/2.163 | 2.219 |
| signed-16-c2_7-s812 | 11786/9083 | 0.235/0.245/0.254 | 2.175/2.278/2.407 | 2.766 |
| signed-512-c2_7-s812 | 391952/287197 | 6.187/6.421/13.047 | 12.592/12.877/26.435 | 11.062 |
| signed-1-c212-s813 | 1037/671 | 0.026/0.028/0.031 | 1.882/2.036/2.450 | 2.219 |
| signed-16-c212-s813 | 11782/9083 | 0.226/0.230/0.247 | 2.297/2.400/2.545 | 2.812 |
| signed-512-c212-s813 | 391958/287197 | 6.002/6.472/7.070 | 13.190/13.485/14.360 | 11.188 |
| test27 | 3181346/1884109 | 18.160/19.072/59.215 | 33.064/34.853/75.946 | 30.297 |

| Workload | Read/model/proof decode ms medians | Obligations | Linear/substitution terms | Work | Generated vars/rows |
|---|---:|---:|---:|---:|---:|
| signed-1-c0-s811 | 0.036/0.020/0.021 | 13 | 3/8 | 633 | 4/4 |
| signed-16-c0-s811 | 0.042/0.069/0.092 | 193 | 48/128 | 9368 | 64/64 |
| signed-512-c0-s811 | 0.088/1.357/2.036 | 6145 | 1536/4096 | 303818 | 2048/2048 |
| signed-1-c2_7-s812 | 0.036/0.019/0.018 | 13 | 3/10 | 661 | 4/4 |
| signed-16-c2_7-s812 | 0.037/0.081/0.091 | 193 | 48/160 | 9756 | 64/64 |
| signed-512-c2_7-s812 | 0.101/1.811/2.118 | 6145 | 1536/5120 | 316110 | 2048/2048 |
| signed-1-c212-s813 | 0.039/0.020/0.019 | 13 | 3/10 | 661 | 4/4 |
| signed-16-c212-s813 | 0.039/0.081/0.092 | 193 | 48/160 | 9756 | 64/64 |
| signed-512-c212-s813 | 0.123/1.846/2.245 | 6145 | 1536/5120 | 316110 | 2048/2048 |
| test27 | 0.373/2.791/7.860 | 13721 | 37238/18996 | 1173116 | 3800/6080 |

Generation and assembly are separate single observations, not repeated verification measurements. Synthetic MCM is written directly by an independent exact Python encoder; no synthetic MPS canonicalization was performed or charged as zero. Every model is still loaded, decoded and validated by the trusted Rust path in full verification. Actual27 preparation includes its actual MPS canonicalization and is disclosed from its preserved historical receipt, which is not a controlled comparison.

| Workload | Generate seconds | Assembly process ms |
|---|---:|---:|
| signed-1-c0-s811 | 0.000823 | 2.614 |
| signed-16-c0-s811 | 0.003217 | 2.485 |
| signed-512-c0-s811 | 0.529469 | 6.265 |
| signed-1-c2_7-s812 | 0.000654 | 2.103 |
| signed-16-c2_7-s812 | 0.003114 | 2.248 |
| signed-512-c2_7-s812 | 0.516966 | 6.217 |
| signed-1-c212-s813 | 0.000660 | 2.139 |
| signed-16-c212-s813 | 0.003193 | 2.617 |
| signed-512-c212-s813 | 0.536688 | 7.418 |

Actual27 historical RPA preparation: 0.983s; two canonicalizer internal totals 7.600ms; assembler internal total 19.960ms. Original receipt and executable identity are retained.

Metered work counts sparse operations rather than CPU instructions or exact bigint complexity. Generated rows/variables are logical model size, not peak physical memory. SignedLift avoids multiplying whole-output sign branches across independent items; it does not claim compactness or linear complexity for arbitrary reformulations. Eager model/proof decoding and exact arithmetic remain costs. No changes to arithmetic, bounds, obligations or resource ceilings were made to improve this baseline.
