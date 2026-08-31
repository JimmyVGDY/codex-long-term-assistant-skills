#!/usr/bin/env python3
"""Create, validate, and reuse a deterministic, progressive review packet.

Reviewers should read ``manifest.json`` and ``packet-summary.md`` first, then inspect
only their assigned files or hunks. ``diff.patch`` remains available for complete
evidence but is not intended to be injected wholesale into every subagent prompt.
"""
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
from typing import Any, Dict, Iterable, List, Optional, Tuple

MAX_SNAPSHOT_BYTES = 1024 * 1024
FULL_HASH_LIMIT = 4 * 1024 * 1024
SAMPLE_BYTES = 1024 * 1024
SENSITIVE_NAMES = {
    ".env",
    ".env.local",
    ".env.production",
    "credentials",
    "credentials.json",
    "secrets.json",
    "id_rsa",
    "id_ed25519",
}
SENSITIVE_SUFFIXES = {".pem", ".key", ".p12", ".pfx", ".jks", ".keystore"}
MODEL_PROFILES: Dict[str, Dict[str, str]] = {
    "luna-low": {"model": "gpt-5.6-luna", "reasoning_effort": "low"},
    "luna-medium": {"model": "gpt-5.6-luna", "reasoning_effort": "medium"},
    "terra-medium": {"model": "gpt-5.6-terra", "reasoning_effort": "medium"},
    "terra-high": {"model": "gpt-5.6-terra", "reasoning_effort": "high"},
}
DEFAULT_PROFILE_BY_TIER = {
    "economy": "luna-low",
    "balanced": "luna-medium",
    "deep": "terra-medium",
}


def die(message: str, code: int = 1) -> None:
    print("[FAIL] " + message, file=sys.stderr)
    raise SystemExit(code)


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


def list_untracked(repo: Path) -> List[str]:
    raw = run(["git", "ls-files", "--others", "--exclude-standard", "-z"], repo)
    return sorted(
        item.decode("utf-8", errors="surrogateescape")
        for item in raw.split(b"\0")
        if item
    )


def describe_untracked(
    repo: Path, output: Optional[Path] = None
) -> Tuple[List[Dict[str, Any]], List[str]]:
    entries: List[Dict[str, Any]] = []
    changed: List[str] = []
    snapshot_root = output / "untracked" if output else None
    for relative in list_untracked(repo):
        changed.append(relative)
        path = safe_relative(repo, relative)
        if not path.exists() and not path.is_symlink():
            entries.append(
                {
                    "path": relative,
                    "snapshot": None,
                    "reason": "missing",
                    "sha256": "",
                    "hash_mode": "none",
                }
            )
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
        elif snapshot_root is not None:
            target = snapshot_root / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, target)
            entry["snapshot"] = target.relative_to(output).as_posix() if output else None
            entry["snapshot_sha256"] = sha256_bytes(target.read_bytes())
        else:
            entry["reason"] = "snapshot-not-requested"
        entries.append(entry)
    return entries, changed


def canonical_manifest_bytes(manifest: Dict[str, Any]) -> bytes:
    return json.dumps(
        manifest, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode()


def prepare_output(output: Path, force: bool) -> None:
    if output.exists() and any(output.iterdir()):
        if not force:
            die("输出目录非空；为避免混入旧审查包，请使用新目录或显式 --force")
        shutil.rmtree(output)
    output.mkdir(parents=True, exist_ok=True)


def git_packet_inputs(repo: Path, base: str) -> Dict[str, bytes]:
    return {
        "diff": run(["git", "diff", "--binary", "--no-ext-diff", base, "--"], repo),
        "status": run(["git", "status", "--porcelain=v1", "--untracked-files=all"], repo),
        "diff_stat": run(["git", "diff", "--stat", "--no-ext-diff", base, "--"], repo),
        "name_status": run(["git", "diff", "--name-status", "--no-ext-diff", base, "--"], repo),
    }


def packet_summary(manifest: Dict[str, Any]) -> str:
    related = manifest.get("related_files") or []
    constraints = manifest.get("constraints") or []
    excluded = [
        item["path"]
        for item in manifest.get("untracked_files", [])
        if not item.get("snapshot")
    ]
    lines = [
        "# 审查包摘要",
        "",
        "- 功能边界：`{}`".format(manifest["boundary_id"]),
        "- 阶段 / 流程档位：`{}` / `{}`".format(manifest["phase"], manifest["profile"]),
        "- Reviewer 成本档位：`{}`".format(manifest["effort_tier"]),
        "- 默认模型档位：`{}`".format(manifest["default_model_profile"]),
        "- 基线 / HEAD：`{}` / `{}`".format(manifest["base_ref"], manifest["head_commit"]),
        "- 改动文件数：{}".format(manifest["changed_file_count"]),
        "- diff 字节数：{}".format(manifest["diff_bytes"]),
        "- packet SHA-256：`{}`".format(manifest["packet_sha256"]),
        "",
        "## 推荐读取顺序",
        "",
        "1. `manifest.json`、本摘要与 `diff-stat.txt`。",
        "2. 当前 Reviewer 被分配的文件、符号、直接上下游和已有验证证据。",
        "3. 仅在需要定位证据时读取 `diff.patch` 对应 hunks；不要把整个 patch 重复塞入每个子 Agent 上下文。",
    ]
    if related:
        lines.extend(["", "## 关联文件", ""] + ["- `{} `".format(item).replace(" `", "`") for item in related])
    if constraints:
        lines.extend(["", "## 约束", ""] + ["- " + item for item in constraints if item.strip()])
    if excluded:
        lines.extend(
            ["", "## 未快照范围", ""]
            + ["- `{}`：需直接读取原仓库或标记未验证。".format(item) for item in excluded]
        )
    return "\n".join(lines).rstrip() + "\n"


def command_create(args: argparse.Namespace) -> None:
    repo = Path(args.repo_path).expanduser().resolve()
    output = Path(args.output_dir).expanduser().resolve()
    if not (repo / ".git").exists():
        # Worktrees may use a .git file; rev-parse is the final authority.
        run(["git", "rev-parse", "--is-inside-work-tree"], repo)
    if inside(output, repo) and not args.allow_inside_repo:
        die("审查包默认必须写在仓库外；需要时显式 --allow-inside-repo")
    prepare_output(output, args.force)

    head = run(["git", "rev-parse", "HEAD"], repo).decode().strip()
    base = args.base_ref
    inputs = git_packet_inputs(repo, base)
    tracked_changed = run(["git", "diff", "--name-only", base, "--"], repo).decode(
        errors="replace"
    ).splitlines()
    untracked_entries, untracked_changed = describe_untracked(repo, output)
    changed_files = sorted(set(tracked_changed + untracked_changed))

    (output / "diff.patch").write_bytes(inputs["diff"])
    (output / "status.txt").write_bytes(inputs["status"])
    (output / "diff-stat.txt").write_bytes(inputs["diff_stat"])
    (output / "name-status.txt").write_bytes(inputs["name_status"])
    (output / "changed-files.txt").write_text(
        "\n".join(changed_files) + ("\n" if changed_files else ""), encoding="utf-8"
    )

    related = [item.strip() for item in args.related_files.split(",") if item.strip()]
    constraints: List[str] = []
    if args.constraints_file:
        constraints = Path(args.constraints_file).read_text(encoding="utf-8-sig").splitlines()
    validations: Any = []
    if args.validations_file:
        validations = json.loads(
            Path(args.validations_file).read_text(encoding="utf-8-sig")
        )

    manifest: Dict[str, Any] = {
        "schema_version": 3,
        "boundary_id": args.boundary_id,
        "phase": args.phase,
        "profile": args.profile,
        "effort_tier": args.effort_tier,
        "default_model_profile": DEFAULT_PROFILE_BY_TIER[args.effort_tier],
        "base_ref": base,
        "head_commit": head,
        "diff_sha256": sha256_bytes(inputs["diff"]),
        "status_sha256": sha256_bytes(inputs["status"]),
        "diff_stat_sha256": sha256_bytes(inputs["diff_stat"]),
        "name_status_sha256": sha256_bytes(inputs["name_status"]),
        "diff_bytes": len(inputs["diff"]),
        "changed_file_count": len(changed_files),
        "changed_files": changed_files,
        "untracked_files": untracked_entries,
        "related_files": related,
        "validation_evidence": validations,
        "constraints": constraints,
        "read_order": [
            "manifest.json",
            "packet-summary.md",
            "diff-stat.txt",
            "changed-files.txt",
            "assigned source files and direct dependencies",
            "relevant diff.patch hunks only",
        ],
        "created_by": "review_packet.py",
    }
    core = canonical_manifest_bytes(manifest)
    manifest["packet_sha256"] = sha256_bytes(
        core
        + inputs["diff"]
        + inputs["status"]
        + inputs["diff_stat"]
        + inputs["name_status"]
    )
    (output / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    (output / "packet-summary.md").write_text(packet_summary(manifest), encoding="utf-8")
    (output / "PACKET_SHA256").write_text(manifest["packet_sha256"] + "\n", encoding="ascii")
    print("[OK] 已创建审查包", output)
    print(manifest["packet_sha256"])
    excluded = [item for item in untracked_entries if not item.get("snapshot")]
    if excluded:
        print(
            "[WARN] 未快照的 untracked 文件:",
            len(excluded),
            "；Reviewer 必须标记未验证或按授权直接读取原仓库。",
        )


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


def load_manifest(packet_dir: Path) -> Dict[str, Any]:
    path = packet_dir / "manifest.json"
    if not path.is_file():
        die("缺少 manifest.json")
    try:
        manifest = json.loads(path.read_text(encoding="utf-8-sig"))
    except json.JSONDecodeError as exc:
        die("manifest.json 不是有效 JSON: {}".format(exc))
    if manifest.get("schema_version") not in {2, 3}:
        die("不支持的审查包 schema_version")
    return manifest


def command_validate(args: argparse.Namespace) -> None:
    packet_dir = Path(args.packet_dir).resolve()
    manifest = load_manifest(packet_dir)
    diff_data = (packet_dir / "diff.patch").read_bytes()
    status_data = (packet_dir / "status.txt").read_bytes()
    if manifest.get("schema_version") == 2:
        core = dict(manifest)
        expected = core.pop("packet_sha256")
        actual = sha256_bytes(canonical_manifest_bytes(core) + diff_data + status_data)
    else:
        diff_stat = (packet_dir / "diff-stat.txt").read_bytes()
        name_status = (packet_dir / "name-status.txt").read_bytes()
        for key, data in (
            ("diff_sha256", diff_data),
            ("status_sha256", status_data),
            ("diff_stat_sha256", diff_stat),
            ("name_status_sha256", name_status),
        ):
            if manifest.get(key) != sha256_bytes(data):
                die("审查包组件 hash 不一致: " + key)
        core = dict(manifest)
        expected = core.pop("packet_sha256")
        actual = sha256_bytes(
            canonical_manifest_bytes(core) + diff_data + status_data + diff_stat + name_status
        )
    validate_snapshots(packet_dir, manifest)
    if expected != actual:
        die("审查包 hash 不一致")
    marker = (packet_dir / "PACKET_SHA256").read_text(encoding="ascii").strip()
    if marker != actual:
        die("PACKET_SHA256 与 manifest 不一致")
    print("[OK] 审查包有效", actual)


def untracked_fingerprint(entries: List[Dict[str, Any]]) -> Dict[str, Tuple[str, str]]:
    return {
        str(item.get("path")): (str(item.get("sha256", "")), str(item.get("hash_mode", "")))
        for item in entries
    }


def command_freshness(args: argparse.Namespace) -> None:
    packet_dir = Path(args.packet_dir).expanduser().resolve()
    repo = Path(args.repo_path).expanduser().resolve()
    manifest = load_manifest(packet_dir)
    base = manifest["base_ref"]
    head = run(["git", "rev-parse", "HEAD"], repo).decode().strip()
    inputs = git_packet_inputs(repo, base)
    current_untracked, _ = describe_untracked(repo, None)
    differences: List[str] = []
    if head != manifest.get("head_commit"):
        differences.append("HEAD 已变化")
    for label, manifest_key, input_key in (
        ("diff", "diff_sha256", "diff"),
        ("status", "status_sha256", "status"),
    ):
        if sha256_bytes(inputs[input_key]) != manifest.get(manifest_key):
            differences.append(label + " 已变化")
    if untracked_fingerprint(current_untracked) != untracked_fingerprint(manifest.get("untracked_files", [])):
        differences.append("untracked 内容已变化")
    if differences:
        print("[STALE] 审查包已过期: " + "；".join(differences))
        raise SystemExit(2)
    print("[FRESH] 审查包仍与当前工作区一致: " + manifest["packet_sha256"])


def command_result_template(args: argparse.Namespace) -> None:
    packet_dir = Path(args.packet_dir).resolve()
    manifest = load_manifest(packet_dir)
    profile = args.model_profile or manifest.get("default_model_profile") or DEFAULT_PROFILE_BY_TIER.get(
        manifest.get("effort_tier", "balanced"), "luna-medium"
    )
    if profile not in MODEL_PROFILES:
        die("未知 model-profile")
    config = MODEL_PROFILES[profile]
    result_id = "RVR_" + hashlib.sha256(
        (manifest["boundary_id"] + "|" + args.reviewer + "|" + manifest["packet_sha256"]).encode("utf-8")
    ).hexdigest()
    result = {
        "schema_version": 2,
        "result_id": result_id,
        "reviewer": args.reviewer,
        "boundary_id": manifest["boundary_id"],
        "packet_sha256": manifest["packet_sha256"],
        "status": "incomplete",
        "isolation_level": "unknown",
        "model_assignment": {
            "requested_profile": profile,
            "requested_model": config["model"],
            "requested_reasoning_effort": config["reasoning_effort"],
            "runtime_model": "",
            "runtime_reasoning_effort": "",
            "status": "unverified",
        },
        "checked_scope": [],
        "findings": [],
        "unverified_items": [],
        "summary": "",
    }
    Path(args.output).write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print("[OK] 已创建结果模板", args.output)


def command_validate_result(args: argparse.Namespace) -> None:
    packet_dir = Path(args.packet_dir).resolve()
    manifest = load_manifest(packet_dir)
    result = json.loads(Path(args.result_file).read_text(encoding="utf-8-sig"))
    required = {
        "schema_version",
        "result_id",
        "reviewer",
        "boundary_id",
        "packet_sha256",
        "status",
        "isolation_level",
        "model_assignment",
        "checked_scope",
        "findings",
        "unverified_items",
    }
    missing = sorted(required - set(result))
    if missing:
        die("Reviewer 结果缺少字段: " + ",".join(missing))
    if result["schema_version"] != 2:
        die("Reviewer 结果 schema_version 必须是 2")
    expected_result_id = "RVR_" + hashlib.sha256(
        (manifest["boundary_id"] + "|" + str(result["reviewer"]) + "|" + manifest["packet_sha256"]).encode("utf-8")
    ).hexdigest()
    if result["result_id"] != expected_result_id:
        die("Reviewer 结果 result_id 与审查包身份不匹配")
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
    assignment = result["model_assignment"]
    if not isinstance(assignment, dict):
        die("model_assignment 必须是对象")
    requested_profile = assignment.get("requested_profile")
    if requested_profile not in MODEL_PROFILES:
        die("model_assignment.requested_profile 非法")
    expected = MODEL_PROFILES[requested_profile]
    if assignment.get("requested_model") != expected["model"]:
        die("model_assignment.requested_model 与档位不一致")
    if assignment.get("requested_reasoning_effort") != expected["reasoning_effort"]:
        die("model_assignment.requested_reasoning_effort 与档位不一致")
    runtime_model = str(assignment.get("runtime_model", ""))
    runtime_effort = str(assignment.get("runtime_reasoning_effort", ""))
    if bool(runtime_model) != bool(runtime_effort):
        die("runtime_model 与 runtime_reasoning_effort 必须同时填写或同时留空")
    print("[OK] Reviewer 结构化结果有效", args.result_file)


def main() -> None:
    parser = argparse.ArgumentParser(description="创建、验证和复用渐进式审查包")
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
    create.add_argument("--force", action="store_true")
    create.set_defaults(func=command_create)

    validate = sub.add_parser("validate")
    validate.add_argument("--packet-dir", required=True)
    validate.set_defaults(func=command_validate)

    freshness = sub.add_parser("freshness")
    freshness.add_argument("--packet-dir", required=True)
    freshness.add_argument("--repo-path", required=True)
    freshness.set_defaults(func=command_freshness)

    template = sub.add_parser("result-template")
    template.add_argument("--packet-dir", required=True)
    template.add_argument("--reviewer", required=True)
    template.add_argument("--model-profile", choices=list(MODEL_PROFILES), default="")
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
