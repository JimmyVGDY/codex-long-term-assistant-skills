"""中文：带来源绑定的最小复审报告与下游交付投影。

English: Minimal source-bound reviewer reports and downstream delivery projection.
"""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any, Mapping

from . import g6_budget_v1 as budget
from .common import RuntimeContractError, atomic_write_json, read_json, repo_snapshot, utc_now, verify_record
from .event_v2 import OwnerTokenLock
from .g6_delivery_v1 import evaluate_delivery
from .routing_contract import _constant, _object, exact, fail, ref, role_for

REPORT_FIELDS = {"status", "findings", "checked_scope", "unverified_items", "summary"}
RECEIPT_FIELDS = {"schema_version", "permit_id", "work_item_id", "review_phase",
                  "phase_source", "agent_ref", "baseline_sha256", "report_status",
                  "finding_refs", "report_ref", "transcript_sha256", "gate_state",
                  "reason_code", "recorded_at", "root_session_ref", "root_identity_ref",
                  "root_ledger_ref"}


def scope_markers(scope: Any) -> list[str]:
    """中文：接受两种明确范围格式，保留原报告字节与摘要，不猜缺失证据。
    English: Accept two explicit scope shapes without rewriting the report or guessing missing evidence.
    """
    if isinstance(scope, list):
        if any(not isinstance(item, str) or len(item) > 4096 for item in scope):
            raise ValueError("REVIEW_SCOPE_SHAPE")
        return scope
    if not isinstance(scope, dict) or not scope or len(scope) > 32:
        raise ValueError("REVIEW_SCOPE_SHAPE")
    # 中文：描述性元数据不授予权限；有界接受新增字段，只读取明确的顶层证据键。
    # English: Descriptive metadata grants no authority. Bound extra fields and read only explicit top-level evidence keys.
    pending, nodes = [(scope, 0)], 0
    while pending:
        item, depth = pending.pop()
        nodes += 1
        if nodes > 512 or depth > 8:
            raise ValueError("REVIEW_SCOPE_SHAPE")
        if isinstance(item, dict):
            if len(item) > 32 or any(not isinstance(key, str) or len(key) > 128 for key in item):
                raise ValueError("REVIEW_SCOPE_SHAPE")
            pending.extend((value, depth + 1) for value in item.values())
        elif isinstance(item, list):
            if len(item) > 128:
                raise ValueError("REVIEW_SCOPE_SHAPE")
            pending.extend((value, depth + 1) for value in item)
        elif item is not None and not isinstance(item, (str, bool, int, float)):
            raise ValueError("REVIEW_SCOPE_SHAPE")
        elif isinstance(item, str) and len(item) > 4096:
            raise ValueError("REVIEW_SCOPE_SHAPE")
    paths = scope.get("paths", [])
    if not isinstance(paths, list) or len(paths) > 128 or any(
            not isinstance(item, str) or len(item) > 4096 for item in paths):
        raise ValueError("REVIEW_SCOPE_SHAPE")
    markers = list(paths)
    evidence_keys = {"focus", "packet_sha256", "context_sha256", "isolation_level",
                     "approved_profile", "dispatch_ref", "score_ref"}
    for key, item in scope.items():
        if key not in evidence_keys:
            continue
        if item is None and key == "score_ref":
            continue
        if not isinstance(item, str) or len(item) > 4096:
            raise ValueError("REVIEW_SCOPE_SHAPE")
        if key in {"packet_sha256", "context_sha256"} and not re.fullmatch(r"[0-9a-f]{64}", item):
            raise ValueError("REVIEW_SCOPE_DIGEST")
        markers.append(key + "=" + item)
    return markers


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
                or not isinstance(value["unverified_items"], list)
                or not isinstance(value["summary"], str)
                or len(value["summary"]) > 5000):
            return None, "REVIEW_BODY_SHAPE"
        scope_markers(value["checked_scope"])
        if any(not isinstance(item, str) or len(item) > 4096 for item in value["unverified_items"]):
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
           permit_id: str | None = None, pending_terminal: Mapping[str, Any] | None = None) -> dict[str, Any] | None:
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
    if pending_terminal is not None:
        # 中文：先冻结最小回执元数据；实际终态匹配前不能发布为有效回执。
        # English: Freeze minimal receipt metadata before settlement; publish only after the real terminal matches.
        exact(pending_terminal, {"permit_id", "agent_ref", "outcome", "proof_ref"}, "G6_REVIEW_PENDING_TERMINAL")
        if (pending_terminal["permit_id"] != permit_id or pending_terminal["agent_ref"] != ref(task_path)
                or pending_terminal["outcome"] not in budget.OUTCOMES
                or not isinstance(pending_terminal["proof_ref"], str)
                or re.fullmatch(r"sha256:[0-9a-f]{64}", pending_terminal["proof_ref"]) is None
                or permit_id in state["terminals"] and state["terminals"][permit_id] != pending_terminal):
            fail("G6_REVIEW_PENDING_TERMINAL")
        state["terminals"] = {**state["terminals"], permit_id: dict(pending_terminal)}
    if permit_id not in state["terminals"]:
        fail("G6_REVIEW_NATIVE_TERMINAL_REQUIRED")
    report, reason = _report(raw_transcript)
    matched = [slot for slot in state["root"]["required_slots"]
               if slot["work_item_id"] == permit["work_item_id"]
               and slot.get("review_phase") in {"pre_review", "post_review", "repair_review"}]
    phase = matched[0]["review_phase"] if len(matched) == 1 else "UNKNOWN"
    work = state.get("review_work", {}).get(permit["work_item_id"])
    if work is not None:
        phase = work["phase"]
    terminal_acceptable = state["terminals"][permit_id]["outcome"] in {"PASS", "UNKNOWN"}
    clear = bool(terminal_acceptable and report and report["status"] == "pass" and not report["findings"]
                 and not report["unverified_items"] and permit["facts"]["baseline_sha256"] is not None)
    if work is not None:
        calls = [call for call in state.get("review_calls", {}).values()
                 if call["work_id"] == permit["work_item_id"] and ref(call) == permit["facts"]["scope_ref"]]
        markers = scope_markers(report["checked_scope"]) if report else []
        packet_verified = bool(report and len(calls) == 1
                               and "packet_sha256=" + calls[0]["packet_sha256"] in markers)
        from .g6_review_requests import context_delivered
        delivery_verified = bool(packet_verified
            and context_delivered(path, permit_id, task_path, calls[0])
            and "context_sha256=" + calls[0]["body_sha256"] in markers)
        clear = clear and delivery_verified
        reason = ("REVIEW_PACKET_VERIFIED" if delivery_verified else
                  "REVIEW_CONTEXT_UNVERIFIED" if packet_verified else "REVIEW_PACKET_UNVERIFIED")
        if report and not terminal_acceptable:
            reason = "REVIEW_NATIVE_TERMINAL_UNSUCCESSFUL"
    receipt = {"schema_version": "g6-review-receipt/1", "permit_id": permit_id,
               "work_item_id": permit["work_item_id"], "review_phase": phase,
               "phase_source": "registered-review-work" if work else "root-required-slot" if matched else "UNKNOWN",
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
               "reason_code": (reason if clear or work is not None else "REVIEW_NOT_CLEAR_OR_PHASE_UNKNOWN"
                               if report else reason), "recorded_at": utc_now()}
    if pending_terminal is not None:
        target = _pending_path(path, permit_id)
        value = {"schema_version": "g6-review-pending/1", "terminal": dict(pending_terminal),
                 "receipt": receipt, "published": False}
        target.parent.mkdir(parents=True, exist_ok=True)
        with OwnerTokenLock(target, timeout=2):
            if target.exists():
                old = _read_pending(target)
                if (any(old["terminal"][key] != value["terminal"][key]
                        for key in ("permit_id", "agent_ref", "outcome"))
                        or _receipt_identity(old["receipt"]) != _receipt_identity(receipt)):
                    fail("G6_REVIEW_PENDING_CHANGED")
                return old
            atomic_write_json(target, value, seal=True)
        return value
    return _publish_receipt(path, receipt)


def _receipt_identity(receipt: Mapping[str, Any]) -> dict[str, Any]:
    return {key: receipt[key] for key in RECEIPT_FIELDS - {"recorded_at"}}


def _publish_receipt(path: Path, receipt: dict[str, Any]) -> dict[str, Any]:
    target = _receipt_path(path, receipt["permit_id"])
    target.parent.mkdir(parents=True, exist_ok=True)
    with OwnerTokenLock(target, timeout=2):
        if target.exists():
            prior = read_json(target, verify=True, label="GPT-6 reviewer receipt")
            prior.pop("integrity")
            if _receipt_identity(prior) != _receipt_identity(receipt):
                fail("G6_REVIEW_RECEIPT_CHANGED")
            return prior
        atomic_write_json(target, receipt, seal=True)
    return receipt


def _pending_path(path: Path, permit_id: str) -> Path:
    return _receipt_dir(path) / "pending" / (permit_id + ".json")


def _read_pending(path: Path) -> dict[str, Any]:
    from .capability_store import bounded_read
    value = json.loads(bounded_read(path, 32_768), object_pairs_hook=_object, parse_constant=_constant)
    verify_record(value, "pending native review receipt")
    value.pop("integrity")
    exact(value, {"schema_version", "terminal", "receipt", "published"}, "G6_REVIEW_PENDING_FIELDS")
    exact(value["receipt"], RECEIPT_FIELDS, "G6_REVIEW_RECEIPT_FIELDS")
    exact(value["terminal"], {"permit_id", "agent_ref", "outcome", "proof_ref"}, "G6_REVIEW_PENDING_TERMINAL")
    if value["schema_version"] != "g6-review-pending/1" or type(value["published"]) is not bool:
        fail("G6_REVIEW_PENDING_FIELDS")
    return value


def publish_pending(path: Path, permit_id: str) -> dict[str, Any] | None:
    target = _pending_path(path, permit_id)
    if not target.exists():
        return None
    with OwnerTokenLock(target, timeout=2):
        value = _read_pending(target)
        state = budget.read_budget(path)
        receipt = value["receipt"]
        permit = state["permits"].get(permit_id)
        if (permit is None or target.name != receipt["permit_id"] + ".json"
                or value["terminal"]["permit_id"] != permit_id
                or receipt["work_item_id"] != permit["work_item_id"]
                or receipt["baseline_sha256"] != permit["facts"]["baseline_sha256"]
                or receipt["agent_ref"] != value["terminal"]["agent_ref"]
                or receipt["root_ledger_ref"] != ref(str(path.resolve()))
                or receipt["root_session_ref"] != state["root"]["host_session_ref"]
                or receipt["root_identity_ref"] != ref(state["root"]["identity"])
                or state["receipts"].get(permit_id, {}).get("disposition") != "created"
                or state["receipts"][permit_id]["agent_ref"] != receipt["agent_ref"]):
            fail("G6_REVIEW_PENDING_IDENTITY")
        terminal = state["terminals"].get(permit_id)
        if terminal is None:
            return None
        if terminal != value["terminal"]:
            fail("G6_REVIEW_PENDING_TERMINAL_CHANGED")
        result = _publish_receipt(path, receipt)
        if not value["published"]:
            value["published"] = True
            atomic_write_json(target, value, seal=True)
        return result


def recover_pending(path: Path, *, limit: int = 2) -> dict[str, Any]:
    # 中文：元数据补发不读后来的回答，不改终态或费用；单条损坏不影响其他调用。
    # English: Republish frozen metadata without reading later answers or changing terminals or charges.
    from itertools import islice
    if type(limit) is not int or not 1 <= limit <= 2:
        fail("G6_REVIEW_PENDING_LIMIT")
    directory = _receipt_dir(path) / "pending"
    files = list(islice(directory.glob("*.json"), 65)) if directory.is_dir() else []
    rows, errors = [], []
    if len(files) > 64:
        return {"items": [], "errors": [{"reason_code": "G6_REVIEW_PENDING_BOUND"}]}
    attempted = 0
    for target in files:
        if attempted >= limit:
            break
        try:
            value = _read_pending(target)
            if value["published"]:
                continue
            attempted += 1
            result = publish_pending(path, value["terminal"]["permit_id"])
            rows.append({"permit_id": value["terminal"]["permit_id"],
                         "status": "RECEIPT_PUBLISHED" if result else "WAIT_RECONCILE",
                         "evidence_source": "frozen-native-receipt-metadata"})
        except (RuntimeContractError, OSError, ValueError, KeyError, TypeError):
            errors.append({"record_ref": ref(str(target)), "reason_code": "G6_REVIEW_PENDING_UNVERIFIED"})
    return {"items": rows, "errors": errors}


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
            packet_verified = (value["work_item_id"] not in state.get("review_work", {})
                               or value["reason_code"] == "REVIEW_PACKET_VERIFIED")
            value["effective_gate_state"] = (value["gate_state"] if current_baseline is not None
                and value["baseline_sha256"] == current_baseline and packet_verified else "MISSING_EVIDENCE")
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
    from .g6_delivery_v1 import native_execution_view
    report["native_execution"] = native_execution_view(state)
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
