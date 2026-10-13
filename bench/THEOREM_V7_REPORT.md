# V7 theorem and actual-certificate baseline

All 26 fixed workloads completed nine fresh-process timing repetitions and three separately timed RSS runs: **312/312 VERIFIED**. Every artifact hash agrees with the earlier diagnostic fixture check. No failed sample was discarded. This establishes a baseline for the newly exercised rules; it is not an optimization speedup claim.

## Conditions and reproduction

The matrix in `theorem_workloads_v7.json` was fixed before additional arithmetic or representation changes. The executable is a fresh locked release build of `audit/checkpoints/v7-source`: Apple M5, 10 CPU cores, 16 GiB RAM, macOS 26.6.2, aarch64, rustc 1.96.0. All three case workers paused computation for the full benchmark and subsequent profile. OS and unrelated application activity were not controlled. Files were warm after preparation, caches were not flushed, and each observation used a new process. Raw results retain source, lockfile, executable and input hashes. Diagnostic timings from `theorem-v7-fixture-check` overlapped other work and are excluded.

```sh
python3 tools/benchmark_theorems.py --kernel target/validation-checkpoint-v7/release/rpx --source-root audit/checkpoints/v7-source --label theorem-v7-quiescent
python3 tools/report_theorems.py
```

The runner refuses an existing label; use a new label for a fresh run. `results/theorem-v7-quiescent/raw.json` preserves every command, result and distribution; `receipts/` preserves the eight original preparation receipts. Times below are milliseconds, shown as min/median/max. Process time includes process startup, file reads, model/proof decoding and checks, verification, serialization and shutdown. Execution is the CLI verification phase. RSS is the median of three separate peak resident-set measurements, in MiB; it includes eagerly loaded models and certificates.

## Time and physical size

| Workload | RPA bytes | RPX bytes | Execute ms min/median/max | Process ms min/median/max | RSS MiB |
|---|---:|---:|---:|---:|---:|
| menu-1-k0 | 812 | 470 | 0.024/0.026/0.103 | 1.963/2.086/2.251 | 2.203 |
| menu-64-k0 | 36157 | 25166 | 0.523/0.541/0.579 | 2.900/3.073/3.661 | 3.188 |
| menu-512-k0 | 295207 | 200782 | 3.760/3.961/4.364 | 8.138/8.563/8.986 | 7.797 |
| menu-1-k2 | 989 | 652 | 0.031/0.034/0.039 | 2.104/2.241/2.369 | 2.203 |
| menu-64-k2 | 48657 | 36814 | 0.855/0.864/0.884 | 3.132/3.246/3.399 | 3.391 |
| menu-512-k2 | 399965 | 293966 | 6.420/6.495/6.638 | 11.326/11.585/12.224 | 9.438 |
| menu-1-k12 | 1904 | 1562 | 0.060/0.063/0.070 | 2.029/2.089/2.205 | 2.297 |
| menu-64-k12 | 112244 | 95054 | 2.560/2.599/2.629 | 5.666/5.848/5.918 | 4.688 |
| menu-512-k12 | 934207 | 759886 | 20.177/20.705/21.063 | 30.426/30.924/32.026 | 17.875 |
| interval-1 | 803 | 459 | 0.021/0.022/0.026 | 1.914/1.974/2.231 | 2.203 |
| interval-128 | 69841 | 49354 | 0.879/0.903/0.922 | 3.024/3.145/3.239 | 3.594 |
| interval-1024 | 571841 | 394314 | 6.757/6.822/7.020 | 11.237/11.394/11.666 | 10.953 |
| flow-1 | 650 | 373 | 0.017/0.018/0.030 | 1.869/1.943/2.052 | 2.203 |
| flow-16 | 5777 | 4618 | 0.090/0.095/0.102 | 1.937/2.124/2.255 | 2.453 |
| flow-128 | 45152 | 36314 | 0.585/0.601/0.631 | 2.726/2.843/2.914 | 3.344 |
| injectivity-1 | 642 | 238 | 0.016/0.017/0.022 | 1.818/1.894/2.049 | 2.156 |
| injectivity-64 | 11478 | 7924 | 0.232/0.240/0.252 | 2.076/2.186/2.315 | 2.484 |
| injectivity-512 | 91866 | 62580 | 1.754/1.776/1.793 | 3.942/4.057/4.295 | 3.641 |
| test18 | 39845824 | 30500427 | 895.986/908.194/920.637 | 1013.279/1025.301/1039.722 | 193.781 |
| test19 | 749360 | 543175 | 32.487/32.818/33.444 | 40.089/40.410/40.941 | 12.031 |
| test23 | 16794987 | 11850424 | 1064.521/1093.561/1110.411 | 1188.011/1216.573/1239.671 | 133.297 |
| test28 | 3049675 | 459185 | 22.878/23.034/23.126 | 29.195/29.335/29.683 | 13.734 |
| test38 | 27251726 | 16191034 | 508.289/514.221/527.561 | 599.496/607.743/628.997 | 159.266 |
| test57 | 84716208 | 59995996 | 4825.391/4932.676/5083.358 | 5420.049/5507.545/5694.299 | 727.562 |
| test59 | 129299645 | 91698522 | 4190.202/4247.703/4311.367 | 4673.843/4734.962/4800.728 | 663.812 |
| test60 | 122979323 | 90516456 | 4771.691/4846.733/4903.379 | 5251.952/5327.660/5392.470 | 602.453 |

## Decode, sparse work and generated domains

These are medians of the same nine runs, not additional timing samples. Logical obligations and branches, visited linear/substitution coefficient terms, and metered work are distinct from physical bytes. Generated variables/rows are cumulative across extensions and paired-domain checks; they do not measure peak live memory. Work is an explicit sparse-operation budget rather than CPU instructions or bigint bit complexity.

| Workload | Read ms | Model decode ms | Proof decode ms | Obligations | Branches | Linear/substitution terms | Work | Generated vars/rows |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| menu-1-k0 | 0.040 | 0.014 | 0.016 | 7 | 0 | 3/2 | 309 | 1/2 |
| menu-64-k0 | 0.052 | 0.091 | 0.190 | 385 | 0 | 192/128 | 17845 | 64/128 |
| menu-512-k0 | 0.093 | 0.549 | 1.267 | 3073 | 0 | 1536/1024 | 145053 | 512/1024 |
| menu-1-k2 | 0.039 | 0.018 | 0.018 | 13 | 0 | 5/8 | 447 | 3/2 |
| menu-64-k2 | 0.046 | 0.133 | 0.243 | 769 | 0 | 320/512 | 26677 | 192/128 |
| menu-512-k2 | 0.086 | 0.902 | 1.781 | 6145 | 0 | 2560/4096 | 215709 | 1536/1024 |
| menu-1-k12 | 0.035 | 0.020 | 0.028 | 43 | 0 | 15/38 | 1117 | 13/2 |
| menu-64-k12 | 0.054 | 0.289 | 0.687 | 2689 | 0 | 960/2432 | 69557 | 832/128 |
| menu-512-k12 | 0.155 | 2.136 | 5.123 | 21505 | 0 | 7680/19456 | 558749 | 6656/1024 |
| interval-1 | 0.034 | 0.012 | 0.013 | 4 | 0 | 6/1 | 237 | 1/2 |
| interval-128 | 0.042 | 0.058 | 0.259 | 385 | 0 | 768/128 | 25929 | 128/256 |
| interval-1024 | 0.079 | 0.341 | 1.874 | 3073 | 0 | 6144/1024 | 208761 | 1024/2048 |
| flow-1 | 0.033 | 0.010 | 0.015 | 4 | 0 | 0/2 | 274 | 2/3 |
| flow-16 | 0.034 | 0.015 | 0.051 | 49 | 0 | 0/32 | 3811 | 32/48 |
| flow-128 | 0.042 | 0.049 | 0.245 | 385 | 0 | 0/256 | 30411 | 256/384 |
| injectivity-1 | 0.033 | 0.011 | 0.009 | 10 | 0 | 0/1 | 246 | 2/1 |
| injectivity-64 | 0.037 | 0.036 | 0.030 | 514 | 0 | 0/64 | 11109 | 128/64 |
| injectivity-512 | 0.044 | 0.178 | 0.162 | 4098 | 0 | 0/512 | 90261 | 1024/512 |
| test18 | 2.682 | 9.555 | 93.383 | 96720 | 18444 | 1848760/172177 | 8266292 | 0/0 |
| test19 | 0.111 | 2.951 | 1.980 | 19331 | 210 | 10162/23830 | 353271 | 0/0 |
| test23 | 1.406 | 45.044 | 69.402 | 181296 | 0 | 459210/162926 | 4668424 | 4934/19736 |
| test28 | 0.104 | 2.244 | 1.522 | 5666 | 0 | 25620/24512 | 405945 | 2350/1593 |
| test38 | 1.728 | 24.684 | 55.459 | 59669 | 14556 | 631452/120700 | 4680150 | 0/0 |
| test57 | 10.212 | 380.121 | 163.404 | 1956604 | 0 | 2266240/5904148 | 35551444 | 0/0 |
| test59 | 8.664 | 44.923 | 389.037 | 160289 | 78835 | 6830737/1306812 | 38506669 | 47848/13169 |
| test60 | 8.363 | 38.446 | 402.667 | 112210 | 67750 | 8177938/1181655 | 39126580 | 40830/6450 |

## Separate preparation costs

Synthetic construction, canonicalization and assembly were measured once each in the same preparation run. They are neither repeated distributions nor part of verification latency. The Python generator is untrusted; its output is checked by the same complete model-bound verifier.

| Synthetic workload | Generate RPA/models ms | Two canonical processes ms | Assembly process ms |
|---|---:|---:|---:|
| menu-1-k0 | 0.689 | 4.958 | 2.232 |
| menu-64-k0 | 2.188 | 5.399 | 3.023 |
| menu-512-k0 | 10.009 | 8.179 | 5.045 |
| menu-1-k2 | 0.350 | 4.918 | 2.120 |
| menu-64-k2 | 4.957 | 11.293 | 3.339 |
| menu-512-k2 | 11.325 | 8.460 | 5.502 |
| menu-1-k12 | 4.027 | 4.089 | 2.005 |
| menu-64-k12 | 4.090 | 5.992 | 3.500 |
| menu-512-k12 | 28.111 | 14.675 | 10.751 |
| interval-1 | 0.352 | 4.204 | 1.934 |
| interval-128 | 2.081 | 4.531 | 2.730 |
| interval-1024 | 14.577 | 6.427 | 6.662 |
| flow-1 | 0.318 | 4.090 | 1.908 |
| flow-16 | 0.446 | 4.052 | 1.934 |
| flow-128 | 1.588 | 4.520 | 2.755 |
| injectivity-1 | 0.450 | 3.880 | 1.935 |
| injectivity-64 | 0.575 | 4.058 | 1.889 |
| injectivity-512 | 2.103 | 5.015 | 2.868 |

The actual-case values below are historical single preparation observations, copied from bound receipts. They may have different build modes and concurrent preparation activity; **do not compare them as controlled performance results**. They disclose work done before verification. Receipt generation time excludes the subsequent canonical/assembly/verify commands; canonical and assembly are the CLI internal totals, excluding process startup. Each receipt retains its exact executable path/hash. Case19 used the preserved original-scope executable; cases23/28 used debug binaries. The newer release values are still single observations.

| Actual workload | RPA generation seconds | Two canonical totals ms | Assembly total ms |
|---|---:|---:|---:|
| test18 | 15.199 | 42.899 | 386.271 |
| test19 | 0.557 | 234.407 | 82.423 |
| test23 | 7.185 | 2322.429 | 2820.082 |
| test28 | 0.440 | 141.223 | 69.591 |
| test38 | 10.805 | 86.076 | 226.669 |
| test57 | 61.629 | 1416.226 | 587.074 |
| test59 | 58.806 | 158.848 | 1063.974 |
| test60 | 52.653 | 136.324 | 1142.893 |

## Interpretation and remaining costs

Menu scaling checks K=0,2,12 and 1,64,512 independent menus. Every optional-menu activation/index premise, output coordinate and observation is proved; K=0 retains the zero-index equality. Interval scaling checks 1,128,1024 simultaneous equality intervals. Flow scaling uses 1,16,128 common-source groups, each containing two zero-demand commodities on a loop: the full observation preserves arbitrary nonnegative circulation. Paired-domain scaling proves complete identity bijections on 1,64,512 binary coordinates. These selected structures expose checker scaling; they do not establish linear cost for arbitrary real proofs.

The real cases retain their full original caller contracts, including fiber strictness (18/19), independent intervals (23), common-source flow (28), shared switch aliases (38), integer/LP inverse maps (57), and integer bijection plus LP projection (59/60). Cases59/60 still contain large scalar injectivity proofs: 78,835/67,750 branches and roughly 91.7/90.5 MB RPX. Their resident-set costs remain substantial. Shared fact scopes reduce branch state copying but do not remove eager decoding, complete paired models or the physical proof tree. Further improvements must retain every obligation and actual model binding.

## External sampling of exact arithmetic

`profiles/v7-test57-quiescent/run.json` records a successful diagnostic OS sample of the same executable and test57 inputs. The verifier independently returned VERIFIED. `sample.txt` retains the complete stacks. The sampler observed only our child process, starting 0.8 seconds after launch, sampling for two seconds at a requested 1 ms interval. The resulting 1,519 main-thread observations cover a portion of execution, not the complete run; they exclude most initial decoding. Sampling perturbs execution and its elapsed time is not used in the benchmark distributions.

```sh
python3 tools/profile_verifier.py --kernel target/validation-checkpoint-v7/release/rpx --case 57 --label v7-test57-quiescent
```

Summing inclusive call-tree entries gives 829 observations under `Context::substitute`, 974 under `Accumulator::add`, 383 under `Context::steps`, 232 under `Context::get`, 381 under rational validation, and 168 under expression scaling. These sets overlap; they must not be added or reported as disjoint CPU percentages. Inlining also means an absent symbol does not imply zero cost. Exclusive top-of-stack examples include bigint right shift (198), gcd (151), trailing-zero counting (122), signed division (114), rational multiplication (35), and accumulator code (32). This supports investigating repeated rational multiplication/reduction and validation before introducing a new number representation. It does not justify weakening canonical-rational checks, using approximate arithmetic, or claiming state maintenance is free.

The baseline retains full source and unchanged certificate bytes. Any candidate arithmetic shortcut must be tested against an independent exact oracle, preserve intermediate resource checks, pass existing semantic/byte attacks and then rerun fixed workloads with the same mathematical requests. No such optimization is included in this baseline.
