"""Controlled Task Checkpoint -> Project Memory -> Knowledge Candidate promotion."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Iterable, List, Sequence

from .common import (
    RuntimeContractError,
    append_jsonl,
    atomic_write_json,
    atomic_write_text,
    file_sha256,
    read_json,
    require_external_state,
    scan_sensitive_text,
    utc_now,
    validate_identifier,
)
from .project import MEMORY_FILE, load_profile

PROJECTION_SCHEMA = 1
KNOWLEDGE_SCHEMA = 1


def _clean_values(values: Iterable[str]) -> List[str]:
    return [item.strip() for item in values if item.strip()]


def create_projection_candidate(
    output: Path,
    profile_path: Path,
    task_id: str,
    projection_id: str,
    source_paths: Sequence[Path],
    facts: Iterable[str],
    decisions: Iterable[str],
    risks: Iterable[str],
    unknowns: Iterable[str],
    summary: str,
    allow_sensitive: bool = False,
) -> Dict[str, Any]:
    profile = load_profile(profile_path)
    repo_path = Path(profile["identity"]["repo_path"]).expanduser().resolve()
    require_external_state(output.expanduser().resolve(), repo_path)
    facts_list = _clean_values(facts)
    decisions_list = _clean_values(decisions)
    risks_list = _clean_values(risks)
    unknowns_list = _clean_values(unknowns)
    sensitive = scan_sensitive_text([summary, *facts_list, *decisions_list, *risks_list, *unknowns_list])
    if sensitive and not allow_sensitive:
        raise RuntimeContractError("Projection Candidate 疑似包含敏感信息: " + ",".join(sensitive))
    sources: List[Dict[str, str]] = []
    for raw_path in source_paths:
        path = raw_path.expanduser().resolve()
        if not path.is_file():
            raise RuntimeContractError("Projection source 不存在: " + str(path))
        sources.append({"path": str(path), "sha256": file_sha256(path)})
    record: Dict[str, Any] = {
        "schema_version": PROJECTION_SCHEMA,
        "projection_id": validate_identifier(projection_id, "projection_id"),
        "project_id": str(profile["project_id"]),
        "task_id": validate_identifier(task_id, "task_id"),
        "status": "CANDIDATE",
        "summary": summary.strip(),
        "facts": facts_list,
        "decisions": decisions_list,
        "risks": risks_list,
        "unknowns": unknowns_list,
        "sources": sources,
        "created_at": utc_now(),
        "reviewed_at": None,
        "reviewed_by": None,
        "limitations": [
            "本记录尚未成为 Project Memory",
            "未确认推断、未知项和单项目经验不得自动升级为跨项目知识",
        ],
    }
    sealed = atomic_write_json(output, record, seal=True)
    append_jsonl(profile_path.parent / "memory-projections.jsonl", {
        "projection_id": sealed["projection_id"],
        "status": sealed["status"],
        "path": str(output.expanduser().resolve()),
        "task_id": sealed["task_id"],
        "created_at": sealed["created_at"],
    })
    return sealed


def load_projection(path: Path) -> Dict[str, Any]:
    record = read_json(path, verify=True, label="Memory Projection")
    if record.get("schema_version") != PROJECTION_SCHEMA:
        raise RuntimeContractError("不支持的 Memory Projection schema_version")
    return record


def promote_projection(projection_path: Path, profile_path: Path, reviewed_by: str) -> Dict[str, Any]:
    profile = load_profile(profile_path)
    projection = load_projection(projection_path)
    if projection.get("project_id") != profile.get("project_id"):
        raise RuntimeContractError("Projection 与 Project Profile 不一致")
    if projection.get("status") not in {"CANDIDATE", "PROMOTED"}:
        raise RuntimeContractError("只有 CANDIDATE 或可恢复的 PROMOTED 记录可晋升")
    reviewer = reviewed_by.strip()
    if not reviewer:
        raise RuntimeContractError("晋升必须记录 reviewed_by")

    memory_path = profile_path.parent / MEMORY_FILE
    if not memory_path.is_file():
        raise RuntimeContractError("缺少 project-memory.md")
    text = memory_path.read_text(encoding="utf-8-sig")
    end_marker = "<!-- project-memory:end -->"
    if end_marker not in text:
        raise RuntimeContractError("project-memory.md 缺少受管结束标记")

    promoted = dict(projection)
    if promoted.get("status") == "CANDIDATE":
        promoted["status"] = "PROMOTED"
        promoted["reviewed_at"] = utc_now()
        promoted["reviewed_by"] = reviewer
    elif not promoted.get("reviewed_by"):
        promoted["reviewed_by"] = reviewer
        promoted["reviewed_at"] = promoted.get("reviewed_at") or utc_now()

    marker = f"## Projection {promoted['projection_id']}"
    if marker not in text:
        block = [
            marker,
            "",
            f"- Task ID：`{promoted['task_id']}`",
            f"- Reviewed by：{promoted['reviewed_by']}",
            f"- Reviewed at：{promoted['reviewed_at']}",
            f"- Summary：{promoted['summary'] or '未填写'}",
            "",
        ]
        for title, key in (("已确认事实", "facts"), ("决策", "decisions"), ("风险", "risks"), ("仍未知", "unknowns")):
            block.append("### " + title)
            values = promoted.get(key, [])
            block.extend(["- " + item for item in values] or ["- 无"])
            block.append("")
        insertion = "\n".join(block).rstrip() + "\n\n"
        atomic_write_text(memory_path, text.replace(end_marker, insertion + end_marker, 1))

    sealed = atomic_write_json(projection_path, promoted, seal=True)
    append_jsonl(profile_path.parent / "memory-projections.jsonl", {
        "projection_id": sealed["projection_id"],
        "status": sealed["status"],
        "path": str(projection_path.expanduser().resolve()),
        "task_id": sealed["task_id"],
        "reviewed_at": sealed["reviewed_at"],
        "reviewed_by": sealed["reviewed_by"],
    })
    return sealed


def create_knowledge_candidate(
    output: Path,
    projection_path: Path,
    profile_path: Path,
    knowledge_id: str,
    knowledge_type: str,
    applicability: Iterable[str],
    limitations: Iterable[str],
    summary: str,
) -> Dict[str, Any]:
    profile = load_profile(profile_path)
    repo_path = Path(profile["identity"]["repo_path"]).expanduser().resolve()
    require_external_state(output.expanduser().resolve(), repo_path)
    projection = load_projection(projection_path)
    if projection.get("status") != "PROMOTED":
        raise RuntimeContractError("只有已晋升的 Project Memory Projection 才能形成 Knowledge Candidate")
    if projection.get("project_id") != profile.get("project_id"):
        raise RuntimeContractError("Projection 与 Project Profile 不一致")
    record: Dict[str, Any] = {
        "schema_version": KNOWLEDGE_SCHEMA,
        "knowledge_id": validate_identifier(knowledge_id, "knowledge_id"),
        "status": "CANDIDATE",
        "primary_type": knowledge_type.strip(),
        "source_project_id": str(profile["project_id"]),
        "source_projection_id": str(projection["projection_id"]),
        "summary": summary.strip(),
        "applicability": _clean_values(applicability),
        "limitations": _clean_values(limitations),
        "evidence": projection.get("sources", []),
        "created_at": utc_now(),
        "activation": {
            "active": False,
            "requires_cross_project_validation": True,
            "requires_scope_review": True,
            "requires_sensitive_data_review": True,
        },
    }
    sealed = atomic_write_json(output, record, seal=True)
    append_jsonl(profile_path.parent / "knowledge-candidates.jsonl", {
        "knowledge_id": sealed["knowledge_id"],
        "status": sealed["status"],
        "path": str(output.expanduser().resolve()),
        "source_projection_id": sealed["source_projection_id"],
        "created_at": sealed["created_at"],
    })
    return sealed
