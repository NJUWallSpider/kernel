#!/usr/bin/env python3
"""Replay the preserved >256MiB test46 merged proof via direct JSON compilation."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import shutil
import tempfile
import time

from replay import ROOT, run, sha


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--kernel",type=Path,default=ROOT/"target/release/rpx")
    args=parser.parse_args()
    directory=Path(__file__).resolve().parent
    case=ROOT/"cases/test46"
    fixture=case/"combined-attempt.rpa"
    request=case/"combined-request.json"
    started=time.perf_counter()
    with tempfile.TemporaryDirectory(prefix="kernel-compiler-merged-") as temporary:
        temp=Path(temporary)
        binary=temp/"rpx";shutil.copy2(args.kernel.resolve(),binary);binary.chmod(0o500)
        raw=temp/"certificate.json";rpx=temp/"proof.rpx"
        with fixture.open("rb") as source,raw.open("wb") as target:
            if source.readline(32)!=b"RPA 5\n":raise ValueError("Unexpected preserved fixture header")
            shutil.copyfileobj(source,target,length=4*1024*1024)
        compilation=run(binary,"compile",raw,rpx)
        verification=run(binary,"verify",case/"source.mcm",case/"target.mcm",rpx,request) if compilation["exit_code"]==0 else None
        expected={}
        for line in (directory/"results.jsonl").read_text().splitlines():
            piece=json.loads(line)
            if piece["case"]!="test46":continue
            for key,value in piece["verification"]["result"]["statistics"].items():
                expected[key]=max(expected.get(key,0),value) if key=="peak_live_facts" else expected.get(key,0)+value
        actual=verification["result"].get("statistics",{}) if verification else {}
        same=bool(expected) and all(expected.get(key,0)==actual.get(key,0) for key in expected.keys()|actual.keys())
        record={"status":"PASS" if compilation["exit_code"]==0 and verification and verification["exit_code"]==0 and same else "FAIL",
                "scope":"existing tested case46 merged-certificate regression, not autonomous Agent acceptance",
                "release_binary_sha256":sha(binary),
                "legacy_fixture":{"path":str(fixture.relative_to(ROOT)),"bytes":fixture.stat().st_size,"sha256":sha(fixture)},
                "raw_json_bytes":raw.stat().st_size,"raw_json_sha256":sha(raw),
                "compiled_rpx_bytes":rpx.stat().st_size if rpx.exists() else None,
                "compiled_rpx_sha256":sha(rpx) if rpx.exists() else None,
                "model_request_hashes":{path.name:sha(path) for path in [case/"source.mcm",case/"target.mcm",request]},
                "compilation":compilation,"verification":verification,
                "statistics_equal_sum_of_shipped_independent_pieces":same,
                "elapsed_seconds":time.perf_counter()-started,
                "historical_obstruction":"legacy RPA assembler rejects >256MiB text; direct Certificate JSON bridge accepts512MiB"}
        (directory/"test46-merged.json").write_text(json.dumps(record,indent=2)+"\n")
        print(json.dumps(record,indent=2),flush=True)
        return 0 if record["status"]=="PASS" else 1


if __name__=="__main__":
    raise SystemExit(main())
