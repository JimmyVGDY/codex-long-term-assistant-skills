from __future__ import annotations

import sys
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
try:
    import test_capability_store as fixtures
except ModuleNotFoundError:
    from runtime.tests import test_capability_store as fixtures
from cp_runtime.capability_gate import GatePolicy
from cp_runtime.capability_operation import CapabilityOperation
from cp_runtime.capability_store import CapabilityError


class OperationTests(unittest.TestCase):
    tearDown = fixtures.CapabilityStoreTests.tearDown

    def setUp(self):
        super().setUp()
        fixtures.CapabilityStoreTests.setUp(self)
        self.policy = GatePolicy(self.store, self.base / "gate-config")
        self.policy.set_enabled(True, None)
        self.clock = [datetime(2026, 1, 1, tzinfo=timezone.utc)]
        self.ops = CapabilityOperation(self.policy, "session", "turn", now=lambda: self.clock[0])

    def origin(self):
        return self.ops.create_or_replay_origin("attempt-a", {"kind": "Update"}, ["src/a.py"], {"src/a.py": "missing"})

    def test_origin_prepare_claim_posttool_finish(self):
        origin = self.origin()
        self.assertEqual("PREPARING", origin["state"])
        self.assertEqual(origin, self.ops.replay_origin("attempt-a", {"kind": "Update"}, ["src/a.py"], {"src/a.py": "missing"}))
        ready = self.ops.prepare_ready(origin["operation_ref"], prepare_sha256="a" * 64)
        claimed = self.ops.find_and_claim(tool_use_id="tool-b", intent={"kind": "Update"}, targets=["src/a.py"], prestate={"src/a.py": "missing"})
        self.assertEqual("DISPATCH_GRANTED", claimed["state"])
        marker = "PRIVATE_POSTTOOL_RESPONSE_MARKER_123"
        pending = self.ops.record_posttool(origin["operation_ref"], "tool-b", {"detail": marker})
        self.assertEqual("RESULT_PENDING", pending["state"])
        self.assertNotIn(marker.encode(), self.ops._path(origin["operation_ref"]).read_bytes())
        self.assertEqual("VERIFIED", self.ops.finish(origin["operation_ref"], "tool-b", evidence_sha256="b" * 64)["state"])

    def test_competing_dispatch_ids_only_one_claims(self):
        origin = self.origin(); self.ops.prepare_ready(origin["operation_ref"], prepare_sha256="a" * 64)
        def claim(value):
            try:
                result = self.ops.find_and_claim(tool_use_id=value, intent={"kind": "Update"}, targets=["src/a.py"], prestate={"src/a.py": "missing"})
                return result and result["dispatch_tool_use_id"]
            except CapabilityError:
                return None
        with ThreadPoolExecutor(max_workers=2) as pool:
            result = list(pool.map(claim, ["tool-b", "tool-c"]))
        self.assertEqual(1, sum(item is not None for item in result))

    def test_expiry_and_missing_receipt_converge_unknown(self):
        origin = self.origin(); self.ops.prepare_ready(origin["operation_ref"], prepare_sha256="a" * 64)
        self.clock[0] += timedelta(minutes=6)
        self.assertIsNone(self.ops.find_and_claim(tool_use_id="tool-b", intent={"kind": "Update"}, targets=["src/a.py"], prestate={"src/a.py": "missing"}))
        self.assertEqual("EXPIRED", self.ops.check(origin["operation_ref"])["state"])
        origin = self.origin()  # 中文：幂等重放仍过期；改用第二个操作。 English: Replay stays expired; use another operation.
        second = self.ops.create_or_replay_origin("attempt-b", {"kind": "Update"}, ["src/b.py"], {})
        self.ops.prepare_ready(second["operation_ref"], prepare_sha256="a" * 64)
        self.ops.find_and_claim(tool_use_id="tool-c", intent={"kind": "Update"}, targets=["src/b.py"], prestate={})
        self.clock[0] += timedelta(minutes=6)
        self.assertEqual("OUTCOME_UNKNOWN", self.ops.reconcile_missing_result(second["operation_ref"])["state"])

    def test_strict_record_rejects_unknown_field_and_cross_identity(self):
        origin = self.origin()
        raw = origin["operation_ref"]
        path = self.ops._path(raw)
        text = path.read_text(encoding="utf-8").replace('"state":"PREPARING"', '"state":"PREPARING","unknown":1')
        path.write_text(text, encoding="utf-8")
        with self.assertRaises(CapabilityError):
            self.ops.check(raw)

    def test_disable_after_dispatch_converges_outcome_unknown(self):
        origin = self.origin()
        self.ops.prepare_ready(origin["operation_ref"], prepare_sha256="a" * 64)
        self.ops.find_and_claim(tool_use_id="tool-b", intent={"kind": "Update"},
                                targets=["src/a.py"], prestate={"src/a.py": "missing"})
        self.policy.set_enabled(False, 0)
        state = self.ops.record_posttool(origin["operation_ref"], "tool-b", {"ok": True})
        self.assertEqual("OUTCOME_UNKNOWN", state["state"])
        self.assertEqual("POLICY_CHANGED", state["reason"])

    def test_clock_rollback_expires_ready_and_marks_dispatched_unknown(self):
        origin = self.origin()
        self.ops.prepare_ready(origin["operation_ref"], prepare_sha256="a" * 64)
        earlier = self.clock[0] - timedelta(seconds=1)
        self.assertIsNone(self.ops.find_and_claim(
            tool_use_id="tool-b", intent={"kind": "Update"}, targets=["src/a.py"],
            prestate={"src/a.py": "missing"}, now=earlier,
        ))
        self.assertEqual("EXPIRED", self.ops.check(origin["operation_ref"])["state"])

    def test_cancel_before_and_after_dispatch_have_distinct_outcomes(self):
        first = self.origin()
        self.assertEqual("CANCELLED", self.ops.cancel(first["operation_ref"])["state"])
        second = self.ops.create_or_replay_origin(
            "attempt-b", {"kind": "Update"}, ["src/b.py"], {"src/b.py": "missing"},
        )
        self.ops.prepare_ready(second["operation_ref"], prepare_sha256="a" * 64)
        self.ops.find_and_claim(tool_use_id="tool-c", intent={"kind": "Update"},
                                targets=["src/b.py"], prestate={"src/b.py": "missing"})
        state = self.ops.cancel(second["operation_ref"])
        self.assertEqual("OUTCOME_UNKNOWN", state["state"])
        self.assertEqual("CANCEL_AFTER_DISPATCH", state["reason"])

    def test_late_posttool_and_late_finish_cannot_verify(self):
        first = self.origin()
        self.ops.prepare_ready(first["operation_ref"], prepare_sha256="a" * 64)
        self.ops.find_and_claim(tool_use_id="tool-b", intent={"kind": "Update"},
                                targets=["src/a.py"], prestate={"src/a.py": "missing"})
        self.clock[0] += timedelta(minutes=5)
        late = self.ops.record_posttool(first["operation_ref"], "tool-b", {"ok": True})
        self.assertEqual("OUTCOME_UNKNOWN", late["state"])
        self.assertEqual("POST_TOOL_RECEIPT_LATE", late["reason"])

        second = self.ops.create_or_replay_origin(
            "attempt-b", {"kind": "Update"}, ["src/b.py"], {"src/b.py": "missing"},
        )
        self.ops.prepare_ready(second["operation_ref"], prepare_sha256="a" * 64)
        self.ops.find_and_claim(tool_use_id="tool-c", intent={"kind": "Update"},
                                targets=["src/b.py"], prestate={"src/b.py": "missing"})
        self.clock[0] += timedelta(minutes=1)
        self.ops.record_posttool(second["operation_ref"], "tool-c", {"ok": True})
        self.clock[0] += timedelta(minutes=5)
        called = []
        expired = self.ops.finish_with_factory(
            second["operation_ref"], "tool-c",
            evidence_factory=lambda: (called.append(True) or "b" * 64, "b" * 64),
        )
        self.assertEqual("OUTCOME_UNKNOWN", expired["state"])
        self.assertEqual("FINISH_DEADLINE_EXPIRED", expired["reason"])
        self.assertEqual([], called)


if __name__ == "__main__":
    unittest.main()
