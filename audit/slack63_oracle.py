#!/usr/bin/env python3
"""Independent exact point oracle for actual slack/difference model bytes."""
from pathlib import Path
from fractions import Fraction as Q
import json,random,sys,time,hashlib
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'tools'))
from prepare_affine import parse_mps
SEED=0x630091

def value(row,point):return sum(c*point[i] for i,c in row['terms'].items())
def check(model,point,integer):
    assert len(model['vars'])==len(point)
    for v,x in zip(model['vars'],point):
        assert not integer or not v['integer'] or x.denominator==1
        assert v['lower'] is None or x>=v['lower']
        assert v['upper'] is None or x<=v['upper']
    for row in model['rows']:
        lhs=value(row,point);rhs=row['rhs'];assert {'E':lhs==rhs,'L':lhs<=rhs,'G':lhs>=rhs}[row['sense']],row['name']
def obj(model,point):return model['objective'][0]+sum(c*point[i] for i,c in model['objective'][1].items())
def run():
    start=time.perf_counter();rng=random.Random(SEED);directory=Path('/Users/bhz/Code/reform_test/runs/test63-nomf-B1');a=parse_mps(directory/'input/model.mps');b=parse_mps(directory/'output/reformulated.mps');height=a['var_index']['h'];loads=[a['rows'][a['row_index'][f'c{i}']] for i in range(21,112)];groups=[a['rows'][a['row_index'][f'c{i}']] for i in range(1,21)];records=[]
    for mode in range(103):
        point=[Q(0)]*len(a['vars'])
        for group in groups:
            ids=sorted(group['terms'])
            if mode==102:
                for i in ids:point[i]=Q(1,len(ids))
            else:point[ids[0] if mode==0 else ids[-1] if mode==1 else rng.choice(ids)]=Q(1)
        peak=max(value(row,point) for row in loads);point[height]=peak+(Q(7,3) if mode%3==0 else Q(0));check(a,point,mode!=102)
        output=[]
        for v in b['vars']:
            if v['name'] in a['var_index']:output.append(point[a['var_index'][v['name']]])
            else:
                assert v['name'].startswith('S');j=int(v['name'][1:]);assert 0<=j<91;output.append(-value(loads[j],point))
        check(b,output,mode!=102);assert obj(a,point)==obj(b,output)
        reverse=[Q(0) if v['name']=='x2' else output[b['var_index'][v['name']]] for v in a['vars']];assert point==reverse
        for j,row in enumerate(loads):assert output[b['var_index'][f'S{j:03d}']]==-value(row,reverse)
        bad=list(point);bad[height]=peak-Q(1,2);assert min(-value(row,bad) for row in loads)==Q(-1,2)
        records.append({'scenario':mode,'integer':mode!=102,'height':str(point[height]),'objective':str(obj(a,point)),'below_peak_slack':str(Q(-1,2))})
    result={'status':'PASS','seed':SEED,'complete_actual_points':len(records),'integer_points':102,'fractional_points':1,'roundtrip_coordinates_per_point':len(a['vars'])+len(b['vars']),'scenarios':records,'source_sha256':hashlib.sha256((directory/'input/model.mps').read_bytes()).hexdigest(),'target_sha256':hashlib.sha256((directory/'output/reformulated.mps').read_bytes()).hexdigest(),'elapsed_seconds':time.perf_counter()-start,'scope':'Independent Fraction point oracle, supplemental to actual universal RPX certificate.'};(ROOT/'audit/slack63_oracle.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps({k:result[k] for k in ['status','complete_actual_points','elapsed_seconds']}))
if __name__=='__main__':run()
