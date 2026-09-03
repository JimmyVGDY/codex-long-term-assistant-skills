#!/usr/bin/env python3
"""中文：保留旧 V7.3 入口，作为当前验证器的兼容别名。

English: Legacy V7.3 entrypoint retained as an alias for the current validator.
"""
from pathlib import Path
import runpy

runpy.run_path(str(Path(__file__).with_name("validate-v74.py")), run_name="__main__")
