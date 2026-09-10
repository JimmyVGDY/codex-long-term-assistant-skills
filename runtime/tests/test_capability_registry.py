"""中文：25 项 AUTO 注册表、功能级降级和偏好 CAS。 English: AUTO registry, per-feature degradation, and preference CAS."""
from __future__ import annotations

import json
import subprocess
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import test_capability_store as fixtures
from cp_runtime.capability_registry import (PreferenceStore, load_registry, migrate_legacy_classification,
                                            read_install_migration, select_capability)
from cp_runtime.capability_store import CapabilityError

ROOT = Path(__file__).resolve().parents[2]
REGISTRY = ROOT / "config" / "capability-registry-v1.json"
EXPECTED_NAMES = [
    "backend-engineering", "ai-engineering", "frontend-engineering", "data-middleware-infrastructure",
    "log-observability-analysis", "engineering-quality-delivery", "multi-agent-independent-review",
    "technical-document-writing", "long-running-task-memory", "controlled-evolution-governance",
    "project-identity-profile", "capability-index", "controlled-write-operation", "delegation-budget",
    "checkpoint-memory", "hooks-observation-queue", "feedback-finalization", "controlled-evolution",
    "independent-reviewers", "installer-lifecycle", "codex-compatibility", "onboarding", "docs-release",
    "diagnostics-inventory", "approval-evidence-finalization",
]


class CapabilityRegistryTests(unittest.TestCase):
    def setUp(self):
        fixtures.CapabilityStoreTests.setUp(self)
        self.registry = load_registry(REGISTRY)
        self.preferences = PreferenceStore(self.profile, self.repo)

    tearDown = fixtures.CapabilityStoreTests.tearDown

    def test_registry_has_exact_c01_c25_mapping_and_digest(self):
        self.assertEqual(["C%02d" % number for number in range(1, 26)],
                         [entry["capability_id"] for entry in self.registry["entries"]])
        self.assertEqual(EXPECTED_NAMES, [entry["name"] for entry in self.registry["entries"]])
        self.assertEqual(64, len(self.registry["registry_digest"]))
        self.assertTrue(all(entry["default_mode"] == "AUTO" and entry["bootstrap_level"] == "BASIC"
                            for entry in self.registry["entries"]))

    def test_registry_rejects_missing_renamed_and_duplicate_entries(self):
        for mutation, code in (
            (lambda value: value["entries"].pop(), "REGISTRY_COUNT"),
            (lambda value: value["entries"][0].update(capability_id="C25"), "REGISTRY_ID_ORDER"),
            (lambda value: value["entries"][1].update(name=value["entries"][0]["name"]), "REGISTRY_NAME"),
        ):
            with self.subTest(code=code):
                value = json.loads(REGISTRY.read_text(encoding="utf-8"))
                mutation(value)
                path = self.base / (code + ".json")
                path.write_text(json.dumps(value), encoding="utf-8")
                with self.assertRaisesRegex(CapabilityError, code):
                    load_registry(path)

    def test_selector_full_degraded_max_and_explicit_off(self):
        c07 = next(entry for entry in self.registry["entries"] if entry["capability_id"] == "C07")
        all_ready = {name: True for name in c07["assisted_prerequisites"] + c07["full_prerequisites"]}
        full = select_capability(self.registry, "C07", all_ready, risk="STRICT")
        self.assertEqual("FULL", full["effective_level"])
        self.assertEqual("STRICT", full["risk"])
        self.assertFalse(full["authorization"])
        self.assertEqual("NOT_AUTHORIZED", full["action_status"])
        degraded = select_capability(self.registry, "C07", {}, risk="LIGHT")
        self.assertEqual("BASIC", degraded["effective_level"])
        self.assertEqual("PREREQUISITE_DEGRADED", degraded["reason_codes"][0])
        capped = select_capability(self.registry, "C07", all_ready,
                                   {"configured_mode": "AUTO", "max_level": "ASSISTED"})
        self.assertEqual("ASSISTED", capped["effective_level"])
        self.assertEqual("MAX_LEVEL_ASSISTED", capped["reason_codes"][0])
        off = select_capability(self.registry, "C07", all_ready,
                                {"configured_mode": "OFF", "max_level": "FULL"}, risk="STRICT")
        self.assertEqual(("OFF", "STRICT", "EXPLICIT_OFF"),
                         (off["effective_level"], off["risk"], off["reason_codes"][0]))

    def test_missing_preference_is_auto_and_does_not_write(self):
        self.assertIsNone(self.preferences.read())
        self.assertIsNone(self.preferences.preference("C01"))
        self.assertFalse(self.preferences.path.exists())
        selected = select_capability(self.registry, "C01", {})
        self.assertEqual(("AUTO", "BASIC"), (selected["configured_mode"], selected["effective_level"]))
        self.assertFalse(self.preferences.path.exists())

    def test_preference_cas_idempotency_and_per_capability_isolation(self):
        first = self.preferences.set_preference("C07", "OFF", None, None)
        self.assertEqual(0, first["revision"])
        same = self.preferences.set_preference("C07", "OFF", None, 0)
        self.assertEqual(first, same)
        second = self.preferences.set_preference("C12", "AUTO", "ASSISTED", 0)
        self.assertEqual(1, second["revision"])
        self.assertEqual("OFF", second["preferences"]["C07"]["configured_mode"])
        with self.assertRaisesRegex(CapabilityError, "PREFERENCE_REVISION_CONFLICT"):
            self.preferences.set_preference("C12", "AUTO", "FULL", 0)

    def test_corrupt_preference_never_becomes_auto_permission(self):
        self.preferences.set_preference("C13", "AUTO", "BASIC", None)
        self.preferences.path.write_bytes(b"{broken")
        with self.assertRaisesRegex(CapabilityError, "PREFERENCE_RECORD_INVALID"):
            self.preferences.read()

    def test_legacy_mapping_is_explicit_and_never_authorizes_or_accepts_scan(self):
        expected = {"DEFAULT_OFF": ("AUTO", "BASIC"), "USER_OFF": ("OFF", None),
                    "UNKNOWN_OFF": ("OFF", None), "LEGACY_ON": ("AUTO", "BASIC")}
        for source, pair in expected.items():
            with self.subTest(source=source):
                result = migrate_legacy_classification(source)
                self.assertEqual(pair, (result["configured_mode"], result["max_level"]))
                self.assertFalse(result["authorization"])
                self.assertFalse(result["scan_consent"])
        with self.assertRaisesRegex(CapabilityError, "LEGACY_CLASSIFICATION_UNKNOWN"):
            migrate_legacy_classification("GATE_ENABLED")

    def test_cli_registry_select_and_preference_readback(self):
        def invoke(*arguments):
            result = subprocess.run(
                [sys.executable, str(ROOT / "scripts" / "cp-runtime.py"), *arguments],
                cwd=ROOT, check=True, capture_output=True, text=True, encoding="utf-8",
            )
            return json.loads(result.stdout)

        registry = invoke("capability-registry")
        self.assertEqual(25, len(registry["entries"]))
        selected = invoke("capability-select", "--profile", str(self.profile), "--repo-path", str(self.repo),
                          "--capability-id", "C01", "--prerequisite", "source_context=true",
                          "--prerequisite", "validation_evidence=true", "--risk", "STANDARD")
        self.assertEqual(("FULL", "STANDARD", False),
                         (selected["effective_level"], selected["risk"], selected["authorization"]))
        invoke("capability-preference-set", "--profile", str(self.profile), "--repo-path", str(self.repo),
               "--capability-id", "C01", "--configured-mode", "OFF")
        shown = invoke("capability-preference-show", "--profile", str(self.profile), "--repo-path", str(self.repo),
                       "--capability-id", "C01")
        self.assertTrue(shown["persisted"])
        self.assertEqual("OFF", shown["preference"]["configured_mode"])

    def test_install_state_lazy_migration_is_exact_cas_and_rejects_tampering(self):
        migration = {"schema_version":"capability-preference-migration/1", "classification":"DEFAULT_OFF",
                     "evidence":"known-version-installer-default", "configured_mode":"AUTO", "max_level":"BASIC",
                     "authorization":False, "scan_consent":False, "gate_policy_excluded":True,
                     "gate_task_excluded":True, "operation_v2_excluded":True,
                     "application":"PROJECT_LAZY_CAS_AFTER_IDENTITY_BINDING"}
        state = self.base / "install-state.json"
        state.write_text(json.dumps({"preference_migration": migration}), encoding="utf-8")
        self.assertEqual("DEFAULT_OFF", read_install_migration(state)["classification"])
        result = subprocess.run(
            [sys.executable, str(ROOT / "scripts" / "cp-runtime.py"), "capability-preference-migrate",
             "--profile", str(self.profile), "--repo-path", str(self.repo), "--capability-id", "C01",
             "--install-state", str(state)], cwd=ROOT, check=True, capture_output=True, text=True, encoding="utf-8",
        )
        self.assertEqual("AUTO", json.loads(result.stdout)["preferences"]["C01"]["configured_mode"])
        migration["authorization"] = True
        state.write_text(json.dumps({"preference_migration": migration}), encoding="utf-8")
        with self.assertRaisesRegex(CapabilityError, "MIGRATION_RECORD_INVALID"):
            read_install_migration(state)


if __name__ == "__main__":
    unittest.main()
