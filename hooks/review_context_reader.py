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
        raw = stream.read(524289)
    if len(raw) > 524288:
        raise ValueError("READER_SIZE")
    grant = json.loads(raw)
    if grant.get('delivery_contract')=='same-call-notify/2':
        # 中文：隔离模式读取器只导入受管同目录运行时，不从调用方工作目录导入。
        # English: -I reader imports only its managed sibling runtime, never caller cwd.
        managed=Path(__file__).absolute().parent.parent/'runtime'
        for part in (managed,*managed.parents):
            info=part.lstat()
            if stat.S_ISLNK(info.st_mode) or getattr(info,'st_file_attributes',0)&0x400:raise ValueError('READER_RUNTIME_REPARSE')
        sys.path.insert(0,str(managed))
        from cp_runtime import notify_wire
        if Path(notify_wire.__file__).absolute().parent!=managed/'cp_runtime':raise ValueError('READER_RUNTIME_ORIGIN')
        wire=json.loads(grant['wire'])
        summary=wire['summary'];binding={k:summary[k] for k in ('bundle_ref','packet_sha256','baseline_sha256')}
        notify_wire.validate_grant(grant,binding)
        sys.stdout.buffer.write(grant['wire'].encode('utf8'));sys.stdout.buffer.flush();return
    if 'delivery_contract' in grant or len(raw)>131072:raise ValueError('READER_LEGACY_BOUND')
    output = grant["output"].encode("utf-8")
    profile = grant.get("context_profile")
    if profile not in {None, "bounded-review-64k/1"}:
        raise ValueError("READER_PROFILE")
    maximum = 65536 if profile == "bounded-review-64k/1" else 8192
    if hashlib.sha256(output).hexdigest() != grant["output_sha256"] or len(output) > maximum:
        raise ValueError("READER_INTEGRITY")
    sys.stdout.buffer.write(output)
    sys.stdout.buffer.flush()

if __name__ == "__main__":
    try:
        main()
    except Exception:
        sys.stderr.write("CONTEXT_READER_FAILED\n")
        sys.exit(1)
