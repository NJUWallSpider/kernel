import hashlib
import json
import os
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from rpx import *
from rpx.lowlevel import assemble, disassemble, verify


class Artifacts(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        b = ModelBuilder("m")
        x = b.add_var("x", integer=True, lower=0, upper=1)
        b.minimize(x)
        self.m = b.build()
        self.p = Proof(self.m, self.m)
        self.p.forward.map(default="same_name").finish()
        self.p.reverse.map(default="same_name").finish()
        self.target = self.m.write_mps(self.root / "target.mps")

    def bundle(self, name="bundle"):
        return self.p.compile(self.root / name, target_artifact=self.target)

    def test_selfcontained_move_and_reopen(self):
        b = self.bundle()
        raw = self.target.read_bytes()
        self.target.unlink()
        shutil.move(b.directory, self.root / "moved")
        b = Bundle.open(self.root / "moved")
        report = b.verify()
        self.assertEqual(report.status, "VERIFIED")
        self.assertEqual(report.artifact_audit["status"], "MATCHED")
        self.assertEqual((b.directory / "target-artifact.mps").read_bytes(), raw)
        doc = json.loads(b.manifest.read_text())
        self.assertTrue(
            all(not Path(v["path"]).is_absolute() for v in doc["artifacts"].values())
        )

    def test_repeat_determinism_and_native_cache(self):
        a = self.bundle()
        one = self.p.preflight()
        b = self.bundle("other")
        self.assertEqual(a.proof.read_bytes(), b.proof.read_bytes())
        self.assertEqual(a.rpa.read_bytes(), b.rpa.read_bytes())
        self.assertEqual(self.p._native.lowering_count, 1)
        self.assertEqual(self.bundle().directory, a.directory)
        self.assertEqual(one, self.p.preflight())

    def test_changed_artifact_rejects_before_publish(self):
        self.m.with_bounds("x", upper=2).write_mps(self.target)
        with self.assertRaises(ArtifactMismatchError):
            self.bundle()
        self.assertFalse((self.root / "bundle").exists())
        self.assertEqual(list(self.root.glob(".bundle.*")), [])

    def test_external_artifact_is_freshly_audited(self):
        b = self.bundle()
        self.m.with_bounds("x", upper=2).write_mps(self.target)
        with self.assertRaises(ArtifactMismatchError):
            b.verify(target_artifact=self.target)
        self.assertEqual(b.verify().status, "VERIFIED")

    def test_digest_tampering_rejected(self):
        b = self.bundle()
        b.proof.write_bytes(b.proof.read_bytes() + b"\0")
        with self.assertRaises(ArtifactMismatchError):
            Bundle.open(b.directory)
        with self.assertRaises(ArtifactMismatchError):
            b.verify()

    def test_unsupported_schema_and_missing_record(self):
        b = self.bundle()
        doc = json.loads(b.manifest.read_text())
        old = dict(doc)
        old["schema"] = "old"
        b.manifest.write_text(json.dumps(old))
        with self.assertRaises(ArtifactMismatchError):
            Bundle.open(b.directory)
        doc["artifacts"].pop("proof")
        b.manifest.write_text(json.dumps(doc))
        with self.assertRaises(ArtifactMismatchError):
            Bundle.open(b.directory)

    def test_relative_path_escape_and_symlink(self):
        b = self.bundle()
        doc = json.loads(b.manifest.read_text())
        doc["artifacts"]["proof"]["path"] = "../outside.rpx"
        b.manifest.write_text(json.dumps(doc))
        with self.assertRaises(ArtifactMismatchError):
            Bundle.open(b.directory)

    def test_file_hardlink_and_symlink_destinations_protect_inputs(self):
        raw = self.target.read_bytes()
        for name, kind in [("same", None), ("hard", "hard"), ("sym", "sym")]:
            path = self.target if kind is None else self.root / name
            if kind == "hard":
                os.link(self.target, path)
            if kind == "sym":
                path.symlink_to(self.target)
            with self.assertRaises(ArtifactMismatchError):
                self.p.compile(path, target_artifact=self.target)
            self.assertEqual(self.target.read_bytes(), raw)

    def test_different_delivery_never_overwrites(self):
        b = self.bundle()
        before = b.manifest.read_bytes()
        q = Proof(self.m, self.m)
        s = q.forward
        s.derive.le(s.lower("x"))
        s.map(default="same_name").finish()
        q.reverse.map(default="same_name").finish()
        with self.assertRaises(ArtifactMismatchError):
            q.compile(b.directory, target_artifact=self.target)
        self.assertEqual(b.manifest.read_bytes(), before)

    def test_publish_failure_cleans_staging(self):
        with patch(
            "rpx.artifacts._rename_exclusive",
            side_effect=OSError("simulated publish failure"),
        ):
            with self.assertRaises(OSError):
                self.bundle()
        self.assertEqual(list(self.root.glob(".bundle.*")), [])
        self.assertFalse((self.root / "bundle").exists())

    def test_fresh_budgets_do_not_trust_receipt(self):
        b = self.bundle()
        self.assertEqual(b.verify().status, "VERIFIED")
        result = b.verify(work=0)
        self.assertEqual(result.status, "RESOURCE_LIMIT")
        self.assertIsNone(result.guarantee)
        with self.assertRaises(ResourceLimitError):
            result.raise_for_status()
        (b.directory / "verification.json").write_text('{"status":"VERIFIED"}')
        self.assertEqual(b.verify(work=0).status, "RESOURCE_LIMIT")
        self.assertEqual(b.verify().status, "VERIFIED")
        self.assertEqual(self.p._native.lowering_count, 1)

    def test_chain_move_and_joins(self):
        a, b = self.bundle(), self.bundle("b")
        chain = Chain([a, b]).compile(self.root / "chain", target_artifact=self.target)
        shutil.rmtree(a.directory)
        shutil.rmtree(b.directory)
        self.target.unlink()
        shutil.move(chain.directory, self.root / "moved")
        chain = Chain.open(self.root / "moved")
        report = chain.verify()
        self.assertEqual(report.status, "VERIFIED")
        report = chain.verify(work=0)
        self.assertEqual(report.status, "RESOURCE_LIMIT")
        with self.assertRaises(ResourceLimitError):
            report.raise_for_status()
        self.assertIsNone(report.guarantee)

    def test_chain_default_endpoints(self):
        chain = Chain([self.bundle()]).compile(self.root / "chain")
        self.assertEqual(chain.verify().status, "VERIFIED")

    def test_chain_copies_only_audited_files_and_allows_safe_nested_destination(self):
        b = self.bundle()
        (b.directory / "unrelated.txt").write_text("not a package artifact")
        chain = Chain([b]).compile(b.directory / "chain")
        self.assertFalse((chain.directory / "stages/0000/unrelated.txt").exists())
        self.assertEqual(chain.verify().status, "VERIFIED")

    def test_chain_rejects_disconnected_models(self):
        a = self.bundle()
        m = self.m.with_bounds("x", upper=2)
        p = Proof(m, m)
        p.forward.map(default="same_name").finish()
        p.reverse.map(default="same_name").finish()
        b = p.compile(self.root / "b")
        with self.assertRaises(ArtifactMismatchError):
            Chain([a, b])

    def test_chain_manifest_cannot_omit_stage_or_endpoint_hash(self):
        c = Chain([self.bundle()]).compile(self.root / "chain")
        path = c.directory / "delivery.json"
        doc = json.loads(path.read_text())
        doc["artifacts"].pop(doc["target_artifact"])
        path.write_text(json.dumps(doc))
        with self.assertRaises(ArtifactMismatchError):
            Chain.open(c.directory)

    def test_format_roundtrip_independent(self):
        b = self.bundle()
        assemble(str(b.rpa), str(self.root / "round.rpx"))
        disassemble(str(b.proof), str(self.root / "round.rpa"))
        self.assertEqual(b.proof.read_bytes(), (self.root / "round.rpx").read_bytes())
        self.assertEqual(b.rpa.read_bytes(), (self.root / "round.rpa").read_bytes())

    def test_invalid_proof_never_claims_delivery_success(self):
        b = self.bundle()
        text = b.rpa.read_text().replace("v0.lo", "v0.hi", 1)
        self.assertNotEqual(text, b.rpa.read_text())
        b.rpa.write_text(text)
        assemble(str(b.rpa), str(b.proof))
        doc = json.loads(b.manifest.read_text())
        for role, path in [("rpa", b.rpa), ("proof", b.proof)]:
            doc["artifacts"][role].update(
                sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
                bytes=path.stat().st_size,
            )
        b.manifest.write_text(json.dumps(doc))
        report = b.verify()
        self.assertEqual(report.status, "INVALID")
        self.assertIsNone(report.guarantee)
        with self.assertRaises(KernelRejectedError):
            report.raise_for_status()

    def test_publication_race_preserves_existing_empty_directory(self):
        from rpx.artifacts import _rename_exclusive

        def race(source, destination):
            destination.mkdir()
            return _rename_exclusive(source, destination)

        with patch("rpx.artifacts._rename_exclusive", side_effect=race):
            with self.assertRaises(ArtifactMismatchError):
                self.bundle()
        self.assertEqual(list((self.root / "bundle").iterdir()), [])
        self.assertEqual(list(self.root.glob(".bundle.*")), [])
