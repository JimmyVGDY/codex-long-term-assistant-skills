"""中文：有界、只读、校验身份与检查点一致性的恢复查询。

English: Bounded read-only recovery with identity and checkpoint consistency checks.
"""
from __future__ import annotations

import json
import re
import time
from pathlib import Path
from typing import Any, Dict, Mapping, Optional, Sequence

from .capability_store import CapabilityError, bounded_read, safe_path, unique_json_object
from .common import RuntimeContractError, verify_record, validate_identifier
from .project import PROFILE_SCHEMA, STATE_SCHEMA, _profile_binding_sha256
from .resume_snapshot import SnapshotBudget, SnapshotLimit, bounded_repo_snapshot

MAX_CHECKPOINTS = 3
MAX_EVIDENCE = 20
MAX_TEXT_BYTES = 2 * 1024 * 1024
QUERY_TIMEOUT_SECONDS = 10.0
CHECKPOINT_ID = re.compile(r"^### (CP-\d{8}-\d{3,})\s*$", re.MULTILINE)
HASH = re.compile(r"^[a-f0-9]{64}$")

# 中文：协议标签在两种语言包中均保留，不作为界面字符串翻译。
# English: Preserve protocol labels in both locales, independently of UI translation.
LABELS = {
    "task": ("任务标识", "Task ID"),
    "task_stage": ("所属任务 / 阶段", "Task / Phase"),
    "state_version": ("状态版本", "State Version"),
    "last_checkpoint": ("最后检查点 ID", "Last Checkpoint ID"),
    "recent_checkpoint": ("最近检查点 ID", "Most Recent Checkpoint ID"),
    "repository": ("仓库路径", "Repository Path"),
    "block_repository": ("仓库", "Repository"),
    "node_status": ("节点状态", "Step Status"),
    "fingerprint": ("工作区指纹", "Worktree Fingerprint", "Workspace Fingerprint"),
    "head": ("分支 / HEAD", "Branch / HEAD"),
    "completed": ("实际完成", "Actual Completion"),
    "next_action": ("下一步唯一行动", "Single Next Action"),
}


class ResumeBudget:
    def __init__(self) -> None:
        self.deadline = time.monotonic() + QUERY_TIMEOUT_SECONDS
        self.remaining = MAX_TEXT_BYTES
        self.stamps: dict[Path, tuple[int, ...]] = {}

    def check_time(self) -> None:
        if time.monotonic() >= self.deadline:
            raise SnapshotLimit("RESUME_TIMEOUT")

    @staticmethod
    def stamp(path: Path) -> tuple[int, ...]:
        info = safe_path(path).stat()
        return (info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns, info.st_ctime_ns)

    def read_text(self, path: Path) -> str:
        self.check_time()
        if self.remaining <= 0:
            raise SnapshotLimit("TEXT_BUDGET_EXCEEDED")
        try:
            checked = safe_path(path)
            before = self.stamp(checked)
            raw = bounded_read(path, self.remaining)
            if self.stamp(checked) != before:
                raise SnapshotLimit("RECORD_CHANGED_DURING_READ")
            self.remaining -= len(raw)
            self.stamps[path.absolute()] = before
            result = raw.decode("utf-8-sig")
        except CapabilityError as exc:
            if str(exc) in {"TOO_LARGE", "READ_CHANGED"}:
                raise SnapshotLimit("TEXT_BUDGET_EXCEEDED" if str(exc) == "TOO_LARGE"
                                    else "RECORD_CHANGED_DURING_READ") from exc
            raise RuntimeContractError("RECORD_" + str(exc)) from exc
        except (OSError, UnicodeError) as exc:
            raise RuntimeContractError("RECORD_UNREADABLE") from exc
        self.check_time()
        return result

    def finish(self) -> None:
        self.check_time()
        for path, before in self.stamps.items():
            if self.stamp(path) != before:
                raise SnapshotLimit("RECORD_CHANGED_DURING_READ")
            self.check_time()


def _json_record(path: Path, budget: ResumeBudget, schema: int, label: str) -> dict[str, Any]:
    try:
        value = json.loads(budget.read_text(path), object_pairs_hook=unique_json_object)
    except (ValueError, RecursionError) as exc:
        raise RuntimeContractError(label + "_JSON_INVALID") from exc
    if not isinstance(value, dict) or type(value.get("schema_version")) is not int or value["schema_version"] != schema:
        raise RuntimeContractError(label + "_SCHEMA_UNSUPPORTED")
    verify_record(value, label)
    return value


def _field(text: str, label: str) -> str:
    aliases = {value.casefold() for value in LABELS[label]}
    values = []
    for line in text.splitlines():
        match = re.match(r"^-\s+([^:：]+)[:：]\s*(.*)$", line)
        if match and match[1].strip().casefold() in aliases:
            values.append(match[2].strip())
    if len(values) > 1:
        raise RuntimeContractError("CHECKPOINT_DUPLICATE_FIELD:" + label)
    return values[0] if values else ""


def _region(text: str, name: str) -> str:
    begin, end = "<!-- " + name + ":begin -->", "<!-- " + name + ":end -->"
    if text.count(begin) != 1 or text.count(end) != 1 or text.index(begin) >= text.index(end):
        raise RuntimeContractError("CHECKPOINT_MARKERS_INVALID:" + name)
    return text.split(begin, 1)[1].split(end, 1)[0]


def _section(text: str, label: str) -> str:
    aliases = {value.casefold() for value in LABELS[label]}
    active = False
    found = False
    for line in text.splitlines():
        if line.startswith("#### "):
            active = line[5:].strip().casefold() in aliases
            if active:
                if found:
                    raise RuntimeContractError("CHECKPOINT_DUPLICATE_SECTION:" + label)
                found = True
        elif active and line.startswith("- "):
            return line[2:].strip()
    return ""


def _read_checkpoints(directory: Path, repo: Path, task_id: str | None,
                      state_reference: Any, budget: ResumeBudget) -> tuple[dict[str, Any] | None, dict[str, Any]]:
    safe_path(directory)
    current_path, progress_path = directory / "CURRENT_TASK.md", directory / "PROGRESS.md"
    if not current_path.exists() or not progress_path.exists():
        return None, {"count": 0, "selected": 0, "reason": "CHECKPOINT_FILES_MISSING"}
    current, progress = budget.read_text(current_path), budget.read_text(progress_path)
    live = _region(current, "live-task-state")
    active = _region(progress, "progress-checkpoints")
    matches = list(CHECKPOINT_ID.finditer(active))
    if not matches:
        return None, {"count": 0, "selected": 0, "reason": "CHECKPOINT_NOT_AVAILABLE"}
    identifiers = [match[1] for match in matches]
    if len(identifiers) != len(set(identifiers)):
        raise RuntimeContractError("CHECKPOINT_DUPLICATE_ID")
    latest_id = identifiers[-1]
    if _field(current, "last_checkpoint") != latest_id or _field(progress, "recent_checkpoint") != latest_id:
        raise RuntimeContractError("CHECKPOINT_REFERENCE_CONFLICT")
    latest = active[matches[-1].start():]
    current_version, entry_version = _field(current, "state_version"), _field(latest, "state_version")
    if not current_version.isdigit() or current_version != entry_version:
        raise RuntimeContractError("CHECKPOINT_VERSION_CONFLICT")
    block_task, separator, stage = _field(latest, "task_stage").partition("/")
    block_task = block_task.strip()
    candidates = [value for value in (task_id, _field(current, "task"), block_task) if value]
    if not separator or not block_task or len(set(candidates)) != 1:
        raise RuntimeContractError("CHECKPOINT_TASK_CONFLICT")
    validate_identifier(block_task, "task_id")
    for recorded_repo in (_field(current, "repository"), _field(latest, "block_repository")):
        if not recorded_repo:
            raise RuntimeContractError("CHECKPOINT_REPOSITORY_MISSING")
        if safe_path(Path(recorded_repo)) != repo:
            raise RuntimeContractError("CHECKPOINT_REPOSITORY_CONFLICT")
    next_action = _section(latest, "next_action")
    if not next_action or _field(live, "next_action") != next_action:
        raise RuntimeContractError("CHECKPOINT_NEXT_ACTION_CONFLICT")
    if state_reference and state_reference != latest_id:
        raise RuntimeContractError("STATE_CHECKPOINT_REFERENCE_CONFLICT")
    return {
        "id": latest_id, "task_id": block_task, "stage": stage.strip() or None,
        "status": _field(latest, "node_status") or "UNKNOWN",
        "completed": _section(latest, "completed") or None, "next_action": next_action,
        "workspace_fingerprint": _field(latest, "fingerprint") or None,
        "fingerprint_kind": "legacy-name-status", "head": _field(latest, "head") or None,
    }, {"count": len(matches), "selected": min(MAX_CHECKPOINTS, len(matches))}


def _evidence_view(path: Path, value: Mapping[str, Any], project_id: str,
                   task_id: str | None, snapshot: Mapping[str, Any]) -> dict[str, Any]:
    if value.get("project_id") != project_id:
        raise RuntimeContractError("EVIDENCE_PROJECT_CONFLICT")
    if task_id is None or value.get("task_id") != task_id:
        raise RuntimeContractError("EVIDENCE_TASK_CONFLICT")
    baseline = value.get("baseline") if isinstance(value.get("baseline"), dict) else {}
    reasons: list[str] = []
    if baseline.get("repo_path") and safe_path(Path(baseline["repo_path"])) != Path(snapshot["repo_path"]):
        raise RuntimeContractError("EVIDENCE_REPOSITORY_CONFLICT")
    if not snapshot.get("complete") or not HASH.fullmatch(str(baseline.get("sha256") or "")):
        freshness = "UNKNOWN"
        reasons.append("BASELINE_NOT_COMPARABLE")
    elif baseline["sha256"] == snapshot.get("sha256"):
        freshness = "CURRENT"
    else:
        freshness = "STALE"
        reasons.append("REPOSITORY_BASELINE_CHANGED")
    if value.get("status") != "valid":
        freshness = "INVALID"
        reasons.append("EVIDENCE_STATUS_NOT_VALID")
    return {"path": str(path), "evidence_id": value.get("evidence_id"), "freshness": freshness,
            "status": value.get("status"), "reasons": reasons}


def _empty_view(evidence_count: int) -> dict[str, Any]:
    return {
        "schema": "resume-view/1", "overall": "PARTIAL", "project": None,
        "task": {"task_id": None, "stage": None, "status": "UNKNOWN"}, "checkpoint": None,
        "repository": {"status": "UNKNOWN", "baseline_sha256": None, "current_sha256": None,
                       "branch": None, "head": None, "complete": False},
        "evidence": [], "blockers": [], "next_action": "RECOVERY_INPUT_REQUIRED",
        "coverage": {"checkpoints_available": 0, "checkpoints_selected": 0,
                     "evidence_requested": evidence_count, "evidence_checked": 0,
                     "evidence_state": "NOT_PROVIDED" if not evidence_count else "NOT_CHECKED",
                     "snapshot_complete": False, "text_bytes_read": 0},
        "limitations": [],
    }


def error_resume_view(reason: str) -> dict[str, Any]:
    view = _empty_view(0)
    view.update(overall="ERROR", blockers=[reason], next_action="CORRECT_RECOVERY_INPUT")
    return view


def build_resume_view(repo_path: Path, profile_path: Optional[Path] = None,
                      state_path: Optional[Path] = None, task_id: Optional[str] = None,
                      checkpoint_dir: Optional[Path] = None,
                      evidence_paths: Sequence[Path] = ()) -> Dict[str, Any]:
    if state_path is not None and profile_path is None:
        raise RuntimeContractError("STATE_REQUIRES_PROFILE: --state requires --profile")
    if evidence_paths and profile_path is None:
        raise RuntimeContractError("EVIDENCE_REQUIRES_PROFILE: --evidence requires --profile")
    if task_id:
        validate_identifier(task_id, "task_id")
    budget = ResumeBudget()
    view = _empty_view(len(evidence_paths))
    if profile_path is None and checkpoint_dir is None:
        view["limitations"] = ["PROFILE_AND_CHECKPOINT_INPUT_MISSING"]
        return view
    try:
        repo = safe_path(repo_path)
        profile: dict[str, Any] = {}
        state: dict[str, Any] = {}
        if profile_path is not None:
            profile = _json_record(profile_path, budget, PROFILE_SCHEMA, "PROFILE")
            if profile.get("binding_sha256") != _profile_binding_sha256(profile):
                raise RuntimeContractError("PROFILE_BINDING_INVALID")
            project_id = profile.get("project_id")
            if not isinstance(project_id, str):
                raise RuntimeContractError("PROFILE_PROJECT_ID_INVALID")
            validate_identifier(project_id, "project_id")
            identity = profile.get("identity")
            if not isinstance(identity, dict) or not isinstance(identity.get("repo_path"), str):
                raise RuntimeContractError("PROFILE_REPOSITORY_INVALID")
            expected_repo = safe_path(Path(identity["repo_path"]))
            if repo != expected_repo and expected_repo not in repo.parents:
                raise RuntimeContractError("PROFILE_REPOSITORY_CONFLICT")
            state_path = state_path or profile_path.with_name("project-state.json")
            state = _json_record(state_path, budget, STATE_SCHEMA, "STATE")
            if state.get("project_id") != project_id:
                raise RuntimeContractError("STATE_PROJECT_CONFLICT")
            state_task = state.get("current_task_id")
            if state_task and (not isinstance(state_task, str) or task_id and task_id != state_task):
                raise RuntimeContractError("STATE_TASK_CONFLICT")
            task_id = task_id or state_task or None
            view["project"] = {"project_id": project_id, "project_name": profile.get("project_name"),
                               "profile": str(safe_path(profile_path)), "state": str(safe_path(state_path))}
        snapshot = bounded_repo_snapshot(repo, budget=SnapshotBudget(deadline=budget.deadline))
        repo = Path(snapshot["repo_path"])
        if profile and snapshot.get("root_verified"):
            if safe_path(Path(profile["identity"]["repo_path"])) != repo:
                raise RuntimeContractError("PROFILE_REPOSITORY_CONFLICT")
            expected_remote = profile["identity"].get("remote_origin") or ""
            if snapshot.get("complete") and expected_remote and snapshot.get("remote_origin") != expected_remote:
                raise RuntimeContractError("PROFILE_REMOTE_CONFLICT")
        limitations = view["limitations"]
        limitations.extend(snapshot.get("limitations") or [])
        baseline = state.get("baseline") if isinstance(state.get("baseline"), dict) else {}
        base_hash = baseline.get("sha256")
        repository_status = "UNKNOWN"
        if snapshot.get("complete") and HASH.fullmatch(str(base_hash or "")):
            repository_status = "UNCHANGED" if base_hash == snapshot["sha256"] else "CHANGED"
        view["repository"] = {
            "status": repository_status, "baseline_sha256": base_hash,
            "current_sha256": snapshot.get("sha256"), "branch": snapshot.get("branch"),
            "head": snapshot.get("head"), "complete": bool(snapshot.get("complete")),
        }
        view["coverage"]["snapshot_complete"] = bool(snapshot.get("complete"))
        if checkpoint_dir is None and profile_path is not None:
            candidate = profile_path.parent
            if (candidate / "CURRENT_TASK.md").exists() or (candidate / "PROGRESS.md").exists():
                checkpoint_dir = candidate
        if checkpoint_dir is not None:
            checkpoint, meta = _read_checkpoints(
                checkpoint_dir, repo, task_id, state.get("last_checkpoint"), budget,
            )
            view["checkpoint"] = checkpoint
            view["coverage"].update(checkpoints_available=meta["count"], checkpoints_selected=meta["selected"])
            if checkpoint:
                task_id = task_id or checkpoint["task_id"]
                view["task"] = {"task_id": task_id, "stage": checkpoint["stage"], "status": checkpoint["status"]}
            else:
                limitations.append(meta["reason"])
        else:
            limitations.append("CHECKPOINT_NOT_AVAILABLE")
        if task_id:
            validate_identifier(task_id, "task_id")
            view["task"]["task_id"] = task_id
        if len(evidence_paths) > MAX_EVIDENCE:
            limitations.append("EVIDENCE_LIMIT_EXCEEDED")
        for path in evidence_paths[:MAX_EVIDENCE]:
            value = _json_record(path, budget, 1, "EVIDENCE")
            view["evidence"].append(_evidence_view(path, value, profile["project_id"], task_id, snapshot))
            view["coverage"]["evidence_checked"] += 1
        if evidence_paths:
            view["coverage"]["evidence_state"] = "CHECKED" if len(evidence_paths) == len(view["evidence"]) else "PARTIAL"
        state_blockers = state.get("blockers") or []
        if not isinstance(state_blockers, list) or any(not isinstance(item, str) for item in state_blockers):
            raise RuntimeContractError("STATE_BLOCKERS_INVALID")
        view["blockers"] = list(state_blockers)
        if repository_status == "CHANGED":
            view["blockers"].append("仓库基线已变化，旧验证或复审需要重新核验")
        if any(item["freshness"] != "CURRENT" for item in view["evidence"]):
            view["blockers"].append("存在过期或无法核验的显式 Evidence")
        view["next_action"] = (view["checkpoint"] or {}).get("next_action") or state.get("next_action") or "RECOVERY_INPUT_REQUIRED"
        if repository_status == "CHANGED":
            view["next_action"] = "先重新读取当前差异并重跑受影响验证，再继续上次检查点的下一步。"
        elif view["blockers"]:
            view["next_action"] = "先处理当前阻塞项，再继续检查点中的下一步。"
        budget.finish()
        if repository_status == "CHANGED":
            view["overall"] = "STALE"
        elif not limitations and not view["blockers"] and view["checkpoint"] and repository_status == "UNCHANGED":
            view["overall"] = "CURRENT"
    except SnapshotLimit as exc:
        view["limitations"].append(str(exc))
        view["repository"].update(status="UNKNOWN", current_sha256=None, complete=False)
        view["coverage"]["snapshot_complete"] = False
        for evidence in view["evidence"]:
            evidence.update(freshness="UNKNOWN", reasons=["QUERY_INCOMPLETE"])
        view["overall"] = "PARTIAL"
        view["next_action"] = "RECHECK_INCOMPLETE_RECOVERY_INPUT"
    except CapabilityError as exc:
        raise RuntimeContractError("RESUME_" + str(exc)) from exc
    except (OSError, TypeError, KeyError, ValueError, RecursionError) as exc:
        raise RuntimeContractError("RESUME_INPUT_INVALID") from exc
    view["coverage"]["text_bytes_read"] = MAX_TEXT_BYTES - budget.remaining
    view["limitations"] = sorted(set(view["limitations"]))
    return view


def render_resume_text(view: Mapping[str, Any]) -> str:
    project = view.get("project") or {}
    task = view.get("task") or {}
    checkpoint = view.get("checkpoint") or {}
    repository = view.get("repository") or {}
    evidence = view.get("evidence") or []
    needs_validation = "、".join(str(item.get("evidence_id") or item.get("path")) for item in evidence
                                if item.get("freshness") != "CURRENT")
    if not needs_validation:
        needs_validation = "CURRENT" if evidence else "无显式 Evidence"
    lines = [
        "当前项目与任务：{} / {}".format(project.get("project_id") or "未绑定", task.get("task_id") or "未知"),
        "上次阶段与检查点：{} / {}".format(task.get("stage") or "未知", checkpoint.get("id") or "未找到"),
        "上次完成：{}".format(checkpoint.get("completed") or "无可引用记录"),
        "仓库变化：{}".format((repository.get("status") or "UNKNOWN")),
        "需重验：{}".format(needs_validation),
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
    return "\n".join(" ".join(line.splitlines()) for line in lines)
