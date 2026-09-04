#!/usr/bin/env python3
"""中文：持久化并约束多 Agent 复审流程和模型路由策略；不启动 Agent、不修改源码仓库，只写入有界复审账本并执行 Luna Low 到 Terra High 的自动上限。

English: Persist and enforce bounded multi-agent review workflow and model-routing policy. This helper launches no agents, modifies no source repositories, writes only a bounded review ledger, and enforces the Luna Low to Terra High automatic ceiling.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import tempfile
from collections import Counter
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterator, List, Optional, Tuple

_RUNTIME_ROOT = Path(__file__).resolve().parents[3] / "runtime"
if str(_RUNTIME_ROOT) not in sys.path:
    sys.path.insert(0, str(_RUNTIME_ROOT))
from cp_runtime.delegation_budget import read_budget, sha256_ref  # noqa: E402

STATE_FILE = "review-state.json"
CALIBRATION_LEDGER_FILE = "review-results.jsonl"
LOCK_FILE = ".review-controller.lock"
SCHEMA_VERSION = 7

# 中文：默认值以成本为先；可显式提高，但绝不能超过 HARD_LIMITS。
# English: Defaults are cost-conscious; they may be raised explicitly but never beyond HARD_LIMITS.
DEFAULT_LIMITS = {
    "max_agent_depth": 2,
    "max_post_review_rounds": 2,
    "max_preimplementation_rounds": 1,
    "max_preimplementation_reviewers": 2,
    "max_parallel_reviewers": 3,
    "max_total_reviewers": 6,
    "max_repair_rounds": 2,
    "max_terra_high_reviewers": 1,
}

# 中文：向后兼容上限保留 V4.1 紧急容量，同时防止提示词或重复工具调用意外扩大规模。
# English: Backward-compatible ceilings preserve V4.1 emergency capacity while preventing
# English: accidental expansion through prompt wording or repeated tool calls.
HARD_LIMITS = {
    "max_agent_depth": 3,
    "max_post_review_rounds": 3,
    "max_preimplementation_rounds": 1,
    "max_preimplementation_reviewers": 4,
    "max_parallel_reviewers": 6,
    "max_total_reviewers": 12,
    "max_repair_rounds": 3,
    "max_terra_high_reviewers": 2,
}

MODEL_PROFILES: Dict[str, Dict[str, str]] = {
    "luna-low": {},
    "luna-medium": {},
    "terra-medium": {},
    "terra-high": {},
}
MODEL_PROFILE_ORDER = {
    "luna-low": 1,
    "luna-medium": 2,
    "terra-medium": 3,
    "terra-high": 4,
}
MODEL_PROFILE_COST_UNITS = {
    "luna-low": 1.0,
    "luna-medium": 2.0,
    "terra-medium": 4.0,
    "terra-high": 8.0,
}
COST_FORMULA_VERSION = "profile-weight-v1"
DEFAULT_PROFILE_BY_TIER = {
    "economy": "luna-low",
    "balanced": "luna-medium",
    "deep": "terra-medium",
}
VALID_PHASES = {"pre", "post"}
VALID_EFFORT_TIERS = {"economy", "balanced", "deep"}
VALID_RESULT_STATUSES = {"pass", "nonblocking", "blocking", "incomplete"}
VALID_PARENT_SANDBOXES = {"read-only", "workspace-write", "danger-full-access", "unknown"}
VALID_DECLARED_SANDBOXES = {"read-only", "workspace-write", "danger-full-access", "unknown"}
VALID_PROBE_RESULTS = {
    "not-run",
    "sandbox-denied",
    "permission-denied",
    "write-succeeded",
    "invalid",
}
VALID_REVIEW_MODES = {"independent-agent", "self-review", "unknown"}
VALID_ISOLATION_LEVELS = {"system-readonly", "logical-readonly", "self-review", "unknown"}
VALID_ROUTE_DECISIONS = {"INLINE", "DELEGATE"}
VALID_ROUTE_REASONS = {
    "INDEPENDENT_EVIDENCE_GAIN", "SEMANTIC_COMPLEXITY", "EVIDENCE_CONFLICT",
    "SECURITY_OR_CONCURRENCY_RISK", "LOWER_TIER_INCONCLUSIVE", "MISSING_EVIDENCE",
    "INLINE_SUFFICIENT",
}
V4_RESULT_FIELDS = {
    "schema_version", "result_id", "reviewer", "task_id", "review_phase", "review_round",
    "boundary_id", "packet_sha256", "status", "isolation_level", "dispatch_assignment",
    "task_difficulty", "duration_ms", "estimated_cost_units", "cost_formula_version",
    "calibration_finalized", "accepted", "rejected", "duplicate", "repaired",
    "regressions_prevented", "checked_scope", "findings", "unverified_items", "summary",
}
V4_ASSIGNMENT_FIELDS = {
    "approved_profile", "minimum_acceptable_profile", "dispatch_permit_ref",
    "policy_status", "cost_basis_units",
}
V3_FINDING_FIELDS = {
    "id", "dimension", "severity", "evidence_level", "blocking", "summary", "location",
    "root_cause_group", "required_validation", "disposition", "adoption_reason", "repaired",
    "regression_prevented", "regression_evidence",
}
FORBIDDEN_CALIBRATION_KEYS = {
    "prompt", "raw_prompt", "response", "full_response", "diff", "patch",
    "token", "tokens", "input_tokens", "output_tokens", "api_key", "cookie",
    "actual" + "_model", "actual" + "_reasoning_effort",
    "runtime" + "_model", "runtime" + "_reasoning_effort",
    "runtime" + "_model_evidence", "host" + "_runtime_attestation",
    "diagnostic" + "_model_observation",
}
VALID_CONCLUSIONS = {
    "系统隔离复审通过，无阻塞项",
    "系统隔离复审有非阻塞问题",
    "逻辑只读复审完成，无阻塞项",
    "逻辑只读复审完成，有非阻塞问题",
    "系统隔离未验证或失败，仅完成逻辑只读复审",
    "有阻塞问题",
    "达到复审上限，仍有阻塞或未验证项",
    "工具或环境受限，未完成独立复审",
    "不适用",
    # 中文：保留向后兼容值。
    # English: Preserve backward-compatible values.
    "通过，无阻塞项",
    "有非阻塞问题",
    "工具或环境受限，未完成严格独立复审",
}


def die(message: str) -> None:
    print("[FAIL] " + message, file=sys.stderr)
    raise SystemExit(1)


def warn(message: str) -> None:
    print("[WARN] " + message, file=sys.stderr)


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def atomic_write(path: Path, data: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(prefix="." + path.name + ".", dir=str(path.parent))
    temp = Path(temp_name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
            json.dump(data, handle, ensure_ascii=False, indent=2, sort_keys=True)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(str(temp), str(path))
    finally:
        if temp.exists():
            try:
                temp.unlink()
            except OSError:
                pass


def atomic_write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(prefix="." + path.name + ".", dir=str(path.parent))
    temp = Path(temp_name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(str(temp), str(path))
    finally:
        if temp.exists():
            try:
                temp.unlink()
            except OSError:
                pass


def canonical_json(data: Any) -> str:
    return json.dumps(data, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def stable_id(prefix: str, *parts: str) -> str:
    digest = hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()
    return prefix + "_" + digest


def nonnegative_int(value: Any, field: str) -> int:
    if isinstance(value, bool):
        die("{} 必须是非负整数".format(field))
    try:
        converted = int(value)
    except (TypeError, ValueError):
        die("{} 必须是非负整数".format(field))
    if converted < 0 or (isinstance(value, float) and not value.is_integer()):
        die("{} 必须是非负整数".format(field))
    return converted


def reject_forbidden_calibration_fields(value: Any, path: str = "result") -> None:
    if isinstance(value, dict):
        for key, child in value.items():
            if str(key).lower() in FORBIDDEN_CALIBRATION_KEYS:
                die("Reviewer 校准结果包含禁止字段: {}.{}".format(path, key))
            reject_forbidden_calibration_fields(child, path + "." + str(key))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            reject_forbidden_calibration_fields(child, "{}[{}]".format(path, index))


def validate_v4_result_shape(result: Dict[str, Any]) -> None:
    reject_forbidden_calibration_fields(result)
    missing = sorted(V4_RESULT_FIELDS - set(result))
    if missing:
        die("Reviewer result_file 缺少 schema 必需字段: {}".format(",".join(missing)))
    unexpected = sorted(set(result) - V4_RESULT_FIELDS)
    if unexpected:
        die("Reviewer result_file 包含 schema 未允许字段: {}".format(",".join(unexpected)))
    assignment = result.get("dispatch_assignment")
    if not isinstance(assignment, dict):
        die("Reviewer result_file dispatch_assignment 必须是对象")
    missing_assignment = sorted(V4_ASSIGNMENT_FIELDS - set(assignment))
    if missing_assignment:
        die("Reviewer result_file dispatch_assignment 缺少 schema 必需字段: {}".format(",".join(missing_assignment)))
    unexpected_assignment = sorted(set(assignment) - V4_ASSIGNMENT_FIELDS)
    if unexpected_assignment:
        die("Reviewer result_file dispatch_assignment 包含 schema 未允许字段: {}".format(",".join(unexpected_assignment)))
    findings = result.get("findings")
    if not isinstance(findings, list):
        die("Reviewer result_file findings 必须是数组")
    for index, finding in enumerate(findings):
        if not isinstance(finding, dict):
            die("Reviewer result_file finding[{}] 必须是对象".format(index))
        missing_finding = sorted(V3_FINDING_FIELDS - set(finding))
        if missing_finding:
            die("Reviewer result_file finding[{}] 缺少 schema 必需字段: {}".format(
                index, ",".join(missing_finding)
            ))
        unexpected_finding = sorted(set(finding) - V3_FINDING_FIELDS)
        if unexpected_finding:
            die("Reviewer result_file finding[{}] 包含 schema 未允许字段: {}".format(
                index, ",".join(unexpected_finding)
            ))
        evidence = finding.get("regression_evidence")
        if not isinstance(evidence, list) or any(not isinstance(item, str) for item in evidence):
            die("Reviewer result_file finding[{}].regression_evidence 必须是字符串数组".format(index))


@contextmanager
def review_lock(review_dir: Path, force_unlock: bool = False) -> Iterator[None]:
    review_dir.mkdir(parents=True, exist_ok=True)
    lock_path = review_dir / LOCK_FILE
    if force_unlock and lock_path.exists():
        lock_path.unlink()
    try:
        fd = os.open(str(lock_path), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError:
        die("检测到复审台账写入锁；确认是崩溃遗留锁后可使用 --force-unlock")
    try:
        os.write(fd, "pid={}\ntime={}\n".format(os.getpid(), now_iso()).encode("utf-8"))
        os.close(fd)
        yield
    finally:
        try:
            lock_path.unlink()
        except FileNotFoundError:
            pass


def state_path(review_dir: Path) -> Path:
    return review_dir / STATE_FILE


def default_isolation() -> Dict[str, Any]:
    return {
        "review_mode": "unknown",
        "parent_sandbox": "unknown",
        "declared_sandbox": "read-only",
        "probe_result": "not-run",
        "agent_config_confirmed": False,
        "runtime_agent_confirmed": False,
        "isolation_level": "unknown",
        "strict_readonly_eligible": False,
        "evidence": "",
        "verified_at": "",
    }


def default_dispatch_policy() -> Dict[str, Any]:
    return {
        "allowed_profiles": list(MODEL_PROFILES.keys()),
        "automatic_dispatch_ceiling_profile": "terra-high",
        "forbidden_request_classes": ["sol-or-stronger", "xhigh-or-stronger"],
        "upgrade_chain": list(MODEL_PROFILES.keys()),
        "enforcement_scope": "review-controller-dispatch",
    }


def derive_isolation_level(data: Dict[str, Any]) -> Tuple[str, bool]:
    review_mode = str(data.get("review_mode", "unknown"))
    parent_sandbox = str(data.get("parent_sandbox", "unknown"))
    probe_result = str(data.get("probe_result", "not-run"))

    if review_mode == "self-review":
        return "self-review", False
    if probe_result == "write-succeeded":
        return "logical-readonly", False
    if probe_result == "sandbox-denied":
        confirmed = bool(data.get("runtime_agent_confirmed"))
        return ("system-readonly", True) if confirmed else ("unknown", False)
    if parent_sandbox in {"workspace-write", "danger-full-access"}:
        return "logical-readonly", False
    if parent_sandbox == "read-only":
        confirmed = bool(data.get("runtime_agent_confirmed")) and bool(data.get("agent_config_confirmed"))
        return ("system-readonly", True) if confirmed else ("unknown", False)
    return "unknown", False


def normalize_dispatch_record(record: Dict[str, Any], effort_tier: str) -> Dict[str, Any]:
    legacy_profile = record.pop("model_profile", "")
    profile = str(record.get("approved_profile") or legacy_profile or DEFAULT_PROFILE_BY_TIER.get(effort_tier, "luna-medium"))
    if profile not in MODEL_PROFILES:
        profile = "luna-medium"
    record["approved_profile"] = profile
    record.pop("requested_model", None)
    record.pop("requested_reasoning_effort", None)
    record.setdefault("minimum_acceptable_profile", profile)
    record.setdefault("escalation_reason", "")
    record.setdefault("repeat_reason", "")
    record.setdefault("delegation_dispatch_ref", "")
    record.setdefault("budget_accounting_owner", "legacy-review-controller")
    return record


def normalize_state_data(state: Dict[str, Any]) -> Dict[str, Any]:
    version = state.get("schema_version")
    if version not in {1, 2, 3, 4, 5, 6, SCHEMA_VERSION}:
        return state

    if version in {1, 2}:
        state.setdefault("risk_level", "unknown")
        state.setdefault("strict_readonly_required", False)
        state.setdefault("isolation", default_isolation())
        if version == 1:
            state.setdefault("notes", []).append(
                "从 schema v1 升级：原状态没有运行时隔离证据，默认标记为 unknown。"
            )
        else:
            state.setdefault("notes", []).append(
                "从 schema v2 升级：重新按运行时证据优先级计算隔离等级。"
            )
        level, eligible = derive_isolation_level(state["isolation"])
        state["isolation"]["isolation_level"] = level
        state["isolation"]["strict_readonly_eligible"] = eligible

    if version in {1, 2, 3}:
        state.setdefault("notes", []).append(
            "升级到 schema v4：启用 Luna/Terra 模型路由、保守默认预算和重复派发保护。"
        )
    if version in {1, 2, 3, 4}:
        state.setdefault("notes", []).append(
            "升级到 schema v5：启用最低可接受模型档位、校准投影与追加式 INLINE/DELEGATE 决策。"
        )
    if version in {1, 2, 3, 4, 5}:
        state.setdefault("notes", []).append(
            "升级到 schema v6：Reviewer 轮次继续独立管理，总成本由 DelegationBudget V1 统一计费。"
        )
    if version in {1, 2, 3, 4, 5, 6}:
        state.setdefault("notes", []).append(
            "升级到 schema v7：删除运行模型自报和实际模型判断，仅保留批准派发档位与结果归因。"
        )

    migrating = version != SCHEMA_VERSION
    state["schema_version"] = SCHEMA_VERSION
    state.setdefault("risk_level", "unknown")
    state.setdefault("strict_readonly_required", False)
    state.setdefault("isolation", default_isolation())
    state.pop("model_policy", None)
    state.setdefault("dispatch_policy", default_dispatch_policy())
    state.setdefault("task_id", str(state.get("boundary_id", "")))
    state.setdefault("routing_decision_required", False)
    state.setdefault("routing_decisions", {"pre": [], "post": []})
    state.setdefault("delegation_budget", {
        "ledger_path": "", "budget_id": "", "accounting_owner": "delegation-budget-v2",
    })
    if state["delegation_budget"].get("accounting_owner") == "delegation-budget-v1":
        state["delegation_budget"]["accounting_owner"] = "delegation-budget-v1-readonly"
    for phase_name in VALID_PHASES:
        state["routing_decisions"].setdefault(phase_name, [])

    limits = state.setdefault("limits", {})
    for key, value in DEFAULT_LIMITS.items():
        limits.setdefault(key, value)

    counters = state.setdefault("counters", {})
    counters.setdefault("total_reviewers", 0)
    counters.setdefault("repair_rounds", 0)
    counters.setdefault("terra_high_reviewers", 0)
    counters.pop("model_policy_violations", None)
    counters.pop("underpowered_results", None)

    phases = state.setdefault("phases", {})
    for phase_name in VALID_PHASES:
        phase = phases.setdefault(phase_name, {"current_round": 0, "rounds": {}})
        phase.setdefault("current_round", 0)
        phase.setdefault("rounds", {})
        for round_key, round_data in phase["rounds"].items():
            tier = str(round_data.get("effort_tier", "balanced"))
            round_data.setdefault("effort_tier", tier)
            default_profile = round_data.pop("default_model_profile", None) or round_data.get("default_dispatch_profile")
            round_data["default_dispatch_profile"] = default_profile or DEFAULT_PROFILE_BY_TIER.get(tier, "luna-medium")
            dispatch = round_data.setdefault("dispatch", {})
            for record in dispatch.values():
                normalize_dispatch_record(record, tier)
            for reviewer, result in round_data.setdefault("results", {}).items():
                requested = dispatch.get(reviewer, {})
                result.pop("model_assignment", None)
                profile = requested.get("approved_profile", "luna-medium")
                if migrating or "dispatch_assignment" not in result:
                    result["dispatch_assignment"] = {
                        "approved_profile": profile,
                        "minimum_acceptable_profile": requested.get("minimum_acceptable_profile", profile),
                        "dispatch_permit_ref": requested.get("delegation_dispatch_ref", ""),
                        "policy_status": "approved" if requested.get("delegation_dispatch_ref") else "legacy-unbound",
                        "cost_basis_units": MODEL_PROFILE_COST_UNITS[profile],
                    }
                if migrating or "calibration_record" not in result:
                    result.pop("calibration_record", None)
                    result["calibration_record"] = calibration_projection(
                        state, phase_name, int(round_key), reviewer, result, requested
                    )
    return state


def load_state(review_dir: Path) -> Dict[str, Any]:
    path = state_path(review_dir)
    if not path.is_file():
        die("缺少复审状态文件，请先执行 init: " + str(path))
    try:
        data = json.loads(path.read_text(encoding="utf-8-sig"))
    except json.JSONDecodeError as exc:
        die("复审状态文件不是有效 JSON: {}".format(exc))
    if not isinstance(data, dict):
        die("复审状态根节点必须是对象")
    state = normalize_state_data(data)
    binding = state.get("delegation_budget", {})
    ledger_path = str(binding.get("ledger_path") or "").strip()
    if ledger_path:
        budget = read_budget(Path(ledger_path))
        binding["accounting_owner"] = (
            "delegation-budget-v1-readonly" if budget.get("read_only") else "delegation-budget-v2"
        )
    return state


def ensure_state_mutable(state: Dict[str, Any]) -> None:
    if state.get("delegation_budget", {}).get("accounting_owner") == "delegation-budget-v1-readonly":
        die("旧 DelegationBudget V1 绑定的 Reviewer 状态只读；请创建独立 V2 预算和新复审边界")


def save_state(review_dir: Path, state: Dict[str, Any]) -> None:
    state["schema_version"] = SCHEMA_VERSION
    state["updated_at"] = now_iso()
    atomic_write(state_path(review_dir), state)


def parse_reviewers(value: str) -> List[str]:
    reviewers = [item.strip() for item in value.split(",") if item.strip()]
    if not reviewers:
        die("Reviewer 列表不能为空")
    if len(set(reviewers)) != len(reviewers):
        die("Reviewer 列表存在重复名称或重复职责")
    return reviewers


def phase_state(state: Dict[str, Any], phase: str) -> Dict[str, Any]:
    if phase not in VALID_PHASES:
        die("phase 必须是 pre 或 post")
    return state.setdefault("phases", {}).setdefault(
        phase, {"current_round": 0, "rounds": {}}
    )


def active_count(state: Dict[str, Any]) -> int:
    return sum(
        len(round_data.get("active", []))
        for phase in state.get("phases", {}).values()
        for round_data in phase.get("rounds", {}).values()
    )


def iter_rounds(state: Dict[str, Any]) -> Iterator[Tuple[str, str, Dict[str, Any]]]:
    for phase_name, phase in state.get("phases", {}).items():
        for round_key, round_data in phase.get("rounds", {}).items():
            yield phase_name, round_key, round_data


def all_dispatch_records(state: Dict[str, Any]) -> Iterator[Tuple[str, str, str, Dict[str, Any]]]:
    for phase_name, round_key, round_data in iter_rounds(state):
        for reviewer, record in round_data.get("dispatch", {}).items():
            yield phase_name, round_key, reviewer, record


def validate_isolation_data(state: Dict[str, Any]) -> None:
    isolation = state.get("isolation", {})
    if isolation.get("review_mode") not in VALID_REVIEW_MODES:
        die("未知 review_mode")
    if isolation.get("parent_sandbox") not in VALID_PARENT_SANDBOXES:
        die("未知 parent_sandbox")
    if isolation.get("declared_sandbox") not in VALID_DECLARED_SANDBOXES:
        die("未知 declared_sandbox")
    if isolation.get("probe_result") not in VALID_PROBE_RESULTS:
        die("未知 probe_result")
    if isolation.get("isolation_level") not in VALID_ISOLATION_LEVELS:
        die("未知 isolation_level")
    derived_level, derived_eligible = derive_isolation_level(isolation)
    if isolation.get("isolation_level") != derived_level:
        die("isolation_level 与运行时证据不一致")
    if bool(isolation.get("strict_readonly_eligible")) != derived_eligible:
        die("strict_readonly_eligible 与运行时证据不一致")


def validate_dispatch_profile(record: Dict[str, Any]) -> None:
    profile = record.get("approved_profile")
    if profile not in MODEL_PROFILES:
        die("未知 Reviewer approved_profile: {}".format(profile))
    minimum = record.get("minimum_acceptable_profile")
    if minimum not in MODEL_PROFILES:
        die("minimum_acceptable_profile 非法")
    if MODEL_PROFILE_ORDER[str(minimum)] > MODEL_PROFILE_ORDER[str(profile)]:
        die("minimum_acceptable_profile 不得高于请求档位")
    if profile == "terra-high" and not str(record.get("escalation_reason", "")).strip():
        die("terra-high 派发必须记录 escalation_reason")


def validate_state_data(state: Dict[str, Any]) -> None:
    if state.get("schema_version") != SCHEMA_VERSION:
        die("不支持的 review-state schema_version")
    delegation = state.get("delegation_budget")
    if not isinstance(delegation, dict) or set(delegation) != {"ledger_path", "budget_id", "accounting_owner"}:
        die("delegation_budget 绑定字段非法")
    if delegation.get("accounting_owner") not in {"delegation-budget-v2", "delegation-budget-v1-readonly"}:
        die("Reviewer 不得成为总预算计费所有者")
    if not str(state.get("task_id", "")).strip():
        die("task_id 不能为空")
    if not isinstance(state.get("routing_decision_required"), bool):
        die("routing_decision_required 必须是布尔值")
    limits = state.get("limits", {})
    for key, ceiling in HARD_LIMITS.items():
        value = limits.get(key)
        if not isinstance(value, int) or value < 1:
            die("复审限制 {} 必须是正整数".format(key))
        if value > ceiling:
            die("复审限制 {}={} 超过硬上限 {}".format(key, value, ceiling))

    counters = state.get("counters", {})
    if int(counters.get("total_reviewers", 0)) > limits["max_total_reviewers"]:
        die("累计 Reviewer 超过上限")
    if int(counters.get("repair_rounds", 0)) > limits["max_repair_rounds"]:
        die("集中修复轮次超过上限")
    if int(counters.get("terra_high_reviewers", 0)) > limits["max_terra_high_reviewers"]:
        die("Terra High Reviewer 超过上限")
    if active_count(state) > limits["max_parallel_reviewers"]:
        die("活跃 Reviewer 超过并行上限")

    validate_isolation_data(state)

    counted_dispatches = 0
    counted_terra_high = 0
    routing_decisions = state.get("routing_decisions", {})
    if not isinstance(routing_decisions, dict):
        die("routing_decisions 必须是对象")
    for phase_name, phase in state.get("phases", {}).items():
        if phase_name not in VALID_PHASES:
            die("未知复审阶段: " + phase_name)
        decisions = routing_decisions.get(phase_name, [])
        if not isinstance(decisions, list):
            die("{} routing_decisions 必须是数组".format(phase_name))
        previous_decision_id = ""
        for index, decision in enumerate(decisions):
            if not isinstance(decision, dict) or decision.get("decision") not in VALID_ROUTE_DECISIONS:
                die("{} 存在非法路由决策".format(phase_name))
            if not str(decision.get("decision_id", "")).startswith("ROUTE_"):
                die("{} 路由 decision_id 非法".format(phase_name))
            if not str(decision.get("reason_code", "")).strip() or not str(decision.get("reason", "")).strip():
                die("{} 路由决策缺少原因".format(phase_name))
            if index == 0:
                if decision.get("supersedes"):
                    die("首个路由决策不得 supersede")
            else:
                if decision.get("supersedes") != previous_decision_id:
                    die("路由改判必须 supersede 前一条决策")
                if decision.get("decision") == decisions[index - 1].get("decision"):
                    die("路由改判必须改变 INLINE/DELEGATE 结论")
                if not str(decision.get("change_reason", "")).strip() or not decision.get("evidence"):
                    die("路由改判必须记录 change_reason 和新证据")
            previous_decision_id = str(decision.get("decision_id", ""))
        if decisions and decisions[-1].get("decision") == "INLINE" and phase.get("rounds"):
            die("最新路由决策为 INLINE 时不得存在复审轮次")
        max_rounds = (
            limits["max_preimplementation_rounds"]
            if phase_name == "pre"
            else limits["max_post_review_rounds"]
        )
        if int(phase.get("current_round", 0)) > max_rounds:
            die("{} 阶段轮次超过上限".format(phase_name))
        for round_key, round_data in phase.get("rounds", {}).items():
            reviewers = round_data.get("planned_reviewers", [])
            if len(reviewers) != len(set(reviewers)):
                die("{} / {} Reviewer 重复".format(phase_name, round_key))
            if int(round_data.get("depth", 0)) > limits["max_agent_depth"]:
                die("{} / {} 深度超过上限".format(phase_name, round_key))
            if round_data.get("effort_tier") not in VALID_EFFORT_TIERS:
                die("{} / {} effort_tier 非法".format(phase_name, round_key))
            if round_data.get("default_dispatch_profile") not in MODEL_PROFILES:
                die("{} / {} default_dispatch_profile 非法".format(phase_name, round_key))
            if phase_name == "pre" and len(reviewers) > limits["max_preimplementation_reviewers"]:
                die("实施前 Reviewer 超过上限")
            if len(reviewers) > limits["max_parallel_reviewers"]:
                die("单轮计划 Reviewer 超过并行上限")
            active = set(round_data.get("active", []))
            completed = set(round_data.get("results", {}).keys())
            planned = set(reviewers)
            if not active.issubset(planned) or not completed.issubset(planned):
                die("{} / {} 存在未计划 Reviewer".format(phase_name, round_key))
            if active & completed:
                die("Reviewer 不能同时处于 active 和 completed")
            dispatch = round_data.get("dispatch", {})
            if not set(dispatch).issubset(planned):
                die("{} / {} 存在未计划派发".format(phase_name, round_key))
            for reviewer, record in dispatch.items():
                validate_dispatch_profile(record)
                counted_dispatches += 1
                if record.get("approved_profile") == "terra-high":
                    counted_terra_high += 1
                result = round_data.get("results", {}).get(reviewer)
                if result:
                    assignment = result.get("dispatch_assignment", {})
                    if assignment.get("approved_profile") != record.get("approved_profile"):
                        die("Reviewer approved_profile 与派发记录不一致")
                    if assignment.get("minimum_acceptable_profile") != record.get("minimum_acceptable_profile"):
                        die("Reviewer minimum_acceptable_profile 与派发记录不一致")
                    if assignment.get("dispatch_permit_ref") != record.get("delegation_dispatch_ref", ""):
                        die("Reviewer dispatch_permit_ref 与派发记录不一致")
                    if float(assignment.get("cost_basis_units") or 0) != MODEL_PROFILE_COST_UNITS[record["approved_profile"]]:
                        die("Reviewer cost_basis_units 与批准档位不一致")

    if int(counters.get("total_reviewers", 0)) != counted_dispatches:
        die("total_reviewers 与实际派发记录不一致")
    if int(counters.get("terra_high_reviewers", 0)) != counted_terra_high:
        die("terra_high_reviewers 与实际派发记录不一致")


def command_init(args: argparse.Namespace) -> None:
    review_dir = Path(args.review_dir).expanduser().resolve()
    review_dir.mkdir(parents=True, exist_ok=True)
    if state_path(review_dir).exists() and not args.force:
        die("复审状态已存在；如需重建请使用 --force")
    limits = dict(DEFAULT_LIMITS)
    for key, ceiling in HARD_LIMITS.items():
        value = getattr(args, key, None)
        if value is not None:
            if value < 1 or value > ceiling:
                die("{} 必须在 1 到硬上限 {} 之间".format(key, ceiling))
            limits[key] = value
    state = {
        "schema_version": SCHEMA_VERSION,
        "boundary_id": args.boundary_id,
        "task_id": args.task_id or args.boundary_id,
        "title": args.title,
        "risk_level": args.risk_level,
        "strict_readonly_required": bool(args.strict_readonly_required),
        "routing_decision_required": True,
        "status": "open",
        "created_at": now_iso(),
        "updated_at": now_iso(),
        "limits": limits,
        "counters": {
            "total_reviewers": 0,
            "repair_rounds": 0,
            "terra_high_reviewers": 0,
        },
        "dispatch_policy": default_dispatch_policy(),
        "phases": {
            "pre": {"current_round": 0, "rounds": {}},
            "post": {"current_round": 0, "rounds": {}},
        },
        "routing_decisions": {"pre": [], "post": []},
        "delegation_budget": {
            "ledger_path": str(Path(args.delegation_ledger).expanduser().resolve()) if args.delegation_ledger else "",
            "budget_id": args.delegation_budget_id,
            "accounting_owner": "delegation-budget-v2",
        },
        "isolation": default_isolation(),
        "conclusion": "",
        "notes": [],
    }
    if state["delegation_budget"]["ledger_path"]:
        bound_budget = read_budget(Path(state["delegation_budget"]["ledger_path"]))
        if bound_budget.get("read_only"):
            die("新 Reviewer 边界不能绑定只读 DelegationBudget V1；请先创建独立 V2 预算")
    validate_state_data(state)
    with review_lock(review_dir, args.force_unlock):
        save_state(review_dir, state)
    print("[OK] 已初始化复审台账: " + str(state_path(review_dir)))
    print("[OK] 默认预算: parallel={} total={} post_rounds={} terra_high={}".format(
        limits["max_parallel_reviewers"],
        limits["max_total_reviewers"],
        limits["max_post_review_rounds"],
        limits["max_terra_high_reviewers"],
    ))
    print("[WARN] 运行时隔离尚未记录；TOML read-only 声明不能单独证明系统级只读。")


def command_isolation(args: argparse.Namespace) -> None:
    review_dir = Path(args.review_dir).expanduser().resolve()
    with review_lock(review_dir, args.force_unlock):
        state = load_state(review_dir)
        ensure_state_mutable(state)
        isolation = {
            "review_mode": args.review_mode,
            "parent_sandbox": args.parent_sandbox,
            "declared_sandbox": args.declared_sandbox,
            "probe_result": args.probe_result,
            "agent_config_confirmed": bool(args.agent_config_confirmed),
            "runtime_agent_confirmed": bool(args.runtime_agent_confirmed),
            "evidence": args.evidence,
            "verified_at": now_iso(),
        }
        level, eligible = derive_isolation_level(isolation)
        isolation["isolation_level"] = level
        isolation["strict_readonly_eligible"] = eligible
        state["isolation"] = isolation
        validate_state_data(state)
        save_state(review_dir, state)
    print("[OK] 已记录复审隔离: level={} strict={}".format(level, eligible))
    if level == "logical-readonly":
        warn("当前仅为逻辑只读；Reviewer TOML 声明没有形成系统级写入隔离。")
    elif level == "unknown":
        warn("运行时隔离仍未验证；不得声称系统强制只读。")


def ensure_strict_if_required(state: Dict[str, Any]) -> None:
    if state.get("strict_readonly_required") and not state["isolation"].get("strict_readonly_eligible"):
        die("当前功能边界采用严格只读复审，但父会话/运行时隔离未满足；请切换到只读父会话或记录有效 sandbox-denied 证据")


def latest_round_data(state: Dict[str, Any], phase_name: str) -> Optional[Dict[str, Any]]:
    rounds = phase_state(state, phase_name).get("rounds", {})
    if not rounds:
        return None
    key = max(rounds, key=lambda item: int(item))
    return rounds[key]


def latest_route_decision(state: Dict[str, Any], phase_name: str) -> Optional[Dict[str, Any]]:
    decisions = state.get("routing_decisions", {}).get(phase_name, [])
    return decisions[-1] if decisions else None


def ensure_delegation_allowed(state: Dict[str, Any], phase_name: str) -> None:
    latest = latest_route_decision(state, phase_name)
    if latest is None and state.get("routing_decision_required"):
        die("{} 阶段必须先记录 INLINE 或 DELEGATE 路由决策".format(phase_name))
    if latest and latest.get("decision") == "INLINE":
        die("{} 阶段最新决策为 INLINE；必须在首轮计划前显式追加 DELEGATE 改判".format(phase_name))


def command_route(args: argparse.Namespace) -> None:
    review_dir = Path(args.review_dir).expanduser().resolve()
    with review_lock(review_dir, args.force_unlock):
        state = load_state(review_dir)
        ensure_state_mutable(state)
        validate_state_data(state)
        if state.get("status") != "open":
            die("复审台账已关闭")
        if args.reason_code not in VALID_ROUTE_REASONS:
            die("路由原因码不属于 V7.4 受控集合")
        if args.decision == "INLINE" and args.reason_code != "INLINE_SUFFICIENT":
            die("INLINE 必须使用 INLINE_SUFFICIENT")
        if args.decision == "DELEGATE" and args.reason_code == "INLINE_SUFFICIENT":
            die("DELEGATE 不得使用 INLINE_SUFFICIENT")
        phase = phase_state(state, args.phase)
        if phase.get("rounds"):
            die("已创建复审轮次，禁止改写该阶段路由决策")
        decisions = state.setdefault("routing_decisions", {}).setdefault(args.phase, [])
        latest = decisions[-1] if decisions else None
        evidence = [str(item).strip() for item in args.evidence if str(item).strip()]
        if latest is None:
            if args.supersedes or args.change_reason:
                die("首个路由决策不得提供 supersedes/change-reason")
        else:
            if args.supersedes != latest.get("decision_id"):
                die("路由改判必须用 --supersedes 指向最新 decision_id")
            if args.decision == latest.get("decision"):
                die("路由改判必须改变 INLINE/DELEGATE 结论")
            if not args.change_reason.strip() or not evidence:
                die("路由改判必须同时提供 --change-reason 和至少一条 --evidence")
        recorded_at = now_iso()
        decision_id = stable_id(
            "ROUTE", str(state.get("boundary_id", "")), args.phase, recorded_at,
            args.decision, args.reason_code, args.reason, str(args.supersedes or ""),
        )
        decisions.append({
            "decision_id": decision_id,
            "phase": args.phase,
            "decision": args.decision,
            "reason_code": args.reason_code,
            "reason": args.reason,
            "evidence": evidence,
            "supersedes": args.supersedes or "",
            "change_reason": args.change_reason,
            "recorded_at": recorded_at,
        })
        validate_state_data(state)
        save_state(review_dir, state)
    print("[OK] 已追加 {} 路由决策: {} / {}".format(args.phase, args.decision, decision_id))


def command_plan(args: argparse.Namespace) -> None:
    review_dir = Path(args.review_dir).expanduser().resolve()
    reviewers = parse_reviewers(args.reviewers)
    with review_lock(review_dir, args.force_unlock):
        state = load_state(review_dir)
        ensure_state_mutable(state)
        validate_state_data(state)
        if state.get("status") != "open":
            die("复审台账已关闭")
        ensure_strict_if_required(state)
        ensure_delegation_allowed(state, args.phase)
        phase = phase_state(state, args.phase)
        previous = latest_round_data(state, args.phase)
        if previous and not previous.get("merge"):
            die("上一轮尚未归并，不能创建下一轮")
        if previous and args.packet_sha256 and args.packet_sha256 == previous.get("packet_sha256"):
            clean = previous.get("merge", {}).get("blocking_count", 0) == 0 and previous.get("merge", {}).get("nonblocking_count", 0) == 0
            if clean:
                die("上一轮已对相同审查包无问题通过；未发生差异变化时禁止机械追加复审")
            if not args.allow_same_packet or not args.same_packet_reason.strip():
                die("相同审查包追加轮次必须显式 --allow-same-packet 并提供 --same-packet-reason")
        next_round = int(phase.get("current_round", 0)) + 1
        max_rounds = (
            state["limits"]["max_preimplementation_rounds"]
            if args.phase == "pre"
            else state["limits"]["max_post_review_rounds"]
        )
        if next_round > max_rounds:
            die("{} 阶段已达到最大轮次 {}".format(args.phase, max_rounds))
        if args.depth > state["limits"]["max_agent_depth"]:
            die("复审深度超过上限")
        if args.phase == "pre" and len(reviewers) > state["limits"]["max_preimplementation_reviewers"]:
            die("实施前 Reviewer 最多 {} 个".format(state["limits"]["max_preimplementation_reviewers"]))
        if len(reviewers) > state["limits"]["max_parallel_reviewers"]:
            die("计划 Reviewer 超过并行上限")
        if len(reviewers) > 1 and not args.packet_sha256:
            die("多 Reviewer 复审必须提供统一审查包 packet_sha256")
        remaining = state["limits"]["max_total_reviewers"] - state["counters"]["total_reviewers"]
        if len(reviewers) > remaining:
            die("Reviewer 总预算不足；剩余 {}，计划 {}".format(remaining, len(reviewers)))
        phase["current_round"] = next_round
        phase["rounds"][str(next_round)] = {
            "round": next_round,
            "phase": args.phase,
            "depth": args.depth,
            "purpose": args.purpose,
            "effort_tier": args.effort_tier,
            "default_dispatch_profile": DEFAULT_PROFILE_BY_TIER[args.effort_tier],
            "packet_sha256": args.packet_sha256,
            "same_packet_reason": args.same_packet_reason if args.allow_same_packet else "",
            "planned_reviewers": reviewers,
            "active": [],
            "dispatch": {},
            "results": {},
            "merge": None,
            "isolation_snapshot": {
                "isolation_level": state["isolation"]["isolation_level"],
                "strict_readonly_eligible": state["isolation"]["strict_readonly_eligible"],
                "parent_sandbox": state["isolation"]["parent_sandbox"],
            },
            "created_at": now_iso(),
        }
        validate_state_data(state)
        save_state(review_dir, state)
    print("[OK] 已创建 {} 第 {} 轮计划: {}；默认派发档位={}".format(
        args.phase,
        next_round,
        ", ".join(reviewers),
        DEFAULT_PROFILE_BY_TIER[args.effort_tier],
    ))


def get_round(state: Dict[str, Any], phase_name: str, round_number: int) -> Dict[str, Any]:
    data = phase_state(state, phase_name).get("rounds", {}).get(str(round_number))
    if not isinstance(data, dict):
        die("不存在 {} 第 {} 轮计划".format(phase_name, round_number))
    return data


def find_previous_same_dispatch(
    state: Dict[str, Any], reviewer: str, packet_sha256: str, phase: str, round_number: int
) -> Optional[Tuple[str, str, Dict[str, Any]]]:
    if not packet_sha256:
        return None
    for phase_name, round_key, reviewer_name, record in all_dispatch_records(state):
        if phase_name == phase and int(round_key) == round_number:
            continue
        if reviewer_name == reviewer and record.get("packet_sha256") == packet_sha256:
            return phase_name, round_key, record
    return None


def validate_requested_profile(
    state: Dict[str, Any], profile: str, escalation_reason: str
) -> None:
    if profile not in MODEL_PROFILES:
        die("model-profile 必须是 {}".format(", ".join(MODEL_PROFILES)))
    if profile == "terra-high":
        if state.get("risk_level") not in {"high", "critical"}:
            die("Terra High 仅允许 high/critical 风险边界")
        if not escalation_reason.strip():
            die("Terra High 必须提供具体 --escalation-reason")
        if state["counters"]["terra_high_reviewers"] >= state["limits"]["max_terra_high_reviewers"]:
            die("Terra High Reviewer 已达到上限")


def command_dispatch(args: argparse.Namespace) -> None:
    review_dir = Path(args.review_dir).expanduser().resolve()
    with review_lock(review_dir, args.force_unlock):
        state = load_state(review_dir)
        ensure_state_mutable(state)
        validate_state_data(state)
        ensure_strict_if_required(state)
        ensure_delegation_allowed(state, args.phase)
        round_data = get_round(state, args.phase, args.round)
        if args.reviewer not in round_data["planned_reviewers"]:
            die("Reviewer 未包含在当前轮计划中")
        if args.reviewer in round_data["active"] or args.reviewer in round_data["results"]:
            die("Reviewer 已派发或已完成")
        if active_count(state) >= state["limits"]["max_parallel_reviewers"]:
            die("当前并行 Reviewer 已达到上限")
        if state["counters"]["total_reviewers"] >= state["limits"]["max_total_reviewers"]:
            die("累计 Reviewer 已达到上限")

        profile = args.model_profile or round_data.get("default_dispatch_profile") or DEFAULT_PROFILE_BY_TIER[round_data.get("effort_tier", "balanced")]
        validate_requested_profile(state, profile, args.escalation_reason)
        minimum_profile = args.minimum_acceptable_profile or profile
        if minimum_profile not in MODEL_PROFILES:
            die("minimum-acceptable-profile 非法")
        if MODEL_PROFILE_ORDER[minimum_profile] > MODEL_PROFILE_ORDER[profile]:
            die("minimum-acceptable-profile 不得高于请求档位")
        packet_sha256 = round_data.get("packet_sha256", "")
        previous = find_previous_same_dispatch(state, args.reviewer, packet_sha256, args.phase, args.round)
        if previous:
            if not args.allow_repeat or not args.repeat_reason.strip():
                die("相同 Reviewer 已审过相同 packet；如确需第二意见，使用 --allow-repeat 并说明 --repeat-reason")

        delegation_binding = state.get("delegation_budget", {})
        delegation_ref = ""
        if delegation_binding.get("ledger_path"):
            if not args.delegation_dispatch_key:
                die("已绑定统一预算账本，Reviewer 派发必须提供 --delegation-dispatch-key")
            budget = read_budget(Path(delegation_binding["ledger_path"]))
            if delegation_binding.get("budget_id") and budget["identity"]["budget_id"] != delegation_binding["budget_id"]:
                die("Reviewer 绑定的 budget_id 与账本不一致")
            delegation_ref = sha256_ref(args.delegation_dispatch_key)
            permit = budget["decisions"].get(delegation_ref)
            if not permit or permit.get("decision") != "DELEGATE":
                die("统一预算账本缺少匹配的 DELEGATE permit")
            if permit.get("role") != "reviewer" or permit.get("approved_profile") != profile:
                die("Reviewer 派发与统一预算 permit 的角色或批准档位不一致")
        round_data["active"].append(args.reviewer)
        round_data.setdefault("dispatch", {})[args.reviewer] = {
            "scope": args.scope,
            "isolation_level": state["isolation"]["isolation_level"],
            "packet_sha256": packet_sha256,
            "effort_tier": round_data.get("effort_tier", "balanced"),
            "approved_profile": profile,
            "minimum_acceptable_profile": minimum_profile,
            "escalation_reason": args.escalation_reason,
            "repeat_reason": args.repeat_reason if args.allow_repeat else "",
            "dispatched_at": now_iso(),
            "delegation_dispatch_ref": delegation_ref,
            "budget_accounting_owner": "delegation-budget-v2" if delegation_ref else "legacy-review-controller",
        }
        state["counters"]["total_reviewers"] += 1
        if profile == "terra-high":
            state["counters"]["terra_high_reviewers"] += 1
        validate_state_data(state)
        save_state(review_dir, state)
    print("[OK] 已记录派发: {} / {} / round {} / {} / {}".format(
        args.reviewer,
        args.phase,
        args.round,
        state["isolation"]["isolation_level"],
        profile,
    ))
    print("[NEXT] 按 approved-profile={} 启动子 Agent；运行身份不属于 Reviewer 契约。".format(profile))


def calibration_projection(
    state: Dict[str, Any],
    phase_name: str,
    round_number: int,
    reviewer: str,
    result_payload: Dict[str, Any],
    dispatch_record: Dict[str, Any],
) -> Dict[str, Any]:
    result_id = str(result_payload.get("result_id", "")).strip()
    if not result_id:
        result_id = stable_id(
            "RVR", str(state.get("boundary_id", "")), str(state.get("task_id", "")),
            phase_name, str(round_number), reviewer,
            str(dispatch_record.get("packet_sha256", "")),
        )
    task_id = str(result_payload.get("task_id") or state.get("task_id") or state.get("boundary_id", ""))
    approved_profile = str(dispatch_record["approved_profile"])
    calibration_findings: List[Dict[str, Any]] = []
    raw_findings = result_payload.get("findings", [])
    if not isinstance(raw_findings, list):
        die("findings 必须是数组")
    for finding in raw_findings:
        if not isinstance(finding, dict):
            die("finding 必须是对象")
        calibration_findings.append({
            key: finding[key]
            for key in (
                "id", "severity", "root_cause_group", "disposition", "adoption_reason",
                "repaired", "regression_prevented", "regression_evidence",
            )
            if key in finding
        })
    projection = {
        "reviewer": reviewer,
        "result_id": result_id,
        "review_phase": phase_name,
        "review_round": nonnegative_int(result_payload.get("review_round", round_number), "review_round"),
        "packet_sha256": str(result_payload.get("packet_sha256") or dispatch_record.get("packet_sha256", "")),
        "task_difficulty": str(result_payload.get("task_difficulty") or "UNKNOWN").upper(),
        "accepted": nonnegative_int(result_payload.get("accepted", 0), "accepted"),
        "rejected": nonnegative_int(result_payload.get("rejected", 0), "rejected"),
        "duplicate": nonnegative_int(result_payload.get("duplicate", 0), "duplicate"),
        "repaired": nonnegative_int(result_payload.get("repaired", 0), "repaired"),
        "regressions_prevented": nonnegative_int(result_payload.get("regressions_prevented", 0), "regressions_prevented"),
        "duration_ms": nonnegative_int(result_payload.get("duration_ms", 0), "duration_ms"),
        "estimated_cost_units": MODEL_PROFILE_COST_UNITS[approved_profile],
        "cost_formula_version": COST_FORMULA_VERSION,
        "calibration_finalized": False,
        "approved_dispatch_profile": approved_profile,
        "cost_basis_profile": approved_profile,
        "cost_basis_units": MODEL_PROFILE_COST_UNITS[approved_profile],
        "findings": calibration_findings,
    }
    if projection["task_difficulty"] not in {"LOW", "MEDIUM", "HIGH", "CRITICAL", "UNKNOWN"}:
        die("task_difficulty 非法")
    if projection["review_round"] < 1:
        die("review_round 必须是正整数")
    return {
        "record_id": stable_id("RCR", task_id, reviewer, result_id),
        "task_id": task_id,
        "timestamp": now_iso(),
        "reviewer_results": [projection],
    }


def calibration_ledger_content(state: Dict[str, Any]) -> str:
    records: List[Dict[str, Any]] = []
    identities = set()
    for _, _, round_data in iter_rounds(state):
        for result in round_data.get("results", {}).values():
            record = result.get("calibration_record")
            if not isinstance(record, dict):
                continue
            projected = record.get("reviewer_results", [{}])[0]
            identity = (record.get("task_id"), projected.get("reviewer"), projected.get("result_id"))
            if identity in identities:
                die("校准投影身份重复: {}".format(identity))
            identities.add(identity)
            records.append(record)
    records.sort(key=lambda item: str(item.get("record_id", "")))
    return "".join(canonical_json(item) + "\n" for item in records)


def rebuild_calibration_ledger(review_dir: Path, state: Dict[str, Any]) -> None:
    atomic_write_text(review_dir / CALIBRATION_LEDGER_FILE, calibration_ledger_content(state))


def validate_calibration_ledger(review_dir: Path, state: Dict[str, Any]) -> None:
    expected = calibration_ledger_content(state)
    ledger_path = review_dir / CALIBRATION_LEDGER_FILE
    actual = ledger_path.read_text(encoding="utf-8") if ledger_path.is_file() else ""
    if actual != expected:
        die("校准台账与 review-state 不一致；请执行 sync-calibration 恢复")


def command_result(args: argparse.Namespace) -> None:
    review_dir = Path(args.review_dir).expanduser().resolve()
    with review_lock(review_dir, args.force_unlock):
        state = load_state(review_dir)
        ensure_state_mutable(state)
        validate_state_data(state)
        round_data = get_round(state, args.phase, args.round)
        expected_packet = round_data.get("packet_sha256", "")
        dispatch_record = round_data.get("dispatch", {}).get(args.reviewer)
        if not isinstance(dispatch_record, dict):
            die("Reviewer 尚未记录派发")
        binding = state.get("delegation_budget", {})
        if binding.get("ledger_path") and not args.delegation_reservation_id:
            die("已绑定统一预算账本，Reviewer 结果必须提供 --delegation-reservation-id")
        delegation_attribution = "unavailable"
        if args.delegation_reservation_id:
            if not binding.get("ledger_path"):
                die("未绑定统一预算账本，不能归因 reservation")
            budget = read_budget(Path(binding["ledger_path"]))
            reservation = budget["reservations"].get(args.delegation_reservation_id)
            if not reservation or reservation.get("role") != "reviewer":
                die("Reviewer reservation 归因非法")
            if reservation.get("dispatch_ref") != dispatch_record.get("delegation_dispatch_ref"):
                die("Reviewer reservation 与派发 permit 不匹配")
            if reservation.get("state") not in {"STARTED", "COMPLETED"}:
                die("Reviewer reservation 必须已启动或完成，不能使用仅预占或已释放记录")
            delegation_attribution = "parent-verified"

        result_payload: Dict[str, Any] = {}
        if expected_packet and not args.result_file:
            die("当前轮绑定了审查包，必须提供结构化 result_file")
        if args.result_file:
            result_path = Path(args.result_file).expanduser().resolve()
            if not result_path.is_file():
                die("Reviewer result_file 不存在")
            try:
                result_payload = json.loads(result_path.read_text(encoding="utf-8-sig"))
            except json.JSONDecodeError as exc:
                die("Reviewer result_file 不是有效 JSON: {}".format(exc))
            if result_payload.get("schema_version") != 4:
                die("Reviewer result_file schema_version 必须是 4；旧结果仅允许只读审计")
            validate_v4_result_shape(result_payload)
            if result_payload.get("reviewer") != args.reviewer:
                die("Reviewer result_file 身份不匹配")
            if result_payload.get("boundary_id") != state.get("boundary_id"):
                die("Reviewer result_file boundary_id 不匹配")
            if expected_packet and result_payload.get("packet_sha256") != expected_packet:
                die("Reviewer result_file packet_sha256 不匹配")
            result_identity = "{}|{}|{}|{}|{}|{}".format(
                state.get("boundary_id", ""), state.get("task_id", ""), args.phase,
                args.round, args.reviewer, expected_packet,
            )
            expected_result_id = "RVR_" + hashlib.sha256(result_identity.encode("utf-8")).hexdigest()
            if result_payload.get("result_id") != expected_result_id:
                die("Reviewer result_file result_id 与派发身份不匹配")
            if result_payload.get("task_id") and result_payload.get("task_id") != state.get("task_id"):
                die("Reviewer result_file task_id 与复审台账不匹配")
            if result_payload.get("review_phase") is not None and result_payload.get("review_phase") != args.phase:
                die("Reviewer result_file review_phase 与当前阶段不匹配")
            if result_payload.get("review_round") is not None and result_payload.get("review_round") != args.round:
                die("Reviewer result_file review_round 与当前轮次不匹配")
            if result_payload.get("status") != args.status:
                die("Reviewer result_file status 与命令参数不匹配")
            if result_payload.get("calibration_finalized") is True:
                die("Reviewer result_file 不得自行设置 calibration_finalized=true")

        assignment_payload = result_payload.get("dispatch_assignment", {}) if result_payload else {}
        approved_profile = dispatch_record["approved_profile"]
        minimum_profile = dispatch_record["minimum_acceptable_profile"]
        result_approved_profile = assignment_payload.get("approved_profile", approved_profile)
        if result_approved_profile != approved_profile:
            die("Reviewer result_file approved_profile 与派发记录不匹配")
        result_minimum_profile = assignment_payload.get("minimum_acceptable_profile", minimum_profile)
        if result_minimum_profile != minimum_profile:
            die("Reviewer result_file minimum_acceptable_profile 与派发记录不匹配")
        permit_ref = str(dispatch_record.get("delegation_dispatch_ref", ""))
        if assignment_payload.get("dispatch_permit_ref", permit_ref) != permit_ref:
            die("Reviewer result_file dispatch_permit_ref 与派发记录不匹配")
        expected_policy_status = "approved" if permit_ref else "legacy-unbound"
        if assignment_payload.get("policy_status", expected_policy_status) != expected_policy_status:
            die("Reviewer result_file policy_status 与派发记录不匹配")
        if float(assignment_payload.get("cost_basis_units", MODEL_PROFILE_COST_UNITS[approved_profile])) != MODEL_PROFILE_COST_UNITS[approved_profile]:
            die("Reviewer result_file cost_basis_units 与批准档位不匹配")

        if args.reviewer not in round_data["active"]:
            die("Reviewer 当前不处于 active 状态")
        calibration_record = calibration_projection(
            state, args.phase, args.round, args.reviewer, result_payload, dispatch_record
        )
        round_data["active"].remove(args.reviewer)
        round_data["results"][args.reviewer] = {
            "status": args.status,
            "blocking_count": args.blocking_count,
            "nonblocking_count": args.nonblocking_count,
            "summary": args.summary,
            "result_file": args.result_file,
            "isolation_level": state["isolation"]["isolation_level"],
            "dispatch_assignment": {
                "approved_profile": approved_profile,
                "minimum_acceptable_profile": minimum_profile,
                "dispatch_permit_ref": permit_ref,
                "policy_status": expected_policy_status,
                "cost_basis_units": MODEL_PROFILE_COST_UNITS[approved_profile],
            },
            "calibration_record": calibration_record,
            "completed_at": now_iso(),
            "delegation_reservation_id": args.delegation_reservation_id,
            "delegation_attribution": delegation_attribution,
        }
        validate_state_data(state)
        save_state(review_dir, state)
        rebuild_calibration_ledger(review_dir, state)
    print("[OK] 已记录 Reviewer 结果: {} -> {} / approved-profile={}".format(
        args.reviewer, args.status, approved_profile
    ))


def command_merge(args: argparse.Namespace) -> None:
    review_dir = Path(args.review_dir).expanduser().resolve()
    with review_lock(review_dir, args.force_unlock):
        state = load_state(review_dir)
        ensure_state_mutable(state)
        validate_state_data(state)
        round_data = get_round(state, args.phase, args.round)
        if round_data["active"]:
            die("仍有活跃 Reviewer，不能归并")
        missing = set(round_data["planned_reviewers"]) - set(round_data["results"].keys())
        if missing:
            die("尚未收齐 Reviewer 结果: {}".format(", ".join(sorted(missing))))
        computed_blocking = sum(int(item.get("blocking_count", 0)) for item in round_data["results"].values())
        computed_nonblocking = sum(int(item.get("nonblocking_count", 0)) for item in round_data["results"].values())
        if args.blocking_count > computed_blocking or args.nonblocking_count > computed_nonblocking:
            warn("归并计数高于 Reviewer 原始计数；请确认是否包含主协调 Agent 的新增发现")
        round_data["merge"] = {
            "blocking_count": args.blocking_count,
            "nonblocking_count": args.nonblocking_count,
            "root_cause_groups": args.root_cause_groups,
            "summary": args.summary,
            "repair_required": args.repair_required,
            "isolation_level": state["isolation"]["isolation_level"],
            "approved_profile_counts": dict(Counter(
                record.get("approved_profile", "unknown")
                for record in round_data.get("dispatch", {}).values()
            )),
            "merged_at": now_iso(),
        }
        validate_state_data(state)
        save_state(review_dir, state)
    print("[OK] 已归并 {} 第 {} 轮".format(args.phase, args.round))
    if args.blocking_count == 0 and args.nonblocking_count == 0:
        print("[STOP] 当前 packet 已无发现；除非差异变化，不得追加相同审查包轮次。")


def command_finalize_calibration(args: argparse.Namespace) -> None:
    review_dir = Path(args.review_dir).expanduser().resolve()
    with review_lock(review_dir, args.force_unlock):
        state = load_state(review_dir)
        ensure_state_mutable(state)
        validate_state_data(state)
        round_data = get_round(state, args.phase, args.round)
        result = round_data.get("results", {}).get(args.reviewer)
        if not isinstance(result, dict):
            die("Reviewer 结果尚未登记，不能最终化校准归因")
        if result.get("status") == "incomplete":
            die("incomplete 结果不能最终化校准归因")
        record = result.get("calibration_record")
        if not isinstance(record, dict) or not record.get("reviewer_results"):
            die("Reviewer 结果缺少可最终化的校准投影")
        projection = record["reviewer_results"][0]
        if projection.get("calibration_finalized"):
            die("Reviewer 校准归因已经最终化，不能覆盖")
        evidence = [str(item).strip() for item in args.evidence if str(item).strip()]
        if not evidence:
            die("最终化校准归因必须提供至少一条 --evidence")
        for name in ("accepted", "rejected", "duplicate", "repaired", "regressions_prevented"):
            projection[name] = nonnegative_int(getattr(args, name), name)
        projection["calibration_finalized"] = True
        projection["calibration_finalization"] = {
            "finalized_by": args.finalized_by,
            "evidence": evidence,
            "note": args.note,
            "finalized_at": now_iso(),
        }
        result["calibration_finalization"] = dict(projection["calibration_finalization"])
        validate_state_data(state)
        save_state(review_dir, state)
        rebuild_calibration_ledger(review_dir, state)
        validate_calibration_ledger(review_dir, state)
    print("[OK] 已最终化 Reviewer 校准归因: {}".format(args.reviewer))


def command_repair(args: argparse.Namespace) -> None:
    review_dir = Path(args.review_dir).expanduser().resolve()
    with review_lock(review_dir, args.force_unlock):
        state = load_state(review_dir)
        ensure_state_mutable(state)
        validate_state_data(state)
        current = state["counters"]["repair_rounds"] + 1
        if current > state["limits"]["max_repair_rounds"]:
            die("集中修复轮次已达到上限")
        affected = [item.strip() for item in args.affected_dimensions.split(",") if item.strip()]
        if not affected:
            warn("未记录 affected_dimensions；后续定向复核可能被迫扩大范围")
        state["counters"]["repair_rounds"] = current
        state.setdefault("repairs", []).append(
            {
                "round": current,
                "summary": args.summary,
                "affected_dimensions": affected,
                "validation": args.validation,
                "recorded_at": now_iso(),
            }
        )
        validate_state_data(state)
        save_state(review_dir, state)
    print("[OK] 已记录第 {} 轮集中修复".format(current))


def dispatch_profile_counts(state: Dict[str, Any]) -> Dict[str, int]:
    return dict(Counter(record.get("approved_profile", "unknown") for _, _, _, record in all_dispatch_records(state)))


def command_validate(args: argparse.Namespace) -> None:
    review_dir = Path(args.review_dir).expanduser().resolve()
    state = load_state(review_dir)
    validate_state_data(state)
    validate_calibration_ledger(review_dir, state)
    if args.require_strict_readonly:
        ensure_strict_if_required({**state, "strict_readonly_required": True})
    print(
        "[OK] 复审台账有效: boundary={} total={} repairs={} active={} isolation={} strict={} profiles={}".format(
            state.get("boundary_id", ""),
            state["counters"]["total_reviewers"],
            state["counters"]["repair_rounds"],
            active_count(state),
            state["isolation"]["isolation_level"],
            state["isolation"]["strict_readonly_eligible"],
            json.dumps(dispatch_profile_counts(state), ensure_ascii=False, sort_keys=True),
        )
    )


def command_sync_calibration(args: argparse.Namespace) -> None:
    review_dir = Path(args.review_dir).expanduser().resolve()
    with review_lock(review_dir, args.force_unlock):
        state = load_state(review_dir)
        ensure_state_mutable(state)
        validate_state_data(state)
        save_state(review_dir, state)
        rebuild_calibration_ledger(review_dir, state)
        validate_calibration_ledger(review_dir, state)
    print("[OK] 已从 review-state 重建校准台账")


def command_status(args: argparse.Namespace) -> None:
    state = load_state(Path(args.review_dir).expanduser().resolve())
    validate_state_data(state)
    limits = state["limits"]
    isolation = state["isolation"]
    print("# 复审状态")
    print("- 功能边界: " + str(state.get("boundary_id", "")))
    print("- 风险级别: " + str(state.get("risk_level", "")))
    print("- 状态: " + str(state.get("status", "")))
    print("- 严格只读约束: " + ("是" if state.get("strict_readonly_required") else "否"))
    print("- Reviewer 配置声明: " + str(isolation.get("declared_sandbox", "unknown")))
    print("- 父会话运行时沙箱: " + str(isolation.get("parent_sandbox", "unknown")))
    print("- 写入探针: " + str(isolation.get("probe_result", "not-run")))
    print("- 复审隔离等级: " + str(isolation.get("isolation_level", "unknown")))
    print("- 系统级严格只读资格: " + ("是" if isolation.get("strict_readonly_eligible") else "否"))
    print("- 累计 Reviewer: {} / {}".format(state["counters"]["total_reviewers"], limits["max_total_reviewers"]))
    print("- Terra High Reviewer: {} / {}".format(state["counters"]["terra_high_reviewers"], limits["max_terra_high_reviewers"]))
    print("- 批准派发档位分布: " + json.dumps(dispatch_profile_counts(state), ensure_ascii=False, sort_keys=True))
    print("- 集中修复轮次: {} / {}".format(state["counters"]["repair_rounds"], limits["max_repair_rounds"]))
    print("- 当前活跃 Reviewer: {} / {}".format(active_count(state), limits["max_parallel_reviewers"]))
    for phase_name in ("pre", "post"):
        phase = phase_state(state, phase_name)
        latest_route = latest_route_decision(state, phase_name)
        print("- {} 路由决策: {}".format(
            phase_name, latest_route.get("decision") if latest_route else "未记录（兼容旧路径）"
        ))
        print("- {} 当前轮次: {}".format(phase_name, phase.get("current_round", 0)))
        for round_key, round_data in sorted(phase.get("rounds", {}).items(), key=lambda item: int(item[0])):
            profiles = Counter(
                record.get("approved_profile", "unknown")
                for record in round_data.get("dispatch", {}).values()
            )
            print(
                "  - round {}: planned={} active={} completed={} merged={} profiles={}".format(
                    round_key,
                    len(round_data.get("planned_reviewers", [])),
                    len(round_data.get("active", [])),
                    len(round_data.get("results", {})),
                    "是" if round_data.get("merge") else "否",
                    dict(profiles),
                )
            )
    if state.get("conclusion"):
        print("- 最终结论: " + state["conclusion"])


def command_close(args: argparse.Namespace) -> None:
    review_dir = Path(args.review_dir).expanduser().resolve()
    with review_lock(review_dir, args.force_unlock):
        state = load_state(review_dir)
        ensure_state_mutable(state)
        validate_state_data(state)
        validate_calibration_ledger(review_dir, state)
        if active_count(state):
            die("仍有活跃 Reviewer，不能关闭")
        isolation = state["isolation"]
        if args.conclusion.startswith("系统隔离复审") and not isolation.get("strict_readonly_eligible"):
            die("没有系统级只读运行时证据，不能使用系统隔离复审结论")
        if state.get("strict_readonly_required") and not isolation.get("strict_readonly_eligible"):
            allowed = {
                "系统隔离未验证或失败，仅完成逻辑只读复审",
                "有阻塞问题",
                "达到复审上限，仍有阻塞或未验证项",
                "工具或环境受限，未完成独立复审",
                "工具或环境受限，未完成严格独立复审",
            }
            if args.conclusion not in allowed:
                die("当前采用严格只读，但运行时隔离不满足；只能记录未完成、阻塞或逻辑只读降级结论")
        state["status"] = "closed"
        state["conclusion"] = args.conclusion
        if args.note:
            state.setdefault("notes", []).append(args.note)
        save_state(review_dir, state)
    print("[OK] 已关闭复审台账: " + args.conclusion)


def add_common(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--review-dir", required=True)
    parser.add_argument("--force-unlock", action="store_true")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="维护多 Agent 复审预算、批准派发档位与隔离证据")
    sub = parser.add_subparsers(dest="command", required=True)

    init = sub.add_parser("init")
    init.add_argument("--review-dir", required=True)
    init.add_argument("--boundary-id", required=True)
    init.add_argument("--task-id", default="")
    init.add_argument("--title", default="")
    init.add_argument("--risk-level", choices=["low", "medium", "high", "critical", "unknown"], default="unknown")
    init.add_argument("--strict-readonly-required", action="store_true")
    init.add_argument("--delegation-ledger", default="")
    init.add_argument("--delegation-budget-id", default="")
    init.add_argument("--force", action="store_true")
    init.add_argument("--force-unlock", action="store_true")
    for key, ceiling in HARD_LIMITS.items():
        init.add_argument(
            "--" + key.replace("_", "-"),
            type=int,
            default=None,
            help="默认 {}，硬上限 {}".format(DEFAULT_LIMITS[key], ceiling),
        )
    init.set_defaults(func=command_init)

    isolation = sub.add_parser("isolation")
    add_common(isolation)
    isolation.add_argument("--review-mode", choices=sorted(VALID_REVIEW_MODES), required=True)
    isolation.add_argument("--parent-sandbox", choices=sorted(VALID_PARENT_SANDBOXES), required=True)
    isolation.add_argument("--declared-sandbox", choices=sorted(VALID_DECLARED_SANDBOXES), default="read-only")
    isolation.add_argument("--probe-result", choices=sorted(VALID_PROBE_RESULTS), default="not-run")
    isolation.add_argument("--agent-config-confirmed", action="store_true")
    isolation.add_argument("--runtime-agent-confirmed", action="store_true")
    isolation.add_argument("--evidence", default="")
    isolation.set_defaults(func=command_isolation)

    route = sub.add_parser("route")
    add_common(route)
    route.add_argument("--phase", choices=sorted(VALID_PHASES), required=True)
    route.add_argument("--decision", choices=sorted(VALID_ROUTE_DECISIONS), required=True)
    route.add_argument("--reason-code", choices=sorted(VALID_ROUTE_REASONS), required=True)
    route.add_argument("--reason", required=True)
    route.add_argument("--evidence", action="append", default=[])
    route.add_argument("--supersedes", default="")
    route.add_argument("--change-reason", default="")
    route.set_defaults(func=command_route)

    plan = sub.add_parser("plan")
    add_common(plan)
    plan.add_argument("--phase", choices=sorted(VALID_PHASES), required=True)
    plan.add_argument("--depth", type=int, required=True)
    plan.add_argument("--reviewers", required=True)
    plan.add_argument("--purpose", required=True)
    plan.add_argument("--effort-tier", choices=sorted(VALID_EFFORT_TIERS), default="balanced")
    plan.add_argument("--packet-sha256", default="")
    plan.add_argument("--allow-same-packet", action="store_true")
    plan.add_argument("--same-packet-reason", default="")
    plan.set_defaults(func=command_plan)

    dispatch = sub.add_parser("dispatch")
    add_common(dispatch)
    dispatch.add_argument("--phase", choices=sorted(VALID_PHASES), required=True)
    dispatch.add_argument("--round", type=int, required=True)
    dispatch.add_argument("--reviewer", required=True)
    dispatch.add_argument("--scope", required=True)
    dispatch.add_argument("--approved-profile", "--model-profile", dest="model_profile",
                          choices=list(MODEL_PROFILES), default="")
    dispatch.add_argument("--minimum-acceptable-profile", choices=list(MODEL_PROFILES), default="")
    dispatch.add_argument("--escalation-reason", default="")
    dispatch.add_argument("--allow-repeat", action="store_true")
    dispatch.add_argument("--repeat-reason", default="")
    dispatch.add_argument("--delegation-dispatch-key", default="")
    dispatch.set_defaults(func=command_dispatch)

    result = sub.add_parser("result")
    add_common(result)
    result.add_argument("--phase", choices=sorted(VALID_PHASES), required=True)
    result.add_argument("--round", type=int, required=True)
    result.add_argument("--reviewer", required=True)
    result.add_argument("--status", choices=sorted(VALID_RESULT_STATUSES), required=True)
    result.add_argument("--blocking-count", type=int, default=0)
    result.add_argument("--nonblocking-count", type=int, default=0)
    result.add_argument("--summary", required=True)
    result.add_argument("--result-file", default="")
    result.add_argument("--delegation-reservation-id", default="")
    result.set_defaults(func=command_result)

    merge = sub.add_parser("merge")
    add_common(merge)
    merge.add_argument("--phase", choices=sorted(VALID_PHASES), required=True)
    merge.add_argument("--round", type=int, required=True)
    merge.add_argument("--blocking-count", type=int, default=0)
    merge.add_argument("--nonblocking-count", type=int, default=0)
    merge.add_argument("--root-cause-groups", type=int, default=0)
    merge.add_argument("--summary", required=True)
    merge.add_argument("--repair-required", action="store_true")
    merge.set_defaults(func=command_merge)

    finalize_calibration = sub.add_parser("finalize-calibration")
    add_common(finalize_calibration)
    finalize_calibration.add_argument("--phase", choices=sorted(VALID_PHASES), required=True)
    finalize_calibration.add_argument("--round", type=int, required=True)
    finalize_calibration.add_argument("--reviewer", required=True)
    finalize_calibration.add_argument("--finalized-by", required=True)
    finalize_calibration.add_argument("--accepted", type=int, required=True)
    finalize_calibration.add_argument("--rejected", type=int, required=True)
    finalize_calibration.add_argument("--duplicate", type=int, required=True)
    finalize_calibration.add_argument("--repaired", type=int, required=True)
    finalize_calibration.add_argument("--regressions-prevented", type=int, required=True)
    finalize_calibration.add_argument("--evidence", action="append", default=[])
    finalize_calibration.add_argument("--note", default="")
    finalize_calibration.set_defaults(func=command_finalize_calibration)

    repair = sub.add_parser("repair")
    add_common(repair)
    repair.add_argument("--summary", required=True)
    repair.add_argument("--affected-dimensions", default="")
    repair.add_argument("--validation", default="")
    repair.set_defaults(func=command_repair)

    validate = sub.add_parser("validate")
    validate.add_argument("--review-dir", required=True)
    validate.add_argument("--require-strict-readonly", action="store_true")
    validate.set_defaults(func=command_validate)

    sync_calibration = sub.add_parser("sync-calibration")
    add_common(sync_calibration)
    sync_calibration.set_defaults(func=command_sync_calibration)

    status = sub.add_parser("status")
    status.add_argument("--review-dir", required=True)
    status.set_defaults(func=command_status)

    close = sub.add_parser("close")
    add_common(close)
    close.add_argument("--conclusion", choices=sorted(VALID_CONCLUSIONS), required=True)
    close.add_argument("--note", default="")
    close.add_argument("--ack-model-policy-violation", action="store_true")
    close.set_defaults(func=command_close)
    return parser


def main() -> None:
    args = build_parser().parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
