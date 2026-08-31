"""自观察 → 分析 → 提案的受控编排服务。"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

from .analysis import assess_snapshot
from .contracts import (
    EvolutionPolicy,
    ExecutionAuthorization,
    OptimizationProposal,
    SelfObservationSnapshot,
    ValueComplexityAssessment,
    to_primitive,
)
from .observation import observe_project
from .proposal import generate_proposals
from .registry import ProposalRegistry, ProposalView
from .storage import atomic_write_json, read_json, resolve_project_dir, safe_child


class EvolutionServiceError(RuntimeError):
    pass


def load_policy(path: Optional[Path] = None) -> EvolutionPolicy:
    if path is None:
        return EvolutionPolicy()
    raw = read_json(Path(path))
    if not isinstance(raw, Mapping):
        raise EvolutionServiceError("策略文件必须是 JSON 对象")
    return EvolutionPolicy.from_mapping(raw)


class ControlledEvolutionService:
    """仅产生分析产物和人工评审提案，不提供自动执行接口。"""

    def __init__(
        self,
        context_root: Path,
        project_id: str,
        policy: Optional[EvolutionPolicy] = None,
        create_project_dir: bool = False,
    ) -> None:
        self.context_root = Path(context_root).expanduser()
        self.project_id = project_id
        self.policy = policy or EvolutionPolicy()
        self.project_dir = resolve_project_dir(self.context_root, project_id, create=create_project_dir)
        if not self.project_dir.exists():
            raise EvolutionServiceError("项目上下文目录不存在，请先执行项目 Onboarding: %s" % self.project_dir)
        self.evolution_root = safe_child(self.project_dir, "evolution")

    def observe(
        self,
        explicit_sources: Optional[Sequence[str]] = None,
        observed_at: Optional[str] = None,
    ) -> SelfObservationSnapshot:
        return observe_project(
            project_id=self.project_id,
            project_dir=self.project_dir,
            policy=self.policy,
            explicit_sources=explicit_sources,
            observed_at=observed_at,
        )

    def analyze(self, snapshot: SelfObservationSnapshot) -> List[ValueComplexityAssessment]:
        return assess_snapshot(snapshot, self.policy)

    def propose(
        self,
        snapshot: SelfObservationSnapshot,
        assessments: Sequence[ValueComplexityAssessment],
    ) -> List[OptimizationProposal]:
        return generate_proposals(self.project_id, snapshot, assessments)

    def run(
        self,
        explicit_sources: Optional[Sequence[str]] = None,
        dry_run: bool = False,
        observed_at: Optional[str] = None,
    ) -> Mapping[str, Any]:
        snapshot = self.observe(explicit_sources=explicit_sources, observed_at=observed_at)
        assessments = self.analyze(snapshot)
        proposals = self.propose(snapshot, assessments)

        registered: List[Mapping[str, Any]] = []
        if not dry_run:
            snapshots_dir = safe_child(self.evolution_root, "snapshots", create_parent=True)
            assessments_dir = safe_child(self.evolution_root, "assessments", create_parent=True)
            snapshots_dir.mkdir(parents=True, exist_ok=True)
            assessments_dir.mkdir(parents=True, exist_ok=True)
            atomic_write_json(safe_child(snapshots_dir, "%s.json" % snapshot.snapshot_id, create_parent=True), snapshot)
            atomic_write_json(
                safe_child(assessments_dir, "%s.json" % snapshot.snapshot_id, create_parent=True),
                {
                    "schema_version": "1.0",
                    "project_id": self.project_id,
                    "snapshot_id": snapshot.snapshot_id,
                    "policy_version": self.policy.policy_version,
                    "assessments": [to_primitive(item) for item in assessments],
                    "execution_authorization": ExecutionAuthorization.NONE.value,
                },
            )
            registry = ProposalRegistry(self.evolution_root, self.project_id)
            for proposal in proposals:
                view, created = registry.register(proposal)
                registered.append({
                    "proposal_id": view.proposal.proposal_id,
                    "fingerprint": view.proposal.fingerprint,
                    "status": view.current_status.value,
                    "created": created,
                })
            registry_summary = registry.validate()
        else:
            registry_summary = {
                "project_id": self.project_id,
                "dry_run": True,
                "proposal_count": len(proposals),
                "execution_authorization": ExecutionAuthorization.NONE.value,
            }
            registered = [
                {
                    "proposal_id": proposal.proposal_id,
                    "fingerprint": proposal.fingerprint,
                    "status": proposal.status.value,
                    "created": False,
                }
                for proposal in proposals
            ]

        return {
            "schema_version": "1.0",
            "mode": "DRY_RUN" if dry_run else "PERSISTED",
            "project_id": self.project_id,
            "snapshot": to_primitive(snapshot),
            "assessment_count": len(assessments),
            "assessments": [to_primitive(item) for item in assessments],
            "proposal_count": len(proposals),
            "proposals": [to_primitive(item) for item in proposals],
            "registered": registered,
            "registry": registry_summary,
            "execution_authorization": ExecutionAuthorization.NONE.value,
            "automatic_execution": False,
        }

    def validate_registry(self) -> Mapping[str, Any]:
        registry = ProposalRegistry(self.evolution_root, self.project_id)
        return registry.validate()
