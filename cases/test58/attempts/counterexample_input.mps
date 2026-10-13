NAME counterexample_input
ROWS
 N obj
 E balance
 L cap_a
 L cap_b
 L cap_r
COLUMNS
    a balance 1 cap_a 1
    b balance 1 cap_b 1
    r balance -1 cap_r 1
RHS
    rhs balance 82
    rhs cap_a 82
    rhs cap_b 82
    rhs cap_r 82
BOUNDS
 FX bound a 82
 FX bound b 82
 FX bound r 82
ENDATA
