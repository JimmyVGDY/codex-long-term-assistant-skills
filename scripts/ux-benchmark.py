#!/usr/bin/env python3
"""中文：显式采样与白名单统计，不自动调用模型或上传数据。

English: Explicit sampling and whitelisted statistics without automatic model calls or uploads.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import re
import statistics
import sys
import time
from pathlib import Path
from typing import Any, Mapping, Sequence

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "runtime"))
from cp_runtime.capability_store import CapabilityError, bounded_read, safe_path
from cp_runtime.common import scan_sensitive_text
from cp_runtime.resume_snapshot import SnapshotBudget, _bounded_process

SCHEMA = "ux-benchmark/1"
MAX_SAMPLES = 1000
MAX_COMMAND_OUTPUT_BYTES = 1024 * 1024
MAX_FIXTURE_FILES = 200
MAX_FIXTURE_BYTES = 16 * 1024 * 1024
MAX_OBSERVATION_BYTES = 2 * 1024 * 1024
IDENTITY_FIELDS = ("scenario_id", "fixture_digest", "os", "python_version",
                   "approved_execution_profile", "cache_condition")
COUNTS = {"tool_count", "auxiliary_read_chars", "confirmation_count", "subagent_count", "repair_count"}
WHITELIST = {
    "schema", "scenario_id", "package_version", "source_sha", "fixture_digest", "os",
    "python_version", "approved_execution_profile", "cache_condition", "sample_id",
    "duration_ms", "tool_count", "auxiliary_read_chars", "confirmation_count",
    "subagent_count", "outcome", "repair_count", "limitations",
}
OUTCOMES = {"PASS", "BLOCKED", "FAILED", "CANCELLED", "PARTIAL", "UNKNOWN"}


def _write(path: Path, value: Mapping[str, Any]) -> None:
    target = safe_path(path)
    if target == ROOT or ROOT in target.parents:
        raise SystemExit("benchmark output must be outside the package repository")
    raw = (json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True, allow_nan=False) + "\n").encode("utf-8")
    if len(raw) > MAX_OBSERVATION_BYTES:
        raise SystemExit("benchmark output exceeds the observation byte budget")
    target.parent.mkdir(parents=True, exist_ok=True)
    # 中文：不覆盖其他样本或把输出写回输入；每次采样使用新的显式目标。
    # English: Preserve prior samples and inputs; each run uses a fresh explicit output.
    with safe_path(target).open("xb") as stream:
        stream.write(raw)


def _read(path: Path) -> Any:
    try:
        return json.loads(bounded_read(path, MAX_OBSERVATION_BYTES).decode("utf-8-sig"),
                          parse_constant=lambda value: (_ for _ in ()).throw(ValueError("non-finite JSON")))
    except (CapabilityError, UnicodeError, ValueError) as exc:
        raise SystemExit("observation input is unreadable, unsafe or invalid") from exc


def _nearest_rank(values: Sequence[float], rank: int) -> float | None:
    return sorted(values)[min(len(values), max(1, rank)) - 1] if values else None


def _digest_fixture(path: Path | None) -> str:
    if path is None:
        return "UNKNOWN"
    root = safe_path(path)
    if not root.exists():
        raise SystemExit("explicit fixture does not exist")
    if root.is_file():
        return hashlib.sha256(bounded_read(root, MAX_FIXTURE_BYTES)).hexdigest()
    files: list[Path] = []
    pending = [root]
    directory_count = 0
    while pending:
        directory = pending.pop()
        directory_count += 1
        if directory_count > MAX_FIXTURE_FILES:
            raise SystemExit("fixture exceeds the directory budget")
        with os.scandir(directory) as entries:
            for entry in entries:
                if entry.name in {".git", "__pycache__"}:
                    continue
                checked = safe_path(Path(entry.path))
                if entry.is_dir(follow_symlinks=False):
                    pending.append(checked)
                    if len(pending) + directory_count > MAX_FIXTURE_FILES:
                        raise SystemExit("fixture exceeds the directory budget")
                elif entry.is_file(follow_symlinks=False):
                    files.append(checked)
                    if len(files) > MAX_FIXTURE_FILES:
                        raise SystemExit("fixture exceeds the file-count budget")
                else:
                    raise SystemExit("fixture contains a non-regular entry")
    digest = hashlib.sha256(b"ux-fixture-path-bytes/1\0")
    remaining = MAX_FIXTURE_BYTES
    for item in sorted(files, key=lambda value: value.relative_to(root).as_posix()):
        content = bounded_read(item, remaining)
        remaining -= len(content)
        digest.update(item.relative_to(root).as_posix().encode("utf-8"))
        digest.update(b"\0")
        digest.update(str(len(content)).encode())
        digest.update(b"\0")
        digest.update(hashlib.sha256(content).digest())
        digest.update(b"\0")
    return digest.hexdigest()


def _run_command(command: Sequence[str], cwd: str | None, timeout_seconds: float,
                 max_output_bytes: int) -> tuple[int, bool, str]:
    budget = SnapshotBudget(timeout=timeout_seconds, byte_limit=max_output_bytes)
    _raw, code, complete = _bounded_process(command, Path(cwd or "."), budget)
    if not complete or not budget.complete:
        reason = "COMMAND_OUTPUT_LIMIT_EXCEEDED" if any("OUTPUT" in item for item in budget.limitations) else "COMMAND_TIMEOUT"
        if code == 127:
            reason = "COMMAND_START_FAILED"
        return code, False, reason
    return code, code == 0, ""


def _observation(item: Any) -> dict[str, Any]:
    if not isinstance(item, dict) or set(item) - WHITELIST:
        raise SystemExit("observation contains invalid or non-whitelisted fields")
    if item.get("schema") not in {None, SCHEMA}:
        raise SystemExit("unsupported observation schema")
    value = {key: item.get(key, "UNKNOWN") for key in WHITELIST}
    value["schema"] = SCHEMA
    for key in WHITELIST - COUNTS - {"duration_ms", "sample_id", "limitations"}:
        if not isinstance(value[key], str) or len(value[key]) > 200:
            raise SystemExit("observation scalar is invalid: " + key)
    if value["outcome"] not in OUTCOMES:
        raise SystemExit("invalid observation outcome")
    for key in COUNTS:
        if value[key] != "UNKNOWN" and (type(value[key]) is not int or value[key] < 0):
            raise SystemExit("invalid observation count: " + key)
    duration = value["duration_ms"]
    if duration != "UNKNOWN" and (
            type(duration) not in {int, float} or not math.isfinite(duration) or duration < 0):
        raise SystemExit("invalid observation duration")
    sample_id = value["sample_id"]
    if type(sample_id) not in {str, int} or not str(sample_id) or len(str(sample_id)) > 128:
        raise SystemExit("invalid sample identity")
    limitations = item.get("limitations", [])
    if not isinstance(limitations, list) or len(limitations) > 20 or any(
            not isinstance(entry, str) or len(entry) > 300 for entry in limitations):
        raise SystemExit("invalid observation limitations")
    if scan_sensitive_text([str(value[key]) for key in value if key != "limitations"] + limitations):
        raise SystemExit("observation contains sensitive text")
    value["limitations"] = limitations
    return value


def _summary(samples: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    successful = [float(item["duration_ms"]) for item in samples
                  if item.get("outcome") == "PASS" and type(item.get("duration_ms")) in {int, float}
                  and math.isfinite(item["duration_ms"]) and item["duration_ms"] >= 0]
    success_count = sum(item.get("outcome") == "PASS" for item in samples)
    return {
        "sample_count": len(samples), "success_count": success_count,
        "failure_count": sum(item.get("outcome") in {"FAILED", "BLOCKED", "CANCELLED"} for item in samples),
        "unknown_or_partial_count": sum(item.get("outcome") in {"UNKNOWN", "PARTIAL"} for item in samples),
        "timing_sample_count": len(successful),
        "median_duration_ms": statistics.median(successful) if successful else None,
        "min_duration_ms": min(successful) if successful else None,
        "max_duration_ms": max(successful) if successful else None,
        "p95_duration_ms": _nearest_rank(successful, math.ceil(len(successful) * 0.95)) if len(successful) >= 20 else None,
    }


def collect(args: argparse.Namespace) -> None:
    command = _read(Path(args.command_file)) if getattr(args, "command_file", None) else json.loads(args.command_json)
    if not isinstance(command, list) or not command or any(not isinstance(item, str) for item in command):
        raise SystemExit("command must be a non-empty JSON string array")
    if not 1 <= args.sample_count <= MAX_SAMPLES:
        raise SystemExit("--sample-count must be between 1 and 1000")
    if not math.isfinite(args.timeout_seconds) or args.timeout_seconds <= 0:
        raise SystemExit("--timeout-seconds must be positive and finite")
    if not 1 <= args.max_output_bytes <= MAX_COMMAND_OUTPUT_BYTES:
        raise SystemExit("--max-output-bytes must be between 1 and 1048576")
    fixture = Path(args.fixture) if args.fixture else None
    actual_digest = _digest_fixture(fixture)
    if fixture and args.fixture_digest and args.fixture_digest != actual_digest:
        raise SystemExit("declared fixture digest does not match actual fixture bytes")
    fixture_digest = args.fixture_digest or actual_digest
    samples = []
    for index in range(args.sample_count):
        started = time.monotonic()
        code, success, limitation = _run_command(command, args.cwd, args.timeout_seconds, args.max_output_bytes)
        sample = {
            "schema": SCHEMA, "scenario_id": args.scenario_id, "package_version": args.package_version,
            "source_sha": args.source_sha, "fixture_digest": fixture_digest, "os": sys.platform,
            "python_version": sys.version.split()[0], "approved_execution_profile": args.execution_profile,
            "cache_condition": args.cache_condition, "sample_id": index + 1,
            "duration_ms": round((time.monotonic() - started) * 1000, 3), "tool_count": 1,
            "auxiliary_read_chars": "UNKNOWN", "confirmation_count": "UNKNOWN", "subagent_count": "UNKNOWN",
            "outcome": "PASS" if success else ("UNKNOWN" if limitation else "FAILED"),
            "repair_count": "UNKNOWN",
            "limitations": ["command-output-not-persisted", "process-exit-only", "semantic-result-requires-fixture-oracle"]
                          + ([limitation] if limitation else []),
        }
        samples.append(_observation(sample))
    if fixture and actual_digest != _digest_fixture(fixture):
        raise SystemExit("fixture changed during collection; samples are not comparable")
    _write(Path(args.output), {"schema": SCHEMA, "mode": "collect", "samples": samples,
                              "summary": _summary(samples), "command_omitted": True})


def import_observations(args: argparse.Namespace) -> None:
    source = _read(Path(args.input))
    raw = source.get("samples") if isinstance(source, dict) else source
    if not isinstance(raw, list) or len(raw) > MAX_SAMPLES:
        raise SystemExit("input must contain at most 1000 observations")
    samples = [_observation(item) for item in raw]
    _write(Path(args.output), {"schema": SCHEMA, "mode": "import-observations",
                              "samples": samples, "summary": _summary(samples)})


def _comparison_samples(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, dict) or value.get("schema") != SCHEMA:
        raise SystemExit("comparison inputs must use ux-benchmark/1")
    raw = value.get("samples")
    if not isinstance(raw, list) or not 1 <= len(raw) <= MAX_SAMPLES:
        raise SystemExit("comparison requires a bounded non-empty sample set")
    samples = [_observation(item) for item in raw]
    for key in (*IDENTITY_FIELDS, "package_version", "source_sha"):
        values = {item[key] for item in samples}
        if len(values) != 1 or values & {"", "UNKNOWN", "MISSING"}:
            raise SystemExit("comparison requires one complete identity per batch: " + key)
    if not re.fullmatch(r"[a-f0-9]{40}|[a-f0-9]{64}", samples[0]["source_sha"]):
        raise SystemExit("comparison requires a full source SHA")
    if not re.fullmatch(r"[a-f0-9]{64}", samples[0]["fixture_digest"]):
        raise SystemExit("comparison requires a complete fixture digest")
    ids = [str(item["sample_id"]) for item in samples]
    if len(ids) != len(set(ids)) or "UNKNOWN" in ids:
        raise SystemExit("comparison sample identifiers are missing or duplicated")
    return samples


def compare(args: argparse.Namespace) -> None:
    before_samples = _comparison_samples(_read(Path(args.before)))
    after_samples = _comparison_samples(_read(Path(args.after)))
    if any(before_samples[0][key] != after_samples[0][key] for key in IDENTITY_FIELDS):
        raise SystemExit("scenario, fixture, or execution environment differs; refusing comparison")
    before, after = _summary(before_samples), _summary(after_samples)
    left, right = before["median_duration_ms"], after["median_duration_ms"]
    _write(Path(args.output), {
        "schema": "ux-benchmark-compare/1", "before": before, "after": after,
        "fixture_digests": [before_samples[0]["fixture_digest"]],
        "median_delta_ms": right - left if left is not None and right is not None else None,
        "limitations": ["statistics-recomputed-from-samples", "quality-and-causality-require-independent-evidence"],
    })


def main() -> int:
    parser = argparse.ArgumentParser(description="Explicit UX benchmark collector")
    sub = parser.add_subparsers(dest="command", required=True)
    collect_parser = sub.add_parser("collect")
    for name in ("scenario-id", "package-version", "source-sha"):
        collect_parser.add_argument("--" + name, required=True)
    collect_parser.add_argument("--fixture")
    collect_parser.add_argument("--fixture-digest")
    collect_parser.add_argument("--execution-profile", default="local")
    collect_parser.add_argument("--cache-condition", default="cold")
    collect_parser.add_argument("--sample-count", type=int, default=20)
    collect_parser.add_argument("--timeout-seconds", type=float, default=10.0)
    collect_parser.add_argument("--max-output-bytes", type=int, default=MAX_COMMAND_OUTPUT_BYTES)
    collect_parser.add_argument("--cwd")
    commands = collect_parser.add_mutually_exclusive_group(required=True)
    commands.add_argument("--command-json")
    commands.add_argument("--command-file")
    collect_parser.add_argument("--output", required=True)
    collect_parser.set_defaults(func=collect)
    importer = sub.add_parser("import-observations")
    importer.add_argument("--input", required=True)
    importer.add_argument("--output", required=True)
    importer.set_defaults(func=import_observations)
    comparison = sub.add_parser("compare")
    for name in ("before", "after", "output"):
        comparison.add_argument("--" + name, required=True)
    comparison.set_defaults(func=compare)
    args = parser.parse_args()
    try:
        args.func(args)
    except (CapabilityError, OSError, ValueError) as exc:
        print("[ERROR] benchmark operation failed: " + type(exc).__name__, file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
