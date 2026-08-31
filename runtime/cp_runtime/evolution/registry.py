"""中文：追加式优化提案注册表与人工决策记录。

English: Append-only optimization-proposal registry and human-decision records.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple

from .contracts import (
    ConfidenceLevel,
    ContractError,
    DecisionType,
    EvidenceReference,
    ExecutionAuthorization,
    OptimizationProposal,
    ProposalAction,
    ProposalDecision,
    ProposalStatus,
    RiskLevel,
    to_primitive,
    validate_project_id,
)
from .storage import FileLock, StorageError, append_hash_chain, read_hash_chain, safe_child
from .redaction import redact_text
from .lifecycle import LifecycleEventType, ProposalLifecycleEvent


class RegistryError(RuntimeError):
    """中文：提案注册、查询、决策或完整性异常。

    English: Proposal registration, query, decision, or integrity failure.
    """


@dataclass(frozen=True)
class ProposalView:
    proposal: OptimizationProposal
    current_status: ProposalStatus
    latest_decision: Optional[ProposalDecision]


def _evidence(raw: Mapping[str, Any]) -> EvidenceReference:
    return EvidenceReference(
        source_kind=str(raw["source_kind"]),
        source_path=str(raw["source_path"]),
        line_number=int(raw["line_number"]),
        record_id=str(raw["record_id"]),
        task_id=None if raw.get("task_id") is None else str(raw.get("task_id")),
        record_hash=None if raw.get("record_hash") is None else str(raw.get("record_hash")),
    )


def _proposal(raw: Mapping[str, Any]) -> OptimizationProposal:
    return OptimizationProposal(
        schema_version=str(raw["schema_version"]),
        proposal_id=str(raw["proposal_id"]),
        project_id=str(raw["project_id"]),
        assessment_id=str(raw["assessment_id"]),
        fingerprint=str(raw["fingerprint"]),
        created_at=str(raw["created_at"]),
        action_type=ProposalAction(str(raw["action_type"])),
        target_resource=str(raw["target_resource"]),
        problem_statement=str(raw["problem_statement"]),
        recommendation=str(raw["recommendation"]),
        expected_value=str(raw["expected_value"]),
        risk_level=RiskLevel(str(raw["risk_level"])),
        complexity_score=int(raw["complexity_score"]),
        confidence=ConfidenceLevel(str(raw["confidence"])),
        evidence=tuple(_evidence(item) for item in raw.get("evidence", [])),
        rollback_plan=tuple(str(item) for item in raw.get("rollback_plan", [])),
        validation_plan=tuple(str(item) for item in raw.get("validation_plan", [])),
        constraints=tuple(str(item) for item in raw.get("constraints", [])),
        execution_authorization=ExecutionAuthorization(str(raw["execution_authorization"])),
        status=ProposalStatus(str(raw["status"])),
        content_hash=str(raw["content_hash"]),
    )


def _decision(raw: Mapping[str, Any]) -> ProposalDecision:
    return ProposalDecision(
        schema_version=str(raw["schema_version"]),
        decision_id=str(raw["decision_id"]),
        proposal_id=str(raw["proposal_id"]),
        decision=DecisionType(str(raw["decision"])),
        actor=str(raw["actor"]),
        rationale=str(raw["rationale"]),
        decided_at=str(raw["decided_at"]),
        content_hash=str(raw["content_hash"]),
    )


def _decision_status(decision: DecisionType) -> ProposalStatus:
    if decision is DecisionType.ACCEPT:
        return ProposalStatus.ACCEPTED
    if decision is DecisionType.REJECT:
        return ProposalStatus.REJECTED
    return ProposalStatus.DEFERRED


class ProposalRegistry:
    """中文：每个项目一个追加式注册表；ACCEPT 只记录人工认可，不产生执行授权或修改工具。

    English: One append-only registry per project. ACCEPT records human approval only and creates neither execution authority nor mutation tooling.
    """

    def __init__(self, evolution_root: Path, project_id: str) -> None:
        self.project_id = validate_project_id(project_id)
        self.root = Path(evolution_root).resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        self.proposals_path = safe_child(self.root, "proposals.jsonl", create_parent=True)
        self.decisions_path = safe_child(self.root, "decisions.jsonl", create_parent=True)
        self.lifecycle_path = safe_child(self.root, "lifecycle.jsonl", create_parent=True)
        self.guard_path = safe_child(self.root, "registry.guard", create_parent=True)

    def _proposal_records(self) -> List[OptimizationProposal]:
        records = read_hash_chain(self.proposals_path)
        proposals: List[OptimizationProposal] = []
        for record in records:
            payload = record.get("payload")
            if not isinstance(payload, Mapping):
                raise RegistryError("提案哈希链 payload 非法")
            proposal = _proposal(payload)
            proposal.verify_integrity()
            if proposal.project_id != self.project_id:
                raise RegistryError("提案 project_id 与注册表不一致")
            proposals.append(proposal)
        return proposals

    def _decision_records(self) -> List[ProposalDecision]:
        records = read_hash_chain(self.decisions_path)
        decisions: List[ProposalDecision] = []
        for record in records:
            payload = record.get("payload")
            if not isinstance(payload, Mapping):
                raise RegistryError("决策哈希链 payload 非法")
            decision = _decision(payload)
            decision.verify_integrity()
            decisions.append(decision)
        return decisions

    def _lifecycle_records(self) -> List[ProposalLifecycleEvent]:
        records = read_hash_chain(self.lifecycle_path)
        events: List[ProposalLifecycleEvent] = []
        for record in records:
            payload = record.get("payload")
            if not isinstance(payload, Mapping):
                raise RegistryError("Lifecycle 哈希链 payload 非法")
            events.append(ProposalLifecycleEvent.from_mapping(payload))
        return events

    def list(self) -> List[ProposalView]:
        proposals = self._proposal_records()
        decisions = self._decision_records()
        lifecycle = self._lifecycle_records()
        decisions_by_proposal: Dict[str, List[ProposalDecision]] = {}
        for decision in decisions:
            decisions_by_proposal.setdefault(decision.proposal_id, []).append(decision)
        known_ids = {proposal.proposal_id for proposal in proposals}
        unknown = sorted({decision.proposal_id for decision in decisions} - known_ids)
        unknown_lifecycle = sorted({event.proposal_id for event in lifecycle} - known_ids)
        if unknown:
            raise RegistryError("存在引用未知提案的决策: %s" % ", ".join(unknown))
        if unknown_lifecycle:
            raise RegistryError("存在引用未知提案的生命周期事件: %s" % ", ".join(unknown_lifecycle))
        lifecycle_by_proposal: Dict[str, List[ProposalLifecycleEvent]] = {}
        for event in lifecycle:
            lifecycle_by_proposal.setdefault(event.proposal_id, []).append(event)
        views: List[ProposalView] = []
        for proposal in proposals:
            proposal_decisions = decisions_by_proposal.get(proposal.proposal_id, [])
            latest = proposal_decisions[-1] if proposal_decisions else None
            status = _decision_status(latest.decision) if latest else ProposalStatus.PENDING_REVIEW
            lifecycle_events = lifecycle_by_proposal.get(proposal.proposal_id, [])
            if lifecycle_events:
                if status is not ProposalStatus.ACCEPTED:
                    raise RegistryError("只有 ACCEPTED 提案才能进入实施生命周期")
                latest_lifecycle = lifecycle_events[-1]
                status_map = {
                    LifecycleEventType.IMPLEMENTATION_LINKED: ProposalStatus.IMPLEMENTATION_LINKED,
                    LifecycleEventType.VALIDATION_RECORDED: ProposalStatus.VALIDATION_RECORDED,
                    LifecycleEventType.CLOSED: ProposalStatus.CLOSED,
                    LifecycleEventType.SUPERSEDED: ProposalStatus.SUPERSEDED,
                }
                status = status_map[latest_lifecycle.event_type]
            views.append(ProposalView(proposal=proposal, current_status=status, latest_decision=latest))
        return views

    def get(self, proposal_id: str) -> ProposalView:
        for view in self.list():
            if view.proposal.proposal_id == proposal_id:
                return view
        raise RegistryError("提案不存在: %s" % proposal_id)

    def register(self, proposal: OptimizationProposal) -> Tuple[ProposalView, bool]:
        proposal.verify_integrity()
        if proposal.project_id != self.project_id:
            raise RegistryError("不能向其他项目注册表写入提案")
        if proposal.execution_authorization is not ExecutionAuthorization.NONE:
            raise RegistryError("提案包含非法执行授权")
        with FileLock(self.guard_path):
            for existing in self.list():
                if existing.proposal.fingerprint == proposal.fingerprint:
            # 中文：相同证据摘要不触发机械重生；只有证据或策略变化形成新 fingerprint 时才能注册新提案。
            # English: An identical evidence digest cannot trigger mechanical rebirth; a new proposal requires evidence or policy change that produces a new fingerprint.
                    return existing, False
            append_hash_chain(self.proposals_path, proposal)
        return self.get(proposal.proposal_id), True

    def decide(
        self,
        proposal_id: str,
        decision: DecisionType,
        actor: str,
        rationale: str,
    ) -> ProposalView:
        with FileLock(self.guard_path):
            current = self.get(proposal_id)
            if current.current_status in {ProposalStatus.ACCEPTED, ProposalStatus.REJECTED, ProposalStatus.IMPLEMENTATION_LINKED, ProposalStatus.VALIDATION_RECORDED, ProposalStatus.CLOSED, ProposalStatus.SUPERSEDED}:
                raise RegistryError("提案已经进入不可覆盖状态，不能覆盖历史决定")
            event = ProposalDecision.create(
                proposal_id=proposal_id,
                decision=decision,
                actor=redact_text(actor),
                rationale=redact_text(rationale),
            )
            append_hash_chain(self.decisions_path, event)
        return self.get(proposal_id)

    def link_implementation(self, proposal_id: str, actor: str, implementation_task_id: str, git_baseline: str) -> ProposalView:
        with FileLock(self.guard_path):
            current = self.get(proposal_id)
            if current.current_status is not ProposalStatus.ACCEPTED:
                raise RegistryError("只有 ACCEPTED 提案才能绑定实施任务")
            event = ProposalLifecycleEvent.create(proposal_id, LifecycleEventType.IMPLEMENTATION_LINKED, actor, implementation_task_id=implementation_task_id, git_baseline=git_baseline)
            append_hash_chain(self.lifecycle_path, event)
        return self.get(proposal_id)

    def record_validation(self, proposal_id: str, actor: str, implementation_commit: str, evidence_refs: Sequence[str]) -> ProposalView:
        with FileLock(self.guard_path):
            current = self.get(proposal_id)
            if current.current_status is not ProposalStatus.IMPLEMENTATION_LINKED:
                raise RegistryError("必须先绑定实施 Task/Git Baseline，才能记录验证")
            event = ProposalLifecycleEvent.create(proposal_id, LifecycleEventType.VALIDATION_RECORDED, actor, implementation_commit=implementation_commit, evidence_refs=evidence_refs)
            append_hash_chain(self.lifecycle_path, event)
        return self.get(proposal_id)

    def close(self, proposal_id: str, actor: str, final_outcome: str) -> ProposalView:
        with FileLock(self.guard_path):
            current = self.get(proposal_id)
            if current.current_status is not ProposalStatus.VALIDATION_RECORDED:
                raise RegistryError("只有已记录验证证据的提案才能关闭")
            event = ProposalLifecycleEvent.create(proposal_id, LifecycleEventType.CLOSED, actor, final_outcome=final_outcome)
            append_hash_chain(self.lifecycle_path, event)
        return self.get(proposal_id)

    def supersede(self, proposal_id: str, actor: str, superseded_by: str) -> ProposalView:
        with FileLock(self.guard_path):
            current = self.get(proposal_id)
            if current.current_status is not ProposalStatus.ACCEPTED:
                raise RegistryError("仅允许在尚未实施的 ACCEPTED 状态标记 SUPERSEDED")
            event = ProposalLifecycleEvent.create(proposal_id, LifecycleEventType.SUPERSEDED, actor, superseded_by=superseded_by)
            append_hash_chain(self.lifecycle_path, event)
        return self.get(proposal_id)

    def validate(self) -> Mapping[str, Any]:
        views = self.list()
        active_fingerprints: Dict[str, str] = {}
        for view in views:
            fingerprint = view.proposal.fingerprint
            if view.current_status in {
                ProposalStatus.PENDING_REVIEW,
                ProposalStatus.ACCEPTED,
                ProposalStatus.DEFERRED,
                ProposalStatus.IMPLEMENTATION_LINKED,
                ProposalStatus.VALIDATION_RECORDED,
            }:
                previous = active_fingerprints.get(fingerprint)
                if previous:
                    raise RegistryError("存在重复活跃提案 fingerprint: %s" % fingerprint)
                active_fingerprints[fingerprint] = view.proposal.proposal_id
        return {
            "project_id": self.project_id,
            "proposal_count": len(views),
            "pending_count": sum(1 for view in views if view.current_status is ProposalStatus.PENDING_REVIEW),
            "accepted_count": sum(1 for view in views if view.current_status is ProposalStatus.ACCEPTED),
            "rejected_count": sum(1 for view in views if view.current_status is ProposalStatus.REJECTED),
            "deferred_count": sum(1 for view in views if view.current_status is ProposalStatus.DEFERRED),
            "implementation_linked_count": sum(1 for view in views if view.current_status is ProposalStatus.IMPLEMENTATION_LINKED),
            "validation_recorded_count": sum(1 for view in views if view.current_status is ProposalStatus.VALIDATION_RECORDED),
            "closed_count": sum(1 for view in views if view.current_status is ProposalStatus.CLOSED),
            "superseded_count": sum(1 for view in views if view.current_status is ProposalStatus.SUPERSEDED),
            "execution_authorization": ExecutionAuthorization.NONE.value,
            "integrity": "PASS",
        }
