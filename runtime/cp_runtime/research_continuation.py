"""中文：将已封存的旧研究尝试承接到新段，不重新派发。

English: Carry a sealed prior study attempt into a new segment without re-dispatch.
"""
from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path

from . import budget_v5 as budget
from .common import atomic_write_json, require_external_state
from .context_final_v2 import read_bound_transcript, extract_final
from .context_recovery_v2 import deadline_for_runtime
from .event_v2 import OwnerTokenLock
from .qualification_study import bind_evaluation, trial_key
from .research_campaign import assert_dispatch
from .research_host_recovery import _terminal_capacity_error
from .routing_context_v4 import read_evaluation
from .routing_contract import _constant, _object, fail, profile_spec, read_document, ref
from .routing_evaluation_v4 import file_reference, trial_packet
from .routing_evaluation_v5 import read_trial


def _read(path: Path) -> dict:
    return json.loads(Path(path).read_text(encoding="utf8"),
                      object_pairs_hook=_object, parse_constant=_constant)


def _normalized_evaluation(value: dict) -> dict:
    """中文：先分别验证研究来源引用，再比较协议内容。
    
    English: Compare protocol content only after each study-specific source_ref is verified.
    """
    result = copy.deepcopy(value)
    for cost in result["costs"]:
        cost.pop("source_ref")
    return result


def _prior_attempt(state: dict, trial_ref: str) -> tuple[str, dict, dict, dict]:
    found = []
    for rid, attempt in state["reservations"].items():
        permit = state["permits"][attempt["permit_id"]]
        request = permit["request"]
        evaluation = read_evaluation(state, case_ref=request["evaluation_case_ref"])
        profile = permit["selection"]["approved_profile"]
        if trial_key(evaluation["protocol_ref"], request["evaluation_case_ref"], profile, 1) == trial_ref:
            found.append((rid, attempt, permit, evaluation))
    if len(found) != 1:
        fail("RESEARCH_CONTINUATION_ORIGINAL_TRIAL")
    return found[0]


def _graded_source(source_path: Path, state: dict, rid: str, trial_ref: str,
                   profile: str, evaluation: dict) -> str:
    folder = source_path.parent
    collection = _read(folder / "trial-results" / trial_ref[7:] / "collection.json")
    grades = [path for path in (folder / "qualification-grades").glob("*.json")
              if _read(path).get("reservation_id") == rid]
    if len(grades) != 1 or collection["reservation_id"] != rid or collection["approved_profile"] != profile:
        fail("RESEARCH_CONTINUATION_GRADE_SOURCE")
    rows = _read(folder / "trial-index.json")["planned_trials"]
    selected = [row for row in rows if row["trial_ref"] == trial_ref]
    if len(selected) != 1:
        fail("RESEARCH_CONTINUATION_SOURCE_CELL")
    gold = _read(folder.parent / "source-map.json")["cells"][selected[0]["source_cell"]]["gold_path"]
    source = {"ledger": str(source_path), "result": str(grades[0]),
              "response": collection["response_path"], "gold": gold,
              "rubric": str(folder.parent / "rubric.json"),
              "transcript": collection["transcript_path"]}
    sample, trace, verified = read_trial(source)
    if (sample["profile_id"] != profile or not trace["native_response_verified"] or
            verified["protocol_ref"] != evaluation["protocol_ref"] or
            sample["response_ref"] != state["accepted_results"][rid]["response_ref"]):
        fail("RESEARCH_CONTINUATION_GRADE_TRACE")
    return file_reference(grades[0])


def _infra_source(source_path: Path, state: dict, rid: str,
                  profile: str) -> str:
    attempt = state["reservations"][rid]
    recovery = state.get("host_terminal_recoveries", {}).get(rid)
    accepted = state["accepted_results"][rid]
    grades = [path for path in (source_path.parent / "qualification-grades").glob("*.json")
              if _read(path).get("reservation_id") == rid]
    if (attempt["outcome"] != "FAILED" or not recovery or
            accepted["status"] != "incomplete" or grades or
            "stop" in state["host_observations"].get(recovery["agent_ref"], {})):
        fail("RESEARCH_CONTINUATION_INFRA_SOURCE")
    proof = _read(Path(recovery["evidence_path"]))
    if ref(proof) != recovery["evidence_ref"] or proof["reservation_id"] != rid:
        fail("RESEARCH_CONTINUATION_INFRA_PROOF")
    original = _read(source_path.parent / "host-capacity-error-unreconciled.json")
    raw, binding = read_bound_transcript(Path(original["transcript_path"]))
    actual_transcript_hash = hashlib.sha256(raw).hexdigest()
    if (original["reservation_id"] != rid or
            actual_transcript_hash != original["transcript_bytes_sha256"] or
            actual_transcript_hash != proof["transcript_bytes_sha256"] or
            actual_transcript_hash != recovery["transcript_bytes_sha256"] or
            ref(binding) != recovery["file_binding_ref"] or
            proof["actual_external_cost"] != "UNKNOWN" or
            proof["refund_claim"] is not False):
        fail("RESEARCH_CONTINUATION_INFRA_TRANSCRIPT")
    events = [json.loads(line, object_pairs_hook=_object, parse_constant=_constant)
              for line in raw.splitlines()]
    spec = profile_spec(profile)
    _, terminal = _terminal_capacity_error(events, model=spec["model"], effort=spec["effort"])
    if ref(terminal) != proof["terminal_event_ref"]:
        fail("RESEARCH_CONTINUATION_INFRA_TERMINAL")
    return recovery["evidence_ref"]


def _reader_denial_source(source_path: Path, state: dict, rid: str,
                          trial_ref: str, profile: str) -> str:
    """中文：将旧控制器独有的读取拒绝绑定到原始宿主字节。
    
    English: Bind an old controller-only reader denial to its original host bytes.
    """
    attempt = state["reservations"][rid]
    accepted = state["accepted_results"][rid]
    recovery = state.get("context_recovery", {}).get(rid, {})
    if (attempt["state"] != "COMPLETED" or accepted["status"] != "incomplete" or
            recovery.get("status") != "DENIED" or
            state["host_receipts"].get(rid, {}).get("disposition") != "created" or
            rid not in state["context_reads"] or rid in state["context_deliveries"] or
            rid in state.get("context_wire_deliveries", {}) or
            rid in state["context_finals"] or rid in state["context_raw_finals"] or
            any(_read(path).get("reservation_id") == rid for path in
                (source_path.parent / "qualification-grades").glob("*.json")) or
            (source_path.parent / "trial-results" / trial_ref[7:] / "collection.json").exists()):
        fail("RESEARCH_CONTINUATION_READER_SOURCE")
    proof = _read(source_path.parent / "reader-window-denial" / (rid + ".json"))
    if (proof.get("schema_version") != "study2-reader-window-denial/1" or
            proof.get("reservation_id") != rid or proof.get("trial_ref") != trial_ref or
            proof.get("permit_id") != attempt["permit_id"] or
            proof.get("recorded_denial") != recovery["reason"] or
            proof.get("model_review_grade") != "UNRECORDED" or
            proof.get("controller_result_status") != "incomplete" or
            proof.get("refund_claim") is not False or
            proof.get("actual_external_cost") != "UNKNOWN"):
        fail("RESEARCH_CONTINUATION_READER_PROOF")
    semantic_path = source_path.parent / "review" / "semantic" / (accepted["response_ref"][7:] + ".json")
    semantic = _read(semantic_path)
    if (file_reference(semantic_path) != accepted["response_ref"] or
            semantic.get("status") != "incomplete" or ref(proof) not in semantic.get("unverified_items", [])):
        fail("RESEARCH_CONTINUATION_READER_ACCOUNTING")
    raw, binding = read_bound_transcript(Path(proof["transcript_path"]))
    events = [json.loads(line, object_pairs_hook=_object, parse_constant=_constant)
              for line in raw.splitlines()]
    header = events[0]["payload"]
    spawn = header["source"]["subagent"]["thread_spawn"]
    permit = state["permits"][attempt["permit_id"]]
    from .routing_hook_v5 import _header_from_bytes
    linked = _header_from_bytes({"session_id": spawn["parent_thread_id"],
                                 "agent_id": header["id"], "agent_type": permit["role"]},
                                state, raw.splitlines()[0], binding)
    if (hashlib.sha256(raw).hexdigest() != proof["transcript_bytes_sha256"] or
            ref(binding) != proof["transcript_file_binding_ref"] or
            ref(linked) != state["host_identity_links"][rid]["proof_ref"] or
            header["id"] != proof["child_id"] or
            state["host_identity_links"][rid]["agent_ref"] != ref(header["id"]) or
            ref(spawn["parent_thread_id"]) != state["root_binding"]["host_session_ref"] or
            ref(spawn["agent_path"].rsplit("/", 1)[-1]) != permit["dispatch_ref"] or
            spawn["agent_role"] != permit["role"] or
            state["host_observations"].get(ref(header["id"]), {}).get("stop") != "UNKNOWN"):
        fail("RESEARCH_CONTINUATION_READER_TRANSCRIPT")
    final_text, _ = extract_final(raw, child_id=header["id"],
                                  root_id=spawn["parent_thread_id"],
                                  task_path=spawn["agent_path"], role=permit["role"],
                                  repo_path=state["root_binding"]["repo_path"])
    final = json.loads(final_text, object_pairs_hook=_object, parse_constant=_constant)
    if final.get("status") != "incomplete" or final.get("findings") != []:
        fail("RESEARCH_CONTINUATION_READER_FINAL")
    from .routing_hook_v5 import _grant_path
    grant_path = _grant_path(source_path, spawn["parent_thread_id"], header["id"])
    grant = _read(grant_path)
    completions = [event["payload"] for event in events if event["type"] == "event_msg"
                   and event["payload"].get("type") == "item_completed"
                   and event["payload"].get("item", {}).get("type") == "CommandExecution"]
    if len(completions) != 1:
        fail("RESEARCH_CONTINUATION_READER_COMMAND")
    completion = completions[0]
    command = completion["item"]
    elapsed = completion["completed_at_ms"] - recovery["first_ms"]
    limit = deadline_for_runtime(state["root_binding"]["context_runtime"])
    if (str(grant_path) != proof["grant_path"] or grant["reservation_id"] != rid or
            grant["call_ref"] != state["context_reads"][rid]["call_ref"] or
            "sha256:" + hashlib.sha256(grant["output"].encode()).hexdigest() != state["context_reads"][rid]["output_ref"] or
            hashlib.sha256(grant["wire"].encode()).hexdigest() != grant["wire_sha256"] or
            grant["wire_sha256"] != proof["wire_sha256"] or
            command["source"] != "unified_exec_startup" or command["status"] != "completed" or
            command["exit_code"] != 0 or command["stdout"] != grant["wire"] or
            command["aggregated_output"] != grant["wire"] or command["stderr"] != "" or
            ref(completion) != proof["command_completion_ref"] or
            recovery["first_ms"] != proof["first_ms"] or
            completion["started_at_ms"] != proof["command_started_ms"] or
            completion["completed_at_ms"] != proof["command_completed_ms"] or
            elapsed != proof["reader_window_elapsed_ms"] or limit != proof["allowed_elapsed_ms"] or
            elapsed <= limit or profile != permit["selection"]["approved_profile"]):
        fail("RESEARCH_CONTINUATION_READER_WINDOW")
    return ref(proof)


def carry_attempt(target_path: Path, source_path: Path, *, trial_ref: str,
                  cwd: str, host_session_id: str) -> dict:
    """中文：核验两个完整且不同的研究根后，追加历史承接记录。
    
    English: Append a historical carry after verifying both full, distinct study roots.
    """
    target_path = Path(target_path).absolute()
    source_path = Path(source_path).absolute()
    with OwnerTokenLock(target_path, timeout=2):
        events = budget._read_events(target_path)
        target = budget.replay(events)
        source = budget.read_budget(source_path)
        if (not source["closed"] or source["outcome"] != "PARTIAL" or
                target["closed"] or target["reservations"] or target["permits"] or
                target["identity"]["project_id"] != source["identity"]["project_id"] or
                target["identity"]["repo_fingerprint"] != source["identity"]["repo_fingerprint"] or
                target["identity"]["task_id"] == source["identity"]["task_id"] or
                target_path == source_path):
            fail("RESEARCH_CONTINUATION_ROOT_SCOPE")
        envelope, _ = read_document(Path(target["sources"]["root_envelope"]))
        declared = envelope["routing"]["research_campaign"]
        assert_dispatch(declared, target, cwd=cwd, session=host_session_id)
        rid, attempt, permit, evaluation = _prior_attempt(source, trial_ref)
        accepted = source["accepted_results"].get(rid)
        profile = permit["selection"]["approved_profile"]
        request = permit["request"]
        case_ref = request["evaluation_case_ref"]
        if (attempt["state"] != "COMPLETED" or not accepted or
                source["host_receipts"].get(rid, {}).get("disposition") != "created" or
                request["packet_sha256"] != trial_packet(case_ref, profile, 1)):
            fail("RESEARCH_CONTINUATION_ORIGINAL_ACCOUNTING")
        target_evaluation = read_evaluation(target, case_ref=case_ref)
        source_envelope = _read(source_path.parent.parent / "study-envelope.json")
        target_envelope = _read(target_path.parent.parent / "study-envelope.json")
        if (bind_evaluation(source_envelope, evaluation["protocol_ref"]) != evaluation or
                bind_evaluation(target_envelope, target_evaluation["protocol_ref"]) != target_evaluation):
            fail("RESEARCH_CONTINUATION_STUDY_COST_SOURCE")
        slot_id = "trial_" + trial_ref[7:59]
        slot = budget._slot(target, slot_id)
        if (_normalized_evaluation(target_evaluation) != _normalized_evaluation(evaluation) or
                ref(slot["scenario"]) != ref(request["scenario"]) or
                not any(option["profile_id"] == profile for option in slot["options"])):
            fail("RESEARCH_CONTINUATION_TARGET_BINDING")
        if rid in source.get("host_terminal_recoveries", {}):
            disposition = "HOST_INFRA_UNGRADED"
            grade_ref = ""
            source_evidence_ref = _infra_source(source_path, source, rid, profile)
        elif accepted["status"] == "incomplete" and source.get("context_recovery", {}).get(rid, {}).get("status") == "DENIED":
            disposition = "READER_PROTOCOL_UNGRADED"
            grade_ref = ""
            source_evidence_ref = _reader_denial_source(source_path, source, rid, trial_ref, profile)
        else:
            disposition = "MODEL_GRADED"
            grade_ref = _graded_source(source_path, source, rid, trial_ref, profile, evaluation)
            source_evidence_ref = grade_ref
        evidence = {"schema_version": "research-historical-attempt-carry-proof/1",
                    "target_task_id": target["identity"]["task_id"],
                    "target_ledger_head_before": target["head_hash"],
                    "slot_id": slot_id, "trial_ref": trial_ref,
                    "source_ledger_path": str(source_path),
                    "source_ledger_head_hash": source["head_hash"],
                    "source_task_id": source["identity"]["task_id"],
                    "source_reservation_id": rid,
                    "source_result_ref": accepted["result_ref"],
                    "source_grade_ref": grade_ref,
                    "source_evidence_ref": source_evidence_ref,
                    "disposition": disposition,
                    "new_model_call": False,
                    "refund_claim": False,
                    "actual_external_cost": "UNKNOWN"}
        evidence_path = target_path.parent / "historical-carries" / (trial_ref[7:] + ".json")
        require_external_state(evidence_path, Path(cwd))
        evidence_path.parent.mkdir(parents=True, exist_ok=True)
        if evidence_path.exists():
            if _read(evidence_path) != evidence:
                fail("RESEARCH_CONTINUATION_CARRY_PROOF_CONFLICT")
        else:
            atomic_write_json(evidence_path, evidence)
        data = {"slot_id": slot_id, "trial_ref": trial_ref,
                "profile_id": profile, "scenario_ref": ref(slot["scenario"]),
                "source_ledger_path": str(source_path),
                "source_ledger_head_hash": source["head_hash"],
                "source_project_id": source["identity"]["project_id"],
                "source_repo_fingerprint": source["identity"]["repo_fingerprint"],
                "source_task_id": source["identity"]["task_id"],
                "source_reservation_id": rid,
                "source_result_ref": accepted["result_ref"],
                "source_grade_ref": grade_ref,
                "source_evidence_ref": source_evidence_ref,
                "carry_evidence_ref": ref(evidence),
                "carry_evidence_path": str(evidence_path),
                "disposition": disposition}
        updated = budget._append(target_path, events,
                                 budget._event(target, target["identity"],
                                               "HISTORICAL_ATTEMPT_CARRIED", data))
        if updated["historical_carries"][slot_id] != data:
            fail("RESEARCH_CONTINUATION_CARRY_READBACK")
        return {"schema_version": "research-historical-carry-receipt/1",
                "trial_ref": trial_ref, "slot_id": slot_id,
                "source_reservation_id": rid,
                "disposition": disposition,
                "carry_evidence_ref": ref(evidence),
                "new_model_call": False,
                "refund_claim": False}


def seal_ungraded_attempt(ledger_path: Path, *, trial_ref: str, reason_code: str,
                          cwd: str, host_session_id: str) -> dict:
    """中文：仅释放失败槽的未来预留，保留已创建调用的费用。
    
    English: Release only the failed slot's future claim; keep its created cost.
    """
    ledger_path = Path(ledger_path).absolute()
    state = budget.read_budget(ledger_path)
    if state["closed"] or state["root_binding"]["context_runtime"].get("research_contract") != "desktop-research-campaign/2":
        fail("RESEARCH_UNGRADED_V2_ROOT_REQUIRED")
    envelope, _ = read_document(Path(state["sources"]["root_envelope"]))
    assert_dispatch(envelope["routing"]["research_campaign"], state,
                    cwd=cwd, session=host_session_id)
    rid, attempt, permit, _ = _prior_attempt(state, trial_ref)
    profile = permit["selection"]["approved_profile"]
    if reason_code == "READER_PROTOCOL_DENIED":
        evidence_ref = _reader_denial_source(ledger_path, state, rid, trial_ref, profile)
        evidence_path = ledger_path.parent / "reader-window-denial" / (rid + ".json")
    elif reason_code == "HOST_CAPACITY_ERROR":
        evidence_ref = _infra_source(ledger_path, state, rid, profile)
        evidence_path = Path(state["host_terminal_recoveries"][rid]["evidence_path"])
    else:
        fail("RESEARCH_UNGRADED_REASON")
    data = {"slot_id": permit["slot_id"], "trial_ref": trial_ref,
            "reservation_id": rid,
            "accepted_result_ref": state["accepted_results"][rid]["result_ref"],
            "evidence_ref": evidence_ref,
            "evidence_path": str(evidence_path), "reason_code": reason_code}
    usage_before = budget._usage(state)["resources"].copy()
    updated = budget.seal_ungraded_evaluation(ledger_path, data)
    if (updated["ungraded_seals"][rid] != data or
            budget._slot(updated, permit["slot_id"])["status"] != "UNGRADABLE" or
            budget._usage(updated)["resources"] != usage_before):
        fail("RESEARCH_UNGRADED_SEAL_READBACK")
    return {"schema_version": "research-ungraded-seal-receipt/1",
            "trial_ref": trial_ref, "reservation_id": rid,
            "reason_code": reason_code, "evidence_ref": evidence_ref,
            "model_grade": "UNRECORDED", "refund_claim": False,
            "created_attempts_after": usage_before["attempts"]}
