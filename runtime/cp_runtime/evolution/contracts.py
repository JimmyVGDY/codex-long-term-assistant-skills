"""中文：受控演进 Runtime 契约；只定义不可变数据、枚举和确定性校验，不自动修改 Skill、Reviewer、模型路由、业务仓库或生产环境。

English: Controlled-evolution runtime contracts defining immutable data, enums, and deterministic validation without automatically modifying Skills, Reviewers, model routing, business repositories, or production environments.
"""
from __future__ import annotations

import hashlib
import json
import re
import uuid
from dataclasses import dataclass, fields, is_dataclass
from datetime import datetime, timezone
from enum import Enum
from types import MappingProxyType
from typing import Any, Dict, Iterable, Mapping, Optional, Sequence, Tuple

SCHEMA_VERSION = "1.0"
POLICY_VERSION = "v6.5-default-1"
_PROJECT_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")
_RESOURCE_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/-]{0,255}$")


class ContractError(ValueError):
    """中文：合同字段非法或完整性校验失败。

    English: Contract fields are invalid or integrity validation failed.
    """


class ConfidenceLevel(str, Enum):
    # 中文：证据强度从无法形成结论递增到长窗口、多来源且稳定的证据。
    # English: Evidence strength increases from no conclusion to stable, multi-source evidence over a long window.
    L0 = "L0"
    L1 = "L1"
    L2 = "L2"
    L3 = "L3"
    L4 = "L4"


class RiskLevel(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class ProposalAction(str, Enum):
    INVESTIGATE = "INVESTIGATE"
    MODIFY = "MODIFY"
    DOCUMENT = "DOCUMENT"
    MERGE = "MERGE"
    DEPRECATE = "DEPRECATE"


class ProposalStatus(str, Enum):
    PENDING_REVIEW = "PENDING_REVIEW"
    ACCEPTED = "ACCEPTED"
    REJECTED = "REJECTED"
    DEFERRED = "DEFERRED"
    IMPLEMENTATION_LINKED = "IMPLEMENTATION_LINKED"
    VALIDATION_RECORDED = "VALIDATION_RECORDED"
    CLOSED = "CLOSED"
    SUPERSEDED = "SUPERSEDED"


class DecisionType(str, Enum):
    ACCEPT = "ACCEPT"
    REJECT = "REJECT"
    DEFER = "DEFER"


class ExecutionAuthorization(str, Enum):
    """中文：V6.0 只允许 NONE，防止分析提案被误当作执行授权。

    English: V6.0 permits only NONE so analytical proposals cannot be mistaken for execution authorization.
    """

    NONE = "NONE"


class SignalType(str, Enum):
    REPEATED_FAILURE = "REPEATED_FAILURE"
    DISPATCH_PROFILE_VALUE_REGRESSION = "DISPATCH_PROFILE_VALUE_REGRESSION"
    ROUTING_DEVIATION = "ROUTING_DEVIATION"
    EXCESSIVE_REPAIR = "EXCESSIVE_REPAIR"
    LOW_REVIEWER_YIELD = "LOW_REVIEWER_YIELD"
    NEGATIVE_OUTCOME = "NEGATIVE_OUTCOME"
    UNUSED_CAPABILITY = "UNUSED_CAPABILITY"


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def parse_iso_datetime(value: str, field_name: str) -> datetime:
    if not isinstance(value, str) or not value.strip():
        raise ContractError("%s 不能为空" % field_name)
    normalized = value.strip().replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError as exc:
        raise ContractError("%s 不是合法 ISO-8601 时间: %s" % (field_name, value)) from exc
    if parsed.tzinfo is None:
        raise ContractError("%s 必须包含时区" % field_name)
    return parsed


def validate_project_id(project_id: str) -> str:
    if not isinstance(project_id, str) or not _PROJECT_ID_RE.fullmatch(project_id):
        raise ContractError("project_id 仅允许字母、数字、点、下划线和连字符，长度 1-128")
    return project_id


def validate_resource_name(value: str, field_name: str = "resource") -> str:
    if not isinstance(value, str) or not _RESOURCE_RE.fullmatch(value):
        raise ContractError("%s 格式非法" % field_name)
    return value


def _require_text(value: str, field_name: str, min_len: int = 1, max_len: int = 4096) -> str:
    if not isinstance(value, str):
        raise ContractError("%s 必须是字符串" % field_name)
    normalized = value.strip()
    if len(normalized) < min_len or len(normalized) > max_len:
        raise ContractError("%s 长度必须在 %d-%d 之间" % (field_name, min_len, max_len))
    if "\x00" in normalized:
        raise ContractError("%s 不允许包含 NUL 字符" % field_name)
    return normalized


def _freeze(value: Any) -> Any:
    if isinstance(value, MappingProxyType):
        return value
    if isinstance(value, Mapping):
        return MappingProxyType({str(k): _freeze(v) for k, v in value.items()})
    if isinstance(value, list):
        return tuple(_freeze(v) for v in value)
    if isinstance(value, tuple):
        return tuple(_freeze(v) for v in value)
    if isinstance(value, set):
        return tuple(sorted((_freeze(v) for v in value), key=lambda item: repr(item)))
    return value


def to_primitive(value: Any) -> Any:
    if isinstance(value, Enum):
        return value.value
    if is_dataclass(value):
        result: Dict[str, Any] = {}
        for field in fields(value):
            result[field.name] = to_primitive(getattr(value, field.name))
        return result
    if isinstance(value, Mapping):
        return {str(k): to_primitive(v) for k, v in sorted(value.items(), key=lambda item: str(item[0]))}
    if isinstance(value, (tuple, list, set)):
        return [to_primitive(v) for v in value]
    return value


def canonical_json(value: Any) -> str:
    return json.dumps(to_primitive(value), ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def sha256_hex(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def new_id(prefix: str, seed: Optional[str] = None) -> str:
    normalized_prefix = _require_text(prefix, "prefix", 2, 16).upper()
    if seed is None:
        suffix = uuid.uuid4().hex[:16]
    else:
        suffix = hashlib.sha256(seed.encode("utf-8")).hexdigest()[:16]
    return "%s-%s" % (normalized_prefix, suffix)


def _hash_payload(payload: Mapping[str, Any]) -> str:
    clean = {k: v for k, v in payload.items() if k != "content_hash"}
    return sha256_hex(clean)


@dataclass(frozen=True)
class EvidenceReference:
    source_kind: str
    source_path: str
    line_number: int
    record_id: str
    task_id: Optional[str] = None
    record_hash: Optional[str] = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "source_kind", _require_text(self.source_kind, "source_kind", 1, 64))
        path = _require_text(self.source_path, "source_path", 1, 1024)
        if path.startswith(("/", "\\")) or ".." in path.replace("\\", "/").split("/"):
            raise ContractError("source_path 必须是安全的相对路径")
        object.__setattr__(self, "source_path", path.replace("\\", "/"))
        if not isinstance(self.line_number, int) or self.line_number < 1:
            raise ContractError("line_number 必须大于等于 1")
        object.__setattr__(self, "record_id", _require_text(self.record_id, "record_id", 1, 256))
        if self.task_id is not None:
            object.__setattr__(self, "task_id", _require_text(self.task_id, "task_id", 1, 256))
        if self.record_hash is not None:
            if not re.fullmatch(r"[0-9a-f]{64}", self.record_hash):
                raise ContractError("record_hash 必须是 64 位小写 SHA-256")


@dataclass(frozen=True)
class PatternSignal:
    signal_id: str
    signal_type: SignalType
    target: str
    occurrence_count: int
    independent_task_count: int
    rate: float
    confidence: ConfidenceLevel
    summary: str
    evidence: Tuple[EvidenceReference, ...]
    metrics: Mapping[str, Any]

    def __post_init__(self) -> None:
        object.__setattr__(self, "signal_id", _require_text(self.signal_id, "signal_id", 3, 128))
        object.__setattr__(self, "target", _require_text(self.target, "target", 1, 256))
        if self.occurrence_count < 0 or self.independent_task_count < 0:
            raise ContractError("信号计数不能为负数")
        if not 0.0 <= float(self.rate) <= 1.0:
            raise ContractError("rate 必须在 0-1 之间")
        object.__setattr__(self, "summary", _require_text(self.summary, "summary", 5, 2048))
        object.__setattr__(self, "evidence", tuple(self.evidence))
        object.__setattr__(self, "metrics", _freeze(self.metrics))


@dataclass(frozen=True)
class SelfObservationSnapshot:
    schema_version: str
    snapshot_id: str
    project_id: str
    observed_at: str
    window_start: Optional[str]
    window_end: Optional[str]
    source_files: Tuple[str, ...]
    record_count: int
    task_count: int
    metrics: Mapping[str, Any]
    signals: Tuple[PatternSignal, ...]
    warnings: Tuple[str, ...]
    source_digest: str
    content_hash: str

    def __post_init__(self) -> None:
        if self.schema_version != SCHEMA_VERSION:
            raise ContractError("不支持的观察快照 schema_version")
        object.__setattr__(self, "snapshot_id", _require_text(self.snapshot_id, "snapshot_id", 3, 128))
        validate_project_id(self.project_id)
        parse_iso_datetime(self.observed_at, "observed_at")
        if self.window_start is not None:
            parse_iso_datetime(self.window_start, "window_start")
        if self.window_end is not None:
            parse_iso_datetime(self.window_end, "window_end")
        if self.record_count < 0 or self.task_count < 0:
            raise ContractError("观察计数不能为负数")
        safe_files = []
        for path in self.source_files:
            normalized = _require_text(path, "source_file", 1, 1024).replace("\\", "/")
            if normalized.startswith("/") or ".." in normalized.split("/"):
                raise ContractError("source_files 只能包含安全相对路径")
            safe_files.append(normalized)
        object.__setattr__(self, "source_files", tuple(safe_files))
        object.__setattr__(self, "metrics", _freeze(self.metrics))
        object.__setattr__(self, "signals", tuple(self.signals))
        object.__setattr__(self, "warnings", tuple(_require_text(v, "warning", 1, 1024) for v in self.warnings))
        if not re.fullmatch(r"[0-9a-f]{64}", self.source_digest):
            raise ContractError("source_digest 必须是 SHA-256")
        if not re.fullmatch(r"[0-9a-f]{64}", self.content_hash):
            raise ContractError("content_hash 必须是 SHA-256")

    @classmethod
    def create(
        cls,
        project_id: str,
        source_files: Sequence[str],
        record_count: int,
        task_count: int,
        metrics: Mapping[str, Any],
        signals: Sequence[PatternSignal],
        warnings: Sequence[str],
        window_start: Optional[str] = None,
        window_end: Optional[str] = None,
        observed_at: Optional[str] = None,
    ) -> "SelfObservationSnapshot":
        timestamp = observed_at or utc_now_iso()
        source_digest = sha256_hex(canonical_json({
            "project_id": project_id,
            "source_files": list(source_files),
            "record_count": int(record_count),
            "task_count": int(task_count),
            "metrics": metrics,
            "signals": [to_primitive(item) for item in signals],
        }))
        # 中文：V6 快照 ID 必须唯一；source_digest 单独用于同源内容比较。
        # English: V6 snapshot IDs must be unique; source_digest separately compares identical source content.
        seed = "%s|%s|%s" % (project_id, timestamp, uuid.uuid4().hex)
        payload: Dict[str, Any] = {
            "schema_version": SCHEMA_VERSION,
            "snapshot_id": new_id("OBS", seed),
            "project_id": validate_project_id(project_id),
            "observed_at": timestamp,
            "window_start": window_start,
            "window_end": window_end,
            "source_files": tuple(source_files),
            "record_count": int(record_count),
            "task_count": int(task_count),
            "metrics": metrics,
            "signals": tuple(signals),
            "warnings": tuple(warnings),
            "source_digest": source_digest,
        }
        payload["content_hash"] = _hash_payload(payload)
        return cls(**payload)

    def verify_integrity(self) -> None:
        if _hash_payload(to_primitive(self)) != self.content_hash:
            raise ContractError("观察快照完整性校验失败")


@dataclass(frozen=True)
class ValueComplexityAssessment:
    schema_version: str
    assessment_id: str
    snapshot_id: str
    signal_id: str
    target: str
    value_score: int
    complexity_score: int
    risk_level: RiskLevel
    confidence: ConfidenceLevel
    recommended_action: ProposalAction
    rationale: str
    constraints: Tuple[str, ...]
    evidence: Tuple[EvidenceReference, ...]
    assessed_at: str
    policy_version: str
    content_hash: str

    def __post_init__(self) -> None:
        if self.schema_version != SCHEMA_VERSION:
            raise ContractError("不支持的评估 schema_version")
        for name in ("assessment_id", "snapshot_id", "signal_id"):
            object.__setattr__(self, name, _require_text(getattr(self, name), name, 3, 128))
        object.__setattr__(self, "target", _require_text(self.target, "target", 1, 256))
        if not 0 <= self.value_score <= 100 or not 0 <= self.complexity_score <= 100:
            raise ContractError("value_score 和 complexity_score 必须在 0-100 之间")
        object.__setattr__(self, "rationale", _require_text(self.rationale, "rationale", 10, 4096))
        object.__setattr__(self, "constraints", tuple(_require_text(v, "constraint", 3, 1024) for v in self.constraints))
        object.__setattr__(self, "evidence", tuple(self.evidence))
        parse_iso_datetime(self.assessed_at, "assessed_at")
        object.__setattr__(self, "policy_version", _require_text(self.policy_version, "policy_version", 3, 128))
        if not re.fullmatch(r"[0-9a-f]{64}", self.content_hash):
            raise ContractError("content_hash 必须是 SHA-256")

    @classmethod
    def create(
        cls,
        snapshot_id: str,
        signal: PatternSignal,
        value_score: int,
        complexity_score: int,
        risk_level: RiskLevel,
        confidence: ConfidenceLevel,
        recommended_action: ProposalAction,
        rationale: str,
        constraints: Sequence[str],
        policy_version: str = POLICY_VERSION,
        assessed_at: Optional[str] = None,
    ) -> "ValueComplexityAssessment":
        timestamp = assessed_at or utc_now_iso()
        seed = "%s|%s|%s|%s" % (snapshot_id, signal.signal_id, policy_version, timestamp)
        payload: Dict[str, Any] = {
            "schema_version": SCHEMA_VERSION,
            "assessment_id": new_id("ASM", seed),
            "snapshot_id": snapshot_id,
            "signal_id": signal.signal_id,
            "target": signal.target,
            "value_score": int(value_score),
            "complexity_score": int(complexity_score),
            "risk_level": risk_level,
            "confidence": confidence,
            "recommended_action": recommended_action,
            "rationale": rationale,
            "constraints": tuple(constraints),
            "evidence": tuple(signal.evidence),
            "assessed_at": timestamp,
            "policy_version": policy_version,
        }
        payload["content_hash"] = _hash_payload(payload)
        return cls(**payload)

    def verify_integrity(self) -> None:
        if _hash_payload(to_primitive(self)) != self.content_hash:
            raise ContractError("价值复杂度评估完整性校验失败")


@dataclass(frozen=True)
class OptimizationProposal:
    schema_version: str
    proposal_id: str
    project_id: str
    assessment_id: str
    fingerprint: str
    created_at: str
    action_type: ProposalAction
    target_resource: str
    problem_statement: str
    recommendation: str
    expected_value: str
    risk_level: RiskLevel
    complexity_score: int
    confidence: ConfidenceLevel
    evidence: Tuple[EvidenceReference, ...]
    rollback_plan: Tuple[str, ...]
    validation_plan: Tuple[str, ...]
    constraints: Tuple[str, ...]
    execution_authorization: ExecutionAuthorization
    status: ProposalStatus
    content_hash: str

    def __post_init__(self) -> None:
        if self.schema_version != SCHEMA_VERSION:
            raise ContractError("不支持的优化提案 schema_version")
        object.__setattr__(self, "proposal_id", _require_text(self.proposal_id, "proposal_id", 3, 128))
        validate_project_id(self.project_id)
        object.__setattr__(self, "assessment_id", _require_text(self.assessment_id, "assessment_id", 3, 128))
        if not re.fullmatch(r"[0-9a-f]{64}", self.fingerprint):
            raise ContractError("fingerprint 必须是 SHA-256")
        parse_iso_datetime(self.created_at, "created_at")
        object.__setattr__(self, "target_resource", _require_text(self.target_resource, "target_resource", 1, 256))
        object.__setattr__(self, "problem_statement", _require_text(self.problem_statement, "problem_statement", 10, 4096))
        object.__setattr__(self, "recommendation", _require_text(self.recommendation, "recommendation", 10, 8192))
        object.__setattr__(self, "expected_value", _require_text(self.expected_value, "expected_value", 5, 4096))
        if not 0 <= self.complexity_score <= 100:
            raise ContractError("complexity_score 必须在 0-100 之间")
        object.__setattr__(self, "evidence", tuple(self.evidence))
        if not self.evidence:
            raise ContractError("优化提案必须引用至少一条证据")
        object.__setattr__(self, "rollback_plan", tuple(_require_text(v, "rollback_step", 3, 2048) for v in self.rollback_plan))
        object.__setattr__(self, "validation_plan", tuple(_require_text(v, "validation_step", 3, 2048) for v in self.validation_plan))
        object.__setattr__(self, "constraints", tuple(_require_text(v, "constraint", 3, 2048) for v in self.constraints))
        if self.execution_authorization is not ExecutionAuthorization.NONE:
            raise ContractError("V6 优化提案的 execution_authorization 只能是 NONE")
        if self.status is not ProposalStatus.PENDING_REVIEW:
            raise ContractError("新建提案状态必须是 PENDING_REVIEW，后续状态由独立决策事件表达")
        if not re.fullmatch(r"[0-9a-f]{64}", self.content_hash):
            raise ContractError("content_hash 必须是 SHA-256")

    @classmethod
    def create(
        cls,
        project_id: str,
        assessment: ValueComplexityAssessment,
        action_type: ProposalAction,
        target_resource: str,
        problem_statement: str,
        recommendation: str,
        expected_value: str,
        rollback_plan: Sequence[str],
        validation_plan: Sequence[str],
        constraints: Sequence[str],
        created_at: Optional[str] = None,
    ) -> "OptimizationProposal":
        timestamp = created_at or utc_now_iso()
        fingerprint = sha256_hex({
            "project_id": project_id,
            "target_resource": target_resource,
            "signal_id": assessment.signal_id,
            "action_type": action_type.value,
            "policy_version": assessment.policy_version,
            # 中文：证据不变时 fingerprint 不变，REJECTED 或 DEFERRED 提案不会机械重生；新证据会自然产生新 fingerprint。
            # English: Unchanged evidence keeps the same fingerprint, preventing mechanical rebirth of REJECTED or DEFERRED proposals; new evidence naturally yields a new fingerprint.
            "evidence": [
                {"source_path": e.source_path, "line_number": e.line_number, "record_id": e.record_id, "record_hash": e.record_hash}
                for e in assessment.evidence
            ],
        })
        payload: Dict[str, Any] = {
            "schema_version": SCHEMA_VERSION,
            "proposal_id": new_id("EVO"),
            "project_id": validate_project_id(project_id),
            "assessment_id": assessment.assessment_id,
            "fingerprint": fingerprint,
            "created_at": timestamp,
            "action_type": action_type,
            "target_resource": target_resource,
            "problem_statement": problem_statement,
            "recommendation": recommendation,
            "expected_value": expected_value,
            "risk_level": assessment.risk_level,
            "complexity_score": assessment.complexity_score,
            "confidence": assessment.confidence,
            "evidence": tuple(assessment.evidence),
            "rollback_plan": tuple(rollback_plan),
            "validation_plan": tuple(validation_plan),
            "constraints": tuple(constraints),
            "execution_authorization": ExecutionAuthorization.NONE,
            "status": ProposalStatus.PENDING_REVIEW,
        }
        payload["content_hash"] = _hash_payload(payload)
        return cls(**payload)

    def verify_integrity(self) -> None:
        if _hash_payload(to_primitive(self)) != self.content_hash:
            raise ContractError("优化提案完整性校验失败")


@dataclass(frozen=True)
class ProposalDecision:
    schema_version: str
    decision_id: str
    proposal_id: str
    decision: DecisionType
    actor: str
    rationale: str
    decided_at: str
    content_hash: str

    def __post_init__(self) -> None:
        if self.schema_version != SCHEMA_VERSION:
            raise ContractError("不支持的决策 schema_version")
        object.__setattr__(self, "decision_id", _require_text(self.decision_id, "decision_id", 3, 128))
        object.__setattr__(self, "proposal_id", _require_text(self.proposal_id, "proposal_id", 3, 128))
        object.__setattr__(self, "actor", _require_text(self.actor, "actor", 2, 256))
        object.__setattr__(self, "rationale", _require_text(self.rationale, "rationale", 10, 4096))
        parse_iso_datetime(self.decided_at, "decided_at")
        if not re.fullmatch(r"[0-9a-f]{64}", self.content_hash):
            raise ContractError("content_hash 必须是 SHA-256")

    @classmethod
    def create(
        cls,
        proposal_id: str,
        decision: DecisionType,
        actor: str,
        rationale: str,
        decided_at: Optional[str] = None,
    ) -> "ProposalDecision":
        timestamp = decided_at or utc_now_iso()
        payload: Dict[str, Any] = {
            "schema_version": SCHEMA_VERSION,
            "decision_id": new_id("DEC"),
            "proposal_id": proposal_id,
            "decision": decision,
            "actor": actor,
            "rationale": rationale,
            "decided_at": timestamp,
        }
        payload["content_hash"] = _hash_payload(payload)
        return cls(**payload)

    def verify_integrity(self) -> None:
        if _hash_payload(to_primitive(self)) != self.content_hash:
            raise ContractError("提案决策完整性校验失败")


@dataclass(frozen=True)
class EvolutionPolicy:
    policy_version: str = POLICY_VERSION
    min_records: int = 5
    min_independent_tasks: int = 3
    repeated_failure_count: int = 3
    dispatch_profile_value_regression_rate: float = 0.25
    routing_deviation_rate: float = 0.30
    excessive_repair_average: float = 1.50
    high_repair_rounds: int = 2
    reviewer_min_invocations: int = 8
    reviewer_min_independent_tasks: int = 5
    reviewer_min_labeled_findings: int = 5
    reviewer_high_duplicate_rate: float = 0.50
    reviewer_low_yield_rate: float = 0.05
    min_lifecycle_completeness_rate: float = 0.80
    min_session_end_coverage: float = 0.80
    min_known_terminal_outcome_coverage: float = 0.80
    min_project_repo_binding_coverage: float = 1.00
    min_observation_window_days: int = 7
    reviewer_min_attribution_coverage: float = 0.80
    reviewer_min_cost_coverage: float = 0.80
    negative_outcome_rate: float = 0.25
    deprecation_min_invocations: int = 20
    deprecation_min_window_days: int = 30
    max_source_files: int = 100
    max_source_file_bytes: int = 20 * 1024 * 1024
    max_record_count: int = 200000

    def __post_init__(self) -> None:
        _require_text(self.policy_version, "policy_version", 3, 128)
        integer_fields = (
            "min_records", "min_independent_tasks", "repeated_failure_count",
            "high_repair_rounds", "reviewer_min_invocations", "reviewer_min_independent_tasks",
            "reviewer_min_labeled_findings", "deprecation_min_invocations",
            "deprecation_min_window_days", "min_observation_window_days", "max_source_files", "max_source_file_bytes", "max_record_count",
        )
        for name in integer_fields:
            if int(getattr(self, name)) <= 0:
                raise ContractError("%s 必须大于 0" % name)
        for name in ("dispatch_profile_value_regression_rate", "routing_deviation_rate", "reviewer_low_yield_rate", "reviewer_high_duplicate_rate", "negative_outcome_rate", "min_lifecycle_completeness_rate", "min_session_end_coverage", "min_known_terminal_outcome_coverage", "min_project_repo_binding_coverage", "reviewer_min_attribution_coverage", "reviewer_min_cost_coverage"):
            value = float(getattr(self, name))
            if not 0.0 <= value <= 1.0:
                raise ContractError("%s 必须在 0-1 之间" % name)
        if self.excessive_repair_average < 0:
            raise ContractError("excessive_repair_average 不能为负数")

    @classmethod
    def from_mapping(cls, raw: Mapping[str, Any]) -> "EvolutionPolicy":
        allowed = {field.name for field in fields(cls)}
        unknown = sorted(set(raw.keys()) - allowed)
        if unknown:
            raise ContractError("EvolutionPolicy 包含未知字段: %s" % ", ".join(unknown))
        return cls(**dict(raw))


def verify_contract_integrity(value: Any) -> None:
    verifier = getattr(value, "verify_integrity", None)
    if verifier is None:
        raise ContractError("对象不支持完整性校验")
    verifier()
