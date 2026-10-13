# Bounded V10 order-sensitivity follow-up

This is one additional fixed experiment on four unchanged old mathematical tasks. It supplements the original 31-workload sequential A/B report; it neither replaces those results nor changes the candidate. No workload preparation or RSS measurement was performed.

Plan `bench/v10_order_sensitivity_plan.json`, SHA-256 `0561daf52fb813f335fc4f6504dfb6577cb4fd270405a71d193e9038b6fdd22d`. Raw evidence `bench/results/v10-order-sensitivity/raw.json`. Old binary `694b1083e2f960aa6e9002c0ce20e796b3bcf091a3397810f30aa43f0ec9f655`; candidate `96a6d3048d1deb6681733ab8b7356875f5e76bd1991c26337fe6820726b9c8f8`.

Each workload has one old and one candidate warmup, recorded but excluded from samples, followed by nine fresh-process pairs. Zero-indexed even pairs run old then candidate; odd pairs run candidate then old. There are 72 timed calls and eight excluded warmups. All calls must succeed with exactly the original statistics, claims and limits. Input artifacts and executable identities are checked before and after each workload.

Isolation declaration: Root authorized one new window and reported root/draft/corpus idle. All task-owned heavy computation is paused except this driver; unrelated host and OS activity remains uncontrolled.

Times are milliseconds. A paired difference is candidate minus old within that pair, not the difference of two unrelated medians. Positive means slower candidate. All observations and outliers remain. These nine pairs support a bounded sensitivity check, not a formal significance claim or guaranteed performance bound.

| Workload | Original sequential execute medians old → new | Alternating old execute min / median / max | Alternating new execute min / median / max | Paired execute difference min / median / max | Positive / zero / negative pairs |
|---|---:|---:|---:|---:|---:|
| rational-1000 | 0.792 → 0.972 | 0.774 / 0.792 / 0.811 | 0.771 / 0.794 / 0.806 | -0.022 / 0.003 / 0.013 | 6 / 0 / 3 |
| real-65 | 1792.479 → 1864.392 | 1747.116 / 1794.533 / 2069.713 | 1789.211 / 1888.465 / 2167.586 | -221.227 / 82.552 / 410.837 | 7 / 0 / 2 |
| real-71 | 78.226 → 84.661 | 76.581 / 78.018 / 79.995 | 77.527 / 78.158 / 81.180 | -1.650 / -0.038 / 4.599 | 4 / 0 / 5 |
| real-79 | 92.846 → 100.561 | 91.449 / 93.047 / 94.707 | 92.408 / 93.641 / 94.012 | -0.800 / -0.005 / 2.229 | 4 / 0 / 5 |

| Workload | Original sequential process medians old → new | Alternating old process min / median / max | Alternating new process min / median / max | Paired process difference min / median / max | Positive / zero / negative pairs |
|---|---:|---:|---:|---:|---:|
| rational-1000 | 3.578 → 3.710 | 3.215 / 3.422 / 4.039 | 3.266 / 3.415 / 3.788 | -0.585 / -0.027 / 0.376 | 2 / 0 / 7 |
| real-65 | 2365.817 → 2404.050 | 2270.931 / 2331.340 / 2622.044 | 2319.194 / 2431.603 / 2761.927 | -240.915 / 81.945 / 455.482 | 6 / 0 / 3 |
| real-71 | 90.147 → 97.329 | 88.519 / 89.831 / 91.639 | 89.060 / 89.997 / 92.904 | -1.896 / -0.298 / 4.384 | 3 / 0 / 6 |
| real-79 | 129.030 → 137.694 | 126.723 / 128.518 / 131.312 | 127.412 / 128.679 / 130.187 | -1.216 / -0.177 / 2.407 | 4 / 0 / 5 |

## Within-pair order check

There are five old-then-new pairs and four new-then-old pairs. These subgroup medians retain the order information; they are not extra runs or independent replication.

| Workload | Execute delta median old→new order | Execute delta median new→old order | Process delta median old→new order | Process delta median new→old order |
|---|---:|---:|---:|---:|
| rational-1000 | +0.005 | +0.003 | -0.023 | -0.065 |
| real-65 | +12.411 | +104.310 | +15.612 | +114.934 |
| real-71 | +0.005 | -0.447 | -0.241 | -0.646 |
| real-79 | -0.005 | +0.106 | -0.505 | +0.099 |

## Interpretation and limits

- `rational-1000`: candidate execution is slower in 6/9 pairs, equal in 0/9 and faster in 3/9; paired median difference +0.003 ms. The paired relative-difference median is +0.38%; interpret it with the absolute time above.
- `real-65`: candidate execution is slower in 7/9 pairs, equal in 0/9 and faster in 2/9; paired median difference +82.552 ms. The paired relative-difference median is +4.52%; interpret it with the absolute time above.
- `real-71`: candidate execution is slower in 4/9 pairs, equal in 0/9 and faster in 5/9; paired median difference -0.038 ms. The paired relative-difference median is -0.05%; interpret it with the absolute time above.
- `real-79`: candidate execution is slower in 4/9 pairs, equal in 0/9 and faster in 5/9; paired median difference -0.005 ms. The paired relative-difference median is -0.01%; interpret it with the absolute time above.

This single bounded follow-up controls the coarse old-first/new-later order more closely, but does not eliminate host activity, clock/thermal state, scheduling noise or all order effects. It cannot identify the internal implementation cause of a regression. The small rational workload remains below one millisecond of verification, so relative changes should not be generalized from its tiny absolute cost. There is no new RSS evidence and no memory-improvement claim. The original sequential results and every new pair remain preserved regardless of direction. No additional resampling or candidate modification is part of this experiment.
