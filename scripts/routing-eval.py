#!/usr/bin/env python3
"""Validate and score manual Codex Skill-routing observations."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Dict, List, Set

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_CASES = ROOT / "tests" / "skill-routing-cases.json"


def die(message: str) -> None:
    print("[FAIL] " + message, file=sys.stderr)
    raise SystemExit(1)


def load_json(path: Path) -> Dict[str, object]:
    try:
        value = json.loads(path.read_text(encoding="utf-8-sig"))
    except FileNotFoundError:
        die("文件不存在: " + str(path))
    except json.JSONDecodeError as exc:
        die("JSON 解析失败 {}: {}".format(path, exc))
    if not isinstance(value, dict):
        die("JSON 根节点必须是对象")
    return value


def validate_cases(data: Dict[str, object]) -> List[Dict[str, object]]:
    if data.get("schema_version") != 1:
        die("不支持的路由用例 schema_version")
    cases = data.get("cases")
    if not isinstance(cases, list) or not cases:
        die("cases 必须是非空数组")
    ids: Set[str] = set()
    for item in cases:
        if not isinstance(item, dict):
            die("每个 case 必须是对象")
        case_id = item.get("id")
        prompt = item.get("prompt")
        if not isinstance(case_id, str) or not case_id:
            die("case.id 不能为空")
        if case_id in ids:
            die("case.id 重复: " + case_id)
        ids.add(case_id)
        if not isinstance(prompt, str) or not prompt.strip():
            die("case.prompt 不能为空: " + case_id)
        sets = {}
        for field in ("required", "optional", "forbidden"):
            value = item.get(field)
            if not isinstance(value, list) or any(not isinstance(one, str) for one in value):
                die("{}.{} 必须是字符串数组".format(case_id, field))
            if len(value) != len(set(value)):
                die("{}.{} 存在重复".format(case_id, field))
            sets[field] = set(value)
        if sets["required"] & sets["forbidden"]:
            die("{} 的 required 与 forbidden 冲突".format(case_id))
        max_active = item.get("max_active")
        if not isinstance(max_active, int) or max_active < 0 or max_active > 4:
            die("{}.max_active 必须在 0～4".format(case_id))
    return cases  # type: ignore[return-value]


def command_validate(args: argparse.Namespace) -> None:
    cases = validate_cases(load_json(Path(args.cases)))
    print("[OK] 路由用例有效: {} 条".format(len(cases)))


def command_list(args: argparse.Namespace) -> None:
    cases = validate_cases(load_json(Path(args.cases)))
    for item in cases:
        print("{}\t{}".format(item["id"], item["prompt"]))


def command_template(args: argparse.Namespace) -> None:
    cases = validate_cases(load_json(Path(args.cases)))
    output = {
        "schema_version": 1,
        "instructions": "在 Codex 中逐条发送 prompt，记录实际激活的 Skill 名称。不要根据 expected 手工补齐。",
        "observations": [
            {"id": item["id"], "activated": [], "notes": ""} for item in cases
        ],
    }
    path = Path(args.output)
    path.write_text(json.dumps(output, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("[OK] 已生成观察模板: " + str(path))


def command_evaluate(args: argparse.Namespace) -> None:
    cases = validate_cases(load_json(Path(args.cases)))
    case_map = {str(item["id"]): item for item in cases}
    result = load_json(Path(args.results))
    observations = result.get("observations")
    if not isinstance(observations, list):
        die("results.observations 必须是数组")
    observed_map = {}
    for item in observations:
        if not isinstance(item, dict) or not isinstance(item.get("id"), str):
            die("observation 格式错误")
        activated = item.get("activated")
        if not isinstance(activated, list) or any(not isinstance(one, str) for one in activated):
            die("observation.activated 必须是字符串数组")
        observed_map[item["id"]] = set(activated)

    failed = 0
    for case_id, case in case_map.items():
        activated = observed_map.get(case_id)
        if activated is None:
            print("[MISS] {} 未记录".format(case_id))
            failed += 1
            continue
        required = set(case["required"])
        forbidden = set(case["forbidden"])
        missing = sorted(required - activated)
        unexpected = sorted(forbidden & activated)
        too_many = len(activated) > int(case["max_active"])
        if missing or unexpected or too_many:
            failed += 1
            print(
                "[FAIL] {} missing={} forbidden={} active={}/{}".format(
                    case_id, missing, unexpected, len(activated), case["max_active"]
                )
            )
        else:
            print("[OK] {} activated={}".format(case_id, sorted(activated)))
    if failed:
        die("路由回归失败或缺失: {} 条".format(failed))
    print("[OK] 路由回归全部通过: {} 条".format(len(case_map)))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Codex Skill 路由回归辅助工具")
    sub = parser.add_subparsers(dest="command", required=True)
    for name, func in (("validate", command_validate), ("list", command_list)):
        one = sub.add_parser(name)
        one.add_argument("--cases", default=str(DEFAULT_CASES))
        one.set_defaults(func=func)
    template = sub.add_parser("make-template")
    template.add_argument("--cases", default=str(DEFAULT_CASES))
    template.add_argument("--output", required=True)
    template.set_defaults(func=command_template)
    evaluate = sub.add_parser("evaluate")
    evaluate.add_argument("--cases", default=str(DEFAULT_CASES))
    evaluate.add_argument("--results", required=True)
    evaluate.set_defaults(func=command_evaluate)
    return parser


def main() -> None:
    args = build_parser().parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
