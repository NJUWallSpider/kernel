#!/usr/bin/env python3
"""Solver-free exact proof replay and complete MPS artifact verification.
Run from workspace root: python output/verify.py
"""
from pathlib import Path
from collections import defaultdict, Counter
from fractions import Fraction
from decimal import Decimal
import hashlib, json

def read_mps(path):
    # Separate reader from the analysis: decimal lexical interpretation,
    # duplicate-term summation, and explicit marker/bound handling.
    senses = {}; columns = {}; rhs = {}; raw_bounds = defaultdict(list)
    marked = set(); objective_rows = []; section = None; integer_mode = False
    rhs_sets = set(); bound_sets = set(); section_order = []
    with Path(path).open() as f:
        for line_number, line in enumerate(f, 1):
            if not line.strip() or line.startswith('*'): continue
            t = line.split()
            if not line[0].isspace():
                assert t[0] in {'NAME','ROWS','COLUMNS','RHS','BOUNDS','ENDATA'}, (line_number,t)
                section = t[0]; section_order.append(section); continue
            if section == 'ROWS':
                sense,r = t
                assert sense in {'N','L','G','E'} and r not in senses
                senses[r] = sense
                if sense == 'N': objective_rows.append(r)
            elif section == 'COLUMNS':
                if len(t) == 3 and t[1].strip("'") == 'MARKER':
                    kind = t[2].strip("'")
                    assert kind in {'INTORG','INTEND'}
                    assert integer_mode != (kind == 'INTORG')
                    integer_mode = kind == 'INTORG'; continue
                assert len(t) in {3,5}
                v = t[0]; columns.setdefault(v,defaultdict(Fraction))
                if integer_mode: marked.add(v)
                for j in range(1,len(t),2):
                    assert t[j] in senses
                    columns[v][t[j]] += Fraction(Decimal(t[j+1].replace('D','E').replace('d','e')))
            elif section == 'RHS':
                assert len(t) in {3,5}; rhs_sets.add(t[0])
                for j in range(1,len(t),2):
                    assert t[j] in senses and t[j] not in rhs
                    rhs[t[j]] = Fraction(Decimal(t[j+1]))
            elif section == 'BOUNDS':
                assert len(t) in {3,4}; k,s,v = t[:3]
                assert v in columns and k in {'LO','UP','FX','BV'}
                bound_sets.add(s)
                raw_bounds[v].append((k,Fraction(Decimal(t[3])) if len(t)==4 else None))
            else: raise AssertionError((line_number,section,t))
    assert section_order == ['NAME','ROWS','COLUMNS','RHS','BOUNDS','ENDATA']
    assert not integer_mode and len(objective_rows)==1 and len(rhs_sets)==len(bound_sets)==1
    objrow = objective_rows[0]; assert rhs.get(objrow,0)==0
    bounds = {}; integers = set(marked)
    for v in columns:
        lo,hi = Fraction(0),Fraction(1) if v in marked else None
        for k,a in raw_bounds[v]:
            if k=='LO':lo=a
            elif k=='UP':hi=a
            elif k=='FX':lo=hi=a
            elif k=='BV':lo,hi=Fraction(0),Fraction(1);integers.add(v)
        assert hi is None or lo<=hi
        bounds[v]=(lo,hi)
    rows={r:{} for r in senses if r!=objrow}; objective={}
    for v,t in columns.items():
        for r,a in t.items():
            if not a:continue
            if r==objrow:objective[v]=a
            else:rows[r][v]=a
    return {'rows':rows,'senses':{r:senses[r] for r in rows},'rhs':{r:rhs.get(r,Fraction(0)) for r in rows},'bounds':bounds,'integer':integers,'objective':objective}

def interval(terms,bounds):
    low=high=Fraction(0)
    for v,a in terms.items():
        lo,hi=bounds[v]; l,h=(lo,hi) if a>0 else (hi,lo)
        low=None if low is None or l is None else low+a*l
        high=None if high is None or h is None else high+a*h
    return low,high

def valid_constant(s,b):
    return b==0 if s=='E' else b>=0 if s=='L' else b<=0

def main():
    audit=json.loads(Path('output/audit.json').read_text())
    for field,path in [('input_sha256',audit['input']),('output_sha256',audit['output'])]:
        assert hashlib.sha256(Path(path).read_bytes()).hexdigest()==audit[field]
    original=read_mps(audit['input']); emitted=read_mps(audit['output'])
    assert all(lo>=0 for lo,hi in original['bounds'].values())
    parent={v:v for v in original['bounds']}; zeros=set()
    lo={v:b[0] for v,b in original['bounds'].items()}
    hi={v:b[1] for v,b in original['bounds'].items()}
    def find(v):
        while parent[v]!=v:v=parent[v]
        return v
    witness_counts=Counter(); bound_proofs={}; phase='closure'
    with Path(audit['proof_file']).open() as f:
        for index,line in enumerate(f):
            w=json.loads(line);kind=w['kind'];witness_counts[kind]+=1
            if kind=='bound_redundant':
                phase='bounds'; assert w['row'] not in bound_proofs
                bound_proofs[w['row']]=w;continue
            assert phase=='closure'
            r=w['row']; terms=defaultdict(Fraction)
            for v,a in original['rows'][r].items():
                root=find(v)
                if root not in zeros:terms[root]+=a
            terms={v:a for v,a in terms.items() if a}
            assert terms=={v:Fraction(a) for v,a in w['terms']}, (index,r)
            assert original['rhs'][r]==0
            s=original['senses'][r]
            if kind=='zero':
                assert terms and ((s in {'E','L'} and all(a>0 for a in terms.values())) or (s in {'E','G'} and all(a<0 for a in terms.values())))
                assert all(lo[v]==0 and (hi[v] is None or hi[v]>=0) for v in terms)
                zeros.update(terms)
            else:
                assert kind=='identify'
                v,u=w['keep'],w['remove']
                assert s=='E' and set(terms)=={v,u} and terms[v]==-terms[u] and terms[v]!=0
                assert find(v)==v and find(u)==u and v not in zeros and u not in zeros
                parent[u]=v;lo[v]=max(lo[v],lo[u])
                hs=[h for h in [hi[v],hi[u]] if h is not None];hi[v]=min(hs) if hs else None
                assert hi[v] is None or lo[v]<=hi[v]
    mapping={v:None if find(v) in zeros else find(v) for v in parent}
    assert mapping==audit['variable_map']
    groups=defaultdict(list)
    for v,root in mapping.items():
        if root is not None:groups[root].append(v)
    expected_bounds={};expected_integer=set();expected_objective={}
    for root,vs in groups.items():
        lower=max(original['bounds'][v][0] for v in vs)
        upper=[original['bounds'][v][1] for v in vs if original['bounds'][v][1] is not None]
        expected_bounds[root]=(lower,min(upper) if upper else None)
        if any(v in original['integer'] for v in vs):expected_integer.add(root)
        c=sum((original['objective'].get(v,Fraction(0)) for v in vs),Fraction(0))
        if c:expected_objective[root]=c
    assert expected_bounds==emitted['bounds']
    assert expected_integer==emitted['integer']
    assert expected_objective==emitted['objective']
    expected_changes={v:{'old':[str(a) if a is not None else None for a in original['bounds'][v]],'new':[str(a) if a is not None else None for a in b]} for v,b in expected_bounds.items() if b!=original['bounds'][v]}
    assert expected_changes==audit['changed_bounds']
    expected_obj_changes={v:{'old':str(original['objective'].get(v,0)),'new':str(expected_objective.get(v,0))} for v in expected_bounds if original['objective'].get(v,0)!=expected_objective.get(v,0)}
    assert expected_obj_changes==audit['changed_objective']
    transformed={}
    for r,t in original['rows'].items():
        nt=defaultdict(Fraction)
        for v,a in t.items():
            if mapping[v] is not None:nt[mapping[v]]+=a
        transformed[r]={v:a for v,a in nt.items() if a}
    removed=audit['removed_rows']
    assert set(emitted['rows'])==set(original['rows'])-set(removed)
    assert set(bound_proofs)=={r for r,reason in removed.items() if reason=='bound_redundant'}
    for r,reason in removed.items():
        b=original['rhs'][r];s=original['senses'][r];t=transformed[r]
        if reason=='constant_tautology':
            assert not t and valid_constant(s,b)
        else:
            assert reason=='bound_redundant';w=bound_proofs[r]
            low,high=interval(t,expected_bounds)
            assert w['sense']==s and Fraction(w['rhs'])==b
            assert w['minimum']==(str(low) if low is not None else None)
            assert w['maximum']==(str(high) if high is not None else None)
            assert {v:Fraction(a) for v,a,l,h in w['terms']}==t
            assert all((Fraction(l),Fraction(h) if h is not None else None)==expected_bounds[v] for v,a,l,h in w['terms'])
            assert (s=='L' and high is not None and high<=b) or (s=='G' and low is not None and low>=b) or (s=='E' and low==high==b)
    for r,t in emitted['rows'].items():
        assert t==transformed[r]
        assert emitted['senses'][r]==original['senses'][r]
        assert emitted['rhs'][r]==original['rhs'][r]
    stats={'status':'PASS','input_sha256':audit['input_sha256'],'output_sha256':audit['output_sha256'],
           'witness_counts':dict(witness_counts),
           'checked_original_rows':len(original['rows']),'checked_emitted_rows':len(emitted['rows']),
           'checked_original_variables':len(parent),'checked_emitted_variables':len(emitted['bounds']),
           'original_integer_variables':len(original['integer']),'final_integer_variables':len(emitted['integer']),
           'original_constraint_nonzeros':sum(map(len,original['rows'].values())),
           'final_constraint_nonzeros':sum(map(len,emitted['rows'].values())),
           'checks':['input/output hashes','independent exact MPS parse','every ordered proof witness against original rows','complete variable reconstruction map','all inherited bounds and integrality','complete objective identity','all retained row coefficients, senses, and RHS','all removed constant and interval-redundant rows','exact changed-bound and changed-objective audit tables'],
           'solver_used':False,'solver_readability_tested':False}
    assert stats['checked_original_rows']==audit['counts']['original_constraints']
    assert stats['checked_emitted_rows']==audit['counts']['final_constraints']
    assert stats['checked_original_variables']==audit['counts']['original_variables']
    assert stats['checked_emitted_variables']==audit['counts']['final_variables']
    assert stats['original_integer_variables']==audit['counts']['original_integer_variables']
    assert stats['final_integer_variables']==audit['counts']['final_integer_variables']
    assert stats['original_constraint_nonzeros']==audit['counts']['original_constraint_nonzeros']
    assert stats['final_constraint_nonzeros']==audit['counts']['final_constraint_nonzeros']
    Path('output/verification.json').write_text(json.dumps(stats,indent=2)+'\n')
    print(json.dumps(stats,indent=2))

if __name__=='__main__': main()
