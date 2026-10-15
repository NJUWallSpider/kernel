# Final supplied-proof encoder regression

**VERIFIED.** The 539 frozen snapshot preserves full bytes of all six artifacts
against the 5c helper arm: source MCM, target MCM, Certificate JSON, Request JSON,
RPX and the committed original C8 MPS. Complete native statistics and all
50,186 definition-expression/scope checks per MI/LP forward claim are identical.
The same four unrestricted Equal inverse claims, 178,164 observations each, and
3,118,120 native obligations remain. No mathematical target is weakened.

| Single serial sample | Old helpers | 539 encoder |
|---|---:|---:|
| Serialization + compile + whole artifact binding | 45.300 s | 17.499 s |
| Full measured execution | 139.444 s | 99.930 s |
| Native verify process wall | 5.315 s | 3.791 s |

These are observations from one sample, not a stable speedup estimate. Other
phases also vary, so the entire 39.513-second total difference is not assigned
to the encoder. RSS is included in the raw record for information only; it is
not a gate, and no additional memory-profiling round is planned.

This final third arm exited 0. No new Agent or solver was launched. Original
two-arm scripts/results/large outputs and the original C8 run are unchanged.
The new output is the independent `encoder/` directory. This regression checks
a supplied proof; fresh cases remain necessary for the user acceptance goal.
