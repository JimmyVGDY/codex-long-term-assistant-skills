#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import platform
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

ROOT = Path(__file__).resolve().parents[1]
COMMAND_TIMEOUT_SECONDS = 1800
MINIMUM_PYTHON = (3, 11)
if sys.version_info < MINIMUM_PYTHON:
    raise RuntimeError("V7.4 完整验证需要 Python 3.11+，当前为 %s" % platform.python_version())
import tomllib
from validation_evidence import (CAPABILITY_TEST_MAP, EvidenceError, evaluate_capabilities,
                                 load_evidence_report, mapping_test_ids_are_loadable,
                                 package_metadata, suite_passed, timeout_report)
from validation_worktree import require_output_outside_worktree, run_with_worktree_guard


parser = argparse.ArgumentParser(description="V7.4 package-only validation")
parser.add_argument("--output")
arguments = parser.parse_args()
output_path = require_output_outside_worktree(ROOT, Path(arguments.output)) if arguments.output else None


def run(stage: str, command: list[str], environment: Mapping[str, str] | None = None) -> None:
    result = subprocess.run(command, cwd=ROOT, text=True, encoding="utf-8", errors="replace",
                            capture_output=True, timeout=COMMAND_TIMEOUT_SECONDS, env=environment)
    if result.returncode:
        # 中文：报告特意排除原始命令/测试输出，避免携带源码片段或宿主细节。
        # English: Reports deliberately exclude raw command/test output, which can carry source snippets or host details.
        executable = Path(command[1]).name if len(command) > 1 else command[0]
        raise RuntimeError("validation stage %s failed with exit code %d: %s" % (stage, result.returncode, executable))


def _interrupted_report(suite_name: str) -> dict[str, Any]:
    report = timeout_report(suite_name, COMMAND_TIMEOUT_SECONDS)
    report["execution_status"] = "INTERRUPTED"
    digest_input = dict(report)
    digest_input.pop("report_sha256", None)
    # 中文：局部帮助器保持 schema 摘要的规范字节；English: local helper keeps the schema digest canonical.
    from validation_evidence import _with_digest
    return _with_digest(digest_input)


def _collect_suite(suite_name: str, start_dir: Path, environment: Mapping[str, str], temporary: Path) -> dict[str, Any]:
    report_path = temporary / (suite_name + ".json")
    command = [sys.executable, "-B", str(ROOT / "scripts" / "validation_evidence.py"), "collect",
               "--start-dir", str(start_dir), "--suite", suite_name, "--output", str(report_path)]
    try:
        result = subprocess.run(command, cwd=ROOT, text=True, encoding="utf-8", errors="replace",
                                capture_output=True, timeout=COMMAND_TIMEOUT_SECONDS, env=environment)
    except subprocess.TimeoutExpired:
        return timeout_report(suite_name, COMMAND_TIMEOUT_SECONDS)
    if result.returncode or not report_path.is_file():
        return _interrupted_report(suite_name)
    try:
        return load_evidence_report(report_path)
    except EvidenceError:
        return _interrupted_report(suite_name)


def _capability_projection(row: Mapping[str, Any]) -> str:
    status = str(row["status"])
    if status == "PASS":
        return "PASS (%d required unittest cases)" % len(row["required_test_ids"])
    reasons = ",".join(str(item) for item in row.get("reason_codes", []))
    return status + (" (" + reasons + ")" if reasons else "")


def validate_package() -> dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix="cp-v74-validation-") as directory:
        temporary = Path(directory)
        validation_env = dict(os.environ)
        validation_env["PYTHONDONTWRITEBYTECODE"] = "1"
        validation_env["PYTHONPYCACHEPREFIX"] = str(temporary / "pycache")
        metadata = package_metadata(ROOT)
        for path in ROOT.rglob("*.json"):
            relative = path.relative_to(ROOT)
            if "__pycache__" not in path.parts and (not relative.parts or relative.parts[0] not in {"project-context", ".git"}):
                json.loads(path.read_text(encoding="utf-8-sig"))
        for path in ROOT.rglob("*.toml"):
            relative = path.relative_to(ROOT)
            if not relative.parts or relative.parts[0] not in {"project-context", ".git"}:
                tomllib.loads(path.read_text(encoding="utf-8-sig"))
        run("compile", [sys.executable, "-m", "compileall", "-q", str(ROOT / "runtime"), str(ROOT / "scripts"), str(ROOT / "hooks")], validation_env)
        run("payload-integrity", [sys.executable, str(ROOT / "scripts" / "payload-integrity.py"), "verify", "--root", str(ROOT),
             "--manifest", str(ROOT / "PLUGIN_PAYLOAD_MANIFEST.json"), "--package", metadata["package"], "--version", metadata["version"]], validation_env)
        for script in ("semantic-lint.py", "privacy-boundary-lint.py", "check-dispatch-policy.py"):
            run(script.removesuffix(".py"), [sys.executable, str(ROOT / "scripts" / script)], validation_env)
        run("routing-eval", [sys.executable, str(ROOT / "scripts" / "routing-eval.py"), "validate"], validation_env)
        run("dispatch-policy-acceptance", [sys.executable, str(ROOT / "scripts" / "dispatch-policy-acceptance.py")], validation_env)
        missing_mapping_ids = mapping_test_ids_are_loadable(ROOT)
        package_report = _collect_suite("package", ROOT / "tests", validation_env, temporary)
        runtime_report = _collect_suite("runtime", ROOT / "runtime" / "tests", validation_env, temporary)
        capabilities = evaluate_capabilities((package_report, runtime_report))
        if missing_mapping_ids:
            for row in capabilities.values():
                row["status"] = "NOT_VERIFIED"
                row["reason_codes"] = ["MAPPING_SOURCE_UNLOADABLE"]
                row["mapping_source_unloadable_test_ids"] = missing_mapping_ids
        return {"metadata": metadata, "package_report": package_report, "runtime_report": runtime_report,
                "capabilities": capabilities, "mapping_source_unloadable_test_ids": missing_mapping_ids}


validation = run_with_worktree_guard(ROOT, validate_package)
metadata = validation["metadata"]
package_report, runtime_report = validation["package_report"], validation["runtime_report"]
capabilities = validation["capabilities"]
package_test_count, runtime_test_count = int(package_report["executed_test_count"]), int(runtime_report["executed_test_count"])
suites_passed = suite_passed(package_report) and suite_passed(runtime_report)
capabilities_passed = all(row["status"] == "PASS" for row in capabilities.values())
result = {
    "ok": suites_passed and capabilities_passed, "evidence_scope": "package-only", "version": metadata["version"],
    "skill_count": metadata["skill_count"], "reviewer_count": metadata["reviewer_count"], "hooks": metadata["hooks"],
    "optional_capability_gate_host_acceptance": "NOT_EVALUATED (separate real-host and fresh-task acceptance)",
    "task_outcome_event": metadata["task_outcome_event"], "execution_authorization": "NONE",
    "automatic_self_modification": metadata["automatic_self_modification"], "dispatch_policy": "PASS", "privacy_boundary": "PASS",
    "python_compatibility": {"minimum": metadata["python_minimum"], "validated_runtime": platform.python_version()},
    "semantic_lint": "PASS", "routing_case_schema": "PASS (%d cases)" % metadata["routing_case_count"], "plugin_payload_manifest": "PASS",
    "codex_compatibility_registry": "PASS (%d verified versions)" % metadata["compatibility_version_count"],
    "codex_compatibility_matrix": "NOT_EVALUATED (separate Windows/Ubuntu workflow)",
    "routing_host_observation": "NOT_EVALUATED (package-only validation)", "worktree_side_effect_gate": "PASS",
    "multiprocess_fault_injection": _capability_projection(capabilities["multiprocess_fault_injection"]),
    "delayed_session_end_seal": _capability_projection(capabilities["delayed_session_end_seal"]),
    "reviewer_result_v4": _capability_projection(capabilities["reviewer_result_v4"]),
    "minimum_profile_and_inline_delegate_gates": _capability_projection(capabilities["minimum_profile_and_inline_delegate_gates"]),
    "state_bound_plugin_runtime": _capability_projection(capabilities["state_bound_plugin_runtime"]),
    "delegation_budget_v2": _capability_projection(capabilities["delegation_budget_v2"]),
    "reviewer_policy_v2": _capability_projection(capabilities["reviewer_policy_v2"]),
    "delegation_budget_v3": _capability_projection(capabilities["delegation_budget_v3"]),
    "reviewer_state_v8_result_v5": _capability_projection(capabilities["reviewer_state_v8_result_v5"]),
    "matrix_hook_protocol": _capability_projection(capabilities["matrix_hook_protocol"]),
    "calibration_sample_v3": _capability_projection(capabilities["calibration_sample_v3"]),
    "native_reviewer_matrix_acceptance": "NOT_EVALUATED (separate real-host acceptance)",
    "delegation_hook_gate": _capability_projection(capabilities["delegation_hook_gate"]),
    "delegation_calibration_replay": _capability_projection(capabilities["delegation_calibration_replay"]),
    "event_archive_capacity_health": _capability_projection(capabilities["event_archive_capacity_health"]),
    "unit_regression_tests": ("PASS (%d package + %d runtime)" % (package_test_count, runtime_test_count)
                              if suites_passed else "FAIL (unittest evidence incomplete or unsuccessful)"),
    "validation_evidence": {
        "schema_version": "package-validation-evidence/2", "collected_at": datetime.now(timezone.utc).isoformat(),
        "source_commit": subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True, encoding="utf-8", capture_output=True, check=True).stdout.strip(),
        "platform": platform.system(), "package_test_count": package_test_count, "runtime_test_count": runtime_test_count,
        "package_test_command": "python -B scripts/validation_evidence.py collect --start-dir tests",
        "runtime_test_command": "python -B scripts/validation_evidence.py collect --start-dir runtime/tests",
        "dispatch_policy_command": "python scripts/dispatch-policy-acceptance.py", "test_suites": [package_report, runtime_report],
        "capabilities": capabilities, "capability_test_map": CAPABILITY_TEST_MAP,
        "mapping_source_unloadable_test_ids": validation["mapping_source_unloadable_test_ids"],
    },
}
serialized = json.dumps(result, ensure_ascii=False, indent=2)
if output_path:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(serialized + "\n", encoding="utf-8", newline="\n")
print(serialized)
if not result["ok"]:
    raise SystemExit(1)
