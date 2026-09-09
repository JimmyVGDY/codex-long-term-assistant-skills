"""中文：能力发现、查询、预算、分支失效与实际CLI行为。 English: Capability discovery, queries, budgets, branch invalidation, and real CLI behavior."""
from __future__ import annotations

import copy
import json
import subprocess
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import test_capability_store as fixtures
from cp_runtime import capability_index as index
from cp_runtime.capability_store import CapabilityError


class CapabilityIndexTests(unittest.TestCase):
    setUp = fixtures.CapabilityStoreTests.setUp
    tearDown = fixtures.CapabilityStoreTests.tearDown

    def test_python_public_entries_and_noop_repeated_scan(self):
        (self.repo / "app.py").write_text("def public():\n    return 1\n\ndef _private():\n    pass\n\nclass Service:\n    def method(self):\n        pass\n", encoding="utf-8")
        first = index.scan(self.store, ["app.py"])
        self.assertTrue(first["coverage"]["complete"])
        self.assertEqual(["Service", "public"], [e["symbol"] for e in self.store.read()["entries"]])
        before = self.store.current.read_bytes()
        with patch("cp_runtime.capability_store.atomic_write_bytes", side_effect=AssertionError("unexpected write")):
            second = index.scan(self.store, ["app.py"])
        self.assertFalse(second["changed"])
        self.assertEqual(before, self.store.current.read_bytes())
        self.assertEqual(2, second["cost"]["source_reads"])

    def test_javascript_exports_ignore_comments_and_string_content(self):
        (self.repo / "ui.tsx").write_text('// export function Fake() {}\nconst s = "export const Fake2 = 1";\nexport function Button() { return null; }\nexport const Panel = () => null;\nexport { Button as Action };\n', encoding="utf-8")
        index.scan(self.store, ["ui.tsx"])
        symbols = [e["symbol"] for e in self.store.read()["entries"]]
        self.assertEqual(["Action", "Button", "Panel"], symbols)

    def test_default_scan_excludes_agent_tooling_but_explicit_source_scope_works(self):
        for directory in (".agents/skills/example/scripts", ".codex/tools"):
            target = self.repo / directory / "helper.py"
            target.parent.mkdir(parents=True)
            target.write_text("def tooling_only():\n    return 1\n", encoding="utf-8")
        result = index.scan(self.store)
        self.assertEqual(["app.py"], [entry["path"] for entry in self.store.read()["entries"]])
        self.assertTrue(result["coverage"]["complete"])
        exclusions = {item["path"] for item in self.store.read()["coverage"]["limitations"] if item["reason"] == "EXCLUDED"}
        self.assertTrue({".agents", ".codex"}.issubset(exclusions))
        index.scan(self.store, [".agents/skills/example/scripts/helper.py"])
        self.assertEqual({"public", "tooling_only"}, {entry["symbol"] for entry in self.store.read()["entries"]})

    def test_explicit_python_exports_and_commonjs_boundary(self):
        (self.repo / "exports.py").write_text("from other import imported\n__all__ = ['imported', '_intentional']\ndef _intentional():\n    pass\ndef internal():\n    pass\n", encoding="utf-8")
        (self.repo / "adapter.cjs").write_text("exports.makeClient = function() {};\nmodule.exports = factory;\n", encoding="utf-8")
        index.scan(self.store, ["exports.py", "adapter.cjs"])
        self.assertEqual({"imported", "_intentional", "makeClient", "module.exports"}, {e["symbol"] for e in self.store.read()["entries"]})

    def test_body_byte_budget_includes_final_verification(self):
        (self.repo / "one.py").write_text("# " + "x" * 1000 + "\ndef one():\n    pass\n", encoding="utf-8")
        (self.repo / "two.py").write_text("# " + "x" * 1000 + "\ndef two():\n    pass\n", encoding="utf-8")
        with patch.object(index, "MAX_READ_BYTES", 2500):
            first = index.scan(self.store, ["one.py", "two.py"])
            self.assertFalse(first["coverage"]["complete"])
            self.assertEqual(2, first["cost"]["source_reads"])
            self.assertLessEqual(first["cost"]["source_bytes"], 2500)
            second = index.scan(self.store, resume=True)
            self.assertTrue(second["coverage"]["complete"])
            self.assertLessEqual(second["cost"]["source_bytes"], 2500)

    def test_context_read_race_aborts_instead_of_becoming_unknown(self):
        (self.repo / "pyproject.toml").write_text("[project]\nname='demo'\n", encoding="utf-8")
        original = index.ReadBudget.read
        def changing_context(budget, relative):
            if relative == "pyproject.toml":
                raise CapabilityError("READ_CHANGED")
            return original(budget, relative)
        with patch.object(index.ReadBudget, "read", changing_context):
            with self.assertRaisesRegex(CapabilityError, "CHANGED"):
                index.scan(self.store, ["app.py"])
        self.assertFalse(self.store.current.exists())

    def test_limited_query_receipt_does_not_embed_pending_paths(self):
        for n in range(8):
            (self.repo / f"task{n}.py").write_text(f"def task{n}():\n    pass\n", encoding="utf-8")
        with patch.object(index, "MAX_READS", 2):
            index.scan(self.store)
        result = index.query(self.store, "public")
        self.assertIn("pending_count", result["coverage"]["cursor"])
        self.assertNotIn("pending", result["coverage"]["cursor"])

    def test_budget_continuation_finishes_without_duplicate_ids(self):
        for n in range(7):
            (self.repo / f"part{n}.py").write_text(f"def task{n}():\n    pass\n", encoding="utf-8")
        with patch.object(index, "MAX_READS", 4):
            result = index.scan(self.store)
            self.assertFalse(result["coverage"]["complete"])
            rounds = 1
            while result["coverage"]["cursor"]:
                self.assertLess(rounds, 10)
                self.assertLessEqual(result["cost"]["source_reads"], 4)
                result = index.scan(self.store, resume=True)
                rounds += 1
        self.assertGreater(rounds, 1)
        entries = self.store.read()["entries"]
        self.assertEqual(8, len(entries))
        self.assertEqual(8, len({e["id"] for e in entries}))
        self.assertTrue(result["coverage"]["complete"])

    def test_directory_budget_is_explicit_and_never_claims_complete(self):
        for n in range(8):
            (self.repo / f"file{n}.py").write_text("def f():\n    pass\n", encoding="utf-8")
        with patch.object(index, "MAX_PATHS", 3):
            result = index.scan(self.store)
        self.assertEqual(3, result["cost"]["enumerated_paths"])
        self.assertFalse(result["coverage"]["complete"])
        self.assertTrue(any(i["reason"] == "DIRECTORY_BUDGET" for i in result["coverage"]["limitations"]))

    def test_source_change_during_scan_aborts_whole_batch(self):
        original = index.ReadBudget.verify
        def change_then_verify(budget):
            (self.repo / "app.py").write_text("def changed():\n    return 2\n", encoding="utf-8")
            original(budget)
        with patch.object(index.ReadBudget, "verify", change_then_verify):
            with self.assertRaisesRegex(CapabilityError, "CHANGED"):
                index.scan(self.store, ["app.py"])
        self.assertFalse(self.store.current.exists())

    def test_query_rechecks_source_without_writing_index(self):
        index.scan(self.store, ["app.py"])
        before = self.store.current.read_bytes()
        current = index.query(self.store, "public")
        self.assertEqual("matched", current["candidates"][0]["freshness"])
        (self.repo / "app.py").write_text("def public():\n    return 99\n", encoding="utf-8")
        stale = index.query(self.store, "public")
        self.assertEqual("stale", stale["candidates"][0]["freshness"])
        self.assertIn("SOURCE_CHANGED", stale["candidates"][0]["current_check"]["reasons"])
        self.assertFalse(stale["candidates"][0]["current_check"]["semantic_reuse_approved"])
        self.assertTrue(stale["source_search_required"])
        self.assertEqual(before, self.store.current.read_bytes())

    def test_context_creation_and_change_are_detected(self):
        index.scan(self.store, ["app.py"])
        (self.repo / "pyproject.toml").write_text("[project]\nname='example'\n", encoding="utf-8")
        result = index.query(self.store, "public")
        self.assertIn("CONTEXT_CHANGED", result["candidates"][0]["current_check"]["reasons"])
        index.scan(self.store, ["app.py"])
        (self.repo / "pyproject.toml").write_text("[project]\nname='different'\n", encoding="utf-8")
        changed = index.query(self.store, "public")
        self.assertIn("REFERENCE_CHANGED", changed["candidates"][0]["current_check"]["reasons"])

    def test_branch_change_never_marks_another_branch_entry_removed(self):
        index.scan(self.store, ["app.py"])
        fixtures.git(self.repo, "checkout", "-qb", "branch-without-app")
        (self.repo / "app.py").unlink()
        index.scan(self.store, ["app.py"])
        entry = self.store.read()["entries"][0]
        self.assertEqual("candidate", entry["lifecycle"])
        self.assertEqual("stale", entry["freshness"])
        index.scan(self.store, ["app.py"])
        self.assertEqual("candidate", self.store.read()["entries"][0]["lifecycle"])

    def test_same_branch_explicit_missing_file_marks_removed(self):
        index.scan(self.store, ["app.py"])
        (self.repo / "app.py").unlink()
        index.scan(self.store, ["app.py"])
        self.assertEqual("removed", self.store.read()["entries"][0]["lifecycle"])
        self.assertEqual([], index.query(self.store, "public")["candidates"])
        self.assertEqual(1, len(index.query(self.store, "public", include_inactive=True)["candidates"]))

    def test_manual_migration_preserves_id_and_inactive_filter(self):
        index.scan(self.store, ["app.py"])
        record = self.store.read()
        entry = copy.deepcopy(record["entries"][0])
        (self.repo / "moved.py").write_bytes((self.repo / "app.py").read_bytes())
        entry["path"] = "moved.py"
        entry["summary"] = "公共任务能力"
        entry["verification"]["scope"] = "已确认迁移映射，依赖未全面核验"
        migrated = index.register(self.store, entry, record["revision"])
        self.assertEqual(entry["id"], migrated["entries"][0]["id"])
        self.assertEqual("moved.py", migrated["entries"][0]["path"])
        self.assertIsNotNone(migrated["entries"][0]["observed_at"])
        with patch("cp_runtime.capability_store.atomic_write_bytes", side_effect=AssertionError("unexpected write")):
            self.assertEqual(migrated, index.register(self.store, entry, migrated["revision"]))
        deprecated = index.lifecycle(self.store, entry["id"], "deprecated", "由新入口替代", migrated["revision"])
        self.assertEqual([], index.query(self.store, "公共")["candidates"])
        self.assertEqual(1, len(index.query(self.store, "公共", include_inactive=True)["candidates"]))
        with self.assertRaisesRegex(CapabilityError, "REVISION_CONFLICT"):
            index.lifecycle(self.store, entry["id"], "active", "复核", migrated["revision"])
        self.assertEqual(deprecated, self.store.read())

    def test_unsupported_and_secret_content_never_become_candidates(self):
        (self.repo / "other.go").write_text("package other\n", encoding="utf-8")
        (self.repo / "secret.py").write_text("secret = 'sk-" + "a" * 30 + "'\ndef leak():\n    pass\n", encoding="utf-8")
        result = index.scan(self.store, ["other.go", "secret.py"])
        self.assertEqual(0, result["entry_count"])
        self.assertFalse(result["coverage"]["complete"])
        self.assertIn({"path": None, "reason": "SENSITIVE_CONTENT"}, result["coverage"]["limitations"])
        self.assertNotIn("sk-", self.store.current.read_text(encoding="utf-8"))
        self.assertNotIn("def leak", self.store.current.read_text(encoding="utf-8"))
        self.assertNotIn("secret.py", self.store.read()["baseline"]["files"])

    def test_no_index_and_no_match_request_source_search(self):
        self.assertEqual("UNAVAILABLE", index.query(self.store, "unknown")["status"])
        self.assertFalse(self.store.current.exists())
        index.scan(self.store, ["app.py"])
        self.assertTrue(index.query(self.store, "unrelated")["source_search_required"])
        with self.assertRaises(CapabilityError):
            index.query(self.store, "public", 21)

    def test_explicit_dependency_invalidation_is_idempotent(self):
        index.scan(self.store, ["app.py"])
        record = self.store.read()
        result = index.invalidate(self.store, ["tests/test_shared.py"], record["revision"])
        self.assertEqual(1, result["invalidated_entries"])
        self.assertEqual("recheck", self.store.read()["entries"][0]["freshness"])
        with patch("cp_runtime.capability_store.atomic_write_bytes", side_effect=AssertionError("unexpected write")):
            repeated = index.invalidate(self.store, ["tests/test_shared.py"], result["revision"])
        self.assertFalse(repeated["changed"])
        self.assertEqual("PARTIAL", repeated["dependency_coverage"])

    def test_context_probe_cache_and_bound(self):
        budget = index.ReadBudget(self.repo)
        self.assertFalse(budget.context_exists("missing.json"))
        self.assertFalse(budget.context_exists("missing.json"))
        self.assertEqual(1, len(budget.context_probes))
        with patch.object(index, "MAX_PATHS", 1):
            with self.assertRaisesRegex(CapabilityError, "BUDGET"):
                budget.context_exists("another.json")

    def test_new_context_during_scan_aborts_batch(self):
        original = index.ReadBudget.verify
        def add_then_verify(budget):
            (self.repo / "pyproject.toml").write_text("[project]\nname='new'\n", encoding="utf-8")
            original(budget)
        with patch.object(index.ReadBudget, "verify", add_then_verify):
            with self.assertRaisesRegex(CapabilityError, "CHANGED"):
                index.scan(self.store, ["app.py"])
        self.assertFalse(self.store.current.exists())

    def test_stale_continuation_is_rejected(self):
        (self.repo / "second.py").write_text("def next_task():\n    pass\n", encoding="utf-8")
        with patch.object(index, "MAX_READS", 2):
            index.scan(self.store)
        fixtures.git(self.repo, "checkout", "-qb", "another")
        with self.assertRaisesRegex(CapabilityError, "CONTINUATION_STALE"):
            index.scan(self.store, resume=True)

    def test_cli_scan_query_and_validation(self):
        cli = Path(__file__).resolve().parents[2] / "scripts" / "cp-runtime.py"
        base = [sys.executable, str(cli)]
        identity = ["--profile", str(self.profile), "--repo-path", str(self.repo)]
        scan = subprocess.run([*base, "capability-scan", *identity, "--scope", "app.py"], check=True, capture_output=True)
        self.assertEqual(1, json.loads(scan.stdout)["entry_count"])
        query = subprocess.run([*base, "capability-query", *identity, "--term", "public"], check=True, capture_output=True)
        self.assertEqual("public", json.loads(query.stdout)["candidates"][0]["symbol"])
        validation = subprocess.run([*base, "capability-validate", *identity], check=True, capture_output=True)
        self.assertEqual("VALID", json.loads(validation.stdout)["status"])
        old = subprocess.run([*base, "project-validate", "--profile", str(self.profile), "--repo-path", str(self.repo)], check=True, capture_output=True)
        self.assertEqual("CAP-TEST", json.loads(old.stdout)["project_id"])


if __name__ == "__main__":
    unittest.main()
