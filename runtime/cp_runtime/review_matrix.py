"""中文：V8 复审状态机；旧 V7 状态由原控制器按旧契约继续处理。

English: Scored V8 review workflow. The existing controller retains its frozen V7 path.
"""
from __future__ import annotations

import json
import os
import secrets
from pathlib import Path
from typing import Any, Mapping

from .common import atomic_write_json, atomic_write_text, read_json, repo_snapshot, require_external_state, utc_now
from .delegation_budget import bind_review_attempt, native_review_message_prefix, read_budget, sha256_ref
from .dispatch_context import read_request_document, read_request_json, verify_root_binding
from .dispatch_policy import (CURRENT_POLICY_ID, DispatchPolicyError, canonical_json, digest,
                              is_premium, policy, policy_digest, resolve_evidence, score_review, validate_scorecard)
from .event_v3 import OwnerTokenLock, project_id_for, stable_repo_fingerprint
from .project import validate_binding
from .review_contract import (REVIEW_STATE_SCHEMA_VERSION, assignment_from_score, default_isolation,
                              derive_isolation, result_template, validate_result)

STATE_FILE = "review-state.json"
DEFAULT_LIMITS = {"max_agent_depth": 2, "max_post_review_rounds": 2, "max_preimplementation_rounds": 1,
                  "max_preimplementation_reviewers": 2, "max_parallel_reviewers": 3, "max_total_reviewers": 6,
                  "max_repair_rounds": 2, "max_terra_high_reviewers": 1,
                  "max_premium_reviewers": policy()["premium_limits"]["max_dispatches"],
                  "max_premium_parallel": policy()["premium_limits"]["max_parallel"],
                  "max_astra_high_reviewers": policy()["premium_limits"]["max_astra_high"]}
HARD_LIMITS = {**DEFAULT_LIMITS, "max_agent_depth": 3, "max_post_review_rounds": 3,
               "max_preimplementation_reviewers": 4, "max_parallel_reviewers": 6,
               "max_total_reviewers": 12, "max_repair_rounds": 3, "max_terra_high_reviewers": 2}


def _fail(message: str) -> None:
    raise DispatchPolicyError(message)


def _rounds(state: Mapping[str, Any]):
    for phase in ("pre", "post"):
        for key in sorted(state["phases"][phase]["rounds"], key=int):
            yield state["phases"][phase]["rounds"][key]


def _dispatches(state: Mapping[str, Any]):
    for row in _rounds(state):
        for reviewer, item in row["dispatch"].items():
            yield row, reviewer, item


def _round(state: Mapping[str, Any], phase: str, number: int) -> dict[str, Any]:
    value = state["phases"][phase]["rounds"].get(str(number))
    if not isinstance(value, dict):
        _fail("REVIEW_ROUND_MISSING")
    return value


def _budget(state: Mapping[str, Any], args: Any, *, live: bool = True) -> dict[str, Any] | None:
    binding = state["delegation_budget"]
    if not binding["ledger_path"]:
        return None
    budget = read_budget(Path(binding["ledger_path"]))
    if budget["schema_version"] != "3.0" or budget["identity"]["budget_id"] != binding["budget_id"] \
            or any(budget["identity"][key] != state[key] for key in ("task_id", "project_id", "repo_fingerprint")) \
            or budget["policy_id"] != state["policy_id"] or budget["policy_digest"] != state["policy_digest"]:
        _fail("REVIEW_BUDGET_BINDING_MISMATCH")
    if live:
        envelope = getattr(args, "root_envelope", "") or binding["root_envelope"]
        session = getattr(args, "host_session_id", "") or os.environ.get("CODEX_THREAD_ID", "")
        if not envelope:
            _fail("REVIEW_ROOT_ENVELOPE_MISSING")
        verify_root_binding(budget["root_binding"], budget["identity"], envelope_path=Path(envelope),
                            cwd=str(Path.cwd()), host_session_id=session)
    return budget


def validate_state(state: Mapping[str, Any]) -> None:
    if state.get("schema_version") != REVIEW_STATE_SCHEMA_VERSION:
        _fail("REVIEW_STATE_VERSION_UNSUPPORTED")
    policy(state["policy_id"], state["policy_digest"])
    if state["review_state_ref"] != sha256_ref(state["review_state_id"]):
        _fail("REVIEW_STATE_OWNER_MISMATCH")
    if any(type(value) is not int or value < 1 or value > HARD_LIMITS.get(key, 0) for key, value in state["limits"].items()) \
            or set(state["limits"]) != set(DEFAULT_LIMITS):
        _fail("REVIEW_LIMITS_INVALID")
    level, strict = derive_isolation(state["isolation"])
    if (level, strict) != (state["isolation"]["isolation_level"], state["isolation"]["strict_readonly_eligible"]):
        _fail("REVIEW_ISOLATION_INVALID")
    count = 0
    permits: set[str] = set()
    for row in _rounds(state):
        planned = set(row["planned_reviewers"])
        if len(planned) != len(row["planned_reviewers"]) or set(row["dispatch"]) - planned or set(row["results"]) - set(row["dispatch"]):
            _fail("REVIEW_ROUND_ASSIGNMENTS_INVALID")
        for reviewer, item in row["dispatch"].items():
            count += 1
            score = validate_scorecard(item["selection_scorecard"])
            if score["policy_id"] != state["policy_id"] or score["policy_digest"] != state["policy_digest"] \
                    or any(score["context"][key] != state[key] for key in ("project_id", "task_id", "repo_fingerprint")) \
                    or score["context"]["packet_sha256"] != row["packet_sha256"]:
                _fail("REVIEW_SCORE_CONTEXT_MISMATCH")
            expected = assignment_from_score(score, item["acceptable_profiles"], review_state_ref=state["review_state_ref"],
                                               permit_ref=item["delegation_dispatch_ref"])
            if canonical_json(item["dispatch_assignment"]) != canonical_json(expected):
                _fail("REVIEW_SCORE_ASSIGNMENT_MISMATCH")
            ref = item["delegation_dispatch_ref"]
            if ref:
                if ref in permits:
                    _fail("REVIEW_PERMIT_REUSED")
                permits.add(ref)
            if reviewer in row["results"]:
                validate_result(row["results"][reviewer]["payload"], expected_assignment=expected,
                                expected_identity={"task_id": state["task_id"], "boundary_id": state["boundary_id"],
                                                   "reviewer": reviewer, "review_phase": row["phase"],
                                                   "review_round": row["round"], "packet_sha256": row["packet_sha256"]})
    if count != state["counters"]["total_reviewers"] or count > state["limits"]["max_total_reviewers"]:
        _fail("REVIEW_TOTAL_COUNTER_MISMATCH")
    records = list(_dispatches(state))
    premium = [entry for entry in records if is_premium(entry[2]["selection_scorecard"]["approved_profile"], state["policy_id"])]
    if len(premium) > state["limits"]["max_premium_reviewers"] \
            or sum(name not in row["results"] for row, name, _item in premium) > state["limits"]["max_premium_parallel"] \
            or sum(len(_active(row)) for row in _rounds(state)) > state["limits"]["max_parallel_reviewers"]:
        _fail("REVIEW_REPLAY_LIMIT_EXCEEDED")


def _write(directory: Path, state: dict[str, Any]) -> None:
    state["updated_at"] = utc_now()
    validate_state(state)
    atomic_write_json(directory / STATE_FILE, state, seal=True)
    _sync_calibration(directory, state)


def _sync_calibration(directory: Path, state: Mapping[str, Any]) -> None:
    records = []
    for row in _rounds(state):
        for reviewer, result in row["results"].items():
            payload = result["payload"]
            assignment = payload["dispatch_assignment"]
            record = {"record_id": "RCR_" + digest([state["task_id"], reviewer, payload["result_id"]])[7:],
                      "timestamp": result["completed_at"],
                      "task_id": state["task_id"], "project_id": state["project_id"],
                      "repo_fingerprint": state["repo_fingerprint"], "reviewer_results": [{
                          "reviewer": reviewer, "result_id": payload["result_id"],
                          "review_phase": row["phase"], "review_round": row["round"], "packet_sha256": row["packet_sha256"],
                          "task_difficulty": payload["task_difficulty"], "duration_ms": payload["duration_ms"],
                          "estimated_cost_units": assignment["cost_basis_units"], "cost_basis_units": assignment["cost_basis_units"],
                          "cost_basis_profile": assignment["approved_profile"], "approved_dispatch_profile": assignment["approved_profile"],
                          "policy_id": state["policy_id"], "policy_digest": state["policy_digest"],
                          "cost_formula_version": payload["cost_formula_version"], "selection_ref": assignment["selection_ref"],
                          "comparison_pairs": [pair for pair in policy(state["policy_id"])["comparison_pairs"]
                                               if assignment["approved_profile"] in pair["profiles"]],
                          "calibration_finalized": bool(result.get("calibration_finalization")),
                          **{key: result.get("calibration_finalization", {}).get(key, payload[key])
                             for key in ("accepted", "rejected", "duplicate", "repaired", "regressions_prevented")},
                          "findings": payload["findings"],
                      }]}
            if result.get("calibration_finalization"):
                record["reviewer_results"][0]["calibration_finalization"] = result["calibration_finalization"]
            records.append(canonical_json(record))
    atomic_write_text(directory / "review-results.jsonl", "\n".join(records) + ("\n" if records else ""))


def initialize(args: Any) -> dict[str, Any]:
    directory = Path(args.review_dir).resolve()
    if (directory / STATE_FILE).exists():
        _fail("REVIEW_STATE_EXISTS_USE_EXISTING_VERSION")
    repo = Path(getattr(args, "repo_path", "") or Path.cwd()).resolve()
    require_external_state(directory, repo)
    snapshot = repo_snapshot(repo)
    fingerprint = stable_repo_fingerprint(str(repo))
    project_id = getattr(args, "project_id", "") or project_id_for(fingerprint, str(repo))
    task_id = args.task_id or args.boundary_id
    limits = dict(DEFAULT_LIMITS)
    for key in limits:
        if getattr(args, key, None) is not None:
            limits[key] = getattr(args, key)
    policy_id = getattr(args, "policy_id", CURRENT_POLICY_ID)
    if "scoring" not in policy(policy_id):
        _fail("REVIEW_MATRIX_POLICY_REQUIRED")
    state_id = "RVS_" + secrets.token_hex(16)
    state = {
        "schema_version": REVIEW_STATE_SCHEMA_VERSION, "review_state_id": state_id, "review_state_ref": sha256_ref(state_id),
        "boundary_id": args.boundary_id, "task_id": task_id, "project_id": project_id, "repo_path": str(repo),
        "repo_fingerprint": fingerprint, "title": args.title, "risk_level": args.risk_level,
        "strict_readonly_required": bool(args.strict_readonly_required), "policy_id": policy_id,
        "policy_digest": policy_digest(policy_id), "status": "open", "created_at": utc_now(), "updated_at": utc_now(),
        "limits": limits, "counters": {"total_reviewers": 0, "repair_rounds": 0},
        "routing_decisions": {"pre": [], "post": []}, "isolation": default_isolation(),
        "phases": {name: {"current_round": 0, "rounds": {}} for name in ("pre", "post")},
        "delegation_budget": {"ledger_path": "", "budget_id": "", "root_envelope": "", "accounting_owner": "policy-only"},
        "initial_baseline_sha256": snapshot["sha256"], "conclusion": "", "notes": [],
    }
    if getattr(args, "project_profile", ""):
        bound = validate_binding(Path(args.project_profile), repo, args.project_id or None)
        state["project_id"] = bound.project_id
    if args.delegation_ledger:
        ledger = Path(args.delegation_ledger).resolve()
        budget = read_budget(ledger)
        if budget["schema_version"] != "3.0":
            _fail("V8_REQUIRES_V3_BUDGET_USE_LEGACY_REVIEW_FOR_V2")
        if args.task_id and args.task_id != budget["identity"]["task_id"]:
            _fail("REVIEW_TASK_ID_MISMATCH")
        if getattr(args, "project_id", "") and args.project_id != budget["identity"]["project_id"]:
            _fail("REVIEW_PROJECT_ID_MISMATCH")
        if getattr(args, "project_profile", "") and state["project_id"] != budget["identity"]["project_id"]:
            _fail("REVIEW_PROJECT_PROFILE_MISMATCH")
        state["task_id"] = budget["identity"]["task_id"]
        state["project_id"] = budget["identity"]["project_id"]
        state["delegation_budget"] = {"ledger_path": str(ledger), "budget_id": budget["identity"]["budget_id"],
                                      "root_envelope": getattr(args, "root_envelope", ""), "accounting_owner": "delegation-budget-v3"}
        _budget(state, args)
    directory.mkdir(parents=True, exist_ok=True)
    with OwnerTokenLock(directory / STATE_FILE, timeout=2):
        if (directory / STATE_FILE).exists():
            _fail("REVIEW_STATE_EXISTS_USE_EXISTING_VERSION")
        _write(directory, state)
    return state


def _require_delegate(state: Mapping[str, Any], phase: str) -> None:
    decisions = state["routing_decisions"][phase]
    if not decisions or decisions[-1]["decision"] != "DELEGATE":
        _fail("REVIEW_DELEGATE_DECISION_REQUIRED")
    if state["strict_readonly_required"] and not state["isolation"]["strict_readonly_eligible"]:
        _fail("REVIEW_SYSTEM_READONLY_NOT_VERIFIED")


def _active(row: Mapping[str, Any]) -> list[str]:
    return [name for name in row["dispatch"] if name not in row["results"]]


def _plan(state: dict[str, Any], args: Any) -> None:
    _require_delegate(state, args.phase)
    names = [item.strip() for item in args.reviewers.split(",") if item.strip()]
    if not names or len(names) != len(set(names)):
        _fail("REVIEW_PLAN_REVIEWERS_INVALID")
    phase = state["phases"][args.phase]
    previous = phase["rounds"].get(str(phase["current_round"]))
    if previous and not previous.get("merge"):
        _fail("REVIEW_PREVIOUS_ROUND_NOT_MERGED")
    packet = args.packet_sha256
    if len(packet) != 64 or any(char not in "0123456789abcdef" for char in packet):
        _fail("V8_REQUIRES_REVIEW_PACKET_HASH")
    if previous and previous["packet_sha256"] == packet:
        if not previous["merge"]["blocking_count"] and not previous["merge"]["nonblocking_count"] \
                and not previous["merge"].get("incomplete_count", 0):
            _fail("REVIEW_CLEAN_PACKET_ALREADY_PASSED")
        if not args.allow_same_packet or not args.same_packet_reason:
            _fail("REVIEW_SAME_PACKET_REASON_REQUIRED")
    number = phase["current_round"] + 1
    maximum = state["limits"]["max_preimplementation_rounds" if args.phase == "pre" else "max_post_review_rounds"]
    if number > maximum or not 1 <= args.depth <= state["limits"]["max_agent_depth"] \
            or len(names) > state["limits"]["max_parallel_reviewers"] \
            or len(names) + state["counters"]["total_reviewers"] > state["limits"]["max_total_reviewers"] \
            or (args.phase == "pre" and len(names) > state["limits"]["max_preimplementation_reviewers"]):
        _fail("REVIEW_PLAN_LIMIT")
    phase["current_round"] = number
    phase["rounds"][str(number)] = {"round": number, "phase": args.phase, "depth": args.depth,
                                  "purpose": args.purpose, "effort_tier": args.effort_tier,
                                  "default_dispatch_profile": "luna-low", "packet_sha256": packet,
                                  "planned_reviewers": names, "dispatch": {}, "results": {}, "merge": None,
                                  "created_at": utc_now()}


def _dispatch(state: dict[str, Any], args: Any) -> str:
    _require_delegate(state, args.phase)
    row = _round(state, args.phase, args.round)
    if args.reviewer not in row["planned_reviewers"] or args.reviewer in row["dispatch"]:
        _fail("REVIEWER_NOT_PLANNED_OR_ALREADY_PREPARED")
    if getattr(args, "minimum_acceptable_profile", ""):
        _fail("V8_USES_EXPLICIT_ACCEPTABLE_PROFILES_NOT_LEGACY_RANK")
    if sum(len(_active(item)) for item in _rounds(state)) >= state["limits"]["max_parallel_reviewers"]:
        _fail("REVIEW_PARALLEL_LIMIT")
    budget = _budget(state, args)
    permit_ref = ""
    agent_type = getattr(args, "agent_type", "")
    if budget:
        if not args.delegation_dispatch_key:
            _fail("REVIEW_DISPATCH_PERMIT_REQUIRED")
        permit_ref = sha256_ref(args.delegation_dispatch_key)
        permit = budget["decisions"].get(permit_ref)
        if not permit or permit["role"] != "reviewer" or permit["decision"] != "DELEGATE":
            _fail("REVIEW_DISPATCH_PERMIT_INVALID")
        assignment = permit["review_assignment"]
        expected = {"reviewer": args.reviewer, "boundary_id": state["boundary_id"], "phase": args.phase,
                    "round": args.round, "packet_sha256": row["packet_sha256"]}
        if any(assignment[key] != value for key, value in expected.items()) or (agent_type and agent_type != assignment["agent_type"]):
            _fail("REVIEW_PERMIT_ASSIGNMENT_MISMATCH")
        agent_type = assignment["agent_type"]
        selection = validate_scorecard(permit["selection_scorecard"])
        acceptable = assignment["acceptable_profiles"]
        if repo_snapshot(Path(state["repo_path"]))["sha256"] != selection["context"]["baseline_sha256"]:
            _fail("REVIEW_SCORE_BASELINE_STALE")
    else:
        if not agent_type or not getattr(args, "selection_input", ""):
            _fail("POLICY_ONLY_REVIEW_REQUIRES_EXPLICIT_SCORE_INPUT_AND_ROLE")
        request = read_request_json(Path(args.selection_input))
        if set(request) - {"reviewer_budget", "requirement_profiles", "evidence_items", "evidence_paths"}:
            _fail("SELECTION_REQUEST_FIELDS")
        context = {key: state[key] for key in ("project_id", "task_id", "repo_fingerprint")}
        context.update(packet_sha256=row["packet_sha256"], baseline_sha256=repo_snapshot(Path(state["repo_path"]))["sha256"])
        proofs = resolve_evidence(request.get("evidence_paths", {}), context, Path(state["repo_path"]))
        selection = score_review(agent_type=agent_type, context=context, reviewer_budget=request.get("reviewer_budget", "economy"),
                                 evidence_items=request.get("evidence_items", []), proofs=proofs,
                                 requirements=request.get("requirement_profiles"), policy_id=state["policy_id"])
        acceptable = [selection["approved_profile"]]
    profile = selection["approved_profile"]
    if getattr(args, "model_profile", "") and args.model_profile != profile:
        _fail("REVIEW_EXPLICIT_PROFILE_DIFFERS_FROM_SCORE")
    previous = [item for old_row, name, item in _dispatches(state)
                if name == args.reviewer and old_row["packet_sha256"] == row["packet_sha256"]]
    if previous and (not args.allow_repeat or not args.repeat_reason or digest(previous[-1]["selection_scorecard"]) == digest(selection)):
        _fail("REVIEW_REPEAT_REQUIRES_NEW_EVIDENCE_AND_REASON")
    records = list(_dispatches(state))
    premium = [entry for entry in records if is_premium(entry[2]["selection_scorecard"]["approved_profile"], state["policy_id"])]
    if is_premium(profile, state["policy_id"]) and (
            len(premium) >= state["limits"]["max_premium_reviewers"] or
            sum(name not in old_row["results"] for old_row, name, _item in premium) >= state["limits"]["max_premium_parallel"]):
        _fail("REVIEW_PREMIUM_LIMIT")
    if profile == "astra-high" and sum(item[2]["selection_scorecard"]["approved_profile"] == profile for item in records) >= state["limits"]["max_astra_high_reviewers"]:
        _fail("REVIEW_ASTRA_HIGH_LIMIT")
    if profile == "terra-high" and sum(item[2]["selection_scorecard"]["approved_profile"] == profile for item in records) >= state["limits"]["max_terra_high_reviewers"]:
        _fail("REVIEW_TERRA_HIGH_LIMIT")
    if state["counters"]["total_reviewers"] >= state["limits"]["max_total_reviewers"]:
        _fail("REVIEW_TOTAL_LIMIT")
    result_assignment = assignment_from_score(selection, acceptable, review_state_ref=state["review_state_ref"], permit_ref=permit_ref)
    native_nonce = secrets.token_hex(32) if budget else ""
    if budget:
        bind_review_attempt(Path(state["delegation_budget"]["ledger_path"]), dispatch_key=args.delegation_dispatch_key,
                            review_state_ref=state["review_state_ref"], assignment=assignment,
                            native_dispatch_nonce=native_nonce)
    row["dispatch"][args.reviewer] = {"scope": args.scope, "agent_type": agent_type,
                                     "selection_scorecard": selection, "acceptable_profiles": acceptable,
                                     "dispatch_assignment": result_assignment, "delegation_dispatch_ref": permit_ref,
                                     "status": "PREPARED", "dispatched_at": utc_now(), "repeat_reason": args.repeat_reason}
    state["counters"]["total_reviewers"] += 1
    return native_nonce


def _record_result(state: dict[str, Any], args: Any) -> None:
    row = _round(state, args.phase, args.round)
    dispatch = row["dispatch"].get(args.reviewer)
    if not dispatch or args.reviewer in row["results"] or not args.result_file:
        _fail("REVIEW_RESULT_REQUIRES_ACTIVE_DISPATCH_AND_FILE")
    payload, result_ref = read_request_document(Path(args.result_file))
    validate_result(payload, expected_assignment=dispatch["dispatch_assignment"], expected_identity={
        "reviewer": args.reviewer, "task_id": state["task_id"], "boundary_id": state["boundary_id"],
        "review_phase": args.phase, "review_round": args.round, "packet_sha256": row["packet_sha256"], "status": args.status,
    })
    budget = _budget(state, args)
    if repo_snapshot(Path(state["repo_path"]))["sha256"] != dispatch["selection_scorecard"]["context"]["baseline_sha256"]:
        _fail("REVIEW_RESULT_BASELINE_STALE")
    reservation_id = args.delegation_reservation_id
    if budget:
        reservation = budget["reservations"].get(reservation_id)
        claim = budget["review_claims"].get(dispatch["delegation_dispatch_ref"])
        if not reservation or reservation["dispatch_ref"] != dispatch["delegation_dispatch_ref"] \
                or reservation["state"] not in {"STARTED", "COMPLETED"} \
                or not claim or claim["review_state_ref"] != state["review_state_ref"]:
            _fail("REVIEW_RESULT_RESERVATION_MISMATCH")
    elif reservation_id:
        _fail("POLICY_ONLY_REVIEW_HAS_NO_RESERVATION")
    blocking = sum(item["blocking"] for item in payload["findings"])
    row["results"][args.reviewer] = {"payload": payload, "result_file": args.result_file,
                                    "result_ref": result_ref,
                                    "blocking_count": blocking, "nonblocking_count": len(payload["findings"]) - blocking,
                                    "delegation_reservation_id": reservation_id, "completed_at": utc_now()}
    dispatch["status"] = "RESULT_RECORDED"


def _reconcile(state: dict[str, Any], args: Any) -> None:
    budget = _budget(state, args)
    if budget is None:
        _fail("POLICY_ONLY_HAS_NO_HOST_LEDGER_TO_RECONCILE")
    for ref, claim in budget["review_claims"].items():
        if claim["review_state_ref"] != state["review_state_ref"]:
            continue
        permit = budget["decisions"][ref]
        assignment = permit["review_assignment"]
        if assignment["boundary_id"] != state["boundary_id"]:
            _fail("REVIEW_CLAIM_BOUNDARY_MISMATCH")
        row = _round(state, assignment["phase"], assignment["round"])
        reviewer = assignment["reviewer"]
        if reviewer not in row["planned_reviewers"] or assignment["packet_sha256"] != row["packet_sha256"]:
            _fail("REVIEW_CLAIM_PLAN_MISMATCH")
        item = row["dispatch"].get(reviewer)
        if item and item["delegation_dispatch_ref"] != ref:
            _fail("REVIEW_CLAIM_SLOT_COLLISION")
        if not item:
            score = validate_scorecard(permit["selection_scorecard"])
            item = {"scope": permit["responsibility"], "agent_type": assignment["agent_type"],
                    "selection_scorecard": score, "acceptable_profiles": assignment["acceptable_profiles"],
                    "dispatch_assignment": assignment_from_score(score, assignment["acceptable_profiles"],
                                                                  review_state_ref=state["review_state_ref"], permit_ref=ref),
                    "delegation_dispatch_ref": ref, "status": "PREPARED", "dispatched_at": utc_now(),
                    "repeat_reason": "Recovered authoritative review claim after interrupted state write"}
            row["dispatch"][reviewer] = item
            state["counters"]["total_reviewers"] += 1
        matches = [value for value in budget["reservations"].values() if value["dispatch_ref"] == ref]
        if len(matches) > 1:
            _fail("REVIEW_MULTIPLE_RESERVATIONS_FOR_ATTEMPT")
        if matches:
            item["reservation_id"] = matches[0]["reservation_id"]
            item["host_lifecycle_state"] = matches[0]["state"]
            if reviewer not in row["results"]:
                item["status"] = matches[0]["state"]
        else:
            item["host_lifecycle_state"] = "UNASSOCIATED"
    # 中文：不从终态猜 findings 或成功；English: never invent review output or a refund.
    state["last_reconciliation"] = {"budget_head_hash": budget["head_hash"], "at": utc_now()}


def run(args: Any) -> None:
    directory = Path(args.review_dir).resolve()
    if args.command == "init":
        state = initialize(args)
        print("[OK] V8 review initialized; Luna-first; " + state["delegation_budget"]["accounting_owner"])
        return
    with OwnerTokenLock(directory / STATE_FILE, timeout=2):
        state = read_json(directory / STATE_FILE, verify=True, label="Reviewer V8")
        validate_state(state)
        if args.command in {"status", "validate"}:
            _budget(state, args, live=False)
            print(json.dumps(state, ensure_ascii=False, indent=2))
            return
        if state["status"] != "open" and args.command != "sync-calibration":
            _fail("REVIEW_STATE_CLOSED")
        if args.command == "isolation":
            state["isolation"].update({key: getattr(args, key) for key in (
                "review_mode", "parent_sandbox", "declared_sandbox", "probe_result", "agent_config_confirmed", "runtime_agent_confirmed", "evidence")})
            level, eligible = derive_isolation(state["isolation"])
            state["isolation"].update(isolation_level=level, strict_readonly_eligible=eligible, verified_at=utc_now())
        elif args.command == "route":
            decisions = state["routing_decisions"][args.phase]
            if args.decision == "INLINE" and args.reason_code != "INLINE_SUFFICIENT":
                _fail("INLINE_REASON_INVALID")
            if args.decision == "DELEGATE" and args.reason_code == "INLINE_SUFFICIENT":
                _fail("DELEGATE_REASON_INVALID")
            if decisions:
                if state["phases"][args.phase]["current_round"] or decisions[-1]["decision"] != "INLINE" \
                        or args.decision != "DELEGATE" or args.supersedes != decisions[-1]["decision_id"] \
                        or not args.change_reason or not args.evidence:
                    _fail("REVIEW_ROUTE_CHANGE_REQUIRES_NEW_EVIDENCE_BEFORE_PLAN")
            data = {"decision": args.decision, "reason_code": args.reason_code, "reason": args.reason,
                    "evidence": args.evidence, "supersedes": args.supersedes, "change_reason": args.change_reason}
            decisions.append({**data, "decision_id": "ROUTE_" + digest(data)[7:]})
        elif args.command == "plan":
            _plan(state, args)
        elif args.command == "dispatch":
            native_nonce = _dispatch(state, args)
        elif args.command == "result":
            _record_result(state, args)
        elif args.command == "result-template":
            row = _round(state, args.phase, args.round)
            dispatch = row["dispatch"].get(args.reviewer)
            if not dispatch:
                _fail("REVIEW_RESULT_TEMPLATE_REQUIRES_DISPATCH")
            value = result_template(boundary_id=state["boundary_id"], task_id=state["task_id"], phase=args.phase,
                                    round_number=args.round, reviewer=args.reviewer, packet_sha256=row["packet_sha256"],
                                    assignment=dispatch["dispatch_assignment"], difficulty=args.task_difficulty)
            atomic_write_json(Path(args.output), value)
            print("[OK] V5 result template created")
            return
        elif args.command == "merge":
            row = _round(state, args.phase, args.round)
            if set(row["results"]) != set(row["planned_reviewers"]):
                _fail("REVIEW_MERGE_REQUIRES_ALL_RESULTS")
            incomplete = sum(item["payload"]["status"] == "incomplete" for item in row["results"].values())
            blocking = sum(item["blocking_count"] for item in row["results"].values())
            nonblocking = sum(item["nonblocking_count"] for item in row["results"].values())
            if blocking and not args.blocking_count and not args.repair_required:
                _fail("REVIEW_BLOCKERS_REQUIRE_REPAIR_OR_EXPLICIT_DISPOSITION")
            row["merge"] = {"blocking_count": args.blocking_count, "nonblocking_count": args.nonblocking_count,
                            "root_cause_groups": args.root_cause_groups, "summary": args.summary,
                            "repair_required": bool(args.repair_required), "raw_blocking": blocking,
                            "raw_nonblocking": nonblocking, "incomplete_count": incomplete}
        elif args.command == "repair":
            if state["counters"]["repair_rounds"] >= state["limits"]["max_repair_rounds"]:
                _fail("REVIEW_REPAIR_LIMIT")
            state["counters"]["repair_rounds"] += 1
            state.setdefault("repairs", []).append({"summary": args.summary, "validation": args.validation,
                                                     "affected_dimensions": args.affected_dimensions, "at": utc_now()})
        elif args.command == "finalize-calibration":
            result = _round(state, args.phase, args.round)["results"].get(args.reviewer)
            if not result or result.get("calibration_finalization") or not args.evidence \
                    or not args.finalized_by.startswith("parent:") or result["result_ref"] not in args.evidence:
                _fail("REVIEW_CALIBRATION_FINALIZATION_INVALID")
            if len(args.evidence) > 20 or any(not isinstance(ref, str) or len(ref) != 71 or not ref.startswith("sha256:")
                                            or any(char not in "0123456789abcdef" for char in ref[7:]) for ref in args.evidence):
                _fail("REVIEW_CALIBRATION_EVIDENCE_INVALID")
            counts = {key: getattr(args, key) for key in ("accepted", "rejected", "duplicate", "repaired", "regressions_prevented")}
            if any(type(value) is not int or value < 0 for value in counts.values()):
                _fail("REVIEW_CALIBRATION_COUNTS_INVALID")
            if counts["accepted"] + counts["rejected"] + counts["duplicate"] > len(result["payload"]["findings"]) \
                    or not counts["regressions_prevented"] <= counts["repaired"] <= counts["accepted"]:
                _fail("REVIEW_CALIBRATION_COUNTS_EXCEED_EVIDENCE")
            budget = _budget(state, args)
            if budget:
                reservation = budget["reservations"].get(result["delegation_reservation_id"])
                if not reservation or reservation["state"] != "COMPLETED" or reservation["completion_ref"] not in args.evidence:
                    _fail("REVIEW_CALIBRATION_COMPLETION_EVIDENCE_MISSING")
            result["calibration_finalization"] = {**counts, "finalized_by": args.finalized_by, "evidence": args.evidence, "note": args.note, "at": utc_now()}
        elif args.command == "sync-calibration":
            _sync_calibration(directory, state)
            print("[OK] V8 calibration projection rebuilt")
            return
        elif args.command == "reconcile":
            _reconcile(state, args)
        elif args.command == "close":
            if any(_active(row) for row in _rounds(state)):
                _fail("REVIEW_ACTIVE_ATTEMPTS_REMAIN")
            rows = list(_rounds(state))
            success = "通过" in args.conclusion or "无阻塞" in args.conclusion
            latest = [state["phases"][phase]["rounds"][str(state["phases"][phase]["current_round"])]
                      for phase in ("pre", "post") if state["phases"][phase]["current_round"]]
            if success and (not latest or any(not row.get("merge") or row["merge"]["blocking_count"]
                                             or row["merge"]["repair_required"] or row["merge"].get("incomplete_count", 0)
                                             for row in latest)):
                _fail("REVIEW_SUCCESS_REQUIRES_COMPLETE_MERGED_ROUNDS")
            if success:
                budget = _budget(state, args)
                if budget:
                    for row in rows:
                        for result in row["results"].values():
                            reservation = budget["reservations"].get(result["delegation_reservation_id"])
                            if not reservation or reservation["state"] != "COMPLETED":
                                _fail("REVIEW_SUCCESS_HOST_LIFECYCLE_NOT_COMPLETE")
            if args.conclusion.startswith("系统隔离复审") and not state["isolation"]["strict_readonly_eligible"]:
                _fail("REVIEW_SYSTEM_READONLY_NOT_VERIFIED")
            state.update(status="closed", conclusion=args.conclusion)
        else:
            _fail("V8_COMMAND_NOT_SUPPORTED")
        _write(directory, state)
    print("[OK] V8 " + args.command)
    if args.command == "dispatch":
        record = _round(state, args.phase, args.round)["dispatch"][args.reviewer]
        selection = record["selection_scorecard"]
        spec = policy(state["policy_id"])["profiles"][selection["approved_profile"]]
        print(json.dumps({"approved_profile": selection["approved_profile"], "earned_budget": selection["earned_budget"],
                          "request_parameters": {"model": spec["model"], "reasoning_effort": spec["effort"],
                                                 "agent_type": record["agent_type"], "fork_turns": "none",
                                                 "task_name": args.delegation_dispatch_key or args.reviewer},
                          "native_request_parameters": {"model": spec["model"], "reasoning_effort": spec["effort"],
                                                        "agent_type": record["agent_type"], "fork_context": False},
                          "native_message_prefix": native_review_message_prefix(native_nonce) if native_nonce else "",
                          "enforcement": state["delegation_budget"]["accounting_owner"]}, ensure_ascii=False))
