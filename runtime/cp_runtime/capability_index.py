"""中文：有界能力发现、使用前核实和显式生命周期维护。 English: Bounded capability discovery, pre-use verification, and explicit lifecycle maintenance."""
from __future__ import annotations

import ast
import copy
import hashlib
import os
import re
import subprocess
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .atomic_io import native_path
from .capability_store import (
    MAX_ENTRIES, CapabilityError, CapabilityStore, bounded_read, empty_payload,
    integer, relative_path, require, safe_path, text_field, validate_payload,
)
from .common import utc_now

MAX_PATHS = 2000
MAX_READS = 128
MAX_READ_BYTES = 2 * 1024 * 1024
MAX_FILE_BYTES = 128 * 1024
SOURCE_SUFFIXES = {".py", ".js", ".jsx", ".mjs", ".cjs", ".ts", ".tsx"}
EXCLUDED_DIRS = {"node_modules", "__pycache__", ".venv", "venv", "dist", "build", "vendor", ".next", "generated", "coverage", ".agents", ".codex"}
CONTEXT_NAMES = ("package.json", "pyproject.toml", "requirements.txt", "package-lock.json", "pnpm-lock.yaml", "yarn.lock", "uv.lock", "poetry.lock", "tsconfig.json")


def git_baseline(repo: Path) -> dict[str, str]:
    values = []
    for args in (["rev-parse", "--verify", "HEAD"], ["symbolic-ref", "--quiet", "--short", "HEAD"]):
        try:
            result = subprocess.run(["git", "--no-optional-locks", *args], cwd=repo,
                                    capture_output=True, timeout=5, check=False)
        except (OSError, subprocess.TimeoutExpired):
            raise CapabilityError("GIT_UNAVAILABLE") from None
        require(result.returncode in {0, 1, 128}, "GIT_UNAVAILABLE")
        value = result.stdout.decode("utf-8", errors="strict").strip() if result.returncode == 0 else ""
        require(len(value) <= 256, "INVALID_GIT_BASELINE")
        values.append(value)
    require(bool(values[0] or values[1]), "GIT_UNAVAILABLE")
    return {"head": values[0], "branch": values[1]}


def source_path(repo: Path, relative: str) -> Path:
    relative_path(relative)
    result = safe_path(repo / relative)
    require(result.is_relative_to(repo), "PATH_ESCAPE")
    return result


@dataclass
class ReadBudget:
    repo: Path
    reads: int = 0
    bytes_read: int = 0
    observed: dict[str, bytes] = field(default_factory=dict)
    context_probes: dict[str, bool] = field(default_factory=dict)
    context_probe_count: int = 0

    def __post_init__(self) -> None:
        """中文：拒绝链接后统一根路径，使短路径别名共享同一预算身份。

        English: Reject links before normalizing the root so short aliases share one budget identity.
        """
        self.repo = safe_path(self.repo)

    def context_exists(self, relative: str) -> bool:
        if relative not in self.context_probes:
            require(self.context_probe_count + len(self.context_probes) + 2 <= MAX_PATHS, "BUDGET")
            self.context_probes[relative] = source_path(self.repo, relative).exists()
            self.context_probe_count += 1
        return self.context_probes[relative]

    def read(self, relative: str) -> bytes:
        if relative in self.observed:
            return self.observed[relative]
        path = source_path(self.repo, relative)
        try:
            size = path.stat().st_size
        except FileNotFoundError:
            raise CapabilityError("MISSING") from None
        except OSError:
            raise CapabilityError("UNREADABLE") from None
        require(size <= MAX_FILE_BYTES, "TOO_LARGE")
        # 中文：每次首次读取同时预留结束核对的完整读取，实际计数仍分开报告。 English: Reserve a full final verification read for each initial read; report actual counts separately.
        require(self.reads + len(self.observed) + 2 <= MAX_READS
                and self.bytes_read + sum(map(len, self.observed.values())) + 2 * size <= MAX_READ_BYTES, "BUDGET")
        raw = bounded_read(path, MAX_FILE_BYTES)
        self.reads += 1
        self.bytes_read += len(raw)
        require(self.bytes_read + sum(map(len, self.observed.values())) + len(raw) <= MAX_READ_BYTES, "CHANGED")
        self.observed[relative] = raw
        return raw

    def verify(self) -> None:
        require(self.reads + len(self.observed) <= MAX_READS
                and self.bytes_read + sum(map(len, self.observed.values())) <= MAX_READ_BYTES
                and self.context_probe_count + len(self.context_probes) <= MAX_PATHS, "BUDGET")
        for relative, previous in self.observed.items():
            remaining = MAX_READ_BYTES - self.bytes_read
            require(self.reads < MAX_READS, "BUDGET")
            raw = bounded_read(source_path(self.repo, relative), min(MAX_FILE_BYTES, remaining))
            self.reads += 1
            self.bytes_read += len(raw)
            require(raw == previous, "CHANGED")
        # 中文：缺失也是观察结果；防止扫描中途新增配置未被结束核对发现。 English: Absence is also an observation; final checks detect configuration created during scanning.
        for relative, existed in self.context_probes.items():
            self.context_probe_count += 1
            require(source_path(self.repo, relative).exists() == existed, "CHANGED")

    def digest(self, relative: str) -> str:
        return hashlib.sha256(self.read(relative)).hexdigest()


def public_symbols(relative: str, raw: bytes) -> list[tuple[str, str]]:
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeError:
        raise CapabilityError("UNSUPPORTED") from None
    text_field(text, MAX_FILE_BYTES)
    suffix = Path(relative).suffix.lower()
    if suffix == ".py":
        try:
            tree = ast.parse(text)
        except (SyntaxError, ValueError, RecursionError):
            raise CapabilityError("PARSE_ERROR") from None
        definitions = {node.name: "class" if isinstance(node, ast.ClassDef) else "function"
                       for node in tree.body if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))}
        exported = None
        for node in tree.body:
            if isinstance(node, ast.Assign) and any(isinstance(target, ast.Name) and target.id == "__all__" for target in node.targets):
                try:
                    exported = ast.literal_eval(node.value)
                except (ValueError, TypeError, RecursionError):
                    raise CapabilityError("UNSUPPORTED") from None
                require(isinstance(exported, (tuple, list)) and all(isinstance(name, str) and name.isidentifier() for name in exported), "UNSUPPORTED")
        names = exported if exported is not None else [name for name in definitions if not name.startswith("_")]
        return sorted({(name, definitions.get(name, "module")) for name in names})
    if suffix not in SOURCE_SUFFIXES:
        raise CapabilityError("UNSUPPORTED")
    # 中文：文本识别只生成候选；先屏蔽注释和字符串，保留换行及非字符串代码。 English: Text recognition only generates candidates; mask comments and strings while retaining newlines and code.
    masked = re.sub(r"//[^\n]*|/\*[\s\S]*?\*/|'(?:\\.|[^'\\])*'|\"(?:\\.|[^\"\\])*\"|`(?:\\.|[^`\\])*`",
                    lambda m: re.sub(r"[^\n]", " ", m.group()), text)
    matches = re.findall(r"\bexport\s+(?:default\s+)?(?:async\s+)?(function|class|const|let|var|interface|type|enum)\s+([A-Za-z_$][\w$]*)", masked)
    found = [(name, "class" if kind == "class" else "function" if kind == "function" else "component" if name[:1].isupper() and suffix in {".jsx", ".tsx"} else "module") for kind, name in matches]
    for group in re.findall(r"\bexport\s*\{([^}]+)\}", masked):
        for part in group.split(","):
            match = re.fullmatch(r"\s*(?:type\s+)?([A-Za-z_$][\w$]*)(?:\s+as\s+([A-Za-z_$][\w$]*))?\s*", part)
            if match:
                found.append((match.group(2) or match.group(1), "module"))
    if re.search(r"\bexport\s+default\b", masked) and not re.search(r"\bexport\s+default\s+(?:async\s+)?(?:function|class)\s+[A-Za-z_$]", masked):
        found.append(("default", "module"))
    if re.search(r"\bexport\s*\*", masked):
        found.append(("*", "module"))
    found.extend((name, "module") for name in re.findall(r"\bexports\.([A-Za-z_$][\w$]*)\s*=", masked))
    if re.search(r"\bmodule\.exports\s*=", masked):
        found.append(("module.exports", "module"))
    require(bool(found) or not re.search(r"\bexport\b", masked), "UNSUPPORTED")
    return sorted(set(found))


def _entry(path: str, symbol: str, kind: str, digest: str) -> dict[str, Any]:
    return {"id": "cap-" + uuid.uuid4().hex, "kind": kind, "path": path, "symbol": symbol,
            "summary": "", "keywords": [], "boundaries": [],
            "references": {"callers": [], "tests": [], "context": []}, "file_sha256": digest,
            "observed_baseline": {"head": "", "branch": ""},
            "observed_at": utc_now(),
            "lifecycle": "candidate", "freshness": "matched",
            "verification": {"scope": "仅识别公开入口；业务适用性和完整依赖关系未核验", "evidence": [], "recorded_at": None}}


def _load(store: CapabilityStore) -> tuple[dict[str, Any], int | None]:
    if native_path(store.current).exists():
        current = store.read()
        return copy.deepcopy(store.payload(current)), current["revision"]
    require(not native_path(store.previous).exists(), "RECOVERY_REQUIRED")
    store._guard()
    return empty_payload(), None


def _reason(exc: CapabilityError) -> str:
    code = str(exc)
    if code in {"SENSITIVE_PATH", "SENSITIVE_CONTENT"}:
        return "SENSITIVE_CONTENT"
    if code == "LINK_REJECTED":
        return "EXCLUDED"
    if code in {"BUDGET", "TOO_LARGE", "UNSUPPORTED", "PARSE_ERROR", "MISSING"}:
        return code
    if code in {"READ_CHANGED", "CHANGED"}:
        raise CapabilityError("CHANGED") from None
    return "UNREADABLE"


def _context_refs(repo: Path, relative: str, budget: ReadBudget) -> tuple[list[dict[str, str]], bool]:
    refs = []
    complete = True
    parent = Path(relative).parent
    for directory in (parent, *parent.parents):
        for name in CONTEXT_NAMES:
            context = (directory / name).as_posix()
            if context == relative:
                continue
            try:
                exists = budget.context_exists(context)
            except CapabilityError as exc:
                if str(exc) in {"CHANGED", "READ_CHANGED"}:
                    raise CapabilityError("CHANGED") from None
                complete = False
                continue
            if exists:
                if len(refs) == 5:
                    complete = False
                    continue
                try:
                    raw = budget.read(context)
                    text_field(raw.decode("utf-8-sig"), MAX_FILE_BYTES)
                    refs.append({"path": context, "sha256": hashlib.sha256(raw).hexdigest()})
                except CapabilityError as exc:
                    if str(exc) in {"CHANGED", "READ_CHANGED"}:
                        raise CapabilityError("CHANGED") from None
                    complete = False
                except UnicodeError:
                    complete = False
    return refs, complete


def coverage_summary(coverage: dict[str, Any]) -> dict[str, Any]:
    return {"scopes": coverage["scopes"][:5], "scope_count": len(coverage["scopes"]),
            "complete": coverage["complete"],
            "cursor": {"pending_count": len(coverage["cursor"]["pending"])} if coverage["cursor"] else None,
            "limitations": coverage["limitations"][:10], "limitation_count": len(coverage["limitations"])}


def scan(store: CapabilityStore, scopes: list[str] | None = None, *, resume: bool = False,
         _budget: ReadBudget | None = None) -> dict[str, Any]:
    started = time.monotonic()
    payload, revision = _load(store)
    baseline = git_baseline(store.repo_path)
    old_baseline = {key: payload["baseline"][key] for key in ("head", "branch")}
    same_branch = baseline == old_baseline
    if resume:
        require(scopes is None and payload["coverage"]["cursor"] is not None, "NO_CONTINUATION")
        require(same_branch, "CONTINUATION_STALE")
        pending = list(payload["coverage"]["cursor"]["pending"])
        limitations = [item for item in payload["coverage"]["limitations"] if item["reason"] != "BUDGET"]
        selected_scopes = payload["coverage"]["scopes"]
    else:
        selected_scopes = list(dict.fromkeys(scopes or ["."]))
        require(0 < len(selected_scopes) <= 128, "INVALID_SCOPE")
        for scope in selected_scopes:
            if scope != ".":
                relative_path(scope)
        pending = selected_scopes[:]
        limitations = []
    if not same_branch:
        for entry in payload["entries"]:
            entry["freshness"] = "recheck"
    budget = _budget or ReadBudget(store.repo_path)
    require(budget.repo == store.repo_path, "BUDGET_IDENTITY_MISMATCH")
    enumerated = 0
    visited = set()
    entries = {(e["path"], e["symbol"]): e for e in payload["entries"]}

    def limitation(path: str | None, reason: str) -> None:
        record = {"path": path, "reason": reason}
        if record not in limitations:
            require(len(limitations) < MAX_ENTRIES, "COVERAGE_CAPACITY")
            limitations.append(record)

    while pending:
        relative = pending.pop(0)
        if relative in visited:
            continue
        visited.add(relative)
        try:
            path = safe_path(store.repo_path) if relative == "." else source_path(store.repo_path, relative)
            if path.is_dir():
                children = []
                exhausted = False
                with os.scandir(path) as iterator:
                    while enumerated < MAX_PATHS:
                        try:
                            child = next(iterator)
                        except StopIteration:
                            exhausted = True
                            break
                        enumerated += 1
                        child_relative = (Path(relative) / child.name).as_posix()
                        try:
                            relative_path(child_relative)
                        except CapabilityError:
                            limitation(None, "EXCLUDED")
                            continue
                        if child.name in EXCLUDED_DIRS:
                            limitation(child_relative, "EXCLUDED")
                            continue
                        if ".generated." in child.name or child.name.endswith((".min.js", "_pb2.py")):
                            limitation(child_relative, "EXCLUDED")
                            continue
                        if child.is_symlink() or getattr(child.stat(follow_symlinks=False), "st_file_attributes", 0) & 0x400:
                            limitation(child_relative, "EXCLUDED")
                            continue
                        if child.is_dir(follow_symlinks=False) or Path(child.name).suffix.lower() in SOURCE_SUFFIXES:
                            children.append(child_relative)
                if not exhausted:
                    limitation(None if relative == "." else relative, "DIRECTORY_BUDGET")
                # 中文：不保存操作系统目录偏移；未穷尽的大目录需显式缩小范围，避免重复全前缀枚举。 English: Do not persist OS directory offsets; unfinished large directories need narrower explicit scopes rather than repeated prefix enumeration.
                require(len(pending) + len(children) <= MAX_ENTRIES, "CONTINUATION_CAPACITY")
                pending = sorted(set(children + pending))
                if enumerated >= MAX_PATHS:
                    break
                continue
            require(Path(relative).suffix.lower() in SOURCE_SUFFIXES, "UNSUPPORTED")
            raw = budget.read(relative)
            symbols = public_symbols(relative, raw)
            digest = hashlib.sha256(raw).hexdigest()
            contexts, context_complete = _context_refs(store.repo_path, relative, budget)
            require(len(entries) + sum((relative, symbol) not in entries for symbol, _ in symbols) <= MAX_ENTRIES, "INDEX_CAPACITY")
            present = {symbol for symbol, _ in symbols}
            for symbol, kind in symbols:
                existed = (relative, symbol) in entries
                entry = entries.setdefault((relative, symbol), _entry(relative, symbol, kind, digest))
                changed = entry["file_sha256"] != digest
                # 中文：扫描更新声明类别；service/adapter是显式登记的职责，不由语法推断覆盖。 English: Refresh declaration kinds; preserve explicitly registered service/adapter roles.
                current_kind = entry["kind"] if entry["kind"] in {"service", "adapter"} else kind
                kind_changed = entry["kind"] != current_kind
                context_changed = existed and entry["references"]["context"] != contexts
                if changed or kind_changed or context_changed or entry["observed_baseline"] != baseline:
                    entry["observed_at"] = utc_now()
                entry["kind"] = current_kind
                entry["file_sha256"] = digest
                entry["observed_baseline"] = dict(baseline)
                entry["references"]["context"] = contexts
                references_current = True
                for category in ("callers", "tests"):
                    for ref in entry["references"][category]:
                        try:
                            if budget.digest(ref["path"]) != ref["sha256"]:
                                references_current = False
                        except CapabilityError as exc:
                            limitation(ref["path"], _reason(exc))
                            references_current = False
                # 中文：freshness只描述当前源与引用匹配，业务核验不能由重复扫描自动晋升。 English: Freshness describes source/reference matching only; repeated scans never promote semantic verification.
                entry["freshness"] = "matched" if context_complete and references_current else "recheck"
                if changed or kind_changed or context_changed or not references_current:
                    entry["verification"] = _entry(relative, symbol, kind, digest)["verification"]
                if entry["lifecycle"] == "removed":
                    entry["lifecycle"] = "candidate"
                    entry["verification"] = _entry(relative, symbol, kind, digest)["verification"]
            for (entry_path, symbol), entry in entries.items():
                if entry_path == relative and symbol not in present:
                    entry["freshness"] = "stale"
                    if entry["observed_baseline"] == baseline:
                        entry["lifecycle"] = "removed"
            payload["baseline"]["files"][relative] = digest
        except CapabilityError as exc:
            if str(exc) in {"INDEX_CAPACITY", "CONTINUATION_CAPACITY", "COVERAGE_CAPACITY"}:
                raise
            reason = _reason(exc)
            if reason == "BUDGET":
                pending.insert(0, relative)
                limitation(relative, reason)
                break
            limitation(None if reason == "SENSITIVE_CONTENT" else relative, reason)
            for (entry_path, _), entry in entries.items():
                if entry_path == relative:
                    entry["freshness"] = "stale" if reason == "MISSING" else "unknown"
                    if reason == "MISSING" and entry["observed_baseline"] == baseline:
                        entry["lifecycle"] = "removed"
        except OSError:
            limitation(None if relative == "." else relative, "UNREADABLE")
    budget.verify()
    require(git_baseline(store.repo_path) == baseline, "CHANGED")
    payload["entries"] = sorted(entries.values(), key=lambda e: (e["path"], e["symbol"], e["id"]))
    payload["baseline"].update(baseline)
    require(len(payload["baseline"]["files"]) <= MAX_ENTRIES, "INDEX_CAPACITY")
    payload["coverage"] = {"scopes": selected_scopes, "complete": not pending and not any(item["reason"] != "EXCLUDED" for item in limitations),
                           "cursor": {"pending": pending} if pending else None,
                           "limitations": sorted(limitations, key=lambda item: (item["path"] or "", item["reason"]))}
    record = store.commit(payload, revision)
    return {"revision": record["revision"], "changed": record["revision"] != revision,
            "entry_count": len(record["entries"]), "coverage": coverage_summary(record["coverage"]),
            "cost": {"enumerated_paths": enumerated, "context_probes": budget.context_probe_count, "source_reads": budget.reads,
                     "source_bytes": budget.bytes_read, "duration_ms": round((time.monotonic() - started) * 1000)}}


def query(store: CapabilityStore, term: str, limit: int = 5, *, include_inactive: bool = False,
          _budget: ReadBudget | None = None) -> dict[str, Any]:
    require(type(limit) is int and 1 <= limit <= 20, "INVALID_LIMIT")
    text_field(term, 256)
    started = time.monotonic()
    if not native_path(store.current).exists():
        store._guard()
        return {"status": "UNAVAILABLE", "reason": "INDEX_MISSING", "candidates": [], "source_search_required": True,
                "maintenance": {"state": "NOT_INITIALIZED", "next_operation": "capability-scan",
                                "when": "AUTHORIZED_FIRST_ONBOARDING_NONTRIVIAL_OR_SHARED_INTERFACE_CHANGE",
                                "scope": "TASK_RELEVANT_ONLY", "otherwise": "BOUNDED_SOURCE_SEARCH"}}
    record = store.read()
    baseline = git_baseline(store.repo_path)
    words = term.casefold().split()
    scored = []
    for entry in record["entries"]:
        if entry["lifecycle"] in {"deprecated", "removed"} and not include_inactive:
            continue
        haystack = " ".join([entry["path"], entry["symbol"], entry["summary"], *entry["keywords"], *entry["boundaries"]]).casefold()
        score = sum(word in haystack for word in words)
        if score or not words:
            scored.append((score, entry))
    selected = sorted(scored, key=lambda pair: (-pair[0], pair[1]["path"], pair[1]["symbol"]))[:limit]
    budget = _budget or ReadBudget(store.repo_path)
    require(budget.repo == store.repo_path, "BUDGET_IDENTITY_MISMATCH")
    candidates = []
    for _, original in selected:
        entry = copy.deepcopy(original)
        reasons = []
        if entry["observed_baseline"] != baseline:
            reasons.append("BASELINE_CHANGED")
        try:
            digest = budget.digest(entry["path"])
            if digest != entry["file_sha256"]:
                reasons.append("SOURCE_CHANGED")
            for refs in entry["references"].values():
                for ref in refs:
                    if budget.digest(ref["path"]) != ref["sha256"]:
                        reasons.append("REFERENCE_CHANGED")
            contexts, complete = _context_refs(store.repo_path, entry["path"], budget)
            if contexts != entry["references"]["context"]:
                reasons.append("CONTEXT_CHANGED")
            if not complete:
                reasons.append("CONTEXT_UNCONFIRMED")
        except CapabilityError as exc:
            reasons.append(_reason(exc))
        if reasons:
            entry["freshness"] = "stale" if any(r in {"SOURCE_CHANGED", "MISSING"} for r in reasons) else "recheck"
        entry["current_check"] = {"reasons": sorted(set(reasons)), "semantic_reuse_approved": False}
        candidates.append(entry)
    budget.verify()
    require(git_baseline(store.repo_path) == baseline, "CHANGED")
    return {"status": "OK", "revision": record["revision"], "candidates": candidates,
            "coverage": coverage_summary(record["coverage"]), "source_search_required": not candidates or not record["coverage"]["complete"] or any(c["current_check"]["reasons"] or c["freshness"] != "matched" for c in candidates),
            "cost": {"context_probes": budget.context_probe_count, "source_reads": budget.reads, "source_bytes": budget.bytes_read,
                     "duration_ms": round((time.monotonic() - started) * 1000)}}


def register(store: CapabilityStore, entry: dict[str, Any], expected_revision: int) -> dict[str, Any]:
    integer(expected_revision, 2**63 - 2)
    payload, revision = _load(store)
    require(revision == expected_revision, "REVISION_CONFLICT")
    candidate = copy.deepcopy(entry)
    validate_payload({**empty_payload(), "entries": [candidate]})
    budget = ReadBudget(store.repo_path)
    baseline = git_baseline(store.repo_path)
    candidate["file_sha256"] = budget.digest(candidate["path"])
    candidate["observed_baseline"] = dict(baseline)
    for refs in candidate["references"].values():
        for ref in refs:
            ref["sha256"] = budget.digest(ref["path"])
    # 中文：人工登记说明保留为声明，不因内容匹配自动批准语义或生命周期。 English: Manual statements remain assertions; matching content never automatically approves semantics or lifecycle.
    candidate["freshness"] = "recheck"
    old = next((e for e in payload["entries"] if e["id"] == candidate["id"]), None)
    if old is not None:
        candidate["observed_at"] = old["observed_at"]
        candidate["verification"]["recorded_at"] = old["verification"]["recorded_at"]
    if candidate != old:
        candidate["observed_at"] = utc_now()
        candidate["verification"]["recorded_at"] = utc_now()
    require(not any(e["id"] != candidate["id"] and (e["path"], e["symbol"]) == (candidate["path"], candidate["symbol"]) for e in payload["entries"]), "DUPLICATE_LOCATOR")
    payload["entries"] = [e for e in payload["entries"] if e["id"] != candidate["id"]] + [candidate]
    budget.verify()
    require(git_baseline(store.repo_path) == baseline, "CHANGED")
    payload["baseline"].update(baseline)
    payload["baseline"]["files"][candidate["path"]] = candidate["file_sha256"]
    return store.commit(payload, revision)


def lifecycle(store: CapabilityStore, entry_id: str, state: str, reason: str, expected_revision: int) -> dict[str, Any]:
    integer(expected_revision, 2**63 - 2)
    require(isinstance(state, str) and state in {"candidate", "active", "deprecated", "removed"}, "INVALID_LIFECYCLE")
    text_field(reason)
    require(bool(reason.strip()), "REASON_REQUIRED")
    payload, revision = _load(store)
    require(revision == expected_revision, "REVISION_CONFLICT")
    entry = next((e for e in payload["entries"] if e["id"] == entry_id), None)
    require(entry is not None, "ENTRY_NOT_FOUND")
    baseline = git_baseline(store.repo_path)
    path = source_path(store.repo_path, entry["path"])
    if state == "removed":
        require(not path.exists(), "ENTRY_STILL_EXISTS")
    else:
        require(path.is_file(), "MISSING")
    changed = entry["lifecycle"] != state or entry["verification"]["scope"] != reason
    entry["lifecycle"] = state
    entry["freshness"] = "stale" if state == "removed" else "recheck"
    entry["verification"]["scope"] = reason
    if changed:
        entry["verification"]["recorded_at"] = utc_now()
    require(git_baseline(store.repo_path) == baseline, "CHANGED")
    return store.commit(payload, revision)


def invalidate(store: CapabilityStore, changed_paths: list[str], expected_revision: int) -> dict[str, Any]:
    """中文：按显式变更使关联定位待复核；未知依赖不据此声称未受影响。 English: Invalidate related locations from explicit changes; unknown dependencies do not establish absence of impact."""
    integer(expected_revision, 2**63 - 2)
    require(isinstance(changed_paths, list) and 0 < len(changed_paths) <= 128, "INVALID_SCOPE")
    changes = {relative_path(path) for path in changed_paths}
    payload, revision = _load(store)
    require(revision == expected_revision, "REVISION_CONFLICT")
    modules = {Path(entry["path"]).parts[0] for entry in payload["entries"]}
    broad = any(len(Path(path).parts) == 1 or Path(path).parts[0] not in modules for path in changes)
    count = 0
    for entry in payload["entries"]:
        references = {ref["path"] for refs in entry["references"].values() for ref in refs}
        same_module = any(Path(path).parts[0] == Path(entry["path"]).parts[0] for path in changes)
        if broad or same_module or entry["path"] in changes or references.intersection(changes):
            if entry["freshness"] != "recheck":
                count += 1
            entry["freshness"] = "recheck"
    record = store.commit(payload, revision)
    return {"revision": record["revision"], "invalidated_entries": count,
            "dependency_coverage": "PARTIAL", "changed": record["revision"] != revision,
            "maintenance": {"state": "INVALIDATED_NOT_UPDATED", "next_operation": "capability-scan",
                            "scope": "CHANGED_AND_CHECKED_SOURCE_PATHS", "owner": "TASK_COORDINATOR",
                            "unverified_references": "KEEP_PENDING_WITH_REASON"}}
