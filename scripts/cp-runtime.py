#!/usr/bin/env python3
"""中文：已安装或源码树中的 cp_runtime 入口。

English: Installed or source-tree entry point for cp_runtime.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path


def _runtime_candidates(package_home: Path):
    """中文：Plugin 模式只使用状态绑定缓存；源码/standalone 使用本地 runtime。

    English: Plugin mode uses only its state-bound cache; source and standalone modes use
    the local runtime tree.
    """
    state_path = package_home / "cp-assistant-v6-state.json"
    try:
        state = json.loads(state_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        if Path(__file__).resolve().parent.name == "scripts" and (package_home / "manifest.json").is_file():
            yield package_home / "runtime"
        return
    if state.get("mode") == "standalone":
        yield package_home / "runtime"
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
    marker = Path("cp_runtime") / "cli.py"
    for candidate in _runtime_candidates(package_home):
        try:
            if (candidate / marker).is_file():
                return candidate
        except OSError:
            continue
    raise ModuleNotFoundError(
        "找不到 cp_runtime；请重新运行当前版本 package_manager.py install/verify"
    )


package_home = Path(__file__).resolve().parents[1]
runtime_root = _select_runtime(package_home)
if str(runtime_root) not in sys.path:
    sys.path.insert(0, str(runtime_root))

from cp_runtime.cli import main  # noqa: E402


if __name__ == "__main__":
    main()
