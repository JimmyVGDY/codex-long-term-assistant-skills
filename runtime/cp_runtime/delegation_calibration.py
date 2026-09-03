"""中文：委派角色收益校准与相邻档位离线回放。

English: Delegation role-value calibration and adjacent-tier offline replay.

Only the parent coordinator can finalize a sample. Child self-reports remain
pending and never enter route recommendations. Replay emits proposals with
``execution_authorization=NONE`` and never changes policy or configuration.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping

from .delegation_budget import (
    CONTEXT_SIZES, DIFFICULTIES, PROFILE_ORDER, PROFILE_WEIGHTS, RISK_DOMAINS,
    ROLES, DelegationBudgetError, canonical_json, read_budget, sha256_ref,
)
from .event_v2 import OwnerTokenLock

SAMPLE_SCHEMA = "1.0"
REPLAY_SCHEMA = "1.0"
IDENTITY_KEYS = ("budget_id", "task_id", "project_id", "repo_fingerprint")
ROLE_METRICS = {
    "reviewer": {"accepted_findings", "repaired_findings", "duplicate_findings", "missed_findings", "regressions_prevented"},
    "explorer": {"evidence_adopted", "questions_resolved", "duplicate_explorations"},
    "worker": {"deliveries_accepted", "validations_passed", "rework_rounds", "rollbacks"},
}
SAMPLE_ID = re.compile(r"^DCS_[0-9a-f]{64}$")
IDENTIFIER = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,159}$")
SHA_REF = re.compile(r"^sha256:[0-9a-f]{64}$")
FINALIZER = re.compile(r"^parent:[A-Za-z0-9][A-Za-z0-9._:-]{0,152}$")
SAMPLE_SOURCES = {"child-self-report", "parent-observation"}
MAX_METRIC_VALUE = 1000
MAX_DURATION_MS = 604_800_000
MAX_RETRY_COUNT = 100


def _nonnegative(value: Any, name: str, *, maximum: int | None = None) -> int:
    if isinstance(value, bool):
        raise DelegationBudgetError("%s 必须是非负整数" % name)
    try:
        result = int(value)
    except (TypeError, ValueError) as exc:
        raise DelegationBudgetError("%s 必须是非负整数" % name) from exc
    if result < 0:
        raise DelegationBudgetError("%s 必须是非负整数" % name)
    if maximum is not None and result > maximum:
        raise DelegationBudgetError("%s 超出校准上限" % name)
    return result


def _sample_id(identity: Mapping[str, str], reservation_id: str) -> str:
    source = "\0".join(str(identity[key]) for key in IDENTITY_KEYS) + "\0" + reservation_id
    return "DCS_" + hashlib.sha256(source.encode("utf-8")).hexdigest()


def _score(role: str, metrics: Mapping[str, int]) -> int:
    if role == "reviewer":
        return max(0, metrics["accepted_findings"] * 3 + metrics["repaired_findings"] * 2
                   + metrics["regressions_prevented"] * 4 - metrics["duplicate_findings"]
                   - metrics["missed_findings"] * 3)
    if role == "explorer":
        return max(0, metrics["evidence_adopted"] * 2 + metrics["questions_resolved"] * 3
                   - metrics["duplicate_explorations"])
    return max(0, metrics["deliveries_accepted"] * 3 + metrics["validations_passed"] * 2
               - metrics["rework_rounds"] * 2 - metrics["rollbacks"] * 4)


def build_pending_sample(ledger_path: Path, reservation_id: str,
                         metrics: Mapping[str, Any], *, source: str = "child-self-report") -> Dict[str, Any]:
    """中文：构建有界 pending 样本；该状态永远不能参与校准。

    English: Build a bounded pending sample; this is never calibration-eligible.
    """
    budget = read_budget(Path(ledger_path))
    reservation = budget["reservations"].get(str(reservation_id))
    if not reservation:
        raise DelegationBudgetError("校准 reservation 不存在")
    if reservation.get("state") != "COMPLETED" or not reservation.get("completion_ref"):
        raise DelegationBudgetError("只有已完成 reservation 可进入校准")
    if source not in SAMPLE_SOURCES:
        raise DelegationBudgetError("校准样本来源非法")
    role = reservation["role"]
    if set(metrics) != ROLE_METRICS[role]:
        raise DelegationBudgetError("角色校准指标字段不完整或包含未知字段")
    normalized = {key: _nonnegative(metrics[key], key, maximum=MAX_METRIC_VALUE) for key in sorted(metrics)}
    decision = budget["decisions"].get(reservation["dispatch_ref"])
    if not decision:
        raise DelegationBudgetError("校准样本缺少路由决策")
    actual_profile = reservation.get("actual_profile") or ""
    actual_verified = bool(actual_profile)
    identity = budget["identity"]
    return {
        "schema_version": SAMPLE_SCHEMA,
        "record_id": _sample_id(identity, reservation_id),
        **identity,
        "reservation_id": reservation_id,
        "reservation_completion_ref": reservation["completion_ref"],
        "role": role,
        "responsibility": decision["responsibility"],
        "difficulty": decision["difficulty"],
        "risk_domain": decision["risk_domain"],
        "requested_profile": reservation["requested_profile"],
        "actual_profile": actual_profile,
        "runtime_profile_verified": actual_verified,
        "context_size": decision["context_size"],
        "duration_ms": 0,
        "retry_count": 0,
        "metrics": normalized,
        "value_score": _score(role, normalized),
        "source": source,
        "calibration_finalized": False,
        "finalized_by": "",
        "evidence_refs": [],
    }


def finalize_sample(sample: Mapping[str, Any], *, finalized_by: str,
                    evidence_refs: Iterable[str], duration_ms: int = 0,
                    retry_count: int = 0) -> Dict[str, Any]:
    """中文：由父协调者最终化样本；子 Agent 报告不能自行最终化。

    English: Parent-finalize a sample. A child report cannot finalize itself.
    """
    value = dict(sample)
    if value.get("schema_version") != SAMPLE_SCHEMA or value.get("calibration_finalized") is not False:
        raise DelegationBudgetError("只能 finalise 合法的 pending 校准样本")
    if not FINALIZER.fullmatch(str(finalized_by)):
        raise DelegationBudgetError("校准只能由主协调 Agent 最终化")
    refs = list(evidence_refs)
    if not refs or len(refs) > 20 or any(not isinstance(ref, str) or not SHA_REF.fullmatch(ref) for ref in refs):
        raise DelegationBudgetError("最终化必须提供 SHA-256 evidence_refs")
    if sample.get("reservation_completion_ref") not in refs:
        raise DelegationBudgetError("最终化证据必须绑定 reservation 完成事件")
    value.update({
        "calibration_finalized": True,
        "finalized_by": str(finalized_by),
        "evidence_refs": refs,
        "duration_ms": _nonnegative(duration_ms, "duration_ms", maximum=MAX_DURATION_MS),
        "retry_count": _nonnegative(retry_count, "retry_count", maximum=MAX_RETRY_COUNT),
    })
    return value


def _validate_sample(sample: Mapping[str, Any]) -> Dict[str, Any]:
    expected_keys = {
        "schema_version", "record_id", *IDENTITY_KEYS, "reservation_id", "reservation_completion_ref",
        "role", "responsibility",
        "difficulty", "risk_domain", "requested_profile", "actual_profile", "runtime_profile_verified",
        "context_size", "duration_ms", "retry_count", "metrics", "value_score", "source",
        "calibration_finalized", "finalized_by", "evidence_refs",
    }
    if set(sample) != expected_keys or sample.get("schema_version") != SAMPLE_SCHEMA:
        raise DelegationBudgetError("校准样本 schema 非法")
    role = str(sample.get("role") or "")
    if role not in ROLES or sample.get("difficulty") not in DIFFICULTIES:
        raise DelegationBudgetError("校准样本角色或难度非法")
    if sample.get("risk_domain") not in RISK_DOMAINS or sample.get("context_size") not in CONTEXT_SIZES:
        raise DelegationBudgetError("校准样本风险域或上下文档位非法")
    if not SAMPLE_ID.fullmatch(str(sample.get("record_id") or "")):
        raise DelegationBudgetError("校准 record_id 非法")
    for key in ("budget_id", "task_id", "project_id", "reservation_id", "responsibility"):
        if not IDENTIFIER.fullmatch(str(sample.get(key) or "")):
            raise DelegationBudgetError("校准身份或职责字段非法")
    if not SHA_REF.fullmatch(str(sample.get("repo_fingerprint") or "")):
        raise DelegationBudgetError("校准 repo_fingerprint 非法")
    if not SHA_REF.fullmatch(str(sample.get("reservation_completion_ref") or "")):
        raise DelegationBudgetError("校准 reservation 完成引用非法")
    requested = str(sample.get("requested_profile") or "")
    actual = str(sample.get("actual_profile") or "")
    if requested not in PROFILE_WEIGHTS or (actual and actual not in PROFILE_WEIGHTS):
        raise DelegationBudgetError("校准模型档位非法")
    if sample.get("runtime_profile_verified") is not bool(actual):
        raise DelegationBudgetError("校准实际模型证明状态非法")
    metrics = sample.get("metrics")
    if not isinstance(metrics, Mapping) or set(metrics) != ROLE_METRICS[role]:
        raise DelegationBudgetError("角色校准指标字段不完整或包含未知字段")
    normalized = {key: _nonnegative(metrics[key], key, maximum=MAX_METRIC_VALUE) for key in sorted(metrics)}
    if sample.get("value_score") != _score(role, normalized):
        raise DelegationBudgetError("校准价值分数与指标不一致")
    if sample.get("source") not in SAMPLE_SOURCES:
        raise DelegationBudgetError("校准样本来源非法")
    _nonnegative(sample.get("duration_ms"), "duration_ms", maximum=MAX_DURATION_MS)
    _nonnegative(sample.get("retry_count"), "retry_count", maximum=MAX_RETRY_COUNT)
    finalized = sample.get("calibration_finalized")
    refs = sample.get("evidence_refs")
    finalizer = str(sample.get("finalized_by") or "")
    if not isinstance(refs, list) or len(refs) > 20:
        raise DelegationBudgetError("校准 evidence_refs 非法")
    if finalized is True:
        if not FINALIZER.fullmatch(finalizer) or not refs or any(not isinstance(ref, str) or not SHA_REF.fullmatch(ref) for ref in refs):
            raise DelegationBudgetError("校准最终化证据非法")
    elif finalized is False:
        if finalizer or refs or sample.get("duration_ms") != 0 or sample.get("retry_count") != 0:
            raise DelegationBudgetError("pending 校准样本包含最终化字段")
    else:
        raise DelegationBudgetError("校准最终化状态非法")
    return dict(sample)


def _validate_against_budget(sample: Mapping[str, Any], ledger_path: Path) -> Dict[str, Any]:
    value = _validate_sample(sample)
    budget = read_budget(Path(ledger_path))
    if any(value[key] != budget["identity"][key] for key in IDENTITY_KEYS):
        raise DelegationBudgetError("校准样本与预算账本身份不一致")
    reservation = budget["reservations"].get(value["reservation_id"])
    if not reservation or reservation.get("state") != "COMPLETED":
        raise DelegationBudgetError("校准样本未绑定已完成 reservation")
    decision = budget["decisions"].get(reservation["dispatch_ref"])
    if not decision:
        raise DelegationBudgetError("校准样本缺少账本路由决策")
    expected = {
        "record_id": _sample_id(budget["identity"], value["reservation_id"]),
        "reservation_completion_ref": reservation["completion_ref"],
        "role": reservation["role"],
        "responsibility": decision["responsibility"],
        "difficulty": decision["difficulty"],
        "risk_domain": decision["risk_domain"],
        "requested_profile": reservation["requested_profile"],
        "actual_profile": reservation.get("actual_profile") or "",
        "runtime_profile_verified": bool(reservation.get("actual_profile")),
        "context_size": decision["context_size"],
    }
    if any(value[key] != expected[key] for key in expected):
        raise DelegationBudgetError("校准样本与 reservation 或路由决策不一致")
    if value["calibration_finalized"] is True and value["reservation_completion_ref"] not in value["evidence_refs"]:
        raise DelegationBudgetError("校准最终化证据未绑定 reservation 完成事件")
    return value


def append_sample(path: Path, sample: Mapping[str, Any], *, ledger_path: Path) -> Dict[str, Any]:
    path = Path(path)
    value = _validate_against_budget(sample, ledger_path)
    serialized = canonical_json(value)
    with OwnerTokenLock(path, timeout=1.5):
        existing: Dict[str, str] = {}
        if path.is_file():
            for line in path.read_text(encoding="utf-8").splitlines():
                if not line.strip():
                    continue
                item = json.loads(line)
                record_id = str(item.get("record_id") or "")
                if record_id in existing and existing[record_id] != canonical_json(item):
                    raise DelegationBudgetError("校准 record_id 冲突")
                existing[record_id] = canonical_json(item)
        if value["record_id"] in existing:
            if existing[value["record_id"]] != serialized:
                raise DelegationBudgetError("校准 record_id 重放内容不一致")
            return value
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8", newline="\n") as handle:
            handle.write(serialized + "\n"); handle.flush(); os.fsync(handle.fileno())
    return value


def load_samples(path: Path, *, ledger_path: Path) -> List[Dict[str, Any]]:
    path = Path(path)
    if not path.is_file():
        return []
    with OwnerTokenLock(path, timeout=1.5):
        values = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    values = [_validate_against_budget(item, ledger_path) for item in values]
    ids = [item.get("record_id") for item in values]
    if len(ids) != len(set(ids)):
        raise DelegationBudgetError("校准样本存在重复 record_id")
    return values


def offline_replay(samples: Iterable[Mapping[str, Any]], *, ledger_path: Path,
                   minimum_samples_per_profile: int = 3) -> Dict[str, Any]:
    minimum = _nonnegative(minimum_samples_per_profile, "minimum_samples_per_profile")
    if minimum < 1:
        raise DelegationBudgetError("minimum_samples_per_profile 至少为 1")
    validated = [_validate_against_budget(item, ledger_path) for item in samples]
    eligible = [dict(item) for item in validated
                if item.get("calibration_finalized") is True and item.get("runtime_profile_verified") is True]
    scenario_groups: Dict[tuple[str, ...], Dict[str, List[Dict[str, Any]]]] = {}
    for item in eligible:
        profile = str(item.get("actual_profile") or "")
        if profile not in PROFILE_WEIGHTS:
            continue
        scenario = tuple(str(item.get(key) or "UNKNOWN") for key in
                         ("role", "responsibility", "difficulty", "risk_domain", "context_size"))
        scenario_groups.setdefault(scenario, {}).setdefault(profile, []).append(item)
    comparisons: List[Dict[str, Any]] = []
    ordered = sorted(PROFILE_ORDER, key=PROFILE_ORDER.get)
    for scenario, profiles in sorted(scenario_groups.items()):
        for lower, higher in zip(ordered, ordered[1:]):
            low = profiles.get(lower, []); high = profiles.get(higher, [])
            enough = len(low) >= minimum and len(high) >= minimum
            low_yield = (sum(item["value_score"] for item in low) / (len(low) * PROFILE_WEIGHTS[lower])) if low else 0.0
            high_yield = (sum(item["value_score"] for item in high) / (len(high) * PROFILE_WEIGHTS[higher])) if high else 0.0
            comparisons.append({
                "scenario": dict(zip(("role", "responsibility", "difficulty", "risk_domain", "context_size"), scenario)),
                "lower_profile": lower, "higher_profile": higher,
                "lower_samples": len(low), "higher_samples": len(high),
                "lower_value_per_unit": round(low_yield, 6), "higher_value_per_unit": round(high_yield, 6),
                "eligible": enough,
                "recommendation": (higher if enough and high_yield > low_yield else lower) if enough else "NO_CHANGE_INSUFFICIENT_DATA",
            })
    digest = hashlib.sha256(canonical_json(comparisons).encode("utf-8")).hexdigest()
    return {
        "schema_version": REPLAY_SCHEMA,
        "proposal_id": "OPT_" + digest,
        "proposal_type": "DELEGATION_MODEL_ROUTING_REVIEW",
        "execution_authorization": "NONE",
        "sample_count": len(eligible),
        "minimum_samples_per_profile": minimum,
        "comparisons": comparisons,
        "automatic_changes_applied": False,
    }
