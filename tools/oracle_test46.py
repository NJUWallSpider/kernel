#!/usr/bin/env python3
"""Independent Fraction oracle for the three distinct test46 arguments.

No preparer/proof-library imports and no solver. Exhaustive finite integer
assignments test moment uniqueness; exact transport points test interval bounds.
These tests supplement, not replace, checking every actual model obligation.
"""
from fractions import Fraction as Q
from itertools import product
from pathlib import Path
import json,random,hashlib

def main():
    rng=random.Random(460051);counts={'onehot_pairs':0,'integer_marginal_tables':0,'lp_interval_couplings':0,'cost_cutoff':0};digest=hashlib.sha256()
    def record(x):digest.update((str(x)+'\n').encode())
    for n in range(1,15):
        states=rng.sample(range(-50,51),n)
        for i,j in product(range(n),repeat=2):
            x=[Q(k==i) for k in range(n)];y=[Q(k==j) for k in range(n)]
            assert (sum(a*b for a,b in zip(states,x))==sum(a*b for a,b in zip(states,y)))==(x==y)
            record((states,i,j));counts['onehot_pairs']+=1
    # A binary row and column one-hot vector uniquely select the common cell.
    # Check all binary assignments for small complete and deleted-cell tables.
    for na,nb in [(1,1),(2,2),(2,3),(3,2)]:
        for i,j in product(range(na),range(nb)):
            for entries in product((Q(0),Q(1)),repeat=na*nb):
                rows=[sum(entries[a*nb+b] for b in range(nb)) for a in range(na)]
                cols=[sum(entries[a*nb+b] for a in range(na)) for b in range(nb)]
                if rows==[Q(a==i) for a in range(na)] and cols==[Q(b==j) for b in range(nb)]:
                    assert entries==tuple(Q(a==i and b==j) for a in range(na) for b in range(nb))
                counts['integer_marginal_tables']+=1
            # Fréchet bounds force every continuous cell to that same 0/1 value.
            for a,b in product(range(na),range(nb)):
                x=Q(a==i);y=Q(b==j);assert max(Q(0),x+y-1)==min(x,y)==Q(a==i and b==j)
    for da,db in product(range(1,10),repeat=2):
        for ia,ib in product(range(da+1),range(db+1)):
            alpha,beta=Q(ia,da),Q(ib,db);lo=max(Q(0),alpha+beta-1);hi=min(alpha,beta);assert lo<=hi
            for t in (lo,(lo+hi)/2,hi):
                weights=[1-alpha-beta+t,alpha-t,beta-t,t]
                assert all(0<=w<=1 for w in weights) and sum(weights)==1
                amin,amax=Q(-13,7),Q(51,11);bmin,bmax=Q(17,5),Q(98,3)
                assert weights[0]*amin+weights[1]*amax+weights[2]*amin+weights[3]*amax==amin+(amax-amin)*alpha
                assert weights[0]*bmin+weights[1]*bmin+weights[2]*bmax+weights[3]*bmax==bmin+(bmax-bmin)*beta
                assert sum(Q(17)*w for w in weights)==17
                counts['lp_interval_couplings']+=1;record(weights)
    for cap in (2,3,17,39424):
        for forbidden in range(5):
            for rest in (Q(0),Q(1,7),Q(cap-1)):
                if cap*forbidden+rest<=cap-1:assert forbidden==0
                counts['cost_cutoff']+=1
    out={'status':'PASS','independent':'Python Fraction; no preparer, kernel, solver, or float arithmetic imports','seed':460051,'checks':counts,'generated_values_sha256':digest.hexdigest(),'scope':'Generalized integer moment uniqueness, binary marginal forcing, exact real interval/corner coupling, and positive-cost cutoff. Full actual model proof is separate.'}
    Path('cases/test46/oracle.json').write_text(json.dumps(out,indent=2)+'\n');print(json.dumps(out))
if __name__=='__main__':main()
