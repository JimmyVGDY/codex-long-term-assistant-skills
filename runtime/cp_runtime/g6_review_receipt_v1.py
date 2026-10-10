"""中文：带来源绑定的最小复审报告与下游交付投影。

English: Minimal source-bound reviewer reports and downstream delivery projection.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Mapping

from . import g6_budget_v1 as budget
from .common import RuntimeContractError, atomic_write_json, read_json, repo_snapshot, utc_now
from .event_v2 import OwnerTokenLock
from .g6_delivery_v1 import evaluate_delivery
from .routing_contract import _constant, _object, exact, fail, ref, role_for

REPORT_FIELDS = {"status", "findings", "checked_scope", "unverified_items", "summary"}
RECEIPT_FIELDS = {"schema_version", "permit_id", "work_item_id", "review_phase",
                  "phase_source", "agent_ref", "baseline_sha256", "report_status",
                  "finding_refs", "report_ref", "transcript_sha256", "gate_state",
                  "reason_code", "recorded_at", "root_session_ref", "root_identity_ref",
                  "root_ledger_ref"}


def _report(raw: bytes) -> tuple[dict[str, Any] | None, str]:
    final_texts = []
    try:
        for line in raw.splitlines():
            event = json.loads(line, object_pairs_hook=_object, parse_constant=_constant)
            payload = event.get("payload", {})
            if (event.get("type") == "response_item" and payload.get("type") == "message"
                    and payload.get("role") == "assistant"
                    and payload.get("phase") in {"final", "final_answer"}):
                content = payload.get("content")
                if (not isinstance(content, list) or len(content) != 1
                        or content[0].get("type") != "output_text"
                        or not isinstance(content[0].get("text"), str)):
                    return None, "REVIEW_FINAL_SHAPE"
                final_texts.append(content[0]["text"])
    except (ValueError, KeyError, TypeError, UnicodeError, RecursionError):
        return None, "REVIEW_TRANSCRIPT_INVALID"
    if len(final_texts) != 1 or len(final_texts[0].encode("utf-8")) > 65_536:
        return None, "REVIEW_FINAL_MISSING_OR_AMBIGUOUS"
    try:
        value = json.loads(final_texts[0], object_pairs_hook=_object, parse_constant=_constant)
        exact(value, REPORT_FIELDS, "G6_REVIEW_REPORT_FIELDS")
        if value["status"] not in {"pass", "nonblocking", "blocking", "incomplete"}:
            return None, "REVIEW_STATUS"
        if (not isinstance(value["findings"], list) or len(value["findings"]) > 50
                or not isinstance(value["checked_scope"], list)
                or not isinstance(value["unverified_items"], list)
                or not isinstance(value["summary"], str)
                or len(value["summary"]) > 5000):
            return None, "REVIEW_BODY_SHAPE"
        for finding in value["findings"]:
            if (not isinstance(finding, dict) or not isinstance(finding.get("id"), str)
                    or not finding["id"] or not isinstance(finding.get("summary"), str)):
                return None, "REVIEW_FINDING_SHAPE"
        if value["status"] == "pass" and value["findings"]:
            return None, "REVIEW_PASS_WITH_FINDINGS"
        if value["status"] == "blocking" and not value["findings"]:
            return None, "REVIEW_BLOCKING_WITHOUT_FINDINGS"
    except (ValueError, KeyError, TypeError, UnicodeError, RecursionError):
        return None, "REVIEW_JSON_INVALID"
    return value, "REPORT_STRUCTURE_VERIFIED"


def _receipt_path(path: Path, permit_id: str) -> Path:
    return _receipt_dir(path) / (permit_id + ".json")


def _receipt_dir(path: Path) -> Path:
    return path.parent / ("g6-review-receipts-" + ref(str(path.resolve()))[7:31])


def _delivery_path(path: Path) -> Path:
    return path.parent / ("g6-delivery-status-" + ref(str(path.resolve()))[7:31] + ".json")


def ingest(path: Path, *, raw_transcript: bytes, task_path: str,
           permit_id: str | None = None) -> dict[str, Any] | None:
    state = budget.read_budget(path)
    matches = [(pid, receipt) for pid, receipt in state["receipts"].items()
               if receipt["disposition"] == "created" and receipt["agent_ref"] == ref(task_path)]
    if permit_id is not None:
        matches = [item for item in matches if item[0] == permit_id]
    if len(matches) != 1:
        fail("G6_REVIEW_RECEIPT_OWNER")
    permit_id = matches[0][0]
    permit = state["permits"][permit_id]
    if role_for(permit["agent_type"]) != "reviewer":
        return None
    if permit_id not in state["terminals"]:
        fail("G6_REVIEW_NATIVE_TERMINAL_REQUIRED")
    report, reason = _report(raw_transcript)
    matched = [slot for slot in state["root"]["required_slots"]
               if slot["work_item_id"] == permit["work_item_id"]
               and slot.get("review_phase") in {"pre_review", "post_review", "repair_review"}]
    phase = matched[0]["review_phase"] if len(matched) == 1 else "UNKNOWN"
    clear = bool(report and report["status"] == "pass" and not report["findings"]
                 and not report["unverified_items"] and permit["facts"]["baseline_sha256"] is not None)
    receipt = {"schema_version": "g6-review-receipt/1", "permit_id": permit_id,
               "work_item_id": permit["work_item_id"], "review_phase": phase,
               "phase_source": "root-required-slot" if matched else "UNKNOWN",
               "agent_ref": ref(task_path),
               "root_session_ref": state["root"]["host_session_ref"],
               "root_identity_ref": ref(state["root"]["identity"]),
               "root_ledger_ref": ref(str(path.resolve())),
               "baseline_sha256": permit["facts"]["baseline_sha256"],
               "report_status": report["status"] if report else "UNVERIFIED",
               "finding_refs": [ref(item) for item in report["findings"]] if report else [],
               "report_ref": ref(report) if report else None,
               # 中文：这是本次传入的有界回执记录字节摘要，不宣称整份会话文件摘要。
               # English: Hash the supplied bounded receipt-record bytes,
               # not an asserted hash of the entire conversation file.
               "transcript_sha256": hashlib.sha256(raw_transcript).hexdigest(),
               "gate_state": "PASS" if clear and phase != "UNKNOWN" else "MISSING_EVIDENCE",
               "reason_code": (reason if clear else "REVIEW_NOT_CLEAR_OR_PHASE_UNKNOWN"
                               if report else reason), "recorded_at": utc_now()}
    target = _receipt_path(path, permit_id)
    target.parent.mkdir(parents=True, exist_ok=True)
    with OwnerTokenLock(target, timeout=2):
        if target.exists():
            prior = read_json(target, verify=True, label="GPT-6 reviewer receipt")
            prior.pop("integrity")
            if {key: prior[key] for key in RECEIPT_FIELDS - {"recorded_at"}} != {
                    key: receipt[key] for key in RECEIPT_FIELDS - {"recorded_at"}}:
                fail("G6_REVIEW_RECEIPT_CHANGED")
            return prior
        atomic_write_json(target, receipt, seal=True)
    return receipt


def project_delivery(path: Path) -> dict[str, Any]:
    """中文：Stop 时消费报告；缺少复审或检查时保持未验证，不记为 PASS。
    
    English: Stop-time consumer: missing review/checks remain unverified, never PASS.
    """
    state = budget.read_budget(path)
    by_phase: dict[str, list[dict]] = {}
    directory = _receipt_dir(path)
    try:
        current_baseline = repo_snapshot(Path(state["root"]["repo_path"]))["sha256"]
    except (OSError, ValueError, TimeoutError, RuntimeContractError):
        current_baseline = None
    if directory.exists():
        for item in sorted(directory.glob("*.json")):
            value = read_json(item, verify=True, label="GPT-6 reviewer receipt")
            value.pop("integrity")
            exact(value, RECEIPT_FIELDS, "G6_REVIEW_RECEIPT_FIELDS")
            permit_id = value["permit_id"]
            if (permit_id not in state["permits"] or item != _receipt_path(path, permit_id)
                    or value["work_item_id"] != state["permits"][permit_id]["work_item_id"]
                    or value["root_session_ref"] != state["root"]["host_session_ref"]
                    or value["root_identity_ref"] != ref(state["root"]["identity"])
                    or value["root_ledger_ref"] != ref(str(path.resolve()))):
                fail("G6_REVIEW_RECEIPT_IDENTITY")
            value["effective_gate_state"] = (value["gate_state"] if current_baseline is not None
                and value["baseline_sha256"] == current_baseline else "MISSING_EVIDENCE")
            by_phase.setdefault(value["review_phase"], []).append(value)
    def gate(phase: str) -> dict | None:
        items = by_phase.get(phase, [])
        if not items or any(item["effective_gate_state"] != "PASS" for item in items):
            return None
        return {"gate_id": phase, "state": "PASS", "affected_action": "none",
                "source_ref": ref([item["report_ref"] for item in items])}
    report = evaluate_delivery(checks=[], baseline_sha256=None,
                               post_review=gate("post_review"),
                               repair_review=gate("repair_review"), installed=False,
                               action="write")
    report["review_report_statuses"] = {
        phase: [{"status": item["report_status"], "finding_count": len(item["finding_refs"]),
                 "phase_source": item["phase_source"],
                 "baseline_current": current_baseline is not None
                 and item["baseline_sha256"] == current_baseline}
                for item in items]
        for phase, items in sorted(by_phase.items())}
    report["unadjudicated_blocking_report"] = any(
        item["report_status"] == "blocking" for items in by_phase.values() for item in items)
    report["unresolved_review_conflict"] = any(
        len({item["report_status"] for item in items}) > 1 for items in by_phase.values())
    report["review_receipt_count"] = sum(len(items) for items in by_phase.values())
    if report["unadjudicated_blocking_report"] or report["unresolved_review_conflict"]:
        report["next_action"] = "adjudicate_reported_conflict_or_continue_local"
    from .g6_observation_v1 import collect
    try:
        report["observation"] = collect(path, expected_head=state["head_hash"])
    except (OSError, ValueError, TimeoutError):
        # 中文：最小观察是附加输出；采集故障不阻塞已经允许的工作。
        # English: Minimal observation is supplemental; collection failure does not block authorized work.
        report["observation"] = {"schema_version": "g6-observation/1", "status": "UNAVAILABLE"}
    target = _delivery_path(path)
    with OwnerTokenLock(target, timeout=2):
        atomic_write_json(target, {"schema_version": "g6-delivery-projection/1",
                                   "ledger_head": state["head_hash"], "status": report}, seal=True)
    return report
