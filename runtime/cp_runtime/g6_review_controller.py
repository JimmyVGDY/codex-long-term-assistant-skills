"""中文：G6 复审工作流只引用根预算，不执行旧评分或重复计费。

English: G6 review workflow references the root budget, without legacy scoring
or a second accounting system.
"""
from __future__ import annotations

import json
import importlib.util
import contextlib
import io
import hashlib
import os
import re
from pathlib import Path
from typing import Any

from . import g6_budget_v1 as budget
from .common import atomic_write_json, read_json, require_external_state, resolve_codex_home, utc_now
from .path_identity import same_path
from .event_v2 import OwnerTokenLock
from .g6_flexible_policy import POLICY_ID
from .g6_hook_v1 import preview
from .routing_contract import ref, role_for
from .capability_store import bounded_read

SCHEMA = "g6-review-state/1"


def _packet_tools():
    package_root = Path(__file__).resolve().parents[2]
    relative = "skills/multi-agent-independent-review/scripts/review_packet.py"
    path = package_root / relative
    if not path.is_file():
        # 中文：增强 Hook 使用账户 runtime；脚本仍在当前 Plugin cache，须核对同版来源。
        # English: Enhanced hooks use account runtime; load the matching verified Plugin script.
        home = resolve_codex_home()
        if not same_path(package_root, home):
            raise ValueError("G6_PACKET_TOOL_UNAVAILABLE")
        installed = json.loads(bounded_read(home / "cp-assistant-v6-state.json", 262_144))
        version = installed.get("version")
        if installed.get("mode") != "plugin" or not isinstance(version, str) or not re.fullmatch(r"\d+\.\d+\.\d+", version):
            raise ValueError("G6_PACKET_INSTALLATION_UNAVAILABLE")
        package_root = home / "plugins/cache/cp-assistant-local/codex-cross-project-engineering-assistant" / version
        from .payload_integrity import load_manifest
        manifest = load_manifest(package_root / "PLUGIN_PAYLOAD_MANIFEST.json")
        entries = {item["path"]: item for item in manifest["files"]}
        path = package_root / relative
        for name, source in ((relative, path), ("runtime/cp_runtime/g6_review_controller.py", Path(__file__))):
            if name not in entries or hashlib.sha256(bounded_read(source, 1_048_576)).hexdigest() != entries[name]["sha256"]:
                raise ValueError("G6_INSTALLED_PACKET_TOOL_CHANGED")
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


def _native_root(value: dict[str, Any], *, required: bool = False) -> Path | None:
    from .g6_handoff_v1 import read
    session = value.get("host_session_id")
    binding = read(session) if session else None
    if binding is None:
        if required:
            raise ValueError("G6_NATIVE_ROOT_NOT_BOUND")
        return None
    ledger = Path(binding["new_ledger_path"])
    root = budget.read_budget(ledger)["root"]
    if (root["host_session_ref"] != ref(session) or not same_path(Path(root["repo_path"]), Path(value["repo_path"]))
            or value.get("ledger_path") and not same_path(Path(value["ledger_path"]), ledger)):
        raise ValueError("G6_REVIEW_NATIVE_ROOT_CONFLICT")
    value["ledger_path"] = str(ledger)
    value["root_task_id"] = root["task_id"]
    return ledger


def _register_plan(value: dict[str, Any], plan: dict[str, Any], args: Any) -> None:
    ledger = _native_root(value)
    if ledger is None or not plan.get("packet_dir"):
        return
    from .g6_runtime_support import installed_allowance_support
    if not installed_allowance_support()["supported"]:
        raise ValueError("G6_INSTALLED_ALLOWANCE_READER_UNAVAILABLE")
    from .g6_review_requests import register_work
    stage = getattr(args, "review_stage", None) or plan.get("review_stage") or (
        "pre_review" if plan["phase"] == "pre" else "post_review")
    if (plan["phase"] == "pre") != (stage == "pre_review"):
        raise ValueError("G6_REVIEW_STAGE_CONFLICT")
    profile = getattr(args, "model_profile", None) or plan.get("model_profile") or "g6-sol-medium"
    allowed = getattr(args, "allowed_path", None) or plan.get("allowed_paths") or None
    work_ids = {}
    for role in plan["reviewers"]:
        work = register_work(ledger, boundary_id=value["boundary_id"], phase=stage, role=role,
                             profile_id=profile, packet_dir=Path(plan["packet_dir"]),
                             purpose=plan["purpose"], allowed_paths=allowed)
        work_ids[role] = work["work_id"]
    plan.update(work_ids=work_ids, review_stage=stage, model_profile=profile, allowed_paths=allowed)
    if getattr(args, "reserve_repair", False) and stage == "post_review":
        plan["future_work_ids"] = {role: register_work(ledger, boundary_id=value["boundary_id"],
            phase="repair_review", role=role, profile_id=profile, packet_dir=Path(plan["packet_dir"]),
            purpose=plan["purpose"], allowed_paths=allowed)["work_id"] for role in plan["reviewers"]}
    state = budget.read_budget(ledger)
    required = [*work_ids.values(), *plan.get("future_work_ids", {}).values()]
    plan["unfunded_required_work"] = [key for key in required if not state["review_work"][key]["base_funded"]
                                     and not any(row["work_id"] == key for row in budget.allowance.buckets(state).values())]


def _allowance_command(value: dict[str, Any], args: Any) -> None:
    from . import g6_allowance_authority as authority, g6_allowance_contract as contract
    from .g6_runtime_support import installed_allowance_support
    support = installed_allowance_support()
    if not support["supported"]:
        value.pop("allowance_request", None)
        value["allowance_status"] = support
        value["next_action"] = "install_matching_allowance_reader_before_requesting_approval"
        return
    if args.command == "bind-native-source":
        session = value.get("host_session_id")
        if not session or os.environ.get("CODEX_THREAD_ID") != session:
            raise ValueError("G6_CURRENT_NATIVE_SESSION_REQUIRED")
        repo = Path(value["repo_path"])
        transcript = Path(args.transcript_path).resolve()
        authority._native_header(transcript, session_id=session, cwd=repo)
        if _native_root(value) is None:
            from .g6_hook_v1 import _ensure_new_session
            if not _ensure_new_session({"session_id": session, "cwd": str(repo)}):
                raise ValueError("G6_LEGACY_POLICY_AMENDMENT_UNSUPPORTED")
        ledger = _native_root(value, required=True)
        authority.bind_source(ledger, {"session_id": session, "cwd": str(repo),
                                      "transcript_path": str(transcript), "turn_id": ""})
        value["next_action"] = "register_required_review_plan"
        value["allowance_status"] = {"status": "NATIVE_SOURCE_BOUND", "allowance_protocol": "g6-allowance/1"}
        return
    ledger = _native_root(value, required=True)
    recovery = authority.recover(ledger)
    value["allowance_recovery"] = recovery
    if args.command == "allowance-quote":
        value.pop("allowance_request", None)
        if recovery.get("has_more"):
            value["allowance_status"] = {"status": "AUTHORITY_RECOVERY_IN_PROGRESS", "supported": True}
            value["next_action"] = "continue_native_authority_recovery"
            return
        if value["strict_readonly_required"]:
            value["allowance_status"] = {"status": "SYSTEM_ISOLATION_UNVERIFIED", "supported": False}
            value["next_action"] = "obtain_required_system_isolation_before_requesting_allowance"
            return
        if recovery["status"] == "NATIVE_SOURCE_UNAVAILABLE":
            value["allowance_status"] = {"status": "NATIVE_SOURCE_UNAVAILABLE", "supported": False}
            value["next_action"] = "bind_current_native_parent_source"
            return
        plan = value["plans"].get(value.get("active_plan_key"))
        if not plan:
            raise ValueError("G6_ALLOWANCE_PLAN_REQUIRED")
        _register_plan(value, plan, args)
        rows = plan.get("future_work_ids" if getattr(args, "future_review", False) else "work_ids", {})
        role = getattr(args, "reviewer", "")
        if role and role not in rows:
            raise ValueError("G6_ALLOWANCE_REVIEWER_NOT_PLANNED")
        work_ids = [rows[role]] if role else list(rows.values())
        if not work_ids:
            raise ValueError("G6_ALLOWANCE_REGISTERED_WORK_REQUIRED")
        state = budget.read_budget(ledger)
        from .routing_contract import integer
        integer(args.additional_reviews, "G6_ALLOWANCE_DISPATCHES", minimum=1, maximum=8)
        active = [pid for pid in state["reservations"] if state["permits"][pid]["work_item_id"] in work_ids
                  and pid not in state["terminals"] and state["receipts"].get(pid, {}).get("disposition") != "not_started"]
        if active:
            value["allowance_status"] = {"status": "NATIVE_OUTCOME_PENDING", "permit_ids": active}
            value["next_action"] = "resume_existing_review"
            return
        from .g6_review_requests import _same_packet_completed
        if any(_same_packet_completed(ledger, state, key, plan["packet_sha256"]) for key in work_ids):
            value["allowance_status"] = {"status": "REVIEW_ALREADY_COMPLETE"}
            value["next_action"] = "use_current_review_result_or_refresh_changed_material"
            return
        needed = {}
        for key in work_ids:
            available = 0
            for funding, bucket in budget.allowance.buckets(state).items():
                if bucket["work_id"] != key:
                    continue
                usage = budget._usage(state, key, funding)
                remaining_units = bucket["units"] - usage["completed_charged_units"] - usage["inflight_reserved_units"]
                remaining_attempts = bucket["attempts"] - usage["completed_charged_attempts"] - usage["inflight_reserved_attempts"]
                available += min(remaining_units // budget.profile_spec(bucket["profile_id"])["planning_units"], remaining_attempts)
            if available < args.additional_reviews:
                needed[key] = args.additional_reviews - available
        if not needed:
            value["allowance_status"] = {"status": "ALREADY_AUTHORIZED", "work_ids": work_ids}
            value["next_action"] = "dispatch_with_existing_allowance"
            return
        request = budget.request_allowance(ledger, work_ids=list(needed), dispatches=needed, retry_limit=args.retry_limit)
        state = budget.read_budget(ledger)
        value["allowance_request"] = {**request,
            "question": contract.quote_question(request, state["review_work"], getattr(args, "locale", "zh-CN")),
            "options": contract.quote_options(getattr(args, "locale", "zh-CN")), "supported": True,
            "authority_status": "PENDING_NATIVE_USER_RESPONSE", "actual_credits": None}
        source = authority._read_source(authority.source_path(ledger))
        value["next_action"] = ("await_existing_allowance_authorization" if request["request_id"] in source["presented_requests"]
                                else "ask_exact_allowance_question_once_then_recover")
    else:
        value["allowance_status"] = budget.allowance_status(budget.read_budget(ledger))
        value["next_action"] = recovery["next_action"]


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
            if value["status"] == "CLOSED" and args.command not in {"status", "validate", "reconcile", "allowance-status"}:
                raise ValueError("G6_REVIEW_CLOSED")
            _native_root(value)
            if args.command in {"status", "validate", "reconcile"}:
                _refresh_reports(value)
                if value["ledger_path"]:
                    state = budget.read_budget(Path(value["ledger_path"]))
                    value["root_usage"] = budget.snapshot(state, work_item_id="review-status", depth=0)
                    value["allowance_status"] = budget.allowance_status(state)
                return value
            if args.command in {"bind-native-source", "allowance-quote", "allowance-status", "allowance-recover"}:
                _allowance_command(value, args)
            elif args.command == "plan":
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
                _register_plan(value, value["plans"][key], args)
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
                    if plan.get("packet_dir") and _native_root(value) is not None:
                        from .g6_allowance_authority import recover
                        from .g6_review_requests import bind_call
                        recovery = recover(Path(value["ledger_path"]))
                        if recovery.get("has_more"):
                            value["dispatch_decision"] = {"decision": "WAIT_RECONCILE",
                                "next_action": "continue_native_authority_recovery", "exact_tool_parameters": None}
                            value["next_action"] = "continue_native_authority_recovery"
                            value["history"].append({"at": utc_now(), "command": args.command})
                            atomic_write_json(path, value, seal=True)
                            return value
                        _register_plan(value, plan, args)
                        if role not in plan.get("work_ids", {}):
                            raise ValueError("G6_REVIEW_ROLE_NOT_REGISTERED")
                        native_state = budget.read_budget(Path(value["ledger_path"]))
                        active = [(pid, native_state["permits"][pid]) for pid in native_state["reservations"]
                                  if native_state["permits"][pid]["work_item_id"] == plan["work_ids"][role]
                                  and pid not in native_state["terminals"]
                                  and native_state["receipts"].get(pid, {}).get("disposition") != "not_started"]
                        if active:
                            if len(active) != 1:
                                raise ValueError("G6_REVIEW_ACTIVE_CALL_CONFLICT")
                            pid, permit = active[0]
                            value["existing_dispatch"] = {"permit_id": pid, "task_name": permit["task_name"],
                                "host_call_ref": native_state["reservations"][pid]["host_call_ref"],
                                "receipt": native_state["receipts"].get(pid)}
                            value["dispatch_decision"] = {"decision": "WAIT_RECONCILE",
                                "next_action": "resume_existing_review", "exact_tool_parameters": None}
                            value["next_action"] = "resume_existing_review"
                            value["history"].append({"at": utc_now(), "command": args.command})
                            atomic_write_json(path, value, seal=True)
                            return value
                        call = bind_call(Path(value["ledger_path"]), work_id=plan["work_ids"][role],
                                         packet_dir=Path(plan["packet_dir"]), instructions=args.scope or "")
                        task_name, message = call["task_name"], call["message"]
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
                    if decision.get("exact_tool_parameters") is None and plan.get("work_ids", {}).get(role):
                        from .g6_hook_v1 import admission_diagnostic
                        state = budget.read_budget(Path(value["ledger_path"]))
                        value["dispatch_recovery"] = admission_diagnostic(state, plan["work_ids"][role],
                                                                         plan["model_profile"], decision)
                        value["next_action"] = value["dispatch_recovery"]["next_action"]
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
                if value["ledger_path"]:
                    ids = {work_id for plan in value["plans"].values()
                           for work_id in [*plan.get("work_ids", {}).values(), *plan.get("future_work_ids", {}).values()]}
                    for work_id in sorted(ids):
                        budget.close_review_work(Path(value["ledger_path"]), work_id)
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
