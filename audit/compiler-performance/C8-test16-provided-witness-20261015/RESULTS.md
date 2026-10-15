# Same supplied C8 test16 proof: regression result

Both arms passed native verification and whole-artifact binding. The baseline
RPX is byte-identical to the original C8 RPX. Both arms preserve the exact source,
target, committed MPS and complete Request bytes: four unrestricted MI/LP
objective-Equal inverse claims, each observing 178,164 coordinates. All 50,186
zero/fixed/alias EQ expressions were individually checked in each MI/LP claim
root scope; their four expression digests agree. Native obligations remain
3,118,120 in both arms.

| Measured phase | Original author | zero_sum + rewrite_many |
|---|---:|---:|
| Zero/fixed/alias derivation, MI+LP | 12.382 s | 4.614 s |
| Forward author functions including substitution | 49.840 s | 41.692 s |
| Serialization + artifact binding + compile | 41.637 s | 45.300 s |
| Native verify process wall | 6.124 s | 5.315 s |
| Full measured execution | 147.734 s | 139.444 s |
| Python peak RSS, decimal GB | 3.205 | 3.777 |

The helper derivation is faster in this single supplied-proof regression, but
the full execution decreases only 8.291 seconds (about 5.6%). Serialization is
slower in the helper sample, and Python peak memory increases about 0.572 GB.
No stable speedup or memory improvement is claimed. The resolver and complete
substitution proof still contribute substantial cost. Load/setup/completion/
materialization/native-call details are in the compact result JSONs.

The immutable 5c42197 package and native 5775d6… are identical in both arms.
The original proof function, including its repeated set(zfacts) assertion, is
preserved separately. The helper consumes only the supplied row/sign/coordinate
sequence and alias witnesses, without selecting rows, discovering closure,
searching for a proof or changing the mathematical target.

This is one baseline-first serial sample per arm on a shared host. It provides
a real full-size mechanical regression, not a fresh Agent or nomf comparison,
and cannot establish faster mathematical discovery, unchanged exploration
willingness, or held-out generalization. Neither the C8 non-affine exploration
gap on test58 nor any new case is tested here. No Agent or solver was launched.
