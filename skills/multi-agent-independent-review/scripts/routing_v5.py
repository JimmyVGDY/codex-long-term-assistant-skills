#!/usr/bin/env python3
"""中文：桌面增强的受管内部入口；English: managed internal Desktop context entry."""
from __future__ import annotations
import runpy
import sys
from pathlib import Path
sys.dont_write_bytecode = True
entry = Path(__file__).resolve()
if entry.parent.name == "tools":
    # 中文：复用已有状态绑定缓存解析，不回退到陈旧运行时。
    # English: Reuse state-bound cache resolution; never fall back to a stale runtime.
    runpy.run_path(str(entry.with_name("cp-runtime.py")), run_name="cp_runtime_bootstrap")
else:
    sys.path.insert(0, str(entry.parents[3] / "runtime"))
from cp_runtime.routing_cli_v5 import main
if __name__ == "__main__":
    main()
