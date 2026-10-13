#!/usr/bin/env python3
"""Attack the complete caller request while reusing the complete valid test36 RPX."""
from pathlib import Path
import json,hashlib,subprocess,time
ROOT=Path(__file__).resolve().parents[1]
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
    root=ROOT/'cases/test36';metadata=root/'preparation.json';meta=json.loads(metadata.read_text());assert meta['status']=='VERIFIED'
    kernel=Path(meta['kernel_binary']['path']);expected=meta['kernel_binary']['sha256'];assert sha(kernel)==expected
    request=json.loads((root/'request.json').read_text());assert len(request['claims'])==3 and len(request['improvements'])==1
    request['claims'][2]['input_halfspace']['terms'].pop()
    path=root/'attacks/full_request_binding.request.json';path.write_text(json.dumps(request,separators=(',',':'))+'\n')
    command=[str(kernel),'verify',str(root/'source.mcm'),str(root/'target.mcm'),str(root/'proof.rpx'),str(path)]
    before=sha(kernel);start=time.perf_counter();run=subprocess.run(command,capture_output=True,text=True);after=sha(kernel);assert before==after==expected
    result=json.loads(run.stdout);assert run.returncode!=0 and result['status']=='INVALID'
    evidence={'mutation':'full_request_binding','rule_broken':'The complete caller request changes its input-domain halfspace while the complete certificate retains the original domain; no claim or improvement is omitted from the request.','status':'INVALID','scope':'Complete three-direction plus strict-improvement certificate and complete request','runs':[{'command':command,'exit_code':run.returncode,'stdout':run.stdout,'stderr':run.stderr,'wall_seconds':time.perf_counter()-start,'binary_sha256_before':before,'binary_sha256_after':after}],'rpx':str(root/'proof.rpx'),'rpx_sha256':sha(root/'proof.rpx'),'request':str(path),'request_sha256':sha(path)}
    receipt=root/'attacks/full_request_binding.json';receipt.write_text(json.dumps(evidence,indent=2)+'\n')
    meta['negative_checks']=[x for x in meta['negative_checks'] if x['mutation']!='full_request_binding']+[{'mutation':'full_request_binding','status':'INVALID','receipt':str(receipt.relative_to(ROOT))}]
    allruns=meta['kernel_runs']+[meta['former_100m_run'],meta['positive_noninteger_terminal_control']]+[r for n in meta['negative_checks'] for r in json.loads((ROOT/n['receipt']).read_text())['runs']]
    assert all(r['binary_sha256_before']==r['binary_sha256_after']==expected for r in allruns)
    meta['fixed_identity_validation']={'status':'PASS','commands':len(allruns),'binary_sha256':expected};meta['attack_status']='ALL_'+str(len(meta['negative_checks']))+'_INVALID';meta['preparers']['tools/check_test36_request_binding.py']=sha(Path(__file__));meta['full_scope_status']='KERNEL_VERIFIED_PENDING_INDEPENDENT_REPORT_REVIEW';metadata.write_text(json.dumps(meta,indent=2)+'\n');print(json.dumps({'status':'INVALID','attack_count':len(meta['negative_checks']),'fixed_commands':len(allruns)}))
if __name__=='__main__':main()
