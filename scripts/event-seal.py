#!/usr/bin/env python3
"""Create or verify detached HMAC seals for a TaskOutcomeEvent V2 chain."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "runtime"))
from cp_runtime.integrity import IntegrityError, seal_event_chain, verify_event_seals  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description="V6.6 event chain seal")
    parser.add_argument("command", choices=["create", "verify"])
    parser.add_argument("--event-file", required=True)
    parser.add_argument("--seal-file")
    parser.add_argument("--keyring")
    args = parser.parse_args()
    keyword = {"seal_path": Path(args.seal_file) if args.seal_file else None,
               "keyring_path": Path(args.keyring) if args.keyring else None}
    result = seal_event_chain(Path(args.event_file), **keyword) if args.command == "create" \
        else verify_event_seals(Path(args.event_file), **keyword)
    print(json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2))


if __name__ == "__main__":
    try:
        main()
    except IntegrityError as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False), file=sys.stderr)
        raise SystemExit(2)
