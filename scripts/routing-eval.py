#!/usr/bin/env python3
"""中文：验证并评分人工记录的 Codex Skill 路由观察。

English: Validate and score manually recorded Codex Skill-routing observations.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Mapping, Set

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_CASES = ROOT / "tests" / "skill-routing-cases.json"
DEFAULT_HOST_PROFILE = ROOT / "tests" / "host-routing-acceptance-profile.json"
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_HOST_EVIDENCE_SOURCES = {"codex_cli_jsonl", "codex_desktop_task"}
_MAX_EVIDENCE_BYTES = 1024 * 1024


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


def _require_timezone_timestamp(value: object, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(label + " 必须是非空时间字符串")
    normalized = value.replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError as exc:
        raise ValueError(label + " 不是有效 ISO-8601 时间") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError(label + " 必须包含时区")
    return value


def validate_host_profile(
    data: Mapping[str, object], cases: List[Dict[str, object]]
) -> Dict[str, object]:
    if data.get("schema_version") != 1:
        raise ValueError("不支持的宿主验收 profile schema_version")
    profile_id = data.get("profile_id")
    if not isinstance(profile_id, str) or not profile_id.strip():
        raise ValueError("profile_id 不能为空")
    required_case_ids = data.get("required_case_ids")
    if (
        not isinstance(required_case_ids, list)
        or not required_case_ids
        or any(not isinstance(item, str) or not item for item in required_case_ids)
    ):
        raise ValueError("required_case_ids 必须是非空字符串数组")
    if len(required_case_ids) != len(set(required_case_ids)):
        raise ValueError("required_case_ids 存在重复")
    known_ids = {str(case["id"]) for case in cases}
    unknown = sorted(set(required_case_ids) - known_ids)
    if unknown:
        raise ValueError("宿主验收 profile 引用了未知用例: " + ", ".join(unknown))
    minimum_pass_rate = data.get("minimum_pass_rate")
    if not isinstance(minimum_pass_rate, (int, float)) or isinstance(minimum_pass_rate, bool):
        raise ValueError("minimum_pass_rate 必须是数值")
    if not math.isfinite(float(minimum_pass_rate)):
        raise ValueError("minimum_pass_rate 必须是有限数值")
    if float(minimum_pass_rate) <= 0 or float(minimum_pass_rate) > 1:
        raise ValueError("minimum_pass_rate 必须在 (0, 1] 范围内")
    minimum_independent_tasks = data.get("minimum_independent_tasks")
    if not isinstance(minimum_independent_tasks, int) or isinstance(minimum_independent_tasks, bool):
        raise ValueError("minimum_independent_tasks 必须是整数")
    if minimum_independent_tasks < len(required_case_ids):
        raise ValueError("minimum_independent_tasks 不能少于 required_case_ids 数量")
    if data.get("required_evidence_level") != "host_final_report":
        raise ValueError("当前宿主验收仅接受 host_final_report 证据级别")
    return dict(data)


def _evidence_bytes(root: Path, relative: object, label: str) -> bytes:
    if not isinstance(relative, str) or not relative.strip():
        raise ValueError(label + " 不能为空")
    candidate = Path(relative)
    if candidate.is_absolute() or ".." in candidate.parts:
        raise ValueError(label + " 必须是安全相对路径")
    root = root.resolve()
    resolved = (root / candidate).resolve()
    try:
        resolved.relative_to(root)
    except ValueError as exc:
        raise ValueError(label + " 越出证据目录") from exc
    if not resolved.is_file():
        raise ValueError(label + " 文件不存在")
    payload = resolved.read_bytes()
    if len(payload) > _MAX_EVIDENCE_BYTES:
        raise ValueError(label + " 超过 1 MiB 上限")
    return payload


def _verify_digest(payload: bytes, expected: object, label: str) -> None:
    if not isinstance(expected, str) or not _SHA256_RE.fullmatch(expected):
        raise ValueError(label + " 必须是小写 SHA-256")
    actual = hashlib.sha256(payload).hexdigest()
    if actual != expected:
        raise ValueError(label + " 与证据文件内容不匹配")


def _marker(text: str, name: str, label: str) -> str:
    matches = re.findall(r"^%s=(.*)$" % re.escape(name), text, flags=re.MULTILINE)
    if len(matches) != 1 or not matches[0].strip():
        raise ValueError(label + " 必须包含唯一的 " + name + " 标记")
    return matches[0].strip()


def _verify_host_readback(host: Mapping[str, object], evidence_root: Path) -> None:
    payload = _evidence_bytes(evidence_root, host.get("readback_file"), "host.readback_file")
    _verify_digest(payload, host.get("readback_sha256"), "host.readback_sha256")
    try:
        text = payload.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ValueError("host.readback_file 必须是 UTF-8") from exc
    expected = {
        "CODEX_VERSION": str(host["codex_version"]),
        "PLUGIN_ID": str(host["plugin_id"]),
        "PLUGIN_VERSION": str(host["plugin_version"]),
        "INSTALLED": "true",
        "ENABLED": "true",
    }
    for marker, value in expected.items():
        if _marker(text, marker, "host.readback_file") != value:
            raise ValueError("host.readback_file 的 %s 与声明不一致" % marker)


def _verify_host_report(item: Mapping[str, object], evidence_root: Path) -> tuple[List[str], int]:
    case_id = str(item["id"])
    payload = _evidence_bytes(evidence_root, item.get("report_file"), case_id + ".report_file")
    _verify_digest(payload, item.get("report_sha256"), case_id + ".report_sha256")
    try:
        text = payload.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ValueError(case_id + ".report_file 必须是 UTF-8") from exc
    if _marker(text, "TASK_ID", case_id + ".report_file") != item["task_id"]:
        raise ValueError(case_id + ".report_file 的 TASK_ID 与 observation 不一致")
    if _marker(text, "OBSERVED_AT", case_id + ".report_file") != item["observed_at"]:
        raise ValueError(case_id + ".report_file 的 OBSERVED_AT 与 observation 不一致")
    activated_text = _marker(text, "ACTIVATED_SKILLS", case_id + ".report_file")
    activated = [] if activated_text == "NONE" else activated_text.split(",")
    if any(not re.fullmatch(r"[a-z0-9][a-z0-9-]*", skill) for skill in activated):
        raise ValueError(case_id + ".report_file 的 ACTIVATED_SKILLS 格式无效")
    if len(activated) != len(set(activated)):
        raise ValueError(case_id + ".report_file 的 ACTIVATED_SKILLS 存在重复")
    return activated, len(payload)


def validate_host_results(
    data: Mapping[str, object], profile: Mapping[str, object], evidence_root: Path
) -> Dict[str, Dict[str, object]]:
    if data.get("schema_version") != 2:
        raise ValueError("不支持的宿主观察 schema_version")
    if data.get("observation_kind") != "real_codex_host":
        raise ValueError("observation_kind 必须是 real_codex_host")
    host = data.get("host")
    if not isinstance(host, dict):
        raise ValueError("host 必须是对象")
    for field in ("codex_version", "plugin_id", "plugin_version", "platform", "evidence_method"):
        if not isinstance(host.get(field), str) or not str(host[field]).strip():
            raise ValueError("host.%s 不能为空" % field)
    if host.get("installed") is not True or host.get("enabled") is not True:
        raise ValueError("宿主读回必须明确 installed=true 且 enabled=true")
    _require_timezone_timestamp(host.get("observed_at"), "host.observed_at")
    required_level = profile["required_evidence_level"]
    if host.get("evidence_level") != required_level:
        raise ValueError("host.evidence_level 必须是 %s" % required_level)
    _verify_host_readback(host, evidence_root)

    observations = data.get("observations")
    if not isinstance(observations, list):
        raise ValueError("observations 必须是数组")
    required_ids = set(profile["required_case_ids"])  # type: ignore[arg-type]
    observed: Dict[str, Dict[str, object]] = {}
    task_ids: Set[str] = set()
    report_files: Set[str] = set()
    for item in observations:
        if not isinstance(item, dict):
            raise ValueError("每条宿主 observation 必须是对象")
        case_id = item.get("id")
        if not isinstance(case_id, str) or not case_id:
            raise ValueError("宿主 observation.id 不能为空")
        if case_id not in required_ids:
            raise ValueError("宿主 observation 不属于验收 profile: " + case_id)
        if case_id in observed:
            raise ValueError("宿主 observation.id 重复: " + case_id)
        activated = item.get("activated")
        if not isinstance(activated, list) or any(not isinstance(one, str) or not one for one in activated):
            raise ValueError(case_id + ".activated 必须是字符串数组")
        if len(activated) != len(set(activated)):
            raise ValueError(case_id + ".activated 存在重复")
        task_id = item.get("task_id")
        if not isinstance(task_id, str) or not task_id.strip():
            raise ValueError(case_id + ".task_id 不能为空")
        if task_id in task_ids:
            raise ValueError("真实宿主观察必须使用独立任务，task_id 重复: " + task_id)
        task_ids.add(task_id)
        _require_timezone_timestamp(item.get("observed_at"), case_id + ".observed_at")
        if item.get("evidence_source") not in _HOST_EVIDENCE_SOURCES:
            raise ValueError(case_id + ".evidence_source 不受支持")
        report_sha256 = item.get("report_sha256")
        if not isinstance(report_sha256, str) or not _SHA256_RE.fullmatch(report_sha256):
            raise ValueError(case_id + ".report_sha256 必须是小写 SHA-256")
        report_file = item.get("report_file")
        if not isinstance(report_file, str) or not report_file.strip():
            raise ValueError(case_id + ".report_file 不能为空")
        if report_file in report_files:
            raise ValueError("真实宿主观察必须绑定独立报告文件: " + report_file)
        report_files.add(report_file)
        if item.get("fresh_session") is not True:
            raise ValueError(case_id + " 必须明确 fresh_session=true")
        if item.get("explicit_skill_names_in_prompt") is not False:
            raise ValueError(case_id + " 必须明确 explicit_skill_names_in_prompt=false")
        verified_activated, evidence_byte_count = _verify_host_report(item, evidence_root)
        if activated != verified_activated:
            raise ValueError(case_id + ".activated 与已封存报告不一致")
        verified_item = dict(item)
        verified_item["evidence_byte_count"] = evidence_byte_count
        observed[case_id] = verified_item
    return observed


def evaluate_host_acceptance(
    cases: List[Dict[str, object]],
    profile: Mapping[str, object],
    results: Mapping[str, object],
    evidence_root: Path,
) -> Dict[str, object]:
    observed = validate_host_results(results, profile, evidence_root)
    case_map = {str(item["id"]): item for item in cases}
    known_skills = {
        str(skill)
        for case in cases
        for field in ("required", "optional", "forbidden")
        for skill in case[field]  # type: ignore[union-attr]
    }
    required_ids = list(profile["required_case_ids"])  # type: ignore[arg-type]
    case_results: List[Dict[str, object]] = []
    passed = 0
    failed = 0
    missing = 0
    for case_id in required_ids:
        case = case_map[case_id]
        item = observed.get(case_id)
        if item is None:
            missing += 1
            case_results.append({"id": case_id, "status": "MISSING"})
            continue
        activated = set(item["activated"])  # type: ignore[arg-type]
        absent = sorted(set(case["required"]) - activated)  # type: ignore[arg-type]
        forbidden = sorted(set(case["forbidden"]) & activated)  # type: ignore[arg-type]
        unrecognized = sorted(activated - known_skills)
        too_many = len(activated) > int(case["max_active"])
        status = "PASS" if not absent and not forbidden and not unrecognized and not too_many else "FAILED"
        if status == "PASS":
            passed += 1
        else:
            failed += 1
        case_results.append({
            "id": case_id,
            "status": status,
            "activated": sorted(activated),
            "missing_required": absent,
            "activated_forbidden": forbidden,
            "activated_unrecognized": unrecognized,
            "active_count": len(activated),
            "max_active": int(case["max_active"]),
            "task_id": item["task_id"],
            "observed_at": item["observed_at"],
            "evidence_source": item["evidence_source"],
            "report_file": item["report_file"],
            "report_sha256": item["report_sha256"],
            "evidence_byte_count": item["evidence_byte_count"],
        })

    required_count = len(required_ids)
    pass_rate = passed / required_count
    independent_tasks = len({str(item["task_id"]) for item in observed.values()})
    if failed:
        status = "FAILED"
    elif (
        missing
        or pass_rate < float(profile["minimum_pass_rate"])
        or independent_tasks < int(profile["minimum_independent_tasks"])
    ):
        status = "PARTIAL"
    else:
        status = "PASS"
    host = results["host"]
    assert isinstance(host, dict)
    return {
        "schema_version": 1,
        "status": status,
        "profile_id": profile["profile_id"],
        "evidence_scope": "HOST_FINAL_REPORT",
        "evidence_binding": "SHA256_VERIFIED_BYTES",
        "router_trace_observed": False,
        "host": {
            "codex_version": host["codex_version"],
            "plugin_id": host["plugin_id"],
            "plugin_version": host["plugin_version"],
            "installed": host["installed"],
            "enabled": host["enabled"],
            "observed_at": host["observed_at"],
            "platform": host["platform"],
            "evidence_level": host["evidence_level"],
            "evidence_method": host["evidence_method"],
            "readback_file": host["readback_file"],
            "readback_sha256": host["readback_sha256"],
        },
        "summary": {
            "required": required_count,
            "observed": len(observed),
            "passed": passed,
            "failed": failed,
            "missing": missing,
            "pass_rate": pass_rate,
            "independent_tasks": independent_tasks,
            "minimum_independent_tasks": int(profile["minimum_independent_tasks"]),
        },
        "cases": case_results,
        "limitations": [
            "Skill activation is reported by the host task final output, not an independent router trace.",
            "Evidence bytes are SHA-256-bound but are not cryptographically signed by the Codex host.",
            "The result applies only to the required cases in this acceptance profile.",
        ],
    }


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


def command_host_template(args: argparse.Namespace) -> None:
    cases = validate_cases(load_json(Path(args.cases)))
    try:
        profile = validate_host_profile(load_json(Path(args.profile)), cases)
    except ValueError as exc:
        die(str(exc))
    case_map = {str(item["id"]): item for item in cases}
    output = {
        "schema_version": 2,
        "observation_kind": "real_codex_host",
        "instructions": (
            "在安装并启用目标 Plugin 后，为每条 prompt 启动全新独立任务；prompt 不得显式包含 Skill 名称。"
            "仅记录宿主任务最终报告的激活 Skill，并保存原始报告 SHA-256；不要查看 expected 后人工补齐。"
        ),
        "host": {
            "codex_version": "",
            "plugin_id": "codex-cross-project-engineering-assistant",
            "plugin_version": "",
            "installed": False,
            "enabled": False,
            "observed_at": "",
            "platform": "",
            "evidence_level": profile["required_evidence_level"],
            "evidence_method": "fresh_independent_task_final_output",
            "readback_file": "host-readback.txt",
            "readback_sha256": "",
        },
        "observations": [
            {
                "id": case_id,
                "prompt": case_map[case_id]["prompt"],
                "activated": [],
                "task_id": "",
                "observed_at": "",
                "evidence_source": "codex_cli_jsonl",
                "report_file": case_id + ".txt",
                "report_sha256": "",
                "fresh_session": True,
                "explicit_skill_names_in_prompt": False,
                "notes": "",
            }
            for case_id in profile["required_case_ids"]  # type: ignore[union-attr]
        ],
    }
    path = Path(args.output)
    path.write_text(json.dumps(output, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("[OK] 已生成真实宿主观察模板: " + str(path))


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
        if item["id"] in observed_map:
            die("observation.id 重复: " + item["id"])
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


def command_host_evaluate(args: argparse.Namespace) -> None:
    cases = validate_cases(load_json(Path(args.cases)))
    try:
        profile = validate_host_profile(load_json(Path(args.profile)), cases)
        report = evaluate_host_acceptance(
            cases, profile, load_json(Path(args.results)), Path(args.evidence_dir)
        )
    except ValueError as exc:
        die(str(exc))
    rendered = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        Path(args.output).write_text(rendered, encoding="utf-8")
        print("[OK] 已写入真实宿主验收报告: " + str(args.output))
    else:
        print(rendered, end="")
    if report["status"] != "PASS":
        raise SystemExit(1)


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
    host_template = sub.add_parser("make-host-template")
    host_template.add_argument("--cases", default=str(DEFAULT_CASES))
    host_template.add_argument("--profile", default=str(DEFAULT_HOST_PROFILE))
    host_template.add_argument("--output", required=True)
    host_template.set_defaults(func=command_host_template)
    evaluate = sub.add_parser("evaluate")
    evaluate.add_argument("--cases", default=str(DEFAULT_CASES))
    evaluate.add_argument("--results", required=True)
    evaluate.set_defaults(func=command_evaluate)
    host_evaluate = sub.add_parser("evaluate-host")
    host_evaluate.add_argument("--cases", default=str(DEFAULT_CASES))
    host_evaluate.add_argument("--profile", default=str(DEFAULT_HOST_PROFILE))
    host_evaluate.add_argument("--results", required=True)
    host_evaluate.add_argument("--evidence-dir", required=True)
    host_evaluate.add_argument("--output")
    host_evaluate.set_defaults(func=command_host_evaluate)
    return parser


def main() -> None:
    args = build_parser().parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
