#!/usr/bin/env python3
"""Independent Fraction oracle and full LP/MCM corpus cross-check (untrusted test code)."""
from __future__ import annotations
import argparse, collections, hashlib, json, pathlib, random, re, struct, subprocess, sys, tempfile, time
from fractions import Fraction as F
ROOT=pathlib.Path(__file__).resolve().parents[1]

def expr(terms,constant=F(0)):
    sums={}
    for i,q in terms:sums[i]=sums.get(i,F(0))+q
    return {'constant':str(constant),'terms':[[i,str(q)] for i,q in sorted(sums.items()) if q]}

def oracle_cases(path):
    rng=random.Random(20261011);cases=[]
    def scalar():return F(rng.randint(-19,19),rng.choice([1,2,5,7,10]))
    def text_number(q):
        # Include exact exponent notation without any binary float formatting.
        if q.denominator in (1,2,5,10) and rng.randrange(3)==0:
            return f'{q*10}e-1' if (q*10).denominator==1 else str(q)
        return str(q)
    def expression(terms,c):
        parts=[]
        for i,q in terms:parts.extend(['-' if q<0 else '+',text_number(abs(q)),f'x{i}'])
        parts.extend(['-' if c<0 else '+',text_number(abs(c))]);return ' '.join(parts)
    def multiline(s):
        t=s.split();return '\n  '.join(' '.join(t[i:i+11]) for i in range(0,len(t),11))
    for case_id in range(160):
        n=rng.randint(1,8);vars=[{'name':f'x{i}','integer':False,'lower':'0','upper':None} for i in range(n)]
        objective=[(i,scalar()) for i in range(n)];constant=scalar();maximize=bool(rng.randrange(2))
        if case_id%17==0:objective[0]=(0,F(2**65+case_id,7))
        rows=[];lines=['Maximize' if maximize else 'Minimize',' obj: '+multiline(expression(objective,constant)),'Subject To']
        for j in range(rng.randint(2,8)):
            terms=[(i,scalar()) for i in range(n)];c=scalar();rhs=scalar();sense=rng.choice(['<=','>=','=']);typ=rng.randrange(4)
            if j%3==0:terms.append((0,scalar()))
            if typ==0:
                left=scalar();right=scalar();sense=rng.choice(['<=','>='])
                row=f'r{j}: {left} {sense} {expression(terms,c)} {sense} {right}'
                lo,hi=(left-c,right-c) if sense=='<=' else (right-c,left-c)
                e=expr(terms)
            elif typ==1:
                others=[(i,scalar()) for i in range(n)];right_c=scalar()
                row=f'r{j}: {expression(terms,c)} {sense} {expression(others,right_c)}'
                e=expr(terms+[(i,-q) for i,q in others]);v=right_c-c
                lo=v if sense in ('>=','=') else None;hi=v if sense in ('<=','=') else None
            else:
                row=f'r{j}: {expression(terms,c)} {sense} {rhs}'
                e=expr(terms);v=rhs-c
                lo=v if sense in ('>=','=') else None;hi=v if sense in ('<=','=') else None
            lines.append(' '+multiline(row));rows.append({'name':f'r{j}','expr':e,'lower':None if lo is None else str(lo),'upper':None if hi is None else str(hi)})
        lines.append('Bounds');binary=[];general=[]
        for i,v in enumerate(vars):
            mode=rng.randrange(6);lo=F(0);hi=None
            if mode==1:lines.append(f' x{i} free');lo=None
            elif mode==2:
                lo=scalar();hi=scalar();lines.append(f' {lo} <= x{i} <= {hi}')
            elif mode==3:hi=scalar();lines.append(f' x{i} <= {hi}')
            elif mode==4:lo=scalar();lines.append(f' {lo} <= x{i}')
            elif mode==5:lo=hi=scalar();lines.append(f' x{i} = {lo}')
            typ=rng.randrange(3);v['integer']=typ!=0
            if typ==1:binary.append(f'x{i}');lo=max(F(0),lo) if lo is not None else F(0);hi=min(F(1),hi) if hi is not None else F(1)
            elif typ==2:general.append(f'x{i}')
            v['lower']=None if lo is None else str(lo);v['upper']=None if hi is None else str(hi)
        lines+=['Binary',' '+' '.join(binary),'General',' '+' '.join(general),'Semi','End']
        sign=-1 if maximize else 1
        cases.append({'id':case_id,'lp':'\n'.join(lines)+'\n','expected':{'name':'LP','vars':vars,'rows':rows,'objective':expr([(i,q*sign) for i,q in objective],constant*sign)}})
    path.parent.mkdir(parents=True,exist_ok=True);path.write_text(json.dumps({'seed':20261011,'oracle':'Python fractions.Fraction; expected models generated before serializing LP; no production LP parser used','cases':cases},indent=2)+'\n')
    return len(cases)

# This separate reference parser is intentionally scoped to the three observed
# corpus LP files: explicit coefficients, finite scalar RHS and simple bounds.
# It uses regular expressions and Fraction, not the production token/state code.
NUMBER=r'(?:\d+(?:\.\d*)?|\.\d+)(?:[eEdD][+-]?\d+)?(?:/[+-]?\d+)?'
TERM=re.compile(r'([+-]?)\s*('+NUMBER+r')\s+([A-Za-z_][A-Za-z_0-9]*)')
HEADERS={'min':'objective','minimize':'objective','max':'objective','maximize':'objective','st':'rows','subject to':'rows','bounds':'bounds','bin':'binary','binary':'binary','binaries':'binary','gen':'general','general':'general','generals':'general','semi':'semi','end':'end'}
def reference_lp(path):
    sections=collections.defaultdict(list);section=None;sense=1;ended=False
    for line in path.read_text().splitlines():
        line=line.split('\\',1)[0].strip()
        if not line:continue
        lower=line.lower()
        if lower in HEADERS:
            section=HEADERS[lower]
            if section=='objective':sense=-1 if lower.startswith('max') else 1
            if section=='end':ended=True
            continue
        assert section and section!='end',(path,'section',line)
        sections[section].append(line)
    assert ended and not sections['semi']
    names={};vars=[]
    def var(n):
        if n not in names:names[n]=len(vars);vars.append({'name':n,'integer':False,'lower':'0','upper':None})
        return names[n]
    def terms(s):
        end=0;out=[]
        for m in TERM.finditer(s):
            assert not s[end:m.start()].strip(),(path,'expression gap',s[end:m.start()]);end=m.end()
            q=F((m[1] or '+')+m[2].replace('D','E').replace('d','e'));out.append((var(m[3]),q))
        assert not s[end:].strip(),(path,'expression tail',s[end:]);return out
    objective=' '.join(sections['objective']);label,objective=objective.split(':',1);assert label.strip()
    objective=expr([(i,q*sense) for i,q in terms(objective)])
    records=[]
    for line in sections['rows']:
        if ':' in line:records.append(line)
        else:assert records;records[-1]+=' '+line
    rows=[]
    for record in records:
        name,body=record.split(':',1);pieces=re.split(r'(<=|>=|=)',body);assert len(pieces)==3
        lhs,rel,rhs=pieces;rhs=F(rhs.replace(' ',''));e=expr(terms(lhs))
        rows.append({'name':name.strip(),'expr':e,'lower':str(rhs) if rel in ('>=','=') else None,'upper':str(rhs) if rel in ('<=','=') else None})
    for record in sections['bounds']:
        t=record.split()
        if len(t)==3 and t[0] in names:
            assert t[1]=='<=';vars[var(t[0])]['upper']=str(F(t[2]))
        elif len(t)==3:
            assert t[1]=='<=';vars[var(t[2])]['lower']=str(F(t[0]))
        else:
            assert len(t)==5 and t[1]==t[3]=='<=';v=vars[var(t[2])];v['lower']=str(F(t[0]));v['upper']=str(F(t[4]))
    for record in sections['binary']:
        for n in record.split():
            v=vars[var(n)];assert not v['integer'];v['integer']=True
            v['lower']=str(max(F(0),F(v['lower']))) if v['lower'] is not None else '0'
            v['upper']=str(min(F(1),F(v['upper']))) if v['upper'] is not None else '1'
    for record in sections['general']:
        for n in record.split():v=vars[var(n)];assert not v['integer'];v['integer']=True
    return {'name':'LP','vars':vars,'rows':rows,'objective':objective}

class Reader:
    def __init__(self,data):
        self.data=data;self.i=0
        assert self.take(4)==b'MCM\0' and self.u(2)==1 and self.u(2)==0 and self.u(8)==len(data)
    def take(self,n):
        b=self.data[self.i:self.i+n];assert len(b)==n;self.i+=n;return b
    def u(self,n):return int.from_bytes(self.take(n),'little')
    def tag(self):
        t=self.u(1);assert self.take(3)==b'\0\0\0';return t
    def name(self):return self.take(self.u(4)).decode('ascii')
    def q(self):
        sign=self.tag();assert sign in (0,1);nl=self.u(4);dl=self.u(4);n=self.u(nl);d=self.u(dl);assert d>0
        return str(F(-n if sign else n,d))
    def opt(self):
        t=self.u(1);assert t in (0,1);return self.q() if t else None
    def expr(self):
        constant=self.q();return {'constant':constant,'terms':[[self.u(4),self.q()] for _ in range(self.u(4))]}
    def model(self):
        name=self.name();vs=[]
        for _ in range(self.u(4)):
            n=self.name();t=self.tag();assert t in (0,1);vs.append({'name':n,'integer':bool(t),'lower':self.opt(),'upper':self.opt()})
        rows=[]
        for _ in range(self.u(4)):rows.append({'name':self.name(),'expr':self.expr(),'lower':self.opt(),'upper':self.opt()})
        obj=self.expr();assert self.i==len(self.data);return {'name':name,'vars':vs,'rows':rows,'objective':obj}

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--generate-oracle',action='store_true');p.add_argument('--corpus',type=pathlib.Path);p.add_argument('--rpx',type=pathlib.Path,default=ROOT/'target/release/rpx');p.add_argument('--output',type=pathlib.Path,default=ROOT/'audit/lp_parse_sweep.json');a=p.parse_args()
    if a.generate_oracle:print('generated',oracle_cases(ROOT/'tests/vectors/lp_oracle.json'),'Fraction vectors')
    if a.corpus:
        results=[];start=time.perf_counter()
        with tempfile.TemporaryDirectory(prefix='rpx-lp-sweep-') as tmp:
            for path in sorted(a.corpus.rglob('*.lp')):
                then=time.perf_counter();expected=reference_lp(path);out=pathlib.Path(tmp)/'model.mcm'
                proc=subprocess.run([str(a.rpx.resolve()),'canonical',str(path),str(out)],capture_output=True,text=True)
                payload=json.loads(proc.stdout);payload.update(path=str(path),sha256=hashlib.sha256(path.read_bytes()).hexdigest(),input_bytes=path.stat().st_size,exit_code=proc.returncode)
                if proc.returncode==0:
                    actual=Reader(out.read_bytes()).model();assert actual==expected,(path,'exact full model mismatch')
                    payload.update(independent_fraction_comparison='ALL_FIELDS_EQUAL',integers=sum(v['integer'] for v in actual['vars']),nonzeros=sum(len(r['expr']['terms']) for r in actual['rows'])+len(actual['objective']['terms']))
                payload['wall_seconds']=time.perf_counter()-then;results.append(payload);print(path,payload['status'],payload.get('independent_fraction_comparison'),flush=True)
        report={'command':'python3 audit/lp_parse_sweep.py --corpus '+str(a.corpus),'python':sys.version,'kernel_sha256':hashlib.sha256(a.rpx.read_bytes()).hexdigest(),'elapsed_seconds':time.perf_counter()-start,'files':len(results),'counts':dict(collections.Counter(r['status'] for r in results)),'results':results}
        a.output.write_text(json.dumps(report,indent=2)+'\n')
if __name__=='__main__':main()
