from __future__ import annotations
import hashlib,json
from pathlib import Path
from datetime import datetime,timezone
from typing import Any,Dict,List,Tuple,Optional,Mapping
from dataclasses import dataclass
from enum import Enum

# 本案例明确的测试边界提供器；不作为真实Git读取实现。
def repo_snapshot(_repo_path):
    return {'sha256': 'current'}

class RuntimeContractError(RuntimeError):
    """中文：失败关闭的 Runtime 契约异常。

    English: A fail-closed runtime contract violation.
    """

def canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))

def canonical_sha256(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()

def record_without_integrity(value: Dict[str, Any]) -> Dict[str, Any]:
    copied = dict(value)
    copied.pop("integrity", None)
    return copied

def verify_record(value: Dict[str, Any], label: str = "记录") -> None:
    integrity = value.get("integrity")
    if not isinstance(integrity, dict) or integrity.get("algorithm") != "sha256-canonical-json":
        raise RuntimeContractError(label + "缺少受支持的完整性字段")
    expected = integrity.get("sha256")
    actual = canonical_sha256(record_without_integrity(value))
    if expected != actual:
        raise RuntimeContractError(label + "完整性校验失败")

def read_json(path: Path, verify: bool = False, label: str = "记录") -> Dict[str, Any]:
    if not path.is_file():
        raise RuntimeContractError(f"缺少文件: {path}")
    try:
        value = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RuntimeContractError(f"读取 JSON 失败 {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise RuntimeContractError(f"JSON 顶层必须是对象: {path}")
    if verify:
        verify_record(value, label)
    return value

class EvidenceFreshness(str, Enum):
    CURRENT = "CURRENT"
    STALE = "STALE"
    NOT_CAPTURED = "NOT_CAPTURED"

@dataclass(frozen=True)
class EvidenceCheckResult:
    valid: bool
    freshness: EvidenceFreshness
    reasons: Tuple[str, ...]
    evidence_id: str

SCHEMA = 1

def load_evidence(path: Path) -> Dict[str, Any]:
    value = read_json(path, verify=True, label="Evidence")
    if value.get("schema_version") != SCHEMA:
        raise RuntimeContractError("不支持的 Evidence schema_version")
    return value

def check_evidence(
    evidence_path: Path,
    repo_path: Optional[Path] = None,
    project_id: Optional[str] = None,
    task_id: Optional[str] = None,
) -> EvidenceCheckResult:
    record = load_evidence(evidence_path)
    reasons: List[str] = []
    freshness = EvidenceFreshness.NOT_CAPTURED
    if project_id and record.get("project_id") != project_id:
        reasons.append("project-id-mismatch")
    if task_id and record.get("task_id") != task_id:
        reasons.append("task-id-mismatch")
    baseline = record.get("baseline")
    if repo_path is not None and isinstance(baseline, dict) and baseline.get("sha256"):
        current = repo_snapshot(repo_path)
        freshness = EvidenceFreshness.CURRENT if current["sha256"] == baseline["sha256"] else EvidenceFreshness.STALE
        if freshness is EvidenceFreshness.STALE:
            reasons.append("repository-baseline-changed")
    else:
        reasons.append("repository-freshness-not-checked")
    if record.get("status") != "valid":
        reasons.append("evidence-status-not-valid")
    return EvidenceCheckResult(
        valid=not reasons and freshness is EvidenceFreshness.CURRENT,
        freshness=freshness,
        reasons=tuple(reasons),
        evidence_id=str(record.get("evidence_id", "")),
    )
