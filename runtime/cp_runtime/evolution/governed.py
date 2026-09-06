"""中文：新提案的完整状态机与收益事件链，旧生命周期保持不变。

English: Full state machine and benefit event chain for new proposals, preserving the legacy lifecycle.
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Mapping, Sequence

from .artifacts import ArtifactError, identifier, load, seal, verify
from .benefits import evaluate_benefit, implementation_evidence, persist_benefit, verify_benefit
from .contracts import OptimizationProposal, ProposalStatus, parse_iso_datetime, sha256_hex, utc_now_iso
from .storage import append_hash_chain, read_hash_chain, safe_child


class GovernedLifecycle:
    def __init__(self, evolution_root: Path) -> None:
        self.project_dir = evolution_root.parent
        self.path = safe_child(evolution_root, "governed-lifecycle.jsonl")

    def records(self) -> list[dict[str, Any]]:
        result = []
        seen = {}
        for entry in read_hash_chain(self.path):
            payload = verify(dict(entry["payload"]), "proposal-governed-event/1")
            expected = {"schema_version", "event_id", "proposal_id", "proposal_hash", "project_id", "repo_fingerprint",
                        "action", "actor", "data", "recorded_at", "execution_authorization", "content_hash"}
            if set(payload) != expected:
                raise ArtifactError("GOVERNED_EVENT_FIELDS_INVALID")
            event_id = sha256_hex({key: payload[key] for key in ("proposal_hash", "action", "data")})
            if payload["event_id"] != event_id:
                raise ArtifactError("GOVERNED_EVENT_ID_INVALID")
            if event_id in seen:
                if seen[event_id] != payload:
                    raise ArtifactError("GOVERNED_EVENT_CONFLICT")
                continue
            seen[event_id] = payload
            result.append(payload)
        return result

    def replay(self, proposal: OptimizationProposal, initial: ProposalStatus,
               extra: Mapping[str, Any] | None = None, *, records: Sequence[Mapping[str, Any]] | None = None) -> dict[str, Any]:
        events = [item for item in (self.records() if records is None else records) if item["proposal_id"] == proposal.proposal_id]
        if extra is not None:
            events.append(dict(extra))
        state: dict[str, Any] = {"status": initial.value, "link": None, "validation": None, "benefit": None, "final_outcome": None}
        previous_time = None
        for event in events:
            if event["project_id"] != proposal.project_id or event["proposal_hash"] != proposal.content_hash or event["repo_fingerprint"] != proposal.hypothesis["scope"]["repo_fingerprint"]:
                raise ArtifactError("GOVERNED_EVENT_IDENTITY_MISMATCH")
            current_time = parse_iso_datetime(event["recorded_at"], "recorded_at")
            if previous_time and current_time < previous_time:
                raise ArtifactError("GOVERNED_EVENT_OUT_OF_ORDER")
            previous_time = current_time
            status = state["status"]
            action, data = event["action"], event["data"]
            identifier(event["actor"])
            if status in {"CLOSED", "SUPERSEDED", "REJECTED"}:
                raise ArtifactError("GOVERNED_EVENT_AFTER_TERMINAL")
            if action == "LINK":
                if status != "ACCEPTED" or set(data) != {"task_id", "git_baseline"}:
                    raise ArtifactError("GOVERNED_LINK_TRANSITION_INVALID")
                identifier(data["task_id"])
                if not re.fullmatch(r"[0-9a-f]{40,64}", data["git_baseline"]):
                    raise ArtifactError("GOVERNED_BASELINE_INVALID")
                state.update(status="IMPLEMENTATION_LINKED", link=data)
            elif action == "VALIDATE":
                if status != "IMPLEMENTATION_LINKED" or set(data) != {"commit", "references"}:
                    raise ArtifactError("GOVERNED_VALIDATION_TRANSITION_INVALID")
                refs = implementation_evidence(self.project_dir, state["link"]["task_id"], data["commit"], [item["path"] for item in data["references"]])
                if refs != data["references"]:
                    raise ArtifactError("GOVERNED_VALIDATION_REFERENCE_CHANGED")
                state.update(status="VALIDATION_RECORDED", validation=data)
            elif action == "OBSERVE":
                if status != "VALIDATION_RECORDED" or set(data) != {"reference"}:
                    raise ArtifactError("GOVERNED_OBSERVATION_TRANSITION_INVALID")
                report = verify_benefit(self.project_dir, data["reference"], proposal, state["link"]["task_id"],
                                        state["link"]["git_baseline"], state["validation"]["commit"])
                if state["benefit"] and parse_iso_datetime(report["observed_at"], "observed_at") < parse_iso_datetime(state["benefit"]["observed_at"], "observed_at"):
                    raise ArtifactError("BENEFIT_REPORT_OUT_OF_ORDER")
                state["benefit"] = report
            elif action == "CLOSE":
                if set(data) != {"outcome", "references", "reason_code"}:
                    raise ArtifactError("GOVERNED_CLOSE_FIELDS_INVALID")
                outcome = data["outcome"]
                benefit = state["benefit"] or {}
                if outcome == "PASS":
                    if status != "VALIDATION_RECORDED" or benefit.get("benefit_status") != "SUPPORTED":
                        raise ArtifactError("BENEFIT_PASS_UNSUPPORTED")
                elif outcome == "FAILED":
                    if status != "VALIDATION_RECORDED" or benefit.get("benefit_status") not in {"REGRESSED", "NOT_SUPPORTED"}:
                        raise ArtifactError("BENEFIT_FAILURE_UNPROVEN")
                elif outcome == "CANCELLED":
                    if status not in {"ACCEPTED", "IMPLEMENTATION_LINKED", "VALIDATION_RECORDED"} or data["reason_code"] != "EXPLICIT_PROPOSAL_CANCELLATION":
                        raise ArtifactError("GOVERNED_CANCELLATION_INVALID")
                elif outcome == "ROLLED_BACK":
                    if status not in {"IMPLEMENTATION_LINKED", "VALIDATION_RECORDED"}:
                        raise ArtifactError("GOVERNED_ROLLBACK_INVALID")
                    refs = implementation_evidence(self.project_dir, state["link"]["task_id"], state["link"]["git_baseline"], [item["path"] for item in data["references"]])
                    if refs != data["references"]:
                        raise ArtifactError("GOVERNED_ROLLBACK_REFERENCE_CHANGED")
                    if any(load(self.project_dir, ref["path"], ref["content_hash"]).get("workspace_clean") is not True for ref in refs):
                        raise ArtifactError("GOVERNED_ROLLBACK_WORKTREE_DIRTY")
                else:
                    raise ArtifactError("GOVERNED_CLOSE_OUTCOME_INVALID")
                state.update(status="CLOSED", final_outcome=outcome)
            elif action == "SUPERSEDE":
                if status != "ACCEPTED" or set(data) != {"superseded_by"} or data["superseded_by"] == proposal.proposal_id:
                    raise ArtifactError("GOVERNED_SUPERSEDE_INVALID")
                state.update(status="SUPERSEDED", final_outcome="SUPERSEDED")
            else:
                raise ArtifactError("GOVERNED_ACTION_INVALID")
        return state

    def append(self, proposal: OptimizationProposal, initial: ProposalStatus, actor: str,
               action: str, data: Mapping[str, Any]) -> dict[str, Any]:
        event_id = sha256_hex({"proposal_hash": proposal.content_hash, "action": action, "data": data})
        for event in self.records():
            if event["event_id"] == event_id:
                return self.replay(proposal, initial)
        event = seal({"schema_version": "proposal-governed-event/1", "event_id": event_id,
                      "proposal_id": proposal.proposal_id, "proposal_hash": proposal.content_hash,
                      "project_id": proposal.project_id, "repo_fingerprint": proposal.hypothesis["scope"]["repo_fingerprint"],
                      "action": action, "actor": actor, "data": dict(data), "recorded_at": utc_now_iso(),
                      "execution_authorization": "NONE"})
        state = self.replay(proposal, initial, extra=event)
        append_hash_chain(self.path, event)
        return state

    def observe(self, proposal: OptimizationProposal, initial: ProposalStatus, actor: str,
                before_ref: Mapping[str, str], after_ref: Mapping[str, str]) -> dict[str, Any]:
        state = self.replay(proposal, initial)
        if state["status"] != "VALIDATION_RECORDED":
            raise ArtifactError("GOVERNED_OBSERVATION_TRANSITION_INVALID")
        report = evaluate_benefit(self.project_dir, proposal, implementation_task_id=state["link"]["task_id"],
                                  git_baseline=state["link"]["git_baseline"], implementation_commit=state["validation"]["commit"],
                                  validation_refs=state["validation"]["references"], before_ref=before_ref, after_ref=after_ref)
        reference = persist_benefit(self.project_dir, report)
        return self.append(proposal, initial, actor, "OBSERVE", {"reference": reference})
