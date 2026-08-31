#!/usr/bin/env python3
"""Create, validate, and consume a minimal deterministic review packet outside the repository."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import stat
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, Iterable, List, Tuple

MAX_SNAPSHOT_BYTES = 1024 * 1024
FULL_HASH_LIMIT = 4 * 1024 * 1024
SAMPLE_BYTES = 1024 * 1024
SENSITIVE_NAMES = {".env", ".env.local", ".env.production", "credentials", "credentials.json", "secrets.json", "id_rsa", "id_ed25519"}
SENSITIVE_SUFFIXES = {".pem", ".key", ".p12", ".pfx", ".jks", ".keystore"}


def die(message: str) -> None:
    print("[FAIL] " + message, file=sys.stderr)
    raise SystemExit(1)


def run(command: Iterable[str], cwd: Path) -> bytes:
    cmd = list(command)
    result = subprocess.run(cmd, cwd=cwd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if result.returncode:
        die(result.stderr.decode(errors="replace"))
    return result.stdout


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def inside(child: Path, parent: Path) -> bool:
    try:
        child.resolve().relative_to(parent.resolve())
        return True
    except ValueError:
        return False


def safe_relative(repo: Path, relative: str) -> Path:
    path = (repo / relative).resolve()
    if not inside(path, repo):
        die("检测到越界路径: " + relative)
    return path


def sensitive_path(relative: str) -> bool:
    path = Path(relative)
    lower_parts = {part.lower() for part in path.parts}
    if path.name.lower() in SENSITIVE_NAMES:
        return True
    if path.suffix.lower() in SENSITIVE_SUFFIXES:
        return True
    return bool(lower_parts & {".ssh", ".aws", ".gnupg", "secrets", "credentials"})


def sampled_file_digest(path: Path) -> Tuple[str, str]:
    info = path.lstat()
    digest = hashlib.sha256()
    digest.update(str(info.st_mode).encode())
    digest.update(b"\0")
    digest.update(str(info.st_size).encode())
    digest.update(b"\0")
    if stat.S_ISLNK(info.st_mode):
        digest.update(os.readlink(path).encode(errors="surrogateescape"))
        return digest.hexdigest(), "symlink"
    if not stat.S_ISREG(info.st_mode):
        digest.update(str(info.st_mtime_ns).encode())
        return digest.hexdigest(), "metadata"
    with path.open("rb") as handle:
        if info.st_size <= FULL_HASH_LIMIT:
            for block in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(block)
            return digest.hexdigest(), "full"
        digest.update(handle.read(SAMPLE_BYTES))
        handle.seek(max(0, info.st_size - SAMPLE_BYTES))
        digest.update(handle.read(SAMPLE_BYTES))
        digest.update(str(info.st_mtime_ns).encode())
        return digest.hexdigest(), "sampled"


def is_probably_text(path: Path) -> bool:
    if not path.is_file():
        return False
    with path.open("rb") as handle:
        sample = handle.read(8192)
    if b"\0" in sample:
        return False
    try:
        sample.decode("utf-8")
        return True
    except UnicodeDecodeError:
        return False


def collect_untracked(repo: Path, output: Path) -> Tuple[List[Dict[str, Any]], List[str]]:
    raw = run(["git", "ls-files", "--others", "--exclude-standard", "-z"], repo)
    names = [item.decode("utf-8", errors="surrogateescape") for item in raw.split(b"\0") if item]
    entries: List[Dict[str, Any]] = []
    changed: List[str] = []
    snapshot_root = output / "untracked"
    for relative in sorted(names):
        changed.append(relative)
        path = safe_relative(repo, relative)
        if not path.exists() and not path.is_symlink():
            entries.append({"path": relative, "snapshot": None, "reason": "missing", "sha256": "", "hash_mode": "none"})
            continue
        digest, hash_mode = sampled_file_digest(path)
        entry: Dict[str, Any] = {
            "path": relative,
            "size": path.lstat().st_size,
            "sha256": digest,
            "hash_mode": hash_mode,
            "snapshot": None,
            "reason": "",
        }
        if sensitive_path(relative):
            entry["reason"] = "excluded-sensitive-path"
        elif path.is_symlink():
            entry["reason"] = "symlink-metadata-only"
        elif not path.is_file():
            entry["reason"] = "non-regular-file"
        elif path.stat().st_size > MAX_SNAPSHOT_BYTES:
            entry["reason"] = "too-large-for-snapshot"
        elif not is_probably_text(path):
            entry["reason"] = "binary-or-non-utf8"
        else:
            target = snapshot_root / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, target)
            entry["snapshot"] = target.relative_to(output).as_posix()
            entry["snapshot_sha256"] = sha256_bytes(target.read_bytes())
        entries.append(entry)
    return entries, changed


def canonical_manifest_bytes(manifest: Dict[str, Any]) -> bytes:
    return json.dumps(manifest, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()


def command_create(args: argparse.Namespace) -> None:
    repo = Path(args.repo_path).expanduser().resolve()
    output = Path(args.output_dir).expanduser().resolve()
    if inside(output, repo) and not args.allow_inside_repo:
        die("审查包默认必须写在仓库外；需要时显式 --allow-inside-repo")
    output.mkdir(parents=True, exist_ok=True)
    head = run(["git", "rev-parse", "HEAD"], repo).decode().strip()
    base = args.base_ref
    diff_data = run(["git", "diff", "--binary", "--no-ext-diff", base, "--"], repo)
    status_data = run(["git", "status", "--porcelain=v1", "--untracked-files=all"], repo)
    tracked_changed = run(["git", "diff", "--name-only", base, "--"], repo).decode(errors="replace").splitlines()
    untracked_entries, untracked_changed = collect_untracked(repo, output)
    changed_files = sorted(set(tracked_changed + untracked_changed))

    (output / "diff.patch").write_bytes(diff_data)
    (output / "status.txt").write_bytes(status_data)
    (output / "changed-files.txt").write_text("\n".join(changed_files) + "\n", encoding="utf-8")

    related = [item.strip() for item in args.related_files.split(",") if item.strip()]
    constraints: List[str] = []
    if args.constraints_file:
        constraints = Path(args.constraints_file).read_text(encoding="utf-8-sig").splitlines()
    validations: Any = []
    if args.validations_file:
        validations = json.loads(Path(args.validations_file).read_text(encoding="utf-8-sig"))

    manifest: Dict[str, Any] = {
        "schema_version": 2,
        "boundary_id": args.boundary_id,
        "phase": args.phase,
        "profile": args.profile,
        "effort_tier": args.effort_tier,
        "base_ref": base,
        "head_commit": head,
        "diff_sha256": sha256_bytes(diff_data),
        "status_sha256": sha256_bytes(status_data),
        "changed_files": changed_files,
        "untracked_files": untracked_entries,
        "related_files": related,
        "validation_evidence": validations,
        "constraints": constraints,
        "created_by": "review_packet.py",
    }
    core = canonical_manifest_bytes(manifest)
    manifest["packet_sha256"] = sha256_bytes(core + diff_data + status_data)
    (output / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    (output / "PACKET_SHA256").write_text(manifest["packet_sha256"] + "\n", encoding="ascii")
    print("[OK] 已创建审查包", output)
    print(manifest["packet_sha256"])
    excluded = [item for item in untracked_entries if not item.get("snapshot")]
    if excluded:
        print("[WARN] 未快照的 untracked 文件:", len(excluded), "；Reviewer 必须把这些范围列为未验证或按授权直接读取原仓库。")


def validate_snapshots(packet_dir: Path, manifest: Dict[str, Any]) -> None:
    for entry in manifest.get("untracked_files", []):
        snapshot = entry.get("snapshot")
        if not snapshot:
            continue
        path = (packet_dir / snapshot).resolve()
        if not inside(path, packet_dir) or not path.is_file():
            die("审查包快照缺失或越界: " + str(snapshot))
        actual = sha256_bytes(path.read_bytes())
        if actual != entry.get("snapshot_sha256"):
            die("审查包快照 hash 不一致: " + str(snapshot))


def command_validate(args: argparse.Namespace) -> None:
    packet_dir = Path(args.packet_dir).resolve()
    manifest = json.loads((packet_dir / "manifest.json").read_text(encoding="utf-8-sig"))
    diff_data = (packet_dir / "diff.patch").read_bytes()
    status_data = (packet_dir / "status.txt").read_bytes()
    expected = manifest.pop("packet_sha256")
    validate_snapshots(packet_dir, manifest)
    actual = sha256_bytes(canonical_manifest_bytes(manifest) + diff_data + status_data)
    if expected != actual:
        die("审查包 hash 不一致")
    print("[OK] 审查包有效", actual)


def command_result_template(args: argparse.Namespace) -> None:
    packet_dir = Path(args.packet_dir).resolve()
    manifest = json.loads((packet_dir / "manifest.json").read_text(encoding="utf-8-sig"))
    result = {
        "schema_version": 1,
        "reviewer": args.reviewer,
        "boundary_id": manifest["boundary_id"],
        "packet_sha256": manifest["packet_sha256"],
        "status": "incomplete",
        "isolation_level": "unknown",
        "checked_scope": [],
        "findings": [],
        "unverified_items": [],
        "summary": "",
    }
    Path(args.output).write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("[OK] 已创建结果模板", args.output)


def command_validate_result(args: argparse.Namespace) -> None:
    packet_dir = Path(args.packet_dir).resolve()
    manifest = json.loads((packet_dir / "manifest.json").read_text(encoding="utf-8-sig"))
    result = json.loads(Path(args.result_file).read_text(encoding="utf-8-sig"))
    required = {
        "schema_version", "reviewer", "boundary_id", "packet_sha256", "status",
        "isolation_level", "checked_scope", "findings", "unverified_items",
    }
    missing = sorted(required - set(result))
    if missing:
        die("Reviewer 结果缺少字段: " + ",".join(missing))
    if result["boundary_id"] != manifest["boundary_id"]:
        die("Reviewer 结果 boundary_id 不匹配")
    if result["packet_sha256"] != manifest["packet_sha256"]:
        die("Reviewer 结果 packet_sha256 不匹配")
    if args.reviewer and result["reviewer"] != args.reviewer:
        die("Reviewer 结果身份不匹配")
    if result["status"] not in {"pass", "nonblocking", "blocking", "incomplete"}:
        die("Reviewer 结果 status 非法")
    if not isinstance(result["findings"], list) or not isinstance(result["unverified_items"], list):
        die("Reviewer findings/unverified_items 必须是数组")
    print("[OK] Reviewer 结构化结果有效", args.result_file)


def main() -> None:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    create = sub.add_parser("create")
    create.add_argument("--repo-path", required=True)
    create.add_argument("--output-dir", required=True)
    create.add_argument("--boundary-id", required=True)
    create.add_argument("--base-ref", default="HEAD")
    create.add_argument("--phase", choices=["pre", "post"], default="post")
    create.add_argument("--profile", choices=["LIGHT", "STANDARD", "STRICT"], default="STANDARD")
    create.add_argument("--effort-tier", choices=["economy", "balanced", "deep"], default="balanced")
    create.add_argument("--related-files", default="")
    create.add_argument("--constraints-file")
    create.add_argument("--validations-file")
    create.add_argument("--allow-inside-repo", action="store_true")
    create.set_defaults(func=command_create)
    validate = sub.add_parser("validate")
    validate.add_argument("--packet-dir", required=True)
    validate.set_defaults(func=command_validate)
    template = sub.add_parser("result-template")
    template.add_argument("--packet-dir", required=True)
    template.add_argument("--reviewer", required=True)
    template.add_argument("--output", required=True)
    template.set_defaults(func=command_result_template)
    result = sub.add_parser("validate-result")
    result.add_argument("--packet-dir", required=True)
    result.add_argument("--result-file", required=True)
    result.add_argument("--reviewer")
    result.set_defaults(func=command_validate_result)
    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
