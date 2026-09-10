from __future__ import annotations

import ast
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "runtime"))
from cp_runtime.capability_registry import load_registry, select_capability

CONTRACT_PATH = ROOT / "config" / "r3-acceptance-v1.json"


def contract():
    return json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))


def discovered_test_names():
    names = set()
    roots = (ROOT / "tests", ROOT / "runtime" / "tests", ROOT / "skills" / "multi-agent-independent-review" / "tests")
    for base in roots:
        for path in base.rglob("test_*.py"):
            tree = ast.parse(path.read_text(encoding="utf-8"))
            names.update(node.name for node in ast.walk(tree)
                         if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name.startswith("test_"))
    return names


class R3AcceptanceMatrixTests(unittest.TestCase):
    def test_matrix_has_exact_u_ux_m_t_ids(self):
        groups = contract()["groups"]
        self.assertEqual(["U%02d" % number for number in range(2, 14)], [item["id"] for item in groups["U"]])
        self.assertEqual(["UX%02d" % number for number in range(1, 41)], [item["id"] for item in groups["UX"]])
        self.assertEqual(["M%02d" % number for number in range(1, 13)], [item["id"] for item in groups["M"]])
        self.assertEqual(["T%02d" % number for number in range(25, 29)], [item["id"] for item in groups["T"]])

    def test_every_contract_has_positive_negative_fallback_implementation_and_real_test(self):
        names = discovered_test_names()
        for group in contract()["groups"].values():
            for item in group:
                with self.subTest(case=item["id"]):
                    for key in ("positive", "negative", "fallback"):
                        self.assertIsInstance(item[key], str)
                        self.assertTrue(item[key])
                    self.assertTrue(item["implementation"])
                    for relative in item["implementation"]:
                        self.assertTrue((ROOT / relative).exists(), "%s: %s" % (item["id"], relative))
                    self.assertTrue(item["evidence_tests"])
                    self.assertTrue(all(name in names for name in item["evidence_tests"]), item)

    def test_reviewer_defaults_single_authority(self):
        authority = (ROOT / "skills" / "multi-agent-independent-review" / "SKILL.md").read_text(encoding="utf-8")
        consumer = (ROOT / "skills" / "engineering-quality-delivery" / "references" /
                    "quality-review-completion.md").read_text(encoding="utf-8")
        self.assertIn("默认并行不超过 3、累计不超过 6", authority)
        self.assertIn("默认值只以 `$multi-agent-independent-review` 为权威", consumer)
        self.assertIn("兼容硬上限", consumer)

    def test_authorization_and_evidence_terms_remain_distinct(self):
        rules = (ROOT / "global" / "AGENTS.md").read_text(encoding="utf-8")
        self.assertIn("Evidence 证明", rules)
        self.assertIn("不能授予提交、推送、部署、重启、生产写入或数据修改权限", rules)

    def test_quick_start_mentions_direct_use_and_skip(self):
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        guide = (ROOT / "docs" / "INSTALLATION_RECOVERY.md").read_text(encoding="utf-8")
        for phrase in ("安装后可直接使用", "首次全扫可以跳过", "inventory"):
            self.assertIn(phrase, readme + guide)

    def test_selector_reports_incomplete_review_without_authorization(self):
        registry = load_registry(ROOT / "config" / "capability-registry-v1.json")
        result = select_capability(registry, "C07", {}, statuses={"review_status": "INCOMPLETE"})
        self.assertEqual(("BASIC", "INCOMPLETE", False),
                         (result["effective_level"], result["review_status"], result["authorization"]))

    def test_decline_keeps_registry_basic_available(self):
        registry = load_registry(ROOT / "config" / "capability-registry-v1.json")
        result = select_capability(registry, "C12", {}, statuses={"persistence_status": "DECLINED"})
        self.assertEqual(("BASIC", "DECLINED", False),
                         (result["effective_level"], result["persistence_status"], result["authorization"]))

    def test_release_and_incident_status_are_separate(self):
        report = (ROOT / "docs" / "releases" / "v7.8.0" / "VALIDATION_REPORT.md").read_text(encoding="utf-8")
        self.assertIn("RELEASE_COMPLETE", report)
        self.assertIn("INCIDENT_EFFECTIVE", report)
        self.assertIn("分别", report)


def _contract_test(case):
    def run(self):
        self.assertRegex(case["id"], r"^(U|UX|M|T)[0-9]{2}$")
        self.assertTrue(case["positive"] and case["negative"] and case["fallback"])
        self.assertTrue(case["implementation"] and case["evidence_tests"])
    return run


for _group in contract()["groups"].values():
    for _case in _group:
        setattr(R3AcceptanceMatrixTests, "test_%s_contract" % _case["id"].lower(), _contract_test(_case))


if __name__ == "__main__":
    unittest.main()
