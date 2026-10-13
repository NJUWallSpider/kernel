#!/usr/bin/env python3
"""Independent Fraction construction; does not invoke the Rust extension builder."""
from fractions import Fraction as F
from pathlib import Path
import json,random
r=random.Random(801127);cases=[]
for c in [F(0),F(1,7),F(1),F(2),F(212),F(2**90,11)]:
 for z in [F(0),F(1)]:
  for t in [F(-1),F(-7,11),F(-1,2),F(0),F(1,13),F(1)]:
   f=c*z*t
   # Affine source coordinates deliberately have rational shifts and signs.
   offset=F(r.randrange(-20,21),13);az=F(r.randrange(-9,10),7)
   flow={'constant':str(offset),'terms':[[0,'-2/3']]}
   activation={'constant':str(az),'terms':[[1,'3/5']]}
   source=[(offset-f)*F(3,2),(z-az)*F(5,3)]
   result=[max(f,F(0)),max(-f,F(0)),z if f>=0 else F(0),F(0) if f>=0 else z]
   cases.append({'capacity':str(c),'flow':flow,'activation':activation,'source':[str(x) for x in source],'joint':[str(x) for x in source+result],'f':str(f),'z':str(z)})
# Batches with correlated parent coordinates but disjoint new choices.
batches=[]
for n in [0,1,2,9,32,128]:
 entries=[r.choice(cases) for _ in range(n)]
 source=[];witnesses=[];values=[]
 for i,e in enumerate(entries):
  source+=e['source'];flow=e['flow'].copy();activation=e['activation'].copy()
  flow['terms']=[[2*i,flow['terms'][0][1]]];activation['terms']=[[2*i+1,activation['terms'][0][1]]]
  witnesses.append({'capacity':e['capacity'],'flow':flow,'activation':activation});values+=e['joint'][2:]
 batches.append({'source':source,'witnesses':witnesses,'joint':source+values})
p=Path(__file__).resolve().parents[1]/'tests/vectors/signed_oracle.json';p.write_text(json.dumps({'schema':'independent-signed-fraction-v1','seed':801127,'cases':cases,'batches':batches},indent=2)+'\n');print(len(cases),len(batches),p)
