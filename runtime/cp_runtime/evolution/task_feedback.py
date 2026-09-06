"""中文：机械验证和主协调 Agent 最终化的任务反馈，不保存命令或输出正文。

English: Mechanical validation and parent-finalized task feedback without command or output bodies.

每个项目/仓库/会话/轮次/任务只有一份不可变定稿；工作区随后变化必须使用新轮次。
Each project/repository/session/turn/task has one immutable final report; later workspace changes require a new turn.
"""
from __future__ import annotations

import subprocess
import time
import uuid
from pathlib import Path
from typing import Any, Mapping, Sequence

from .artifacts import ArtifactError, HASH, MAX_BYTES, _git_bytes, identifier, load, persist, project_identity, seal, verify, worktree_fingerprint
from .contracts import parse_iso_datetime, sha256_hex, utc_now_iso
from .storage import safe_child

VALIDATION_SCHEMA = "task-validation/1"
FEEDBACK_SCHEMA = "task-feedback/1"
OUTCOMES = {"PASS", "BLOCKED", "FAILED", "CANCELLED", "PARTIAL", "UNKNOWN"}
FAILURES = {"NONE", "INPUT_CONTRACT", "ROUTING", "IMPLEMENTATION", "VALIDATION", "REVIEW", "ENVIRONMENT", "UNKNOWN"}
ROUTING = {"MATCHED", "MISSED", "UNNECESSARY", "WRONG_DOMAIN", "UNKNOWN"}
IDENTITY_KEYS = ("project_id", "repo_fingerprint", "session_id", "turn_id", "task_id", "worktree_root", "worktree_fingerprint")


def subject(project_dir: Path, session_id: str, turn_id: str, task_id: str) -> dict[str, str]:
    value = project_identity(project_dir)
    value.update(session_id=identifier(session_id), turn_id=identifier(turn_id), task_id=identifier(task_id))
    value["worktree_fingerprint"] = worktree_fingerprint(Path(value["worktree_root"]))
    return value


def report_path(identity: Mapping[str, str]) -> str:
    locator = {key: identity[key] for key in ("project_id", "repo_fingerprint", "session_id", "turn_id", "task_id")}
    return "feedback/finalized-tasks/" + sha256_hex(locator) + ".json"


def run_validation(project_dir: Path, session_id: str, turn_id: str, task_id: str,
                   command: Sequence[str], timeout_seconds: int = 600) -> dict[str, Any]:
    if not command or not 1 <= timeout_seconds <= 600:
        raise ArtifactError("INVALID_VALIDATION_COMMAND")
    identity = subject(project_dir, session_id, turn_id, task_id)
    started = time.monotonic()
    try:
        result = subprocess.run(list(command), cwd=identity["worktree_root"], stdout=subprocess.DEVNULL,
                                stderr=subprocess.DEVNULL, timeout=timeout_seconds, shell=False)
        code = result.returncode
    except subprocess.TimeoutExpired:
        code = 124
    unchanged = worktree_fingerprint(Path(identity["worktree_root"])) == identity["worktree_fingerprint"]
    value = seal({"schema_version": VALIDATION_SCHEMA, "validation_id": "VAL_" + uuid.uuid4().hex,
                  "commit": _git_bytes(Path(identity["worktree_root"]), ["rev-parse", "HEAD"]).decode().strip(),
                  "subject": identity, "command_digest": sha256_hex(list(command)), "exit_code": code,
                  "workspace_unchanged": unchanged, "duration_ms": int((time.monotonic() - started) * 1000),
                  "workspace_clean": not bool(_git_bytes(Path(identity["worktree_root"]), ["status", "--porcelain=v1", "-z"])),
                  "observed_at": utc_now_iso(), "execution_authorization": "NONE"})
    ref = persist(project_dir, "feedback/validations/" + value["validation_id"] + ".json", value)
    return {"reference": ref, "exit_code": code, "workspace_unchanged": unchanged}


def _validate_report(project_dir: Path, value: Mapping[str, Any]) -> dict[str, Any]:
    report = verify(dict(value), FEEDBACK_SCHEMA)
    if set(report) != {"schema_version", "subject", "finalized_by", "terminal_outcome", "failure_category",
                       "routing_deviation", "repair_rounds", "validation_passed", "validation_failed", "evidence_refs",
                       "execution_authorization", "finalized_at", "content_hash", "root_cause_id", "root_cause_confirmed"}:
        raise ArtifactError("FEEDBACK_UNKNOWN_FIELDS")
    identity = report["subject"]
    if set(identity) != set(IDENTITY_KEYS) or report["finalized_by"] != "parent:" + identifier(identity["task_id"]):
        raise ArtifactError("FEEDBACK_FINALIZER_MISMATCH")
    expected = project_identity(project_dir, verify_live=False)
    if any(identity[key] != expected[key] for key in expected):
        raise ArtifactError("FEEDBACK_IDENTITY_MISMATCH")
    for key in ("session_id", "turn_id", "task_id"):
        identifier(identity[key])
    if not HASH.fullmatch(identity["worktree_fingerprint"]):
        raise ArtifactError("FEEDBACK_WORKTREE_INVALID")
    if report["terminal_outcome"] not in OUTCOMES or report["failure_category"] not in FAILURES or report["routing_deviation"] not in ROUTING:
        raise ArtifactError("FEEDBACK_ENUM_INVALID")
    if type(report["repair_rounds"]) is not int or not 0 <= report["repair_rounds"] <= 100:
        raise ArtifactError("FEEDBACK_REPAIR_COUNT_INVALID")
    if type(report["root_cause_confirmed"]) is not bool:
        raise ArtifactError("FEEDBACK_ROOT_CAUSE_INVALID")
    if report["root_cause_id"]:
        identifier(report["root_cause_id"])
    if report["root_cause_confirmed"] and (not report["root_cause_id"] or report["failure_category"] in {"NONE", "UNKNOWN"}):
        raise ArtifactError("FEEDBACK_ROOT_CAUSE_UNSUPPORTED")
    finalized = parse_iso_datetime(report["finalized_at"], "finalized_at")
    references = report["evidence_refs"]
    if not 1 <= len(references) <= 100 or len({ref["path"] for ref in references}) != len(references):
        raise ArtifactError("FEEDBACK_EVIDENCE_INVALID")
    passed = failed = 0
    if sum(safe_child(project_dir, ref["path"]).stat().st_size for ref in references) > MAX_BYTES:
        raise ArtifactError("FEEDBACK_EVIDENCE_TOO_LARGE")
    for ref in references:
        if set(ref) != {"path", "content_hash"}:
            raise ArtifactError("FEEDBACK_REFERENCE_FIELDS")
        evidence = load(project_dir, ref["path"], ref["content_hash"], VALIDATION_SCHEMA)
        if set(evidence) != {"schema_version", "validation_id", "subject", "command_digest", "exit_code", "commit",
                             "workspace_unchanged", "workspace_clean", "duration_ms", "observed_at", "execution_authorization", "content_hash"}:
            raise ArtifactError("VALIDATION_UNKNOWN_FIELDS")
        if evidence["subject"] != identity or not evidence["workspace_unchanged"]:
            raise ArtifactError("VALIDATION_BASELINE_MISMATCH")
        if parse_iso_datetime(evidence["observed_at"], "observed_at") > finalized:
            raise ArtifactError("VALIDATION_TIME_MISMATCH")
        if type(evidence["exit_code"]) is not int:
            raise ArtifactError("VALIDATION_EXIT_CODE_INVALID")
        passed += evidence["exit_code"] == 0
        failed += evidence["exit_code"] != 0
    if report["validation_passed"] != passed or report["validation_failed"] != failed:
        raise ArtifactError("VALIDATION_COUNT_MISMATCH")
    if report["terminal_outcome"] == "PASS" and (not passed or failed or report["failure_category"] != "NONE"):
        raise ArtifactError("FEEDBACK_PASS_UNSUPPORTED")
    return report


def finalize_feedback(project_dir: Path, session_id: str, turn_id: str, task_id: str, *,
                      actor: str, outcome: str, failure_category: str, routing_deviation: str,
                      repair_rounds: int, evidence_paths: Sequence[str], root_cause_id: str = "",
                      root_cause_confirmed: bool = False) -> dict[str, Any]:
    identity = subject(project_dir, session_id, turn_id, task_id)
    references = []
    passed = failed = 0
    for path in evidence_paths:
        evidence = load(project_dir, path, schema=VALIDATION_SCHEMA)
        references.append({"path": path, "content_hash": evidence["content_hash"]})
        passed += evidence["exit_code"] == 0
        failed += evidence["exit_code"] != 0
    payload = {"schema_version": FEEDBACK_SCHEMA, "subject": identity, "finalized_by": actor,
               "terminal_outcome": outcome, "failure_category": failure_category, "routing_deviation": routing_deviation,
               "repair_rounds": repair_rounds, "validation_passed": passed, "validation_failed": failed,
               "evidence_refs": references, "execution_authorization": "NONE"}
    payload.update(root_cause_id=root_cause_id, root_cause_confirmed=root_cause_confirmed)
    relative = report_path(identity)
    if safe_child(project_dir, relative).exists():
        existing = _validate_report(project_dir, load(project_dir, relative))
        if any(existing[key] != item for key, item in payload.items()):
            raise ArtifactError("FEEDBACK_FINALIZATION_CONFLICT")
        return {"reference": {"path": relative, "content_hash": existing["content_hash"]}, "report": existing}
    report = _validate_report(project_dir, seal({**payload, "finalized_at": utc_now_iso()}))
    return {"reference": persist(project_dir, relative, report), "report": report}


def consume_for_hook(project_dir: Path, event: Mapping[str, Any], cwd: str) -> dict[str, Any] | None:
    if not all(event.get(key) for key in ("session_id", "turn_id", "task_id")):
        return None
    relative = report_path(event)
    if not safe_child(project_dir, relative).exists():
        return None
    report = _validate_report(project_dir, load(project_dir, relative))
    identity = report["subject"]
    for key in ("project_id", "repo_fingerprint", "session_id", "turn_id", "task_id"):
        if identity[key] != event[key]:
            raise ArtifactError("FEEDBACK_HOOK_IDENTITY_MISMATCH")
    if str(Path(cwd).resolve()) != identity["worktree_root"] or worktree_fingerprint(Path(cwd), time_budget_seconds=1) != identity["worktree_fingerprint"]:
        raise ArtifactError("FEEDBACK_HOOK_STALE")
    return report


def finalized_reports(project_dir: Path, maximum: int = 200000) -> list[tuple[str, dict[str, Any]]]:
    root = safe_child(project_dir, "feedback", "finalized-tasks")
    paths = []
    if root.exists():
        for path in root.glob("*.json"):
            if len(paths) >= maximum:
                raise ArtifactError("TOO_MANY_FEEDBACK_REPORTS")
            paths.append(path)
    result = []
    total_bytes = 0
    for path in sorted(paths):
        relative = "feedback/finalized-tasks/" + path.name
        value = load(project_dir, relative)
        total_bytes += path.stat().st_size + sum(safe_child(project_dir, ref["path"]).stat().st_size for ref in value["evidence_refs"])
        if total_bytes > MAX_BYTES:
            raise ArtifactError("FEEDBACK_TOTAL_IO_LIMIT")
        value = _validate_report(project_dir, value)
        if relative != report_path(value["subject"]):
            raise ArtifactError("FEEDBACK_LOCATION_MISMATCH")
        result.append((relative, value))
    return result
