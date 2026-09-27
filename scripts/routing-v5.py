#!/usr/bin/env python3
"""中文：显式启用的桌面 V2 上下文管理。English: Internal management for opt-in Desktop V2 context transport."""
import runpy
import sys
from pathlib import Path
sys.dont_write_bytecode = True
if __name__ == "__main__":
    runpy.run_path(str(Path(__file__).resolve().parents[1] /
        "skills/multi-agent-independent-review/scripts/routing_v5.py"), run_name="__main__")
