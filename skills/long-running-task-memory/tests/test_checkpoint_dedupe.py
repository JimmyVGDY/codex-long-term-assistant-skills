#!/usr/bin/env python3
"""Regression test for idempotent checkpoint append and V5.0 inherited defaults."""
from __future__ import annotations

import re
import subprocess
import sys
import tempfile
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "checkpoint.py"


def run(*args: str) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if result.returncode != 0:
        raise AssertionError(result.stdout + result.stderr)
    return result


def count_entries(progress: Path) -> int:
    return len(re.findall(r"(?m)^### CP-", progress.read_text(encoding="utf-8")))


with tempfile.TemporaryDirectory(prefix="checkpoint-v50-") as temp:
    memory = Path(temp) / "memory"
    run("init", "--project-dir", str(memory), "--task-id", "T1", "--title", "test")
    args = (
        "append",
        "--project-dir",
        str(memory),
        "--task-id",
        "T1",
        "--node-type",
        "analysis",
        "--summary",
        "completed one stable node",
        "--next-action",
        "verify the next bounded node",
        "--stage",
        "PLAN",
    )
    first = run(*args)
    assert "已写入检查点" in first.stdout
    progress = memory / "PROGRESS.md"
    assert count_entries(progress) == 1

    duplicate = run(*args)
    assert "未重复写入" in duplicate.stdout
    assert count_entries(progress) == 1

    run(*args, "--force-append")
    assert count_entries(progress) == 2

    current = (memory / "CURRENT_TASK.md").read_text(encoding="utf-8")
    assert "0 / 8" in current
    assert "最近恢复读取检查点：3" in current
    assert "活跃检查点上限：20" in current

print("checkpoint dedupe tests passed")
