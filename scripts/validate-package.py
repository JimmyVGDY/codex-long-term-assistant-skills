#!/usr/bin/env python3
from pathlib import Path
import runpy
runpy.run_path(str(Path(__file__).with_name('validate-v72.py')),run_name='__main__')
