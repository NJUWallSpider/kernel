#!/usr/bin/env python3
"""Independent finite exact checks of the generic optimal-face identities.

This does not call the proof preparer, kernel or a solver. It complements the
actual-model complete symbolic audit and RPX proof, not replaces either.
"""
from fractions import Fraction as F
from itertools import product
from pathlib import Path
import hashlib,json,time

def main():
    start=time.perf_counter();identity_checks=0;assignment_checks=0;rounding_checks=0
    for np in range(7):
        for nb in range(5):
            for bits in product((0,1),repeat=np+nb):
                p,b=bits[:np],bits[np:];obj=sum(p)-10*sum(b);gap=sum(p)+10*sum(1-x for x in b)
                assert obj+10*nb==gap>=0
                assert (obj==-10*nb)==(all(x==0 for x in p) and all(x==1 for x in b));identity_checks+=1
    for positions in range(1,5):
        vectors=[(0,)*positions]+[tuple(int(i==j) for i in range(positions)) for j in range(positions)]
        for arity in range(1,6):
            for ys in product(vectors,repeat=arity):
                for chosen in range(positions):
                    x=tuple(int(j==chosen) for j in range(positions))
                    feasible=all(sum(y[j] for y in ys)-x[j]<=arity-1 and sum(y[j] for y in ys)-arity*x[j]>=0 for j in range(positions))
                    assert feasible==all(y==x for y in ys);assignment_checks+=1
    for k in range(1,25):
        constant=-F(k-1,k);ceiling=-(-constant.numerator//constant.denominator);assert ceiling==0
        for z in range(-30,31):
            assert (F(z)+constant<=0)==(z<=0);rounding_checks+=1
    # Positive nonuniform rational coefficients retain the zero-sum conclusion.
    rational_checks=0
    for n in range(1,9):
        coefficients=[F(2*i+1,i+2) for i in range(n)]
        for values in product((F(0),F(1,3)),repeat=n):
            total=sum((c*x for c,x in zip(coefficients,values)),F(0));assert total>=0
            assert (total==0)==all(x==0 for x in values);rational_checks+=1
    root=Path(__file__).resolve().parents[1];result={'status':'PASS','independence':'Standard-library Fraction/product calculations; no imports from proof preparers, Rust or solvers.','objective_lower_and_all_fixings':identity_checks,'complete_local_assignment_patterns':assignment_checks,'rounding_implication_values':rounding_checks,'nonuniform_rational_zero_sum_patterns':rational_checks,'elapsed_seconds':time.perf_counter()-start,'generator_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest()};(root/'audit/optimal_face80_oracle.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))

if __name__=='__main__':main()
