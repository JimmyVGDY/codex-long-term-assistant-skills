"""中文：收益验证使用的不可变分窗观察证据。

English: Immutable observation-window evidence used for benefit validation.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

from .artifacts import ArtifactError, load, persist, project_identity, seal
from .contracts import ConfidenceLevel, EvidenceReference, PatternSignal, SelfObservationSnapshot, SignalType, to_primitive


def snapshot_from_mapping(raw: Mapping[str, Any]) -> SelfObservationSnapshot:
    values = dict(raw)
    values["signals"] = tuple(PatternSignal(
        signal_id=item["signal_id"], signal_type=SignalType(item["signal_type"]), target=item["target"],
        occurrence_count=item["occurrence_count"], independent_task_count=item["independent_task_count"],
        rate=item["rate"], confidence=ConfidenceLevel(item["confidence"]), summary=item["summary"],
        evidence=tuple(EvidenceReference(**ref) for ref in item["evidence"]), metrics=item["metrics"],
    ) for item in raw["signals"])
    snapshot = SelfObservationSnapshot(**values)
    snapshot.verify_integrity()
    return snapshot


def persist_snapshot(project_dir: Path, snapshot: SelfObservationSnapshot) -> dict[str, str]:
    snapshot.verify_integrity()
    identity = project_identity(project_dir, verify_live=False)
    if snapshot.project_id != identity["project_id"] or snapshot.metrics.get("repo_fingerprint") != identity["repo_fingerprint"]:
        raise ArtifactError("SNAPSHOT_IDENTITY_MISMATCH")
    value = seal({"schema_version": "observation-evidence/1", "snapshot": to_primitive(snapshot),
                  "execution_authorization": "NONE"})
    return persist(project_dir, "evolution/observation-evidence/" + snapshot.snapshot_id + ".json", value)


def load_snapshot(project_dir: Path, reference: Mapping[str, str]) -> SelfObservationSnapshot:
    value = load(project_dir, reference["path"], reference["content_hash"], "observation-evidence/1")
    snapshot = snapshot_from_mapping(value["snapshot"])
    identity = project_identity(project_dir, verify_live=False)
    if snapshot.project_id != identity["project_id"] or snapshot.metrics.get("repo_fingerprint") != identity["repo_fingerprint"]:
        raise ArtifactError("SNAPSHOT_IDENTITY_MISMATCH")
    return snapshot
