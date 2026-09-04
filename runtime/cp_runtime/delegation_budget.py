"""中文：DelegationBudget V2 与只读 V1 兼容校验。

English: DelegationBudget V2, the root-task weighted budget ledger shared by
Reviewer, Explorer, and Worker subagents.

账本只接受受控枚举、标识符和 SHA-256 引用；不保存 Prompt、回答、代码、Diff、
原始 tool input、Token 或凭据。事件链与预算链互不改写；旧 V1 账本只读验证。
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import secrets
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional

from .event_v2 import OwnerTokenLock

SCHEMA_VERSION = "2.0"
LEGACY_SCHEMA_VERSION = "1.0"
ZERO_HASH = "0" * 64
ROLES = {"reviewer", "explorer", "worker"}
PROFILES = ("luna-low", "luna-medium", "terra-medium", "terra-high")
PROFILE_WEIGHTS = {"luna-low": 1, "luna-medium": 2, "terra-medium": 4, "terra-high": 8}
PROFILE_ORDER = {name: index for index, name in enumerate(PROFILES)}
BUDGET_CLASSES = {
    "LIGHT": {"max_units": 4, "max_dispatches": 2, "max_parallel": 1, "max_depth": 1, "max_terra_high": 0},
    "STANDARD": {"max_units": 16, "max_dispatches": 6, "max_parallel": 3, "max_depth": 2, "max_terra_high": 1},
    "STRICT": {"max_units": 32, "max_dispatches": 10, "max_parallel": 3, "max_depth": 2, "max_terra_high": 1},
}
REASONS = {
    "INDEPENDENT_EVIDENCE_GAIN", "SEMANTIC_COMPLEXITY", "EVIDENCE_CONFLICT",
    "SECURITY_OR_CONCURRENCY_RISK", "LOWER_TIER_INCONCLUSIVE", "MISSING_EVIDENCE",
    "INLINE_SUFFICIENT",
}
EVENT_TYPES = {
    "DECISION_RECORDED", "BUDGET_RESERVED", "AGENT_STARTED", "AGENT_COMPLETED",
    "NOT_STARTED_RELEASED", "BUDGET_VIOLATED", "TASK_BUDGET_CLOSED",
}
EVENT_DATA_KEYS = {
    ("DECISION_RECORDED", "budget-initialized"): {
        "decision_kind", "budget_class", "default_dispatch_profile", "limits",
        "role_limits", "cost_formula_version", "association_mode",
    },
    ("DECISION_RECORDED", "dispatch"): {
        "decision_kind", "dispatch_ref", "decision", "role", "approved_profile",
        "reason_code", "responsibility", "difficulty", "risk_domain", "context_size",
        "parent_reservation_id", "depth", "prior_profile", "prior_result_ref",
    },
    ("BUDGET_RESERVED", ""): {
        "reservation_id", "dispatch_ref", "host_dispatch_ref", "role",
        "approved_profile", "approval_basis", "units", "parent_reservation_id",
        "depth", "association",
    },
    ("AGENT_STARTED", ""): {
        "reservation_id", "agent_ref", "association",
    },
    ("AGENT_COMPLETED", ""): {"reservation_id", "outcome"},
    ("NOT_STARTED_RELEASED", ""): {"reservation_id", "proof_ref", "proof_kind"},
    ("TASK_BUDGET_CLOSED", ""): {"conclusion", "association_complete", "budget_pass"},
}
# 中文：PRIVACY_LEGACY_READER_BEGIN；English: legacy-reader scope begins.
LEGACY_EVENT_DATA_KEYS = {
    ("DECISION_RECORDED", "budget-initialized"): {
        "decision_kind", "budget_class", "default_model_profile", "limits", "role_limits",
        "cost_formula_version", "association_mode",
    },
    ("DECISION_RECORDED", "dispatch"): {
        "decision_kind", "dispatch_ref", "decision", "role", "requested_profile",
        "reason_code", "responsibility", "difficulty", "risk_domain", "context_size",
        "parent_reservation_id", "depth", "prior_profile", "prior_result_ref",
    },
    ("BUDGET_RESERVED", ""): {
        "reservation_id", "dispatch_ref", "host_dispatch_ref", "role", "requested_profile",
        "request_basis", "units", "parent_reservation_id", "depth", "association",
    },
    ("AGENT_STARTED", ""): {
        "reservation_id", "agent_ref", "actual_profile", "runtime_evidence", "top_up_units", "association",
    },
    ("AGENT_COMPLETED", ""): {"reservation_id", "outcome"},
    ("NOT_STARTED_RELEASED", ""): {"reservation_id", "proof_ref", "proof_kind"},
    ("BUDGET_VIOLATED", ""): {"reservation_id", "reason_code", "required_top_up_units"},
    ("TASK_BUDGET_CLOSED", ""): {"conclusion", "association_complete", "budget_pass"},
}
# 中文：PRIVACY_LEGACY_READER_END；English: legacy-reader scope ends.
RESERVATION_STATES = {"RESERVED", "STARTED", "COMPLETED", "NOT_STARTED_RELEASED"}
IDENTIFIER = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,159}$")
SHA_REF = re.compile(r"^sha256:[0-9a-f]{64}$")
REPO_FINGERPRINT = SHA_REF
DIFFICULTIES = {"LOW", "MEDIUM", "HIGH", "CRITICAL", "UNKNOWN"}
RISK_DOMAINS = {"GENERAL", "SECURITY", "CONCURRENCY", "DATA", "COMPATIBILITY", "PERFORMANCE", "UNKNOWN"}
CONTEXT_SIZES = {"SMALL", "MEDIUM", "LARGE", "UNKNOWN"}


class DelegationBudgetError(ValueError):
    """中文：预算契约、完整性或容量错误。

    English: Budget contract, integrity, or capacity error.
    """


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")


def canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def sha256_ref(value: str) -> str:
    return "sha256:" + hashlib.sha256(value.encode("utf-8", errors="strict")).hexdigest()


def stable_id(prefix: str, *parts: str) -> str:
    digest = hashlib.sha256("\0".join(parts).encode("utf-8")).hexdigest()[:32]
    return "%s_%s" % (prefix, digest)


def _identifier(value: Any, name: str) -> str:
    text = str(value or "").strip()
    if not IDENTIFIER.fullmatch(text):
        raise DelegationBudgetError("%s 非法" % name)
    return text


def _sha_ref(value: Any, name: str, *, optional: bool = False) -> str:
    text = str(value or "").strip()
    if optional and not text:
        return ""
    if not SHA_REF.fullmatch(text):
        raise DelegationBudgetError("%s 必须是 sha256 引用" % name)
    return text


def _positive(value: Any, name: str, *, allow_zero: bool = False) -> int:
    if isinstance(value, bool):
        raise DelegationBudgetError("%s 必须是整数" % name)
    try:
        result = int(value)
    except (TypeError, ValueError) as exc:
        raise DelegationBudgetError("%s 必须是整数" % name) from exc
    if result < (0 if allow_zero else 1):
        raise DelegationBudgetError("%s 超出范围" % name)
    return result


def normalize_role(value: Any) -> str:
    role = str(value or "").strip().lower()
    if role.startswith("cp_review") or role == "review":
        role = "reviewer"
    if role not in ROLES:
        raise DelegationBudgetError("未知 agent role，受控任务失败关闭")
    return role


def profile_for(model: str, effort: str, default_profile: str) -> tuple[str, str]:
    model = str(model or "").strip()
    effort = str(effort or "").strip().lower()
    if not model and not effort:
        if default_profile not in PROFILE_WEIGHTS:
            raise DelegationBudgetError("Task Envelope 默认模型档位非法")
        return default_profile, "policy-default"
    mapping = {
        ("gpt-5.6-luna", "low"): "luna-low",
        ("gpt-5.6-luna", "medium"): "luna-medium",
        ("gpt-5.6-terra", "medium"): "terra-medium",
        ("gpt-5.6-terra", "high"): "terra-high",
    }
    profile = mapping.get((model, effort))
    if not profile:
        raise DelegationBudgetError("显式模型与 reasoning_effort 不属于批准的四级档位")
    return profile, "explicit-request"


def _validate_limits(value: Mapping[str, Any]) -> Dict[str, int]:
    required = {"max_units", "max_dispatches", "max_parallel", "max_depth", "max_terra_high"}
    if set(value) != required:
        raise DelegationBudgetError("预算 limits 字段不完整或包含未知字段")
    return {
        "max_units": _positive(value["max_units"], "max_units"),
        "max_dispatches": _positive(value["max_dispatches"], "max_dispatches"),
        "max_parallel": _positive(value["max_parallel"], "max_parallel"),
        "max_depth": _positive(value["max_depth"], "max_depth"),
        "max_terra_high": _positive(value["max_terra_high"], "max_terra_high", allow_zero=True),
    }


def _default_role_limits(limits: Mapping[str, int]) -> Dict[str, Dict[str, int]]:
    return {role: {"max_units": limits["max_units"], "max_dispatches": limits["max_dispatches"]} for role in sorted(ROLES)}


def _validate_role_limits(value: Mapping[str, Any], limits: Mapping[str, int]) -> Dict[str, Dict[str, int]]:
    if set(value) != ROLES:
        raise DelegationBudgetError("role_limits 必须精确覆盖 reviewer/explorer/worker")
    result: Dict[str, Dict[str, int]] = {}
    for role in sorted(ROLES):
        item = value[role]
        if not isinstance(item, Mapping) or set(item) != {"max_units", "max_dispatches"}:
            raise DelegationBudgetError("role_limits.%s 字段非法" % role)
        result[role] = {
            "max_units": min(_positive(item["max_units"], role + ".max_units"), limits["max_units"]),
            "max_dispatches": min(_positive(item["max_dispatches"], role + ".max_dispatches"), limits["max_dispatches"]),
        }
    return result


def _record_hash(previous: str, unsigned: Mapping[str, Any]) -> str:
    return hashlib.sha256((previous + "\n" + canonical_json(unsigned)).encode("utf-8")).hexdigest()


def _event(identity: Mapping[str, str], event_type: str, event_id: str, data: Mapping[str, Any], sequence: int, previous: str) -> Dict[str, Any]:
    if event_type not in EVENT_TYPES:
        raise DelegationBudgetError("未知预算事件")
    unsigned = {
        "schema_version": SCHEMA_VERSION,
        "event_id": _identifier(event_id, "event_id"),
        "event_type": event_type,
        "captured_at": utc_now(),
        "sequence": sequence,
        "budget_id": _identifier(identity["budget_id"], "budget_id"),
        "task_id": _identifier(identity["task_id"], "task_id"),
        "project_id": _identifier(identity["project_id"], "project_id"),
        "repo_fingerprint": _sha_ref(identity["repo_fingerprint"], "repo_fingerprint"),
        "data": dict(data),
    }
    record = dict(unsigned)
    record["previous_hash"] = previous
    record["record_hash"] = _record_hash(previous, unsigned)
    return record


def _validate_event_data(schema_version: str, event_type: str, data: Mapping[str, Any]) -> None:
    decision_kind = str(data.get("decision_kind") or "") if event_type == "DECISION_RECORDED" else ""
    contracts = EVENT_DATA_KEYS if schema_version == SCHEMA_VERSION else LEGACY_EVENT_DATA_KEYS
    expected = contracts.get((event_type, decision_kind))
    if expected is None or set(data) != expected:
        raise DelegationBudgetError("预算事件 data 字段非法")


def _read_records_unlocked(path: Path) -> List[Dict[str, Any]]:
    if not path.exists():
        return []
    records: List[Dict[str, Any]] = []
    previous = ZERO_HASH
    identity: Optional[tuple[str, str, str, str]] = None
    ledger_schema: Optional[str] = None
    seen = set()
    with path.open("r", encoding="utf-8") as handle:
        for number, line in enumerate(handle, 1):
            if not line.strip():
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError as exc:
                raise DelegationBudgetError("预算账本第 %d 行不是完整 JSON" % number) from exc
            expected_keys = {
                "schema_version", "event_id", "event_type", "captured_at", "sequence",
                "budget_id", "task_id", "project_id", "repo_fingerprint", "data",
                "previous_hash", "record_hash",
            }
            if not isinstance(record, dict) or set(record) != expected_keys:
                raise DelegationBudgetError("预算账本第 %d 行字段非法" % number)
            if record["schema_version"] not in {SCHEMA_VERSION, LEGACY_SCHEMA_VERSION} or record["event_type"] not in EVENT_TYPES:
                raise DelegationBudgetError("预算账本 schema 或事件类型未知")
            if ledger_schema is None:
                ledger_schema = str(record["schema_version"])
            elif record["schema_version"] != ledger_schema:
                raise DelegationBudgetError("同一预算账本禁止混用 V1 与 V2")
            if record["schema_version"] == SCHEMA_VERSION and record["event_type"] == "BUDGET_VIOLATED":
                raise DelegationBudgetError("Budget V2 不支持启动后补扣违规事件")
            if record["sequence"] != len(records) + 1 or record["previous_hash"] != previous:
                raise DelegationBudgetError("预算账本序号或哈希链断裂")
            if record["event_id"] in seen:
                raise DelegationBudgetError("预算账本 event_id 重复")
            current_identity = tuple(str(record[key]) for key in ("budget_id", "task_id", "project_id", "repo_fingerprint"))
            if identity is None:
                identity = current_identity
            elif current_identity != identity:
                raise DelegationBudgetError("预算账本项目或根任务身份串线")
            unsigned = {key: record[key] for key in expected_keys - {"previous_hash", "record_hash"}}
            expected_hash = _record_hash(previous, unsigned)
            if record["record_hash"] != expected_hash:
                raise DelegationBudgetError("预算账本哈希校验失败")
            if not isinstance(record["data"], dict):
                raise DelegationBudgetError("预算事件 data 必须是对象")
            _validate_event_data(str(record["schema_version"]), record["event_type"], record["data"])
            previous = record["record_hash"]
            seen.add(record["event_id"])
            records.append(record)
    return records


def _append_unlocked(path: Path, records: List[Dict[str, Any]]) -> None:
    if not records:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8", newline="\n") as handle:
        for record in records:
            handle.write(canonical_json(record) + "\n")
        handle.flush()
        os.fsync(handle.fileno())


def _identity(records: List[Dict[str, Any]]) -> Dict[str, str]:
    if not records:
        raise DelegationBudgetError("预算账本尚未初始化")
    first = records[0]
    return {key: str(first[key]) for key in ("budget_id", "task_id", "project_id", "repo_fingerprint")}


def _replay(records: List[Dict[str, Any]]) -> Dict[str, Any]:
    if not records or records[0]["event_type"] != "DECISION_RECORDED" or records[0]["data"].get("decision_kind") != "budget-initialized":
        raise DelegationBudgetError("预算账本缺少初始化事件")
    if records[0].get("schema_version") != SCHEMA_VERSION:
        raise DelegationBudgetError("DelegationBudget V1 为只读；请初始化独立 V2 账本")
    init = records[0]["data"]
    limits = _validate_limits(init.get("limits") or {})
    role_limits = _validate_role_limits(init.get("role_limits") or {}, limits)
    default_profile = str(init.get("default_dispatch_profile") or "")
    budget_class = str(init.get("budget_class") or "")
    if default_profile not in PROFILE_WEIGHTS or budget_class not in BUDGET_CLASSES:
        raise DelegationBudgetError("初始化预算档位非法")
    if init["limits"] != BUDGET_CLASSES[budget_class] \
            or init["cost_formula_version"] != "profile-weight-v1" \
            or init["association_mode"] != "explicit-dispatch-permit":
        raise DelegationBudgetError("初始化预算契约非法")
    decisions: Dict[str, Dict[str, Any]] = {}
    reservations: Dict[str, Dict[str, Any]] = {}
    violations: List[Dict[str, Any]] = []
    closed = False
    for record in records[1:]:
        event_type = record["event_type"]
        data = record["data"]
        if closed:
            raise DelegationBudgetError("预算关闭后不得追加事件")
        if event_type == "DECISION_RECORDED":
            ref = _sha_ref(data.get("dispatch_ref"), "dispatch_ref")
            if ref in decisions:
                raise DelegationBudgetError("dispatch decision 重复")
            decision = str(data.get("decision") or "")
            role = normalize_role(data.get("role"))
            profile = str(data.get("approved_profile") or "")
            reason = str(data.get("reason_code") or "")
            difficulty = str(data.get("difficulty") or "")
            risk_domain = str(data.get("risk_domain") or "")
            context_size = str(data.get("context_size") or "")
            if decision not in {"INLINE", "DELEGATE"} or profile not in PROFILE_WEIGHTS or reason not in REASONS:
                raise DelegationBudgetError("账本路由决策非法")
            if difficulty not in DIFFICULTIES or risk_domain not in RISK_DOMAINS or context_size not in CONTEXT_SIZES:
                raise DelegationBudgetError("账本校准场景枚举非法")
            _identifier(data.get("responsibility"), "responsibility")
            parent_reservation_id = str(data.get("parent_reservation_id") or "")
            if parent_reservation_id:
                _identifier(parent_reservation_id, "parent_reservation_id")
            depth = _positive(data.get("depth"), "depth")
            prior_profile = str(data.get("prior_profile") or "")
            prior_result_ref = str(data.get("prior_result_ref") or "")
            if decision == "INLINE" and reason != "INLINE_SUFFICIENT":
                raise DelegationBudgetError("账本 INLINE 决策原因非法")
            if decision == "DELEGATE" and reason == "INLINE_SUFFICIENT":
                raise DelegationBudgetError("账本 DELEGATE 决策原因非法")
            if reason == "LOWER_TIER_INCONCLUSIVE":
                if prior_profile not in PROFILE_WEIGHTS or PROFILE_ORDER[profile] != PROFILE_ORDER[prior_profile] + 1:
                    raise DelegationBudgetError("账本逐级升级关系非法")
                _sha_ref(prior_result_ref, "prior_result_ref")
            elif prior_profile or prior_result_ref:
                raise DelegationBudgetError("账本非升级决策携带上一档结果")
            decisions[ref] = {**dict(data), "role": role, "depth": depth}
        elif event_type == "BUDGET_RESERVED":
            rid = _identifier(data.get("reservation_id"), "reservation_id")
            if rid in reservations:
                raise DelegationBudgetError("reservation_id 重复")
            if data.get("dispatch_ref") not in decisions:
                raise DelegationBudgetError("预占缺少对应 decision")
            role = normalize_role(data.get("role"))
            profile = str(data.get("approved_profile") or "")
            if profile not in PROFILE_WEIGHTS:
                raise DelegationBudgetError("预占模型档位非法")
            decision = decisions[data["dispatch_ref"]]
            if decision["decision"] != "DELEGATE" or role != decision["role"] \
                    or profile != decision["approved_profile"] \
                    or data["units"] != PROFILE_WEIGHTS[profile] \
                    or data["parent_reservation_id"] != decision["parent_reservation_id"] \
                    or data["depth"] != decision["depth"] \
                    or data["approval_basis"] not in {"policy-default", "explicit-request"} \
                    or data["association"] != "pretool-verified":
                raise DelegationBudgetError("预占与显式 decision 不一致")
            _sha_ref(data.get("host_dispatch_ref"), "host_dispatch_ref")
            reservations[rid] = {
                **dict(data), "role": role, "charged_units": PROFILE_WEIGHTS[profile],
                "state": "RESERVED", "agent_ref": "", "completion_ref": "",
            }
        elif event_type == "AGENT_STARTED":
            rid = _identifier(data.get("reservation_id"), "reservation_id")
            item = reservations.get(rid)
            if not item or item["state"] != "RESERVED":
                raise DelegationBudgetError("AGENT_STARTED 状态转换非法")
            item["state"] = "STARTED"
            item["agent_ref"] = _sha_ref(data.get("agent_ref"), "agent_ref")
            if data.get("association") != "reservation-id":
                raise DelegationBudgetError("启动关联字段非法")
        elif event_type == "AGENT_COMPLETED":
            rid = _identifier(data.get("reservation_id"), "reservation_id")
            item = reservations.get(rid)
            if not item or item["state"] != "STARTED":
                raise DelegationBudgetError("AGENT_COMPLETED 状态转换非法")
            item["state"] = "COMPLETED"
            outcome = str(data.get("outcome") or "")
            if outcome not in {"PASS", "BLOCKED", "FAILED", "CANCELLED", "PARTIAL", "UNKNOWN"}:
                raise DelegationBudgetError("账本 Agent outcome 非法")
            item["outcome"] = outcome
            item["completion_ref"] = "sha256:" + record["record_hash"]
        elif event_type == "NOT_STARTED_RELEASED":
            rid = _identifier(data.get("reservation_id"), "reservation_id")
            item = reservations.get(rid)
            if not item or item["state"] != "RESERVED":
                raise DelegationBudgetError("只有未启动预占可以释放")
            _sha_ref(data.get("proof_ref"), "proof_ref")
            if data.get("proof_kind") != "host-confirmed-not-started":
                raise DelegationBudgetError("预占释放证明类型非法")
            item["state"] = "NOT_STARTED_RELEASED"
            item["charged_units"] = 0
        elif event_type == "TASK_BUDGET_CLOSED":
            if closed:
                raise DelegationBudgetError("预算已经关闭")
            if data.get("conclusion") not in {"PASS", "BLOCKED", "FAILED", "CANCELLED", "PARTIAL", "UNKNOWN"} \
                    or not isinstance(data.get("association_complete"), bool) \
                    or not isinstance(data.get("budget_pass"), bool):
                raise DelegationBudgetError("预算关闭事件非法")
            expected_association = all(item["state"] != "RESERVED" for item in reservations.values()
                                       if item["state"] != "NOT_STARTED_RELEASED")
            if data["association_complete"] != expected_association or data["budget_pass"] != (not violations):
                raise DelegationBudgetError("预算关闭快照与账本状态不一致")
            closed = True
    charged = [item for item in reservations.values() if item["state"] != "NOT_STARTED_RELEASED"]
    active = [item for item in charged if item["state"] in {"RESERVED", "STARTED"}]
    role_usage = {
        role: {
            "units": sum(item["charged_units"] for item in charged if item["role"] == role),
            "dispatches": sum(1 for item in charged if item["role"] == role),
            "active": sum(1 for item in active if item["role"] == role),
        }
        for role in sorted(ROLES)
    }
    profile_usage = {profile: sum(1 for item in charged if item["approved_profile"] == profile) for profile in PROFILES}
    used_units = sum(item["charged_units"] for item in charged)
    violated = bool(violations) or used_units > limits["max_units"]
    return {
        "identity": _identity(records), "budget_class": budget_class,
        "schema_version": SCHEMA_VERSION, "read_only": False,
        "default_dispatch_profile": default_profile, "limits": limits, "role_limits": role_limits,
        "decisions": decisions, "reservations": reservations, "violations": violations,
        "usage": {"units": used_units, "dispatches": len(charged), "active": len(active),
                  "terra_high": sum(1 for item in charged if item["approved_profile"] == "terra-high"),
                  "by_role": role_usage, "by_approved_profile": profile_usage},
        "remaining_units": max(0, limits["max_units"] - used_units),
        "violated": violated, "closed": closed, "association_complete": all(item["state"] != "RESERVED" for item in charged),
        "head_hash": records[-1]["record_hash"], "event_count": len(records),
    }


# 中文：PRIVACY_LEGACY_READER_BEGIN；English: legacy-reader scope begins.
def _replay_legacy_budget(records: List[Dict[str, Any]]) -> Dict[str, Any]:
    """中文：先重放冻结的 V1 状态机，再暴露安全投影。

    English: Replay the frozen V1 state machine before any safe projection is exposed.
    """
    if not records or records[0]["event_type"] != "DECISION_RECORDED" \
            or records[0]["data"].get("decision_kind") != "budget-initialized":
        raise DelegationBudgetError("旧预算账本缺少初始化事件")
    init = records[0]["data"]
    limits = _validate_limits(init.get("limits") or {})
    role_limits = _validate_role_limits(init.get("role_limits") or {}, limits)
    default_profile = str(init.get("default_model_profile") or "")
    budget_class = str(init.get("budget_class") or "")
    if default_profile not in PROFILE_WEIGHTS or budget_class not in BUDGET_CLASSES:
        raise DelegationBudgetError("旧预算初始化档位非法")
    if init["limits"] != BUDGET_CLASSES[budget_class] \
            or init["cost_formula_version"] != "profile-weight-v1" \
            or init["association_mode"] != "explicit-dispatch-permit":
        raise DelegationBudgetError("旧预算初始化契约非法")
    decisions: Dict[str, Dict[str, Any]] = {}
    reservations: Dict[str, Dict[str, Any]] = {}
    violations: List[Dict[str, Any]] = []
    closed = False
    for record in records[1:]:
        event_type = record["event_type"]
        data = record["data"]
        if closed:
            raise DelegationBudgetError("旧预算关闭后不得追加事件")
        if event_type == "DECISION_RECORDED":
            ref = _sha_ref(data.get("dispatch_ref"), "dispatch_ref")
            if ref in decisions:
                raise DelegationBudgetError("旧预算 dispatch decision 重复")
            decision = str(data.get("decision") or "")
            role = normalize_role(data.get("role"))
            profile = str(data.get("requested_profile") or "")
            reason = str(data.get("reason_code") or "")
            difficulty = str(data.get("difficulty") or "")
            risk_domain = str(data.get("risk_domain") or "")
            context_size = str(data.get("context_size") or "")
            if decision not in {"INLINE", "DELEGATE"} or profile not in PROFILE_WEIGHTS or reason not in REASONS:
                raise DelegationBudgetError("旧预算路由决策非法")
            if difficulty not in DIFFICULTIES or risk_domain not in RISK_DOMAINS or context_size not in CONTEXT_SIZES:
                raise DelegationBudgetError("旧预算校准场景枚举非法")
            _identifier(data.get("responsibility"), "responsibility")
            parent_reservation_id = str(data.get("parent_reservation_id") or "")
            if parent_reservation_id:
                _identifier(parent_reservation_id, "parent_reservation_id")
            depth = _positive(data.get("depth"), "depth")
            prior_profile = str(data.get("prior_profile") or "")
            prior_result_ref = str(data.get("prior_result_ref") or "")
            if decision == "INLINE" and reason != "INLINE_SUFFICIENT":
                raise DelegationBudgetError("旧预算 INLINE 决策原因非法")
            if decision == "DELEGATE" and reason == "INLINE_SUFFICIENT":
                raise DelegationBudgetError("旧预算 DELEGATE 决策原因非法")
            if reason == "LOWER_TIER_INCONCLUSIVE":
                if prior_profile not in PROFILE_WEIGHTS or PROFILE_ORDER[profile] != PROFILE_ORDER[prior_profile] + 1:
                    raise DelegationBudgetError("旧预算逐级升级关系非法")
                _sha_ref(prior_result_ref, "prior_result_ref")
            elif prior_profile or prior_result_ref:
                raise DelegationBudgetError("旧预算非升级决策携带上一档结果")
            decisions[ref] = {**dict(data), "role": role, "depth": depth}
        elif event_type == "BUDGET_RESERVED":
            rid = _identifier(data.get("reservation_id"), "reservation_id")
            if rid in reservations:
                raise DelegationBudgetError("旧预算 reservation_id 重复")
            if data.get("dispatch_ref") not in decisions:
                raise DelegationBudgetError("旧预算预占缺少对应 decision")
            role = normalize_role(data.get("role"))
            profile = str(data.get("requested_profile") or "")
            if profile not in PROFILE_WEIGHTS:
                raise DelegationBudgetError("旧预算预占档位非法")
            decision = decisions[data["dispatch_ref"]]
            if decision["decision"] != "DELEGATE" or role != decision["role"] \
                    or profile != decision["requested_profile"] \
                    or data["units"] != PROFILE_WEIGHTS[profile] \
                    or data["parent_reservation_id"] != decision["parent_reservation_id"] \
                    or data["depth"] != decision["depth"] \
                    or data["request_basis"] not in {"policy-default", "explicit-request"} \
                    or data["association"] != "pretool-verified":
                raise DelegationBudgetError("旧预算预占与显式 decision 不一致")
            _sha_ref(data.get("host_dispatch_ref"), "host_dispatch_ref")
            reservations[rid] = {
                **dict(data), "role": role, "charged_units": PROFILE_WEIGHTS[profile],
                "state": "RESERVED", "actual_profile": "", "agent_ref": "", "completion_ref": "",
            }
        elif event_type == "AGENT_STARTED":
            rid = _identifier(data.get("reservation_id"), "reservation_id")
            item = reservations.get(rid)
            if not item or item["state"] != "RESERVED":
                raise DelegationBudgetError("旧预算 AGENT_STARTED 状态转换非法")
            item["state"] = "STARTED"
            item["agent_ref"] = _sha_ref(data.get("agent_ref"), "agent_ref")
            actual = str(data.get("actual_profile") or "")
            expected_top_up = max(0, PROFILE_WEIGHTS.get(actual, 0) - item["charged_units"])
            if data.get("top_up_units") != expected_top_up or data.get("association") != "reservation-id":
                raise DelegationBudgetError("旧预算启动补扣或关联字段非法")
            if actual:
                if actual not in PROFILE_WEIGHTS or data.get("runtime_evidence") != "host-attested-hook-payload":
                    raise DelegationBudgetError("旧预算实际档位缺少原始证明")
                item["actual_profile"] = actual
                item["charged_units"] = max(item["charged_units"], PROFILE_WEIGHTS[actual])
            elif data.get("runtime_evidence") != "unavailable":
                raise DelegationBudgetError("旧预算未证明实际档位时证据状态非法")
        elif event_type == "AGENT_COMPLETED":
            rid = _identifier(data.get("reservation_id"), "reservation_id")
            item = reservations.get(rid)
            if not item or item["state"] != "STARTED":
                raise DelegationBudgetError("旧预算 AGENT_COMPLETED 状态转换非法")
            item["state"] = "COMPLETED"
            outcome = str(data.get("outcome") or "")
            if outcome not in {"PASS", "BLOCKED", "FAILED", "CANCELLED", "PARTIAL", "UNKNOWN"}:
                raise DelegationBudgetError("旧预算 Agent outcome 非法")
            item["outcome"] = outcome
            item["completion_ref"] = "sha256:" + record["record_hash"]
        elif event_type == "NOT_STARTED_RELEASED":
            rid = _identifier(data.get("reservation_id"), "reservation_id")
            item = reservations.get(rid)
            if not item or item["state"] != "RESERVED":
                raise DelegationBudgetError("旧预算只有未启动预占可以释放")
            _sha_ref(data.get("proof_ref"), "proof_ref")
            if data.get("proof_kind") != "host-confirmed-not-started":
                raise DelegationBudgetError("旧预算预占释放证明类型非法")
            item["state"] = "NOT_STARTED_RELEASED"
            item["charged_units"] = 0
        elif event_type == "BUDGET_VIOLATED":
            rid = _identifier(data.get("reservation_id"), "reservation_id")
            item = reservations.get(rid)
            required = _positive(data.get("required_top_up_units"), "required_top_up_units")
            if not item or item["state"] != "STARTED" \
                    or data.get("reason_code") != "ACTUAL_PROFILE_TOP_UP_EXCEEDED" \
                    or required != max(0, item["charged_units"] - PROFILE_WEIGHTS[item["requested_profile"]]):
                raise DelegationBudgetError("旧预算违规事件非法")
            violations.append(dict(data))
        elif event_type == "TASK_BUDGET_CLOSED":
            if closed:
                raise DelegationBudgetError("旧预算已经关闭")
            if data.get("conclusion") not in {"PASS", "BLOCKED", "FAILED", "CANCELLED", "PARTIAL", "UNKNOWN"} \
                    or not isinstance(data.get("association_complete"), bool) \
                    or not isinstance(data.get("budget_pass"), bool):
                raise DelegationBudgetError("旧预算关闭事件非法")
            expected_association = all(item["state"] != "RESERVED" for item in reservations.values()
                                       if item["state"] != "NOT_STARTED_RELEASED")
            if data["association_complete"] != expected_association or data["budget_pass"] != (not violations):
                raise DelegationBudgetError("旧预算关闭快照与账本状态不一致")
            closed = True
    return {
        "init": init, "limits": limits, "role_limits": role_limits,
        "decisions": decisions, "reservations": reservations,
        "violations": violations, "closed": closed,
    }


def _project_legacy_budget(records: List[Dict[str, Any]]) -> Dict[str, Any]:
    """中文：返回 V1 的安全只读投影；宿主模型身份及补扣内容不进入结果。

    English: Return a safe read-only V1 projection without host model identity or top-up data.
    """
    if not records or records[0].get("schema_version") != LEGACY_SCHEMA_VERSION:
        raise DelegationBudgetError("不是 DelegationBudget V1 账本")
    replayed = _replay_legacy_budget(records)
    init = replayed["init"]
    limits = replayed["limits"]
    role_limits = replayed["role_limits"]
    decisions = {
        ref: {
            "decision_kind": "dispatch", "dispatch_ref": data["dispatch_ref"],
            "decision": data["decision"], "role": data["role"],
            "approved_profile": data["requested_profile"], "reason_code": data["reason_code"],
            "responsibility": data["responsibility"], "difficulty": data["difficulty"],
            "risk_domain": data["risk_domain"], "context_size": data["context_size"],
            "parent_reservation_id": data["parent_reservation_id"], "depth": data["depth"],
            "prior_profile": data["prior_profile"], "prior_result_ref": data["prior_result_ref"],
        }
        for ref, data in replayed["decisions"].items()
    }
    reservations = {
        rid: {
            "reservation_id": data["reservation_id"], "dispatch_ref": data["dispatch_ref"],
            "host_dispatch_ref": data["host_dispatch_ref"], "role": data["role"],
            "approved_profile": data["requested_profile"], "approval_basis": data["request_basis"],
            "units": data["units"], "charged_units": data["units"],
            "parent_reservation_id": data["parent_reservation_id"], "depth": data["depth"],
            "association": data["association"], "state": data["state"],
            "agent_ref": data.get("agent_ref", ""), "completion_ref": data.get("completion_ref", ""),
            **({"outcome": data["outcome"]} if "outcome" in data else {}),
        }
        for rid, data in replayed["reservations"].items()
    }
    closed = replayed["closed"]
    charged = [item for item in reservations.values() if item["state"] != "NOT_STARTED_RELEASED"]
    active = [item for item in charged if item["state"] in {"RESERVED", "STARTED"}]
    used_units = sum(int(item["charged_units"]) for item in charged)
    by_role = {role: {"units": sum(item["charged_units"] for item in charged if item["role"] == role),
                      "dispatches": sum(1 for item in charged if item["role"] == role),
                      "active": sum(1 for item in active if item["role"] == role)} for role in sorted(ROLES)}
    by_profile = {profile: sum(1 for item in charged if item["approved_profile"] == profile) for profile in PROFILES}
    return {
        "schema_version": LEGACY_SCHEMA_VERSION, "read_only": True, "identity": _identity(records),
        "budget_class": init["budget_class"], "default_dispatch_profile": init["default_model_profile"],
        "limits": limits, "role_limits": role_limits, "decisions": decisions, "reservations": reservations,
        "violations": [], "usage": {"units": used_units, "dispatches": len(charged), "active": len(active),
        "terra_high": by_profile["terra-high"], "by_role": by_role, "by_approved_profile": by_profile},
        "remaining_units": max(0, limits["max_units"] - used_units), "violated": False, "closed": closed,
        "association_complete": all(item["state"] != "RESERVED" for item in charged),
        "head_hash": records[-1]["record_hash"], "event_count": len(records),
    }
# 中文：PRIVACY_LEGACY_READER_END；English: legacy-reader scope ends.


def read_budget(path: Path) -> Dict[str, Any]:
    path = Path(path)
    with OwnerTokenLock(path, timeout=1.5):
        records = _read_records_unlocked(path)
        if records and records[0].get("schema_version") == LEGACY_SCHEMA_VERSION:
            return _project_legacy_budget(records)
        return _replay(records)


def initialize_budget(path: Path, *, budget_id: str, task_id: str, project_id: str,
                      repo_fingerprint: str, budget_class: str,
                      default_dispatch_profile: str,
                      role_limits: Optional[Mapping[str, Any]] = None) -> Dict[str, Any]:
    path = Path(path)
    identity = {
        "budget_id": _identifier(budget_id, "budget_id"),
        "task_id": _identifier(task_id, "task_id"),
        "project_id": _identifier(project_id, "project_id"),
        "repo_fingerprint": _sha_ref(repo_fingerprint, "repo_fingerprint"),
    }
    if budget_class not in BUDGET_CLASSES or default_dispatch_profile not in PROFILE_WEIGHTS:
        raise DelegationBudgetError("预算或默认派发档位非法")
    limits = dict(BUDGET_CLASSES[budget_class])
    roles = _validate_role_limits(role_limits or _default_role_limits(limits), limits)
    data = {
        "decision_kind": "budget-initialized", "budget_class": budget_class,
        "default_dispatch_profile": default_dispatch_profile, "limits": limits,
        "role_limits": roles, "cost_formula_version": "profile-weight-v1",
        "association_mode": "explicit-dispatch-permit",
    }
    with OwnerTokenLock(path, timeout=1.5):
        existing = _read_records_unlocked(path)
        if existing:
            state = _replay(existing)
            if state["identity"] != identity or existing[0]["data"] != data:
                raise DelegationBudgetError("已存在预算账本与初始化请求不一致")
            return state
        first = _event(identity, "DECISION_RECORDED", stable_id("DBE", budget_id, "init"), data, 1, ZERO_HASH)
        _append_unlocked(path, [first])
        return _replay([first])


def record_decision(path: Path, *, dispatch_key: str, decision: str, role: str,
                    approved_profile: str, reason_code: str,
                    responsibility: str = "general", difficulty: str = "UNKNOWN",
                    risk_domain: str = "UNKNOWN", context_size: str = "UNKNOWN",
                    parent_reservation_id: str = "", prior_profile: str = "",
                    prior_result_ref: str = "") -> Dict[str, Any]:
    path = Path(path)
    dispatch_key = _identifier(dispatch_key, "dispatch_key")
    dispatch_ref = sha256_ref(dispatch_key)
    decision = str(decision or "").upper()
    role = normalize_role(role)
    reason_code = str(reason_code or "").upper()
    difficulty = str(difficulty or "UNKNOWN").upper()
    risk_domain = str(risk_domain or "UNKNOWN").upper()
    context_size = str(context_size or "UNKNOWN").upper()
    responsibility = _identifier(responsibility, "responsibility")
    if decision not in {"INLINE", "DELEGATE"} or reason_code not in REASONS:
        raise DelegationBudgetError("路由决策或原因码非法")
    if approved_profile not in PROFILE_WEIGHTS:
        raise DelegationBudgetError("批准派发档位非法")
    if difficulty not in DIFFICULTIES or risk_domain not in RISK_DOMAINS or context_size not in CONTEXT_SIZES:
        raise DelegationBudgetError("校准场景枚举非法")
    if decision == "INLINE" and reason_code != "INLINE_SUFFICIENT":
        raise DelegationBudgetError("INLINE 必须使用 INLINE_SUFFICIENT")
    if decision == "DELEGATE" and reason_code == "INLINE_SUFFICIENT":
        raise DelegationBudgetError("DELEGATE 不得使用 INLINE_SUFFICIENT")
    with OwnerTokenLock(path, timeout=1.5):
        records = _read_records_unlocked(path)
        state = _replay(records)
        if state["closed"] or state["violated"]:
            raise DelegationBudgetError("预算已关闭或已违规，拒绝新决策")
        if reason_code == "MISSING_EVIDENCE" and PROFILE_ORDER[approved_profile] > PROFILE_ORDER[state["default_dispatch_profile"]]:
            raise DelegationBudgetError("MISSING_EVIDENCE 不允许升级派发档位")
        if reason_code == "LOWER_TIER_INCONCLUSIVE":
            if prior_profile not in PROFILE_WEIGHTS or not prior_result_ref:
                raise DelegationBudgetError("逐级升级必须引用上一档结果")
            _sha_ref(prior_result_ref, "prior_result_ref")
            if PROFILE_ORDER[approved_profile] != PROFILE_ORDER[prior_profile] + 1:
                raise DelegationBudgetError("LOWER_TIER_INCONCLUSIVE 只允许逐级升级")
        elif prior_profile or prior_result_ref:
            raise DelegationBudgetError("仅逐级升级决策可携带上一档结果")
        if approved_profile == "terra-high" and reason_code not in {"SECURITY_OR_CONCURRENCY_RISK", "LOWER_TIER_INCONCLUSIVE"}:
            raise DelegationBudgetError("Terra High 仅允许高风险直达或逐级升级")
        depth = 1
        if parent_reservation_id:
            parent_reservation_id = _identifier(parent_reservation_id, "parent_reservation_id")
            parent = state["reservations"].get(parent_reservation_id)
            if not parent or parent["state"] not in {"RESERVED", "STARTED"}:
                raise DelegationBudgetError("父 reservation 不可用于嵌套派发")
            depth = int(parent["depth"]) + 1
        if depth > state["limits"]["max_depth"]:
            raise DelegationBudgetError("嵌套深度超过根任务预算")
        data = {
            "decision_kind": "dispatch", "dispatch_ref": dispatch_ref, "decision": decision,
            "role": role, "approved_profile": approved_profile, "reason_code": reason_code,
            "responsibility": responsibility, "difficulty": difficulty, "risk_domain": risk_domain,
            "context_size": context_size, "parent_reservation_id": parent_reservation_id,
            "depth": depth, "prior_profile": prior_profile, "prior_result_ref": prior_result_ref,
        }
        existing = state["decisions"].get(dispatch_ref)
        if existing:
            if existing != data:
                raise DelegationBudgetError("同一 dispatch key 的决策内容发生碰撞")
            return {"decision_id": stable_id("DBD", state["identity"]["budget_id"], dispatch_ref), **data}
        record = _event(state["identity"], "DECISION_RECORDED",
                        stable_id("DBD", state["identity"]["budget_id"], dispatch_ref),
                        data, len(records) + 1, records[-1]["record_hash"])
        _append_unlocked(path, [record])
        return {"decision_id": record["event_id"], **data}


def reserve_budget(path: Path, *, dispatch_key: str, host_dispatch_id: str,
                   approved_profile: str = "", approval_basis: str = "",
                   role: str = "") -> Dict[str, Any]:
    path = Path(path)
    dispatch_ref = sha256_ref(_identifier(dispatch_key, "dispatch_key"))
    host_ref = sha256_ref(_identifier(host_dispatch_id, "host_dispatch_id"))
    with OwnerTokenLock(path, timeout=1.5):
        records = _read_records_unlocked(path)
        state = _replay(records)
        if state["closed"] or state["violated"]:
            raise DelegationBudgetError("预算已关闭或已违规，拒绝派发")
        decision = state["decisions"].get(dispatch_ref)
        if not decision or decision["decision"] != "DELEGATE":
            raise DelegationBudgetError("缺少显式 DELEGATE permit")
        if role and normalize_role(role) != decision["role"]:
            raise DelegationBudgetError("派发角色与显式 permit 不一致")
        profile = approved_profile or decision["approved_profile"]
        basis = approval_basis or ("policy-default" if not approved_profile else "explicit-request")
        if profile != decision["approved_profile"] or basis not in {"policy-default", "explicit-request"}:
            raise DelegationBudgetError("批准派发档位与显式 permit 不一致")
        reservation_id = stable_id("DBR", state["identity"]["budget_id"], host_ref)
        existing = state["reservations"].get(reservation_id)
        expected = {
            "reservation_id": reservation_id, "dispatch_ref": dispatch_ref, "host_dispatch_ref": host_ref,
            "role": decision["role"], "approved_profile": profile, "approval_basis": basis,
            "units": PROFILE_WEIGHTS[profile], "parent_reservation_id": decision["parent_reservation_id"],
            "depth": decision["depth"], "association": "pretool-verified",
        }
        if existing:
            comparable = {key: existing.get(key) for key in expected}
            if comparable != expected:
                raise DelegationBudgetError("同一 host dispatch id 的预占输入发生碰撞")
            return {**expected, "idempotent": True}
        units = PROFILE_WEIGHTS[profile]
        role_usage = state["usage"]["by_role"][decision["role"]]
        role_limits = state["role_limits"][decision["role"]]
        if state["usage"]["units"] + units > state["limits"]["max_units"]:
            raise DelegationBudgetError("根任务加权单位预算不足")
        if state["usage"]["dispatches"] + 1 > state["limits"]["max_dispatches"]:
            raise DelegationBudgetError("根任务总派发数预算不足")
        if state["usage"]["active"] + 1 > state["limits"]["max_parallel"]:
            raise DelegationBudgetError("根任务并行预占已达上限")
        if role_usage["units"] + units > role_limits["max_units"] or role_usage["dispatches"] + 1 > role_limits["max_dispatches"]:
            raise DelegationBudgetError("角色预算不足")
        if profile == "terra-high" and state["usage"]["terra_high"] + 1 > state["limits"]["max_terra_high"]:
            raise DelegationBudgetError("Terra High 派发已达上限")
        record = _event(state["identity"], "BUDGET_RESERVED", stable_id("DBE", reservation_id, "reserved"),
                        expected, len(records) + 1, records[-1]["record_hash"])
        _append_unlocked(path, [record])
        return {**expected, "idempotent": False}


def mark_started(path: Path, *, reservation_id: str, agent_id: str) -> Dict[str, Any]:
    path = Path(path)
    reservation_id = _identifier(reservation_id, "reservation_id")
    agent_ref = sha256_ref(_identifier(agent_id, "agent_id"))
    with OwnerTokenLock(path, timeout=1.5):
        records = _read_records_unlocked(path)
        state = _replay(records)
        item = state["reservations"].get(reservation_id)
        if state["closed"]:
            raise DelegationBudgetError("预算已经关闭")
        if not item:
            raise DelegationBudgetError("找不到 reservation")
        if item["state"] in {"STARTED", "COMPLETED"}:
            if item["agent_ref"] != agent_ref:
                raise DelegationBudgetError("reservation 已绑定其他 Agent")
            return {"reservation_id": reservation_id, "state": item["state"], "idempotent": True}
        if item["state"] != "RESERVED":
            raise DelegationBudgetError("reservation 已释放，不能启动")
        data = {"reservation_id": reservation_id, "agent_ref": agent_ref,
                "association": "reservation-id"}
        start = _event(state["identity"], "AGENT_STARTED", stable_id("DBE", reservation_id, "started"),
                       data, len(records) + 1, records[-1]["record_hash"])
        _append_unlocked(path, [start])
        return {**data, "state": "STARTED", "violated": False, "idempotent": False}


def mark_completed(path: Path, *, reservation_id: str, outcome: str = "UNKNOWN") -> Dict[str, Any]:
    path = Path(path)
    reservation_id = _identifier(reservation_id, "reservation_id")
    outcome = str(outcome or "UNKNOWN").upper()
    if outcome not in {"PASS", "BLOCKED", "FAILED", "CANCELLED", "PARTIAL", "UNKNOWN"}:
        raise DelegationBudgetError("Agent outcome 非法")
    with OwnerTokenLock(path, timeout=1.5):
        records = _read_records_unlocked(path)
        state = _replay(records)
        item = state["reservations"].get(reservation_id)
        if state["closed"]:
            raise DelegationBudgetError("预算已经关闭")
        if not item:
            raise DelegationBudgetError("找不到 reservation")
        if item["state"] == "COMPLETED":
            if item.get("outcome") != outcome:
                raise DelegationBudgetError("完成结果重放内容不一致")
            return {"reservation_id": reservation_id, "state": "COMPLETED", "idempotent": True}
        if item["state"] != "STARTED":
            raise DelegationBudgetError("Agent 未启动，不能完成")
        data = {"reservation_id": reservation_id, "outcome": outcome}
        record = _event(state["identity"], "AGENT_COMPLETED", stable_id("DBE", reservation_id, "completed"),
                        data, len(records) + 1, records[-1]["record_hash"])
        _append_unlocked(path, [record])
        return {**data, "state": "COMPLETED", "idempotent": False}


def release_not_started(path: Path, *, reservation_id: str, proof_ref: str) -> Dict[str, Any]:
    path = Path(path)
    reservation_id = _identifier(reservation_id, "reservation_id")
    proof_ref = _sha_ref(proof_ref, "proof_ref")
    with OwnerTokenLock(path, timeout=1.5):
        records = _read_records_unlocked(path)
        state = _replay(records)
        item = state["reservations"].get(reservation_id)
        if state["closed"]:
            raise DelegationBudgetError("预算已经关闭")
        if not item:
            raise DelegationBudgetError("找不到 reservation")
        if item["state"] == "NOT_STARTED_RELEASED":
            return {"reservation_id": reservation_id, "state": item["state"], "idempotent": True}
        if item["state"] != "RESERVED":
            raise DelegationBudgetError("Agent 启动后不得退款")
        data = {"reservation_id": reservation_id, "proof_ref": proof_ref, "proof_kind": "host-confirmed-not-started"}
        record = _event(state["identity"], "NOT_STARTED_RELEASED", stable_id("DBE", reservation_id, "released"),
                        data, len(records) + 1, records[-1]["record_hash"])
        _append_unlocked(path, [record])
        return {**data, "state": "NOT_STARTED_RELEASED", "idempotent": False}


def close_budget(path: Path, *, conclusion: str) -> Dict[str, Any]:
    path = Path(path)
    conclusion = str(conclusion or "").upper()
    if conclusion not in {"PASS", "BLOCKED", "FAILED", "CANCELLED", "PARTIAL", "UNKNOWN"}:
        raise DelegationBudgetError("预算关闭结论非法")
    with OwnerTokenLock(path, timeout=1.5):
        records = _read_records_unlocked(path)
        state = _replay(records)
        if state["closed"]:
            return state
        data = {"conclusion": conclusion, "association_complete": state["association_complete"],
                "budget_pass": not state["violated"]}
        record = _event(state["identity"], "TASK_BUDGET_CLOSED", stable_id("DBE", state["identity"]["budget_id"], "closed"),
                        data, len(records) + 1, records[-1]["record_hash"])
        _append_unlocked(path, [record])
        return _replay(records + [record])


def reservation_for_host_dispatch(path: Path, host_dispatch_id: str) -> Optional[str]:
    state = read_budget(path)
    host_ref = sha256_ref(_identifier(host_dispatch_id, "host_dispatch_id"))
    for reservation_id, item in state["reservations"].items():
        if item.get("host_dispatch_ref") == host_ref:
            return reservation_id
    return None
