#!/usr/bin/env python3
"""中文：绑定实际产物的有界离线比较；不调用模型、不执行产物、不推断语义成功。
English: Bounded offline comparisons bound to actual artifacts; no model calls, artifact execution, or inferred semantic success.
"""
from __future__ import annotations

import argparse
import base64
import binascii
from functools import lru_cache
import hashlib
import html
import importlib.util
import json
import math
import os
from pathlib import Path, PurePosixPath
import re
import stat
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "runtime"))
from cp_runtime.capability_store import (
    CapabilityError, bounded_read, safe_path, DENIED_NAMES, DENIED_PARTS,
)
from cp_runtime.common import scan_sensitive_text

MAX_FILES = 256
MAX_DIRECTORIES = 128
MAX_FILE_BYTES = 2 * 1024 * 1024
MAX_TOTAL_BYTES = 16 * 1024 * 1024
MAX_JSON_BYTES = 2 * 1024 * 1024
MAX_PREVIEW_BYTES = 64 * 1024
MAX_PREVIEW_TOTAL = 4 * 1024 * 1024
MAX_PNG_BYTES = 1024 * 1024
MAX_PREVIEW_PIXELS = 16 * 1024 * 1024
HASH = re.compile(r"[0-9a-f]{64}\Z")
IDENTIFIER = re.compile(r"[a-zA-Z0-9][a-zA-Z0-9_.-]{0,95}\Z")
INPUT_FIELDS = {
    "schema", "study_id", "case_id", "sample_id", "variant", "fixture_digest",
    "rule_digest", "source_sha", "environment", "initial_files", "allowed_changes",
    "artifacts", "checks", "metrics", "rule_files",
}
ENV_FIELDS = {"platform", "runtime", "requested_model", "requested_effort",
              "permissions_digest", "cache_condition"}
METRICS = {"duration_ms", "tool_count", "auxiliary_read_chars", "confirmation_count",
           "subagent_count", "repair_count"}


class EvalError(ValueError):
    pass


def require(condition, code):
    if not condition:
        raise EvalError(code)


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True,
                      separators=(",", ":"), allow_nan=False).encode("utf-8")


def digest(value):
    return hashlib.sha256(value).hexdigest()


def _unique(pairs):
    result = {}
    for key, value in pairs:
        require(key not in result, "DUPLICATE_JSON_KEY")
        result[key] = value
    return result


def _nonfinite(_):
    raise EvalError("NONFINITE_JSON")


def read_json(path):
    raw = bounded_read(Path(path), MAX_JSON_BYTES)
    try:
        value = json.loads(raw.decode("utf-8-sig"), object_pairs_hook=_unique,
                           parse_constant=_nonfinite)
    except (UnicodeError, json.JSONDecodeError, RecursionError) as exc:
        raise EvalError("INVALID_JSON") from exc
    require(isinstance(value, dict), "JSON_OBJECT_REQUIRED")
    return value


def relative(value):
    require(isinstance(value, str) and 0 < len(value) <= 500, "INVALID_PATH")
    require("\\" not in value and ":" not in value, "INVALID_PATH")
    parts = value.split("/")
    require(not PurePosixPath(value).is_absolute()
            and all(p not in {"", ".", ".."} and not any(ord(c) < 32 for c in p)
                    for p in parts), "PATH_ESCAPE")
    lower = [p.lower() for p in parts]
    require(not any(p in DENIED_PARTS or p.startswith(".env") for p in lower)
            and lower[-1] not in DENIED_NAMES, "SENSITIVE_PATH")
    require(Path(value).suffix.lower() not in {".pem", ".key", ".p12", ".pfx"},
            "SENSITIVE_PATH")
    return value


def external(path):
    target = safe_path(Path(path))
    require(target != ROOT and ROOT not in target.parents, "OUTPUT_INSIDE_REPOSITORY")
    return target


def text_value(value, limit=500):
    require(isinstance(value, str) and 0 < len(value) <= limit
            and "\x00" not in value, "INVALID_TEXT")
    require(not scan_sensitive_text([value]), "SENSITIVE_CONTENT")


def snapshot(directory):
    """中文：有界遍历普通文件，拒绝链接、特殊文件和并发变化。
    English: Bounded traversal of regular files; reject links, special files, and concurrent changes.
    """
    root = external(directory)
    require(root.is_dir(), "ARTIFACT_DIRECTORY_REQUIRED")
    queue, directories, result, total = [root], 0, {}, 0
    while queue:
        current = safe_path(queue.pop())
        directories += 1
        require(directories <= MAX_DIRECTORIES, "DIRECTORY_LIMIT")
        with os.scandir(current) as entries:
            for entry in entries:
                path = safe_path(Path(entry.path))
                name = relative(path.relative_to(root).as_posix())
                info = path.lstat()
                require(not (getattr(info, "st_file_attributes", 0) & 0x400)
                        and not stat.S_ISLNK(info.st_mode), "LINK_REJECTED")
                if stat.S_ISDIR(info.st_mode):
                    require(len(queue) + directories < MAX_DIRECTORIES, "DIRECTORY_LIMIT")
                    queue.append(path)
                else:
                    require(stat.S_ISREG(info.st_mode) and info.st_nlink == 1,
                            "NONREGULAR_OR_HARDLINK")
                    require(len(result) < MAX_FILES, "FILE_COUNT_LIMIT")
                    raw = bounded_read(path, min(MAX_FILE_BYTES, MAX_TOTAL_BYTES - total))
                    total += len(raw)
                    require(total <= MAX_TOTAL_BYTES, "TOTAL_BYTE_LIMIT")
                    result[name] = {"sha256": digest(raw), "size": len(raw)}
    return dict(sorted(result.items()))


def validate_input(value):
    require(set(value) == INPUT_FIELDS and value["schema"] == "skill-eval-input/1",
            "INPUT_SCHEMA")
    for key in ("study_id", "case_id", "sample_id"):
        require(isinstance(value[key], str) and IDENTIFIER.fullmatch(value[key]),
                "INVALID_IDENTIFIER")
    require(value["variant"] in {"baseline", "candidate"}, "INVALID_VARIANT")
    for key in ("fixture_digest", "rule_digest"):
        require(isinstance(value[key], str) and HASH.fullmatch(value[key]), "INVALID_DIGEST")
    require(isinstance(value["source_sha"], str)
            and re.fullmatch(r"[0-9a-f]{40}|[0-9a-f]{64}", value["source_sha"]), "SOURCE_SHA")
    env = value["environment"]
    require(isinstance(env, dict) and set(env) == ENV_FIELDS, "ENVIRONMENT_SCHEMA")
    for field in ENV_FIELDS:
        text_value(env[field], 200)
    require(HASH.fullmatch(env["permissions_digest"]), "PERMISSION_DIGEST")
    initial = value["initial_files"]
    require(isinstance(initial, dict) and len(initial) <= MAX_FILES, "INITIAL_FILES")
    for name, sha in initial.items():
        relative(name)
        require(isinstance(sha, str) and HASH.fullmatch(sha), "INITIAL_DIGEST")
    rules = value["rule_files"]
    require(isinstance(rules, dict) and len(rules) <= MAX_FILES, "RULE_FILES")
    for name, sha in rules.items():
        relative(name)
        require((name == "AGENTS.md" or name.startswith(".agents/skills/"))
                and isinstance(sha, str) and HASH.fullmatch(sha), "RULE_FILE")
    require(not set(rules) & set(initial), "RULE_INPUT_OVERLAP")
    require(value["rule_digest"] == digest(canonical(rules)), "RULE_DIGEST")
    for key in ("allowed_changes", "artifacts"):
        names = value[key]
        require(isinstance(names, list) and len(names) <= MAX_FILES, "PATH_LIST")
        for name in names:
            relative(name)
        require(len(names) == len(set(names)), "DUPLICATE_PATH")
    require(value["artifacts"], "ARTIFACTS_REQUIRED")
    require(not set(value["allowed_changes"]) & set(rules), "RULE_MUTATION_FORBIDDEN")
    metrics = value["metrics"]
    require(isinstance(metrics, dict) and set(metrics) <= METRICS, "METRICS_SCHEMA")
    for key, number in metrics.items():
        if number == "UNKNOWN":
            continue
        require(type(number) in (int, float) and math.isfinite(number) and number >= 0,
                "INVALID_METRIC")
        require(key == "duration_ms" or type(number) is int, "INTEGER_COUNT_REQUIRED")
    checks = value["checks"]
    require(isinstance(checks, list) and 1 <= len(checks) <= 100, "CHECKS_REQUIRED")
    seen = set()
    for check in checks:
        require(isinstance(check, dict) and set(check) == {"id", "kind", "path", "expected"},
                "CHECK_SCHEMA")
        require(isinstance(check["id"], str) and IDENTIFIER.fullmatch(check["id"])
                and check["id"] not in seen and check["id"] != "protected-inputs"
                and not check["id"].startswith("required-"), "CHECK_ID")
        seen.add(check["id"])
        require(check["kind"] in {"nonempty", "contains", "not_contains", "json_equal", "manual"},
                "CHECK_KIND")
        require(check["path"] in value["artifacts"], "CHECK_ARTIFACT")
        if check["kind"] in {"contains", "not_contains", "manual"}:
            text_value(check["expected"], 2000)
        if check["kind"] == "nonempty":
            require(check["expected"] is None, "NONEMPTY_EXPECTATION")
        require(len(canonical(check["expected"])) <= 8192, "EXPECTATION_LIMIT")
    return value


def evaluate_check(check, root, files):
    name = check["path"]
    base = {"id": check["id"], "path": name, "kind": check["kind"]}
    if name not in files:
        return {**base, "outcome": "FAILED", "reason": "ARTIFACT_MISSING"}
    if check["kind"] == "manual":
        return {**base, "outcome": "UNKNOWN", "reason": "INDEPENDENT_JUDGMENT_REQUIRED"}
    raw = bounded_read(root / name, MAX_FILE_BYTES)
    require(digest(raw) == files[name]["sha256"], "ARTIFACT_CHANGED_DURING_CHECK")
    kind = check["kind"]
    if kind == "nonempty":
        passed = bool(raw.strip())
    else:
        try:
            text = raw.decode("utf-8")
            if kind == "json_equal":
                parsed = json.loads(text, object_pairs_hook=_unique, parse_constant=_nonfinite)
                passed = canonical(parsed) == canonical(check["expected"])
            elif kind == "contains":
                passed = check["expected"] in text
            else:
                passed = check["expected"] not in text
        except (UnicodeError, json.JSONDecodeError, RecursionError, EvalError):
            passed = False
    return {**base, "outcome": "PASS" if passed else "FAILED",
            "reason": "PREDICATE_MATCHED" if passed else "PREDICATE_FAILED"}


def capture(input_value, directory):
    """中文：从当前产物重算机械检查，不把执行者声明当成语义判定。
    English: Recompute mechanical checks from current artifacts, not executor claims of semantic success.
    """
    config = validate_input(input_value)
    root = external(directory)
    before = snapshot(root)
    initial = {**config["initial_files"], **config["rule_files"]}
    changed = {name for name in set(before) | set(initial)
               if before.get(name, {}).get("sha256") != initial.get(name)}
    forbidden = sorted(changed - set(config["allowed_changes"]))
    checks = [evaluate_check(check, root, before) for check in config["checks"]]
    for name in config["artifacts"]:
        if name not in before and not any(c["path"] == name for c in checks):
            checks.append({"id": "required-" + str(len(checks)), "path": name,
                           "kind": "required", "outcome": "FAILED", "reason": "ARTIFACT_MISSING"})
    checks.append({"id": "protected-inputs", "path": "", "kind": "scope",
                   "outcome": "FAILED" if forbidden else "PASS",
                   "reason": "UNAUTHORIZED_FILE_CHANGE" if forbidden else "SCOPE_PRESERVED"})
    require(snapshot(root) == before, "ARTIFACT_CHANGED_DURING_CAPTURE")
    outcomes = {row["outcome"] for row in checks}
    outcome = "FAILED" if "FAILED" in outcomes else "UNKNOWN" if "UNKNOWN" in outcomes else "PASS"
    record = {
        "schema": "skill-eval-run/1", "input": config, "input_digest": digest(canonical(config)),
        "artifact_root": str(root), "files": before, "checks": checks,
        "outcome": outcome, "semantic_quality": "UNKNOWN", "forbidden_changes": forbidden,
        "limitations": ["mechanical-predicates-only", "input-contract-is-maintainer-supplied",
                        "no-host-isolation-attestation", "no-model-cost-inference"],
    }
    record["record_digest"] = digest(canonical(record))
    return record


def verify_record(record):
    require(isinstance(record, dict) and set(record) == {
        "schema", "input", "input_digest", "artifact_root", "files", "checks", "outcome",
        "semantic_quality", "forbidden_changes", "limitations", "record_digest",
    }, "RUN_SCHEMA")
    require(record["schema"] == "skill-eval-run/1", "RUN_SCHEMA")
    supplied = dict(record)
    seal = supplied.pop("record_digest")
    require(isinstance(seal, str) and seal == digest(canonical(supplied)), "RECORD_DIGEST")
    replayed = capture(record["input"], record["artifact_root"])
    require(replayed == record, "STALE_OR_FORGED_RESULT")
    return replayed


@lru_cache(maxsize=1)
def ux_statistics():
    """中文：复用现有 UX 统计，不改变旧观测白名单。
    English: Reuse existing UX statistics without changing the old observation whitelist.
    """
    spec = importlib.util.spec_from_file_location("skill_eval_ux", ROOT / "scripts/ux-benchmark.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module._summary


def compare(baseline, candidate):
    left, right = verify_record(baseline), verify_record(candidate)
    a, b = left["input"], right["input"]
    require(a["variant"] == "baseline" and b["variant"] == "candidate", "VARIANT_ORDER")
    for key in ("study_id", "case_id", "sample_id", "fixture_digest", "environment",
                "initial_files", "allowed_changes", "artifacts", "checks"):
        require(a[key] == b[key], "INCOMPARABLE_" + key.upper())
    left_root, right_root = external(left["artifact_root"]), external(right["artifact_root"])
    require(left_root != right_root and left_root not in right_root.parents
            and right_root not in left_root.parents, "INDEPENDENT_DIRECTORIES_REQUIRED")
    stats = ux_statistics()
    def summary(run):
        return stats([{"outcome": run["outcome"],
                       "duration_ms": run["input"]["metrics"].get("duration_ms", "UNKNOWN")}])
    before, after = summary(left), summary(right)
    a_time, b_time = before["median_duration_ms"], after["median_duration_ms"]
    return {
        "schema": "skill-eval-comparison/1", "case_id": a["case_id"],
        "baseline": left, "candidate": right, "metrics": {"baseline": before, "candidate": after},
        "median_delta_ms": b_time - a_time if a_time is not None and b_time is not None else None,
        "benefit": "UNKNOWN", "human_judgment": "NOT_RECORDED",
        "limitations": ["single-pair-not-general-evidence", "quality-requires-independent-judgment"],
    }


def png_dimensions(raw):
    """中文：只为有界静态PNG提供预览，其他格式保持转义文本。
    English: Preview bounded static PNGs; other formats remain escaped text.
    """
    if (not 33 <= len(raw) <= MAX_PNG_BYTES or raw[:8] != b"\x89PNG\r\n\x1a\n"
            or raw[8:16] != b"\x00\x00\x00\rIHDR"
            or int.from_bytes(raw[29:33], "big") != binascii.crc32(raw[12:29]) & 0xffffffff):
        return None
    width, height = int.from_bytes(raw[16:20], "big"), int.from_bytes(raw[20:24], "big")
    if not 1 <= width <= 8192 or not 1 <= height <= 8192 or width * height > 8 * 1024 * 1024:
        return None
    offset, chunks = 8, 0
    while offset + 12 <= len(raw):
        size = int.from_bytes(raw[offset:offset + 4], "big")
        kind = raw[offset + 4:offset + 8]
        chunks += 1
        if chunks > 1024 or size > len(raw) - offset - 12 or kind == b"acTL":
            return None
        offset += size + 12
        if kind == b"IEND":
            return (width, height) if size == 0 and offset == len(raw) else None
    return None


def render(comparison, feedback=None):
    """中文：无脚本、无外部资源的转义文本查看页；产物 HTML 永不作为页面执行。
    English: Escaped text viewer without scripts or external resources; artifact HTML is never executed.
    """
    recomputed = compare(comparison["baseline"], comparison["candidate"])
    require(recomputed == comparison, "COMPARISON_CHANGED")
    esc = lambda value: html.escape(str(value), quote=True)
    review = ""
    if feedback is not None:
        from skill_eval_review import verify_feedback
        verify_feedback(comparison, feedback)
        item = feedback["feedback"]
        review = ("<aside><h2>Recorded review</h2><p>" + esc(item["verdict"]) + " — "
                  + esc(item["reviewer_id"]) + "</p><pre>" + esc(item["notes"])
                  + "</pre><p>Artifact references verified; reviewer identity is not attested. "
                  "No automatic benefit or authorization follows.</p></aside>")
    sections = []
    preview_bytes, preview_pixels = 0, 0
    for variant in ("baseline", "candidate"):
        run = comparison[variant]
        rows = []
        for name in run["input"]["artifacts"]:
            if name not in run["files"]:
                rows.append("<h3>" + esc(name) + "</h3><p>Artifact missing</p>")
                continue
            raw = bounded_read(Path(run["artifact_root"]) / name, MAX_FILE_BYTES)
            require(digest(raw) == run["files"][name]["sha256"], "ARTIFACT_CHANGED_DURING_RENDER")
            title = "<h3>" + esc(name) + "</h3>"
            if raw.startswith(b"\x89PNG\r\n\x1a\n"):
                dimensions = png_dimensions(raw)
                if (dimensions is None or preview_bytes + len(raw) > MAX_PREVIEW_TOTAL
                        or preview_pixels + dimensions[0] * dimensions[1] > MAX_PREVIEW_PIXELS):
                    rows.append(title + "<p>PNG preview omitted: invalid, animated, or above preview bounds.</p>")
                    continue
                preview_bytes += len(raw)
                preview_pixels += dimensions[0] * dimensions[1]
                rows.append(title + '<img alt="' + esc(name) + '" src="data:image/png;base64,'
                            + base64.b64encode(raw).decode("ascii") + '">')
                continue
            limit = min(MAX_PREVIEW_BYTES, MAX_PREVIEW_TOTAL - preview_bytes)
            text = raw[:limit].decode("utf-8", errors="replace")
            preview_bytes += min(len(raw), limit)
            suffix = "\n[Preview truncated]" if len(raw) > limit else ""
            rows.append("<h3>" + esc(name) + "</h3><pre>" + esc(text + suffix) + "</pre>")
        checks = "".join("<li>" + esc(c["id"]) + ": " + esc(c["outcome"]) + " — "
                         + esc(c["reason"]) + "</li>" for c in run["checks"])
        sections.append("<section><h2>" + esc(variant) + "</h2><p>Mechanical outcome: "
                        + esc(run["outcome"]) + "; semantic quality: UNKNOWN</p><pre>"
                        + esc(json.dumps(run["input"]["metrics"], ensure_ascii=False, sort_keys=True))
                        + "</pre><ul>"
                        + checks + "</ul>" + "".join(rows) + "</section>")
    return (
        '<!doctype html><html lang="en"><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        '<meta http-equiv="Content-Security-Policy" content="default-src \'none\'; '
        'style-src \'unsafe-inline\'; img-src data:; base-uri \'none\'; form-action \'none\'">'
        "<title>Skill output comparison</title><style>"
        "body{font:16px system-ui;margin:2rem;color:#172534;background:#f5f7fa}"
        "main{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:1.5rem}"
        "section{padding:1.25rem;background:white;border:1px solid #ccd5df}"
        "pre{white-space:pre-wrap;overflow-wrap:anywhere;max-height:36rem;overflow:auto}"
        "img{display:block;max-width:100%;height:auto;border:1px solid #ccd5df}"
        "@media(max-width:800px){main{grid-template-columns:1fr}}</style>"
        "<h1>Skill output comparison</h1><p>Case: " + esc(comparison["case_id"])
        + "</p><p>These are mechanical checks. Benefits and independent quality remain unverified."
        "</p>" + review + "<main>" + "".join(sections) + "</main></html>"
    )


def write_new(path, payload):
    target = external(path)
    require(isinstance(payload, bytes) and len(payload) <= MAX_TOTAL_BYTES, "OUTPUT_LIMIT")
    target.parent.mkdir(parents=True, exist_ok=True)
    target = external(target)
    with target.open("xb") as stream:
        stream.write(payload)


def main():
    parser = argparse.ArgumentParser(description="Explicit offline Skill artifact comparison")
    sub = parser.add_subparsers(dest="command", required=True)
    prepare_parser = sub.add_parser("prepare")
    for name in ("suite", "case", "baseline", "environment", "output"):
        prepare_parser.add_argument("--" + name, required=True)
    prepare_parser.add_argument("--candidate")
    prepare_parser.add_argument("--sample-id", default="one")
    reuse_parser = sub.add_parser("prepare-reuse")
    for name in ("case", "baseline", "environment", "output"):
        reuse_parser.add_argument("--" + name, required=True)
    reuse_parser.add_argument("--allow-change", action="append", required=True)
    reuse_parser.add_argument("--candidate")
    reuse_parser.add_argument("--sample-id", default="one")
    verifier = sub.add_parser("verify-reuse")
    verifier.add_argument("--run", required=True)
    capture_parser = sub.add_parser("capture")
    capture_parser.add_argument("--input", required=True)
    capture_parser.add_argument("--artifacts", required=True)
    capture_parser.add_argument("--output", required=True)
    capture_parser.add_argument("--metrics")
    compare_parser = sub.add_parser("compare")
    compare_parser.add_argument("--baseline", required=True)
    compare_parser.add_argument("--candidate", required=True)
    compare_parser.add_argument("--output", required=True)
    render_parser = sub.add_parser("render")
    render_parser.add_argument("--comparison", required=True)
    render_parser.add_argument("--output", required=True)
    render_parser.add_argument("--feedback")
    feedback_template_parser = sub.add_parser("feedback-template")
    feedback_template_parser.add_argument("--comparison", required=True)
    feedback_template_parser.add_argument("--output", required=True)
    feedback_parser = sub.add_parser("record-feedback")
    feedback_parser.add_argument("--comparison", required=True)
    feedback_parser.add_argument("--feedback", required=True)
    feedback_parser.add_argument("--output", required=True)
    args = parser.parse_args()
    try:
        if args.command == "prepare":
            from skill_eval_fixture import prepare
            result = prepare(read_json(args.suite), args.case, args.output, args.baseline,
                             read_json(args.environment), args.candidate, args.sample_id)
            print(json.dumps(result))
            return 0
        if args.command == "capture":
            inputs = read_json(args.input)
            if args.metrics:
                inputs["metrics"] = read_json(args.metrics)
            value = capture(inputs, args.artifacts)
            write_new(args.output, canonical(value) + b"\n")
        elif args.command == "compare":
            value = compare(read_json(args.baseline), read_json(args.candidate))
            write_new(args.output, canonical(value) + b"\n")
        elif args.command == "render":
            write_new(args.output, render(read_json(args.comparison),
                      read_json(args.feedback) if args.feedback else None).encode("utf-8"))
        elif args.command in {"feedback-template", "record-feedback"}:
            from skill_eval_review import feedback_template, record_feedback
            comparison = read_json(args.comparison)
            value = (feedback_template(comparison) if args.command == "feedback-template" else
                     record_feedback(comparison, read_json(args.feedback)))
            write_new(args.output, canonical(value) + b"\n")
        elif args.command == "prepare-reuse":
            from skill_eval_review import prepare_reuse
            value = prepare_reuse(args.case, args.output, args.baseline, read_json(args.environment),
                                  args.allow_change, args.candidate, args.sample_id)
            print(json.dumps(value))
            return 0
        elif args.command == "verify-reuse":
            from skill_eval_review import verify_reuse
            value = verify_reuse(args.run)
            print(json.dumps(value))
            return 0 if value["oracle"]["behavior_passed"] else 1
        print(json.dumps({"status": "WRITTEN", "output": str(external(args.output)),
                          "semantic_quality": "UNKNOWN"}))
        return 0
    except (CapabilityError, ValueError, OSError, KeyError, TypeError, SystemExit) as exc:
        print(json.dumps({"status": "FAILED", "reason": str(exc)[:200]}), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
