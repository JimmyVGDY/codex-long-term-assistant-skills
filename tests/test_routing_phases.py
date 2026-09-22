from __future__ import annotations

import importlib.util
import json
import unittest
from copy import deepcopy
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("routing_phases", ROOT / "scripts" / "routing-eval.py")
assert spec and spec.loader
routing = importlib.util.module_from_spec(spec)
spec.loader.exec_module(routing)


class RoutingPhaseTests(unittest.TestCase):
    def setUp(self):
        self.cases = routing.validate_cases(json.loads((ROOT / "tests" / "skill-routing-cases.json").read_text(encoding="utf-8")))
        self.case = deepcopy(next(case for case in self.cases if case["id"] == "phased-long-task-review"))
        self.observation = {
            "activated": list(self.case["required"]),
            "phases": [{"id": phase["id"], "activated": list(phase["required"]), "exception_reason": ""}
                       for phase in self.case["phases"]],
        }

    def test_stage_union_can_exceed_current_stage_limit(self):
        self.assertEqual(4, len(self.observation["activated"]))
        self.assertTrue(all(len(phase["activated"]) == 3 for phase in self.observation["phases"]))
        self.assertEqual([], routing.phase_findings(self.case, self.observation))

    def test_four_current_skills_require_reason_not_silent_limit_increase(self):
        phase = self.observation["phases"][1]
        phase["activated"].append("long-running-task-memory")
        self.assertIn("PHASE_EXCEPTION_REQUIRED:review", routing.phase_findings(self.case, self.observation))
        phase["exception_reason"] = "The independent review spans sessions and must retain the current evidence handoff."
        self.assertEqual([], routing.phase_findings(self.case, self.observation))

    def test_reason_cannot_override_forbidden_or_maximum(self):
        phase = self.observation["phases"][1]
        phase["activated"].extend(["long-running-task-memory", "controlled-evolution-governance"])
        phase["exception_reason"] = "not a waiver"
        findings = routing.phase_findings(self.case, self.observation)
        self.assertIn("PHASE_SKILL_MISMATCH:review", findings)
        self.assertIn("PHASE_ACTIVE_LIMIT:review", findings)

    def test_missing_duplicate_and_unknown_stages_are_not_passes(self):
        self.assertEqual(["PHASE_EVIDENCE_MISSING"], routing.phase_findings(self.case, {"activated": []}))
        for replacement in ([], [self.observation["phases"][0]],
                            [self.observation["phases"][0]] * 2,
                            [{"id": "invented", "activated": []}]):
            with self.subTest(replacement=replacement):
                changed = {**self.observation, "phases": replacement}
                self.assertTrue(routing.phase_findings(self.case, changed))

    def test_aggregate_must_match_reported_phase_union(self):
        self.observation["activated"].pop()
        self.assertIn("PHASE_UNION_MISMATCH", routing.phase_findings(self.case, self.observation))

    def test_legacy_cases_do_not_require_phase_evidence(self):
        legacy = next(case for case in self.cases if case["id"] == "java-concept-readonly")
        self.assertEqual([], routing.phase_findings(legacy, {"activated": ["backend-engineering"]}))

    def test_unphased_four_skill_case_still_requires_justification(self):
        legacy = next(case for case in self.cases if case["id"] == "architecture-document")
        observation = {"activated": legacy["required"] + legacy["optional"]}
        self.assertEqual(["ACTIVATION_EXCEPTION_REQUIRED"], routing.phase_findings(legacy, observation))
        observation["exception_reason"] = "This design simultaneously compares backend, model semantics and storage boundaries."
        self.assertEqual([], routing.phase_findings(legacy, observation))

    def test_schema_rejects_invalid_phase_contracts(self):
        for kind in ("duplicate", "outside", "boolean-limit", "exception-limit"):
            case = deepcopy(self.case)
            if kind == "duplicate":
                case["phases"].append(deepcopy(case["phases"][0]))
            elif kind == "outside":
                case["phases"][0]["required"].append("invented-skill")
            elif kind == "boolean-limit":
                case["phases"][0]["max_active"] = True
            else:
                case["phases"][0]["exception_above"] = 4
            with self.subTest(kind=kind), self.assertRaises(SystemExit):
                routing.validate_cases({"schema_version": 1, "cases": [case]})

    def test_governance_has_positive_and_negative_regressions(self):
        by_id = {case["id"]: case for case in self.cases}
        for identifier in ("cross-task-review-value", "reviewer-cost-calibration", "optimization-proposal-lifecycle"):
            self.assertIn("controlled-evolution-governance", by_id[identifier]["required"])
        for identifier in ("single-python-fix-not-evolution", "ordinary-review-not-evolution", "ordinary-long-task-not-evolution"):
            self.assertIn("controlled-evolution-governance", by_id[identifier]["forbidden"])


if __name__ == "__main__":
    unittest.main()
