# Extended fixed V3 performance checkpoint

This supplements the earlier fixed baseline. It is not final performance acceptance
for unimplemented features or the remaining corpus. The matrix was frozen before
further representation work, at `bench/extended_workloads.json`; the implementation
is the independently built V3 source checkpoint. All23workloads passed9fresh-process
observations each, plus3separate RSS observations each. All276processes returned
VERIFIED. Workers held heavy work after explicit idle confirmations. Filesystem
caches are warm; unrelated OS/user activity is uncontrolled.

Hardware: {'machdep.cpu.brand_string': 'Apple M5', 'hw.memsize': '17179869184', 'hw.ncpu': '10'}. Compiler, dependency/source/binary hashes, raw timings,
process startup, model/proof decode timing and logical counters are preserved in
`bench/results/extended-v3-quiescent/raw.json`. RSS below is the median of three
separate runs; process/execute medians are from the nine main observations.

| Workload | Execute ms | Full process ms | Process range ms | RPX bytes | Work units | Peak live facts | RSS MiB |
| --- | ---: | ---: | --- | ---: | ---: | ---: | ---: |
| history-64 | 0.057 | 2.207 | 2.069–2.775 | 4132 | 461 | 2 | 2.12 |
| history-4096 | 2.668 | 8.596 | 5.715–21.587 | 258148 | 28685 | 2 | 5.31 |
| history-65536 | 39.694 | 57.243 | 56.236–59.569 | 4128868 | 458765 | 2 | 53.25 |
| branch-1 | 0.010 | 1.989 | 1.905–2.228 | 236 | 29 | 1 | 2.03 |
| branch-64 | 0.075 | 2.123 | 1.959–2.250 | 8804 | 1289 | 2 | 2.20 |
| branch-1024 | 1.041 | 3.511 | 3.297–3.818 | 139364 | 20489 | 2 | 3.41 |
| chain-16 | 0.235 | 2.268 | 2.200–2.483 | 6605 | 1666 | 16 | 2.28 |
| chain-64 | 3.019 | 5.510 | 5.364–6.405 | 87725 | 23578 | 64 | 3.27 |
| chain-256 | 46.447 | 56.012 | 55.291–56.681 | 1333805 | 364666 | 256 | 15.45 |
| local-1 | 0.010 | 1.965 | 1.827–2.207 | 171 | 26 | 1 | 2.03 |
| local-1000 | 2.598 | 6.085 | 5.829–6.272 | 118053 | 25001 | 1000 | 5.62 |
| local-10000 | 26.838 | 44.099 | 43.581–44.530 | 1180053 | 250001 | 10000 | 35.45 |
| bigint-64 | 0.540 | 3.049 | 2.821–3.347 | 15165 | 4611 | 0 | 2.59 |
| bigint-512 | 0.563 | 3.229 | 2.920–3.447 | 15165 | 4611 | 0 | 2.66 |
| bigint-4096 | 0.663 | 3.348 | 3.266–3.611 | 15165 | 4611 | 0 | 3.47 |
| real-33 | 1170.078 | 1379.097 | 1370.678–1393.479 | 27989684 | 10759860 | 90000 | 362.25 |
| real-40 | 6.910 | 10.163 | 9.678–10.730 | 96420 | 35492 | 240 | 3.91 |
| real-65 | 3757.004 | 4283.819 | 4235.241–4435.582 | 57125072 | 22434220 | 52554 | 865.27 |
| real-68 | 693.559 | 757.599 | 739.922–784.970 | 4822420 | 4433660 | 1046 | 90.08 |
| real-71 | 130.559 | 144.559 | 140.863–152.023 | 304420 | 2829481 | 1 | 16.23 |
| real-79 | 267.719 | 305.670 | 299.105–319.004 | 3466070 | 1940098 | 196 | 54.77 |
| real-84 | 13.682 | 17.966 | 17.453–19.031 | 400516 | 108015 | 838 | 4.89 |
| real-88 | 185.197 | 215.798 | 209.111–226.895 | 5395057 | 8324541 | 2573 | 51.12 |

History workloads keep at most two live facts despite65,536fact definitions. RSS
still grows with the completely decoded proof: the live fact store does not retain
dead entries, but whole-file decoding remains a material limitation. This measurement
does not claim streaming verification or constant total memory.

The chain fixture stores all prefix maps explicitly. Its map terms and linear
references grow quadratically with chain length and are recorded separately from
actual substitution visits and bytes. The current ISA has no shared mapping DAG.
The source itself also has prefix rows of quadratic physical size, so the observed
cost is not proof of superlinear execution relative to encoded input. A future DAG
optimization needs equal-input/claim comparisons and actual sparse chain cases.

The64/512/4096-bit cases test exact coefficient processing at a fixed256variables;
they do not exhaust all possible large-rational multiplication/gcd patterns. Actual
cases include2,917,586obligations in test65,5,376local branches in test88, and523,776
checked label pairs plus exact point witnesses in test71. Different actual-case
times prove no speed ratio between different mathematical tasks.

Synthetic generation, MPS canonicalization and RPA assembly costs are individually
recorded. Real certificate preparation is not rerun inside this benchmark; the
original preparation receipts are archived with matching hashes under the result
directory. Their times and compiler configurations must be read independently.
Execution timing includes complete semantic model validation plus proof operations;
finer arithmetic/substitution/state CPU timing attribution remains unmeasured.

`extended-v3-fixture-check` is a one-sample debug correctness diagnostic with other
work active. It is not an isolated performance run and is excluded from this table.
New flow/interval features, additional large-rational patterns, future shared DAGs
and full corpus coverage require further measurements.

Reproduce in an idle-worker window:

```sh
python3 tools/benchmark_extended.py --kernel target/validation-checkpoint-v3/release/rpx --source-root audit/checkpoints/v3-source --label NEW_LABEL
```
