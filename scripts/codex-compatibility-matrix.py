#!/usr/bin/env python3
"""中文：隔离重放一个官方 Codex 稳定版兼容单元。

English: Replay one official Codex stable-release compatibility cell in isolation.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import package_manager as manager  # noqa: E402
from codex_compatibility import (  # noqa: E402
    canonical_digest, profile_for_version, verify_artifact_file,
)


def digest(text: str) -> str:
    return hashlib.sha256(text.rstrip("\r\n").encode("utf-8")).hexdigest()


def run_hook(hook: str, payload: dict, data_root: Path) -> dict:
    env = os.environ.copy()
    env["CP_ASSISTANT_DATA"] = str(data_root)
    result = subprocess.run(
        [sys.executable, str(ROOT / "hooks" / "cp_hook.py"), hook],
        input=json.dumps(payload), text=True, encoding="utf-8", errors="replace",
        capture_output=True, env=env, timeout=20,
    )
    if result.returncode != 0:
        raise RuntimeError(f"{hook} Hook failed: {result.stderr[-2000:]}")
    try:
        return json.loads(result.stdout or "{}")
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"{hook} Hook returned invalid JSON") from exc


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--expected-version", required=True)
    parser.add_argument("--codex-executable")
    parser.add_argument("--artifact")
    args = parser.parse_args()
    if args.codex_executable:
        os.environ["CP_ASSISTANT_CODEX_EXECUTABLE"] = str(Path(args.codex_executable).resolve(strict=True))
    version_profile = profile_for_version(manager.COMPATIBILITY_REGISTRY, args.expected_version)
    evidence = version_profile["probe_evidence"]
    artifact_report = None
    if args.artifact:
        artifact_report = verify_artifact_file(
            manager.COMPATIBILITY_REGISTRY, args.expected_version, Path(args.artifact),
        )

    with tempfile.TemporaryDirectory(prefix=f"cp-codex-matrix-{args.expected_version}-") as td:
        isolated_home = Path(td) / "codex-home"
        isolated_home.mkdir()
        original_home = os.environ.get("CODEX_HOME")
        os.environ["CODEX_HOME"] = str(isolated_home)
        try:
            profile = manager._probe_plugin_host()
            if not profile.get("ok") or profile["codex_version"] != args.expected_version:
                raise RuntimeError(f"host profile mismatch: {profile}")
            if digest(profile["codex_version_output"]) != evidence["version_output_sha256"]:
                raise RuntimeError("version output digest mismatch")
            for name in ("marketplace_add", "marketplace_remove", "plugin_add", "plugin_remove"):
                if profile["commands"][name]["sha256"] != evidence[f"{name}_help_sha256"]:
                    raise RuntimeError(f"{name} help digest mismatch")
            empty = manager._run_codex(["plugin", "list", "--json"], home_override=isolated_home)
            if digest(empty.stdout or empty.stderr or "") != evidence["plugin_list_empty_sha256"]:
                raise RuntimeError("empty plugin list digest mismatch")
            plugin = manager._isolated_plugin_preflight(profile)

            data_root = Path(td) / "events"
            denial = run_hook(
                "PreToolUse",
                {
                    "hookEventName": "PreToolUse", "toolName": "spawn_agent",
                    "toolUseId": "matrix-deny", "toolInput": {
                        "taskName": "matrix", "agentType": "worker",
                        "modelName": "gpt-5.6-sol", "reasoningEffort": "high",
                    },
                },
                data_root,
            )
            wire = denial.get("hookSpecificOutput") or {}
            if wire.get("hookEventName") != "PreToolUse" or wire.get("permissionDecision") != "deny":
                raise RuntimeError("PreToolUse deny envelope mismatch")
            for hook in ("Stop", "SubagentStop"):
                if run_hook(hook, {"hook_event_name": hook, "cwd": str(ROOT)}, data_root) != {}:
                    raise RuntimeError(f"{hook} did not return neutral JSON")
        finally:
            if original_home is None:
                os.environ.pop("CODEX_HOME", None)
            else:
                os.environ["CODEX_HOME"] = original_home

    print(json.dumps({
        "status": "PASS",
        "codex_version": args.expected_version,
        "registry_digest": canonical_digest(manager.COMPATIBILITY_REGISTRY),
        "artifact_sha256": artifact_report["tarball_sha256"] if artifact_report else "NOT_EVALUATED",
        "cli_contract": "CLI_CONTRACT_PASS",
        "isolated_plugin": plugin["status"],
        "synthetic_hook": "SYNTHETIC_HOOK_PASS",
        "real_host": "NOT_EVALUATED",
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"[ERROR] {exc}", file=sys.stderr)
        raise SystemExit(2)
