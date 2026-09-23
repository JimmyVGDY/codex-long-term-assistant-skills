"""中文：DelegationBudget V3、冻结 V2 续写与只读 V1 兼容校验。

English: DelegationBudget V3, the root-task weighted budget ledger shared by
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
from .dispatch_policy import (
    CURRENT_POLICY_ID, LEGACY_POLICY_ID, DispatchPolicyError, allowed_profiles,
    digest as policy_value_digest, is_premium, policy, policy_digest, profile_weights,
    role_for, validate_scorecard,
)
from .dispatch_context import ROOT_BINDING_FIELDS

SCHEMA_VERSION = "3.0"
V2_SCHEMA_VERSION = "2.0"
LEGACY_SCHEMA_VERSION = "1.0"
ZERO_HASH = "0" * 64
ROLES = {"reviewer", "explorer", "worker"}
# 中文：兼容导出是冻结 V2 契约，V3 必须使用账本固定的策略。
# English: Compatibility exports remain V2; V3 resolves its own pinned contract.
PROFILES = tuple(policy(LEGACY_POLICY_ID)["legacy_order"])
PROFILE_WEIGHTS = profile_weights(LEGACY_POLICY_ID)
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
    "NOT_STARTED_RELEASED", "BUDGET_VIOLATED", "TASK_BUDGET_CLOSED", "REVIEW_ATTEMPT_BOUND",
    "HOST_DISPATCH_RECEIPT", "HOST_AGENT_OBSERVED",
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
V3_EVENT_DATA_KEYS = {key: set(value) for key, value in EVENT_DATA_KEYS.items()}
V3_EVENT_DATA_KEYS[("DECISION_RECORDED", "budget-initialized")].update({
    "policy_id", "policy_digest", "review_extension", "root_binding",
})
V3_EVENT_DATA_KEYS[("DECISION_RECORDED", "dispatch")].update({
    "selection_scorecard", "review_assignment", "transition",
})
V3_EVENT_DATA_KEYS[("REVIEW_ATTEMPT_BOUND", "")] = {"dispatch_ref", "review_state_ref", "assignment_ref"}
V3_EVENT_DATA_KEYS[("HOST_DISPATCH_RECEIPT", "")] = {
    "reservation_id", "host_dispatch_ref", "agent_ref", "disposition", "proof_ref",
}
V3_EVENT_DATA_KEYS[("HOST_AGENT_OBSERVED", "")] = {"agent_ref", "phase", "outcome"}
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
NATIVE_DISPATCH_PREFIX = "CP_REVIEW_DISPATCH/1 "
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


def _validate_limits(value: Mapping[str, Any], *, matrix: bool = False) -> Dict[str, int]:
    required = {"max_units", "max_dispatches", "max_parallel", "max_depth", "max_terra_high"}
    if matrix:
        required |= {"max_base_units", "max_premium_units", "max_premium_dispatches",
                     "max_premium_parallel", "max_astra_high"}
    if set(value) != required:
        raise DelegationBudgetError("预算 limits 字段不完整或包含未知字段")
    result = {
        "max_units": _positive(value["max_units"], "max_units"),
        "max_dispatches": _positive(value["max_dispatches"], "max_dispatches"),
        "max_parallel": _positive(value["max_parallel"], "max_parallel"),
        "max_depth": _positive(value["max_depth"], "max_depth"),
        "max_terra_high": _positive(value["max_terra_high"], "max_terra_high", allow_zero=True),
    }
    if matrix:
        result.update({key: _positive(value[key], key, allow_zero=True) for key in required - set(result)})
    return result


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


def _event(identity: Mapping[str, str], event_type: str, event_id: str, data: Mapping[str, Any], sequence: int, previous: str,
           *, schema_version: str = SCHEMA_VERSION) -> Dict[str, Any]:
    if event_type not in EVENT_TYPES:
        raise DelegationBudgetError("未知预算事件")
    unsigned = {
        "schema_version": schema_version,
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


def _state_event(state: Mapping[str, Any], event_type: str, event_id: str,
                 data: Mapping[str, Any], sequence: int, previous: str) -> Dict[str, Any]:
    return _event(state["identity"], event_type, event_id, data, sequence, previous,
                  schema_version=state["schema_version"])


def _validate_event_data(schema_version: str, event_type: str, data: Mapping[str, Any]) -> None:
    decision_kind = str(data.get("decision_kind") or "") if event_type == "DECISION_RECORDED" else ""
    contracts = (V3_EVENT_DATA_KEYS if schema_version == SCHEMA_VERSION else
                 EVENT_DATA_KEYS if schema_version == V2_SCHEMA_VERSION else LEGACY_EVENT_DATA_KEYS)
    expected = contracts.get((event_type, decision_kind))
    if schema_version == SCHEMA_VERSION and event_type == "REVIEW_ATTEMPT_BOUND" and "native_dispatch_ref" in data:
        expected = expected | {"native_dispatch_ref"}
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
            if record["schema_version"] not in {SCHEMA_VERSION, V2_SCHEMA_VERSION, LEGACY_SCHEMA_VERSION} or record["event_type"] not in EVENT_TYPES:
                raise DelegationBudgetError("预算账本 schema 或事件类型未知")
            if ledger_schema is None:
                ledger_schema = str(record["schema_version"])
            elif record["schema_version"] != ledger_schema:
                raise DelegationBudgetError("同一预算账本禁止混用格式版本")
            if record["schema_version"] != LEGACY_SCHEMA_VERSION and record["event_type"] == "BUDGET_VIOLATED":
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


def matrix_limits(budget_class: str, review_extension: bool, policy_id: str = CURRENT_POLICY_ID) -> Dict[str, int]:
    contract = policy(policy_id)
    if budget_class not in contract["budget_classes"] or type(review_extension) is not bool:
        raise DelegationBudgetError("预算类别或扩展标记非法")
    if review_extension and budget_class == "LIGHT":
        raise DelegationBudgetError("LIGHT 不允许复审预算扩展")
    result = dict(contract["budget_classes"][budget_class])
    base = result["max_units"]
    extra = contract["review_extension_units"] if review_extension else 0
    result.update(max_units=base + extra, max_base_units=base,
                  max_premium_units=extra if review_extension else base,
                  max_premium_dispatches=contract["premium_limits"]["max_dispatches"],
                  max_premium_parallel=contract["premium_limits"]["max_parallel"],
                  max_astra_high=contract["premium_limits"]["max_astra_high"])
    return result


def _matrix_root(value: Mapping[str, Any]) -> Dict[str, Any]:
    if not isinstance(value, Mapping) or set(value) != ROOT_BINDING_FIELDS \
            or value.get("schema_version") != "dispatch-root/1":
        raise DelegationBudgetError("V3 缺少完整根任务绑定")
    for key in ("envelope_identity_ref", "host_session_ref"):
        _sha_ref(value[key], key)
    _sha_ref("sha256:" + str(value["profile_binding_sha256"]), "profile_binding_sha256")
    try:
        contract = policy(value["reviewer_policy_id"], value["reviewer_policy_digest"])
    except DispatchPolicyError as exc:
        raise DelegationBudgetError(str(exc)) from exc
    if "scoring" not in contract:
        raise DelegationBudgetError("旧任务信封保持旧策略；V3 需要新评分策略任务")
    if any(not isinstance(value[key], str) or not value[key] for key in ("repo_path", "profile_path")):
        raise DelegationBudgetError("根任务项目路径缺失")
    return dict(value)


def _matrix_decision(data: Mapping[str, Any], identity: Mapping[str, str],
                     decisions: Mapping[str, Any], reservations: Mapping[str, Any], policy_id: str) -> None:
    """中文：统一校验写入和回放；English: one contract for issuance and replay."""
    role, profile = data["role"], data["approved_profile"]
    if data["decision"] == "INLINE":
        if data["selection_scorecard"] or data["review_assignment"] or data["transition"] or profile != "luna-low":
            raise DelegationBudgetError("INLINE 不创建评分派发或复审尝试")
        return
    if role != "reviewer":
        if profile not in allowed_profiles(role, policy_id) or data["selection_scorecard"] \
                or data["review_assignment"] or data["transition"]:
            raise DelegationBudgetError("普通角色不得扩展复审模型或伪装复审绑定")
        return
    assignment = data["review_assignment"]
    fields = {"reviewer", "agent_type", "boundary_id", "phase", "round", "packet_sha256", "acceptable_profiles"}
    if not isinstance(assignment, dict) or set(assignment) != fields:
        raise DelegationBudgetError("V3 Reviewer 派发绑定字段非法")
    try:
        if role_for(assignment["agent_type"], policy_id=policy_id) != "reviewer":
            raise DelegationBudgetError("Reviewer 必须使用登记角色")
        selection = validate_scorecard(data["selection_scorecard"])
        permitted = allowed_profiles(assignment["agent_type"], policy_id)
    except (DispatchPolicyError, TypeError) as exc:
        raise DelegationBudgetError(str(exc)) from exc
    _identifier(assignment["reviewer"], "reviewer")
    _identifier(assignment["boundary_id"], "boundary_id")
    if assignment["phase"] not in {"pre", "post"} or type(assignment["round"]) is not int or assignment["round"] < 1:
        raise DelegationBudgetError("Reviewer 阶段轮次非法")
    _sha_ref("sha256:" + str(assignment["packet_sha256"]), "packet_sha256")
    acceptable = assignment["acceptable_profiles"]
    if not isinstance(acceptable, list) or not acceptable or any(not isinstance(item, str) for item in acceptable) \
            or len(acceptable) != len(set(acceptable)) or not set(acceptable).issubset(permitted) \
            or not set(acceptable).issubset(selection["requirement_profiles"]) or profile not in acceptable:
        raise DelegationBudgetError("Reviewer 可接受组合集合非法")
    if selection["policy_id"] != policy_id or selection["policy_digest"] != policy_digest(policy_id) \
            or selection["approved_profile"] != profile or selection["agent_type"] != assignment["agent_type"] \
            or any(selection["context"][key] != identity[key] for key in ("task_id", "project_id", "repo_fingerprint")) \
            or selection["context"]["packet_sha256"] != assignment["packet_sha256"]:
        raise DelegationBudgetError("评分与派发或根任务身份不一致")
    if data["prior_profile"] or data["prior_result_ref"]:
        raise DelegationBudgetError("V3 Reviewer 不接受旧线性升级字段")
    transition = data["transition"]
    if transition:
        if not isinstance(transition, dict) or set(transition) != {"kind", "reason_code", "prior_dispatch_ref", "prior_result_ref"}:
            raise DelegationBudgetError("Reviewer 切换字段非法")
        if transition["kind"] not in {"effort-increase", "model-switch", "fallback"} \
                or transition["reason_code"] not in {"LOWER_TIER_INCONCLUSIVE", "EVIDENCE_CONFLICT", "HOST_UNAVAILABLE"}:
            raise DelegationBudgetError("Reviewer 切换类型或原因非法")
        previous_ref = _sha_ref(transition["prior_dispatch_ref"], "prior_dispatch_ref")
        result_ref = _sha_ref(transition["prior_result_ref"], "prior_result_ref")
        previous = decisions.get(previous_ref)
        attempts = [item for item in reservations.values() if item["dispatch_ref"] == previous_ref]
        if not previous or previous.get("role") != "reviewer" or len(attempts) != 1 \
                or attempts[0]["state"] not in {"COMPLETED", "NOT_STARTED_RELEASED"}:
            raise DelegationBudgetError("Reviewer 切换缺少终态前次尝试")
        proven = any(proof["prior_attempt_ref"] == previous_ref and proof["prior_result_ref"] == result_ref
                     and proof["status"] == "valid" and proof["context"] == selection["context"]
                     for proof in selection["proofs"].values())
        if not proven:
            raise DelegationBudgetError("Reviewer 切换缺少匹配结果来源")
        old_spec = policy(policy_id)["profiles"][previous["approved_profile"]]
        new_spec = policy(policy_id)["profiles"][profile]
        if transition["kind"] == "effort-increase":
            efforts = ("low", "medium", "high")
            if old_spec["family"] != new_spec["family"] or efforts.index(new_spec["effort"]) <= efforts.index(old_spec["effort"]):
                raise DelegationBudgetError("同模型推理强度升级非法")
        if transition["kind"] == "model-switch" and old_spec["family"] == new_spec["family"]:
            raise DelegationBudgetError("跨模型切换需要不同模型系列")
        if transition["kind"] == "fallback" and profile not in previous["review_assignment"]["acceptable_profiles"]:
            raise DelegationBudgetError("回退组合未在前次批准集合内")


def _matrix_usage(reservations: Mapping[str, Any], review_extension: bool, policy_id: str) -> Dict[str, int]:
    attempts = list(reservations.values())
    charged = [item for item in attempts if item["state"] != "NOT_STARTED_RELEASED"]
    premium = [item for item in attempts if is_premium(item["approved_profile"], policy_id)]
    premium_units = sum(item["charged_units"] for item in premium)
    nonpremium_units = sum(item["charged_units"] for item in charged if not is_premium(item["approved_profile"], policy_id))
    return {
        "nonpremium_units": nonpremium_units, "premium_units": premium_units,
        "base_units": nonpremium_units + (0 if review_extension else premium_units),
        "extension_units": premium_units if review_extension else 0,
        "premium_dispatches": len(premium),
        "premium_active": sum(item["state"] in {"RESERVED", "STARTED"} for item in premium),
        "astra_high": sum(item["approved_profile"] == "astra-high" for item in premium),
        "attempts": len(attempts),
    }


def _enforce_matrix_capacity(reservations: Mapping[str, Any], limits: Mapping[str, int],
                             role_limits: Mapping[str, Any], review_extension: bool, policy_id: str) -> None:
    usage = _matrix_usage(reservations, review_extension, policy_id)
    attempts = list(reservations.values())
    comparisons = {
        "max_units": sum(item["charged_units"] for item in attempts),
        "max_dispatches": usage["attempts"],
        "max_parallel": sum(item["state"] in {"RESERVED", "STARTED"} for item in attempts),
        "max_base_units": usage["base_units"], "max_premium_units": usage["premium_units"],
        "max_premium_dispatches": usage["premium_dispatches"], "max_premium_parallel": usage["premium_active"],
        "max_astra_high": usage["astra_high"],
        "max_terra_high": sum(item["approved_profile"] == "terra-high" for item in attempts),
    }
    if any(value > limits[key] for key, value in comparisons.items()):
        raise DelegationBudgetError("根任务预算、原始额度或模型家族上限不足")
    for role, allowed in role_limits.items():
        items = [item for item in attempts if item["role"] == role]
        if sum(item["charged_units"] for item in items) > allowed["max_units"] or len(items) > allowed["max_dispatches"]:
            raise DelegationBudgetError("角色累计预算不足")


def _receipt_proof(identity: Mapping[str, str], host_ref: str, agent_ref: str, disposition: str) -> str:
    return policy_value_digest({"source": "native-post-tool", "identity": dict(identity),
                                "host_dispatch_ref": host_ref, "agent_ref": agent_ref, "disposition": disposition})


def _apply_host_associations(reservations: Mapping[str, Any], receipts: Mapping[str, Any],
                              observations: Mapping[str, Any]) -> None:
    for rid, receipt in receipts.items():
        if receipt["disposition"] != "created":
            if reservations[rid]["state"] not in {"RESERVED", "NOT_STARTED_RELEASED"}:
                raise DelegationBudgetError("未启动回执与生命周期冲突")
            continue
        item = reservations[rid]
        if item["state"] == "NOT_STARTED_RELEASED":
            raise DelegationBudgetError("已退款尝试出现宿主创建回执")
        agent_ref = receipt["agent_ref"]
        observed = observations.get(agent_ref, {})
        if item.get("agent_ref") and item["agent_ref"] != agent_ref:
            raise DelegationBudgetError("宿主回执与已绑定 Agent 不一致")
        if "start" not in observed:
            continue
        item["agent_ref"] = agent_ref
        if item["state"] == "RESERVED":
            item["state"] = "STARTED"
        if "stop" in observed:
            outcome = observed["stop"]["outcome"]
            if item["state"] == "COMPLETED" and item.get("outcome") != outcome:
                raise DelegationBudgetError("宿主终态与已记录结果冲突")
            item["state"] = "COMPLETED"
            item["outcome"] = outcome
            item.setdefault("completion_ref", observed["stop"]["event_ref"])
            if not item["completion_ref"]:
                item["completion_ref"] = observed["stop"]["event_ref"]


def _matrix_association_complete(reservations: Mapping[str, Any], receipts: Mapping[str, Any],
                                 observations: Mapping[str, Any]) -> bool:
    for rid, item in reservations.items():
        receipt = receipts.get(rid)
        if not receipt:
            return False
        if item["state"] == "NOT_STARTED_RELEASED":
            if receipt["disposition"] != "not-started":
                return False
            continue
        observed = observations.get(receipt["agent_ref"], {})
        if item["state"] != "COMPLETED" or receipt["disposition"] != "created" \
                or item["agent_ref"] != receipt["agent_ref"] or "start" not in observed or "stop" not in observed \
                or item["completion_ref"] != observed["stop"]["event_ref"] \
                or item["outcome"] != observed["stop"]["outcome"]:
            return False
    return True


def _replay(records: List[Dict[str, Any]]) -> Dict[str, Any]:
    if not records or records[0]["event_type"] != "DECISION_RECORDED" or records[0]["data"].get("decision_kind") != "budget-initialized":
        raise DelegationBudgetError("预算账本缺少初始化事件")
    schema = records[0].get("schema_version")
    if schema not in {V2_SCHEMA_VERSION, SCHEMA_VERSION}:
        raise DelegationBudgetError("DelegationBudget V1 为只读；请初始化独立 V2 账本")
    init = records[0]["data"]
    matrix = schema == SCHEMA_VERSION
    policy_id = init.get("policy_id", LEGACY_POLICY_ID) if matrix else LEGACY_POLICY_ID
    try:
        contract = policy(policy_id, init.get("policy_digest", "") if matrix else "")
    except DispatchPolicyError as exc:
        raise DelegationBudgetError(str(exc)) from exc
    if matrix and ("scoring" not in contract or not init.get("policy_digest")):
        raise DelegationBudgetError("V3 策略身份缺失")
    weights = {name: spec["units"] for name, spec in contract["profiles"].items()}
    limits = _validate_limits(init.get("limits") or {}, matrix=matrix)
    role_limits = _validate_role_limits(init.get("role_limits") or {}, limits)
    default_profile = str(init.get("default_dispatch_profile") or "")
    budget_class = str(init.get("budget_class") or "")
    if default_profile not in contract["role_profiles"]["worker"] or budget_class not in contract["budget_classes"]:
        raise DelegationBudgetError("初始化预算档位非法")
    expected_limits = matrix_limits(budget_class, init["review_extension"], policy_id) if matrix else contract["budget_classes"][budget_class]
    if init["limits"] != expected_limits \
            or init["cost_formula_version"] != contract["cost_formula_version"] \
            or init["association_mode"] != "explicit-dispatch-permit":
        raise DelegationBudgetError("初始化预算契约非法")
    if matrix:
        _matrix_root(init["root_binding"])
        if init["root_binding"]["reviewer_policy_id"] != policy_id or init["root_binding"]["reviewer_policy_digest"] != init["policy_digest"]:
            raise DelegationBudgetError("预算策略与任务信封固定策略不一致")
        for role in ("worker", "explorer"):
            if role_limits[role]["max_units"] > limits["max_base_units"]:
                raise DelegationBudgetError("复审扩展不得扩大普通角色额度")
    decisions: Dict[str, Dict[str, Any]] = {}
    reservations: Dict[str, Dict[str, Any]] = {}
    review_claims: Dict[str, Dict[str, Any]] = {}
    host_receipts: Dict[str, Dict[str, Any]] = {}
    host_agents: Dict[str, Dict[str, Any]] = {}
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
            if decision not in {"INLINE", "DELEGATE"} or profile not in weights or reason not in REASONS:
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
            if matrix:
                _matrix_decision(data, _identity(records), decisions, reservations, policy_id)
            if reason == "LOWER_TIER_INCONCLUSIVE" and not (matrix and role == "reviewer"):
                if prior_profile not in PROFILE_WEIGHTS or PROFILE_ORDER[profile] != PROFILE_ORDER[prior_profile] + 1:
                    raise DelegationBudgetError("账本逐级升级关系非法")
                _sha_ref(prior_result_ref, "prior_result_ref")
            elif (prior_profile or prior_result_ref) and not (matrix and role == "reviewer"):
                raise DelegationBudgetError("账本非升级决策携带上一档结果")
            decisions[ref] = {**dict(data), "role": role, "depth": depth}
        elif event_type == "REVIEW_ATTEMPT_BOUND":
            ref = _sha_ref(data["dispatch_ref"], "dispatch_ref")
            decision = decisions.get(ref)
            if not matrix or not decision or decision["role"] != "reviewer" or decision["decision"] != "DELEGATE" \
                    or ref in review_claims or data["assignment_ref"] != policy_value_digest(decision["review_assignment"]):
                raise DelegationBudgetError("Reviewer 尝试绑定非法或重复")
            _sha_ref(data["review_state_ref"], "review_state_ref")
            if "native_dispatch_ref" in data:
                native_ref = _sha_ref(data["native_dispatch_ref"], "native_dispatch_ref")
                if any(claim.get("native_dispatch_ref") == native_ref for claim in review_claims.values()):
                    raise DelegationBudgetError("NATIVE_REVIEW_REFERENCE_REUSED")
            slot_keys = ("reviewer", "boundary_id", "phase", "round", "packet_sha256")
            for claimed_ref, claim in review_claims.items():
                previous_assignment = decisions[claimed_ref]["review_assignment"]
                if claim["review_state_ref"] == data["review_state_ref"] and all(
                        previous_assignment[key] == decision["review_assignment"][key] for key in slot_keys):
                    raise DelegationBudgetError("同一复审槽位存在重复许可")
            review_claims[ref] = dict(data)
        elif event_type == "BUDGET_RESERVED":
            rid = _identifier(data.get("reservation_id"), "reservation_id")
            if rid in reservations:
                raise DelegationBudgetError("reservation_id 重复")
            if data.get("dispatch_ref") not in decisions:
                raise DelegationBudgetError("预占缺少对应 decision")
            role = normalize_role(data.get("role"))
            profile = str(data.get("approved_profile") or "")
            if profile not in weights:
                raise DelegationBudgetError("预占模型档位非法")
            decision = decisions[data["dispatch_ref"]]
            if matrix and role == "reviewer" and data["dispatch_ref"] not in review_claims:
                raise DelegationBudgetError("Reviewer permit 尚未绑定复审状态")
            if decision["decision"] != "DELEGATE" or role != decision["role"] \
                    or profile != decision["approved_profile"] \
                    or data["units"] != weights[profile] \
                    or data["parent_reservation_id"] != decision["parent_reservation_id"] \
                    or data["depth"] != decision["depth"] \
                    or data["approval_basis"] not in {"policy-default", "explicit-request"} \
                    or data["association"] != "pretool-verified":
                raise DelegationBudgetError("预占与显式 decision 不一致")
            if matrix and is_premium(profile, policy_id) and data["approval_basis"] != "explicit-request":
                raise DelegationBudgetError("新增模型组合必须显式请求")
            _sha_ref(data.get("host_dispatch_ref"), "host_dispatch_ref")
            if matrix and any(item["dispatch_ref"] == data["dispatch_ref"] for item in reservations.values()):
                raise DelegationBudgetError("单次派发许可已被消费")
            if matrix and any(item["host_dispatch_ref"] == data["host_dispatch_ref"] for item in reservations.values()):
                raise DelegationBudgetError("V3_HOST_CALL_ALREADY_BOUND")
            reservations[rid] = {
                **dict(data), "role": role, "charged_units": weights[profile],
                "state": "RESERVED", "agent_ref": "", "completion_ref": "",
            }
            if matrix:
                _enforce_matrix_capacity(reservations, limits, role_limits, init["review_extension"], policy_id)
        elif event_type == "HOST_DISPATCH_RECEIPT":
            rid = _identifier(data["reservation_id"], "reservation_id")
            item = reservations.get(rid)
            agent_ref = _sha_ref(data["agent_ref"], "agent_ref", optional=True)
            disposition = data["disposition"]
            if not matrix or not item or rid in host_receipts or data["host_dispatch_ref"] != item["host_dispatch_ref"] \
                    or disposition not in {"created", "not-started"} or bool(agent_ref) != (disposition == "created"):
                raise DelegationBudgetError("宿主派发回执字段或关联非法")
            if data["proof_ref"] != _receipt_proof(_identity(records), data["host_dispatch_ref"], agent_ref, disposition):
                raise DelegationBudgetError("宿主回执摘要不匹配")
            if disposition == "not-started" and item["state"] != "RESERVED":
                raise DelegationBudgetError("已启动尝试不能登记未启动回执")
            if agent_ref and any(value["agent_ref"] == agent_ref for value in host_receipts.values()):
                raise DelegationBudgetError("同一宿主 Agent 不能归属两个派发")
            host_receipts[rid] = dict(data)
        elif event_type == "HOST_AGENT_OBSERVED":
            agent_ref = _sha_ref(data["agent_ref"], "agent_ref")
            phase = data["phase"]
            outcome = data["outcome"]
            if not matrix or phase not in {"start", "stop"} or outcome not in {"PASS", "BLOCKED", "FAILED", "CANCELLED", "PARTIAL", "UNKNOWN"} \
                    or (phase == "start" and outcome != "UNKNOWN"):
                raise DelegationBudgetError("宿主 Agent 生命周期回执非法")
            if len(host_agents) >= limits["max_dispatches"] * 2 and agent_ref not in host_agents:
                raise DelegationBudgetError("未关联生命周期回执达到有界上限")
            agent = host_agents.setdefault(agent_ref, {})
            if phase in agent:
                raise DelegationBudgetError("宿主生命周期事件重复")
            agent[phase] = {"outcome": outcome, "event_ref": "sha256:" + record["record_hash"]}
        elif event_type == "AGENT_STARTED":
            if matrix:
                raise DelegationBudgetError("V3_LIFECYCLE_REQUIRES_HOST_RECEIPTS")
            rid = _identifier(data.get("reservation_id"), "reservation_id")
            item = reservations.get(rid)
            if not item or item["state"] != "RESERVED":
                raise DelegationBudgetError("AGENT_STARTED 状态转换非法")
            item["state"] = "STARTED"
            item["agent_ref"] = _sha_ref(data.get("agent_ref"), "agent_ref")
            if data.get("association") != "reservation-id":
                raise DelegationBudgetError("启动关联字段非法")
        elif event_type == "AGENT_COMPLETED":
            if matrix:
                raise DelegationBudgetError("V3_LIFECYCLE_REQUIRES_HOST_RECEIPTS")
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
            if matrix:
                receipt = host_receipts.get(rid)
                if not receipt or receipt["disposition"] != "not-started" or receipt["proof_ref"] != data["proof_ref"]:
                    raise DelegationBudgetError("V3 退款缺少匹配的宿主未启动回执")
            item["state"] = "NOT_STARTED_RELEASED"
            item["charged_units"] = 0
        elif event_type == "TASK_BUDGET_CLOSED":
            if closed:
                raise DelegationBudgetError("预算已经关闭")
            if data.get("conclusion") not in {"PASS", "BLOCKED", "FAILED", "CANCELLED", "PARTIAL", "UNKNOWN"} \
                    or not isinstance(data.get("association_complete"), bool) \
                    or not isinstance(data.get("budget_pass"), bool):
                raise DelegationBudgetError("预算关闭事件非法")
            expected_association = (_matrix_association_complete(reservations, host_receipts, host_agents) if matrix else
                                    all(item["state"] != "RESERVED" for item in reservations.values()))
            expected_pass = not violations and (expected_association or not matrix)
            if data["association_complete"] != expected_association or data["budget_pass"] != expected_pass:
                raise DelegationBudgetError("预算关闭快照与账本状态不一致")
            closed = True
        if matrix:
            _apply_host_associations(reservations, host_receipts, host_agents)
    charged = [item for item in reservations.values() if item["state"] != "NOT_STARTED_RELEASED"]
    active = [item for item in charged if item["state"] in {"RESERVED", "STARTED"}]
    counted = list(reservations.values()) if matrix else charged
    role_usage = {
        role: {
            "units": sum(item["charged_units"] for item in charged if item["role"] == role),
            "dispatches": sum(1 for item in counted if item["role"] == role),
            "active": sum(1 for item in active if item["role"] == role),
        }
        for role in sorted(ROLES)
    }
    profile_usage = {profile: sum(1 for item in counted if item["approved_profile"] == profile) for profile in weights}
    used_units = sum(item["charged_units"] for item in charged)
    violated = bool(violations) or used_units > limits["max_units"]
    return {
        "identity": _identity(records), "budget_class": budget_class,
        "schema_version": schema, "read_only": False,
        **({"policy_id": policy_id, "policy_digest": policy_digest(policy_id),
            "cost_formula_version": contract["cost_formula_version"],
            "review_extension": init["review_extension"], "root_binding": init["root_binding"],
            "review_claims": review_claims, "host_receipts": host_receipts, "host_agents": host_agents} if matrix else {}),
        "default_dispatch_profile": default_profile, "limits": limits, "role_limits": role_limits,
        "decisions": decisions, "reservations": reservations, "violations": violations,
        "usage": {"units": used_units, "dispatches": len(counted), "active": len(active),
                  "terra_high": sum(1 for item in charged if item["approved_profile"] == "terra-high"),
                  "by_role": role_usage, "by_approved_profile": profile_usage,
                  **(_matrix_usage(reservations, init["review_extension"], policy_id) if matrix else {})},
        "remaining_units": max(0, limits["max_units"] - used_units),
        "violated": violated, "closed": closed,
        "association_complete": (_matrix_association_complete(reservations, host_receipts, host_agents) if matrix else
                                 all(item["state"] != "RESERVED" for item in charged)),
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
        if path.is_file():
            with path.open("rb") as stream:
                first_line = stream.readline(8_388_609)
            if len(first_line) > 8_388_608:
                raise DelegationBudgetError("预算首记录超过有界读取上限")
            try:
                header = json.loads(first_line) if first_line.strip() else {}
            except (ValueError, UnicodeError):
                header = {}
            if isinstance(header, dict) and header.get("schema_version") == "4.0":
                from .budget_v4 import _read_events, replay
                return replay(_read_events(path))
        records = _read_records_unlocked(path)
        if records and records[0].get("schema_version") == LEGACY_SCHEMA_VERSION:
            return _project_legacy_budget(records)
        return _replay(records)


def initialize_budget(path: Path, *, budget_id: str, task_id: str, project_id: str,
                      repo_fingerprint: str, budget_class: str,
                      default_dispatch_profile: str,
                      role_limits: Optional[Mapping[str, Any]] = None,
                      policy_id: str = LEGACY_POLICY_ID, review_extension: bool = False,
                      root_binding: Optional[Mapping[str, Any]] = None) -> Dict[str, Any]:
    """中文：无 policy_id 的旧 Python 调用保留 V2，新入口显式指定当前策略。

    English: Preserve the V2 Python call contract; new task entry points name the current policy.
    """
    path = Path(path)
    identity = {
        "budget_id": _identifier(budget_id, "budget_id"),
        "task_id": _identifier(task_id, "task_id"),
        "project_id": _identifier(project_id, "project_id"),
        "repo_fingerprint": _sha_ref(repo_fingerprint, "repo_fingerprint"),
    }
    try:
        contract = policy(policy_id)
    except DispatchPolicyError as exc:
        raise DelegationBudgetError(str(exc)) from exc
    matrix = policy_id != LEGACY_POLICY_ID
    schema = SCHEMA_VERSION if matrix else V2_SCHEMA_VERSION
    if budget_class not in contract["budget_classes"] or default_dispatch_profile not in contract["role_profiles"]["worker"]:
        raise DelegationBudgetError("预算或默认派发档位非法")
    if not matrix and (review_extension or root_binding):
        raise DelegationBudgetError("V2 不接受新策略扩展或根绑定字段")
    limits = matrix_limits(budget_class, review_extension, policy_id) if matrix else dict(contract["budget_classes"][budget_class])
    defaults = _default_role_limits(limits)
    if matrix:
        for role in ("worker", "explorer"):
            defaults[role]["max_units"] = limits["max_base_units"]
    roles = _validate_role_limits(role_limits or defaults, limits)
    data = {
        "decision_kind": "budget-initialized", "budget_class": budget_class,
        "default_dispatch_profile": default_dispatch_profile, "limits": limits,
        "role_limits": roles, "cost_formula_version": contract["cost_formula_version"],
        "association_mode": "explicit-dispatch-permit",
    }
    if matrix:
        data.update(policy_id=policy_id, policy_digest=policy_digest(policy_id),
                    review_extension=review_extension, root_binding=_matrix_root(root_binding or {}))
    with OwnerTokenLock(path, timeout=1.5):
        existing = _read_records_unlocked(path)
        if existing:
            state = _replay(existing)
            if state["identity"] != identity or existing[0]["data"] != data:
                raise DelegationBudgetError("已存在预算账本与初始化请求不一致")
            return state
        first = _event(identity, "DECISION_RECORDED", stable_id("DBE", budget_id, "init"), data, 1, ZERO_HASH,
                       schema_version=schema)
        _replay([first])
        _append_unlocked(path, [first])
        return _replay([first])


def record_decision(path: Path, *, dispatch_key: str, decision: str, role: str,
                    approved_profile: str, reason_code: str,
                    responsibility: str = "general", difficulty: str = "UNKNOWN",
                    risk_domain: str = "UNKNOWN", context_size: str = "UNKNOWN",
                    parent_reservation_id: str = "", prior_profile: str = "",
                    prior_result_ref: str = "", selection_scorecard: Optional[Mapping[str, Any]] = None,
                    review_assignment: Optional[Mapping[str, Any]] = None,
                    transition: Optional[Mapping[str, Any]] = None) -> Dict[str, Any]:
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
    if approved_profile not in profile_weights(CURRENT_POLICY_ID):
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
        matrix = state["schema_version"] == SCHEMA_VERSION
        weights = profile_weights(state.get("policy_id", LEGACY_POLICY_ID))
        if approved_profile not in weights:
            raise DelegationBudgetError("批准档位不属于账本固定策略")
        if not matrix and (selection_scorecard or review_assignment or transition):
            raise DelegationBudgetError("V2 不接受 V3 评分或派发字段")
        if state["closed"] or state["violated"]:
            raise DelegationBudgetError("预算已关闭或已违规，拒绝新决策")
        if reason_code == "MISSING_EVIDENCE" and weights[approved_profile] > weights[state["default_dispatch_profile"]]:
            raise DelegationBudgetError("MISSING_EVIDENCE 不允许升级派发档位")
        if reason_code == "LOWER_TIER_INCONCLUSIVE" and not (matrix and role == "reviewer"):
            if prior_profile not in PROFILE_WEIGHTS or not prior_result_ref:
                raise DelegationBudgetError("逐级升级必须引用上一档结果")
            _sha_ref(prior_result_ref, "prior_result_ref")
            if PROFILE_ORDER[approved_profile] != PROFILE_ORDER[prior_profile] + 1:
                raise DelegationBudgetError("LOWER_TIER_INCONCLUSIVE 只允许逐级升级")
        elif (prior_profile or prior_result_ref) and not (matrix and role == "reviewer"):
            raise DelegationBudgetError("仅逐级升级决策可携带上一档结果")
        if approved_profile == "terra-high" and not (matrix and role == "reviewer") \
                and reason_code not in {"SECURITY_OR_CONCURRENCY_RISK", "LOWER_TIER_INCONCLUSIVE"}:
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
        if matrix:
            data.update(selection_scorecard=dict(selection_scorecard or {}),
                        review_assignment=dict(review_assignment or {}), transition=dict(transition or {}))
            _matrix_decision(data, state["identity"], state["decisions"], state["reservations"], state["policy_id"])
        existing = state["decisions"].get(dispatch_ref)
        if existing:
            if existing != data:
                raise DelegationBudgetError("同一 dispatch key 的决策内容发生碰撞")
            return {"decision_id": stable_id("DBD", state["identity"]["budget_id"], dispatch_ref), **data}
        record = _state_event(state, "DECISION_RECORDED",
                        stable_id("DBD", state["identity"]["budget_id"], dispatch_ref),
                        data, len(records) + 1, records[-1]["record_hash"])
        _append_unlocked(path, [record])
        return {"decision_id": record["event_id"], **data}


def bind_review_attempt(path: Path, *, dispatch_key: str, review_state_ref: str,
                        assignment: Mapping[str, Any], native_dispatch_nonce: str = "") -> Dict[str, Any]:
    """中文：同一许可只能归属一个复审状态；English: atomically claim the review owner."""
    path = Path(path)
    ref = sha256_ref(_identifier(dispatch_key, "dispatch_key"))
    owner = _sha_ref(review_state_ref, "review_state_ref")
    with OwnerTokenLock(path, timeout=1.5):
        records = _read_records_unlocked(path)
        state = _replay(records)
        if state["schema_version"] != SCHEMA_VERSION or state["closed"] or state["violated"]:
            raise DelegationBudgetError("当前预算不可绑定新复审尝试")
        decision = state["decisions"].get(ref)
        if not decision or decision["decision"] != "DELEGATE" or decision["role"] != "reviewer" \
                or canonical_json(decision["review_assignment"]) != canonical_json(assignment):
            raise DelegationBudgetError("复审状态与 permit 指定任务不一致")
        data = {"dispatch_ref": ref, "review_state_ref": owner, "assignment_ref": policy_value_digest(assignment)}
        if native_dispatch_nonce:
            data["native_dispatch_ref"] = _native_nonce_ref(native_dispatch_nonce)
        existing = state["review_claims"].get(ref)
        if existing:
            if existing != data:
                raise DelegationBudgetError("该许可已归属其他复审状态")
            return {**data, "idempotent": True}
        slot_keys = ("reviewer", "boundary_id", "phase", "round", "packet_sha256")
        for claimed_ref, claim in state["review_claims"].items():
            if data.get("native_dispatch_ref") and claim.get("native_dispatch_ref") == data["native_dispatch_ref"]:
                raise DelegationBudgetError("NATIVE_REVIEW_REFERENCE_REUSED")
            old_assignment = state["decisions"][claimed_ref]["review_assignment"]
            if claim["review_state_ref"] == owner and all(old_assignment[key] == assignment[key] for key in slot_keys):
                raise DelegationBudgetError("同一复审槽位已有派发尝试；重试须新轮次或明确的新任务槽位")
        event = _state_event(state, "REVIEW_ATTEMPT_BOUND", stable_id("DBA", state["identity"]["budget_id"], ref),
                             data, len(records) + 1, records[-1]["record_hash"])
        _append_unlocked(path, [event])
        return {**data, "idempotent": False}


def _native_nonce_ref(nonce: str) -> str:
    if not isinstance(nonce, str) or not re.fullmatch(r"[0-9a-f]{64}", nonce):
        raise DelegationBudgetError("NATIVE_REVIEW_REFERENCE_INVALID")
    return sha256_ref(nonce)


def native_review_message_prefix(nonce: str) -> str:
    _native_nonce_ref(nonce)
    return NATIVE_DISPATCH_PREFIX + nonce + "\n\n"


def native_review_nonce(message: Any) -> str:
    # 中文：仅解析固定长度首行与空行分隔符，不扫描、保存或解释其余正文。
    # English: Parse only the fixed header and blank separator; never scan or retain the body.
    size = len(NATIVE_DISPATCH_PREFIX) + 64 + 2
    if not isinstance(message, str) or len(message) < size:
        raise DelegationBudgetError("NATIVE_REVIEW_REFERENCE_REQUIRED")
    header = message[:size]
    nonce = header[len(NATIVE_DISPATCH_PREFIX):-2]
    if header != native_review_message_prefix(nonce):
        raise DelegationBudgetError("NATIVE_REVIEW_REFERENCE_INVALID")
    return nonce


def _native_review_ref(state: Mapping[str, Any], profile: str,
                       agent_type: str, baseline_sha256: str, nonce: str) -> str:
    if state["schema_version"] != SCHEMA_VERSION or agent_type not in policy(state["policy_id"])["reviewer_roles"]:
        raise DelegationBudgetError("NATIVE_REVIEW_REQUIRES_V3_REGISTERED_ROLE")
    if not isinstance(baseline_sha256, str) or not re.fullmatch(r"[a-f0-9]{64}", baseline_sha256):
        raise DelegationBudgetError("NATIVE_REVIEW_BASELINE_INVALID")
    native_ref = _native_nonce_ref(nonce)
    candidates = []
    for ref, decision in state["decisions"].items():
        if state["review_claims"].get(ref, {}).get("native_dispatch_ref") != native_ref:
            continue
        if decision["decision"] != "DELEGATE" or decision["role"] != "reviewer" or ref not in state["review_claims"]:
            continue
        if decision["parent_reservation_id"] or decision["depth"] != 1:
            continue
        if decision["approved_profile"] != profile or decision["review_assignment"]["agent_type"] != agent_type:
            continue
        if decision["selection_scorecard"]["context"]["baseline_sha256"] != baseline_sha256:
            continue
        candidates.append(ref)
    if len(candidates) != 1:
        raise DelegationBudgetError("NATIVE_REVIEW_REFERENCE_NOT_BOUND")
    return candidates[0]


def reserve_native_review(path: Path, *, host_dispatch_id: str, approved_profile: str,
                          agent_type: str, baseline_sha256: str, native_dispatch_nonce: str) -> Dict[str, Any]:
    """中文：原生接口消费显式单次引用指定的许可；校验与预占同锁完成。

    English: Native calls consume an explicitly referenced permit under the reservation lock.
    """
    return reserve_budget(path, dispatch_key="", host_dispatch_id=host_dispatch_id,
                          approved_profile=approved_profile, approval_basis="explicit-request", role=agent_type,
                          _native_review=(agent_type, baseline_sha256, native_dispatch_nonce))


def reserve_budget(path: Path, *, dispatch_key: str, host_dispatch_id: str,
                   approved_profile: str = "", approval_basis: str = "",
                   role: str = "", _native_review: Optional[tuple[str, str, str]] = None) -> Dict[str, Any]:
    path = Path(path)
    if _native_review is not None and dispatch_key:
        raise DelegationBudgetError("NATIVE_REVIEW_KEY_CONFLICT")
    dispatch_ref = "" if _native_review is not None else sha256_ref(_identifier(dispatch_key, "dispatch_key"))
    host_ref = sha256_ref(_identifier(host_dispatch_id, "host_dispatch_id"))
    with OwnerTokenLock(path, timeout=1.5):
        records = _read_records_unlocked(path)
        state = _replay(records)
        matrix = state["schema_version"] == SCHEMA_VERSION
        weights = profile_weights(state.get("policy_id", LEGACY_POLICY_ID))
        if state["closed"] or state["violated"]:
            raise DelegationBudgetError("预算已关闭或已违规，拒绝派发")
        if _native_review is not None:
            dispatch_ref = _native_review_ref(state, approved_profile, *_native_review)
        decision = state["decisions"].get(dispatch_ref)
        if not decision or decision["decision"] != "DELEGATE":
            raise DelegationBudgetError("缺少显式 DELEGATE permit")
        if matrix and decision["role"] == "reviewer" and dispatch_ref not in state["review_claims"]:
            raise DelegationBudgetError("Reviewer permit 尚未绑定复审状态")
        if role and normalize_role(role) != decision["role"]:
            raise DelegationBudgetError("派发角色与显式 permit 不一致")
        profile = approved_profile or decision["approved_profile"]
        basis = approval_basis or ("policy-default" if not approved_profile else "explicit-request")
        if profile != decision["approved_profile"] or basis not in {"policy-default", "explicit-request"}:
            raise DelegationBudgetError("批准派发档位与显式 permit 不一致")
        if matrix and is_premium(profile, state["policy_id"]) and basis != "explicit-request":
            raise DelegationBudgetError("新增模型组合必须显式请求")
        reservation_id = stable_id("DBR", state["identity"]["budget_id"], host_ref)
        existing = state["reservations"].get(reservation_id)
        expected = {
            "reservation_id": reservation_id, "dispatch_ref": dispatch_ref, "host_dispatch_ref": host_ref,
            "role": decision["role"], "approved_profile": profile, "approval_basis": basis,
            "units": weights[profile], "parent_reservation_id": decision["parent_reservation_id"],
            "depth": decision["depth"], "association": "pretool-verified",
        }
        if existing:
            comparable = {key: existing.get(key) for key in expected}
            if comparable != expected:
                raise DelegationBudgetError("同一 host dispatch id 的预占输入发生碰撞")
            if matrix and existing["state"] == "NOT_STARTED_RELEASED":
                raise DelegationBudgetError("已释放尝试不可重新派发")
            if matrix and reservation_id in state["host_receipts"]:
                raise DelegationBudgetError("V3_HOST_RECEIPT_ALREADY_RECORDED")
            return {**expected, "idempotent": True, **({"state": existing["state"]} if matrix else {})}
        if matrix and any(item["dispatch_ref"] == dispatch_ref for item in state["reservations"].values()):
            raise DelegationBudgetError("单次派发许可已绑定另一宿主调用")
        units = weights[profile]
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
        if matrix:
            hypothetical = {**state["reservations"], reservation_id: {
                **expected, "charged_units": units, "state": "RESERVED",
            }}
            _enforce_matrix_capacity(hypothetical, state["limits"], state["role_limits"], state["review_extension"], state["policy_id"])
        record = _state_event(state, "BUDGET_RESERVED", stable_id("DBE", reservation_id, "reserved"),
                        expected, len(records) + 1, records[-1]["record_hash"])
        _append_unlocked(path, [record])
        return {**expected, "idempotent": False, **({"state": "RESERVED"} if matrix else {})}


def record_host_dispatch_receipt(path: Path, *, host_dispatch_id: str, dispatch_key: str = "",
                                 agent_id: str = "", disposition: str = "created") -> Dict[str, Any]:
    """中文：供已验证根身份的宿主适配器使用；不接收调用方提交的证明摘要。

    English: Trusted host adapter entry after root verification, not a user-supplied proof endpoint.
    """
    path = Path(path)
    host_ref = sha256_ref(_identifier(host_dispatch_id, "host_dispatch_id"))
    dispatch_ref = sha256_ref(_identifier(dispatch_key, "dispatch_key")) if dispatch_key else ""
    agent_ref = sha256_ref(_identifier(agent_id, "agent_id")) if agent_id else ""
    with OwnerTokenLock(path, timeout=1.5):
        records = _read_records_unlocked(path)
        state = _replay(records)
        if state["schema_version"] != SCHEMA_VERSION or state["closed"]:
            raise DelegationBudgetError("宿主回执需要未关闭的 V3 账本")
        matches = [item for item in state["reservations"].values()
                   if item["host_dispatch_ref"] == host_ref and (not dispatch_ref or item["dispatch_ref"] == dispatch_ref)]
        if len(matches) != 1:
            raise DelegationBudgetError("宿主回执没有唯一匹配的预占")
        rid = matches[0]["reservation_id"]
        data = {"reservation_id": rid, "host_dispatch_ref": host_ref, "agent_ref": agent_ref,
                "disposition": disposition,
                "proof_ref": _receipt_proof(state["identity"], host_ref, agent_ref, disposition)}
        prior = state["host_receipts"].get(rid)
        if prior:
            if prior != data:
                raise DelegationBudgetError("宿主派发回执重放冲突")
            return {**data, "idempotent": True}
        record = _state_event(state, "HOST_DISPATCH_RECEIPT", stable_id("DBE", rid, "host-receipt"),
                              data, len(records) + 1, records[-1]["record_hash"])
        _replay(records + [record])
        _append_unlocked(path, [record])
        return {**data, "idempotent": False}


def record_host_agent_observation(path: Path, *, agent_id: str, phase: str,
                                  outcome: str = "UNKNOWN") -> Dict[str, Any]:
    """中文：缓存有界生命周期元数据；仅凭 Agent ID 与精确派发回执关联。

    English: Buffer bounded lifecycle metadata and join only by the exact receipt agent ID.
    """
    path = Path(path)
    agent_ref = sha256_ref(_identifier(agent_id, "agent_id"))
    data = {"agent_ref": agent_ref, "phase": phase, "outcome": outcome}
    with OwnerTokenLock(path, timeout=1.5):
        records = _read_records_unlocked(path)
        state = _replay(records)
        if state["schema_version"] != SCHEMA_VERSION or state["closed"]:
            raise DelegationBudgetError("生命周期回执需要未关闭的 V3 账本")
        prior = state["host_agents"].get(agent_ref, {}).get(phase)
        if prior:
            if prior["outcome"] != outcome:
                raise DelegationBudgetError("宿主生命周期重放冲突")
            return {**data, "idempotent": True}
        record = _state_event(state, "HOST_AGENT_OBSERVED", stable_id("DBE", agent_ref, phase),
                              data, len(records) + 1, records[-1]["record_hash"])
        _replay(records + [record])
        _append_unlocked(path, [record])
        return {**data, "idempotent": False}


def mark_started(path: Path, *, reservation_id: str, agent_id: str) -> Dict[str, Any]:
    path = Path(path)
    reservation_id = _identifier(reservation_id, "reservation_id")
    agent_ref = sha256_ref(_identifier(agent_id, "agent_id"))
    with OwnerTokenLock(path, timeout=1.5):
        records = _read_records_unlocked(path)
        state = _replay(records)
        if state["schema_version"] == SCHEMA_VERSION:
            raise DelegationBudgetError("V3_LIFECYCLE_REQUIRES_HOST_RECEIPTS")
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
        start = _state_event(state, "AGENT_STARTED", stable_id("DBE", reservation_id, "started"),
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
        if state["schema_version"] == SCHEMA_VERSION:
            raise DelegationBudgetError("V3_LIFECYCLE_REQUIRES_HOST_RECEIPTS")
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
        record = _state_event(state, "AGENT_COMPLETED", stable_id("DBE", reservation_id, "completed"),
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
        if state["schema_version"] == SCHEMA_VERSION:
            receipt = state["host_receipts"].get(reservation_id)
            if not receipt or receipt["disposition"] != "not-started" or receipt["proof_ref"] != proof_ref:
                raise DelegationBudgetError("V3 退款缺少匹配的宿主未启动回执")
        if item["state"] == "NOT_STARTED_RELEASED":
            return {"reservation_id": reservation_id, "state": item["state"], "idempotent": True}
        if item["state"] != "RESERVED":
            raise DelegationBudgetError("Agent 启动后不得退款")
        data = {"reservation_id": reservation_id, "proof_ref": proof_ref, "proof_kind": "host-confirmed-not-started"}
        record = _state_event(state, "NOT_STARTED_RELEASED", stable_id("DBE", reservation_id, "released"),
                        data, len(records) + 1, records[-1]["record_hash"])
        if state["schema_version"] == SCHEMA_VERSION:
            _replay(records + [record])
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
        matrix = state["schema_version"] == SCHEMA_VERSION
        if matrix and conclusion == "PASS" and not state["association_complete"]:
            raise DelegationBudgetError("未完成或未关联的尝试不能关闭为 PASS")
        data = {"conclusion": conclusion, "association_complete": state["association_complete"],
                "budget_pass": not state["violated"] and (state["association_complete"] or not matrix)}
        record = _state_event(state, "TASK_BUDGET_CLOSED", stable_id("DBE", state["identity"]["budget_id"], "closed"),
                        data, len(records) + 1, records[-1]["record_hash"])
        _append_unlocked(path, [record])
        return _replay(records + [record])


def reservation_for_host_dispatch(path: Path, host_dispatch_id: str) -> Optional[str]:
    state = read_budget(path)
    if state["schema_version"] == "4.0":
        from .routing_contract import ref
        return state["host_dispatches"].get(ref(_identifier(host_dispatch_id, "host_dispatch_id")))
    host_ref = sha256_ref(_identifier(host_dispatch_id, "host_dispatch_id"))
    for reservation_id, item in state["reservations"].items():
        if item.get("host_dispatch_ref") == host_ref:
            return reservation_id
    return None
