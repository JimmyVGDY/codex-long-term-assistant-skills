"""中文：构造六项优化的公开合成样例；答案仅写入协调者评估输入。
English: Build public six-track fixtures; answer keys remain in coordinator evaluation input.
"""
from __future__ import annotations

import argparse
from pathlib import Path

import skill_eval_fixture as fixture

ROOT = Path(__file__).resolve().parents[1]


def build_suite():
    source = fixture.EVAL.read_json(ROOT / "tests/skill-quality-scenarios.json")
    fixture.EVAL.require(set(source) == {"schema", "cases"} and source["schema"] == "skill-quality-scenarios/1",
                         "QUALITY_SCENARIOS_SCHEMA")
    suite = {"schema": "skill-eval-suite/1", "suite_id": "six-track-quality",
             "data_classification": "public-synthetic", "cases": source["cases"]}
    harness = fixture.bounded_read(ROOT / "tests/fixtures/quality_mcp.py", 32_768).decode("utf-8")
    for case in suite["cases"]:
        if case["id"].startswith("mcp-"):
            case["files"]["fixture_mcp.py"] = harness
        fixture.select_case(suite, case["id"])
    return suite


def main():
    parser = argparse.ArgumentParser(description="Prepare public synthetic quality fixtures without model calls.")
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    target = fixture.EVAL.external(args.output)
    suite = build_suite()
    fixture.EVAL.write_new(target, fixture.EVAL.canonical(suite) + b"\n")
    print(str(target))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
