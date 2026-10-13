#!/usr/bin/env python3
"""Independent finite Fraction checks for indicator tightening mathematics.

Does not import the RPX kernel, preparer, Builder, proof-expression operations,
or original trajectory verification script. Tests finite truth sets directly.
"""
from fractions import Fraction as F
from itertools import product
from pathlib import Path
import hashlib,json,random,time


def main():
    start=time.perf_counter();rng=random.Random(370011);counts={'indicator_truth_checks':0,'impossible_selector_checks':0,'box_corner_checks':0,'path_checks':0,'rounding_checks':0}
    for _ in range(160):
        L=F(rng.randrange(-50,20),rng.choice([1,2,3,7]));U=L+F(rng.randrange(0,40),rng.choice([1,2,5]))
        b=F(rng.randrange(-30,40),rng.choice([1,3,5]));required=max(F(0),b-L)
        newM=F(-((-required.numerator)//required.denominator));M=newM+F(rng.randrange(1,40),rng.choice([1,2,7]))
        rhs=b-M;newrhs=b-newM;assert newrhs>=rhs and newrhs<=L
        for k in range(25):
            A=L+(U-L)*F(k,24)
            for y in (F(0),F(1)):
                assert (A-M*y>=rhs)==(A-newM*y>=newrhs)
                counts['indicator_truth_checks']+=1
            for y in (F(1,19),F(1,7),F(1,2),F(9,10),F(18,19)):
                if A-newM*y>=newrhs:assert A-M*y>=rhs
                counts['indicator_truth_checks']+=1
    for _ in range(160):
        L=F(rng.randrange(-50,20),rng.choice([1,2,3]));U=L+F(rng.randrange(1,30),rng.choice([1,2,5]));b=U+F(rng.randrange(1,30),rng.choice([1,3,7]))
        M=b-L+F(rng.randrange(1,20));rhs=b-M;B=(U-rhs)/M;assert 0<B<1
        for k in range(17):
            A=L+(U-L)*F(k,16)
            for y in (F(0),F(1)):
                if A-M*y>=rhs:assert y==0
                counts['impossible_selector_checks']+=1
    for _ in range(120):
        n=rng.randrange(1,6);bounds=[(F(rng.randrange(-20,1),rng.choice([1,2,7])),F(rng.randrange(1,20),rng.choice([1,3,5]))) for _ in range(n)]
        cs=[F(rng.choice([x for x in range(-9,10) if x]),rng.choice([1,2,5])) for _ in range(n)]
        values=[sum(c*x for c,x in zip(cs,corner)) for corner in product(*bounds)]
        direct_min=sum(c*(lo if c>0 else hi) for c,(lo,hi) in zip(cs,bounds))
        direct_max=sum(c*(hi if c>0 else lo) for c,(lo,hi) in zip(cs,bounds))
        assert min(values)==direct_min and max(values)==direct_max;counts['box_corner_checks']+=len(values)
    for _ in range(200):
        n=rng.randrange(2,9);x=[F(rng.randrange(-100,100),rng.choice([1,2,3,7])) for _ in range(n)]
        order=list(range(n));rng.shuffle(order)
        ds=[x[u]-x[v]+F(rng.randrange(0,30),rng.choice([1,2,5])) for u,v in zip(order,order[1:])]
        assert all(x[u]-x[v]<=d for u,v,d in zip(order,order[1:],ds))
        assert x[order[0]]-x[order[-1]]<=sum(ds);counts['path_checks']+=1
    for den in range(1,20):
        for num in range(-100,101):
            d=F(num,den);ceil=-((-d.numerator)//d.denominator)
            for z in range(-10,11):
                assert (d+z<=0)==(ceil+z<=0);counts['rounding_checks']+=1
    # Actual c22 witness, evaluated directly without loading its certificate.
    M,newM,oldrhs,newrhs=map(F,(8400000,840000,-7910000,-350000));A=F(0);y=F(9,10)
    assert A-M*y-oldrhs==350000 and newrhs-A+newM*y==406000
    result={'status':'PASS','seed':370011,'counts':counts,'actual_c22_source_slack':'350000','actual_c22_target_violation':'406000',
            'oracle':'stdlib fractions.Fraction; direct finite truth tables and corner enumeration; no kernel/preparer imports',
            'limitations':'Finite independent checks supplement universal algebraic argument and complete kernel proof; they are not a proof of all real points.',
            'elapsed_seconds':time.perf_counter()-start,'script_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
    Path(__file__).with_suffix('.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))

if __name__=='__main__':main()
