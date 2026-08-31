#!/usr/bin/env python3
"""V6.5 controlled-evolution CLI for source-tree and installed usage."""
from __future__ import annotations

import sys
from pathlib import Path

package_home = Path(__file__).resolve().parents[1]
runtime_root = package_home / "runtime"
if str(runtime_root) not in sys.path:
    sys.path.insert(0, str(runtime_root))

from cp_runtime.evolution.cli import main  # noqa: E402


if __name__ == "__main__":
    raise SystemExit(main())
