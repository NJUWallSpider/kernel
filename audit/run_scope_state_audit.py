#!/usr/bin/env python3
"""Test the candidate's private Facts state without changing its measured source.

Copies the candidate workspace into a temporary directory and appends a test-only
module hook there. The reference is an ordinary fully copied BTreeMap. Production,
frozen checkpoints, candidate verify.rs and its performance metadata are untouched.
"""
from pathlib import Path
import argparse
import hashlib
import json
import re
import shutil
import subprocess
import tempfile
import time

ROOT=Path(__file__).resolve().parents[1]


def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()


if __name__=="__main__":
    parser=argparse.ArgumentParser()
    parser.add_argument("--candidate",type=Path,default=ROOT/"bench/shared-scope-prototype")
    parser.add_argument("--output",type=Path,default=ROOT/"audit/scope_state_audit.json")
    args=parser.parse_args();candidate=args.candidate.resolve();source=candidate/"crates/core/src/verify.rs";tests=candidate/"crates/core/src/scope_state_audit.rs"
    before=sha(source);start=time.perf_counter()
    with tempfile.TemporaryDirectory(prefix="rpx-scope-audit-") as directory:
        destination=Path(directory)
        for name in ["Cargo.toml","Cargo.lock"]:shutil.copy2(candidate/name,destination/name)
        shutil.copytree(candidate/"crates",destination/"crates",ignore=shutil.ignore_patterns("target",".git","__pycache__"))
        staged=destination/"crates/core/src/verify.rs"
        with staged.open("a") as file:file.write('\n#[cfg(test)]\n#[path = "scope_state_audit.rs"]\nmod scope_state_audit;\n')
        command=["cargo","test","--manifest-path",str(destination/"Cargo.toml"),"-p","kernel-core","--lib","scope_state_audit","--locked","--","--nocapture"]
        result=subprocess.run(command,capture_output=True,text=True)
        raw=result.stdout+"\n"+result.stderr
    assert sha(source)==before,"candidate verifier changed during audit"
    match=re.search(r"traces=(\d+), operations=(\d+), defines=(\d+), drops=(\d+), child_forks=(\d+), expected_rejections=(\d+)",raw)
    summary={"status":"PASS" if result.returncode==0 else "FAIL","candidate":str(candidate),"candidate_verify_sha256":before,
             "test_source_sha256":sha(tests),"seed_base":"0x52505853434f5045","deep_scope_levels":64,"elapsed_seconds":time.perf_counter()-start,
             "execution":"temporary copied candidate plus test-only child module; no production or measured source changes",
             "tests":7,"exit_code":result.returncode}
    if match:summary.update(dict(zip(["traces","operations","defines","drops","child_forks","expected_rejections"],map(int,match.groups()))))
    args.output.parent.mkdir(parents=True,exist_ok=True);args.output.write_text(json.dumps(summary,indent=2)+"\n");args.output.with_suffix(".log").write_text(raw)
    print(json.dumps(summary,indent=2))
    if result.returncode:print(raw);raise SystemExit(result.returncode)
