"""从项目上下文中的结构化执行记录生成自观察快照。"""
from __future__ import annotations

import json
import math
import re
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
from ..event_v2 import read_event_chain, EventContractError

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


def _wilson(successes: int, total: int, z: float = 1.959963984540054) -> Tuple[Optional[float], Optional[float]]:
    if total <= 0:
        return None, None
    proportion = float(successes) / total
    denominator = 1.0 + z * z / total
    centre = proportion + z * z / (2.0 * total)
    margin = z * math.sqrt((proportion * (1.0 - proportion) + z * z / (4.0 * total)) / total)
    return max(0.0, (centre - margin) / denominator), min(1.0, (centre + margin) / denominator)


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
    outcome = _first_text(payload, ("quality_outcome", "terminal_outcome", "outcome", "result"))
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
            has_segments = candidate.name == "task-outcome-v2.jsonl" and any(
                candidate.parent.glob(candidate.stem + ".segment-*" + candidate.suffix))
            if (not candidate.exists() or not candidate.is_file()) and not has_segments:
                raise ObservationError("显式数据源不存在: %s" % raw)
            if candidate.suffix.lower() != ".jsonl":
                raise ObservationError("V6.0 自观察只接受 JSONL 数据源: %s" % raw)
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
            segment = re.fullmatch(r"(.+)\.segment-\d{6}(\.jsonl)", candidate.name)
            sources.append(candidate.with_name(segment.group(1) + segment.group(2)) if segment else candidate)
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



def _expected_repo_fingerprint(project_dir: Path) -> Optional[str]:
    profile = project_dir / "project-profile.json"
    if not profile.is_file():
        return None
    try:
        import json
        raw = json.loads(profile.read_text(encoding="utf-8-sig"))
        identity = raw.get("identity") or {}
        repo_path = str(identity.get("repo_path") or "").strip()
        remote = str(identity.get("remote_origin") or "").strip()
        if not repo_path:
            return None
        normalized = str(Path(repo_path).expanduser().resolve(strict=False))
        return "sha256:" + sha256_hex(normalized + "\n" + remote)
    except Exception:
        return None


def _with_hashed_v2_session_ids(source: Path, rows: Sequence[JsonLineRecord]) -> List[JsonLineRecord]:
    """恢复仅用于分组的 session 稳定代号，绝不把原 session_id 写入快照或日志。"""
    raw_by_line: Dict[int, Mapping[str, Any]] = {}
    for number, line in enumerate(source.read_text(encoding="utf-8").splitlines(), 1):
        if line.strip():
            try:
                raw_by_line[number] = json.loads(line)
            except json.JSONDecodeError:
                continue
    restored: List[JsonLineRecord] = []
    for row in rows:
        raw = raw_by_line.get(row.line_number, {})
        session_id = str(raw.get("session_id", "")).strip() if isinstance(raw, Mapping) else ""
        if str(row.payload.get("schema_version", "")) == "2.0" and session_id:
            payload = dict(row.payload)
            payload["session_id"] = "session-" + sha256_hex(session_id)[:16]
            restored.append(JsonLineRecord(row.relative_path, row.line_number, payload, row.raw_hash))
        else:
            restored.append(row)
    return restored


def _validate_and_aggregate_v2(rows: Sequence[JsonLineRecord], project_id: str, project_dir: Path) -> Tuple[List[JsonLineRecord], int, int, Mapping[str, Any]]:
    """V6：严格项目隔离、event_id 去重，并将生命周期事件按 task_id 折叠。"""
    expected_fp = _expected_repo_fingerprint(project_dir)
    observed_fp: Optional[str] = expected_fp
    legacy: List[JsonLineRecord] = []
    events: List[JsonLineRecord] = []
    seen_event_ids: Set[str] = set()
    raw_v2 = 0
    duplicate_v2 = 0
    binding_count = 0
    for row in rows:
        payload = row.payload
        row_project = _first_text(payload, ("project_id",))
        if row_project and row_project != project_id:
            raise ObservationError("检测到跨项目记录：%s != %s（%s:%d）" % (row_project, project_id, row.relative_path, row.line_number))
        is_v2 = str(payload.get("schema_version", "")) == "2.0" and bool(payload.get("event_id"))
        if not is_v2:
            legacy.append(row)
            continue
        raw_v2 += 1
        repo_fp = _first_text(payload, ("repo_fingerprint",))
        if not repo_fp:
            raise ObservationError("TaskOutcomeEvent V2 缺少 repo_fingerprint：%s:%d" % (row.relative_path, row.line_number))
        if observed_fp is None:
            observed_fp = repo_fp
        if repo_fp != observed_fp:
            raise ObservationError("检测到跨仓库事件：%s != %s" % (repo_fp, observed_fp))
        binding_count += 1
        event_id = str(payload.get("event_id"))
        if event_id in seen_event_ids:
            duplicate_v2 += 1
            continue
        seen_event_ids.add(event_id)
        events.append(row)

    grouped: DefaultDict[Tuple[str, str], List[JsonLineRecord]] = defaultdict(list)
    for row in events:
        payload = row.payload
        task_id = _extract_task_id(payload) or _first_text(payload, ("turn_id", "session_id")) or str(payload.get("event_id"))
        session_id = str(payload.get("session_id", "")).strip()
        grouped[(session_id, task_id)].append(row)

    collapsed: List[JsonLineRecord] = []
    missing_events: Counter[str] = Counter()
    out_of_order = 0
    session_events: DefaultDict[str, List[str]] = defaultdict(list)
    session_tasks: DefaultDict[str, Set[str]] = defaultdict(set)
    task_sessions: DefaultDict[str, Set[str]] = defaultdict(set)
    complete_tasks = 0
    substantive_task_count = 0
    duplicate_event_count = 0
    for row in events:
        payload = row.payload
        event_type = str(payload.get("event_type", "")).upper()
        session_id = str(payload.get("session_id", "")).strip()
        task_id = _extract_task_id(payload) or _first_text(payload, ("turn_id",))
        if session_id:
            session_events[session_id].append(event_type)
            if task_id and event_type != "SESSION_ENDED":
                session_tasks[session_id].add(task_id)
                task_sessions[task_id].add(session_id)
    for (_group_session_id, task_id), group in sorted(grouped.items()):
        event_types = [str(row.payload.get("event_type", "")).upper() for row in group]
        event_type_set = set(event_types)
        if event_type_set <= {"SESSION_ENDED"}:
            continue
        substantive_task_count += 1
        if event_type_set & {"TURN_OPENED", "TASK_COMPLETED"}:
            required = {"TURN_OPENED", "TASK_COMPLETED"}
            if event_type_set & {"SUBAGENT_STARTED", "SUBAGENT_STOPPED"}:
                required.update(("SUBAGENT_STARTED", "SUBAGENT_STOPPED"))
        elif event_type_set & {"SUBAGENT_STARTED", "SUBAGENT_STOPPED"}:
            required = {"SUBAGENT_STARTED", "SUBAGENT_STOPPED"}
        else:
            required = set()
        complete_tasks += int(required.issubset(event_types))
        for missing in sorted(required - set(event_types)):
            missing_events[missing] += 1
        counts = Counter(event_types)
        duplicate_event_count += sum(max(0, count - 1) for count in counts.values())
        positions = {event_type: index for index, event_type in enumerate(event_types)}
        ordered = [positions[name] for name in ("TURN_OPENED", "SUBAGENT_STARTED", "SUBAGENT_STOPPED", "TASK_COMPLETED") if name in positions]
        if ordered != sorted(ordered):
            out_of_order += 1
        terminal = None
        for row in group:
            if str(row.payload.get("event_type", "")).upper() == "TASK_COMPLETED":
                terminal = row
        base = terminal or group[-1]
        merged = dict(base.payload)
        merged["task_id"] = task_id
        merged["event_type"] = "TASK_AGGREGATE"
        merged["lifecycle_event_count"] = len(group)
        merged["actual_reviewers"] = sum(1 for row in group if str(row.payload.get("event_type", "")).upper() == "SUBAGENT_STARTED")
        if terminal is not None:
            merged["terminal_outcome"] = str(terminal.payload.get("terminal_outcome") or "UNKNOWN")
            for key in ("blocking_findings", "nonblocking_findings", "repair_rounds", "recommended_model", "actual_model", "actual_reasoning_effort"):
                if key in terminal.payload:
                    merged[key] = terminal.payload[key]
        raw_hash = sha256_hex(canonical_json(merged))
        collapsed.append(JsonLineRecord(relative_path=base.relative_path, line_number=base.line_number, payload=merged, raw_hash=raw_hash))
    sessions_with_end = sum(1 for types in session_events.values() if "SESSION_ENDED" in types)
    task_session_conflicts = sum(1 for sessions in task_sessions.values() if len(sessions) > 1)
    missing_session_bindings = sum(
        1
        for row in events
        if not str(row.payload.get("session_id", "")).strip()
        and str(row.payload.get("event_type", "")).upper() != "SESSION_ENDED"
    )
    diagnostics = {
        "v2_task_count": substantive_task_count, "lifecycle_complete_task_count": complete_tasks,
        "lifecycle_completeness_rate": (float(complete_tasks) / substantive_task_count) if substantive_task_count else 0.0,
        "missing_event_categories": dict(sorted(missing_events.items())), "out_of_order_task_count": out_of_order,
        "duplicate_event_count": duplicate_event_count,
        "session_count": len(session_events), "sessions_with_end_count": sessions_with_end,
        "session_end_coverage": (float(sessions_with_end) / len(session_events)) if session_events else 0.0,
        "cross_task_session_leakage_count": task_session_conflicts,
        "cross_session_task_leakage_count": missing_session_bindings,
        "task_session_conflict_count": task_session_conflicts,
        "missing_session_binding_count": missing_session_bindings,
        "multi_task_session_count": sum(1 for tasks in session_tasks.values() if len(tasks) > 1),
        "project_repo_binding_coverage": (float(binding_count) / raw_v2) if raw_v2 else 0.0,
    }
    return legacy + collapsed, raw_v2, duplicate_v2, diagnostics


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
        is_task_outcome = source.name == "task-outcome-v2.jsonl"
        if is_task_outcome:
            try:
                import os
                chain_data = read_event_chain(source, os.environ.get("CP_ASSISTANT_HMAC_KEY"), allow_duplicate_ids=True)
            except EventContractError as exc:
                raise ObservationError("TaskOutcomeEvent V2 完整性校验失败: %s" % exc) from exc
            total_bytes = sum(Path(item).stat().st_size for item in chain_data["files"])
            if total_bytes > policy.max_source_file_bytes:
                raise ObservationError("TaskOutcomeEvent V2 分段总大小超过策略上限")
            if len(chain_data["events"]) > policy.max_record_count:
                raise ObservationError("TaskOutcomeEvent V2 记录数超过策略上限")
            relative = source.resolve(strict=False).relative_to(project_dir).as_posix()
            rows = [JsonLineRecord(relative_path=relative, line_number=index,
                                   payload=item, raw_hash=sha256_hex(canonical_json(item)))
                    for index, item in enumerate(chain_data["events"], 1)]
        else:
            rows = read_jsonl(
                source,
                relative_to=project_dir,
                max_bytes=policy.max_source_file_bytes,
                max_records=policy.max_record_count,
            )
        rows = _with_hashed_v2_session_ids(source, rows)
        # V6 Hook 事件采用独立 hash-chain/HMAC 合同；任何链路损坏都失败关闭。
        if rows and all(str(row.payload.get("schema_version", "")) == "2.0" and row.payload.get("event_id") for row in rows):
            try:
                chain_result = chain_data if is_task_outcome else {"duplicate_event_id_count": 0}
                if chain_result.get("duplicate_event_id_count"):
                    warnings.append("TaskOutcomeEvent V2 检测到重复 event_id，完整链验证后按 event_id 去重")
            except EventContractError as exc:
                raise ObservationError("TaskOutcomeEvent V2 完整性校验失败: %s" % exc) from exc
        all_rows.extend(rows)
        if len(all_rows) > policy.max_record_count:
            raise ObservationError("全部数据源记录总数超过策略上限")

    raw_record_count = len(all_rows)
    all_rows, raw_v2_event_count, duplicate_v2_event_count, v2_diagnostics = _validate_and_aggregate_v2(all_rows, project_id, project_dir)
    if duplicate_v2_event_count:
        warnings.append("%d 条重复 event_id 已在聚合前去重" % duplicate_v2_event_count)
    if v2_diagnostics["missing_event_categories"]:
        warnings.append("生命周期缺失事件：%s" % v2_diagnostics["missing_event_categories"])
    if v2_diagnostics["out_of_order_task_count"]:
        warnings.append("%d 个任务的生命周期事件乱序" % v2_diagnostics["out_of_order_task_count"])
    if v2_diagnostics["duplicate_event_count"]:
        warnings.append("%d 个同任务同类型生命周期事件重复" % v2_diagnostics["duplicate_event_count"])
    if v2_diagnostics["cross_task_session_leakage_count"] or v2_diagnostics["cross_session_task_leakage_count"]:
        warnings.append("检测到跨任务/跨 session 串线：task->session=%d，session->task=%d" % (v2_diagnostics["cross_task_session_leakage_count"], v2_diagnostics["cross_session_task_leakage_count"]))

    task_ids: Set[str] = set()
    timestamps: List[datetime] = []
    accepted_count = 0
    negative_count = 0
    known_outcome_count = 0
    routing_deviation_count = 0
    routing_known_count = 0
    model_escalation_count = 0
    model_comparison_count = 0
    actual_model_count = 0
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
    reviewer_result_identities: Dict[Tuple[str, str, str], str] = {}
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

        outcome = _first_text(payload, ("quality_outcome", "terminal_outcome", "outcome", "result"))
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
        if actual_model:
            actual_model_count += 1

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
                "accepted": 0, "rejected": 0, "duplicate": 0, "repaired": 0,
                "regressions_prevented": 0, "reported_regressions_prevented": 0,
                "regression_prevention_claim_count": 0, "regression_prevention_evidence_count": 0,
                "duration_ms": 0, "cost_units": 0.0,
                "attribution_count": 0,
                "labeled_finding_count": 0, "unattributed_result_count": 0,
                "duplicate_result_count": 0, "conflicting_result_count": 0,
                "difficulty_distribution": Counter(), "finding_clusters": Counter(),
                "adoption_reasons": Counter(),
            })
            result_id = _first_text(result, ("result_id", "review_result_id"))
            review_round = _first_text(result, ("review_round", "round"))
            packet_hash = _first_text(result, ("packet_sha256", "packet_hash"))
            if not result_id and task_id and review_round and packet_hash:
                result_id = "derived:" + sha256_hex("%s|%s|%s|%s" % (task_id, reviewer, review_round, packet_hash))
            if not task_id or not result_id:
                stats["unattributed_result_count"] += 1
                continue
            identity = (task_id, reviewer, result_id)
            result_hash = sha256_hex(canonical_json(result))
            previous_result_hash = reviewer_result_identities.get(identity)
            if previous_result_hash is not None:
                if previous_result_hash == result_hash:
                    stats["duplicate_result_count"] += 1
                else:
                    stats["conflicting_result_count"] += 1
                continue
            reviewer_result_identities[identity] = result_hash
            stats["invocations"] += 1
            for name in ("accepted", "rejected", "duplicate", "repaired"):
                stats[name] += max(0, _to_int(result.get(name), 0))
            stats["reported_regressions_prevented"] += max(0, _to_int(result.get("regressions_prevented"), 0))
            difficulty = str(result.get("task_difficulty") or "UNKNOWN").strip().upper()
            if difficulty not in {"LOW", "MEDIUM", "HIGH", "CRITICAL"}:
                difficulty = "UNKNOWN"
            stats["difficulty_distribution"][difficulty] += 1
            stats["duration_ms"] += max(0, _to_int(result.get("duration_ms"), 0))
            stats["cost_units"] += max(0.0, _to_float(result.get("cost_units"), 0.0))
            if any(name in result for name in ("accepted", "rejected", "duplicate", "repaired", "regressions_prevented")):
                stats["attribution_count"] += 1
                stats["labeled_finding_count"] += sum(max(0, _to_int(result.get(name), 0))
                                                        for name in ("accepted", "rejected", "duplicate"))
            findings = result.get("findings")
            if isinstance(findings, list):
                # V6：明细是权威来源，避免与汇总数字重复计数。
                for finding in findings:
                    if not isinstance(finding, Mapping):
                        continue
                    severity = str(finding.get("severity", "")).upper()
                    if severity in {"BLOCKING", "CRITICAL", "HIGH"}:
                        stats["blocking_findings"] += 1
                    else:
                        stats["nonblocking_findings"] += 1
                    if any(str(finding.get(name) or "").strip() for name in ("status", "outcome", "disposition", "label")):
                        stats["labeled_finding_count"] += 1
                    cluster = _first_text(finding, ("root_cause_group", "cluster_id", "finding_fingerprint"))
                    if cluster:
                        stats["finding_clusters"][sha256_hex(cluster)] += 1
                    disposition = str(_first_text(finding, ("disposition", "status", "outcome", "label")) or "").upper()
                    reason = str(_first_text(finding, ("adoption_reason", "disposition_reason")) or "UNSPECIFIED").upper()
                    if reason not in {"CORRECTNESS", "SECURITY", "COMPATIBILITY", "PERFORMANCE", "DATA_CONTRACT",
                                      "REGRESSION_PREVENTION", "OUT_OF_SCOPE", "DUPLICATE", "INSUFFICIENT_EVIDENCE",
                                      "DEFERRED", "REJECTED", "UNSPECIFIED"}:
                        reason = "UNSPECIFIED"
                    if disposition in {"ACCEPTED", "REPAIRED", "REGRESSION_PREVENTED", "REJECTED", "DEFERRED", "OUT_OF_SCOPE"}:
                        stats["adoption_reasons"][reason] += 1
                    regression_claim = bool(finding.get("regression_prevented")) or disposition == "REGRESSION_PREVENTED"
                    if regression_claim:
                        stats["regression_prevention_claim_count"] += 1
                        references = finding.get("regression_evidence") or finding.get("regression_test_refs") or []
                        if isinstance(references, list) and any(isinstance(item, Mapping) or str(item).strip() for item in references):
                            stats["regression_prevention_evidence_count"] += 1
                            stats["regressions_prevented"] += 1
            else:
                stats["blocking_findings"] += max(0, _to_int(result.get("blocking_findings"), 0))
                stats["nonblocking_findings"] += max(0, _to_int(result.get("nonblocking_findings"), 0))
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
        task_count = len(stats["tasks"])
        attribution_coverage = float(stats["attribution_count"]) / invocations if invocations else 0.0
        adoption_total = stats["accepted"] + stats["rejected"]
        adoption_low, adoption_high = _wilson(stats["accepted"], adoption_total)
        duplicate_rate = float(stats["duplicate"]) / max(1, total_findings)
        clustered_findings = sum(stats["finding_clusters"].values())
        duplicate_cluster_findings = sum(max(0, count - 1) for count in stats["finding_clusters"].values())
        clustered_duplicate_rate = float(duplicate_cluster_findings) / clustered_findings if clustered_findings else None
        effective_duplicate_rate = max(duplicate_rate, clustered_duplicate_rate or 0.0)
        benefit_proxy = float(stats["repaired"] + stats["regressions_prevented"]) / max(1.0, stats["cost_units"])
        sample_sufficient = (invocations >= policy.reviewer_min_invocations
                             and task_count >= policy.reviewer_min_independent_tasks
                             and attribution_coverage >= policy.reviewer_min_attribution_coverage
                             and stats["labeled_finding_count"] >= policy.reviewer_min_labeled_findings)
        if stats["conflicting_result_count"]:
            calibration_status = "CONFLICT"
        elif not sample_sufficient:
            calibration_status = "INSUFFICIENT_DATA"
        elif effective_duplicate_rate >= policy.reviewer_high_duplicate_rate:
            calibration_status = "HIGH_DUPLICATION"
        elif adoption_high is not None and adoption_high < 0.20 and benefit_proxy <= policy.reviewer_low_yield_rate:
            calibration_status = "LOW_YIELD_CANDIDATE"
        elif (adoption_low is not None and adoption_low >= 0.20) or benefit_proxy > policy.reviewer_low_yield_rate:
            calibration_status = "EFFECTIVE"
        else:
            calibration_status = "OBSERVE"
        normalized_reviewer_metrics[reviewer] = {
            "invocations": invocations,
            "blocking_findings": stats["blocking_findings"],
            "nonblocking_findings": stats["nonblocking_findings"],
            "findings_per_invocation": (float(total_findings) / invocations) if invocations else 0.0,
            "independent_task_count": task_count,
            "accepted": stats["accepted"], "rejected": stats["rejected"], "duplicate": stats["duplicate"],
            "repaired": stats["repaired"], "regressions_prevented": stats["regressions_prevented"],
            "reported_regressions_prevented": stats["reported_regressions_prevented"],
            "regression_prevention_claim_count": stats["regression_prevention_claim_count"],
            "regression_prevention_evidence_count": stats["regression_prevention_evidence_count"],
            "regression_prevention_evidence_rate": round(float(stats["regression_prevention_evidence_count"]) /
                                                         stats["regression_prevention_claim_count"], 6)
            if stats["regression_prevention_claim_count"] else None,
            "task_difficulty_distribution": dict(sorted(stats["difficulty_distribution"].items())),
            "known_task_difficulty_coverage": round(float(invocations - stats["difficulty_distribution"]["UNKNOWN"]) / invocations, 6)
            if invocations else 0.0,
            "finding_cluster_count": len(stats["finding_clusters"]),
            "clustered_finding_count": clustered_findings,
            "duplicate_cluster_finding_count": duplicate_cluster_findings,
            "clustered_duplicate_rate": round(clustered_duplicate_rate, 6) if clustered_duplicate_rate is not None else None,
            "adoption_reasons": dict(sorted(stats["adoption_reasons"].items())),
            "duration_ms": stats["duration_ms"], "cost_units": round(stats["cost_units"], 6),
            "attribution_coverage": round(attribution_coverage, 6),
            "adoption_rate": round(float(stats["accepted"]) / (stats["accepted"] + stats["rejected"]), 6) if stats["accepted"] + stats["rejected"] else None,
            "adoption_wilson_95": [round(adoption_low, 6), round(adoption_high, 6)] if adoption_low is not None else None,
            "repair_conversion_rate": round(float(stats["repaired"]) / stats["accepted"], 6) if stats["accepted"] else None,
            "duplicate_rate": round(duplicate_rate, 6) if total_findings else None,
            "duration_per_invocation_ms": round(float(stats["duration_ms"]) / invocations, 6) if invocations else None,
            "cost_per_accepted": round(float(stats["cost_units"]) / stats["accepted"], 6) if stats["accepted"] else None,
            "cost_per_repaired": round(float(stats["cost_units"]) / stats["repaired"], 6) if stats["repaired"] else None,
            "benefit_proxy": round(benefit_proxy, 6),
            "labeled_finding_count": stats["labeled_finding_count"],
            "sample_sufficient": sample_sufficient,
            "calibration_status": calibration_status,
            "unattributed_result_count": stats["unattributed_result_count"],
            "duplicate_result_count": stats["duplicate_result_count"],
            "conflicting_result_count": stats["conflicting_result_count"],
        }

    metrics: Dict[str, Any] = {
        "policy_version": policy.policy_version,
        "source_file_count": source_count,
        "record_count": len(all_rows),
        "raw_record_count": raw_record_count,
        "raw_v2_event_count": raw_v2_event_count,
        "deduplicated_v2_event_count": duplicate_v2_event_count,
        "task_count": len(task_ids),
        "records_without_task_id": records_without_task,
        "window_days": window_days,
        "known_outcome_count": known_outcome_count,
        "accepted_count": accepted_count,
        "negative_outcome_count": negative_count,
        "negative_outcome_rate": round(negative_rate, 6),
        "model_comparison_count": model_comparison_count,
        "actual_model_count": actual_model_count,
        "actual_model_coverage": round(float(actual_model_count) / len(task_ids), 6) if task_ids else 0.0,
        "known_terminal_outcome_coverage": round(float(known_outcome_count) / len(task_ids), 6) if task_ids else 0.0,
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
        "lifecycle": v2_diagnostics,
    }

    evidence_gate_failures = []
    if raw_v2_event_count:
        for label, actual, threshold in (
            ("lifecycle_completeness", v2_diagnostics["lifecycle_completeness_rate"], policy.min_lifecycle_completeness_rate),
            ("session_end_coverage", v2_diagnostics["session_end_coverage"], policy.min_session_end_coverage),
            ("project_repo_binding_coverage", v2_diagnostics["project_repo_binding_coverage"], policy.min_project_repo_binding_coverage),
        ):
            if actual < threshold:
                evidence_gate_failures.append("%s=%.3f<%.3f" % (label, actual, threshold))
        anomaly_count = (
            duplicate_v2_event_count
            + int(v2_diagnostics["duplicate_event_count"])
            + int(v2_diagnostics["out_of_order_task_count"])
            + int(v2_diagnostics["task_session_conflict_count"])
            + int(v2_diagnostics["missing_session_binding_count"])
        )
        if anomaly_count:
            evidence_gate_failures.append("lifecycle_integrity_anomalies=%d" % anomaly_count)
    if raw_v2_event_count:
        for label, actual, threshold in (
            ("actual_model_coverage", metrics["actual_model_coverage"], policy.min_actual_model_coverage),
            ("known_terminal_outcome_coverage", metrics["known_terminal_outcome_coverage"], policy.min_known_terminal_outcome_coverage),
        ):
            if actual < threshold:
                evidence_gate_failures.append("%s=%.3f<%.3f" % (label, actual, threshold))
    if len(all_rows) < policy.min_records or len(task_ids) < policy.min_independent_tasks or window_days < policy.min_observation_window_days:
        evidence_gate_failures.append("minimum_window_or_sample_not_met")
    metrics["evidence_sufficient"] = not evidence_gate_failures
    metrics["insufficient_evidence"] = tuple(evidence_gate_failures)
    if evidence_gate_failures:
        warnings.append("insufficient-evidence：%s；快照保留但不生成优化信号" % ", ".join(evidence_gate_failures))
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
        attribution_coverage = (float(stats["attribution_count"]) / invocations) if invocations else 0.0
        benefit_proxy = float(stats["repaired"] + stats["regressions_prevented"]) / max(1.0, stats["cost_units"])
        # 缺少因果归因时，禁止仅根据 finding 数量将 Reviewer 判定为低收益。
        calibration = normalized_reviewer_metrics[reviewer]
        if calibration["calibration_status"] != "LOW_YIELD_CANDIDATE":
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
            summary="Reviewer %s 调用 %d 次，归因收益代理 %.4f 且归因覆盖率 %.2f%%" % (reviewer, invocations, benefit_proxy, attribution_coverage * 100),
            evidence=tuple(stats["evidence"]),
            metrics={
                "invocations": invocations,
                "findings": total_findings,
                "findings_per_invocation": yield_rate,
                "benefit_proxy": benefit_proxy,
                "attribution_coverage": attribution_coverage,
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

    if evidence_gate_failures:
        signals = []
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
