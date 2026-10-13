#!/usr/bin/env python3
"""Independent exact OR/dominance construction and complete actual point checks."""
from fractions import Fraction as Q
from pathlib import Path
import hashlib,json,random,sys,time
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'tools'))
from prepare_affine import parse_mps
SEED=0x8700C0

def run():
    started=time.perf_counter();rng=random.Random(SEED);generic=0
    # Independent local family: all assignments for group sizes1..12, exact
    # unequal fractional nonnegative costs; shared replacement has cheapest cost.
    for n in range(1,13):
        cheap=Q(rng.randrange(1,8),rng.randrange(1,9));cost=[cheap]+[cheap+Q(rng.randrange(0,9),rng.randrange(1,9)) for _ in range(n-1)]
        for mask in range(1<<n):
            x=[(mask>>j)&1 for j in range(n)];y=max(x)
            assert y in (0,1) and all(t<=y for t in x) and y<=sum(x)
            assert cheap*y<=sum(c*t for c,t in zip(cost,x))
            # Any source covering row's nonempty selected subset remains covered
            # if every original column in it is mapped to this shared survivor.
            for subset in [list(range(n)),list(range(0,n,2))]:
                if sum(x[i] for i in subset)>=1:assert y>=1
            generic+=1
    directory=Path('/Users/bhz/Code/reform_test/runs/test87-nomf-B1');a=parse_mps(directory/'input/model.mps');b=parse_mps(directory/'output/reformulated.mps');h=json.loads((directory/'output/audit.json').read_text())
    assert all(c==1 for m in [a,b] for r in m['rows'] for c in r['terms'].values())
    costs_a=[int(a['objective'][1][i]) for i in range(len(a['vars']))];costs_b=[int(b['objective'][1][i]) for i in range(len(b['vars']))]
    def valid(model,p):
        assert len(p)==len(model['vars'])
        for v,x in zip(model['vars'],p):assert x.denominator==1 and v['lower']<=x<=v['upper']
        assert all(sum(p[i] for i in r['terms'])>=r['rhs'] for r in model['rows'])
    records=[]
    for case in range(18):
        p=[1 if case==0 else 0 for _ in a['vars']]
        if case:
            for row in a['rows']:
                ids=sorted(row['terms']);p[ids[0] if case==1 else rng.choice(ids)]=1
            if case>1:
                for i in rng.sample(range(len(p)),min(len(p),(case-1)*1500)):p[i]=1
        valid(a,p);original_cost=sum(c*x for c,x in zip(costs_a,p));current=list(p);stage_costs=[]
        for stage in h['stages']:
            old=list(current);groups={}
            for v,w in stage['column_replacements'].items():groups.setdefault(a['var_index'][w],[]).append(a['var_index'][v])
            for w,vs in groups.items():current[w]=max([old[w]]+[old[i] for i in vs])
            for v in stage['empty_columns']+list(stage['column_replacements']):current[a['var_index'][v]]=0
            for v in stage['fixed_one']:
                i=a['var_index'][v];assert old[i]==1;current[i]=1
            cost=sum(c*x for c,x in zip(costs_a,current));assert cost<=sum(c*x for c,x in zip(costs_a,old));stage_costs.append(cost)
        target=[current[a['var_index'][v['name']]] for v in b['vars']];valid(b,target)
        backward=[target[b['var_index'][v['name']]] if v['name'] in b['var_index'] else 0 for v in a['vars']];valid(a,backward)
        final_cost=sum(c*x for c,x in zip(costs_b,target));assert final_cost==sum(c*x for c,x in zip(costs_a,backward))==stage_costs[-1]<=original_cost
        records.append({'case':case,'original_objective':original_cost,'stage_objectives':stage_costs,'target_and_lift_objective':final_cost})
    result={'status':'PASS','seed':SEED,'generic_or_assignments':generic,'generic_max_group_size':12,'actual_complete_forward_reverse_points':len(records),'actual_points':records,'source_sha256':hashlib.sha256((directory/'input/model.mps').read_bytes()).hexdigest(),'target_sha256':hashlib.sha256((directory/'output/reformulated.mps').read_bytes()).hexdigest(),'elapsed_seconds':time.perf_counter()-started,'scope':'Supplemental independent exact point oracle; actual universal acceptance requires complete RPX verification.'};(ROOT/'audit/setcover87_oracle.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps({k:result[k] for k in ['status','generic_or_assignments','actual_complete_forward_reverse_points','elapsed_seconds']}))
if __name__=='__main__':run()
