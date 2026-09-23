#!/usr/bin/env python3
"""中文：已安装桌面插件的路由管理入口。 English: Installed Desktop plugin routing entry."""
from __future__ import annotations

import runpy
import sys
from pathlib import Path

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "runtime"))
if __name__ == "__main__":
    runpy.run_module("cp_runtime.routing_cli_v4", run_name="__main__")
