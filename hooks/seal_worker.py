#!/usr/bin/env python3
"""中文：已安装 Plugin 的延迟 SessionEnd 追加与封印入口。

English: Installed Plugin entry point for delayed SessionEnd append and sealing.
"""
from __future__ import annotations

import argparse
import base64
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "runtime"))
from cp_runtime.seal_queue import (  # noqa: E402
    BOOTSTRAP_EVENT_MAX_BYTES, SealQueueError, prepare_session_end, process_queue,
)


def main() -> None:
    parser = argparse.ArgumentParser(description="V6.6 delayed event seal worker")
    parser.add_argument("--queue", required=True); parser.add_argument("--keyring")
    parser.add_argument("--max-jobs", type=int, default=100)
    parser.add_argument("--bootstrap-event-b64"); args = parser.parse_args()
    queue = Path(args.queue)
    keyring = Path(args.keyring) if args.keyring else None
    if args.bootstrap_event_b64:
        try:
            raw = base64.b64decode(args.bootstrap_event_b64.encode("ascii"), altchars=b"-_", validate=True)
        except (UnicodeError, ValueError) as exc:
            raise SealQueueError("BOOTSTRAP_EVENT_INVALID") from exc
        if len(raw) > BOOTSTRAP_EVENT_MAX_BYTES:
            raise SealQueueError("BOOTSTRAP_EVENT_TOO_LARGE")
        try:
            event = json.loads(raw.decode("utf-8"))
        except (UnicodeError, ValueError) as exc:
            raise SealQueueError("BOOTSTRAP_EVENT_INVALID") from exc
        if not isinstance(event, dict):
            raise SealQueueError("BOOTSTRAP_EVENT_INVALID")
        prepare_session_end(queue, event, keyring)
    report = process_queue(queue, keyring, args.max_jobs)
    print(json.dumps(report, ensure_ascii=False, sort_keys=True))
    if not report["ok"]: raise SystemExit(2)


if __name__ == "__main__":
    try: main()
    except SealQueueError as exc:
        print(json.dumps({"ok": False, "error_code": str(exc)}, ensure_ascii=False), file=sys.stderr)
        raise SystemExit(2)
