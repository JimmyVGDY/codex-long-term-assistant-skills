"""中文：验证澄清后的评测金标；夹具故意包含已知缺陷。

English: Verify clarified evaluation gold; fixtures intentionally include known defects.
"""
from __future__ import annotations

import hashlib
import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

FIXTURES = Path(__file__).parent / "fixtures" / "review-workflow-v2"


def load_case(name):
    module_name = "frozen_workflow_case_" + name.replace("-", "_")
    spec = importlib.util.spec_from_file_location(module_name, FIXTURES / (name + ".py"))
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


class ClarifiedCaseTests(unittest.TestCase):
    def test_six_frozen_sources_have_exact_hashes_and_new_identities(self):
        manifest = json.loads((FIXTURES / "cases.json").read_text(encoding="utf-8"))
        self.assertEqual("workflow-cases/2", manifest["schema_version"])
        self.assertEqual(6, len(manifest["cases"]))
        self.assertEqual(6, len({row["case_id"] for row in manifest["cases"]}))
        for row in manifest["cases"]:
            with self.subTest(case=row["case_id"]):
                self.assertNotEqual(row["case_id"], row["predecessor_case_id"])
                self.assertFalse(row["historical_study_mutated"])
                self.assertEqual(row["source_sha256"], hashlib.sha256(
                    (FIXTURES / row["source_file"]).read_bytes()).hexdigest())
                self.assertEqual(bool(row["expected_root_causes"]), row["expected_status"] == "blocking")

    def test_null_is_omission_and_non_null_unknown_outcomes_fail(self):
        mod = load_case("null-outcome")
        payload = {"event_type": " task_completed ", "project_id": "project-1",
                   "repo_fingerprint": "sha256:" + "a" * 64, "status": "FAILED"}
        expected = ("TASK_COMPLETED", "project-1", payload["repo_fingerprint"])
        self.assertEqual(expected, mod._validate_identity_and_terminal(payload))
        self.assertEqual(expected, mod._validate_identity_and_terminal({**payload, "terminal_outcome": None}))
        for outcome in mod.TERMINAL_OUTCOMES:
            self.assertEqual(expected, mod._validate_identity_and_terminal(
                {**payload, "terminal_outcome": " " + outcome.lower() + " "}))
        for outcome in ("", "success", 0, False, []):
            with self.subTest(outcome=outcome), self.assertRaises(mod.EventContractError):
                mod._validate_identity_and_terminal({**payload, "terminal_outcome": outcome})
        for key, value in (("event_type", "bogus"), ("project_id", "../foreign"),
                           ("repo_fingerprint", "sha256:" + "A" * 64)):
            with self.assertRaises(mod.EventContractError):
                mod._validate_identity_and_terminal({**payload, key: value})

    def test_file_replacement_error_precedence_and_real_regular_file_change(self):
        mod = load_case("file-replacement")
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "source.txt"
            path.write_bytes(b"abc")
            self.assertEqual(b"abc", mod.bounded_read(path, 3))
            with self.assertRaisesRegex(mod.CapabilityError, "TOO_LARGE"):
                mod.bounded_read(path, 2)
            original_safe = mod.safe_path
            for mutation, expected in (("regular", "READ_CHANGED"), ("missing", "UNREADABLE"),
                                       ("link-rejection", "LINK_REJECTED")):
                path.write_bytes(b"abc")
                calls = 0

                def final_check(candidate):
                    nonlocal calls
                    calls += 1
                    if calls == 2:
                        if mutation == "regular":
                            replacement = path.with_suffix(".new")
                            replacement.write_bytes(b"different regular file")
                            replacement.replace(path)
                        elif mutation == "missing":
                            path.unlink()
                        else:
                            # 中文：仅注入错误优先级，不构成原生符号链接证明。
                            # English: Only error precedence is injected; this is not native symlink proof.
                            raise mod.CapabilityError("LINK_REJECTED")
                    return original_safe(candidate)

                with self.subTest(mutation=mutation), patch.object(mod, "safe_path", final_check):
                    with self.assertRaisesRegex(mod.CapabilityError, expected):
                        mod.bounded_read(path)

    def test_reserved_aliases_are_real_counterexamples_not_false_positives(self):
        mod = load_case("reserved-aliases")
        for path in (".GIT/config", "source_manifest.json", "Source_Manifest.JSON"):
            self.assertEqual([path], mod._paths([path]))  # 中文：冻结的缺陷就是金标发现。 / English: Frozen defect is the gold finding.
        for paths in ([".git/config"], ["SOURCE_MANIFEST.json"], ["a", "a/b"],
                      ["a/b", "a"], ["Dir/a", "dir/b"], ["a", "a"], ["../x"], ["CON.txt"]):
            with self.assertRaises(mod.SourceError):
                mod._paths(paths)
        self.assertEqual(["a/b", "z"], mod._paths(["z", "a/b"]))

    def test_optional_identity_filters_and_freshness_are_distinct(self):
        mod = load_case("optional-identities")
        record = {"schema_version": 1, "project_id": "p", "task_id": "t", "evidence_id": "e",
                  "baseline": {"sha256": "current"}, "status": "valid"}
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "evidence.json"

            def write(value):
                value = dict(value)
                value["integrity"] = {"algorithm": "sha256-canonical-json",
                                      "sha256": mod.canonical_sha256(value)}
                path.write_text(json.dumps(value), encoding="utf-8")

            write(record)
            for project, task in ((None, None), ("", ""), ("p", "t"), (None, "t")):
                self.assertTrue(mod.check_evidence(path, Path(directory), project, task).valid)
            self.assertFalse(mod.check_evidence(path, None).valid)
            self.assertFalse(mod.check_evidence(path, Path(directory), "foreign", "t").valid)
            self.assertFalse(mod.check_evidence(path, Path(directory), "p", "foreign").valid)
            for changed in ({**record, "status": "failed"}, {**record, "baseline": {"sha256": "old"}}):
                write(changed)
                self.assertFalse(mod.check_evidence(path, Path(directory)).valid)
            path.write_text(json.dumps(record), encoding="utf-8")
            with self.assertRaises(mod.RuntimeContractError):
                mod.check_evidence(path, Path(directory))

    def test_display_name_gold_covers_meaning_and_supplementary_han(self):
        mod = load_case("display-names")
        self.assertEqual("!!!", mod._release_name("!!!", "en"))
        self.assertEqual("\U00020000", mod._release_name("\U00020000", "en"))
        with self.assertRaises(mod.ReleaseWorkflowError):
            mod._release_name("\U00020000", "zh-CN")
        chinese = mod._release_name("流程修复", "zh-CN")
        english = mod._release_name("Workflow repair", "en")
        self.assertEqual("V7.14.0 | 流程修复 / Workflow repair", mod._release_title("7.14.0", chinese, english))
        with self.assertRaises(mod.ReleaseWorkflowError):
            mod._release_title("7.14.0", mod._release_name("汉" * 30, "zh-CN"),
                               mod._release_name("é" * 80, "en"))
        for name in (" padded ", "x\u200by", "x\x00y"):
            with self.assertRaises(mod.ReleaseWorkflowError):
                mod._release_name(name, "en")

    def test_timezone_overflow_is_a_real_contract_failure(self):
        mod = load_case("timezone-overflow")
        window = {"created_at": "2026-09-28T00:00:00Z", "expires_at": "2026-09-29T00:00:00Z"}
        self.assertIsNone(mod.assert_current_window(window, "2026-09-28T08:00:00+08:00"))
        for now in ("2026-09-27T23:59:59Z", "2026-09-29T00:00:00Z", "bad", "2026-09-28T00:00:00"):
            with self.assertRaises(mod.RoutingError):
                mod.assert_current_window(window, now)
        for extreme in ("0001-01-01T00:00:00+01:00", "9999-12-31T23:59:59-01:00"):
            with self.assertRaises(OverflowError):
                mod.assert_current_window(window, extreme)  # 中文：这是冻结金标的精确反例。 / English: Exact counterexample to frozen gold.


if __name__ == "__main__":
    unittest.main()
