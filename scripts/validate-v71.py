#!/usr/bin/env python3
"""中文：保留旧 V7.1 验证命令入口，并转发到当前验证器。

English: Preserve the former V7.1 validation entry point and forward it to the current validator.
"""
from __future__ import annotations

import runpy
from pathlib import Path


runpy.run_path(str(Path(__file__).with_name("validate-v72.py")), run_name="__main__")
