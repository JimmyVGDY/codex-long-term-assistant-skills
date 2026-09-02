#!/usr/bin/env python3
"""中文：源码树与安装环境共用的 V7 受控演进命令行入口。

English: V7 controlled-evolution CLI for source-tree and installed usage.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path


def _runtime_candidates(package_home: Path):
    """优先使用源码/standalone runtime，再回退到安装状态绑定的 Plugin cache。"""
    yield package_home / "runtime"
    state_path = package_home / "cp-assistant-v6-state.json"
    try:
        state = json.loads(state_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return
    if state.get("mode") != "plugin":
        return
    version = str(state.get("version") or "")
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,63}", version):
        return
    yield (
        package_home
        / "plugins"
        / "cache"
        / "cp-assistant-local"
        / "codex-cross-project-engineering-assistant"
        / version
        / "runtime"
    )


def _select_runtime(package_home: Path) -> Path:
    marker = Path("cp_runtime") / "evolution" / "cli.py"
    for candidate in _runtime_candidates(package_home):
        try:
            if (candidate / marker).is_file():
                return candidate
        except OSError:
            continue
    raise ModuleNotFoundError(
        "找不到 cp_runtime.evolution；请重新运行当前版本 package_manager.py install/verify"
    )


package_home = Path(__file__).resolve().parents[1]
runtime_root = _select_runtime(package_home)
if str(runtime_root) not in sys.path:
    sys.path.insert(0, str(runtime_root))

from cp_runtime.evolution.cli import main  # noqa: E402


if __name__ == "__main__":
    raise SystemExit(main())
