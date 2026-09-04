from __future__ import annotations

import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "runtime"))
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "hooks"))

from cp_runtime.event_v2 import (EventContractError, ZERO_HASH, append_event, canonical_json,
                                 make_event, read_event_chain, sha256_hex, verify_event_chain)
from payload_integrity import PayloadIntegrityError, build_manifest, verify_payload
from cp_hook import _event


def load_package_manager():
    spec = importlib.util.spec_from_file_location("package_manager_v65", ROOT / "scripts" / "package_manager.py")
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class V64ResilienceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory(prefix="cp-v65-resilience-")
        self.root = Path(self.temporary.name)
        self.project = "project-v65"
        self.repo = "sha256:" + "a" * 64

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def event(self, index: int, event_type: str = "TURN_OPENED") -> dict:
        return {
            "event_id": "EVT_%03d" % index,
            "event_type": event_type,
            "session_id": "session",
            "turn_id": "turn",
            "task_id": "task",
            "project_id": self.project,
            "repo_fingerprint": self.repo,
            "metadata": {"padding": "x" * 180},
        }

    def test_payload_manifest_is_deterministic_and_tamper_fails(self) -> None:
        first = build_manifest(ROOT, "codex-cross-project-engineering-assistant", "6.5.0")
        second = build_manifest(ROOT, "codex-cross-project-engineering-assistant", "6.5.0")
        self.assertEqual(first, second)
        payload = self.root / "payload"
        for name in (".codex-plugin", "skills", "hooks", "runtime"):
            shutil.copytree(ROOT / name, payload / name, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
        verify_payload(payload, first, package="codex-cross-project-engineering-assistant", version="6.5.0")
        target = next(path for path in (payload / "hooks").rglob("*.py"))
        target.write_bytes(target.read_bytes() + b"\n# tamper\n")
        with self.assertRaises(PayloadIntegrityError):
            verify_payload(payload, first)

    def test_state_v1_migration_preserves_unknown_fields_and_rejects_unknown_schema(self) -> None:
        manager = load_package_manager()
        original = {"schema_version": 1, "scope": "user", "mode": "plugin", "backup": "old",
                    "managed_hashes": {}, "future_field": {"keep": True}}
        migrated = manager.migrate_state_v1_to_v2(original, "user", "plugin")
        self.assertEqual(2, migrated["schema_version"])
        self.assertEqual({"keep": True}, migrated["future_field"])
        self.assertEqual("old", migrated["backup"])
        with self.assertRaises(manager.InstallError):
            manager.migrate_state_v1_to_v2({"schema_version": 99}, "user", "plugin")

    def test_hook_drops_all_host_model_identity_aliases(self) -> None:
        base = {"hook_event_name": "Stop", "cwd": str(self.root), "session_id": "s", "turn_id": "t",
                "model": "gpt-5.6-terra", "reasoning_effort": "high", "quality_outcome": "PASS", "status": "success"}
        result = _event(base)
        assert result is not None
        self.assertNotIn("actual_model", result)
        self.assertNotIn("actual_reasoning_effort", result)
        self.assertEqual("UNKNOWN", result["terminal_outcome"])
        self.assertNotIn("actual_model_source", result)
        explicit = dict(base, actual_model="gpt-5.6-terra", actual_reasoning_effort="high", terminal_outcome="PASS")
        validated = make_event(_event(explicit) or {})
        self.assertNotIn("actual_model_source", validated)
        self.assertNotIn("actual_model", validated)
        self.assertEqual("hook-payload", validated["terminal_outcome_source"])

    def test_invalid_terminal_model_identity_is_ignored_and_bad_schema_fails(self) -> None:
        with self.assertRaises(EventContractError):
            make_event(dict(self.event(1), terminal_outcome="SUCCESS"))
        sanitized = make_event(dict(self.event(1), actual_model="gpt-invented"))
        self.assertNotIn("actual_model", sanitized)
        payload = make_event(self.event(2, "TASK_COMPLETED"))
        payload["terminal_outcome"] = "SUCCESS"
        envelope = dict(payload, previous_hash=ZERO_HASH,
                        record_hash=sha256_hex(ZERO_HASH + "\n" + canonical_json(payload)))
        path = self.root / "task-outcome-v3.jsonl"
        path.write_text(canonical_json(envelope) + "\n", encoding="utf-8")
        with self.assertRaises(EventContractError):
            verify_event_chain(path)

    def test_segments_are_contiguous_and_missing_segment_fails(self) -> None:
        path = self.root / "task-outcome-v3.jsonl"
        old = os.environ.get("CP_ASSISTANT_EVENT_SEGMENT_BYTES")
        os.environ["CP_ASSISTANT_EVENT_SEGMENT_BYTES"] = "256"
        try:
            for index in range(6):
                append_event(path, self.event(index))
        finally:
            if old is None:
                os.environ.pop("CP_ASSISTANT_EVENT_SEGMENT_BYTES", None)
            else:
                os.environ["CP_ASSISTANT_EVENT_SEGMENT_BYTES"] = old
        result = read_event_chain(path)
        self.assertEqual(6, result["record_count"])
        self.assertGreaterEqual(len(result["files"]), 2)
        segment = sorted(self.root.glob("task-outcome-v3.segment-*.jsonl"))[0]
        segment.unlink()
        with self.assertRaises(EventContractError):
            verify_event_chain(path)

    def test_partial_active_tail_is_quarantined_and_chain_continues(self) -> None:
        path = self.root / "task-outcome-v3.jsonl"
        append_event(path, self.event(1))
        with path.open("ab") as handle:
            handle.write(b'{"partial":')
            handle.flush()
            os.fsync(handle.fileno())
        append_event(path, self.event(2, "TASK_COMPLETED"))
        result = read_event_chain(path)
        self.assertEqual(2, result["record_count"])
        quarantines = list(self.root.glob("task-outcome-v3.corrupt-tail-*.bin"))
        self.assertEqual(1, len(quarantines))
        self.assertEqual(b'{"partial":', quarantines[0].read_bytes())

    def test_real_process_mid_record_crash_recovers_without_chain_loss(self) -> None:
        path = self.root / "task-outcome-v3.jsonl"
        append_event(path, self.event(1))
        code = (
            "from pathlib import Path; from cp_runtime.event_v2 import append_event; "
            "append_event(Path(r'%s'), %r)" % (str(path), self.event(2))
        )
        env = dict(os.environ, PYTHONPATH=str(ROOT / "runtime"), CP_ASSISTANT_TEST_EVENT_HARD_CRASH_POINT="MID_RECORD")
        crashed = subprocess.run([sys.executable, "-c", code], env=env, capture_output=True, text=True)
        self.assertEqual(92, crashed.returncode)
        append_event(path, self.event(3, "TASK_COMPLETED"))
        result = read_event_chain(path)
        self.assertEqual(["EVT_001", "EVT_003"], [item["event_id"] for item in result["events"]])
        self.assertEqual(1, len(list(self.root.glob("task-outcome-v3.corrupt-tail-*.bin"))))


if __name__ == "__main__":
    unittest.main()
