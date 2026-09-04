#!/usr/bin/env python3
"""中文：下载固定的官方 Codex 包并校验两种登记摘要。

English: Download one frozen official Codex tarball and verify both registered digests.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from codex_compatibility import (  # noqa: E402
    CompatibilityError, load_registry, profile_for_version, verify_artifact_file,
)

MAX_ARTIFACT_BYTES = 256 * 1024 * 1024


def download(version: str, output: Path) -> dict:
    registry = load_registry(ROOT / "config" / "codex-compatibility-v1.json", "7.4.3")
    profile = profile_for_version(registry, version)
    output = output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            prefix=output.name + ".", suffix=".tmp", dir=output.parent, delete=False,
        ) as handle:
            temporary = Path(handle.name)
            request = urllib.request.Request(
                profile["artifact"]["tarball"],
                headers={"User-Agent": "codex-long-term-assistant-skills/7.4.3"},
            )
            with urllib.request.urlopen(request, timeout=120) as response:
                total = 0
                while True:
                    chunk = response.read(1024 * 1024)
                    if not chunk:
                        break
                    total += len(chunk)
                    if total > MAX_ARTIFACT_BYTES:
                        raise CompatibilityError("Codex 固定制品超过大小上限")
                    handle.write(chunk)
            handle.flush()
            os.fsync(handle.fileno())
        report = verify_artifact_file(registry, version, temporary)
        os.replace(temporary, output)
        report["path"] = str(output)
        return report
    finally:
        if temporary is not None and temporary.exists():
            temporary.unlink()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--version", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    try:
        report = download(args.version, Path(args.output))
    except Exception as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 2
    print(json.dumps({"ok": True, **report}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
