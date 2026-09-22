from __future__ import annotations

import contextlib
import importlib.util
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
MANAGER = ROOT / "scripts" / "package_manager.py"
ENTRY = ROOT / "scripts" / "cp-assistant.py"
sys.path.insert(0, str(ROOT / "scripts"))
SPEC = importlib.util.spec_from_file_location("quick_status_manager", MANAGER)
assert SPEC and SPEC.loader
package_manager = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(package_manager)
ENTRY_SPEC = importlib.util.spec_from_file_location("quick_status_entry", ENTRY)
assert ENTRY_SPEC and ENTRY_SPEC.loader
cp_assistant = importlib.util.module_from_spec(ENTRY_SPEC)
ENTRY_SPEC.loader.exec_module(cp_assistant)


class QuickStatusTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="quick-status-")
        self.home = Path(self.temp.name) / "codex"
        self.home.mkdir()
        self.state_path = self.home / "cp-assistant-v6-state.json"
        self.patches = [
            mock.patch.object(package_manager, "codex_home", return_value=self.home),
            mock.patch.object(package_manager, "_probe_plugin_host", side_effect=AssertionError("host probe")),
            mock.patch.object(package_manager, "verify_payload", side_effect=AssertionError("payload verification")),
            mock.patch.object(package_manager, "payload_report", side_effect=AssertionError("payload report")),
            mock.patch.object(package_manager, "_diagnostic_facts", side_effect=AssertionError("stability reread")),
        ]
        for patcher in self.patches:
            patcher.start()

    def tearDown(self):
        for patcher in reversed(self.patches):
            patcher.stop()
        self.temp.cleanup()

    def _state(self, **changes):
        value = {
            "schema_version": 3, "package": package_manager.PACKAGE, "version": package_manager.VERSION,
            "mode": "plugin", "components": {"enhancement": {"status": "MANAGED"}},
            "managed_hashes": {}, "payload_identity": {},
        }
        value.update(changes)
        self.state_path.write_text(json.dumps(value), encoding="utf-8")

    def _quick(self, mode=None):
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            package_manager.status("user", mode, None, summary=False, quick=True)
        return json.loads(output.getvalue())

    def test_quick_is_bounded_read_only_and_never_passes(self):
        self._state()
        before = {path.relative_to(self.home): path.read_bytes() for path in self.home.rglob("*") if path.is_file()}
        value = self._quick()
        after = {path.relative_to(self.home): path.read_bytes() for path in self.home.rglob("*") if path.is_file()}
        self.assertEqual(before, after)
        self.assertEqual(("cp-assistant-quick-status/1", "QUICK", "UNKNOWN"),
                         (value["schema"], value["query_tier"], value["overall"]))
        self.assertEqual("NOT_EVALUATED", value["current_check"])
        self.assertTrue(value["read_only"])
        self.assertFalse(value["authorization_evidence"])
        self.assertIsNone(value["last_full_validation_at"])
        self.assertEqual("DECLARED_MANAGED", value["file_state"]["status"])
        self.assertEqual("NOT_EVALUATED", value["registration_state"]["status"])
        self.assertEqual("NOT_EVALUATED", value["loaded_state"]["status"])
        self.assertEqual("NOT_EVALUATED", value["control_state"]["status"])
        self.assertIn("CACHE_PAYLOAD_VERIFICATION", value["not_evaluated"])

    def test_quick_missing_or_unmanaged_enhancement_is_not_available(self):
        missing = self._quick()
        self.assertEqual("MISSING", missing["installation_state"]["status"])
        self.assertEqual("UNKNOWN", missing["overall"])
        self.assertIsNotNone(missing["next_action_detail"])
        self._state(components={"enhancement": {"status": "EXTERNAL"}})
        declared = self._quick()
        self.assertEqual("DECLARED_UNVERIFIED", declared["file_state"]["status"])
        self.assertEqual("UNKNOWN", declared["overall"])

    def test_base_only_installation_is_not_reported_as_missing_enhancement(self):
        base = {
            "schema_version": 1, "package": package_manager.PACKAGE,
            "marketplace": package_manager.BASE_MARKETPLACE,
            "market_root": str(package_manager.base_marketplace_root()),
            "status": "INSTALLED", "version": package_manager.VERSION,
        }
        package_manager.base_state_path().write_text(json.dumps(base), encoding="utf-8")
        value = self._quick()
        self.assertEqual("BASE_ONLY", value["installation_state"]["status"])
        self.assertEqual("PRESENT", value["base_installation_state"]["status"])
        self.assertEqual("MISSING", value["enhancement_installation_state"]["status"])
        self.assertEqual("UNKNOWN", value["overall"])
        self.assertIsNone(value["next_action_detail"])

    def test_corrupt_state_is_blocked_without_repair(self):
        self.state_path.write_bytes(b"not-json")
        before = self.state_path.read_bytes()
        value = self._quick()
        self.assertEqual(before, self.state_path.read_bytes())
        self.assertEqual("BLOCKED", value["overall"])
        self.assertEqual("STATE_UNREADABLE_OR_INVALID", value["state_error"])
        self.assertEqual("INSPECT_MANAGED_STATE", value["next_action_detail"]["code"])

    def test_live_transaction_precedes_corrupt_state(self):
        self.state_path.write_bytes(b"not-json")
        journal = package_manager.transaction_path("user")
        journal.write_text(json.dumps({"schema_version": package_manager.JOURNAL_SCHEMA,
                                       "scope": "user", "stage": "APPLYING"}), encoding="utf-8")
        value = self._quick()
        self.assertEqual("BLOCKED", value["overall"])
        self.assertIsNotNone(value["live_transaction"])
        self.assertEqual("RECOVER_INSTALLATION_TRANSACTION", value["next_action_detail"]["code"])

    def test_requested_mode_mismatch_is_blocked_and_scope_is_not_expanded(self):
        self._state(mode="standalone")
        value = self._quick(mode="plugin")
        self.assertEqual("BLOCKED", value["overall"])
        self.assertEqual("REQUESTED_MODE_MISMATCH", value["mode_error"])
        self.assertEqual("user", value["scope"])

    def test_quick_output_is_stable_except_collection_time(self):
        self._state()
        left, right = self._quick(), self._quick()
        left.pop("collected_at")
        right.pop("collected_at")
        self.assertEqual(left, right)

    def test_changed_second_read_is_unknown_and_drops_recovery_action(self):
        self.state_path.write_bytes(b"not-json")
        journal = package_manager.transaction_path("user")
        journal.write_text(json.dumps({"schema_version": package_manager.JOURNAL_SCHEMA,
                                       "scope": "user", "stage": "APPLYING"}), encoding="utf-8")
        first = package_manager._quick_installation_facts_once("user", None, None)
        journal.unlink()
        second = package_manager._quick_installation_facts_once("user", None, None)
        with mock.patch.object(package_manager, "_quick_installation_facts_once", side_effect=[first, second]):
            value = package_manager._quick_installation_facts("user", None, None)
        self.assertEqual("UNKNOWN", value["overall"])
        self.assertEqual("INSTALLATION_CHANGED_DURING_READ", value["sample_error"])
        self.assertEqual("VERIFY_INSTALLATION", value["next_action_detail"]["code"])

    def test_unified_entry_displays_quick_tier_causes_and_limits(self):
        payload = {"overall": "UNKNOWN", "query_tier": "QUICK", "current_check": "NOT_EVALUATED",
                   "causes": [{"id": "installation-state", "detail": "INSTALLATION_STATE_MISSING"}],
                   "not_evaluated": ["HOST_PROBE", "CACHE_PAYLOAD_VERIFICATION"]}
        output = io.StringIO()
        with mock.patch.object(cp_assistant, "_entry", side_effect=lambda _target, _args: (print(json.dumps(payload)), 0)[1]), \
                contextlib.redirect_stdout(output):
            self.assertEqual(0, cp_assistant.main(["status", "--quick"]))
        rendered = output.getvalue()
        self.assertIn("查询层级： QUICK", rendered)
        self.assertIn("当前完整检查： NOT_EVALUATED", rendered)
        self.assertIn("INSTALLATION_STATE_MISSING", rendered)
        self.assertIn("CACHE_PAYLOAD_VERIFICATION", rendered)


if __name__ == "__main__":
    unittest.main()
