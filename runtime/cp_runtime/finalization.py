"""Accepted-final-state readback and claim verification."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional

from .common import (
    RuntimeContractError,
    atomic_write_json,
    atomic_write_text,
    read_json,
    repo_snapshot,
    require_external_state,
    utc_now,
)
from .contracts import FinalizationSurface

SCHEMA = 1
SURFACES = ("modified", "validated", "reviewed", "committed", "pushed", "deployed", "restarted", "effective")


def _current_evidence(group: Mapping[str, Any], current_sha: str) -> List[str]:
    valid: List[str] = []
    for name, item in group.items():
        fingerprint = item.get("fingerprint") or item.get("baseline") or {}
        if item.get("status") == "valid" and fingerprint.get("sha256") == current_sha:
            valid.append(name)
    return valid


def _action_supported(state: Dict[str, Any], name: str, current_sha: str) -> Optional[str]:
    action = (state.get("actions") or {}).get(name)
    if not isinstance(action, dict):
        return None
    fingerprint = action.get("fingerprint") or {}
    if action.get("status") not in {"success", "confirmed", "valid"}:
        return None
    if fingerprint.get("sha256") and fingerprint.get("sha256") != current_sha:
        return None
    return str(action.get("evidence") or action.get("summary") or "execution-state action")


def derive_surfaces(state: Dict[str, Any], repo_path: Path) -> Dict[str, FinalizationSurface]:
    current = repo_snapshot(repo_path)
    baseline = state.get("baseline_fingerprint") or state.get("initial_repo_fingerprint") or state.get("repo_fingerprint") or {}
    baseline_head = baseline.get("head")
    baseline_sha = baseline.get("sha256")
    validations = _current_evidence((state.get("evidence") or {}).get("validations", {}), current["sha256"])
    reviews = _current_evidence((state.get("evidence") or {}).get("reviews", {}), current["sha256"])
    actions = state.get("actions") or {}
    result: Dict[str, FinalizationSurface] = {}
    result["modified"] = FinalizationSurface(
        "modified", bool(baseline_sha and current["sha256"] != baseline_sha),
        "workspace-changed" if baseline_sha and current["sha256"] != baseline_sha else "not-confirmed",
        current["sha256"],
    )
    result["validated"] = FinalizationSurface(
        "validated", bool(validations), "current-evidence" if validations else "not-confirmed", ",".join(validations) or None,
    )
    result["reviewed"] = FinalizationSurface(
        "reviewed", bool(reviews), "current-evidence" if reviews else "not-confirmed", ",".join(reviews) or None,
    )
    committed = bool(baseline_head and current["head"] != baseline_head)
    result["committed"] = FinalizationSurface(
        "committed", committed, "head-advanced" if committed else "not-confirmed", current["head"] if committed else None,
    )
    pushed_evidence = _action_supported(state, "pushed", current["sha256"])
    result["pushed"] = FinalizationSurface(
        "pushed", bool(pushed_evidence), "explicit-readback-evidence" if pushed_evidence else "not-confirmed", pushed_evidence,
    )
    for name in ("deployed", "restarted", "effective"):
        evidence = _action_supported(state, name, current["sha256"])
        result[name] = FinalizationSurface(
            name, bool(evidence), "explicit-readback-evidence" if evidence else "not-confirmed", evidence,
        )
    return result


def build_finalization_report(
    execution_state_path: Path,
    repo_path: Path,
    claims: Iterable[str],
    output_json: Path,
    output_markdown: Optional[Path] = None,
) -> Dict[str, Any]:
    state = read_json(execution_state_path)
    current = repo_snapshot(repo_path)
    state_repo = str(state.get("repo_path") or "").strip()
    if not state_repo:
        raise RuntimeContractError("execution-state 缺少 repo_path")
    if Path(state_repo).expanduser().resolve() != Path(current["repo_path"]).resolve():
        raise RuntimeContractError("execution-state 与 Finalization 仓库不一致")
    require_external_state(output_json.expanduser().resolve(), Path(current["repo_path"]))
    if output_markdown is not None:
        require_external_state(output_markdown.expanduser().resolve(), Path(current["repo_path"]))
    surfaces = derive_surfaces(state, repo_path)
    normalized_claims = sorted({item.strip().lower() for item in claims if item.strip()})
    invalid = sorted(set(normalized_claims) - set(SURFACES))
    if invalid:
        raise RuntimeContractError("未知 Finalization claim: " + ",".join(invalid))
    unsupported = [name for name in normalized_claims if not surfaces[name].supported]
    report: Dict[str, Any] = {
        "schema_version": SCHEMA,
        "task_id": state.get("task_id", ""),
        "project_id": (state.get("project") or {}).get("project_id", ""),
        "accepted_final_state": {
            "claims": normalized_claims,
            "unsupported_claims": unsupported,
        },
        "readback": {
            "repo": current,
            "surfaces": {
                name: {
                    "supported": surface.supported,
                    "status": surface.status,
                    "evidence": surface.evidence,
                }
                for name, surface in surfaces.items()
            },
        },
        "result": "PASS" if not unsupported else "BLOCKED",
        "generated_at": utc_now(),
        "limitations": [
            "本检查器不会执行 commit/push/deploy/restart 或生产操作",
            "Push 只有显式动作读回证据才能标记为已确认，本地 upstream ref 不能替代远端读回",
            "未记录 readback evidence 的外部动作必须保持 not-confirmed",
        ],
    }
    sealed = atomic_write_json(output_json, report, seal=True)
    if output_markdown:
        lines = [
            "# Finalization Integrity Report",
            "",
            f"- Task ID：`{sealed.get('task_id', '')}`",
            f"- Project ID：`{sealed.get('project_id', '')}`",
            f"- Result：`{sealed['result']}`",
            f"- Generated at：`{sealed['generated_at']}`",
            "",
            "## Claims",
            "",
        ]
        for claim in normalized_claims:
            surface = sealed["readback"]["surfaces"][claim]
            lines.append(f"- `{claim}`：`{surface['status']}`；Evidence：{surface.get('evidence') or 'NOT_CAPTURED'}")
        if unsupported:
            lines.extend(["", "## Blockers", "", *["- Unsupported claim: `" + item + "`" for item in unsupported]])
        lines.extend(["", "## Limitations", "", *["- " + item for item in sealed["limitations"]], ""])
        atomic_write_text(output_markdown, "\n".join(lines))
    return sealed
