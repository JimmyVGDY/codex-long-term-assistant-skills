#!/usr/bin/env python3
"""中文：显式 UX 基准采集器；不启动模型、不上传数据。

English: Explicit UX benchmark collector; it never starts a model or uploads data.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import statistics
import subprocess
import sys
import threading
import time
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Sequence

SCHEMA = "ux-benchmark/1"
MAX_SAMPLES = 1000
MAX_COMMAND_OUTPUT_BYTES = 1024 * 1024
MAX_FIXTURE_FILES = 200
MAX_FIXTURE_BYTES = 16 * 1024 * 1024
MAX_OBSERVATION_BYTES = 2 * 1024 * 1024
WHITELIST = {
    "schema", "scenario_id", "package_version", "source_sha", "fixture_digest", "os",
    "python_version", "approved_execution_profile", "cache_condition", "sample_id",
    "duration_ms", "tool_count", "auxiliary_read_chars", "confirmation_count",
    "subagent_count", "outcome", "repair_count", "limitations",
}


def _write(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _read(path: Path) -> Any:
    if path.is_symlink() or path.stat().st_size > MAX_OBSERVATION_BYTES:
        raise SystemExit("observation input is linked or exceeds the 2 MiB budget")
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _nearest_rank(values: Sequence[float], rank: int) -> float | None:
    if not values:
        return None
    return sorted(values)[min(len(values), max(1, rank)) - 1]


def _digest_fixture(path: Path | None) -> str:
    if path is None:
        return "UNKNOWN"
    digest = hashlib.sha256()
    if path.is_file():
        if path.is_symlink() or path.stat().st_size > MAX_FIXTURE_BYTES:
            raise SystemExit("fixture is linked or exceeds the byte budget")
        with path.open("rb") as handle:
            for block in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(block)
    elif path.is_dir():
        if path.is_symlink():
            raise SystemExit("fixture must not be a symbolic link")
        files = [item for item in path.rglob("*") if item.is_file()]
        if len(files) > MAX_FIXTURE_FILES:
            raise SystemExit("fixture exceeds the file-count budget")
        total = 0
        for item in sorted(files, key=lambda p: p.relative_to(path).as_posix()):
            if item.is_symlink():
                raise SystemExit("fixture contains a symbolic link")
            size = item.stat().st_size
            total += size
            if total > MAX_FIXTURE_BYTES:
                raise SystemExit("fixture exceeds the byte budget")
            digest.update(item.relative_to(path).as_posix().encode())
            with item.open("rb") as handle:
                for block in iter(lambda: handle.read(1024 * 1024), b""):
                    digest.update(block)
    else:
        return "MISSING"
    return digest.hexdigest()


def _run_command(command: Sequence[str], cwd: str | None, timeout_seconds: float,
                 max_output_bytes: int) -> tuple[int, bool, str]:
    environment = os.environ.copy()
    environment["PYTHONDONTWRITEBYTECODE"] = "1"
    try:
        process = subprocess.Popen(command, cwd=cwd or None, env=environment,
                                   stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    except OSError:
        return 127, False, "COMMAND_START_FAILED"
    holder: List[bytes] = []

    def read_output() -> None:
        assert process.stdout is not None
        holder.append(process.stdout.read(max_output_bytes + 1))

    reader = threading.Thread(target=read_output, daemon=True)
    reader.start()
    reader.join(max(0.05, timeout_seconds))
    timed_out = reader.is_alive()
    if timed_out:
        process.kill()
        reader.join(1.0)
    raw = holder[0] if holder else b""
    overflow = len(raw) > max_output_bytes
    if overflow:
        process.kill()
    try:
        returncode = process.wait(timeout=1.0)
    except subprocess.TimeoutExpired:
        process.kill()
        returncode = 124
    if process.stdout is not None:
        process.stdout.close()
    if timed_out:
        return returncode, False, "COMMAND_TIMEOUT"
    if overflow:
        return returncode, False, "COMMAND_OUTPUT_LIMIT_EXCEEDED"
    return returncode, returncode == 0, ""


def _summary(samples: Sequence[Mapping[str, Any]]) -> Dict[str, Any]:
    successful: List[float] = []
    for item in samples:
        if item.get("outcome") != "PASS":
            continue
        try:
            successful.append(float(item["duration_ms"]))
        except (KeyError, TypeError, ValueError):
            continue
    failures = sum(1 for item in samples if item.get("outcome") != "PASS")
    return {
        "sample_count": len(samples),
        "success_count": len(successful),
        "failure_count": failures,
        "median_duration_ms": statistics.median(successful) if successful else None,
        "min_duration_ms": min(successful) if successful else None,
        "max_duration_ms": max(successful) if successful else None,
        "p95_duration_ms": _nearest_rank(successful, 19),
    }


def collect(args: argparse.Namespace) -> None:
    command = json.loads(args.command_json)
    if not isinstance(command, list) or not command or any(not isinstance(item, str) for item in command):
        raise SystemExit("--command-json must be a non-empty JSON string array")
    if args.sample_count < 1 or args.sample_count > MAX_SAMPLES:
        raise SystemExit("--sample-count must be between 1 and 1000")
    if args.timeout_seconds <= 0:
        raise SystemExit("--timeout-seconds must be positive")
    if args.max_output_bytes < 1 or args.max_output_bytes > MAX_COMMAND_OUTPUT_BYTES:
        raise SystemExit("--max-output-bytes must be between 1 and 1048576")
    fixture = Path(args.fixture).expanduser().absolute() if args.fixture else None
    fixture_digest = args.fixture_digest or _digest_fixture(fixture)
    samples: List[Dict[str, Any]] = []
    for index in range(args.sample_count):
        started = time.monotonic()
        returncode, succeeded, limitation = _run_command(
            command, args.cwd, args.timeout_seconds, args.max_output_bytes,
        )
        duration_ms = round((time.monotonic() - started) * 1000, 3)
        samples.append({
            "schema": SCHEMA, "scenario_id": args.scenario_id, "package_version": args.package_version,
            "source_sha": args.source_sha, "fixture_digest": fixture_digest, "os": sys.platform,
            "python_version": sys.version.split()[0], "approved_execution_profile": args.execution_profile,
            "cache_condition": args.cache_condition, "sample_id": index + 1, "duration_ms": duration_ms,
            "tool_count": 1, "auxiliary_read_chars": "UNKNOWN", "confirmation_count": "UNKNOWN",
            "subagent_count": "UNKNOWN", "outcome": "PASS" if succeeded else ("UNKNOWN" if limitation else "FAILED"),
            "repair_count": "UNKNOWN", "limitations": ["command-output-not-persisted", "no-model-observation"] + ([limitation] if limitation else []),
        })
    _write(Path(args.output), {"schema": SCHEMA, "mode": "collect", "samples": samples,
                               "summary": _summary(samples), "command_omitted": True})


def import_observations(args: argparse.Namespace) -> None:
    source = _read(Path(args.input))
    raw = source.get("samples") if isinstance(source, dict) else source
    if not isinstance(raw, list):
        raise SystemExit("input must contain a samples array")
    if len(raw) > MAX_SAMPLES:
        raise SystemExit("input contains too many observations")
    samples: List[Dict[str, Any]] = []
    for item in raw:
        if not isinstance(item, dict):
            raise SystemExit("each observation must be an object")
        unknown = set(item) - WHITELIST
        if unknown:
            raise SystemExit("observation contains non-whitelisted fields: " + ",".join(sorted(unknown)))
        if item.get("schema") not in {None, SCHEMA}:
            raise SystemExit("unsupported observation schema")
        samples.append({key: item.get(key, "UNKNOWN") for key in WHITELIST})
        samples[-1]["schema"] = SCHEMA
    _write(Path(args.output), {"schema": SCHEMA, "mode": "import-observations", "samples": samples,
                               "summary": _summary(samples)})


def compare(args: argparse.Namespace) -> None:
    before = _read(Path(args.before))
    after = _read(Path(args.after))
    if before.get("schema") != SCHEMA or after.get("schema") != SCHEMA:
        raise SystemExit("both inputs must use ux-benchmark/1")
    before_samples = before.get("samples") or []
    after_samples = after.get("samples") or []
    before_scenarios = {item.get("scenario_id") for item in before_samples}
    after_scenarios = {item.get("scenario_id") for item in after_samples}
    if before_scenarios != after_scenarios or not before_scenarios or "UNKNOWN" in before_scenarios:
        raise SystemExit("scenario ids differ or are missing; refusing to compare")
    if any(not item.get("package_version") or not item.get("source_sha") for item in [*before_samples, *after_samples]):
        raise SystemExit("package_version and source_sha are required for comparison")
    before_fixture = {item.get("fixture_digest") for item in before_samples}
    after_fixture = {item.get("fixture_digest") for item in after_samples}
    if before_fixture != after_fixture:
        raise SystemExit("fixture digests differ; refusing to compare")
    before_summary = before.get("summary") or _summary(before_samples)
    after_summary = after.get("summary") or _summary(after_samples)
    before_median = before_summary.get("median_duration_ms")
    after_median = after_summary.get("median_duration_ms")
    _write(Path(args.output), {
        "schema": "ux-benchmark-compare/1", "before": before_summary, "after": after_summary,
        "fixture_digests": sorted(before_fixture),
        "median_delta_ms": (after_median - before_median) if before_median is not None and after_median is not None else None,
        "limitations": ["deterministic wrapper measurement only", "does not prove real Agent task improvement"],
    })


def main() -> int:
    parser = argparse.ArgumentParser(description="Explicit UX benchmark collector")
    sub = parser.add_subparsers(dest="command", required=True)
    collect_parser = sub.add_parser("collect")
    collect_parser.add_argument("--scenario-id", required=True)
    collect_parser.add_argument("--package-version", required=True)
    collect_parser.add_argument("--source-sha", required=True)
    collect_parser.add_argument("--fixture")
    collect_parser.add_argument("--fixture-digest")
    collect_parser.add_argument("--execution-profile", default="local")
    collect_parser.add_argument("--cache-condition", default="cold")
    collect_parser.add_argument("--sample-count", type=int, default=20)
    collect_parser.add_argument("--timeout-seconds", type=float, default=10.0)
    collect_parser.add_argument("--max-output-bytes", type=int, default=MAX_COMMAND_OUTPUT_BYTES)
    collect_parser.add_argument("--cwd")
    collect_parser.add_argument("--command-json", required=True)
    collect_parser.add_argument("--output", required=True)
    collect_parser.set_defaults(func=collect)
    import_parser = sub.add_parser("import-observations")
    import_parser.add_argument("--input", required=True)
    import_parser.add_argument("--output", required=True)
    import_parser.set_defaults(func=import_observations)
    compare_parser = sub.add_parser("compare")
    compare_parser.add_argument("--before", required=True)
    compare_parser.add_argument("--after", required=True)
    compare_parser.add_argument("--output", required=True)
    compare_parser.set_defaults(func=compare)
    args = parser.parse_args()
    args.func(args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
