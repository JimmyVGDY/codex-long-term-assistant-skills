"""中文：能力索引存储的身份、故障恢复、隐私和并发契约。 English: Identity, fault recovery, privacy, and concurrency contracts for capability storage."""
from __future__ import annotations

import copy
import hashlib
import json
import multiprocessing
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from cp_runtime import capability_store as store_module
from cp_runtime.capability_store import CapabilityError, CapabilityStore, empty_payload, relative_path
from cp_runtime.common import RuntimeContractError, atomic_write_bytes, canonical_json, seal_record
from cp_runtime.event_v3 import OwnerTokenLock
from cp_runtime.project import onboard_project


def git(repo, *args):
    return subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True, text=True).stdout.strip()


def update_child(profile, repo, root, marker, ready, start, result):
    store = CapabilityStore(Path(profile), Path(repo), Path(root))
    payload = empty_payload()
    payload["baseline"]["branch"] = marker
    ready.put(True)
    start.wait(10)
    try:
        result.put(("OK", store.commit(payload, 0)["revision"]))
    except RuntimeContractError as exc:
        result.put(("ERROR", str(exc)))


def lock_child(path, ready):
    with OwnerTokenLock(Path(path)):
        ready.put(True)
        import time
        time.sleep(30)


class CapabilityStoreTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="capability-store-")
        self.base = Path(self.temp.name)
        self.repo = self.base / "repo"
        self.repo.mkdir()
        git(self.repo, "init", "-q")
        git(self.repo, "config", "user.name", "Test")
        git(self.repo, "config", "user.email", "test@example.invalid")
        (self.repo / "app.py").write_text("def public():\n    return 1\n", encoding="utf-8")
        git(self.repo, "add", ".")
        git(self.repo, "commit", "-qm", "fixture")
        binding = onboard_project(self.repo, "CAP-TEST", "Test", self.base / "context")
        self.profile = binding.profile_path
        self.store = CapabilityStore(self.profile, self.repo)

    def tearDown(self):
        self.temp.cleanup()

    def init(self):
        return self.store.commit(empty_payload(), None)

    def test_missing_snapshot_is_distinct_from_unreadable_existing_snapshot(self):
        with self.assertRaisesRegex(CapabilityError, "INDEX_MISSING"):
            self.store.read()
        self.init()
        original = store_module.bounded_read
        def deny_snapshot(path, *args):
            if path == self.store.current:
                raise CapabilityError("UNREADABLE")
            return original(path, *args)
        with patch("cp_runtime.capability_store.bounded_read", side_effect=deny_snapshot):
            with self.assertRaisesRegex(CapabilityError, "UNREADABLE"):
                self.store.read()

    def test_reserved_container_cannot_shadow_default_worktree_index(self):
        self.init()
        before = self.store.current.read_bytes()
        container = self.profile.parent / "capability-index"
        with self.assertRaisesRegex(CapabilityError, "INDEX_ROOT_IS_CONTAINER_OMIT_OVERRIDE"):
            CapabilityStore(self.profile, self.repo, container)
        self.assertFalse((container / "index.json").exists())
        self.assertEqual(before, self.store.current.read_bytes())
        explicit = CapabilityStore(self.profile, self.repo, self.store.root)
        self.assertEqual(self.store.read(), explicit.read())
        custom = CapabilityStore(self.profile, self.repo, self.base / "custom-index")
        self.assertEqual(0, custom.commit(empty_payload(), None)["revision"])

    def changed(self):
        payload = empty_payload()
        payload["baseline"]["branch"] = "feature"
        return payload

    def entry_payload(self):
        payload = empty_payload()
        payload["entries"] = [{"id": "cap-1", "kind": "function", "path": "app.py", "symbol": "public",
            "summary": "公共能力", "keywords": [], "boundaries": [],
            "references": {"callers": [], "tests": [], "context": []},
            "file_sha256": None, "lifecycle": "candidate", "freshness": "unknown",
            "observed_baseline": {"head": "", "branch": ""},
            "observed_at": None,
            "verification": {"scope": "仅定位", "evidence": [], "recorded_at": None}}]
        return payload

    def test_init_noop_preserves_profile_and_memory(self):
        originals = {p: p.read_bytes() for p in self.profile.parent.iterdir() if p.is_file()}
        record = self.init()
        self.assertEqual(0, record["revision"])
        self.assertFalse(record["coverage"]["complete"])
        before = self.store.current.stat().st_mtime_ns
        with patch.object(store_module, "atomic_write_bytes", side_effect=AssertionError("unexpected write")):
            self.assertEqual(record, self.store.commit(empty_payload(), 0))
        self.assertEqual(before, self.store.current.stat().st_mtime_ns)
        self.assertFalse(self.store.previous.exists())
        for path, content in originals.items():
            self.assertEqual(content, path.read_bytes())

    def test_exact_revision_and_previous_snapshot(self):
        original = self.init()
        result = self.store.commit(self.changed(), 0)
        self.assertEqual(1, result["revision"])
        self.assertEqual(original, json.loads(self.store.previous.read_bytes()))
        with self.assertRaisesRegex(CapabilityError, "REVISION_CONFLICT"):
            self.store.commit(empty_payload(), 0)
        with self.assertRaisesRegex(CapabilityError, "ALREADY_EXISTS"):
            self.init()
        with self.assertRaises(CapabilityError):
            self.store.commit(empty_payload(), True)

    def test_identity_root_and_worktree_are_bound(self):
        self.init()
        other = CapabilityStore(self.profile, self.repo, self.base / "other-index")
        other.root.mkdir()
        other.current.write_bytes(self.store.current.read_bytes())
        with self.assertRaisesRegex(CapabilityError, "IDENTITY_MISMATCH"):
            other.read()
        worktree = self.base / "worktree"
        git(self.repo, "worktree", "add", "-qb", "other", str(worktree))
        with self.assertRaises(RuntimeContractError):
            CapabilityStore(self.profile, worktree)
        binding = onboard_project(worktree, "CAP-OTHER", "Other", self.base / "worktree-context")
        separate = CapabilityStore(binding.profile_path, worktree)
        self.assertNotEqual(self.store.identity["worktree_id"], separate.identity["worktree_id"])
        with self.assertRaises(RuntimeContractError):
            CapabilityStore(self.profile, self.repo, self.repo / "inside")

    def test_remote_change_rejected_after_object_creation(self):
        self.init()
        git(self.repo, "remote", "add", "origin", "https://example.invalid/repository.git")
        with self.assertRaisesRegex(CapabilityError, "IDENTITY_CHANGED"):
            self.store.read()

    def test_schema_integrity_size_and_path_validation(self):
        record = self.init()
        for mutation in (lambda v: v.update(schema_version=2), lambda v: v.update(extra="x"),
                         lambda v: v.update(revision=True), lambda v: v["coverage"].update(extra="x")):
            value = copy.deepcopy(record)
            mutation(value)
            self.store.current.write_text(canonical_json(seal_record(value)), encoding="utf-8")
            with self.assertRaises(RuntimeContractError):
                self.store.read()
        self.store.current.write_text(canonical_json({**record, "revision": 7}), encoding="utf-8")
        with self.assertRaises(RuntimeContractError):
            self.store.read()
        with self.store.current.open("wb") as stream:
            stream.truncate(store_module.MAX_BYTES + 1)
        with self.assertRaisesRegex(CapabilityError, "TOO_LARGE"):
            self.store.read()
        for value in ("../escape", "/root", "C:/root", "a\\b", "a//b", ".env.local", "keys/x.pem", "secrets/a"):
            with self.subTest(path=value), self.assertRaises(CapabilityError):
                relative_path(value)

    def test_sensitive_or_unknown_entry_rejected_without_write(self):
        for secret in ("-----BEGIN RSA PRIVATE KEY-----", "Bearer " + "a" * 40,
                       "https://user:password@example.invalid", "sk-" + "a" * 30,
                       "Ab3CD4ef56GHij78KLmn90OPqr12STuv34WXyz56"):
            payload = self.entry_payload()
            payload["entries"][0]["summary"] = secret
            with self.subTest(secret_type=secret[:3]), self.assertRaisesRegex(CapabilityError, "SENSITIVE_CONTENT"):
                self.store.commit(payload, None)
            self.assertFalse(self.store.current.exists())
        payload = self.entry_payload()
        payload["entries"][0]["unknown"] = "unsupported"
        with self.assertRaises(CapabilityError):
            self.store.commit(payload, None)
        valid = self.entry_payload()
        valid["entries"][0]["file_sha256"] = hashlib.sha256(b"source").hexdigest()
        self.assertEqual(1, len(self.store.commit(valid, None)["entries"]))

    def test_previous_write_failure_keeps_current(self):
        self.init()
        before = self.store.current.read_bytes()
        with patch.object(store_module, "atomic_write_bytes", side_effect=OSError("injected")):
            with self.assertRaises(OSError):
                self.store.commit(self.changed(), 0)
        self.assertEqual(before, self.store.current.read_bytes())

    def test_current_failure_before_and_after_replace_is_recoverable(self):
        self.init()
        before = self.store.current.read_bytes()
        def failing_write(path, raw):
            if path == self.store.current:
                raise OSError("injected")
            atomic_write_bytes(path, raw)
        with patch.object(store_module, "atomic_write_bytes", side_effect=failing_write):
            with self.assertRaisesRegex(CapabilityError, "COMMIT_UNCERTAIN"):
                self.store.commit(self.changed(), 0)
        self.assertEqual(before, self.store.current.read_bytes())
        def replaced_then_failed(path, raw):
            atomic_write_bytes(path, raw)
            if path == self.store.current:
                raise OSError("injected post-replace failure")
        with patch.object(store_module, "atomic_write_bytes", side_effect=replaced_then_failed):
            with self.assertRaisesRegex(CapabilityError, "COMMIT_UNCERTAIN"):
                self.store.commit(self.changed(), 0)
        self.assertEqual(1, self.store.read()["revision"])
        self.assertEqual(before, self.store.previous.read_bytes())

    def test_corrupt_recovery_requires_cas_preserves_bytes_and_is_idempotent(self):
        self.init()
        self.store.commit(self.changed(), 0)
        broken = b"{broken"
        self.store.current.write_bytes(broken)
        digest = hashlib.sha256(broken).hexdigest()
        with self.assertRaisesRegex(CapabilityError, "RECOVERY_CONFLICT"):
            self.store.recover("0" * 64)
        restored = self.store.recover(digest)
        self.assertEqual(2, restored["revision"])
        self.assertEqual(empty_payload(), self.store.payload(restored))
        self.assertEqual(broken, (self.store.root / ("index.recovery-" + digest + ".bin")).read_bytes())
        with self.assertRaisesRegex(CapabilityError, "RECOVERY_CONFLICT"):
            self.store.recover(digest)
        current_hash = hashlib.sha256(self.store.current.read_bytes()).hexdigest()
        with patch.object(store_module, "atomic_write_bytes", side_effect=AssertionError("unexpected write")):
            self.assertEqual(restored, self.store.recover(current_hash))

    def test_missing_current_does_not_allow_reinitialization(self):
        self.init()
        self.store.commit(self.changed(), 0)
        self.store.current.unlink()
        with self.assertRaisesRegex(CapabilityError, "ALREADY_EXISTS"):
            self.init()
        self.assertEqual(2, self.store.recover("MISSING")["revision"])

    def test_invalid_previous_never_overwrites_current(self):
        self.init()
        self.store.commit(self.changed(), 0)
        before = self.store.current.read_bytes()
        digest = hashlib.sha256(before).hexdigest()
        previous = json.loads(self.store.previous.read_bytes())
        for mutate in (lambda v: v.update(schema_version=88),
                       lambda v: v["identity"].update(project_id="OTHER"),
                       lambda v: v.update(revision=9)):
            value = copy.deepcopy(previous)
            mutate(value)
            self.store.previous.write_text(canonical_json(seal_record(value)), encoding="utf-8")
            with self.assertRaises(RuntimeContractError):
                self.store.recover(digest)
            self.assertEqual(before, self.store.current.read_bytes())

    def test_read_detects_real_replacement_before_final_path_check(self):
        path = self.base / "race.txt"
        path.write_bytes(b"before")
        real_safe_path = store_module.safe_path
        calls = 0
        def replace_on_final_path_check(candidate):
            nonlocal calls
            calls += 1
            if calls == 2:
                # 中文：Windows已打开句柄禁止替换；关闭后、最终路径核对前替换。 English: Windows blocks replacement with an open handle; replace after close and before final path verification.
                replacement = self.base / "replacement.txt"
                replacement.write_bytes(b"after")
                os.replace(replacement, path)
            return real_safe_path(candidate)
        with patch.object(store_module, "safe_path", side_effect=replace_on_final_path_check):
            with self.assertRaisesRegex(CapabilityError, "READ_CHANGED"):
                store_module.bounded_read(path)

    def test_recovery_refuses_foreign_or_unknown_current_format(self):
        self.init()
        self.store.commit(self.changed(), 0)
        original = json.loads(self.store.current.read_bytes())
        for mutate in (lambda v: v.update(schema_version=99),
                       lambda v: v["identity"].update(project_id="FOREIGN")):
            value = copy.deepcopy(original)
            mutate(value)
            raw = canonical_json(seal_record(value)).encode("utf-8")
            self.store.current.write_bytes(raw)
            with self.assertRaises(CapabilityError):
                self.store.recover(hashlib.sha256(raw).hexdigest())
            self.assertEqual(raw, self.store.current.read_bytes())

    def test_duplicate_json_fields_and_relative_index_root_rejected(self):
        self.init()
        raw = self.store.current.read_bytes()
        self.store.current.write_bytes(b'{"schema_version":1,' + raw[1:])
        with self.assertRaisesRegex(CapabilityError, "DUPLICATE_FIELD"):
            self.store.read()
        with self.assertRaisesRegex(CapabilityError, "INVALID_INDEX_ROOT"):
            CapabilityStore(self.profile, self.repo, Path("relative-index"))

    def test_entry_count_and_serialized_budget_enforced(self):
        payload = self.entry_payload()
        with patch.object(store_module, "MAX_ENTRIES", 0):
            with self.assertRaises(CapabilityError):
                self.store.commit(payload, None)
        with patch.object(store_module, "MAX_BYTES", 128):
            with self.assertRaisesRegex(CapabilityError, "TOO_LARGE"):
                self.store.commit(empty_payload(), None)
        self.assertFalse(self.store.current.exists())

    def test_lock_time_identity_change_refuses_write(self):
        self.init()
        before = self.store.current.read_bytes()
        real_lock = self.store.lock
        repo = self.repo
        class ChangingLock:
            path = real_lock.path
            def __enter__(self):
                real_lock.__enter__()
                git(repo, "remote", "add", "origin", "https://example.invalid/changed.git")
            def __exit__(self, *args):
                return real_lock.__exit__(*args)
        self.store.lock = ChangingLock()
        with self.assertRaisesRegex(CapabilityError, "IDENTITY_CHANGED"):
            self.store.commit(self.changed(), 0)
        self.assertEqual(before, self.store.current.read_bytes())

    def test_previous_readback_failure_does_not_replace_current(self):
        self.init()
        before = self.store.current.read_bytes()
        original_read = store_module.bounded_read
        def bad_previous_read(path, *args):
            if path == self.store.previous:
                return b"wrong bytes"
            return original_read(path, *args)
        with patch.object(store_module, "bounded_read", side_effect=bad_previous_read):
            with self.assertRaisesRegex(CapabilityError, "PREVIOUS_VERIFY_FAILED"):
                self.store.commit(self.changed(), 0)
        self.assertEqual(before, self.store.current.read_bytes())

    def test_unknown_nested_types_and_matched_without_hash_rejected(self):
        payload = self.entry_payload()
        for key, value in (("kind", []), ("lifecycle", {}), ("freshness", []),
                           ("freshness", "matched"), ("summary", "x" * 501)):
            candidate = copy.deepcopy(payload)
            candidate["entries"][0][key] = value
            with self.subTest(key=key), self.assertRaises(CapabilityError):
                self.store.commit(candidate, None)
        payload["entries"].append(copy.deepcopy(payload["entries"][0]))
        with self.assertRaises(CapabilityError):
            self.store.commit(payload, None)

    def test_two_processes_cannot_lose_an_update(self):
        self.init()
        ctx = multiprocessing.get_context("spawn")
        ready, result, start = ctx.Queue(), ctx.Queue(), ctx.Event()
        children = [ctx.Process(target=update_child, args=(str(self.profile), str(self.repo), str(self.store.root), marker, ready, start, result)) for marker in ("first", "second")]
        try:
            for child in children:
                child.start()
            for _ in children:
                self.assertTrue(ready.get(timeout=15))
            start.set()
            outcomes = [result.get(timeout=15) for _ in children]
            self.assertEqual([("ERROR", "REVISION_CONFLICT"), ("OK", 1)], sorted(outcomes))
            self.assertEqual(1, self.store.read()["revision"])
        finally:
            for child in children:
                child.join(5)
                if child.is_alive():
                    child.terminate()
                    child.join(5)

    def test_killed_lock_owner_releases_kernel_lock(self):
        self.init()
        ctx = multiprocessing.get_context("spawn")
        ready = ctx.Queue()
        child = ctx.Process(target=lock_child, args=(str(self.store.current), ready))
        try:
            child.start()
            self.assertTrue(ready.get(timeout=15))
            with self.assertRaises(TimeoutError), OwnerTokenLock(self.store.current, timeout=0.1):
                pass
        finally:
            child.terminate()
            child.join(5)
        self.assertEqual(1, self.store.commit(self.changed(), 0)["revision"])

    @unittest.skipUnless(os.name == "nt", "Windows junction test")
    def test_windows_junction_rejected_before_resolve(self):
        target = self.base / "target"
        target.mkdir()
        junction = self.base / "junction"
        command = "New-Item -ItemType Junction -Path '" + str(junction).replace("'", "''") + "' -Target '" + str(target).replace("'", "''") + "' | Out-Null"
        subprocess.run(["powershell", "-NoProfile", "-Command", command], check=True, capture_output=True)
        try:
            with self.assertRaisesRegex(CapabilityError, "LINK_REJECTED"):
                CapabilityStore(self.profile, self.repo, junction / "index")
        finally:
            os.rmdir(junction)


if __name__ == "__main__":
    unittest.main()
