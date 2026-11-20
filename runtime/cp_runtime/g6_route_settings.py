"""中文：新任务策略选择、旧根保留和降级预检。
English: Project-scoped policy selection, retained roots, and reader rollback inspection.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Mapping

from . import g6_catalog as catalogs, revision_pages as pages
from .capability_gate import _read, _write, worktree_key
from .capability_store import bounded_read, registered_account_file, safe_path
from .common import require_external_state, resolve_codex_home, utc_now
from .event_v2 import OwnerTokenLock, _repo_identity_source, project_identity_for
from .g6_journal_versions import READABLE
from .routing_contract import exact, fail, ref

MAX_CHANGES = 256


def _selection(repo: Path) -> tuple[Path, Path]:
    root, _ = _repo_identity_source(str(repo))
    root = root.resolve()
    path = safe_path(
        resolve_codex_home() / "cp-assistant" / "catalog-defaults" / (worktree_key(root) + ".json")
    )
    require_external_state(path, root)
    return path, root


def _binding(root: Path) -> dict:
    fingerprint, project = project_identity_for(str(root))
    return {"project_id": project, "repo_fingerprint": fingerprint}


def _read_changes(path: Path, root: Path, binding: dict) -> pages.Page:
    if not path.exists():
        return pages.Page([])
    data = _read(path, 262144)
    fields = {"schema_version", "project", "worktree", "changes", "integrity"}
    exact(data, fields | ({"page"} if "page" in data else set()), "CATALOG_DEFAULT_STORE")
    changes = data["changes"]
    if (
        data["schema_version"] != "desktop-catalog-selection/1"
        or data["project"] != binding
        or data["worktree"] != worktree_key(root)
        or not isinstance(changes, list)
        or len(changes) > MAX_CHANGES
    ):
        fail("CATALOG_DEFAULT_BINDING")
    page = pages.decode(data, "changes")
    previous = catalogs.LEGACY
    if page.start:
        archive = pages.read_previous(path, page.start, page.previous, 262144)
        prior = pages.decode(archive, "changes")
        if (
            not prior.rows
            or prior.revision != page.start
            or archive["project"] != binding
            or archive["worktree"] != worktree_key(root)
            or page.baseline != prior.rows[-1]["to"]
        ):
            fail("CATALOG_ARCHIVE_BINDING")
        previous = page.baseline
    for index, row in enumerate(changes, page.start):
        exact(row, {"revision", "from", "to", "at", "request_ref"}, "CATALOG_CHANGE")
        if (
            row["revision"] != index
            or row["from"] != previous
            or row["request_ref"] != ref([binding, worktree_key(root), index, previous, row["to"]])
        ):
            fail("CATALOG_CHANGE_CHAIN")
        catalogs.policy_id(row["to"])
        previous = row["to"]
    return page


def selected_digest(repo: Path, project: Mapping | None = None) -> str:
    if not (resolve_codex_home() / "cp-assistant/catalog-defaults").is_dir():
        return catalogs.LEGACY
    path, root = _selection(repo)
    if not path.exists():
        return catalogs.LEGACY
    page = _read_changes(path, root, dict(project) if project else _binding(root))
    return page.rows[-1]["to"] if page.rows else (page.baseline or catalogs.LEGACY)


def selection(
    repo: Path,
    mode: str,
    target: str | None = None,
    revision: int | None = None,
    confirmation: str | None = None,
) -> dict:
    path, root = _selection(repo)
    project = _binding(root)
    page = _read_changes(path, root, project)
    previous = page.rows[-1]["to"] if page.rows else (page.baseline or catalogs.LEGACY)
    base = {
        "revision": page.revision,
        "project": project,
        "current_policy": catalogs.policy_id(previous),
        "current_digest": previous,
        "scope": "new-project-roots",
        "execution_authorization": "NONE",
    }
    if mode == "show":
        return {
            **base,
            "readers": [catalogs.LEGACY_ID, *(r["policy_id"] for r in catalogs.entries())],
            "journal_versions": list(READABLE),
        }
    if mode not in {"preview", "apply"} or target is None or type(revision) is not int or revision < 0:
        fail("CATALOG_SELECTION_ARGUMENTS")
    proposed = catalogs.digest_for(target)
    if mode == "apply":
        with OwnerTokenLock(path, timeout=2):
            page = _read_changes(path, root, project)
            prior = (
                pages.old_row(path, page, revision, "changes", 262144) if revision < page.revision else None
            )
            if prior and prior["request_ref"] == confirmation and prior["to"] == proposed:
                return {"idempotent": True, "revision": page.revision, "active_digest": page.rows[-1]["to"]}
            previous = page.rows[-1]["to"] if page.rows else (page.baseline or catalogs.LEGACY)
            key = ref([project, worktree_key(root), revision, previous, proposed])
            if revision != page.revision or key != confirmation:
                fail("CATALOG_SELECTION_STALE")
            if proposed != catalogs.LEGACY:
                from .g6_runtime_support import installed_task_scope_support

                if not installed_task_scope_support()["supported"]:
                    fail("CATALOG_MATCHING_INSTALLED_READER_REQUIRED")
            if len(page.rows) >= MAX_CHANGES:
                page = pages.roll(path, page, previous, utc_now(), 262144)
            if _binding(root) != project:
                fail("CATALOG_SELECTION_LIMIT_OR_BINDING")
            page.rows.append(
                {"revision": revision, "from": previous, "to": proposed, "at": utc_now(), "request_ref": key}
            )
            _write(
                path,
                {
                    "schema_version": "desktop-catalog-selection/1",
                    "project": project,
                    "worktree": worktree_key(root),
                    "changes": page.rows,
                    **page.header(),
                },
                262144,
            )
            return {
                "revision": page.revision,
                "active_digest": proposed,
                "idempotent": False,
                "scope": "new-project-roots",
            }
    if revision != page.revision:
        fail("CATALOG_SELECTION_STALE")
    return {
        **base,
        "proposed_policy": target,
        "proposed_digest": proposed,
        "request_ref": ref([project, worktree_key(root), revision, previous, proposed]),
        "next_action": "apply_exact_preview",
    }


def registered_ledger_path(path: Path, account: Path | None = None) -> Path:
    """中文：仅展开同一账户根的历史别名，仍逐级核验账本路径。
    English: Resolve a proven account-root alias and keep strict checks below the root.
    """
    if not path.is_absolute() or ".." in path.parts:
        fail("CATALOG_ROLLBACK_ROOT_BINDING")
    return registered_account_file(path, account if account is not None else resolve_codex_home())


def registered_ledgers(repo: Path, project: dict) -> list[Path]:
    """中文：只读本项目登记的历史和在途根。 English: Include registered legacy and late-settlement roots."""
    folder = safe_path(resolve_codex_home() / "cp-assistant/g6-routing")
    if not folder.exists():
        return []
    result = set()
    for i, pointer in enumerate(folder.glob("session-*.json")):
        if i >= 4096:
            fail("CATALOG_ROLLBACK_INVENTORY_LIMIT")
        record = _read(safe_path(pointer), 524288)
        if record.get("project_identity") != project or Path(record.get("repo_path", "")).resolve() != repo:
            continue
        if record.get("schema_version") == "g6-session-routing-handoff/1":
            result.add(registered_ledger_path(Path(record["new_ledger_path"]), resolve_codex_home()))
        elif record.get("schema_version") == "g6-task-routing/1":
            for entry in record["scopes"].values():
                if entry["identity"] != project or Path(entry["repo_path"]).resolve() != repo:
                    fail("CATALOG_ROLLBACK_ROOT_BINDING")
                result.add(registered_ledger_path(Path(entry["ledger_path"]), resolve_codex_home()))
        else:
            fail("CATALOG_UNKNOWN_ROUTING_POINTER")
    return sorted(result)


def reader_contract(target_manifest: Path) -> dict:
    manifest_path = safe_path(target_manifest)
    manifest = json.loads(bounded_read(manifest_path, 1_048_576))
    if manifest.get("package") != "codex-cross-project-engineering-assistant":
        fail("CATALOG_ROLLBACK_TARGET")
    target = manifest.get("desktop_g6_default_v1", {})
    versions = set(target.get("readable_budget_schema_versions", []))
    digests = set()
    source = manifest_path.parent / "runtime/cp_runtime/data/desktop-g6-flexible-policy-v1.json"
    if target.get("policy_id") == catalogs.LEGACY_ID and source.is_file():
        import hashlib

        digests.add("sha256:" + hashlib.sha256(bounded_read(safe_path(source), 262144)).hexdigest())
    reader = manifest.get("desktop_catalog_reader")
    if reader and reader.get("algorithm") == "role-cost-v2":
        index = manifest_path.parent / "runtime/cp_runtime/data/desktop-policy-readers.json"
        rows = json.loads(bounded_read(safe_path(index), 262144)).get("policies", [])
        for item in rows:
            import hashlib
            import re

            name = item["file"]
            if not re.fullmatch(r"desktop-model-catalog-[a-z0-9-]+\.json", name):
                fail("CATALOG_ROLLBACK_TARGET")
            actual = hashlib.sha256(bounded_read(safe_path(index.parent / name), 262144)).hexdigest()
            if actual != item["sha256"]:
                fail("CATALOG_ROLLBACK_TARGET_DIGEST")
            digests.add("sha256:" + actual)
    return {"policy_digests": sorted(digests), "journal_versions": sorted(versions)}


def check_replacement(account: Path, target: dict | None) -> None:
    """中文：替换账户读取器前逐根检查，保留未结调用及未完成任务。
    English: Check each registered root before replacing an account reader.
    """
    from . import g6_budget_v1 as budget

    folder = safe_path(account / "cp-assistant/g6-routing")
    if not folder.is_dir():
        return
    supported = set((target or {}).get("policy_digests", []))
    versions = set((target or {}).get("journal_versions", []))
    roots = {}
    for i, path in enumerate(folder.glob("session-*.json")):
        if i >= 4096:
            fail("CATALOG_ROLLBACK_INVENTORY_LIMIT")
        record = _read(safe_path(path), 524288)
        if record["schema_version"] == "g6-task-routing/1":
            for row in record["scopes"].values():
                roots[Path(row["ledger_path"])] = (
                    row["identity"],
                    row["repo_path"],
                    row["status"] == "ACTIVE",
                )
        elif record["schema_version"] == "g6-session-routing-handoff/1":
            roots[Path(record["new_ledger_path"])] = (record["project_identity"], record["repo_path"], False)
        else:
            fail("CATALOG_UNKNOWN_ROUTING_POINTER")
    for recorded_path, (project, repo, active) in roots.items():
        path = registered_ledger_path(recorded_path, account)
        require_external_state(path, Path(repo))
        with OwnerTokenLock(path, timeout=2):
            events = budget._read_events(path)
            state = budget.replay(events)
        root = state["root"]
        if root["identity"] != project or Path(root["repo_path"]).resolve() != Path(repo).resolve():
            fail("CATALOG_ROLLBACK_ROOT_BINDING")
        if root["policy_digest"] in supported and all(e["schema_version"] in versions for e in events):
            continue
        usage = budget.snapshot(state, work_item_id="reader-replacement", depth=0)
        if active or usage["active_calls"] or usage["future_required_hold_units"]:
            fail("CATALOG_RETAIN_READER_FOR_ACTIVE_ROOT")


def rollback_check(repo: Path, target_manifest: Path, ledgers: list[Path] | None = None) -> dict:
    from . import g6_budget_v1 as budget

    _, root = _selection(repo)
    project = _binding(root)
    target = reader_contract(target_manifest)
    digests = set(target["policy_digests"])
    versions = set(target["journal_versions"])
    paths = set(registered_ledgers(root, project))
    paths.update(safe_path(p) for p in (ledgers or []))
    results = []
    for path in sorted(paths):
        require_external_state(path, root)
        with OwnerTokenLock(path, timeout=2):
            events = budget._read_events(path)
            state = budget.replay(events)
        record = state["root"]
        if record["identity"] != project or Path(record["repo_path"]).resolve() != root:
            fail("CATALOG_ROLLBACK_ROOT_BINDING")
        formats = sorted({e["schema_version"] for e in events})
        compatible = record["policy_digest"] in digests and set(formats) <= versions
        results.append(
            {
                "root_ref": ref(str(path)),
                "policy_digest": record["policy_digest"],
                "formats": formats,
                "inflight": budget.snapshot(state, work_item_id="rollback-check", depth=0)["active_calls"],
                "readable": compatible,
            }
        )
    return {
        "safe_to_replace_reader": all(r["readable"] for r in results),
        "roots": results,
        "scope": "registered-project-roots",
        "next_action": "reader_compatible"
        if all(r["readable"] for r in results)
        else "restore_new_task_default_and_retain_current_reader",
        "execution_authorization": "NONE",
    }


def add_commands(sub):
    cmd = sub.add_parser("routing-policy")
    cmd.add_argument(
        "mode", choices=("show", "preview", "apply", "rollback-check", "refresh-capabilities", "compare")
    )
    cmd.add_argument("--repo-path", required=True)
    cmd.add_argument("--policy-id")
    cmd.add_argument("--revision", type=int)
    cmd.add_argument("--confirm")
    cmd.add_argument("--session-id")
    cmd.add_argument("--target-manifest", type=Path)
    cmd.add_argument("--ledger", type=Path, action="append")
    cmd.add_argument("--evidence", type=Path, action="append")
    cmd.add_argument(
        "--save-timing",
        action="store_true",
        help="Store only sufficiently sampled, comparable, parent-adjudicated timing cohorts.",
    )
    cmd.add_argument("--project-profile", type=Path)

    def run(args):
        if args.mode == "compare":
            from .g6_routing_study import compare

            if not args.policy_id:
                fail("CATALOG_POLICY_REQUIRED")
            result = compare(
                args.repo_path,
                args.policy_id,
                args.ledger,
                evidence=args.evidence,
                profile=args.project_profile,
                save_timing=args.save_timing,
            )
        elif args.mode == "refresh-capabilities":
            from .g6_capability_source import refresh

            if not args.session_id:
                fail("CAPABILITY_SESSION_REQUIRED")
            result = refresh(Path(args.repo_path).resolve(), args.session_id)
        elif args.mode == "rollback-check":
            if not args.target_manifest:
                fail("CATALOG_ROLLBACK_TARGET_REQUIRED")
            result = rollback_check(Path(args.repo_path), args.target_manifest, args.ledger)
        else:
            result = selection(Path(args.repo_path), args.mode, args.policy_id, args.revision, args.confirm)
        print(json.dumps(result, ensure_ascii=False, indent=2))

    cmd.set_defaults(func=run)
