"""V6 Optimization Proposal 实施/验证生命周期事件。"""
from __future__ import annotations

import hashlib
import json
import re
import secrets
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Mapping, Optional, Sequence, Tuple

class LifecycleError(ValueError):
    pass

class LifecycleEventType(str, Enum):
    IMPLEMENTATION_LINKED = "IMPLEMENTATION_LINKED"
    VALIDATION_RECORDED = "VALIDATION_RECORDED"
    CLOSED = "CLOSED"
    SUPERSEDED = "SUPERSEDED"

FINAL_OUTCOMES = {"PASS", "FAILED", "ROLLED_BACK", "CANCELLED", "SUPERSEDED"}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def canonical(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def digest(value: Any) -> str:
    return hashlib.sha256(canonical(value).encode("utf-8")).hexdigest()


def _text(value: Any, name: str, min_len: int = 1, max_len: int = 2048) -> str:
    text = str(value or "").strip()
    if not min_len <= len(text) <= max_len:
        raise LifecycleError("%s 长度非法" % name)
    return text

@dataclass(frozen=True)
class ProposalLifecycleEvent:
    schema_version: str
    lifecycle_id: str
    proposal_id: str
    event_type: LifecycleEventType
    actor: str
    created_at: str
    implementation_task_id: str
    git_baseline: str
    implementation_commit: str
    evidence_refs: Tuple[str, ...]
    final_outcome: str
    superseded_by: str
    content_hash: str

    @classmethod
    def create(
        cls,
        proposal_id: str,
        event_type: LifecycleEventType,
        actor: str,
        implementation_task_id: str = "",
        git_baseline: str = "",
        implementation_commit: str = "",
        evidence_refs: Sequence[str] = (),
        final_outcome: str = "",
        superseded_by: str = "",
    ) -> "ProposalLifecycleEvent":
        payload = {
            "schema_version": "1.0",
            "lifecycle_id": "LCE_" + secrets.token_hex(16),
            "proposal_id": _text(proposal_id, "proposal_id", 3, 128),
            "event_type": event_type.value,
            "actor": _text(actor, "actor", 2, 256),
            "created_at": utc_now(),
            "implementation_task_id": str(implementation_task_id or "").strip()[:256],
            "git_baseline": str(git_baseline or "").strip()[:256],
            "implementation_commit": str(implementation_commit or "").strip()[:256],
            "evidence_refs": tuple(str(x).strip()[:512] for x in evidence_refs if str(x).strip()),
            "final_outcome": str(final_outcome or "").strip().upper(),
            "superseded_by": str(superseded_by or "").strip()[:128],
        }
        if event_type is LifecycleEventType.IMPLEMENTATION_LINKED:
            if not payload["implementation_task_id"] or not payload["git_baseline"]:
                raise LifecycleError("绑定实施必须同时提供 implementation_task_id 与 git_baseline")
        elif event_type is LifecycleEventType.VALIDATION_RECORDED:
            if not payload["implementation_commit"] or not payload["evidence_refs"]:
                raise LifecycleError("记录验证必须提供 implementation_commit 与至少一条 evidence_ref")
        elif event_type is LifecycleEventType.CLOSED:
            if payload["final_outcome"] not in FINAL_OUTCOMES:
                raise LifecycleError("关闭提案必须提供合法 final_outcome")
        elif event_type is LifecycleEventType.SUPERSEDED:
            if not payload["superseded_by"]:
                raise LifecycleError("SUPERSEDED 必须提供 superseded_by")
            payload["final_outcome"] = "SUPERSEDED"
        payload["content_hash"] = digest(payload)
        return cls(
            schema_version=payload["schema_version"], lifecycle_id=payload["lifecycle_id"],
            proposal_id=payload["proposal_id"], event_type=event_type, actor=payload["actor"],
            created_at=payload["created_at"], implementation_task_id=payload["implementation_task_id"],
            git_baseline=payload["git_baseline"], implementation_commit=payload["implementation_commit"],
            evidence_refs=tuple(payload["evidence_refs"]), final_outcome=payload["final_outcome"],
            superseded_by=payload["superseded_by"], content_hash=payload["content_hash"])

    @classmethod
    def from_mapping(cls, raw: Mapping[str, Any]) -> "ProposalLifecycleEvent":
        obj = cls(
            schema_version=str(raw["schema_version"]), lifecycle_id=str(raw["lifecycle_id"]),
            proposal_id=str(raw["proposal_id"]), event_type=LifecycleEventType(str(raw["event_type"])),
            actor=str(raw["actor"]), created_at=str(raw["created_at"]),
            implementation_task_id=str(raw.get("implementation_task_id") or ""),
            git_baseline=str(raw.get("git_baseline") or ""), implementation_commit=str(raw.get("implementation_commit") or ""),
            evidence_refs=tuple(str(x) for x in raw.get("evidence_refs", [])), final_outcome=str(raw.get("final_outcome") or ""),
            superseded_by=str(raw.get("superseded_by") or ""), content_hash=str(raw["content_hash"]))
        obj.verify_integrity(); return obj

    def verify_integrity(self) -> None:
        raw = {
            "schema_version": self.schema_version, "lifecycle_id": self.lifecycle_id, "proposal_id": self.proposal_id,
            "event_type": self.event_type.value, "actor": self.actor, "created_at": self.created_at,
            "implementation_task_id": self.implementation_task_id, "git_baseline": self.git_baseline,
            "implementation_commit": self.implementation_commit, "evidence_refs": self.evidence_refs,
            "final_outcome": self.final_outcome, "superseded_by": self.superseded_by,
        }
        if digest(raw) != self.content_hash:
            raise LifecycleError("Proposal Lifecycle content_hash 不一致")
