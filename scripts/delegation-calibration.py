#!/usr/bin/env python3
"""Offline replay for parent-finalized DelegationBudget calibration samples."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "runtime"))
from cp_runtime.delegation_budget import DelegationBudgetError  # noqa: E402
from cp_runtime.delegation_calibration import load_samples, offline_replay  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--samples", required=True)
    parser.add_argument("--ledger", required=True)
    parser.add_argument("--minimum-samples-per-profile", type=int, default=3)
    args = parser.parse_args()
    try:
        ledger = Path(args.ledger).expanduser().resolve()
        result = offline_replay(load_samples(Path(args.samples).expanduser().resolve(), ledger_path=ledger),
                                ledger_path=ledger,
                                minimum_samples_per_profile=args.minimum_samples_per_profile)
    except (DelegationBudgetError, OSError, ValueError, json.JSONDecodeError) as exc:
        print("[FAIL] " + str(exc), file=sys.stderr); return 2
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
