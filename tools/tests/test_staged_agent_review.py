from pathlib import Path
import copy
import json
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from run_compiler_agents import assess, digest
from verify_staged_agent_delivery import review


def model(order=("x", "y"), coefficient=1):
    return {"name": "example", "variables": [{"name": n, "lower": "0", "upper": "1", "integer": True} for n in order],
            "rows": [], "objective": {"constant": "0", "terms": [[order.index("x"), str(coefficient)]]}}


class EndpointTests(unittest.TestCase):
    def fixture(self, directory, *, reorder=False, break_boundary=False, mutate_input=False):
        base = Path(directory).resolve();batch = base / "compiler-batch-fixture";batch.mkdir()
        (batch / "kernel").mkdir();binary = batch / "kernel/rpx";binary.write_bytes(b"pinned-kernel")
        run = base / "test9-compiler-compiler-batch-fixture";run.mkdir()
        (run / "input").mkdir();(run / "output").mkdir()
        original = run / "input/model.mps";original.write_bytes(b"pristine")
        trusted = digest(original)
        (batch / "batch.json").write_text(json.dumps({"input_sha256": {"test9": trusted},
            "kernel_sha256": digest(binary), "git_head": "checkpoint"}))
        if mutate_input:original.write_bytes(b"changed")
        (run / "execution.json").write_text("{}")
        (run / "assessment.json").write_text('{"errors":["preserved strict failure"]}')
        pieces=[];models={str(original):model()}
        final = run / "output/final.mps";final.write_bytes(b"final")
        models[str(final)]=model()
        for index in range(2):
            paths={}
            for key, suffix in (("source","mcm"),("target","mcm"),("proof","rpx")):
                p=run/f"output/{key}-{index}.{suffix}";p.write_bytes(f"{key}-{index}".encode());paths[key]=str(p)
            models[paths["source"]]=model(("y","x")) if index==0 and reorder else model()
            models[paths["target"]]=model(coefficient=2) if index==0 and break_boundary else model()
            pieces.append(paths)
        (run / "output/delivery.json").write_text(json.dumps({"committed_model":str(final),"pieces":pieces}))
        def canonical(_binary, source, destination):
            value=copy.deepcopy(models[str(source)]);destination.write_text(json.dumps(value));return value
        return batch, run, canonical

    def test_broken_boundary_is_rejected_and_strict_report_preserved(self):
        with tempfile.TemporaryDirectory() as directory:
            batch,run,canonical=self.fixture(directory,break_boundary=True)
            old=(run/'assessment.json').read_bytes()
            with patch("verify_staged_agent_delivery.canonical_model", side_effect=canonical), patch(
                "verify_staged_agent_delivery.kernel_call", return_value={"exit_code":0,"result":{"status":"VERIFIED","guarantee":"MI_OPT"}}):
                result=review(batch,"test9",Path(directory)/"review")
            self.assertEqual(result["status"],"REVIEW_FAILED")
            self.assertIn("unlinked",result["errors"][0])
            self.assertEqual((run/'assessment.json').read_bytes(),old)

    def test_pristine_mutation_is_rejected_before_readback(self):
        with tempfile.TemporaryDirectory() as directory:
            batch,run,canonical=self.fixture(directory,mutate_input=True)
            with patch("verify_staged_agent_delivery.canonical_model") as readback:
                result=review(batch,"test9",Path(directory)/"review")
            readback.assert_not_called()
            self.assertEqual(result["status"],"REVIEW_FAILED")
            self.assertIn("original input changed",result["errors"][0])

    def test_reordered_source_uses_its_own_coordinate_order(self):
        with tempfile.TemporaryDirectory() as directory:
            batch,run,canonical=self.fixture(directory,reorder=True)
            destination=Path(directory)/"review"
            with patch("verify_staged_agent_delivery.canonical_model", side_effect=canonical), patch(
                "verify_staged_agent_delivery.kernel_call", return_value={"exit_code":0,"result":{"status":"VERIFIED","guarantee":"MI_OPT"}}) as verify:
                result=review(batch,"test9",destination)
            self.assertEqual(result["status"],"VERIFIED_CHAIN")
            self.assertEqual(verify.call_args_list[0].args[2],destination/'source-0.mcm')
            self.assertEqual(json.loads((destination/'source-0.mcm').read_text())["variables"][0]["name"],"y")


    def test_native_two_stage_chain_links_distinct_intermediate_and_final_models(self):
        root=Path(__file__).resolve().parents[2];binary=root/'target/release/rpx'
        if not binary.is_file():self.skipTest('release kernel unavailable')
        sys.path.insert(0,str(root/'python'))
        from kernel_compiler import Expr,Kernel,Model,Proof,Row,Variable,write_chain
        kernel=Kernel(binary)
        with tempfile.TemporaryDirectory() as directory:
            run=Path(directory).resolve();(run/'input').mkdir();(run/'output').mkdir()
            x,y=Expr.var(0),Expr.var(1)
            original=Model('original',[Variable('x',lower=0,upper=1),Variable('y',lower=0,upper=2)],
                           [Row('define',y-2*x,lower=0,upper=0)],objective=y,kernel=kernel)
            middle=Model('middle',[original.vars[1],original.vars[0]],
                         [Row('define',Expr.var(0)-2*Expr.var(1),lower=0,upper=0)],
                         objective=Expr.var(0),kernel=kernel)
            final=middle.substitute({'y':2*middle.var('x')},drop_rows=['define'],preserve_bounds=False)
            original.write_mps(run/'input/model.mps');final.write_mps(run/'output/final.mps')
            first=Proof(original,middle)
            forward,reverse=(first.forward.map({v.name:original.var(v.name) for v in middle.vars}), first.reverse.map({v.name:middle.var(v.name) for v in original.vars}))
            forward.complete();reverse.complete();first.verify(run/'output/first')
            second=Proof(middle,final)
            forward,reverse=(second.forward.map({'x':middle.var('x')}), second.reverse.map({'x':final.var('x'),'y':2*final.var('x')}))
            forward.eq([(forward.row('define'),-1)]);forward.complete()
            reverse.le([(reverse.lower('x'),2)]);reverse.le([(reverse.upper('x'),2)]);reverse.complete()
            second.verify(run/'output/second')
            write_chain([run/'output/first/delivery.json',run/'output/second/delivery.json'],
                        run/'output/delivery.json',committed_model=run/'output/final.mps',
                        original_model=run/'input/model.mps')
            result=assess(run,binary,'compiler',expected_input_sha256=digest(run/'input/model.mps'))
            self.assertTrue(result['kernel_verified'],result)
            self.assertEqual(result['guarantee'],'MI_OPT')

    def test_explicit_ordered_chain_dispatches_independent_composition(self):
        with tempfile.TemporaryDirectory() as directory:
            batch,run,canonical=EndpointTests().fixture(directory)
            manifest=run/'output/delivery.json'
            document=json.loads(manifest.read_text())
            document.pop('relation',None)
            document['composition']={'ordered_chain':True}
            manifest.write_text(json.dumps(document))
            with patch('run_compiler_agents.canonical_model',side_effect=canonical), patch(
                'verify_staged_agent_delivery.canonical_model',side_effect=canonical), patch(
                'verify_staged_agent_delivery.kernel_call',return_value={'exit_code':0,'result':{'status':'VERIFIED','guarantee':'MI_OPT'}}):
                result=assess(run,batch/'kernel/rpx','compiler',
                              expected_input_sha256=digest(run/'input/model.mps'))
            self.assertTrue(result['kernel_verified'],result)
            self.assertTrue(result['ordered_chain'])
            self.assertEqual(result['guarantee'],'MI_OPT')
            self.assertTrue(Path(result['staged_review']).is_file())

    def test_native_reordered_source_anchors_by_names_but_verifies_own_indices(self):
        root=Path(__file__).resolve().parents[2]
        binary=root/'target/release/rpx'
        if not binary.is_file():self.skipTest('release kernel unavailable')
        sys.path.insert(0,str(root/'python'))
        from kernel_compiler import Expr,Kernel,Model,Proof,Variable
        kernel=Kernel(binary)
        for chain in (False,True):
            with self.subTest(ordered_chain=chain),tempfile.TemporaryDirectory() as directory:
                run=Path(directory).resolve();(run/'input').mkdir();(run/'output').mkdir()
                source=Model('original',[Variable('x',integer=True,lower=0,upper=1),
                                        Variable('y',integer=True,lower=0,upper=2)],
                             objective=3*Expr.var(0)+5*Expr.var(1),kernel=kernel)
                reordered=Model('reordered',[source.vars[1],source.vars[0]],
                                objective=5*Expr.var(0)+3*Expr.var(1),kernel=kernel)
                source.write_mps(run/'input/model.mps')
                source.write_mps(run/'output/final.mps')
                proof=Proof(reordered,source)
                forward,reverse=(proof.forward.map({v.name:reordered.var(v.name) for v in source.vars}), proof.reverse.map({v.name:source.var(v.name) for v in reordered.vars}))
                forward.complete();reverse.complete()
                proof.verify(run/'output',committed_model=run/'output/final.mps')
                manifest=run/'output/delivery.json';document=json.loads(manifest.read_text())
                document.pop('relation',None)
                if chain:document['composition']={'ordered_chain':True}
                manifest.write_text(json.dumps(document))
                result=assess(run,binary,'compiler',expected_input_sha256=digest(run/'input/model.mps'))
                self.assertTrue(result['kernel_verified'],result)
                self.assertEqual(result['errors'],[])
                # Original coordinate order is incompatible with this RPX.
                bad=kernel.verify(run/'harness-assessment/input.mcm',run/'output/target.mcm',
                                  run/'output/proof.rpx')
                self.assertEqual(bad['status'],'INVALID',bad)


if __name__ == "__main__":unittest.main()
