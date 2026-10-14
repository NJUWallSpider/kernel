# C4 test9 quality diagnosis

[diagnosis.json](diagnosis.json) records exact readback statistics, the three existing solver samples, and evidence from the completed Agent trace. It does not rerun a solver or change either formulation.

The compiler artifact has 1,309 variables / 3,174 matrix terms, versus nomf's 1,553 / 3,570; both have 846 rows and 170 integer variables. Both LP objectives are 6,637.1880269. MIP median wall times are 22.872248 s and 11.345495 s, respectively. All three fixed-seed repeats follow the same work path within each arm: 2,875 nodes / 416,566 LP iterations for compiler, 1,916 / 135,216 for nomf. This is a material measured difference despite the smaller compiler artifact.

Matrix signed and magnitude ranges agree. Objective magnitude spans are also nearly equal, but signed structure differs: compiler has 17 negative coefficients near −1 million; nomf's 153 active negative coefficients lie between −20.6 and −7.48. The record folds nomf's fixed `OBJCONST` term into the constant before comparison. Seventeen exact two-coordinate row witnesses establish opposing large objective pairs whose coefficient sums are only 55.189999–71.029998.

The compiler Agent called `coefficient_stats` on the source and target and acknowledged this representation risk. The existing API exposes the required signed statistics. No missing statistics feature is established.

The observed selection trades additional elimination/canonicalization for a different objective and equality structure. Node, presolve, cut, and branching behavior also changed. There is no controlled ablation proving that opposing coefficients alone caused the time gap, and the logs show no numerical failure. The record preserves this limitation and the solver's 0.01% gap tolerance.
