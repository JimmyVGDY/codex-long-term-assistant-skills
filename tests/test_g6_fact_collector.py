"""中文：限定 Git 范围的计数可重现，不能变成难度分数。

English: Scoped Git counts stay reproducible and do not become difficulty scores.
"""
from __future__ import annotations

import subprocess
import tempfile
import unittest
import os
from pathlib import Path
from unittest import mock

from cp_runtime import g6_fact_collector as collector
from cp_runtime.g6_fact_collector import (collect, metric_dictionary,
                                          read_metric_receipt, store_metric_receipt)
from cp_runtime.g6_hook_v1 import _facts
from cp_runtime.routing_contract import RoutingError


class G6FactCollectorTests(unittest.TestCase):
    def test_scoped_diff_and_untracked_lines(self):
        with tempfile.TemporaryDirectory() as temporary:
            repo = Path(temporary)
            def git(*args):
                return subprocess.run(["git", "-C", str(repo), *args],
                                      capture_output=True, check=True).stdout.decode().strip()
            git("init", "-q")
            git("config", "user.name", "Test")
            git("config", "user.email", "test@example.invalid")
            (repo / "module_a").mkdir()
            (repo / "module_b").mkdir()
            (repo / "module_a" / "file.py").write_text("one\n", encoding="utf8")
            (repo / "module_b" / "other.py").write_text("untouched\n", encoding="utf8")
            git("add", ".")
            git("commit", "-qm", "baseline")
            baseline = git("rev-parse", "HEAD")
            (repo / "module_a" / "file.py").write_text("one\ntwo\n", encoding="utf8")
            (repo / "module_a" / "state.py").write_text("x\ny\n", encoding="utf8")
            result = collect(repo, baseline_commit=baseline, scope_paths=["module_a"])
            self.assertEqual(result["changed_files"], 2)
            self.assertEqual(result["changed_lines"], 3)
            self.assertEqual(result["changed_modules"], 1)
            self.assertEqual(result["contract_categories_hit"], ["state_boundary"])
            self.assertIn("neither task difficulty nor defect proof", result["interpretation"])
            (repo / "module_a" / "state.py").write_text("p\nq\n", encoding="utf8")
            refreshed = collect(repo, baseline_commit=baseline, scope_paths=["module_a"])
            self.assertEqual(refreshed["changed_lines"], result["changed_lines"])
            self.assertNotEqual(refreshed["source_ref"], result["source_ref"])

    def test_unsafe_scope_fails_before_git(self):
        with self.assertRaises(RoutingError):
            collect(Path.cwd(), baseline_commit="a" * 40, scope_paths=["../secrets"])

    def test_dictionary_registers_units_sources_types_and_unknown_rules(self):
        rows = metric_dictionary()["metrics"]
        required = {"metric_id", "definition", "unit", "source", "calculation_version",
                    "scope", "baseline", "freshness", "missing_behavior", "decision_use",
                    "value_type", "data_class"}
        self.assertTrue(rows)
        self.assertTrue(all(set(row) == required for row in rows))
        self.assertEqual(len(rows), len({row["metric_id"] for row in rows}))
        self.assertTrue({"scope", "contract", "material", "resource", "scheduling", "execution",
                         "validation", "review", "actual_cost"}.issubset({row["scope"] for row in rows}))
        self.assertTrue({"measured", "deterministic_derived", "estimate", "policy_parameter",
                         "semantic_suggestion"}.issubset({row["data_class"] for row in rows}))
        self.assertIn("never difficulty", next(row for row in rows if row["metric_id"] ==
                                                "changed_files")["decision_use"])
        self.assertIn("UNKNOWN", next(row for row in rows if row["metric_id"] ==
                                         "host_credits")["missing_behavior"])
        by_id = {row["metric_id"]: row for row in rows}
        self.assertIn("not-started", by_id["attempts_used"]["definition"])
        self.assertIn("host-created", by_id["created_calls"]["source"])
        self.assertIn("unknown creation state", by_id["active_reservations"]["definition"])

    def test_late_untracked_source_keeps_observation_but_not_a_complete_count(self):
        with tempfile.TemporaryDirectory() as temporary:
            repo = Path(temporary)
            seen_deadlines = []

            def run(_repo, *args, deadline, remaining_output):
                seen_deadlines.append(deadline)
                if args[0] == "rev-parse":
                    return (str(repo) + "\n").encode()
                if args[0] == "cat-file":
                    return b""
                if args[0] == "diff":
                    return b"1\t0\tmodule_a/state.py\x00"
                raise collector.CollectionUnavailable("time_budget")

            with mock.patch.object(collector, "_run", side_effect=run):
                result = collect(repo, baseline_commit="a" * 40,
                                 scope_paths=[collector.ALL_REPO_SCOPE])
            self.assertEqual(len(set(seen_deadlines)), 1)
            self.assertEqual(result["deadline_ms"], 5000)
            self.assertEqual(result["collection_status"], "PARTIAL")
            self.assertEqual(result["observed_tracked_files"], 1)
            self.assertIsNone(result["changed_files"])
            self.assertIsNone(result["changed_lines"])
            self.assertEqual(result["metrics"]["changed_files"]["type"], "unknown")
            self.assertEqual(result["metrics"]["changed_files"]["missing_reason"], "time_budget")
            self.assertIsNotNone(result["source_ref"])
            with tempfile.TemporaryDirectory() as home, \
                 mock.patch.dict(os.environ, CODEX_HOME=home):
                identity = {"project_id": "partial", "repo_fingerprint": "sha256:" + "a" * 64}
                receipt_ref = store_metric_receipt(result, identity=identity,
                                                   host_session_ref="sha256:" + "b" * 64,
                                                   baseline_sha256="c" * 64, repo_path=repo)
                receipt = read_metric_receipt(receipt_ref, identity=identity,
                                              host_session_ref="sha256:" + "b" * 64,
                                              baseline_sha256="c" * 64)
            self.assertEqual(receipt["observed_tracked_files"], 1)
            self.assertEqual(receipt["observed_tracked_lines"], 1)
            self.assertIsNone(receipt["metrics"]["changed_files"]["value"])

    def test_deadline_during_untracked_scan_cannot_report_an_undercount(self):
        with tempfile.TemporaryDirectory() as temporary:
            repo = Path(temporary)
            (repo / "a.py").write_text("a\n", encoding="utf-8")
            (repo / "b.py").write_text("b\n", encoding="utf-8")

            def run(_repo, *args, deadline, remaining_output):
                if args[0] == "rev-parse":
                    return (str(repo) + "\n").encode()
                if args[0] == "ls-files":
                    return b"a.py\x00b.py\x00"
                return b""

            with mock.patch.object(collector, "_run", side_effect=run), \
                 mock.patch.object(Path, "open", side_effect=AssertionError("late file read")), \
                 mock.patch.object(collector.time, "monotonic", side_effect=[0.0, 6.0, 6.0, 6.0]):
                result = collect(repo, baseline_commit="a" * 40,
                                 scope_paths=[collector.ALL_REPO_SCOPE])
            self.assertEqual(result["collection_status"], "PARTIAL")
            self.assertIsNone(result["changed_files"])
            self.assertIsNone(result["metrics"]["changed_files"]["value"])
            self.assertEqual(result["missing_reason"], "time_budget")

    def test_content_budget_preserves_file_count_but_marks_lines_unknown(self):
        with tempfile.TemporaryDirectory() as temporary:
            repo = Path(temporary)
            (repo / "a.py").write_bytes(b"a" * 15)
            (repo / "b.py").write_bytes(b"b" * 15)

            def run(_repo, *args, deadline, remaining_output):
                if args[0] == "rev-parse":
                    return (str(repo) + "\n").encode()
                if args[0] == "ls-files":
                    return b"a.py\x00b.py\x00"
                return b""

            with mock.patch.object(collector, "MAX_OUTPUT", 20), \
                 mock.patch.object(collector, "_run", side_effect=run):
                result = collect(repo, baseline_commit="a" * 40,
                                 scope_paths=[collector.ALL_REPO_SCOPE])
            self.assertEqual(result["changed_files"], 2)
            self.assertIsNone(result["changed_lines"])
            self.assertEqual(result["missing_reason"], "material_byte_budget")

    def test_unavailable_git_is_unknown_not_zero(self):
        with tempfile.TemporaryDirectory() as temporary:
            result = collect(Path(temporary), baseline_commit="a" * 40,
                             scope_paths=[collector.ALL_REPO_SCOPE])
        self.assertEqual(result["collection_status"], "UNKNOWN")
        self.assertIsNone(result["changed_files"])
        self.assertIsNone(result["metrics"]["host_credits"]["value"])
        self.assertEqual(result["metrics"]["host_credits"]["type"], "unknown")

    def test_command_uses_remaining_deadline_and_bounds_output_before_reading(self):
        seen = {}

        def git(_args, *, stdout, stderr, timeout, check, env):
            seen["timeout"] = timeout
            self.assertEqual(env["GIT_OPTIONAL_LOCKS"], "0")
            stdout.write(b"abcd")
            return subprocess.CompletedProcess(_args, 0)

        with mock.patch.object(collector.time, "monotonic", return_value=12.0), \
             mock.patch.object(collector.subprocess, "run", side_effect=git):
            with self.assertRaises(collector.CollectionUnavailable) as failure:
                collector._run(Path.cwd(), "status", deadline=15.0, remaining_output=3)
        self.assertEqual(seen["timeout"], 3.0)
        self.assertEqual(failure.exception.reason, "output_budget")
        with mock.patch.object(collector.time, "monotonic", return_value=15.0), \
             mock.patch.object(collector.subprocess, "run") as launched:
            with self.assertRaises(collector.CollectionUnavailable) as failure:
                collector._run(Path.cwd(), "status", deadline=15.0, remaining_output=100)
        launched.assert_not_called()
        self.assertEqual(failure.exception.reason, "time_budget")

    def test_git_environment_keeps_only_exact_host_safe_directory(self):
        with tempfile.TemporaryDirectory() as temporary:
            repo = Path(temporary)
            injected = {"GIT_CONFIG_COUNT": "3", "GIT_CONFIG_KEY_0": "safe.directory",
                        "GIT_CONFIG_VALUE_0": str(repo), "GIT_CONFIG_KEY_1": "safe.directory",
                        "GIT_CONFIG_VALUE_1": "*", "GIT_CONFIG_KEY_2": "alias.status",
                        "GIT_CONFIG_VALUE_2": "!untrusted-command"}
            with mock.patch.dict(os.environ, injected):
                environment = collector._git_env(repo)
        self.assertEqual(environment["GIT_CONFIG_COUNT"], "1")
        self.assertEqual(environment["GIT_CONFIG_KEY_0"], "safe.directory")
        self.assertEqual(environment["GIT_CONFIG_VALUE_0"], str(repo))
        self.assertNotIn("GIT_CONFIG_KEY_1", environment)
        self.assertEqual(environment["GIT_TERMINAL_PROMPT"], "0")

    def test_metric_receipt_is_retrievable_by_bound_ref_and_rejects_tampering(self):
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            repo = base / "repo"
            repo.mkdir()
            home = base / "codex-home"

            def git(*args):
                return subprocess.run(["git", "-C", str(repo), *args],
                                      capture_output=True, check=True).stdout.decode().strip()

            git("init", "-q")
            git("config", "user.name", "Test")
            git("config", "user.email", "test@example.invalid")
            (repo / "app.py").write_text("one\n", encoding="utf-8")
            git("add", ".")
            git("commit", "-qm", "baseline")
            head = git("rev-parse", "HEAD")
            (repo / "app.py").write_text("one\ntwo\n", encoding="utf-8")
            report = collect(repo, baseline_commit=head, scope_paths=[collector.ALL_REPO_SCOPE])
            identity = {"project_id": "test", "repo_fingerprint": "sha256:" + "a" * 64}
            session_ref = "sha256:" + "b" * 64
            baseline_sha256 = "c" * 64
            with mock.patch.dict(os.environ, CODEX_HOME=str(home)):
                receipt_ref = store_metric_receipt(report, identity=identity,
                                                   host_session_ref=session_ref,
                                                   baseline_sha256=baseline_sha256,
                                                   repo_path=repo)
                receipt = read_metric_receipt(receipt_ref, identity=identity,
                                              host_session_ref=session_ref,
                                              baseline_sha256=baseline_sha256)
                self.assertEqual(receipt["metrics"]["changed_files"]["value"], 1)
                self.assertEqual(receipt["measurement_source_ref"], report["source_ref"])
                with self.assertRaises(collector.MetricReceiptIntegrityError):
                    read_metric_receipt(receipt_ref,
                                        identity={**identity, "project_id": "foreign"},
                                        host_session_ref=session_ref,
                                        baseline_sha256=baseline_sha256)
                path = collector._receipt_path(receipt_ref)
                self.assertNotIn("one\\ntwo", path.read_text(encoding="utf-8"))
                path.write_text("{}\n", encoding="utf-8")
                with self.assertRaises(collector.MetricReceiptIntegrityError):
                    read_metric_receipt(receipt_ref, identity=identity,
                                        host_session_ref=session_ref,
                                        baseline_sha256=baseline_sha256)

    def test_real_hook_facts_bind_measurement_ref_without_promoting_scope_to_difficulty(self):
        source_ref = "sha256:" + "c" * 64
        root = {"repo_path": str(Path.cwd()), "host_session_ref": "sha256:" + "a" * 64,
                "identity": {"project_id": "synthetic", "repo_fingerprint": "sha256:" + "b" * 64},
                "task_id": "synthetic"}
        args = {"task_name": "sample", "agent_type": "explorer", "message": "Read files."}
        with mock.patch("cp_runtime.g6_hook_v1.repo_snapshot",
                        return_value={"head": "d" * 40, "sha256": "e" * 64}), \
             mock.patch("cp_runtime.g6_hook_v1.collect_scope_facts",
                        return_value={"source_ref": source_ref, "collection_status": "PARTIAL",
                                      "changed_lines": None}) as measured, \
             mock.patch("cp_runtime.g6_hook_v1.store_metric_receipt",
                        return_value="sha256:" + "f" * 64):
            facts = _facts(root, args, persist=True)
        measured.assert_called_once()
        self.assertEqual(facts["source_refs"], ["sha256:" + "f" * 64])
        self.assertIn("scope_metrics", facts["missing_evidence"])
        self.assertEqual(facts["task_kind"], "unknown")
        with mock.patch("cp_runtime.g6_hook_v1.repo_snapshot",
                        return_value={"head": "d" * 40, "sha256": "e" * 64}), \
             mock.patch("cp_runtime.g6_hook_v1.collect_scope_facts",
                        return_value={"source_ref": source_ref, "collection_status": "COMPLETE",
                                      "changed_lines": 1}), \
             mock.patch("cp_runtime.g6_hook_v1.store_metric_receipt") as writer:
            preview_facts = _facts(root, args)
        writer.assert_not_called()
        self.assertEqual(preview_facts["source_refs"], [])
        with mock.patch("cp_runtime.g6_hook_v1.repo_snapshot",
                        return_value={"head": "d" * 40, "sha256": "e" * 64}), \
             mock.patch("cp_runtime.g6_hook_v1.collect_scope_facts",
                        side_effect=RuntimeError("optional collector unavailable")):
            fallback = _facts(root, args)
        self.assertEqual(fallback["source_refs"], [])
        self.assertIn("scope_metrics", fallback["missing_evidence"])


if __name__ == "__main__":
    unittest.main()
