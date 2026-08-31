#!/usr/bin/env python3
"""Installed/source-tree entrypoint for cp_runtime."""
from __future__ import annotations

import sys
from pathlib import Path

runtime_root = Path(__file__).resolve().parents[1] / "runtime"
if str(runtime_root) not in sys.path:
    sys.path.insert(0, str(runtime_root))

from cp_runtime.cli import main  # noqa: E402


if __name__ == "__main__":
    main()
