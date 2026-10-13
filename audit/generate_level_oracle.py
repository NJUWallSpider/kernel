#!/usr/bin/env python3
"""Independent Fraction objective-level truth table; no kernel/model writer used."""
from fractions import Fraction as F
from pathlib import Path
import json

ROOT=Path(__file__).resolve().parents[1]

def main():
    cases=[]
    objectives=[(F(0),F(0),F(0)),(F(7,3),F(0),F(0)),(F(-5,7),F(-2,3),F(11,5)),(F(13,2),F(1),F(-3)),(F(-9),F(-7),F(-1,2))]
    for c,a,b in objectives:
        for level in [F(-7),F(0),c,c+a-b,F(19,11)]:
            points=[]
            for ix in range(-7,10):
                x=F(ix,2)
                for iy in range(-5,8):
                    y=F(iy,2);r=F(2,3)+2*x-y
                    old=(-3<=x<=4 and -2<=y<=3 and y.denominator==1 and -2<=r<=5)
                    obj=c+a*x+b*y
                    points.append({'values':[str(x),str(y)],'objective':str(obj),'original':old,'restricted':old and obj==level})
            cases.append({'objective':{'constant':str(c),'terms':[[i,str(q)] for i,q in enumerate([a,b]) if q]},'level':str(level),'points':points})
    path=ROOT/'tests/vectors/level_oracle.json';path.write_text(json.dumps({'generator':'audit/generate_level_oracle.py','cases':cases},separators=(',',':'))+'\n')
    print(json.dumps({'cases':len(cases),'points':sum(len(c['points']) for c in cases),'path':str(path)}))

if __name__=='__main__':main()
