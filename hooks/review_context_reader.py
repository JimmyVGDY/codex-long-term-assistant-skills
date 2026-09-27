#!/usr/bin/env python3
"""中文：只读固定许可；English: bounded reader; no imports from a caller-controlled directory."""
import hashlib
import json
import os
import stat
import sys
from pathlib import Path

sys.dont_write_bytecode = True

def main():
    if len(sys.argv) != 2:
        raise ValueError("READER_ARGUMENTS")
    path = Path(sys.argv[1])
    if not path.is_absolute() or ".." in path.parts or (os.name == "nt" and any(":" in p for p in path.parts[1:])):
        raise ValueError("READER_PATH")
    for part in (path, *path.parents):
        info = part.lstat()
        if stat.S_ISLNK(info.st_mode) or getattr(info, "st_file_attributes", 0) & 0x400:
            raise ValueError("READER_REPARSE")
    with path.open("rb") as stream:
        raw = stream.read(131073)
    if len(raw) > 131072:
        raise ValueError("READER_SIZE")
    grant = json.loads(raw)
    output = grant["output"].encode("utf-8")
    if hashlib.sha256(output).hexdigest() != grant["output_sha256"] or len(output) > 8192:
        raise ValueError("READER_INTEGRITY")
    sys.stdout.buffer.write(output)
    sys.stdout.buffer.flush()

if __name__ == "__main__":
    try:
        main()
    except Exception:
        sys.stderr.write("CONTEXT_READER_FAILED\n")
        sys.exit(1)
