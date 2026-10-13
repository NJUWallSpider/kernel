#!/usr/bin/env python3
"""One fixed alternating-pair follow-up; never retry or replace raw evidence."""
from pathlib import Path
import datetime,hashlib,json,statistics,subprocess,time
ROOT=Path(__file__).resolve().parents[1]
PLAN=ROOT/'bench/v10_order_sensitivity_plan.json'
OUT=ROOT/'bench/results/v10-order-sensitivity'
def sha(p):
    h=hashlib.sha256()
    with Path(p).open('rb') as f:
        for b in iter(lambda:f.read(1<<20),b''):h.update(b)
    return h.hexdigest()
def now():return datetime.datetime.now(datetime.timezone.utc).isoformat()
def demand(c,m):
    if not c:raise RuntimeError(m)
def dist(x):return {'min':min(x),'median':statistics.median(x),'max':max(x)}
def fmt(x,scale=1):return ' / '.join(f'{v:.3f}' for v in (min(x)/scale,statistics.median(x)/scale,max(x)/scale))
def sem(result):return {k:v for k,v in result.items() if k not in ['read_us','model_decode_us','proof_decode_us','execute_us','total_us','statistics']}
def check_artifacts(workload):
    seen={}
    for name,item in workload['artifacts'].items():
        p=Path(item['path']);m={'bytes':p.stat().st_size,'sha256':sha(p)};demand(m=={k:item[k] for k in m},f'{workload["name"]}/{name}: artifact drift');seen[name]=m
    return seen

def report(raw):
    plan=raw['plan'];lines=['# Bounded V10 order-sensitivity follow-up','',
      'This is one additional fixed experiment on four unchanged old mathematical tasks. It supplements the original 31-workload sequential A/B report; it neither replaces those results nor changes the candidate. No workload preparation or RSS measurement was performed.', '',
      f'Plan `bench/v10_order_sensitivity_plan.json`, SHA-256 `{raw["plan_sha256"]}`. Raw evidence `bench/results/v10-order-sensitivity/raw.json`. Old binary `{plan["old_binary"]["sha256"]}`; candidate `{plan["new_binary"]["sha256"]}`.', '',
      'Each workload has one old and one candidate warmup, recorded but excluded from samples, followed by nine fresh-process pairs. Zero-indexed even pairs run old then candidate; odd pairs run candidate then old. There are 72 timed calls and eight excluded warmups. All calls must succeed with exactly the original statistics, claims and limits. Input artifacts and executable identities are checked before and after each workload.', '',
      f'Isolation declaration: {plan["isolation_declaration"]}', '',
      'Times are milliseconds. A paired difference is candidate minus old within that pair, not the difference of two unrelated medians. Positive means slower candidate. All observations and outliers remain. These nine pairs support a bounded sensitivity check, not a formal significance claim or guaranteed performance bound.', '',
      '| Workload | Original sequential execute medians old → new | Alternating old execute min / median / max | Alternating new execute min / median / max | Paired execute difference min / median / max | Positive / zero / negative pairs |',
      '|---|---:|---:|---:|---:|---:|']
    summaries=[]
    for record,task in zip(raw['workloads'],plan['workloads']):
        pairs=record['pairs'];a=[p['calls']['old']['result']['execute_us'] for p in pairs];b=[p['calls']['new']['result']['execute_us'] for p in pairs];delta=[y-x for x,y in zip(a,b)];pa=[p['calls']['old']['wall_ns'] for p in pairs];pb=[p['calls']['new']['wall_ns'] for p in pairs];pd=[y-x for x,y in zip(pa,pb)]
        original=task['original_sequential'];counts={'positive':sum(d>0 for d in delta),'zero':sum(d==0 for d in delta),'negative':sum(d<0 for d in delta)}
        summaries.append({'name':task['name'],'old_execute_us':dist(a),'new_execute_us':dist(b),'paired_execute_delta_us':dist(delta),'paired_execute_relative_delta_percent':dist([100*d/x for d,x in zip(delta,a)]),'execute_pair_signs':counts,'old_process_ns':dist(pa),'new_process_ns':dist(pb),'paired_process_delta_ns':dist(pd),'process_pair_signs':{'positive':sum(d>0 for d in pd),'zero':sum(d==0 for d in pd),'negative':sum(d<0 for d in pd)},'order_groups':{}})
        # JSON object keys explicitly name order groups, retaining the 5/4 split.
        summaries[-1]['order_groups']={}
        for key,order in [('old_then_new',['old','new']),('new_then_old',['new','old'])]:
            selected=[p for p in pairs if p['order']==order];summaries[-1]['order_groups'][key]={'count':len(selected),'execute_delta_us':dist([p['calls']['new']['result']['execute_us']-p['calls']['old']['result']['execute_us'] for p in selected]),'process_delta_ns':dist([p['calls']['new']['wall_ns']-p['calls']['old']['wall_ns'] for p in selected])}
        lines.append('| '+' | '.join([task['name'],f'{statistics.median(original["old"]["execute_us"])/1000:.3f} → {statistics.median(original["new"]["execute_us"])/1000:.3f}',fmt(a,1000),fmt(b,1000),fmt(delta,1000),f'{counts["positive"]} / {counts["zero"]} / {counts["negative"]}'])+' |')
    lines+=['','| Workload | Original sequential process medians old → new | Alternating old process min / median / max | Alternating new process min / median / max | Paired process difference min / median / max | Positive / zero / negative pairs |','|---|---:|---:|---:|---:|---:|']
    for record,task,summary in zip(raw['workloads'],plan['workloads'],summaries):
        pairs=record['pairs'];a=[p['calls']['old']['wall_ns'] for p in pairs];b=[p['calls']['new']['wall_ns'] for p in pairs];delta=[y-x for x,y in zip(a,b)];c=summary['process_pair_signs'];original=task['original_sequential']
        lines.append('| '+' | '.join([task['name'],f'{statistics.median(original["old"]["process_ns"])/1e6:.3f} → {statistics.median(original["new"]["process_ns"])/1e6:.3f}',fmt(a,1e6),fmt(b,1e6),fmt(delta,1e6),f'{c["positive"]} / {c["zero"]} / {c["negative"]}'])+' |')
    lines+=['','## Within-pair order check','','There are five old-then-new pairs and four new-then-old pairs. These subgroup medians retain the order information; they are not extra runs or independent replication.','','| Workload | Execute delta median old→new order | Execute delta median new→old order | Process delta median old→new order | Process delta median new→old order |','|---|---:|---:|---:|---:|']
    for s in summaries:
        a,b=[s['order_groups'][x] for x in ['old_then_new','new_then_old']];lines.append(f'| {s["name"]} | {a["execute_delta_us"]["median"]/1000:+.3f} | {b["execute_delta_us"]["median"]/1000:+.3f} | {a["process_delta_ns"]["median"]/1e6:+.3f} | {b["process_delta_ns"]["median"]/1e6:+.3f} |')
    lines+=['','## Interpretation and limits','']
    for s in summaries:
        counts=s['execute_pair_signs'];lines.append(f'- `{s["name"]}`: candidate execution is slower in {counts["positive"]}/9 pairs, equal in {counts["zero"]}/9 and faster in {counts["negative"]}/9; paired median difference {s["paired_execute_delta_us"]["median"]/1000:+.3f} ms. The paired relative-difference median is {s["paired_execute_relative_delta_percent"]["median"]:+.2f}%; interpret it with the absolute time above.')
    lines+=['','This single bounded follow-up controls the coarse old-first/new-later order more closely, but does not eliminate host activity, clock/thermal state, scheduling noise or all order effects. It cannot identify the internal implementation cause of a regression. The small rational workload remains below one millisecond of verification, so relative changes should not be generalized from its tiny absolute cost. There is no new RSS evidence and no memory-improvement claim. The original sequential results and every new pair remain preserved regardless of direction. No additional resampling or candidate modification is part of this experiment.','']
    raw['paired_summary']=summaries
    return '\n'.join(lines)

def main():
    demand(not (OUT/'raw.json').exists(),'Refusing to repeat or overwrite this one bounded experiment')
    plan=json.loads(PLAN.read_text());demand(plan['status']=='FIXED_BEFORE_MEASUREMENT' and plan['repetitions']==9 and len(plan['workloads'])==4 and plan['timed_calls']==72 and plan['warmup_calls']==8,'Wrong fixed plan')
    demand(sha(ROOT/plan['source_comparison']['path'])==plan['source_comparison']['sha256'],'Original comparison changed')
    OUT.mkdir(parents=True,exist_ok=True);raw={'status':'RUNNING','started_utc':now(),'plan':plan,'plan_sha256':sha(PLAN),'script_sha256':sha(Path(__file__)),'workloads':[]}
    def save():(OUT/'raw.json').write_text(json.dumps(raw,indent=2)+'\n')
    def binaries():
        hashes={v:sha(Path(plan[v+'_binary']['path'])) for v in ['old','new']};demand(all(hashes[v]==plan[v+'_binary']['sha256'] for v in hashes),'Binary identity drift');return hashes
    def call(version,task):
        command=[plan[version+'_binary']['path'],*task['verify_arguments']];start=time.perf_counter_ns();p=subprocess.run(command,capture_output=True,text=True);elapsed=time.perf_counter_ns()-start
        try:r=json.loads(p.stdout)
        except json.JSONDecodeError:r={'status':'IO_ERROR','unparsed_stdout':p.stdout}
        return {'command':command,'exit_code':p.returncode,'wall_ns':elapsed,'stdout':p.stdout,'stderr':p.stderr,'result':r}
    def validate(item,task):
        demand(item['exit_code']==0 and item['result'].get('status')=='VERIFIED',task['name']+': non-VERIFIED call')
        demand(item['result']['statistics']==task['expected_statistics'],task['name']+': changed statistics')
        demand(sem(item['result'])==task['expected_result_semantics'],task['name']+': changed claims/limits')
    try:
        raw['binary_hashes_before']=binaries();save()
        for task in plan['workloads']:
            record={'name':task['name'],'artifacts_before':check_artifacts(task),'binary_hashes_before':binaries(),'warmups':[],'pairs':[]};raw['workloads'].append(record);save()
            for version in plan['warmup_order']:
                item=call(version,task);record['warmups'].append({'version':version,**item});save();validate(item,task)
            for index in range(9):
                order=['old','new'] if index%2==0 else ['new','old'];pair={'index':index,'order':order,'calls':{}};record['pairs'].append(pair)
                for version in order:
                    item=call(version,task);pair['calls'][version]=item;save();validate(item,task)
            record['artifacts_after']=check_artifacts(task);record['binary_hashes_after']=binaries();save();print(task['name'],'9 paired samples VERIFIED',flush=True)
        raw['binary_hashes_after']=binaries();raw['status']='ALL_VERIFIED_ONE_BOUNDED_FOLLOWUP';raw['finished_utc']=now();raw['timed_calls']=sum(2*len(w['pairs']) for w in raw['workloads']);raw['warmup_calls']=sum(len(w['warmups']) for w in raw['workloads']);demand(raw['timed_calls']==72 and raw['warmup_calls']==8,'Call count');save()
        text=report(raw);(OUT/'ORDER_SENSITIVITY_REPORT.md').write_text(text);raw['report']={'path':str((OUT/'ORDER_SENSITIVITY_REPORT.md').relative_to(ROOT)),'sha256':sha(OUT/'ORDER_SENSITIVITY_REPORT.md')};save();print(json.dumps({'status':raw['status'],'timed_calls':raw['timed_calls'],'warmups':raw['warmup_calls'],'report':raw['report']}),flush=True)
    except Exception as error:
        raw['status']='FAILED_EVIDENCE_RETAINED_NO_RETRY';raw['error']=str(error);raw['finished_utc']=now();save();raise
if __name__=='__main__':main()
