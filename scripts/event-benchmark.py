#!/usr/bin/env python3
"""中文：全历史 TaskOutcomeEvent 追加行为的显式本机基准。

English: Explicit local benchmark for full-history TaskOutcomeEvent append behavior.

中文：它在源码树外创建合成且独立核验的 fixture；构造时间不计入追加耗时，且仅在显式调用时运行。
English: It creates synthetic, independently verified fixtures outside the source tree. Fixture construction is excluded from append timings and the tool runs only when explicitly called.
"""
from __future__ import annotations

import argparse
import importlib
import json
import statistics
import sys
import time
import tracemalloc
from pathlib import Path
from typing import Any


def percentile(values: list[float], fraction: float) -> float | None:
    if not values:
        return None
    return sorted(values)[min(len(values) - 1, max(0, int(len(values) * fraction + 0.999999) - 1))]


def load_events(root: Path):
    sys.path.insert(0, str(root / "runtime"))
    return importlib.import_module("cp_runtime.event_v2")


def event(index: int) -> dict[str, Any]:
    return {"event_id": "EVT_benchmark_%06d" % index, "event_type": "TURN_OPENED",
            "captured_at": "2026-09-22T00:%02d:%02d.000+00:00" % ((index // 60) % 60, index % 60),
            "project_id": "benchmark-project", "repo_fingerprint": "sha256:" + "b" * 64,
            "session_id": "session-%d" % index, "turn_id": "turn-%d" % index, "task_id": "task-%d" % index}


def write_fixture(events_module: Any, path: Path, count: int, segmented: bool) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    rows: list[str] = []
    previous = events_module.ZERO_HASH
    for index in range(count):
        payload = events_module.make_event(event(index))
        digest = events_module.sha256_hex(previous + "\n" + events_module.canonical_json(payload))
        rows.append(events_module.canonical_json({**payload, "previous_hash": previous, "record_hash": digest}) + "\n")
        previous = digest
    if segmented and count > 1:
        midpoint = max(1, count // 2)
        path.with_name(path.stem + ".segment-000001" + path.suffix).write_text("".join(rows[:midpoint]), encoding="utf-8")
        path.write_text("".join(rows[midpoint:]), encoding="utf-8")
    else:
        path.write_text("".join(rows), encoding="utf-8")
    verified = events_module.verify_event_chain(path)
    if verified["record_count"] != count:
        raise RuntimeError("fixture verification count mismatch")


def measure(events_module: Any, fixture_root: Path, count: int, samples: int, segmented: bool) -> dict[str, Any]:
    timings: list[float] = []
    lock_holds: list[float] = []
    peaks: list[int] = []
    read_bytes: list[int] = []
    original_lock = events_module.OwnerTokenLock
    for sample in range(samples):
        path = fixture_root / ("events-%d-%d.jsonl" % (count, sample))
        write_fixture(events_module, path, count, segmented)
        read_bytes.append(sum(item.stat().st_size for item in [*events_module.event_segment_paths(path), path] if item.exists()))
        held: list[float] = []
        class TimingLock:
            def __init__(self, *args: Any, **kwargs: Any) -> None:
                self.inner = original_lock(*args, **kwargs)
            def __enter__(self):
                self.inner.__enter__(); self.started = time.perf_counter(); return self
            def __exit__(self, *args: Any) -> None:
                held.append((time.perf_counter() - self.started) * 1000); self.inner.__exit__(*args)
        events_module.OwnerTokenLock = TimingLock
        tracemalloc.start()
        started = time.perf_counter()
        try:
            events_module.append_event(path, event(count))
        finally:
            elapsed = (time.perf_counter() - started) * 1000
            _current, peak = tracemalloc.get_traced_memory()
            tracemalloc.stop()
            events_module.OwnerTokenLock = original_lock
        if events_module.verify_event_chain(path)["record_count"] != count + 1:
            raise RuntimeError("append result did not verify")
        timings.append(elapsed); lock_holds.extend(held); peaks.append(peak)
    return {"event_count_before_append": count, "segmented": segmented, "sample_count": samples,
            "append_median_ms": statistics.median(timings), "append_p95_ms": percentile(timings, .95),
            "read_bytes_median": statistics.median(read_bytes), "lock_hold_median_ms": statistics.median(lock_holds),
            "lock_hold_p95_ms": percentile(lock_holds, .95), "peak_memory_bytes_median": statistics.median(peaks)}


def main() -> int:
    parser = argparse.ArgumentParser(description="Explicit full-history event append benchmark")
    parser.add_argument("--runtime-root", required=True, help="Repository root to benchmark")
    parser.add_argument("--fixture-root", required=True, help="External writable fixture directory")
    parser.add_argument("--output", required=True)
    parser.add_argument("--sizes", default="100,1000,10000")
    parser.add_argument("--samples", type=int, default=20)
    parser.add_argument("--segmented", action="store_true")
    args = parser.parse_args()
    if not 1 <= args.samples <= 100:
        raise SystemExit("--samples must be between 1 and 100")
    sizes = [int(value) for value in args.sizes.split(",")]
    if any(value < 1 or value > 100000 for value in sizes):
        raise SystemExit("sizes must be between 1 and 100000")
    module = load_events(Path(args.runtime_root).resolve())
    fixture_root = Path(args.fixture_root).resolve()
    report = {"schema": "event-benchmark/1", "runtime_root": str(Path(args.runtime_root).resolve()),
              "samples": args.samples, "segmented": args.segmented,
              "results": [measure(module, fixture_root, size, args.samples, args.segmented) for size in sizes],
              "limitations": ["synthetic-fixture", "fixture-build-excluded-from-append-timing", "full-history-verification-retained"]}
    Path(args.output).write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
