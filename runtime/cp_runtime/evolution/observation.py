"""从项目上下文中的结构化执行记录生成自观察快照。"""
from __future__ import annotations

from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from statistics import mean
from typing import Any, DefaultDict, Dict, Iterable, List, Mapping, MutableMapping, Optional, Sequence, Set, Tuple

from .contracts import (
    ConfidenceLevel,
    EvidenceReference,
    EvolutionPolicy,
    PatternSignal,
    SelfObservationSnapshot,
    SignalType,
    canonical_json,
    new_id,
    parse_iso_datetime,
    sha256_hex,
)
from .storage import JsonLineRecord, StorageError, read_jsonl, safe_child

_ALLOWED_SOURCE_WORDS = (
    "feedback", "execution", "review", "evidence", "checkpoint", "audit", "outcome", "result"
)
_EXCLUDED_SOURCE_WORDS = (
    "proposal", "decision", "snapshot", "assessment", "knowledge-candidate"
)
_MODEL_RANK = {
    "luna-low": 1,
    "luna-medium": 2,
    "terra-medium": 3,
    "terra-high": 4,
}
_SUCCESS_OUTCOMES = {"accepted", "success", "succeeded", "pass", "passed", "ok", "completed", "complete"}
_UNKNOWN_OUTCOMES = {"", "unknown", "none", "n/a", "na"}
_TIME_FIELDS = (
    "timestamp", "created_at", "updated_at", "recorded_at", "completed_at", "finished_at", "observed_at"
)


class ObservationError(RuntimeError):
    """观察输入不足、损坏或越界。"""


def _to_int(value: Any, default: int = 0) -> int:
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, int):
        return value
    if isinstance(value, float) and value.is_integer():
        return int(value)
    if isinstance(value, str):
        try:
            return int(value.strip())
        except ValueError:
            return default
    return default


def _to_float(value: Any, default: float = 0.0) -> float:
    if isinstance(value, bool):
        return float(value)
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value.strip())
        except ValueError:
            return default
    return default


def _first_text(mapping: Mapping[str, Any], names: Sequence[str]) -> Optional[str]:
    for name in names:
        value = mapping.get(name)
        if value is not None and str(value).strip():
            return str(value).strip()
    return None


def _nested_mapping(mapping: Mapping[str, Any], name: str) -> Mapping[str, Any]:
    value = mapping.get(name)
    return value if isinstance(value, Mapping) else {}


def _extract_task_id(payload: Mapping[str, Any]) -> Optional[str]:
    direct = _first_text(payload, ("task_id", "taskId", "operation_id", "operationId"))
    if direct:
        return direct[:256]
    for container in ("task", "envelope", "task_envelope", "context"):
        nested = _nested_mapping(payload, container)
        value = _first_text(nested, ("task_id", "taskId", "operation_id", "operationId", "id"))
        if value:
            return value[:256]
    return None


def _extract_record_id(row: JsonLineRecord) -> str:
    direct = _first_text(row.payload, ("record_id", "event_id", "id", "feedback_id", "review_id"))
    if direct:
        return direct[:256]
    return "%s:%d:%s" % (row.relative_path, row.line_number, row.raw_hash[:12])


def _extract_timestamp(payload: Mapping[str, Any]) -> Optional[str]:
    for field in _TIME_FIELDS:
        value = payload.get(field)
        if isinstance(value, str) and value.strip():
            try:
                parsed = parse_iso_datetime(value.strip(), field)
                return parsed.isoformat()
            except Exception:
                continue
    for container in ("metadata", "context", "task", "envelope"):
        nested = _nested_mapping(payload, container)
        for field in _TIME_FIELDS:
            value = nested.get(field)
            if isinstance(value, str) and value.strip():
                try:
                    parsed = parse_iso_datetime(value.strip(), field)
                    return parsed.isoformat()
                except Exception:
                    continue
    return None


def _source_kind(path: str) -> str:
    lowered = path.lower()
    for name in ("feedback", "review", "evidence", "checkpoint", "audit"):
        if name in lowered:
            return name
    return "execution-record"


def _evidence(row: JsonLineRecord, task_id: Optional[str]) -> EvidenceReference:
    return EvidenceReference(
        source_kind=_source_kind(row.relative_path),
        source_path=row.relative_path,
        line_number=row.line_number,
        record_id=_extract_record_id(row),
        task_id=task_id,
        record_hash=row.raw_hash,
    )


def _normalize_model(value: Optional[str]) -> Optional[str]:
    if not value:
        return None
    normalized = value.strip().lower().replace("_", "-").replace(" ", "-")
    aliases = {
        "lunalow": "luna-low",
        "lunamedium": "luna-medium",
        "terramedium": "terra-medium",
        "terrahigh": "terra-high",
    }
    return aliases.get(normalized.replace("-", ""), normalized)


def _is_model_escalation(recommended: Optional[str], actual: Optional[str]) -> bool:
    recommended = _normalize_model(recommended)
    actual = _normalize_model(actual)
    if not recommended or not actual or recommended == actual:
        return False
    if recommended in _MODEL_RANK and actual in _MODEL_RANK:
        return _MODEL_RANK[actual] > _MODEL_RANK[recommended]
    return False


def _failure_labels(payload: Mapping[str, Any]) -> Set[str]:
    labels: Set[str] = set()
    for field in ("failure_code", "error_code", "error_type", "failure_type", "failure_category"):
        value = payload.get(field)
        if value is not None and str(value).strip():
            labels.add("%s:%s" % (field, str(value).strip().lower()[:160]))
    categories = payload.get("blocking_categories")
    if isinstance(categories, (list, tuple)):
        for value in categories:
            if str(value).strip():
                labels.add("blocking_category:%s" % str(value).strip().lower()[:160])
    findings = payload.get("findings")
    if isinstance(findings, list):
        for finding in findings:
            if not isinstance(finding, Mapping):
                continue
            severity = str(finding.get("severity", "")).strip().upper()
            if severity in {"BLOCKING", "CRITICAL", "HIGH"}:
                category = str(finding.get("category") or finding.get("type") or "unspecified").strip().lower()
                labels.add("finding:%s" % category[:160])
    outcome = _first_text(payload, ("quality_outcome", "outcome", "result", "status"))
    if outcome:
        normalized = outcome.strip().lower()
        if normalized not in _SUCCESS_OUTCOMES and normalized not in _UNKNOWN_OUTCOMES:
            labels.add("outcome:%s" % normalized[:160])
    blocking = _to_int(payload.get("blocking_findings"), 0)
    if blocking > 0:
        labels.add("blocking_findings")
    return labels


def _reviewer_results(payload: Mapping[str, Any]) -> List[Mapping[str, Any]]:
    for name in ("reviewer_results", "review_results", "reviews"):
        value = payload.get(name)
        if isinstance(value, list):
            return [item for item in value if isinstance(item, Mapping)]
    review = payload.get("review")
    if isinstance(review, Mapping):
        for name in ("reviewer_results", "results", "reviews"):
            value = review.get(name)
            if isinstance(value, list):
                return [item for item in value if isinstance(item, Mapping)]
    return []


def _confidence(independent_tasks: int, occurrences: int, source_count: int, window_days: int, policy: EvolutionPolicy) -> ConfidenceLevel:
    if independent_tasks >= 20 and source_count >= 2 and window_days >= 30:
        return ConfidenceLevel.L4
    if independent_tasks >= policy.min_independent_tasks and occurrences >= policy.repeated_failure_count:
        return ConfidenceLevel.L3
    if independent_tasks >= 2 and occurrences >= 2:
        return ConfidenceLevel.L2
    if occurrences > 0:
        return ConfidenceLevel.L1
    return ConfidenceLevel.L0


def discover_sources(
    project_dir: Path,
    policy: EvolutionPolicy,
    explicit_sources: Optional[Sequence[str]] = None,
) -> List[Path]:
    project_dir = Path(project_dir).resolve()
    sources: List[Path] = []
    if explicit_sources:
        for raw in explicit_sources:
            candidate = safe_child(project_dir, raw)
            if not candidate.exists() or not candidate.is_file():
                raise ObservationError("显式数据源不存在: %s" % raw)
            if candidate.suffix.lower() != ".jsonl":
                raise ObservationError("V5.1 自观察只接受 JSONL 数据源: %s" % raw)
            sources.append(candidate)
    else:
        for candidate in sorted(project_dir.rglob("*.jsonl")):
            try:
                relative = candidate.resolve().relative_to(project_dir).as_posix()
            except ValueError:
                continue
            parts = relative.split("/")
            if "evolution" in {part.lower() for part in parts[:-1]}:
                continue
            lowered = relative.lower()
            if any(word in lowered for word in _EXCLUDED_SOURCE_WORDS):
                continue
            if not any(word in lowered for word in _ALLOWED_SOURCE_WORDS):
                continue
            if len(parts) > 5:
                continue
            sources.append(candidate)
    unique: List[Path] = []
    seen: Set[str] = set()
    for source in sources:
        resolved = source.resolve()
        key = str(resolved)
        if key in seen:
            continue
        seen.add(key)
        unique.append(resolved)
    if len(unique) > policy.max_source_files:
        raise ObservationError("自观察数据源数量超过策略上限: %d" % policy.max_source_files)
    return unique


def observe_project(
    project_id: str,
    project_dir: Path,
    policy: Optional[EvolutionPolicy] = None,
    explicit_sources: Optional[Sequence[str]] = None,
    observed_at: Optional[str] = None,
) -> SelfObservationSnapshot:
    policy = policy or EvolutionPolicy()
    project_dir = Path(project_dir).resolve()
    sources = discover_sources(project_dir, policy, explicit_sources)
    warnings: List[str] = []
    if not sources:
        warnings.append("没有发现允许的 JSONL 执行数据源；当前快照不会生成优化提案")

    all_rows: List[JsonLineRecord] = []
    for source in sources:
        rows = read_jsonl(
            source,
            relative_to=project_dir,
            max_bytes=policy.max_source_file_bytes,
            max_records=policy.max_record_count,
        )
        all_rows.extend(rows)
        if len(all_rows) > policy.max_record_count:
            raise ObservationError("全部数据源记录总数超过策略上限")

    task_ids: Set[str] = set()
    timestamps: List[datetime] = []
    accepted_count = 0
    negative_count = 0
    known_outcome_count = 0
    routing_deviation_count = 0
    routing_known_count = 0
    model_escalation_count = 0
    model_comparison_count = 0
    repair_rounds: List[int] = []
    high_repair_count = 0
    failure_counter: Counter[str] = Counter()
    failure_tasks: DefaultDict[str, Set[str]] = defaultdict(set)
    failure_evidence: DefaultDict[str, List[EvidenceReference]] = defaultdict(list)
    model_evidence: List[EvidenceReference] = []
    routing_evidence: List[EvidenceReference] = []
    repair_evidence: List[EvidenceReference] = []
    negative_evidence: List[EvidenceReference] = []
    reviewer_stats: Dict[str, Dict[str, Any]] = {}
    skill_usage: Counter[str] = Counter()
    records_without_task = 0

    for row in all_rows:
        payload = row.payload
        task_id = _extract_task_id(payload)
        if task_id:
            task_ids.add(task_id)
        else:
            records_without_task += 1
        evidence = _evidence(row, task_id)
        timestamp = _extract_timestamp(payload)
        if timestamp:
            try:
                timestamps.append(parse_iso_datetime(timestamp, "timestamp"))
            except Exception:
                pass

        outcome = _first_text(payload, ("quality_outcome", "outcome", "result", "status"))
        if outcome:
            normalized_outcome = outcome.lower()
            if normalized_outcome not in _UNKNOWN_OUTCOMES:
                known_outcome_count += 1
                if normalized_outcome in _SUCCESS_OUTCOMES:
                    accepted_count += 1
                else:
                    negative_count += 1
                    if len(negative_evidence) < 50:
                        negative_evidence.append(evidence)

        routing = _first_text(payload, ("routing_deviation", "route_deviation", "routingDeviation"))
        if routing is not None:
            routing_known_count += 1
            if routing.strip().lower() not in {"none", "no", "false", "0", "matched", "no_deviation"}:
                routing_deviation_count += 1
                if len(routing_evidence) < 50:
                    routing_evidence.append(evidence)

        recommended_model = _first_text(payload, ("recommended_model", "suggested_model", "recommendedModel"))
        actual_model = _first_text(payload, ("actual_model", "selected_model", "actualModel", "model_profile"))
        if recommended_model and actual_model:
            model_comparison_count += 1
            if _is_model_escalation(recommended_model, actual_model):
                model_escalation_count += 1
                if len(model_evidence) < 50:
                    model_evidence.append(evidence)

        repair = _to_int(payload.get("repair_rounds", payload.get("repairRounds", 0)), 0)
        if repair >= 0 and ("repair_rounds" in payload or "repairRounds" in payload):
            repair_rounds.append(repair)
            if repair >= policy.high_repair_rounds:
                high_repair_count += 1
                if len(repair_evidence) < 50:
                    repair_evidence.append(evidence)

        for label in _failure_labels(payload):
            failure_counter[label] += 1
            if task_id:
                failure_tasks[label].add(task_id)
            if len(failure_evidence[label]) < 50:
                failure_evidence[label].append(evidence)

        for result in _reviewer_results(payload):
            reviewer = _first_text(result, ("reviewer", "reviewer_id", "name", "id"))
            if not reviewer:
                continue
            reviewer = reviewer[:256]
            stats = reviewer_stats.setdefault(reviewer, {
                "invocations": 0,
                "blocking_findings": 0,
                "nonblocking_findings": 0,
                "tasks": set(),
                "evidence": [],
            })
            stats["invocations"] += 1
            stats["blocking_findings"] += max(0, _to_int(result.get("blocking_findings"), 0))
            stats["nonblocking_findings"] += max(0, _to_int(result.get("nonblocking_findings"), 0))
            findings = result.get("findings")
            if isinstance(findings, list):
                for finding in findings:
                    if not isinstance(finding, Mapping):
                        continue
                    severity = str(finding.get("severity", "")).upper()
                    if severity in {"BLOCKING", "CRITICAL", "HIGH"}:
                        stats["blocking_findings"] += 1
                    else:
                        stats["nonblocking_findings"] += 1
            if task_id:
                stats["tasks"].add(task_id)
            if len(stats["evidence"]) < 50:
                stats["evidence"].append(evidence)

        skills = payload.get("skills")
        if isinstance(skills, list):
            for skill in skills:
                if str(skill).strip():
                    skill_usage[str(skill).strip()[:256]] += 1
        else:
            skill = _first_text(payload, ("skill", "selected_skill", "primary_skill"))
            if skill:
                skill_usage[skill[:256]] += 1

    if records_without_task:
        warnings.append("%d 条记录缺少 task_id，不会被计入独立任务置信度" % records_without_task)

    source_count = len(sources)
    if timestamps:
        window_start_dt = min(timestamps)
        window_end_dt = max(timestamps)
        window_start = window_start_dt.isoformat()
        window_end = window_end_dt.isoformat()
        window_days = max(0, (window_end_dt - window_start_dt).days)
    else:
        window_start = None
        window_end = None
        window_days = 0
        if all_rows:
            warnings.append("数据记录缺少可解析的带时区时间，无法形成长期窗口置信度")

    model_rate = (float(model_escalation_count) / model_comparison_count) if model_comparison_count else 0.0
    routing_rate = (float(routing_deviation_count) / routing_known_count) if routing_known_count else 0.0
    negative_rate = (float(negative_count) / known_outcome_count) if known_outcome_count else 0.0
    repair_average = mean(repair_rounds) if repair_rounds else 0.0
    high_repair_rate = (float(high_repair_count) / len(repair_rounds)) if repair_rounds else 0.0

    normalized_reviewer_metrics: Dict[str, Any] = {}
    for reviewer, stats in sorted(reviewer_stats.items()):
        total_findings = stats["blocking_findings"] + stats["nonblocking_findings"]
        invocations = stats["invocations"]
        normalized_reviewer_metrics[reviewer] = {
            "invocations": invocations,
            "blocking_findings": stats["blocking_findings"],
            "nonblocking_findings": stats["nonblocking_findings"],
            "findings_per_invocation": (float(total_findings) / invocations) if invocations else 0.0,
            "independent_task_count": len(stats["tasks"]),
        }

    metrics: Dict[str, Any] = {
        "policy_version": policy.policy_version,
        "source_file_count": source_count,
        "record_count": len(all_rows),
        "task_count": len(task_ids),
        "records_without_task_id": records_without_task,
        "window_days": window_days,
        "known_outcome_count": known_outcome_count,
        "accepted_count": accepted_count,
        "negative_outcome_count": negative_count,
        "negative_outcome_rate": round(negative_rate, 6),
        "model_comparison_count": model_comparison_count,
        "model_escalation_count": model_escalation_count,
        "model_escalation_rate": round(model_rate, 6),
        "routing_known_count": routing_known_count,
        "routing_deviation_count": routing_deviation_count,
        "routing_deviation_rate": round(routing_rate, 6),
        "repair_observation_count": len(repair_rounds),
        "repair_round_average": round(float(repair_average), 6),
        "high_repair_task_count": high_repair_count,
        "high_repair_rate": round(high_repair_rate, 6),
        "failure_patterns": dict(sorted(failure_counter.items())),
        "reviewer_stats": normalized_reviewer_metrics,
        "skill_usage": dict(sorted(skill_usage.items())),
    }

    signals: List[PatternSignal] = []
    for label, count in sorted(failure_counter.items(), key=lambda item: (-item[1], item[0])):
        independent = len(failure_tasks[label])
        if count < policy.repeated_failure_count or independent < policy.min_independent_tasks:
            continue
        confidence = _confidence(independent, count, source_count, window_days, policy)
        signal_id = new_id("SIG", "%s|%s|%s" % (project_id, SignalType.REPEATED_FAILURE.value, label))
        signals.append(PatternSignal(
            signal_id=signal_id,
            signal_type=SignalType.REPEATED_FAILURE,
            target=label,
            occurrence_count=count,
            independent_task_count=independent,
            rate=(float(count) / len(all_rows)) if all_rows else 0.0,
            confidence=confidence,
            summary="失败模式 %s 在 %d 个独立任务中重复出现 %d 次" % (label, independent, count),
            evidence=tuple(failure_evidence[label]),
            metrics={"window_days": window_days, "record_count": len(all_rows)},
        ))

    if model_comparison_count >= policy.min_records and model_rate >= policy.model_escalation_rate:
        independent = len({ref.task_id for ref in model_evidence if ref.task_id})
        signals.append(PatternSignal(
            signal_id=new_id("SIG", "%s|%s" % (project_id, SignalType.MODEL_ESCALATION.value)),
            signal_type=SignalType.MODEL_ESCALATION,
            target="model-routing",
            occurrence_count=model_escalation_count,
            independent_task_count=independent,
            rate=model_rate,
            confidence=_confidence(independent, model_escalation_count, source_count, window_days, policy),
            summary="%d/%d 次模型路由发生向上升级，升级率 %.2f%%" % (model_escalation_count, model_comparison_count, model_rate * 100),
            evidence=tuple(model_evidence),
            metrics={"comparison_count": model_comparison_count, "window_days": window_days},
        ))

    if routing_known_count >= policy.min_records and routing_rate >= policy.routing_deviation_rate:
        independent = len({ref.task_id for ref in routing_evidence if ref.task_id})
        signals.append(PatternSignal(
            signal_id=new_id("SIG", "%s|%s" % (project_id, SignalType.ROUTING_DEVIATION.value)),
            signal_type=SignalType.ROUTING_DEVIATION,
            target="skill-routing",
            occurrence_count=routing_deviation_count,
            independent_task_count=independent,
            rate=routing_rate,
            confidence=_confidence(independent, routing_deviation_count, source_count, window_days, policy),
            summary="%d/%d 次记录存在路由偏差，偏差率 %.2f%%" % (routing_deviation_count, routing_known_count, routing_rate * 100),
            evidence=tuple(routing_evidence),
            metrics={"known_count": routing_known_count, "window_days": window_days},
        ))

    if repair_rounds and (repair_average >= policy.excessive_repair_average or high_repair_rate >= 0.30):
        independent = len({ref.task_id for ref in repair_evidence if ref.task_id})
        signals.append(PatternSignal(
            signal_id=new_id("SIG", "%s|%s" % (project_id, SignalType.EXCESSIVE_REPAIR.value)),
            signal_type=SignalType.EXCESSIVE_REPAIR,
            target="review-repair-loop",
            occurrence_count=high_repair_count,
            independent_task_count=independent,
            rate=high_repair_rate,
            confidence=_confidence(independent, high_repair_count, source_count, window_days, policy),
            summary="平均修复轮次 %.2f，高修复任务占比 %.2f%%" % (repair_average, high_repair_rate * 100),
            evidence=tuple(repair_evidence),
            metrics={"average_repair_rounds": repair_average, "repair_observation_count": len(repair_rounds)},
        ))

    for reviewer, stats in sorted(reviewer_stats.items()):
        invocations = stats["invocations"]
        total_findings = stats["blocking_findings"] + stats["nonblocking_findings"]
        yield_rate = (float(total_findings) / invocations) if invocations else 0.0
        if invocations < policy.reviewer_min_invocations or yield_rate > policy.reviewer_low_yield_rate:
            continue
        independent = len(stats["tasks"])
        signals.append(PatternSignal(
            signal_id=new_id("SIG", "%s|%s|%s" % (project_id, SignalType.LOW_REVIEWER_YIELD.value, reviewer)),
            signal_type=SignalType.LOW_REVIEWER_YIELD,
            target="reviewer:%s" % reviewer,
            occurrence_count=invocations,
            independent_task_count=independent,
            rate=min(1.0, yield_rate),
            confidence=_confidence(independent, invocations, source_count, window_days, policy),
            summary="Reviewer %s 调用 %d 次，仅产生 %d 条发现" % (reviewer, invocations, total_findings),
            evidence=tuple(stats["evidence"]),
            metrics={
                "invocations": invocations,
                "findings": total_findings,
                "findings_per_invocation": yield_rate,
                "window_days": window_days,
            },
        ))

    if known_outcome_count >= policy.min_records and negative_rate >= policy.negative_outcome_rate:
        independent = len({ref.task_id for ref in negative_evidence if ref.task_id})
        signals.append(PatternSignal(
            signal_id=new_id("SIG", "%s|%s" % (project_id, SignalType.NEGATIVE_OUTCOME.value)),
            signal_type=SignalType.NEGATIVE_OUTCOME,
            target="quality-outcome",
            occurrence_count=negative_count,
            independent_task_count=independent,
            rate=negative_rate,
            confidence=_confidence(independent, negative_count, source_count, window_days, policy),
            summary="%d/%d 个已知结果为非成功状态，比例 %.2f%%" % (negative_count, known_outcome_count, negative_rate * 100),
            evidence=tuple(negative_evidence),
            metrics={"known_outcome_count": known_outcome_count, "window_days": window_days},
        ))

    if len(all_rows) < policy.min_records:
        warnings.append("有效记录少于 %d 条，只保留观察快照，不建议形成优化提案" % policy.min_records)
    if len(task_ids) < policy.min_independent_tasks:
        warnings.append("独立任务少于 %d 个，所有长期模式置信度受限" % policy.min_independent_tasks)

    return SelfObservationSnapshot.create(
        project_id=project_id,
        source_files=[source.resolve().relative_to(project_dir).as_posix() for source in sources],
        record_count=len(all_rows),
        task_count=len(task_ids),
        metrics=metrics,
        signals=signals,
        warnings=warnings,
        window_start=window_start,
        window_end=window_end,
        observed_at=observed_at,
    )
