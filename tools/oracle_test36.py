#!/usr/bin/env python3
"""Independent exact oracle for canonical AND chains and top-five box bounds."""
from fractions import Fraction as Q
from itertools import product
from pathlib import Path
import random,json,hashlib

def main():
    rng=random.Random(360019);count={'boolean_chains':0,'signed_zero_and_nonzero':0,'top_five_box_identities':0,'rational_top_five_samples':0};digest=hashlib.sha256()
    for n in range(2,12):
        for bits in product((0,1),repeat=n):
            old=Q(0);canon=Q(0)
            for j in range(1,n):
                old=max(Q(0),old+bits[j]-1) if j>1 else max(Q(0),bits[0]+bits[1]-1)
                old+=Q(rng.randrange(4),7)
                canon=Q(all(bits[:j+1]));assert 0<=canon<=1 and canon.denominator==1 and canon<=old
                assert canon==max(Q(0),sum(bits[:j+1])-j)
            count['boolean_chains']+=1;digest.update(str((bits,old,canon)).encode())
    for capacity in range(1,16):
        for f in range(-capacity,2):
            for u in (0,1):
                p=max(Q(f),Q(0));neg=max(Q(-f),Q(0));v=1-u
                if p<=capacity*u and neg<=capacity*v:
                    assert p-neg==f and p.denominator==1
                    assert (p==0 if u==0 else p==f)
                    count['signed_zero_and_nonzero']+=1
    for _ in range(500):
        n=rng.randrange(5,101);w=[Q(rng.randrange(80)) for _ in range(n)];q=sorted(w,reverse=True)[4];top=sum(sorted(w,reverse=True)[:5])
        # Expand the author's purely linear top-five construction independently.
        coeff=[-q-max(Q(0),wi-q)+max(Q(0),q-wi) for wi in w]
        constant=q*(n-5)-sum(max(Q(0),q-wi) for wi in w)
        assert coeff==[-wi for wi in w] and constant==sum(w)-top;count['top_five_box_identities']+=1
        first=set(rng.sample(range(n),5));second=set(rng.sample(range(n),5));t=Q(rng.randrange(18),17)
        missing=[t*Q(i in first)+(1-t)*Q(i in second) for i in range(n)]
        assert sum(missing)==5 and all(0<=d<=1 for d in missing) and sum(wi*d for wi,d in zip(w,missing))<=top;count['rational_top_five_samples']+=1
    out={'status':'PASS','seed':360019,'independence':'Python Fraction; no kernel, preparer or solver imports','checks':count,'digest':digest.hexdigest(),'scope':'Generalized binary prefix chains with nonminimal real lifts, signed zero ambiguity, exact top-five linear identities and fractional box samples. Actual-model contracts checked separately by the kernel.'};Path('cases/test36/oracle.json').write_text(json.dumps(out,indent=2)+'\n');print(json.dumps(out))
if __name__=='__main__':main()
