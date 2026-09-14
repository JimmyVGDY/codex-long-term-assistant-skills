"""中文：只读、有界的项目恢复摘要，schema 为 ``resume-view/1``。

English: Read-only bounded project recovery view using schema ``resume-view/1``.
"""
from __future__ import annotations

import json
import os
import re
import stat
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple

from .common import RuntimeContractError, verify_record
from .project import load_profile, load_state, validate_binding
from .resume_snapshot import bounded_repo_snapshot

MAX_CHECKPOINTS = 3
MAX_EVIDENCE = 20
MAX_TEXT_BYTES = 2 * 1024 * 1024


def _safe_path(path: Path, label: str) -> Path:
    original = path.expanduser()
    current = original.absolute()
    while True:
        try:
            info = current.lstat()
            is_reparse = os.name == "nt" and bool(
                getattr(info, "st_file_attributes", 0) & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
            )
            if current.is_symlink() or is_reparse:
                raise RuntimeContractError(label + "不能包含符号链接或 Reparse Point 祖先")
        except FileNotFoundError:
            pass
        parent = current.parent
        if parent == current:
            break
        current = parent
    return original.resolve()


def _read_text(path: Path, label: str) -> str:
    path = _safe_path(path, label)
    if not path.is_file():
        raise RuntimeContractError("缺少文件: " + str(path))
    if path.stat().st_size > MAX_TEXT_BYTES:
        raise RuntimeContractError(label + "超过 2 MiB 读取上限")
    try:
        return path.read_text(encoding="utf-8-sig")
    except (OSError, UnicodeError) as exc:
        raise RuntimeContractError("读取 " + label + " 失败: " + str(exc)) from exc


def _field(text: str, label: str) -> str:
    match = re.search(r"(?m)^-\s*" + re.escape(label) + r"\s*[：:]\s*(.*)$", text)
    return match.group(1).strip() if match else ""


def _section(text: str, heading: str) -> str:
    match = re.search(r"(?ms)^####\s*" + re.escape(heading) + r"\s*\n(.*?)(?=^####\s|^###\s|\Z)", text)
    return match.group(1).strip() if match else ""


def _first_bullet(text: str) -> str:
    for line in text.splitlines():
        value = line.strip()
        if value.startswith("-"):
            return value[1:].strip()
    return ""


def _checkpoint_blocks(progress: str) -> List[Tuple[str, str]]:
    matches = list(re.finditer(r"(?m)^###\s+(CP-[^\n]+)\s*$", progress))
    result: List[Tuple[str, str]] = []
    for index, match in enumerate(matches):
        end = matches[index + 1].start() if index + 1 < len(matches) else len(progress)
        result.append((match.group(1).strip(), progress[match.start():end].strip()))
    return result


def _read_checkpoints(directory: Path, task_id: Optional[str]) -> Tuple[Optional[Dict[str, Any]], List[str], Dict[str, Any]]:
    current_path = directory / "CURRENT_TASK.md"
    progress_path = directory / "PROGRESS.md"
    limitations: List[str] = []
    if not current_path.is_file() or not progress_path.is_file():
        return None, ["CHECKPOINT_FILES_MISSING"], {"count": 0, "selected": 0}
    current = _read_text(current_path, "CURRENT_TASK.md")
    progress = _read_text(progress_path, "PROGRESS.md")
    blocks = _checkpoint_blocks(progress)
    selected = blocks[-MAX_CHECKPOINTS:]
    current_task = _field(current, "任务标识")
    block_tasks: List[str] = []
    parsed: List[Dict[str, Any]] = []
    for checkpoint_id, block in selected:
        task_stage = _field(block, "所属任务 / 阶段")
        block_task, _, block_stage = task_stage.partition("/")
        block_task = block_task.strip()
        block_tasks.append(block_task)
        parsed.append({
            "id": checkpoint_id,
            "task_id": block_task or None,
            "stage": block_stage.strip() or None,
            "status": _field(block, "节点状态") or None,
            "completed": _first_bullet(_section(block, "实际完成")) or None,
            "next_action": _first_bullet(_section(block, "下一步唯一行动")) or None,
            "workspace_fingerprint": _field(block, "工作区指纹") or None,
            "head": _field(block, "分支 / HEAD") or None,
        })
    if task_id and current_task and task_id != current_task:
        raise RuntimeContractError("检查点任务标识冲突: " + task_id + "," + current_task)
    requested_task = task_id or current_task or None
    distinct_block_tasks = {value for value in block_tasks if value}
    if requested_task:
        matching = [item for item in parsed if item.get("task_id") == requested_task]
        if parsed and not matching:
            limitations.append("TASK_NOT_FOUND_IN_RECENT_CHECKPOINTS")
        latest = matching[-1] if matching else None
        chosen_task = requested_task
    elif len(distinct_block_tasks) > 1:
        raise RuntimeContractError("检查点任务标识冲突: " + ",".join(sorted(distinct_block_tasks)))
    else:
        chosen_task = next(iter(distinct_block_tasks), None)
        latest = parsed[-1] if parsed else None
    return latest, limitations, {"count": len(blocks), "selected": len(selected), "current_task": chosen_task,
                                "all": parsed}


def _load_evidence(path: Path) -> Dict[str, Any]:
    raw = _read_text(path, "Evidence")
    try:
        value = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise RuntimeContractError("Evidence JSON 无法解析: " + str(path)) from exc
    if not isinstance(value, dict):
        raise RuntimeContractError("Evidence 顶层必须是对象: " + str(path))
    if value.get("schema_version") != 1:
        raise RuntimeContractError("不支持的 Evidence schema_version")
    verify_record(value, "Evidence")
    return value


def _evidence_view(path: Path, value: Mapping[str, Any], project_id: Optional[str], task_id: Optional[str],
                   snapshot: Mapping[str, Any]) -> Dict[str, Any]:
    reasons: List[str] = []
    if project_id and value.get("project_id") != project_id:
        reasons.append("PROJECT_ID_MISMATCH")
    if task_id and value.get("task_id") != task_id:
        reasons.append("TASK_ID_MISMATCH")
    baseline = value.get("baseline") if isinstance(value.get("baseline"), Mapping) else {}
    if not snapshot.get("complete") or not snapshot.get("sha256"):
        freshness = "UNKNOWN"
        reasons.append("CURRENT_SNAPSHOT_UNKNOWN")
    elif baseline.get("sha256") == snapshot.get("sha256"):
        freshness = "CURRENT"
    else:
        freshness = "STALE"
        reasons.append("REPOSITORY_BASELINE_CHANGED")
    if value.get("status") != "valid":
        reasons.append("EVIDENCE_STATUS_NOT_VALID")
    if reasons and any(reason in {"PROJECT_ID_MISMATCH", "TASK_ID_MISMATCH", "EVIDENCE_STATUS_NOT_VALID"}
                       for reason in reasons):
        freshness = "INVALID"
    return {"path": str(path), "evidence_id": value.get("evidence_id"),
            "freshness": freshness, "status": value.get("status"), "reasons": reasons}


def build_resume_view(
    repo_path: Path,
    profile_path: Optional[Path] = None,
    state_path: Optional[Path] = None,
    task_id: Optional[str] = None,
    checkpoint_dir: Optional[Path] = None,
    evidence_paths: Sequence[Path] = (),
) -> Dict[str, Any]:
    if state_path is not None and profile_path is None:
        raise RuntimeContractError("STATE_REQUIRES_PROFILE: --state requires --profile")
    if evidence_paths and profile_path is None:
        raise RuntimeContractError("EVIDENCE_REQUIRES_PROFILE: --evidence requires --profile")
    repo = repo_path.expanduser().resolve()
    project: Optional[Dict[str, Any]] = None
    state: Dict[str, Any] = {}
    if profile_path is not None:
        binding = validate_binding(profile_path, repo, state_path=state_path)
        profile = load_profile(profile_path.expanduser().resolve())
        state = load_state(binding.state_path)
        project = {"project_id": binding.project_id, "project_name": profile.get("project_name"),
                   "profile": str(binding.profile_path), "state": str(binding.state_path)}
        if task_id and state.get("current_task_id") and task_id != state.get("current_task_id"):
            raise RuntimeContractError("显式 task-id 与 Project State 不一致")
        if not task_id and state.get("current_task_id"):
            task_id = str(state["current_task_id"])
    directory = _safe_path(checkpoint_dir, "checkpoint-dir") if checkpoint_dir else None
    if directory is None and profile_path is not None:
        candidate = profile_path.expanduser().resolve().parent
        if (candidate / "CURRENT_TASK.md").is_file() or (candidate / "PROGRESS.md").is_file():
            directory = candidate
    checkpoint: Optional[Dict[str, Any]] = None
    checkpoint_limits: List[str] = []
    checkpoint_meta: Dict[str, Any] = {"count": 0, "selected": 0}
    if directory is not None:
        checkpoint, checkpoint_limits, checkpoint_meta = _read_checkpoints(directory, task_id)
    snapshot = bounded_repo_snapshot(repo)
    baseline = state.get("baseline") if isinstance(state.get("baseline"), Mapping) else {}
    if not snapshot.get("complete") or not snapshot.get("sha256"):
        repository_status = "UNKNOWN"
    elif baseline.get("sha256") and baseline.get("sha256") != snapshot.get("sha256"):
        repository_status = "CHANGED"
    elif baseline.get("sha256"):
        repository_status = "UNCHANGED"
    else:
        repository_status = "UNKNOWN"
    evidence: List[Dict[str, Any]] = []
    limitations = list(snapshot.get("limitations") or []) + checkpoint_limits
    if len(evidence_paths) > MAX_EVIDENCE:
        limitations.append("EVIDENCE_LIMIT_EXCEEDED")
        evidence_paths = evidence_paths[:MAX_EVIDENCE]
    for path in evidence_paths:
        value = _load_evidence(path.expanduser().resolve())
        evidence.append(_evidence_view(path.expanduser().resolve(), value,
                                       project.get("project_id") if project else None,
                                       task_id, snapshot))
    blockers: List[str] = []
    if state.get("blockers"):
        blockers.extend(str(item) for item in state["blockers"] if str(item).strip())
    if repository_status == "CHANGED":
        blockers.append("仓库基线已变化，旧验证或复审需要重新核验")
    if checkpoint is None:
        limitations.append("CHECKPOINT_NOT_AVAILABLE")
    if any(item["freshness"] in {"STALE", "UNKNOWN", "INVALID"} for item in evidence):
        blockers.append("存在过期或无法核验的显式 Evidence")
    next_action = (checkpoint or {}).get("next_action") or state.get("next_action") or "先提供明确的 checkpoint-dir 或 Project Profile，再重新查询恢复摘要"
    if repository_status == "CHANGED":
        next_action = "先重新读取当前差异并重跑受影响验证，再继续上次检查点的下一步。"
    elif blockers:
        next_action = "先处理当前阻塞项，再继续检查点中的下一步。"
    if blockers and next_action == "":
        next_action = "核对当前阻塞项。"
    if not checkpoint and not profile_path and not checkpoint_dir:
        limitations.append("PROFILE_AND_CHECKPOINT_INPUT_MISSING")
    if blockers:
        overall = "STALE" if repository_status == "CHANGED" else "PARTIAL"
    elif limitations or not snapshot.get("complete") or repository_status == "UNKNOWN":
        overall = "PARTIAL"
    elif checkpoint is None:
        overall = "UNKNOWN"
    else:
        overall = "CURRENT"
    return {
        "schema": "resume-view/1",
        "overall": overall,
        "project": project,
        "task": {"task_id": task_id or checkpoint_meta.get("current_task"),
                 "stage": (checkpoint or {}).get("stage") or state.get("stage"),
                 "status": (checkpoint or {}).get("status") or "UNKNOWN"},
        "checkpoint": checkpoint,
        "repository": {"status": repository_status, "baseline_sha256": baseline.get("sha256"),
                        "current_sha256": snapshot.get("sha256"), "branch": snapshot.get("branch"),
                        "head": snapshot.get("head"), "complete": snapshot.get("complete")},
        "evidence": evidence,
        "blockers": blockers,
        "next_action": next_action,
        "coverage": {"checkpoints_available": checkpoint_meta.get("count", 0),
                     "checkpoints_selected": checkpoint_meta.get("selected", 0),
                     "evidence_requested": len(evidence_paths),
                     "evidence_checked": len(evidence),
                     "snapshot_complete": bool(snapshot.get("complete"))},
        "limitations": sorted(set(limitations)),
    }


def render_resume_text(view: Mapping[str, Any]) -> str:
    project = view.get("project") or {}
    task = view.get("task") or {}
    checkpoint = view.get("checkpoint") or {}
    repository = view.get("repository") or {}
    evidence = view.get("evidence") or []
    lines = [
        "当前项目与任务：{} / {}".format(project.get("project_id") or "未绑定", task.get("task_id") or "未知"),
        "上次阶段与检查点：{} / {}".format(task.get("stage") or "未知", checkpoint.get("id") or "未找到"),
        "上次完成：{}".format(checkpoint.get("completed") or "无可引用记录"),
        "仓库变化：{}".format((repository.get("status") or "UNKNOWN")),
        "需重验：{}".format("、".join(item.get("evidence_id") or item.get("path") for item in evidence
                                  if item.get("freshness") != "CURRENT") or "无显式 Evidence"),
        "当前阻塞：{}".format("；".join(view.get("blockers") or []) or "无"),
        "下一步：{}".format(view.get("next_action") or "未知"),
        "覆盖：检查点 {}/{}，Evidence {}/{}".format(
            (view.get("coverage") or {}).get("checkpoints_selected", 0),
            (view.get("coverage") or {}).get("checkpoints_available", 0),
            (view.get("coverage") or {}).get("evidence_checked", 0),
            (view.get("coverage") or {}).get("evidence_requested", 0),
        ),
        "状态：{}".format(view.get("overall") or "UNKNOWN"),
    ]
    limitations = view.get("limitations") or []
    if limitations:
        lines.append("限制：" + "；".join(str(item) for item in limitations[:5]))
    return "\n".join(lines)
