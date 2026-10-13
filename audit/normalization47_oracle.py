#!/usr/bin/env python3
"""Independent exact point-level exchange oracle; never an acceptance authority."""
from fractions import Fraction as Q
from pathlib import Path
import hashlib,itertools,json,random,sys,time
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
from prepare_affine import parse_mps
SEED=0x47D0A1

def exchange(point,removed,witnesses,coefficients,limit):
    original=list(point);current=list(point);stages=[]
    for v in removed:
        old=list(current);candidates=witnesses[v];assert len(candidates)==len(set(candidates))==limit
        assert all(i not in removed for i in candidates)
        prefix=[old[v]]
        for w in candidates:prefix.append(prefix[-1]*old[w])
        assert prefix[-1]==0 # cardinality forbids all limit+1 inputs equal to one
        current[v]=0
        for j,w in enumerate(candidates):current[w]=old[w]+prefix[j]-prefix[j+1]
        assert all(x in (0,1) for x in current) and sum(current)==sum(original)<=limit
        deltas=[]
        for row in coefficients:
            expected=sum((row[w]-row[v])*(prefix[j]-prefix[j+1]) for j,w in enumerate(candidates))
            assert all(row[w]>=row[v] for w in candidates)
            actual=sum(a*(new-before) for a,new,before in zip(row,current,old))
            assert actual==expected>=0;deltas.append(actual)
        stages.append({'removed':v,'moved':old[v],'last_prefix':prefix[-1],'row_deltas':[str(x) for x in deltas]})
    assert all(current[v]==0 for v in removed)
    return current,stages

def feasible(model,values):
    assert len(values)==len(model['vars'])
    for v,x in zip(model['vars'],values):
        assert not v['integer'] or x.denominator==1
        assert v['lower'] is None or x>=v['lower']
        assert v['upper'] is None or x<=v['upper']
    for row in model['rows']:
        lhs=sum(c*values[i] for i,c in row['terms'].items());rhs=row['rhs']
        assert {'E':lhs==rhs,'G':lhs>=rhs,'L':lhs<=rhs}[row['sense']],row['name']

def objective(model,values):
    constant,terms=model['objective'];return constant+sum(c*values[i] for i,c in terms.items())

def run():
    started=time.perf_counter();rng=random.Random(SEED);generic=[];assignments=0
    for limit in range(1,11):
        n=limit+7;removed=list(range(4));retained=list(range(4,n));witnesses={v:rng.sample(retained,limit) for v in removed}
        coefficients=[]
        for _ in range(5):
            base=Q(rng.randint(-15,20),rng.randint(1,11));row=[base-Q(rng.randint(0,9),rng.randint(1,9)) for _ in removed]+[base+Q(rng.randint(0,12),rng.randint(1,9)) for _ in retained];coefficients.append(row)
        samples=[]
        if limit<=3:
            for k in range(limit+1):
                for ids in itertools.combinations(range(n),k):samples.append(set(ids))
        else:
            samples=[set(),set(removed),set(rng.sample(range(n),limit))]
            samples.extend(set(rng.sample(range(n),rng.randint(0,limit))) for _ in range(100))
        for ids in samples:
            old=[int(i in ids) for i in range(n)];new,stages=exchange(old,removed,witnesses,coefficients,limit)
            # Deliberately different exact constants, signs, and fractional weights.
            for weight in [Q(-7,13),Q(0),Q(4,9)]:assert Q(29,17)+weight*sum(old)==Q(29,17)+weight*sum(new)
            assignments+=1
        generic.append({'cardinality_limit':limit,'binary_variables':n,'removed_variables':len(removed),'rows':len(coefficients),'checked_points':len(samples),'coefficients_include_negative_and_fractional':True})
    run=Path('/Users/bhz/Code/reform_test/runs/test47-nomf-B1');a=parse_mps(run/'input/model.mps');b=parse_mps(run/'output/reformulated.mps');h=json.loads((run/'output/audit.json').read_text());binary=[i for i,v in enumerate(a['vars']) if v['integer']];local={i:j for j,i in enumerate(binary)}
    removed=[local[a['var_index'][name]] for name in h['removed_binary_variables']];witnesses={local[a['var_index'][name]]:[local[a['var_index'][w]] for w in ws] for name,ws in h['retained_dominator_witnesses'].items()}
    rows=[[a['rows'][a['row_index'][name]]['terms'].get(i,Q(0)) for i in binary] for name in h['covering_rows']]
    rows=[[c.numerator if c.denominator==1 else c for c in row] for row in rows]
    chosen=[set(),set(removed[:20])]
    chosen.extend({v,*witnesses[v][:-1]} for v in removed)
    chosen.extend(set(rng.sample(range(len(binary)),rng.randint(0,20))) for _ in range(256))
    actual=[]
    for case,ids in enumerate(chosen):
        old=[int(i in ids) for i in range(len(binary))];new,stages=exchange(old,removed,witnesses,rows,20)
        source=[Q(0)]*len(a['vars']);source[a['var_index']['x151']]=a['vars'][a['var_index']['x151']]['upper']
        current=list(source)
        for i,j in local.items():source[i]=old[j];current[i]=new[j]
        feasible(a,source);feasible(a,current);target=[]
        for v in b['vars']:
            names=h['aggregated_binary_groups'].get(v['name'],[v['name']]);target.append(sum(current[a['var_index'][name]] for name in names))
        feasible(b,target);assert objective(a,source)==objective(b,target)
        reverse=[Q(0)]*len(a['vars'])
        for i,v in enumerate(a['vars']):
            if v['name'] in b['var_index']:reverse[i]=target[b['var_index'][v['name']]]
        for name,members in h['aggregated_binary_groups'].items():
            count=target[b['var_index'][name]];assert count in (0,1,2)
            reverse[a['var_index'][members[0]]]=Q(int(count>=1));reverse[a['var_index'][members[1]]]=Q(int(count==2))
        feasible(a,reverse);assert objective(a,reverse)==objective(b,target)
        assert sum(source[i] for i in binary)==sum(reverse[i] for i in binary)
        actual.append({'case':case,'selected_source_indices':[binary[j] for j in sorted(ids)],'moves':int(sum(stage['moved'] for stage in stages)),'objective':str(objective(a,source))})
    out={'status':'PASS','seed':SEED,'generic_models':generic,'generic_point_count':assignments,'actual_point_count':len(actual),'actual_points':actual,'source_sha256':hashlib.sha256((run/'input/model.mps').read_bytes()).hexdigest(),'target_sha256':hashlib.sha256((run/'output/reformulated.mps').read_bytes()).hexdigest(),'elapsed_seconds':time.perf_counter()-started,'scope':'Independent Fraction point-level oracle. This is supplemental to complete RPX verification and does not certify arbitrary points by itself.'}
    path=ROOT/'audit/normalization47_oracle.json';path.write_text(json.dumps(out,indent=2)+'\n');print(json.dumps({k:out[k] for k in ('status','seed','generic_point_count','actual_point_count','elapsed_seconds')}))
if __name__=='__main__':run()
