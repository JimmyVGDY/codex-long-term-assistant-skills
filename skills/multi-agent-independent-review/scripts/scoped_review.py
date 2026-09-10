#!/usr/bin/env python3
"""中文：范围审查的目标/依赖/配置指纹伴随清单。 English: Target/dependency/config fingerprint companion for scoped review."""
from __future__ import annotations

import argparse
import ast
import hashlib
import json
import os
import stat
import subprocess
from pathlib import Path, PurePosixPath
from typing import Any

SCHEMA = "scoped-review/1"
MAX_FILES = 256
MAX_FILE_BYTES = 4 * 1024 * 1024


class ScopeError(RuntimeError):
    pass


def canonical(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def fail(code: str) -> None:
    raise ScopeError(code)


def repo_root(value: str) -> Path:
    path = Path(value).expanduser().resolve()
    result = subprocess.run(["git", "rev-parse", "--show-toplevel"], cwd=path, capture_output=True, text=True)
    if result.returncode:
        fail("NOT_GIT_REPOSITORY")
    root = Path(result.stdout.strip()).resolve()
    if root != path:
        fail("REPOSITORY_ROOT_REQUIRED")
    return root


def normalized(repo: Path, value: str) -> tuple[str, Path]:
    if not isinstance(value, str) or not value or "\\" in value or ":" in value:
        fail("SCOPE_PATH_INVALID")
    pure = PurePosixPath(value)
    if pure.is_absolute() or any(part in {"", ".", ".."} for part in pure.parts):
        fail("SCOPE_PATH_INVALID")
    path = repo.joinpath(*pure.parts)
    try:
        path.resolve().relative_to(repo)
    except ValueError:
        fail("SCOPE_PATH_ESCAPE")
    for item in (path, *path.parents):
        if item == repo.parent:
            break
        try:
            info = item.lstat()
        except FileNotFoundError:
            continue
        if stat.S_ISLNK(info.st_mode) or getattr(info, "st_file_attributes", 0) & 0x400:
            fail("SCOPE_LINK_REJECTED")
    return pure.as_posix(), path


def fingerprint(path: Path) -> dict[str, Any]:
    try:
        info = path.stat()
    except OSError:
        fail("SCOPE_PATH_MISSING")
    if not path.is_file() or info.st_size > MAX_FILE_BYTES:
        fail("SCOPE_FILE_UNSUPPORTED")
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    return {"sha256": digest, "size": info.st_size, "hash_mode": "full"}


def resolve_module(repo: Path, source: Path, module: str, level: int, aliases: list[str]) -> list[str]:
    if level:
        base = source.parent
        for _ in range(level - 1):
            base = base.parent
        parts = [part for part in module.split(".") if part]
        candidates = [base.joinpath(*parts)] if parts else [base]
        if not parts:
            candidates.extend(base / alias for alias in aliases)
    else:
        parts = [part for part in module.split(".") if part]
        candidates = [repo.joinpath(*parts)] if parts else []
    resolved = []
    for candidate in candidates:
        for path in (candidate.with_suffix(".py"), candidate / "__init__.py"):
            if path.is_file():
                try:
                    resolved.append(path.resolve().relative_to(repo).as_posix())
                except ValueError:
                    fail("SCOPE_PATH_ESCAPE")
                break
    return resolved


def discover_python(repo: Path, seeds: list[str]) -> tuple[list[str], list[str]]:
    pending = list(seeds)
    discovered: set[str] = set()
    unknown: set[str] = set()
    visited: set[str] = set()
    while pending:
        relative = pending.pop(0)
        if relative in visited or not relative.endswith(".py"):
            continue
        visited.add(relative)
        if len(visited) > MAX_FILES:
            fail("SCOPE_CLOSURE_LIMIT")
        _, source = normalized(repo, relative)
        try:
            tree = ast.parse(source.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, SyntaxError):
            unknown.add("unreadable-or-unparseable:" + relative)
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                name = getattr(node.func, "id", "") or getattr(node.func, "attr", "")
                if name in {"__import__", "import_module"}:
                    unknown.add("dynamic-import:" + relative)
            modules: list[str] = []
            if isinstance(node, ast.Import):
                for alias in node.names:
                    modules.extend(resolve_module(repo, source, alias.name, 0, []))
            elif isinstance(node, ast.ImportFrom):
                modules.extend(resolve_module(repo, source, node.module or "", node.level,
                                              [alias.name for alias in node.names]))
                if node.level and not modules:
                    unknown.add("unresolved-relative-import:" + relative + ":" + (node.module or ""))
            for dependency in modules:
                if dependency not in seeds and dependency not in discovered:
                    discovered.add(dependency)
                    pending.append(dependency)
    return sorted(discovered), sorted(unknown)


def create(args) -> dict[str, Any]:
    repo = repo_root(args.repo_path)
    categories = {"target": args.target or [], "dependency": args.dependency or [],
                  "config": args.config or [], "authority": args.authority or []}
    if not categories["target"]:
        fail("SCOPE_TARGET_REQUIRED")
    supplied: dict[str, str] = {}
    for category, values in categories.items():
        for value in values:
            relative, path = normalized(repo, value)
            if relative in supplied:
                fail("SCOPE_DUPLICATE_PATH")
            fingerprint(path)
            supplied[relative] = category
    discovered, unknown = discover_python(repo, list(supplied))
    for value in args.unknown_dependency or []:
        unknown.append("caller-declared:" + value[:160])
    entries = []
    for relative in sorted(set(supplied) | set(discovered)):
        _, path = normalized(repo, relative)
        entries.append({"path": relative, "category": supplied.get(relative, "discovered-dependency"),
                        **fingerprint(path)})
    head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=repo, check=True, capture_output=True, text=True).stdout.strip()
    manifest = {"schema_version": SCHEMA, "head_commit": head, "release_scope": False,
                "entries": entries, "unknown_dependencies": sorted(set(unknown)),
                "closure_complete": not unknown}
    manifest["integrity"] = {"algorithm": "sha256", "sha256": hashlib.sha256(canonical(manifest)).hexdigest()}
    output = Path(args.output).expanduser().resolve()
    try:
        output.relative_to(repo)
        fail("SCOPE_OUTPUT_INSIDE_REPOSITORY")
    except ValueError:
        pass
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return manifest


def load(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        fail("SCOPE_MANIFEST_INVALID")
    integrity = value.pop("integrity", None)
    if not isinstance(integrity, dict) or integrity.get("algorithm") != "sha256" \
            or integrity.get("sha256") != hashlib.sha256(canonical(value)).hexdigest():
        fail("SCOPE_MANIFEST_INTEGRITY")
    value["integrity"] = integrity
    if value.get("schema_version") != SCHEMA or not isinstance(value.get("entries"), list):
        fail("SCOPE_MANIFEST_SCHEMA")
    return value


def freshness(args) -> dict[str, Any]:
    repo = repo_root(args.repo_path)
    manifest = load(Path(args.manifest).expanduser().resolve())
    stale = []
    scoped = set()
    for entry in manifest["entries"]:
        relative, path = normalized(repo, entry["path"])
        scoped.add(relative)
        try:
            current = fingerprint(path)
        except ScopeError:
            stale.append(relative + ":missing")
            continue
        if current["sha256"] != entry["sha256"] or current["size"] != entry["size"]:
            stale.append(relative + ":changed")
    changed = set()
    if manifest["head_commit"] != subprocess.run(["git", "rev-parse", "HEAD"], cwd=repo, check=True,
                                                   capture_output=True, text=True).stdout.strip():
        changed.update(subprocess.run(["git", "diff", "--name-only", manifest["head_commit"], "HEAD", "--"],
                                      cwd=repo, check=True, capture_output=True, text=True).stdout.splitlines())
    status = subprocess.run(["git", "status", "--porcelain=v1", "--untracked-files=all"], cwd=repo, check=True,
                            capture_output=True, text=True).stdout.splitlines()
    changed.update(line[3:].strip().replace("\\", "/") for line in status if len(line) > 3)
    warnings = sorted(path for path in changed if path not in scoped)
    if stale:
        return {"status": "STALE", "stale": sorted(stale), "warnings": warnings, "release_scope": False}
    if manifest["unknown_dependencies"]:
        return {"status": "INCOMPLETE", "stale": [], "unknown_dependencies": manifest["unknown_dependencies"],
                "warnings": warnings, "release_scope": False}
    return {"status": "FRESH", "stale": [], "warnings": warnings, "release_scope": False}


def main() -> None:
    parser = argparse.ArgumentParser(description="Scoped review companion manifest")
    sub = parser.add_subparsers(dest="command", required=True)
    item = sub.add_parser("create")
    item.add_argument("--repo-path", required=True); item.add_argument("--output", required=True)
    for name in ("target", "dependency", "config", "authority", "unknown-dependency"):
        item.add_argument("--" + name, action="append")
    item = sub.add_parser("validate"); item.add_argument("--manifest", required=True)
    item = sub.add_parser("freshness"); item.add_argument("--repo-path", required=True); item.add_argument("--manifest", required=True)
    args = parser.parse_args()
    try:
        if args.command == "create":
            result = create(args)
        elif args.command == "validate":
            result = {"status": "VALID", "manifest": load(Path(args.manifest).expanduser().resolve())}
        else:
            result = freshness(args)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        if result.get("status") == "STALE":
            raise SystemExit(2)
        if result.get("status") == "INCOMPLETE":
            raise SystemExit(3)
    except ScopeError as exc:
        print("[FAIL] " + str(exc), file=os.sys.stderr)
        raise SystemExit(1)


if __name__ == "__main__":
    main()
