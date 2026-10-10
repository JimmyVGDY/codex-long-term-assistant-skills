"""中文：G6 复审工作流只引用根预算，不执行旧评分或重复计费。

English: G6 review workflow references the root budget, without legacy scoring
or a second accounting system.
"""
from __future__ import annotations

import json
import importlib.util
import contextlib
import io
from pathlib import Path
from typing import Any

from . import g6_budget_v1 as budget
from .common import atomic_write_json, read_json, require_external_state, utc_now
from .event_v2 import OwnerTokenLock
from .g6_flexible_policy import POLICY_ID
from .g6_hook_v1 import preview
from .routing_contract import ref, role_for
from .capability_store import bounded_read

SCHEMA = "g6-review-state/1"


def _packet_tools():
    path = Path(__file__).resolve().parents[2] / "skills/multi-agent-independent-review/scripts/review_packet.py"
    spec = importlib.util.spec_from_file_location("g6_packet_runtime", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _packet_current(packet_dir: str, repo_path: str) -> bool:
    if not packet_dir:
        return False
    from types import SimpleNamespace
    try:
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            _packet_tools().command_freshness(SimpleNamespace(packet_dir=packet_dir, repo_path=repo_path))
        return True
    except (SystemExit, RuntimeError, ValueError, OSError):
        return False


def _refresh_reports(value: dict[str, Any]) -> None:
    for reviewer, row in value["results"].items():
        assignment = value.get("assignments", {}).get(reviewer, {})
        row["packet_current"] = (row.get("assignment_ref") == ref(assignment)
                                 and _packet_current(assignment.get("packet_dir", ""), value["repo_path"]))
    if not _reports_current(value):
        value["verification_state"] = "UNVERIFIED"


def _reports_current(value: dict[str, Any]) -> bool:
    plans = value.get("plans", {})
    plan = plans.get(value.get("active_plan_key"))
    if not plan:
        return False
    expected = set(plan["reviewers"])
    if not expected or not expected.issubset(value["results"]):
        return False
    for reviewer in expected:
        row = value["results"][reviewer]
        assignment = value.get("assignments", {}).get(reviewer, {})
        if (assignment.get("phase") != plan["phase"]
                or assignment.get("packet_sha256") != plan["packet_sha256"]
                or row.get("assignment_ref") != ref(assignment)
                or row["verification_state"] != "NATIVE_REPORT_VERIFIED"
                or not row["packet_current"]):
            return False
    return True


def run(args: Any) -> dict[str, Any]:
    directory = Path(args.review_dir).expanduser().resolve()
    path = directory / "review-state.json"
    directory.mkdir(parents=True, exist_ok=True)
    with OwnerTokenLock(path, timeout=2):
        if args.command == "init":
            if path.exists():
                raise ValueError("G6_REVIEW_STATE_EXISTS")
            repo = Path(args.repo_path).resolve() if args.repo_path else Path.cwd().resolve()
            require_external_state(directory, repo)
            ledger = str(Path(args.delegation_ledger).resolve()) if args.delegation_ledger else ""
            root = budget.read_budget(Path(ledger))["root"] if ledger else None
            if root and args.host_session_id and root["host_session_ref"] != ref(args.host_session_id):
                raise ValueError("G6_REVIEW_ROOT_SESSION")
            value = {"schema_version": SCHEMA, "policy_id": POLICY_ID,
                     "boundary_id": args.boundary_id,
                     "task_id": args.task_id or (root["task_id"] if root else args.boundary_id),
                     "repo_path": str(repo), "ledger_path": ledger,
                     "host_session_id": args.host_session_id,
                     "strict_readonly_required": bool(args.strict_readonly_required),
                     "isolation_level": "logical-readonly", "status": "OPEN",
                     "plans": {}, "results": {}, "history": [],
                     "verification_state": "UNVERIFIED", "next_action": "prepare_scoped_packet"}
        else:
            value = read_json(path, verify=True, label="G6 review controller")
            value.pop("integrity")
            if value["schema_version"] != SCHEMA or value["policy_id"] != POLICY_ID:
                raise ValueError("G6_REVIEW_STATE_SCHEMA")
            if value["status"] == "CLOSED" and args.command not in {"status", "validate", "reconcile"}:
                raise ValueError("G6_REVIEW_CLOSED")
            if args.command in {"status", "validate", "reconcile"}:
                _refresh_reports(value)
                if value["ledger_path"]:
                    state = budget.read_budget(Path(value["ledger_path"]))
                    value["root_usage"] = budget.snapshot(state, work_item_id="review-status", depth=0)
                return value
            if args.command == "plan":
                reviewers = [item.strip() for item in args.reviewers.split(",") if item.strip()]
                if not reviewers:
                    reviewers = ["cp_review_functional_business"]
                if len(reviewers) > 3 or len(reviewers) != len(set(reviewers)):
                    raise ValueError("G6_REVIEW_ROLE_LIMIT")
                for reviewer in reviewers:
                    role_for(reviewer)
                packet = args.packet_sha256 or "UNVERIFIED"
                packet_dir = getattr(args, "packet_dir", "")
                if packet_dir:
                    manifest = _packet_tools().load_manifest(Path(packet_dir).resolve())
                    if args.packet_sha256 and args.packet_sha256 != manifest["packet_sha256"]:
                        raise ValueError("G6_REVIEW_PACKET_CONFLICT")
                    packet = manifest["packet_sha256"]
                key = ref([args.phase, packet, reviewers])[7:]
                value["plans"].setdefault(key, {"phase": args.phase, "packet_sha256": packet,
                    "reviewers": reviewers, "purpose": args.purpose or "Review the scoped changes.",
                    "status": "PLANNED", "packet_dir": packet_dir})
                value["active_plan_key"] = key
                value["verification_state"] = "UNVERIFIED"
                value["next_action"] = "dispatch_with_native_root_budget"
            elif args.command == "dispatch":
                if value["strict_readonly_required"]:
                    value["next_action"] = "obtain_requested_system_isolation_or_continue_unaffected_work"
                elif not value["host_session_id"]:
                    value["next_action"] = "read_current_desktop_session_identity"
                else:
                    role = args.agent_type or args.reviewer
                    role_for(role)
                    plan = value["plans"].get(value.get("active_plan_key"))
                    if plan and (plan["phase"] != args.phase or args.reviewer not in plan["reviewers"]):
                        raise ValueError("G6_REVIEW_ACTIVE_PLAN_MISMATCH")
                    plan = plan or {"packet_sha256": "UNVERIFIED"}
                    task_name = "review_" + ref([value["boundary_id"], args.phase,
                                                 plan["packet_sha256"], role])[7:39]
                    message = (args.scope or "Read the available scoped material and report unknowns.")
                    message += ("\nReturn a raw JSON object with status, findings, checked_scope, "
                                "unverified_items, summary. Include packet_sha256=" + plan["packet_sha256"]
                                + " in checked_scope. Logical-readonly only; do not edit or publish.")
                    cwd = Path(value["repo_path"])
                    if value["ledger_path"]:
                        cwd = Path(budget.read_budget(Path(value["ledger_path"]))["root"]["repo_path"])
                    decision = preview(session_id=value["host_session_id"], cwd=cwd,
                                       agent_type=role, task_name=task_name, message=message,
                                       requested_profile=args.model_profile or None)
                    value["dispatch_decision"] = decision
                    value.setdefault("assignments", {})[args.reviewer] = {
                        "task_name": task_name, "phase": args.phase,
                        "packet_sha256": plan["packet_sha256"], "packet_dir": plan.get("packet_dir", ""),
                        "decision_ref": decision["decision_ref"]}
                    value["verification_state"] = "UNVERIFIED"
                    value["next_action"] = decision["next_action"]
            elif args.command == "result-template":
                report = {"status": "incomplete", "findings": [], "checked_scope": [],
                          "unverified_items": ["Review not completed."], "summary": ""}
                Path(args.output).write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
                value["next_action"] = "consume_native_reviewer_report"
            elif args.command == "result":
                # 中文：人工文件只作待裁决材料；不提升成原生复审通过，也不扣第二份预算。
                # English: A supplied file is unadjudicated material, not proof
                # of native review or a second charge against the budget.
                if args.result_file:
                    raw = bounded_read(Path(args.result_file), 65_536)
                    from .g6_review_receipt_v1 import _report
                    record = {"type": "response_item", "payload": {"type": "message", "role": "assistant",
                              "phase": "final_answer", "content": [{"type": "output_text", "text": raw.decode("utf-8")} ]}}
                    report, reason = _report((json.dumps(record) + "\n").encode("utf-8"))
                    if report is None:
                        raise ValueError("G6_REVIEW_REPORT_INVALID_" + reason)
                    row = {"report_ref": ref(report), "declared_status": report.get("status", "incomplete"),
                           "verification_state": "UNVERIFIED", "finding_refs": [], "packet_current": False}
                    assignment = value.get("assignments", {}).get(args.reviewer)
                    row["assignment_ref"] = ref(assignment or {})
                    if assignment and value["ledger_path"]:
                        from .g6_review_receipt_v1 import _receipt_path
                        state = budget.read_budget(Path(value["ledger_path"]))
                        matches = [pid for pid, permit in state["permits"].items()
                                   if permit["task_name"] == assignment["task_name"]]
                        if len(matches) == 1:
                            receipt_path = _receipt_path(Path(value["ledger_path"]), matches[0])
                            if receipt_path.exists():
                                receipt = read_json(receipt_path, verify=True, label="native review receipt")
                                if (receipt["report_ref"] == row["report_ref"]
                                        and receipt["root_ledger_ref"] == ref(str(Path(value["ledger_path"]).resolve()))
                                        and receipt["root_session_ref"] == state["root"]["host_session_ref"]
                                        and receipt["permit_id"] == matches[0]
                                        and "packet_sha256=" + assignment["packet_sha256"] in report.get("checked_scope", [])):
                                    row.update(verification_state="NATIVE_REPORT_VERIFIED",
                                               finding_refs=receipt["finding_refs"], permit_id=matches[0])
                        row["packet_current"] = _packet_current(assignment.get("packet_dir", ""), value["repo_path"])
                    value["results"][args.reviewer] = row
                value["next_action"] = "reconcile_native_receipt_and_adjudicate_findings"
            elif args.command == "merge":
                _refresh_reports(value)
                plan = value["plans"].get(value.get("active_plan_key"), {})
                rows = [value["results"][reviewer] for reviewer in plan.get("reviewers", [])
                        if reviewer in value["results"]
                        and value.get("assignments", {}).get(reviewer, {}).get("phase") == plan.get("phase")
                        and value["assignments"][reviewer].get("packet_sha256") == plan.get("packet_sha256")]
                refs = [item for row in rows for item in row["finding_refs"]]
                value["merge"] = {"distinct_finding_refs": sorted(set(refs)),
                    "duplicates": len(refs) - len(set(refs)),
                    "reported_blockers": any(row["declared_status"] == "blocking" for row in rows),
                    "unresolved_report_conflict": len({row["declared_status"] for row in rows}) > 1,
                    "semantic_adjudication": "UNVERIFIED"}
                value["verification_state"] = ("NATIVE_REPORTS_CURRENT" if _reports_current(value)
                    else "UNVERIFIED")
                value["next_action"] = "adjudicate_deduplicated_findings_or_continue_unaffected_work"
            elif args.command == "repair":
                for row in value["results"].values():
                    row["packet_current"] = False
                value["verification_state"] = "UNVERIFIED"
                value["next_action"] = "refresh_affected_packet_and_targeted_checks"
            elif args.command == "close":
                _refresh_reports(value)
                value["status"] = "CLOSED"
                value["next_action"] = "deliver_with_explicit_review_evidence_status"
            elif args.command == "isolation":
                value["isolation_level"] = "logical-readonly"
                value["next_action"] = "prepare_scoped_packet"
            elif args.command == "route":
                value["route"] = {"phase": args.phase, "requested_decision": args.decision,
                                  "evidence_state": "UNVERIFIED"}
                value["next_action"] = "plan_default_scoped_review"
            elif args.command in {"finalize-calibration", "sync-calibration"}:
                value["calibration"] = {"status": "NOT_REQUIRED_FOR_DISPATCH", "execution_authorization": "NONE"}
                value["next_action"] = "continue_native_budget_workflow"
            else:
                raise ValueError("G6_REVIEW_COMMAND_UNSUPPORTED")
        value["history"].append({"at": utc_now(), "command": args.command})
        atomic_write_json(path, value, seal=True)
        return value
