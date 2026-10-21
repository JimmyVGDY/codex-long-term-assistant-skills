"""中文：全部宿主报告均为本地合成合同夹具，不代表真实 Desktop 行为证据。
English: All host reports here are local synthetic contract fixtures, not real Desktop behavior evidence.
"""
import importlib.util
import json
import sys
import tempfile
import unittest
from copy import deepcopy
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import routing_study as study

spec = importlib.util.spec_from_file_location("study_legacy_eval", ROOT / "scripts/routing-eval.py")
legacy = importlib.util.module_from_spec(spec)
spec.loader.exec_module(legacy)


class RoutingStudyTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.output = self.base / "study"
        self.suite = study.EVAL.read_json(ROOT / "tests/skill-routing-study-cases.json")
        self.environment = {"platform": "Windows-fixture", "runtime": "fixture-version",
                            "requested_model": "gpt-6-sol", "requested_effort": "medium",
                            "permissions_digest": "a" * 64, "cache_condition": "fresh"}
        with mock.patch.object(study, "resolve_commit", return_value="a" * 40), \
             mock.patch.object(study, "_rule_entries", side_effect=lambda commit, locale="zh-CN": (
                 "7.16.2" if commit else "7.17.2",
                 {"skills/frontend-engineering/SKILL.md": b"baseline" if commit else b"candidate"})):
            self.prepared = study.prepare(self.suite, self.output, self.environment, "v7.16.2", legacy)
        self.manifest = study.EVAL.read_json(self.output / "study.json")
        self.cases = {row["id"]: row for row in self.suite["cases"]}
        self.results = self.base / "results"
        self.results.mkdir()
        self.index = {"schema": "routing-study-results/1", "study_digest": self.manifest["record_digest"], "runs": []}

    def put(self, path, value):
        raw = value if isinstance(value, bytes) else value.encode("utf-8")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(raw)
        return study.EVAL.digest(raw)

    def seal_report(self, trial, result, evidence):
        item = result["observations"][0]
        body = ("TASK_ID=" + item["task_id"] + "\nOBSERVED_AT=" + item["observed_at"]
                + "\nACTIVATED_SKILLS=" + (",".join(item["activated"]) or "NONE")
                + "\nTRIAL_ID=" + trial["trial_id"] + "\nINPUT_SHA256=" + trial["input_sha256"] + "\n")
        if "phases" in item:
            body += "PHASE_OBSERVATIONS=" + json.dumps(item["phases"]) + "\n"
        item["report_sha256"] = self.put(evidence / "report.txt", body)

    def make_run(self, trial):
        case = self.cases[trial["case_id"]]
        relative = "runs/" + trial["trial_id"]
        directory = self.results / relative
        evidence = directory / "evidence"
        host = {"codex_version": "fixture-version", "plugin_id": "codex-cross-project-engineering-assistant",
                "plugin_version": self.manifest["rules"][trial["variant"]]["plugin_version"],
                "installed": True, "enabled": True, "platform": self.environment["platform"],
                "observed_at": "2026-10-16T00:00:00+08:00", "evidence_level": "host_final_report",
                "evidence_method": "synthetic-contract-fixture-only", "readback_file": "host.txt"}
        body = ("CODEX_VERSION=" + host["codex_version"] + "\nPLUGIN_ID=" + host["plugin_id"]
                + "\nPLUGIN_VERSION=" + host["plugin_version"] + "\nINSTALLED=true\nENABLED=true"
                + "\nRULE_DIGEST=" + self.manifest["rules"][trial["variant"]]["rule_digest"]
                + "\nENVIRONMENT_DIGEST=" + study.EVAL.digest(study.EVAL.canonical(self.environment)) + "\n")
        host["readback_sha256"] = self.put(evidence / "host.txt", body)
        observation = {"id": case["id"], "activated": list(case["required"]),
                       "task_id": "fixture-" + trial["trial_id"], "observed_at": host["observed_at"],
                       "evidence_source": "codex_desktop_task", "report_file": "report.txt",
                       "fresh_session": True, "explicit_skill_names_in_prompt": False}
        if case.get("phases"):
            observation["phases"] = [{"id": phase["id"], "activated": list(phase["required"]),
                                      "exception_reason": ""} for phase in case["phases"]]
        result = {"schema_version": 2, "observation_kind": "real_codex_host",
                  "host": host, "observations": [observation]}
        self.seal_report(trial, result, evidence)
        self.put(directory / "result.json", json.dumps(result))
        entry = {"trial_id": trial["trial_id"], "results_file": relative + "/result.json",
                 "evidence_dir": relative + "/evidence"}
        self.index["runs"].append(entry)
        return result, directory, evidence

    def fill(self, split):
        for trial in self.manifest["trials"]:
            if trial["split"] == split:
                self.make_run(trial)

    def evaluate(self, split="development"):
        path = self.results / "index.json"
        self.put(path, json.dumps(self.index))
        return study.evaluate(self.output / "study.json", path, split, legacy)

    def test_balanced_split_blind_requests_and_legacy_52_unchanged(self):
        self.assertEqual(self.prepared["cases"], 24)
        self.assertEqual(self.prepared["trials"], 80)
        self.assertEqual(len(legacy.validate_cases(legacy.load_json(legacy.DEFAULT_CASES))), 52)
        for path in (self.output / "prompts").glob("*.json"):
            self.assertEqual(set(study.EVAL.read_json(path)), {"schema", "trial_id", "prompt"})
        changed = deepcopy(self.suite)
        changed["cases"][2]["intent_family"] = changed["cases"][0]["intent_family"]
        with self.assertRaisesRegex(ValueError, "STUDY_FAMILY_LEAK"):
            study.validate_suite(changed, legacy)

    def test_rule_mutation_and_output_reuse_are_rejected(self):
        file = next((self.output / "rules").rglob("SKILL.md"))
        file.write_bytes(b"changed")
        with self.assertRaisesRegex(ValueError, "STUDY_INPUT_CHANGED"):
            study.verify(self.output / "study.json", legacy)
        with self.assertRaisesRegex(ValueError, "STUDY_OUTPUT_EXISTS"):
            study.prepare(self.suite, self.output, self.environment, "v7.16.2", legacy)

    def test_english_fixture_has_same_intent_split_and_uses_english_rule_entries(self):
        english = study.EVAL.read_json(ROOT / "locales/en/tests/skill-routing-study-cases.json")
        study.validate_suite(english, legacy)
        self.assertEqual([(r["id"], r["split"], r["intent_family"]) for r in english["cases"]],
                         [(r["id"], r["split"], r["intent_family"]) for r in self.suite["cases"]])
        version, entries = study._rule_entries(None, "en")
        self.assertEqual(set(entries), set(study._rule_entries(None)[1]))
        self.assertEqual(entries["skills/frontend-engineering/SKILL.md"],
                         (ROOT / "locales/en/skills/frontend-engineering/SKILL.md").read_bytes())

    def test_complete_synthetic_development_score_preserves_unknown_benefit(self):
        self.fill("development")
        report = self.evaluate()
        self.assertEqual(report["status"], "PASS")
        self.assertEqual(len(report["trials"]), 48)
        self.assertEqual(report["benefit"], "UNKNOWN")
        self.assertFalse(report["router_trace_observed"])
        self.assertFalse(report["description_changes"])

    def test_missing_observations_are_partial_not_pass(self):
        report = self.evaluate()
        self.assertEqual(report["status"], "PARTIAL")
        self.assertEqual(len(report["missing_trials"]), 48)

    def test_frozen_rule_plan_keeps_actual_install_version_and_legacy_contract(self):
        trial = next(row for row in self.manifest["trials"] if row["variant"] == "baseline")
        result, directory, evidence = self.make_run(trial)
        result["host"]["plugin_version"] = "7.17.2"
        body = (evidence / "host.txt").read_text().replace("PLUGIN_VERSION=7.16.2", "PLUGIN_VERSION=7.17.2")
        result["host"]["readback_sha256"] = self.put(evidence / "host.txt", body)
        self.put(directory / "result.json", json.dumps(result))
        with self.assertRaisesRegex(ValueError, "STUDY_HOST_VERSION"):
            self.evaluate()
        rule = self.manifest["rules"]["baseline"]
        result["rule_context"] = {"kind": "frozen_snapshot_plan", "plugin_version": rule["plugin_version"],
                                  "rule_digest": rule["rule_digest"]}
        self.put(directory / "result.json", json.dumps(result))
        with self.assertRaises(ValueError):
            self.evaluate()
        body += "RULE_CONTEXT=frozen_snapshot_plan\nRULE_PLUGIN_VERSION=7.16.2\n"
        result["host"]["readback_sha256"] = self.put(evidence / "host.txt", body)
        self.put(directory / "result.json", json.dumps(result))
        evaluated = self.evaluate()
        row = evaluated["trials"][0]
        self.assertEqual((row["status"], row["evidence_mode"], row["rule_plugin_version"], row["installed_plugin_version"]),
                         ("PASS", "frozen_snapshot_plan", "7.16.2", "7.17.2"))
        self.assertEqual(evaluated["status"], "PARTIAL")
        self.assertFalse(evaluated["router_trace_observed"])
        changed = deepcopy(result)
        changed["rule_context"]["rule_digest"] = "0" * 64
        self.put(directory / "result.json", json.dumps(changed))
        with self.assertRaisesRegex(ValueError, "STUDY_RULE_CONTEXT"):
            self.evaluate()
        changed = deepcopy(result)
        changed["host"]["installed"] = False
        self.put(directory / "result.json", json.dumps(changed))
        with self.assertRaises(ValueError):
            self.evaluate()

    def test_miss_false_activation_overload_and_phase_errors_are_separate(self):
        self.fill("development")
        for name, active in (("document-handover", []), ("document-changelog-word", ["technical-document-writing"])):
            trial = next(row for row in self.manifest["trials"] if row["case_id"] == name
                         and row["variant"] == "baseline" and row["repeat"] == 1)
            directory = self.results / "runs" / trial["trial_id"]
            result = study.EVAL.read_json(directory / "result.json")
            result["observations"][0]["activated"] = active
            self.seal_report(trial, result, directory / "evidence")
            self.put(directory / "result.json", json.dumps(result))
        report = self.evaluate()
        self.assertEqual(report["status"], "FAILED")
        row = report["groups"]["baseline"]["documents"]
        self.assertEqual((row["missed_trigger"], row["false_activation"], row["overload"]), (1, 1, 1))
        self.index["runs"] = []
        self.fill("final")
        trial = next(row for row in self.manifest["trials"] if row["case_id"] == "design-phased-player"
                     and row["variant"] == "baseline" and row["repeat"] == 1)
        directory = self.results / "runs" / trial["trial_id"]
        result = study.EVAL.read_json(directory / "result.json")
        result["observations"][0]["phases"][1]["activated"] = ["frontend-engineering"]
        self.seal_report(trial, result, directory / "evidence")
        self.put(directory / "result.json", json.dumps(result))
        self.assertEqual(self.evaluate("final")["groups"]["baseline"]["design"]["phase_errors"], 1)

    def test_duplicate_native_task_and_cross_split_results_are_rejected(self):
        trial = next(row for row in self.manifest["trials"] if row["split"] == "development")
        first, _, _ = self.make_run(trial)
        other = next(row for row in self.manifest["trials"] if row["split"] == "development"
                     and row["trial_id"] != trial["trial_id"])
        result, directory, evidence = self.make_run(other)
        result["observations"][0]["task_id"] = first["observations"][0]["task_id"]
        self.seal_report(other, result, evidence)
        self.put(directory / "result.json", json.dumps(result))
        with self.assertRaisesRegex(ValueError, "STUDY_TASK_REUSE"):
            self.evaluate()
        with self.assertRaisesRegex(ValueError, "STUDY_RUN_ID"):
            self.evaluate("final")

    def test_new_study_rejects_cli_evidence_and_escape_paths(self):
        trial = next(row for row in self.manifest["trials"] if row["split"] == "development")
        result, directory, _ = self.make_run(trial)
        result["observations"][0]["evidence_source"] = "codex_cli_jsonl"
        self.put(directory / "result.json", json.dumps(result))
        with self.assertRaisesRegex(ValueError, "STUDY_DESKTOP_ONLY"):
            self.evaluate()
        self.index["runs"][0]["results_file"] = "../escape.json"
        with self.assertRaisesRegex(ValueError, "PATH_ESCAPE"):
            self.evaluate()

    def test_report_must_bind_frozen_input_rules_and_environment(self):
        trial = next(row for row in self.manifest["trials"] if row["split"] == "development")
        result, directory, evidence = self.make_run(trial)
        body = (evidence / "report.txt").read_text().replace(trial["input_sha256"], "0" * 64)
        result["observations"][0]["report_sha256"] = self.put(evidence / "report.txt", body)
        self.put(directory / "result.json", json.dumps(result))
        with self.assertRaisesRegex(ValueError, "STUDY_REPORT_INPUT"):
            self.evaluate()
        self.seal_report(trial, result, evidence)
        body = (evidence / "host.txt").read_text().replace(
            study.EVAL.digest(study.EVAL.canonical(self.environment)), "0" * 64)
        result["host"]["readback_sha256"] = self.put(evidence / "host.txt", body)
        self.put(directory / "result.json", json.dumps(result))
        with self.assertRaisesRegex(ValueError, "STUDY_HOST_ENVIRONMENT"):
            self.evaluate()


if __name__ == "__main__":
    unittest.main()
