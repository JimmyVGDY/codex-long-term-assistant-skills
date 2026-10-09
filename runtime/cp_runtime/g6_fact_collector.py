"""中文：有界采集 Git 范围指标；数量仅是信号，不是难度证明。

English: Bounded Git scope measurements; counts are signals, never difficulty proof.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import tempfile
import time
from pathlib import Path
from typing import Any

from .common import (atomic_write_json, require_external_state, resolve_codex_home,
                     utc_now)
from .path_identity import same_path
from .routing_contract import _constant, _object, fail, ref, sha

VERSION = "g6-git-scope-facts/2"
DICTIONARY_VERSION = "g6-metric-dictionary/1"
RECEIPT_VERSION = "g6-scope-metric-receipt/1"
DATA_CLASSES = ("measured", "deterministic_derived", "policy_parameter",
                "estimate", "semantic_suggestion", "unknown")
MAX_TOTAL_SECONDS = 5.0
ALL_REPO_SCOPE = "@repo"
MAX_PATHS = 32
MAX_OUTPUT = 1_000_000
MAX_FILE_BYTES = 1_000_000
MAX_CHANGED_FILES = 4096
CATEGORY_RULES = {
    "api_contract": {"api", "route", "routes", "endpoint", "endpoints"},
    "data_contract": {"schema", "schemas", "migration", "migrations", "sql"},
    "permission_boundary": {"auth", "permission", "permissions", "access"},
    "state_boundary": {"state", "states", "workflow", "task", "tasks"},
}

# 中文：首批指标的类型和来源固定登记；未采集的值仍为 UNKNOWN。
# English: First-batch metric types and sources are registered; unavailable values remain UNKNOWN.
METRIC_SPECS = (
    ("changed_files", "scope", "file", "git:numstat+untracked", "integer", "measured"),
    ("changed_lines", "scope", "line", "git:numstat+untracked-text", "integer", "measured"),
    ("changed_modules", "scope", "top_level_path", "git:changed-paths", "integer", "deterministic_derived"),
    ("module_map_quality", "scope", "enum", "path:first-component", "string", "estimate"),
    ("contract_categories_hit", "contract", "category", "versioned:path-token-rules", "array", "deterministic_derived"),
    ("state_path_hits", "contract", "path", "versioned:path-token-rules", "integer", "deterministic_derived"),
    ("read_bytes", "material", "byte", "context-reader:verified-read", "integer", "measured"),
    ("token_estimate", "material", "token", "versioned:content-token-estimator", "integer", "estimate"),
    ("deduplicated_items", "material", "item", "context-reader:source-fingerprint", "integer", "deterministic_derived"),
    ("truncated_items", "material", "item", "context-reader:truncation-receipt", "integer", "measured"),
    ("cache_hits", "material", "item", "context-reader:cache-receipt", "integer", "measured"),
    ("charged_units", "resource", "planning_unit", "g6-ledger:terminal", "integer", "measured"),
    ("inflight_units", "resource", "planning_unit", "g6-ledger:reservation", "integer", "measured"),
    ("remaining_units", "resource", "planning_unit", "g6-ledger:verified-snapshot", "integer", "deterministic_derived"),
    ("attempts_used", "resource", "attempt", "g6-ledger:reservation-and-terminal", "integer", "measured"),
    ("created_calls", "execution", "call", "g6-ledger:verified-host-created", "integer", "measured"),
    ("active_reservations", "scheduling", "reservation", "g6-ledger:active-reservation", "integer", "measured"),
    ("queue_depth", "scheduling", "work_item", "g6-scheduler:queue-snapshot", "integer", "measured"),
    ("call_depth", "scheduling", "level", "desktop-host:task-tree", "integer", "measured"),
    ("deadline_ms", "scheduling", "millisecond", "g6-policy:deadline", "integer", "policy_parameter"),
    ("terminal_outcome", "execution", "enum", "native-host:verified-terminal", "string", "measured"),
    ("call_elapsed_ms", "execution", "millisecond", "native-host:verified-timestamps", "integer", "measured"),
    ("error_class", "execution", "enum", "native-host:classified-error", "string", "deterministic_derived"),
    ("check_exit_code", "validation", "exit_code", "validation-run:process-receipt", "integer", "measured"),
    ("check_id", "validation", "check_id", "validation-run:versioned-identity", "string", "measured"),
    ("check_coverage", "validation", "check_id", "validation-run:scope-manifest", "array", "deterministic_derived"),
    ("deduplicated_findings", "review", "finding", "review-receipt:exact-fingerprint", "integer", "deterministic_derived"),
    ("confirmed_findings", "review", "finding", "review-receipt:adjudication", "integer", "measured"),
    ("false_positives", "review", "finding", "review-receipt:adjudication", "integer", "measured"),
    ("unresolved_findings", "review", "finding", "review-receipt:unadjudicated", "integer", "measured"),
    ("semantic_task_kind", "task", "enum", "model:semantic-proposal", "string", "semantic_suggestion"),
    ("host_tokens", "actual_cost", "token", "desktop-host:usage-receipt", "integer", "measured"),
    ("host_credits", "actual_cost", "credit", "desktop-host:billing-receipt", "number", "measured"),
    ("host_elapsed_ms", "actual_cost", "millisecond", "desktop-host:timing-receipt", "integer", "measured"),
)
DEFINITIONS = {
    "changed_files": "Distinct tracked and untracked paths changed under the declared scope",
    "changed_lines": "Added plus removed text lines under the declared scope; null for binary or unreadable inputs",
    "changed_modules": "Distinct first path components among changed paths; only an approximate module map",
    "module_map_quality": "Quality label for the module mapping rule used on the changed-path set",
    "contract_categories_hit": "Distinct versioned path-token categories observed in the complete changed-path set",
    "state_path_hits": "Changed paths whose tokens match the versioned state-boundary rule",
    "read_bytes": "Bytes actually returned by a verified context read",
    "token_estimate": "Tokens estimated from content by a named versioned estimator, not host usage",
    "deduplicated_items": "Verified context items removed as exact source-fingerprint duplicates",
    "truncated_items": "Verified context items whose content was truncated",
    "cache_hits": "Verified context reads served from a matching content-addressed cache",
    "charged_units": "Planning units retained by terminal events in the verified root ledger",
    "inflight_units": "Planning units held by active reservations in the verified root ledger",
    "remaining_units": "Capacity minus charged, inflight and required future holds at one ledger head",
    "attempts_used": "All retained attempts including reserved and proven not-started attempts at one ledger head",
    "created_calls": "Native calls with an exact verified host-created receipt at one ledger head",
    "active_reservations": "Reservations still held at one ledger head, including unknown creation state",
    "queue_depth": "Pending work items in one scheduler snapshot",
    "call_depth": "Depth of one host task-tree node from its root",
    "deadline_ms": "Total time allowed by the active versioned scheduling policy",
    "terminal_outcome": "Outcome from the native terminal evidence of one exact host call",
    "call_elapsed_ms": "Elapsed milliseconds between verified native call start and terminal timestamps",
    "error_class": "Versioned classification of one verified native failure",
    "check_exit_code": "Process exit code for one versioned validation check on one source baseline",
    "check_id": "Identity and version of one validation check",
    "check_coverage": "Check identifiers covered by one versioned validation scope manifest",
    "deduplicated_findings": "Distinct exact-fingerprint findings from one review root",
    "confirmed_findings": "Distinct findings adjudicated valid for one review baseline",
    "false_positives": "Distinct findings adjudicated false for one review baseline",
    "unresolved_findings": "Distinct findings awaiting adjudication for one review baseline",
    "semantic_task_kind": "Model-proposed task kind pending independent rule and source validation",
    "host_tokens": "Tokens reported by the host for one exact native call",
    "host_credits": "Credits reported by a host billing receipt for one exact native call",
    "host_elapsed_ms": "Elapsed milliseconds reported by the host for one exact native call",
}


def metric_dictionary() -> dict[str, Any]:
    """中文：登记单位、来源、类型、基线、时效、缺失和决策用途。

    English: Register unit, source, type, baseline, freshness, missing semantics and use.
    """
    metrics = []
    for metric_id, group, unit, source, value_type, data_class in METRIC_SPECS:
        baseline = ("git-commit-and-worktree" if group in {"scope", "contract"} else
                    "verified-ledger-head" if group in {"resource", "scheduling"} else
                    "source-or-native-receipt")
        missing = ("UNKNOWN; restrict budgeted dispatch until ledger verification"
                   if group == "resource" else
                   "UNKNOWN; do not infer zero or convert planning units"
                   if group == "actual_cost" else
                   "null/UNKNOWN; retain verified partial material")
        freshness = ("retain with original host call" if group in {"actual_cost", "execution"} else
                     "reread before budgeted action" if group in {"resource", "scheduling"} else
                     "invalidate on source or rule baseline change")
        decision_use = ("context scope only; never difficulty alone" if group == "scope" else
                        "follow-up reading or review angle; never defect proof" if group == "contract" else
                        "exact budget admission" if group == "resource" else
                        "observation only; not initial dispatch eligibility" if group == "review" else
                        "semantic proposal; script recomputes final choice" if group == "task" else
                        "separate cost report" if group == "actual_cost" else
                        "bounded workflow and evidence reporting")
        metrics.append({"metric_id": metric_id, "definition": DEFINITIONS[metric_id],
                        "unit": unit, "source": source, "calculation_version": VERSION,
                        "scope": group, "baseline": baseline,
                        "freshness": freshness,
                        "missing_behavior": missing, "decision_use": decision_use,
                        "value_type": value_type, "data_class": data_class})
    return {"schema_version": DICTIONARY_VERSION,
            "data_classes": list(DATA_CLASSES), "metrics": metrics}


class CollectionUnavailable(Exception):
    """中文：可选来源超时、超量或不可用；English: Optional source is bounded or unavailable."""

    def __init__(self, reason: str):
        super().__init__(reason)
        self.reason = reason


class MetricReceiptIntegrityError(RuntimeError):
    """中文：指标收据引用或归属不一致；English: Metric receipt integrity or owner mismatch."""


STORED_SCOPE_METRICS = ("changed_files", "changed_lines", "changed_modules",
                        "module_map_quality", "contract_categories_hit", "state_path_hits")
RECEIPT_FIELDS = {"schema_version", "identity", "host_session_ref", "baseline_sha256",
                  "dictionary_version", "collection_status", "measurement_source_ref",
                  "scope_ref", "metrics", "unknown_fields", "missing_reason",
                  "observed_tracked_files", "observed_tracked_lines"}


def _receipt_path(source_ref: str) -> Path:
    sha(source_ref)
    return (resolve_codex_home() / "cp-assistant" / "g6-routing" / "facts" /
            (source_ref[7:] + ".json"))


def read_metric_receipt(source_ref: str, *, identity: dict[str, str],
                        host_session_ref: str, baseline_sha256: str) -> dict[str, Any]:
    """中文：按内容引用和根身份读回最小指标值；English: Read by content ref and root identity."""
    path = _receipt_path(source_ref)
    try:
        value = json.loads(path.read_text(encoding="utf-8"),
                           object_pairs_hook=_object, parse_constant=_constant)
    except (OSError, ValueError) as exc:
        raise MetricReceiptIntegrityError("G6_METRIC_RECEIPT_UNREADABLE") from exc
    if (not isinstance(value, dict) or set(value) != RECEIPT_FIELDS
            or value["schema_version"] != RECEIPT_VERSION or ref(value) != source_ref
            or value["identity"] != identity or value["host_session_ref"] != host_session_ref
            or value["baseline_sha256"] != baseline_sha256
            or set(value["metrics"]) != set(STORED_SCOPE_METRICS)):
        raise MetricReceiptIntegrityError("G6_METRIC_RECEIPT_INTEGRITY")
    return value


def store_metric_receipt(report: dict[str, Any], *, identity: dict[str, str],
                         host_session_ref: str, baseline_sha256: str,
                         repo_path: Path) -> str | None:
    """中文：只保存计数、缺项和来源摘要，不保存 Prompt 或代码正文。

    English: Persist counts, unknowns and source digests, never prompts or code bodies.
    """
    if report["source_ref"] is None or report["collection_status"] == "UNKNOWN":
        return None
    value = {"schema_version": RECEIPT_VERSION, "identity": identity,
             "host_session_ref": host_session_ref, "baseline_sha256": baseline_sha256,
             "dictionary_version": report["dictionary_version"],
             "collection_status": report["collection_status"],
             "measurement_source_ref": report["source_ref"],
             "scope_ref": ref(report["scope_paths"]),
             "metrics": {key: report["metrics"][key] for key in STORED_SCOPE_METRICS},
             "unknown_fields": report["unknown_fields"],
             "observed_tracked_files": report["observed_tracked_files"],
             "observed_tracked_lines": report["observed_tracked_lines"],
             "missing_reason": report["missing_reason"]}
    source_ref = ref(value)
    path = _receipt_path(source_ref)
    require_external_state(path.resolve(), repo_path.resolve())
    if not path.exists():
        atomic_write_json(path, value)
    readback = read_metric_receipt(source_ref, identity=identity,
                                   host_session_ref=host_session_ref,
                                   baseline_sha256=baseline_sha256)
    if readback != value:
        raise MetricReceiptIntegrityError("G6_METRIC_RECEIPT_CHANGED")
    return source_ref


def _git_env(repo: Path) -> dict[str, str]:
    """中文：只保留宿主对当前精确仓库的 safe.directory 授权。

    English: Retain only host safe.directory grants for this exact repository.
    """
    environment = {key: value for key, value in os.environ.items() if not key.startswith("GIT_")}
    grants = []
    try:
        count = min(16, max(0, int(os.environ.get("GIT_CONFIG_COUNT", "0"))))
    except ValueError:
        count = 0
    for index in range(count):
        key = os.environ.get(f"GIT_CONFIG_KEY_{index}")
        value = os.environ.get(f"GIT_CONFIG_VALUE_{index}")
        if key == "safe.directory" and value and value != "*":
            try:
                if same_path(Path(value), repo):
                    grants.append(value)
            except (OSError, ValueError):
                continue
    environment.update(GIT_OPTIONAL_LOCKS="0", GIT_TERMINAL_PROMPT="0",
                       GIT_CONFIG_COUNT=str(len(grants)))
    for index, value in enumerate(grants):
        environment[f"GIT_CONFIG_KEY_{index}"] = "safe.directory"
        environment[f"GIT_CONFIG_VALUE_{index}"] = value
    return environment


def _run(repo: Path, *args: str, deadline: float, remaining_output: int) -> bytes:
    """中文：全部子命令共享协作式五秒预算与输出上限。

    English: Subprocesses share one cooperative five-second budget and output cap.
    """
    remaining_time = deadline - time.monotonic()
    if remaining_time <= 0:
        raise CollectionUnavailable("time_budget")
    if remaining_output <= 0:
        raise CollectionUnavailable("output_budget")
    environment = _git_env(repo)
    try:
        with tempfile.TemporaryFile() as output:
            result = subprocess.run(["git", "-c", "core.fsmonitor=false", "-C", str(repo), *args],
                                    stdout=output, stderr=subprocess.DEVNULL,
                                    timeout=remaining_time, check=False, env=environment)
            if result.returncode:
                raise CollectionUnavailable("source_unavailable")
            size = output.tell()
            if size > remaining_output:
                raise CollectionUnavailable("output_budget")
            output.seek(0)
            return output.read(remaining_output + 1)
    except subprocess.TimeoutExpired as exc:
        raise CollectionUnavailable("time_budget") from exc
    except OSError as exc:
        raise CollectionUnavailable("source_unavailable") from exc


def _scope(paths: list[str]) -> list[str]:
    if not isinstance(paths, list) or not 1 <= len(paths) <= MAX_PATHS:
        fail("G6_SCOPE_PATH_COUNT")
    result = []
    for item in paths:
        if (not isinstance(item, str) or not item or len(item) > 260
                or item.startswith(("/", "\\")) or re.match(r"^[A-Za-z]:", item)
                or "\\" in item or "\x00" in item
                or any(part in {"", ".", ".."} for part in item.split("/"))):
            fail("G6_SCOPE_PATH_UNSAFE")
        result.append(item)
    if len(result) != len(set(result)) or (ALL_REPO_SCOPE in result and len(result) != 1):
        fail("G6_SCOPE_PATH_DUPLICATE")
    return result


def _hints(paths: list[str]) -> tuple[list[str], int]:
    categories = set()
    state_hits = 0
    for name in paths:
        tokens = {token.lower() for token in re.split(r"[/._-]+", name) if token}
        if name.lower().endswith(".sql"):
            tokens.add("sql")
        for category, words in CATEGORY_RULES.items():
            if tokens & words:
                categories.add(category)
                if category == "state_boundary":
                    state_hits += 1
    return sorted(categories), state_hits


def collect(repo_path: Path, *, baseline_commit: str, scope_paths: list[str]) -> dict[str, Any]:
    """中文：按协作式五秒预算返回事实；单次文件系统 I/O 无硬截止保证。

    English: Use a cooperative five-second budget; one filesystem I/O has no hard cutoff.
    """
    started = time.monotonic()
    deadline = started + MAX_TOTAL_SECONDS
    scope = _scope(scope_paths)
    if not isinstance(baseline_commit, str) or not re.fullmatch(r"[0-9a-fA-F]{40,64}", baseline_commit):
        fail("G6_BASELINE_COMMIT")
    baseline = baseline_commit.lower()
    repo = repo_path.resolve()
    completed: list[str] = []
    output_used = 0
    diff: bytes | None = None
    untracked: bytes | None = None
    missing_reason: str | None = None
    try:
        root_raw = _run(repo, "rev-parse", "--show-toplevel", deadline=deadline,
                        remaining_output=MAX_OUTPUT - output_used)
        output_used += len(root_raw)
        root = Path(root_raw.decode("utf-8").strip()).resolve()
        if root != repo:
            fail("G6_SCOPE_NOT_REPO_ROOT")
        completed.append("repo_identity")
        _run(repo, "cat-file", "-e", baseline + "^{commit}", deadline=deadline,
             remaining_output=MAX_OUTPUT - output_used)
        completed.append("baseline_commit")
        pathspecs = [] if scope == [ALL_REPO_SCOPE] else [":(literal)" + item for item in scope]
        diff = _run(repo, "diff", "--numstat", "-z", "--no-renames", baseline, "--", *pathspecs,
                    deadline=deadline, remaining_output=MAX_OUTPUT - output_used)
        output_used += len(diff)
        completed.append("tracked_diff")
        untracked = _run(repo, "ls-files", "--others", "--exclude-standard", "-z", "--", *pathspecs,
                         deadline=deadline, remaining_output=MAX_OUTPUT - output_used)
        output_used += len(untracked)
        completed.append("untracked_paths")
    except CollectionUnavailable as exc:
        missing_reason = exc.reason
    changed: set[str] = set()
    line_total = 0
    lines_known = True
    for raw in (diff or b"").split(b"\x00"):
        if not raw:
            continue
        columns = raw.decode("utf-8", errors="surrogateescape").split("\t", 2)
        if len(columns) != 3:
            fail("G6_NUMSTAT_SHAPE")
        added, removed, name = columns
        changed.add(name)
        if added == "-" or removed == "-":
            lines_known = False
        else:
            line_total += int(added) + int(removed)
    observed_tracked_files = len(changed) if diff is not None else None
    observed_tracked_lines = line_total if diff is not None and lines_known else None
    untracked_scan_complete = True
    untracked_content_digest = hashlib.sha256()
    remaining_content = MAX_OUTPUT
    for raw in (untracked or b"").split(b"\x00"):
        if not raw:
            continue
        if time.monotonic() >= deadline:
            lines_known = False
            missing_reason = "time_budget"
            untracked_scan_complete = False
            break
        name = raw.decode("utf-8", errors="surrogateescape")
        changed.add(name)
        untracked_content_digest.update(raw)
        untracked_content_digest.update(b"\x00")
        path = repo / name
        try:
            unsafe = path.is_symlink() or not path.is_file()
            size = path.stat().st_size if not unsafe else None
            if unsafe or size > MAX_FILE_BYTES or size > remaining_content:
                lines_known = False
                untracked_content_digest.update(b"UNREADABLE\x00")
                if size is not None and size > remaining_content and missing_reason is None:
                    missing_reason = "material_byte_budget"
            else:
                with path.open("rb") as stream:
                    content = stream.read(remaining_content + 1)
                if len(content) > remaining_content:
                    lines_known = False
                    untracked_content_digest.update(b"UNREADABLE\x00")
                    if missing_reason is None:
                        missing_reason = "material_byte_budget"
                else:
                    remaining_content -= len(content)
                    untracked_content_digest.update(content)
                    untracked_content_digest.update(b"\x00")
                    if b"\x00" in content:
                        lines_known = False
                    else:
                        line_total += len(content.splitlines())
        except OSError:
            lines_known = False
            untracked_content_digest.update(b"UNREADABLE\x00")
        if time.monotonic() >= deadline:
            lines_known = False
            missing_reason = "time_budget"
            untracked_scan_complete = False
            break
    if len(changed) > MAX_CHANGED_FILES:
        missing_reason = "changed_file_bound"
    if time.monotonic() >= deadline and missing_reason is None:
        missing_reason = "time_budget"
    names_complete = (untracked is not None and untracked_scan_complete
                      and missing_reason != "changed_file_bound")
    names = sorted(changed)
    categories, state_hits = _hints(names)
    modules = {name.split("/", 1)[0] for name in names}
    raw_ref = (ref({"numstat_sha256": hashlib.sha256(diff).hexdigest(),
                    "untracked_sha256": hashlib.sha256(untracked).hexdigest() if untracked is not None else None,
                    "untracked_content_sha256": untracked_content_digest.hexdigest()
                    if untracked is not None and untracked_scan_complete else None,
                    "scope": scope, "baseline": baseline, "rule_version": VERSION,
                    "completed_sources": completed})
               if diff is not None else None)
    values = {"changed_files": len(names) if names_complete else None,
              "changed_lines": line_total if names_complete and lines_known else None,
              "changed_modules": len(modules) if names_complete else None,
              "module_map_quality": "approximate_root" if names_complete else None,
              "contract_categories_hit": categories if names_complete else None,
              "state_path_hits": state_hits if names_complete else None}
    status = "COMPLETE" if names_complete and missing_reason != "time_budget" else \
             "PARTIAL" if diff is not None else "UNKNOWN"
    if not lines_known and missing_reason is None:
        missing_reason = "binary_or_unreadable_lines"
    registry = metric_dictionary()
    metrics = {}
    for definition in registry["metrics"]:
        metric_id = definition["metric_id"]
        value = values.get(metric_id)
        metrics[metric_id] = {"value": value, "unit": definition["unit"],
                              "source_ref": raw_ref if value is not None else None,
                              "type": definition["data_class"] if value is not None else "unknown",
                              "missing_reason": None if value is not None else
                              missing_reason if metric_id in values else "not_collected_by_git_scope_collector"}
    unknown = [name for name in values if values[name] is None]
    return {"schema_version": VERSION, "collected_at": utc_now(),
            "dictionary_version": DICTIONARY_VERSION,
            "baseline_commit": baseline, "scope_paths": scope,
            "collection_status": status, "deadline_ms": int(MAX_TOTAL_SECONDS * 1000),
            "elapsed_ms": int((time.monotonic() - started) * 1000),
            "completed_sources": completed, "missing_reason": missing_reason,
            "changed_files": values["changed_files"], "changed_lines": values["changed_lines"],
            "changed_modules": values["changed_modules"],
            "module_map_quality": values["module_map_quality"],
            "contract_categories_hit": values["contract_categories_hit"],
            "state_path_hits": values["state_path_hits"],
            "observed_tracked_files": observed_tracked_files,
            "observed_tracked_lines": observed_tracked_lines,
            "metrics": metrics,
            "metric_class": "measured_git_scope" if status == "COMPLETE" else "unknown_or_partial_git_scope",
            "rule_version": VERSION, "source_ref": raw_ref,
            "unknown_fields": unknown,
            "interpretation": "scope signal only; neither task difficulty nor defect proof"}
