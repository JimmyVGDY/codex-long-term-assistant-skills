from __future__ import annotations

import concurrent.futures
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
import sys
sys.path.insert(0, str(ROOT / "runtime"))

from cp_runtime import event_v2 as events  # noqa: E402


class EventScalingTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory(prefix="event-scaling-")
        self.path = Path(self.temp.name) / "task-outcome-v3.jsonl"

    def tearDown(self) -> None:
        self.temp.cleanup()

    @staticmethod
    def event(index: int) -> dict:
        return {
            "event_id": "EVT_scale_%05d" % index, "event_type": "TURN_OPENED",
            "captured_at": "2026-09-22T00:00:%02d.000+00:00" % (index % 60),
            "project_id": "scale-project", "repo_fingerprint": "sha256:" + "a" * 64,
            "session_id": "session-%d" % index, "turn_id": "turn-%d" % index,
            "task_id": "task-%d" % index,
        }

    def test_append_revalidates_earliest_history_before_writing(self) -> None:
        for index in range(3):
            events.append_event(self.path, self.event(index))
        lines = self.path.read_text(encoding="utf-8").splitlines()
        lines[0] = lines[0].replace("scale-project", "tampered-project")
        self.path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        before = self.path.read_bytes()
        with self.assertRaises(events.EventContractError):
            events.append_event(self.path, self.event(3))
        self.assertEqual(before, self.path.read_bytes())

    def test_segmented_chain_keeps_order_and_detects_truncation(self) -> None:
        previous = os.environ.get("CP_ASSISTANT_EVENT_SEGMENT_BYTES")
        os.environ["CP_ASSISTANT_EVENT_SEGMENT_BYTES"] = "256"
        try:
            for index in range(6):
                events.append_event(self.path, self.event(index))
        finally:
            if previous is None:
                os.environ.pop("CP_ASSISTANT_EVENT_SEGMENT_BYTES", None)
            else:
                os.environ["CP_ASSISTANT_EVENT_SEGMENT_BYTES"] = previous
        result = events.verify_event_chain(self.path)
        self.assertEqual(6, result["record_count"])
        first = sorted(self.path.parent.glob("task-outcome-v3.segment-*.jsonl"))[0]
        first.write_bytes(first.read_bytes()[:-1])
        with self.assertRaises(events.EventContractError):
            events.verify_event_chain(self.path)

    def test_concurrent_appends_keep_a_complete_chain(self) -> None:
        with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
            futures = [pool.submit(events.append_event, self.path, self.event(index), None,
                                   lock_timeout=5.0) for index in range(12)]
            for future in futures:
                future.result()
        self.assertEqual(12, events.verify_event_chain(self.path)["record_count"])

    def test_shared_identity_resolution_reads_repository_once(self) -> None:
        root = Path(self.temp.name) / "repo"
        with mock.patch.object(events, "_repo_identity_source", return_value=(root, "origin")) as source:
            fingerprint, project_id = events.project_identity_for(str(root))
        self.assertEqual(1, source.call_count)
        self.assertTrue(fingerprint.startswith("sha256:"))
        self.assertTrue(project_id.startswith("repo-"))

    def test_shared_identity_matches_legacy_public_helpers(self) -> None:
        root = Path(self.temp.name) / "repo"
        with mock.patch.object(events, "_repo_identity_source", return_value=(root, "origin")):
            fingerprint, project_id = events.project_identity_for(str(root))
            self.assertEqual(fingerprint, events.stable_repo_fingerprint(str(root)))
            self.assertEqual(project_id, events.project_id_for(fingerprint, str(root)))


if __name__ == "__main__":
    unittest.main()
