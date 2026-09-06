"""中文：记录级增量收据、原子提交和显式项目自动化。

English: Record-level incremental receipts, atomic commits, and explicit project automation.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Callable, Mapping

from ..common import atomic_write_json
from ..event_v3 import OwnerTokenLock
from .artifacts import ArtifactError, identifier, load, persist, project_identity, seal
from .contracts import parse_iso_datetime, sha256_hex, to_primitive, utc_now_iso
from .health import inspect_health
from .registry import ProposalRegistry, _proposal
from .storage import safe_child

RECEIPT = "evolution/incremental-receipt.json"
CONFIG = "evolution/automation-config.json"
LAST_RESULT = "evolution/automation-last-result.json"


def _bounded_int(value: int, low: int, high: int) -> int:
    if type(value) is not int or not low <= value <= high:
        raise ArtifactError("INVALID_INCREMENTAL_LIMIT")
    return value


def run_incremental(service: Any, *, observed_at: str | None = None, milestone: str = "",
                    minimum_new_tasks: int = 3, cooldown_seconds: int = 3600,
                    max_age_days: int = 30, fault: Callable[[str], None] | None = None) -> dict[str, Any]:
    _bounded_int(minimum_new_tasks, 1, 10000)
    _bounded_int(cooldown_seconds, 0, 604800)
    if milestone:
        identifier(milestone)
    now = observed_at or utc_now_iso()
    parse_iso_datetime(now, "observed_at")
    project_dir = service.project_dir
    guard = safe_child(project_dir, "evolution", "incremental.guard")
    guard.parent.mkdir(parents=True, exist_ok=True)
    with OwnerTokenLock(guard, timeout=2):
        health, snapshot = inspect_health(project_dir, service.project_id, service.policy,
                                          observed_at=now, max_age_days=max_age_days)
        result: dict[str, Any] = {"schema_version": "incremental-result/1", "project_id": service.project_id,
                                  "status": health["status"], "health": health, "notification_required": False,
                                  "execution_authorization": "NONE"}
        if not health["analysis_allowed"] or snapshot is None:
            return result
        identity = {"project_id": service.project_id, "repo_fingerprint": health["repo_fingerprint"]}
        previous = load(project_dir, RECEIPT, schema="incremental-receipt/1") if safe_child(project_dir, RECEIPT).exists() else None
        if previous and previous["identity"] != identity:
            raise ArtifactError("INCREMENTAL_RECEIPT_IDENTITY_MISMATCH")
        inputs = {**identity, "policy_digest": health["policy_digest"], "milestone": milestone,
                  "records": snapshot.metrics["input_record_digest"], "feedback": snapshot.metrics["feedback_input_digest"],
                  "calibration": snapshot.metrics["calibration_input_digest"]}
        key = sha256_hex(inputs)
        task_ids = list(snapshot.metrics["independent_task_ids"])
        new_tasks = len(set(task_ids) - set(previous["task_ids"] if previous else []))
        result.update(input_key=key, new_independent_tasks=new_tasks)
        if previous and previous["input_key"] == key:
            transaction = load(project_dir, previous["transaction"]["path"], previous["transaction"]["content_hash"], "evolution-transaction/1")
            if transaction["inputs"] != inputs:
                raise ArtifactError("INCREMENTAL_TRANSACTION_MISMATCH")
            load(project_dir, previous["observation_reference"]["path"], previous["observation_reference"]["content_hash"], "observation-evidence/1")
            registry = ProposalRegistry(service.evolution_root, service.project_id)
            views = {view.proposal.proposal_id: view for view in registry.list()}
            for ref in previous["registered"]:
                if ref["proposal_id"] not in views or views[ref["proposal_id"]].proposal.content_hash != ref["content_hash"]:
                    raise ArtifactError("INCREMENTAL_REGISTERED_OUTPUT_MISMATCH")
            result["status"] = "NO_CHANGE"
            return result
        policy_changed = previous and previous["policy_digest"] != inputs["policy_digest"]
        milestone_changed = bool(milestone and (not previous or previous["milestone"] != milestone))
        supplemental = bool(previous and (previous["feedback_digest"] != inputs["feedback"] or previous.get("calibration_digest") != inputs["calibration"]))
        signals = [{"type": signal.signal_type.value, "target": signal.target,
                    "count": signal.occurrence_count, "rate": signal.rate,
                    "confidence": signal.confidence.value} for signal in snapshot.signals]
        signal_digest = sha256_hex(sorted(signals, key=lambda item: (item["type"], item["target"])))
        signal_changed = bool(previous and previous.get("signal_digest", sha256_hex([])) != signal_digest)
        result["signal_changed"] = signal_changed
        if new_tasks < minimum_new_tasks and not (policy_changed or milestone_changed or supplemental or signal_changed):
            result["status"] = "WAITING_FOR_TASKS"
            return result
        if previous:
            elapsed = (parse_iso_datetime(now, "observed_at") - parse_iso_datetime(previous["analyzed_at"], "analyzed_at")).total_seconds()
            if elapsed < 0:
                raise ArtifactError("INCREMENTAL_CLOCK_REGRESSION")
            if elapsed < cooldown_seconds and not (milestone_changed or policy_changed or signal_changed):
                result["status"] = "COOLDOWN"
                return result
        transaction_path = "evolution/transactions/" + key + ".json"
        if safe_child(project_dir, transaction_path).exists():
            transaction = load(project_dir, transaction_path, schema="evolution-transaction/1")
            if transaction["inputs"] != inputs:
                raise ArtifactError("INCREMENTAL_TRANSACTION_MISMATCH")
        else:
            assessments = service.analyze(snapshot)
            proposals = service.propose(snapshot, assessments)
            transaction = seal({"schema_version": "evolution-transaction/1", "inputs": inputs,
                                "snapshot": to_primitive(snapshot), "assessments": to_primitive(assessments),
                                "proposals": to_primitive(proposals), "execution_authorization": "NONE"})
            persist(project_dir, transaction_path, transaction)
        if fault:
            fault("after_outputs")
        from .snapshots import persist_snapshot, snapshot_from_mapping
        observation_ref = persist_snapshot(project_dir, snapshot_from_mapping(transaction["snapshot"]))
        registry = ProposalRegistry(service.evolution_root, service.project_id)
        registered = []
        for raw in transaction["proposals"]:
            view, created = registry.register(_proposal(raw))
            registered.append({"proposal_id": view.proposal.proposal_id, "content_hash": view.proposal.content_hash, "created": created})
        registry.validate()
        if fault:
            fault("before_receipt")
        receipt = seal({"schema_version": "incremental-receipt/1", "identity": identity, "input_key": key,
                        "policy_digest": inputs["policy_digest"], "milestone": milestone,
                        "record_digest": inputs["records"], "feedback_digest": inputs["feedback"],
                        "calibration_digest": inputs["calibration"],
                        "signal_digest": signal_digest,
                        "task_ids": task_ids, "analyzed_at": now,
                        "observation_reference": observation_ref,
                        "registered": [{key: item[key] for key in ("proposal_id", "content_hash")} for item in registered],
                        "transaction": {"path": transaction_path, "content_hash": transaction["content_hash"]},
                        "execution_authorization": "NONE"})
        atomic_write_json(safe_child(project_dir, RECEIPT), receipt)
        result.update(status="ANALYZED", transaction=receipt["transaction"], registered=registered,
                      observation_reference=observation_ref,
                      notification_required=any(item["created"] for item in registered))
        return result


def configure_automation(project_dir: Path, *, enabled: bool, minimum_new_tasks: int = 3,
                         cooldown_seconds: int = 3600, max_age_days: int = 30) -> dict[str, Any]:
    if type(enabled) is not bool:
        raise ArtifactError("INVALID_AUTOMATION_ENABLED")
    identity = project_identity(project_dir)
    value = seal({"schema_version": "evolution-automation/1", "identity": identity, "enabled": enabled,
                  "minimum_new_tasks": _bounded_int(minimum_new_tasks, 1, 10000),
                  "cooldown_seconds": _bounded_int(cooldown_seconds, 0, 604800),
                  "max_age_days": _bounded_int(max_age_days, 1, 365), "execution_authorization": "NONE"})
    path = safe_child(project_dir, CONFIG)
    path.parent.mkdir(parents=True, exist_ok=True)
    with OwnerTokenLock(path, timeout=2):
        atomic_write_json(path, value)
    return value


def _automation_tick(project_dir: Path) -> dict[str, Any]:
    path = safe_child(project_dir, CONFIG)
    if not path.exists():
        return {"status": "DISABLED", "notification_required": False}
    config = load(project_dir, CONFIG, schema="evolution-automation/1")
    if not config["enabled"]:
        return {"status": "DISABLED", "notification_required": False}
    if config["identity"] != project_identity(project_dir):
        raise ArtifactError("AUTOMATION_IDENTITY_MISMATCH")
    from .service import ControlledEvolutionService
    service = ControlledEvolutionService(project_dir.parent, project_dir.name)
    result = run_incremental(service, minimum_new_tasks=config["minimum_new_tasks"],
                             cooldown_seconds=config["cooldown_seconds"], max_age_days=config["max_age_days"])
    previous = load(project_dir, LAST_RESULT, schema="automation-status/1") if safe_child(project_dir, LAST_RESULT).exists() else None
    actionable = result["status"] in {"DATA_DAMAGED", "IDENTITY_MISMATCH", "IDENTITY_UNAVAILABLE", "STALE_DATA"}
    result["notification_required"] = result["notification_required"] or bool(actionable and (not previous or previous["status"] != result["status"]))
    if not previous or previous["status"] != result["status"] or result["notification_required"]:
        status = seal({"schema_version": "automation-status/1", "status": result["status"],
                       "notification_required": result["notification_required"], "checked_at": utc_now_iso(),
                       "execution_authorization": "NONE"})
        atomic_write_json(safe_child(project_dir, LAST_RESULT), status)
    return result


def automation_tick(project_dir: Path) -> dict[str, Any]:
    try:
        return _automation_tick(project_dir)
    except Exception:
        result = {"status": "RETRY_REQUIRED", "notification_required": True}
        path = safe_child(project_dir, LAST_RESULT)
        path.parent.mkdir(parents=True, exist_ok=True)
        with OwnerTokenLock(path, timeout=2):
            previous = load(project_dir, LAST_RESULT, schema="automation-status/1") if path.exists() else None
            if not previous or previous["status"] != "RETRY_REQUIRED":
                atomic_write_json(path, seal({"schema_version": "automation-status/1", **result,
                                             "checked_at": utc_now_iso(), "execution_authorization": "NONE"}))
            else:
                result["notification_required"] = False
        return result
