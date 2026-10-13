#!/usr/bin/env python3
"""Parameterized complementary-integer elimination with independent permutations."""
import argparse,json,random,subprocess,time
from fractions import Fraction as F
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
p=argparse.ArgumentParser();p.add_argument('--kernel',default='target/release/rpx');a=p.parse_args();kernel=(ROOT/a.kernel).resolve();rng=random.Random(0x52505847454e)
def expr(c=0,terms=()):return {'constant':str(c),'terms':[[i,str(v)] for i,v in sorted(terms) if v]}
def ref(k,i):return {k:i}
def mps(path,names,rows,obj,constant,upper):
 out=['NAME generated','ROWS',' N obj']+[f' E {r}' for r,_,_ in rows]+['COLUMNS']
 for v in names:
  out.append(f' {v} obj {obj.get(v,0)}')
  for r,c,b in rows:
   if c.get(v,0):out.append(f' {v} {r} {c[v]}')
 out+=['RHS',f' rhs obj {-constant}']+[f' rhs {r} {b}' for r,c,b in rows]+['BOUNDS']
 for v in names:out.extend([f' LI b {v} 0',f' UI b {v} {upper[v]}'])
 out+=['ENDATA'];path.write_text('\n'.join(out)+'\n')
records=[];base=ROOT/'tests/generated/affine-generalization';base.mkdir(parents=True,exist_ok=True)
for n in [1,2,7,31,127]:
 for param in [1,2,17]:
  d=base/f'n{n}-a{param}';d.mkdir(exist_ok=True);xs=[f'renamed_x{rng.randrange(10**9)}' for _ in range(n)];ys=[f'renamed_y{rng.randrange(10**9)}' for _ in range(n)];sn=xs+ys;tn=xs.copy();rng.shuffle(sn);rng.shuffle(tn);si={v:i for i,v in enumerate(sn)};ti={v:i for i,v in enumerate(tn)}
  rows=[(f'eq_{k}',{xs[k]:1,ys[k]:1},param) for k in range(n)];rng.shuffle(rows);ri={int(r[3:]):i for i,(r,c,b) in enumerate(rows)};sx={v:rng.randrange(-11,12) for v in sn};constant=rng.randrange(-100,101);tx={xs[k]:sx[xs[k]]-sx[ys[k]] for k in range(n)};tc=constant+param*sum(sx[y] for y in ys)
  mps(d/'source.mps',sn,rows,sx,constant,{v:param for v in sn});mps(d/'target.mps',tn,[],tx,tc,{v:param for v in tn})
  # Rowless target remains a legitimate MILP, including unbounded objectives only if bounds permit.
  claims=[];blocks=[]
  for integral in [True,False]:
   for reverse in [False,True]:
    idx=len(claims);inp=tn if reverse else sn;out=sn if reverse else tn
    claim={'reverse':reverse,'input_integers':integral,'output_integers':integral,'objective':'Equal','projection':[[ti[x],si[x]] if reverse else [si[x],ti[x]] for x in xs],'inverse':idx-1 if reverse else idx+1};claims.append(claim)
    maps=[];checks=[];steps=[]
    if not reverse:
     for x in tn:
      maps.append(expr(0,[(si[x],1)]));checks += [ref('VarLower',si[x]),ref('VarUpper',si[x])]+(['Exact'] if integral else [])
     terms=[[ref('RowEq',ri[k]),str(-sx[ys[k]] )] for k in range(n)]
     steps.append({'Lin':{'id':0,'kind':'Eq','constant':'0','terms':terms}});checks.append(ref('Local',0));checks += ['Exact']*n
     for v in sn:
      if v in ti:checks.append('Exact')
      else:
       k=ys.index(v);j=k+1;steps.append({'Lin':{'id':j,'kind':'Eq','constant':'0','terms':[[ref('RowEq',ri[k]),'-1']]}});checks.append(ref('Local',j))
    else:
     for v in sn:
      if v in ti:
       maps.append(expr(0,[(ti[v],1)]));checks += [ref('VarLower',ti[v]),ref('VarUpper',ti[v])]
      else:
       k=ys.index(v);i=ti[xs[k]];maps.append(expr(param,[(i,-1)]));checks += [ref('VarUpper',i),ref('VarLower',i)]
      if integral:checks.append('Exact')
     checks += ['Exact']*(len(rows)+1+n+len(tn))
    blocks.append({'steps':steps,'end':{'Return':{'map':maps,'checks':checks}}})
  cert={'claims':claims,'blocks':blocks};(d/'proof.rpa').write_text('RPA 1\n'+json.dumps(cert));(d/'request.json').write_text(json.dumps(claims));runs=[]
  for args in [['canonical',d/'source.mps',d/'source.mcm'],['canonical',d/'target.mps',d/'target.mcm'],['assemble',d/'proof.rpa',d/'proof.rpx'],['verify',d/'source.mcm',d/'target.mcm',d/'proof.rpx',d/'request.json']]:
   r=subprocess.run([str(kernel),*map(str,args)],capture_output=True,text=True);v=json.loads(r.stdout);runs.append(v)
   if r.returncode:raise RuntimeError((str(d),args,v))
  records.append({'n':n,'parameter':param,'result':runs[-1]})
report={'seed':'0x52505847454e','cases':records,'count':len(records),'all_verified':all(r['result']['status']=='VERIFIED' for r in records)};(ROOT/'audit/generalization.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps({'count':report['count'],'all_verified':report['all_verified']}))
