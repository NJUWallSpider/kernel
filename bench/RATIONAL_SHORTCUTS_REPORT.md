# Exact rational shortcut comparison

The fixed matrices test the same complete mathematical requests and exact certificate bytes before and after the isolated arithmetic changes. All mathematical work counters must agree. The optimization changes no proof rule, rational domain, wire encoding or accepted mathematical relation. It keeps arbitrary-precision arithmetic and canonical-rational validation.

## Scope and conditions

The baseline is the frozen V7 source and its clean release executable. The candidate is `bench/rational-shortcuts-prototype`, which changes only denominator-one canonicality checks, multiplication by ±1 in expression scaling and sparse accumulation, and zero-plus-value handling. All intermediate product/result checks remain. The source diff and independent review are retained with the prototype. Its 182 core tests include 1,228 Python Fraction/gcd oracle vectors.

Both matrices were fixed before this optimization. Apple M5, 10 cores, 16 GiB RAM, macOS 26.6.2, rustc 1.96.0, locked release builds. All case workers paused computation during measurements. Each workload has nine fresh-process timing runs and three separate RSS observations; files are warm, caches are not flushed, unrelated OS/application activity is not controlled. The original theorem baseline was completed in an earlier isolated window on this same host; the candidate theorem and both extended runs share the later window. Runs are sequential, not randomized/interleaved, so small differences can include drift. All observations and outliers remain in the raw distributions.

Times are milliseconds. Execute is the internal complete verification phase; process includes startup, file reads, model/proof decoding, verification and shutdown. RSS is median peak resident set in MiB. A negative percentage means lower candidate latency, not a claim about every possible certificate.

## Reproduction

```sh
python3 tools/prepare_rational_shortcuts_experiment.py
python3 tools/benchmark_theorems.py --kernel target/validation-checkpoint-v7/release/rpx --source-root audit/checkpoints/v7-source --label theorem-v7-quiescent
python3 tools/benchmark_theorems.py --kernel bench/rational-shortcuts-prototype/target/release/rpx --source-root bench/rational-shortcuts-prototype --label rational-theorems-v7-quiescent-after
python3 tools/benchmark_extended.py --kernel target/validation-checkpoint-v7/release/rpx --source-root audit/checkpoints/v7-source --label rational-extended-v7-quiescent-before
python3 tools/benchmark_extended.py --kernel bench/rational-shortcuts-prototype/target/release/rpx --source-root bench/rational-shortcuts-prototype --label rational-extended-v7-quiescent-after
python3 tools/report_rational_shortcuts.py
```

The prototype and run scripts refuse to overwrite evidence; use fresh destinations/labels for a new experiment. See `RATIONAL_SHORTCUTS_PROTOTYPE.md` for the exact prototype preparation command if its generator interface changes. Raw per-sample results retain source, executable, lockfile, model, proof and request hashes.

## Theorem and actual certificates

| Workload | Execute before min/median/max | Execute after min/median/max | Median change | Process before → after median | RSS before → after MiB |
|---|---:|---:|---:|---:|---:|
| menu-1-k0 | 0.024/0.026/0.103 | 0.016/0.018/0.089 | -30.8% | 2.086 → 1.795 | 2.203 → 2.219 |
| menu-64-k0 | 0.523/0.541/0.579 | 0.236/0.247/0.269 | -54.3% | 3.073 → 2.687 | 3.188 → 3.188 |
| menu-512-k0 | 3.760/3.961/4.364 | 1.576/1.613/1.662 | -59.3% | 8.563 → 5.494 | 7.797 → 7.812 |
| menu-1-k2 | 0.031/0.034/0.039 | 0.018/0.020/0.026 | -41.2% | 2.241 → 1.910 | 2.203 → 2.219 |
| menu-64-k2 | 0.855/0.864/0.884 | 0.327/0.337/0.395 | -61.0% | 3.246 → 2.534 | 3.391 → 3.406 |
| menu-512-k2 | 6.420/6.495/6.638 | 2.438/2.464/2.507 | -62.1% | 11.585 → 7.033 | 9.438 → 9.422 |
| menu-1-k12 | 0.060/0.063/0.070 | 0.033/0.034/0.040 | -46.0% | 2.089 → 1.866 | 2.297 → 2.328 |
| menu-64-k12 | 2.560/2.599/2.629 | 0.935/0.954/0.976 | -63.3% | 5.848 → 3.712 | 4.688 → 4.625 |
| menu-512-k12 | 20.177/20.705/21.063 | 7.180/7.539/7.775 | -63.6% | 30.924 → 16.710 | 17.875 → 17.875 |
| interval-1 | 0.021/0.022/0.026 | 0.015/0.016/0.020 | -27.3% | 1.974 → 1.887 | 2.203 → 2.203 |
| interval-128 | 0.879/0.903/0.922 | 0.306/0.315/0.329 | -65.1% | 3.145 → 2.553 | 3.594 → 3.578 |
| interval-1024 | 6.757/6.822/7.020 | 2.272/2.330/2.428 | -65.8% | 11.394 → 6.738 | 10.953 → 10.938 |
| flow-1 | 0.017/0.018/0.030 | 0.015/0.016/0.030 | -11.1% | 1.943 → 1.945 | 2.203 → 2.219 |
| flow-16 | 0.090/0.095/0.102 | 0.047/0.051/0.053 | -46.3% | 2.124 → 2.022 | 2.453 → 2.453 |
| flow-128 | 0.585/0.601/0.631 | 0.250/0.255/0.271 | -57.6% | 2.843 → 2.559 | 3.344 → 3.328 |
| injectivity-1 | 0.016/0.017/0.022 | 0.015/0.016/0.023 | -5.9% | 1.894 → 1.902 | 2.156 → 2.172 |
| injectivity-64 | 0.232/0.240/0.252 | 0.115/0.120/0.127 | -50.0% | 2.186 → 2.391 | 2.484 → 2.469 |
| injectivity-512 | 1.754/1.776/1.793 | 0.733/0.746/0.754 | -58.0% | 4.057 → 3.428 | 3.641 → 3.641 |
| test18 | 895.986/908.194/920.637 | 213.872/217.168/235.467 | -76.1% | 1025.301 → 333.572 | 193.781 → 193.812 |
| test19 | 32.487/32.818/33.444 | 14.609/15.107/16.047 | -54.0% | 40.410 → 22.104 | 12.031 → 12.078 |
| test23 | 1064.521/1093.561/1110.411 | 646.848/664.304/837.313 | -39.3% | 1216.573 → 783.359 | 133.297 → 133.562 |
| test28 | 22.878/23.034/23.126 | 6.251/6.417/6.596 | -72.1% | 29.335 → 12.091 | 13.734 → 13.781 |
| test38 | 508.289/514.221/527.561 | 196.197/200.721/204.611 | -61.0% | 607.743 → 290.108 | 159.266 → 159.281 |
| test57 | 4825.391/4932.676/5083.358 | 2189.395/2219.925/2267.087 | -55.0% | 5507.545 → 2766.383 | 727.562 → 727.750 |
| test59 | 4190.202/4247.703/4311.367 | 1480.743/1486.271/2132.726 | -65.0% | 4734.962 → 1958.993 | 663.812 → 663.938 |
| test60 | 4771.691/4846.733/4903.379 | 1623.005/1630.983/1712.296 | -66.3% | 5327.660 → 2115.523 | 602.453 → 602.625 |

## Extended regression matrix

| Workload | Execute before min/median/max | Execute after min/median/max | Median change | Process before → after median | RSS before → after MiB |
|---|---:|---:|---:|---:|---:|
| history-64 | 0.053/0.057/0.087 | 0.021/0.022/0.060 | -61.4% | 2.183 → 1.884 | 2.188 → 2.188 |
| history-4096 | 2.482/2.501/3.138 | 0.638/0.649/0.710 | -74.1% | 5.297 → 3.234 | 4.516 → 4.516 |
| history-65536 | 39.470/40.215/40.565 | 10.975/11.335/12.036 | -71.8% | 55.029 → 27.001 | 39.328 → 39.328 |
| branch-1 | 0.008/0.009/0.013 | 0.008/0.008/0.011 | -11.1% | 1.981 → 1.990 | 2.078 → 2.094 |
| branch-64 | 0.067/0.070/0.079 | 0.030/0.031/0.036 | -55.7% | 2.092 → 2.029 | 2.250 → 2.250 |
| branch-1024 | 0.900/0.938/0.998 | 0.340/0.345/0.368 | -63.2% | 3.408 → 2.831 | 3.469 → 3.469 |
| chain-16 | 0.235/0.250/0.255 | 0.057/0.059/0.061 | -76.4% | 2.198 → 2.009 | 2.375 → 2.375 |
| chain-64 | 2.981/3.036/3.070 | 0.483/0.498/0.514 | -83.6% | 5.507 → 2.868 | 3.484 → 3.500 |
| chain-256 | 46.069/46.274/46.713 | 6.870/7.052/7.222 | -84.8% | 55.789 → 16.004 | 15.703 → 15.797 |
| local-1 | 0.009/0.010/0.015 | 0.008/0.009/0.014 | -10.0% | 2.055 → 1.948 | 2.094 → 2.109 |
| local-1000 | 2.614/2.661/2.744 | 1.283/1.303/1.335 | -51.0% | 6.233 → 4.594 | 5.625 → 5.609 |
| local-10000 | 26.781/26.932/27.285 | 13.579/13.965/14.344 | -48.1% | 44.426 → 29.838 | 34.484 → 34.484 |
| bigint-64 | 0.530/0.558/0.571 | 0.214/0.223/0.240 | -60.0% | 2.758 → 2.441 | 2.750 → 2.734 |
| bigint-512 | 0.527/0.550/0.564 | 0.220/0.224/0.242 | -59.3% | 2.841 → 2.455 | 2.828 → 2.828 |
| bigint-4096 | 0.640/0.653/0.667 | 0.279/0.285/0.292 | -56.4% | 3.005 → 2.586 | 3.641 → 3.625 |
| real-33 | 1151.995/1162.954/1219.689 | 366.297/368.678/376.895 | -68.3% | 1376.941 → 560.924 | 343.172 → 343.188 |
| real-40 | 6.556/6.897/7.158 | 2.110/2.153/2.384 | -68.8% | 10.134 → 5.284 | 3.984 → 3.969 |
| real-65 | 3710.658/3776.316/3880.642 | 1769.381/1795.367/1850.028 | -52.5% | 4351.612 → 2307.968 | 855.391 → 855.375 |
| real-68 | 683.981/694.384/705.553 | 353.634/358.622/372.512 | -48.4% | 765.204 → 424.125 | 90.016 → 90.125 |
| real-71 | 127.283/131.576/135.039 | 80.017/81.881/116.880 | -37.8% | 145.843 → 93.862 | 16.422 → 16.375 |
| real-79 | 264.195/274.840/278.367 | 95.315/96.210/99.680 | -65.0% | 314.640 → 132.939 | 54.922 → 54.953 |
| real-84 | 13.379/13.644/14.948 | 7.062/7.149/7.315 | -47.6% | 17.930 → 11.248 | 5.016 → 4.984 |
| real-88 | 118.147/119.390/125.183 | 30.627/32.330/33.481 | -72.9% | 147.965 → 59.498 | 42.641 → 42.656 |

## Costs and interpretation

All **1176/1176** verifier processes passed. Every paired workload has identical physical artifact hashes and complete statistics, including metered work; time savings come from performing the same exact task with fewer generic arithmetic operations. The tables retain every workload, including regressions and outliers. No aggregate geometric mean hides a regression.

Execution medians decrease in all 49 paired workloads. Actual test57 falls from 4,932.676 to 2,219.925 ms; test65 falls from 3,776.316 to 1,795.367 ms. Tiny-process latency does not uniformly improve: injectivity-64 process median rises from 2.186 to 2.391 ms (+9.4%) even as its execution median halves from 0.240 to 0.120 ms. Flow-1, injectivity-1 and branch-1 process medians rise by 0.1–0.5%. Those startup-dominated regressions are retained. All median RSS changes are within 3%, so this is principally a latency/throughput improvement, not a demonstrated major memory reduction.

Each raw run records synthetic preparation stages, all proof byte sizes, logical work, generated domains and per-stage decoder costs. Historical actual preparation costs are preserved in archived receipts rather than remeasured; theorem actual-workload preparation arrays are empty and their generation_ns=0 is a sentinel, not a claim of zero preparation cost. The theorem baseline is also tabulated in `THEOREM_V7_REPORT.md`; the extended representation is described in `EXTENDED_REPORT.md`. Real preparation receipts are copied under each extended result directory. Actual certificates were not redesigned for this optimization, so proof size and original RPA-authoring work do not decrease. Canonical/assembly generation samples are recorded separately and are not folded into verification latency.

These shortcuts address exact arithmetic in the existing flat/sparse representation. They do not remove eager decoding, the quadratic physical size of expanded prefix-map chains, or large scalar injectivity certificates. Arbitrary non-unit rationals still use BigRational multiplication; the big-integer workload is part of the unchanged regression matrix. Peak resident-set differences are reported independently, not inferred from logical live facts.

This report describes the isolated candidate. Subsequent status-classification or public-helper resource-policy repairs and the production merge need their own validation receipt; do not silently identify a later executable with the measured hashes. Tests and independent review support this engineering choice without constituting a formal proof of the complete kernel.
