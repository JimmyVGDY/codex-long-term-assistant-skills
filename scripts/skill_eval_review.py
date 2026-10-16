"""中文：评测反馈与现有复用验收桥接，所有写入限于显式仓库外样例。
English: Evaluation feedback and existing reuse-verifier adapters, restricted to explicit external fixtures.
"""
from __future__ import annotations

import copy
from datetime import datetime, timezone
from functools import lru_cache
import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


@lru_cache(maxsize=None)
def module(name):
    """中文：只加载包内固定维护工具，不接受外部脚本路径。
    English: Load fixed package maintenance tools only, never caller-selected script paths.
    """
    names = {"eval": "skill-eval.py", "fixture": "skill_eval_fixture.py", "reuse": "reuse-eval.py"}
    spec = importlib.util.spec_from_file_location("skill_review_" + name, ROOT / "scripts" / names[name])
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


def comparison_current(comparison):
    tool = module("eval")
    tool.require(tool.compare(comparison["baseline"], comparison["candidate"]) == comparison,
                 "COMPARISON_CHANGED")
    return tool.digest(tool.canonical(comparison))


def feedback_template(comparison):
    tool = module("eval")
    sha = comparison_current(comparison)
    return {
        "schema": "skill-eval-feedback-input/1", "comparison_digest": sha,
        "reviewer_kind": "human", "reviewer_id": "replace-with-reviewer-id",
        "verdict": "insufficient", "notes": "",
        "criteria": [{"id": check["id"], "baseline": "UNKNOWN", "candidate": "UNKNOWN",
                      "reason": "", "evidence": []}
                     for check in comparison["baseline"]["input"]["checks"]],
        "evaluation_gaps": [],
    }


def record_feedback(comparison, feedback):
    """中文：重验产物引用后记录判断；不将自报身份、偏好或质量自动升级为授权。
    English: Reverify output references before recording judgments, without promoting identity claims or preferences into authority.
    """
    tool = module("eval")
    sha = comparison_current(comparison)
    tool.require(isinstance(feedback, dict) and set(feedback) == {
        "schema", "comparison_digest", "reviewer_kind", "reviewer_id", "verdict",
        "notes", "criteria", "evaluation_gaps",
    } and feedback["schema"] == "skill-eval-feedback-input/1", "FEEDBACK_SCHEMA")
    tool.require(feedback["comparison_digest"] == sha, "FEEDBACK_BASELINE_CHANGED")
    tool.require(feedback["reviewer_kind"] in {"human", "independent-agent"}, "REVIEWER_KIND")
    tool.text_value(feedback["reviewer_id"], 128)
    tool.require(feedback["reviewer_id"] != "replace-with-reviewer-id", "REVIEWER_REQUIRED")
    tool.require(feedback["verdict"] in {"baseline", "candidate", "tie", "insufficient"}, "VERDICT")
    tool.text_value(feedback["notes"], 4000)
    required = {check["id"] for check in comparison["baseline"]["input"]["checks"]}
    criteria = feedback["criteria"]
    tool.require(isinstance(criteria, list) and len(criteria) == len(required), "FEEDBACK_CRITERIA")
    seen = set()
    for row in criteria:
        tool.require(isinstance(row, dict) and set(row) == {
            "id", "baseline", "candidate", "reason", "evidence"}, "FEEDBACK_CRITERION")
        tool.require(row["id"] in required and row["id"] not in seen, "FEEDBACK_CRITERION_ID")
        seen.add(row["id"])
        for side in ("baseline", "candidate"):
            tool.require(row[side] in {"PASS", "FAILED", "UNKNOWN"}, "FEEDBACK_OUTCOME")
        tool.text_value(row["reason"], 2000)
        refs = row["evidence"]
        tool.require(isinstance(refs, list) and len(refs) <= 20, "FEEDBACK_EVIDENCE")
        for item in refs:
            tool.require(isinstance(item, dict) and set(item) == {"variant", "path", "sha256"},
                         "FEEDBACK_REFERENCE")
            side = item["variant"]
            tool.require(side in {"baseline", "candidate"}, "FEEDBACK_VARIANT")
            artifact = comparison[side]["files"].get(item["path"])
            tool.require(item["path"] in comparison[side]["input"]["artifacts"]
                         and artifact is not None and item["sha256"] == artifact["sha256"],
                         "FEEDBACK_ARTIFACT_MISMATCH")
        for side in ("baseline", "candidate"):
            if row[side] != "UNKNOWN":
                tool.require(any(item["variant"] == side for item in refs), "FEEDBACK_EVIDENCE_REQUIRED")
    if feedback["verdict"] != "insufficient":
        tool.require(any(row["baseline"] != "UNKNOWN" and row["candidate"] != "UNKNOWN"
                         for row in criteria), "FEEDBACK_JUDGMENT_REQUIRED")
    gaps = feedback["evaluation_gaps"]
    tool.require(isinstance(gaps, list) and len(gaps) <= 20, "EVALUATION_GAPS")
    for gap in gaps:
        tool.require(isinstance(gap, dict) and set(gap) == {"check_id", "issue", "evidence"},
                     "EVALUATION_GAP")
        tool.require(gap["check_id"] in required or gap["check_id"] == "missing-coverage",
                     "EVALUATION_GAP_CHECK")
        tool.text_value(gap["issue"], 2000)
        tool.text_value(gap["evidence"], 2000)
    return {
        "schema": "skill-eval-feedback/1", "feedback": copy.deepcopy(feedback),
        "recorded_at": datetime.now(timezone.utc).isoformat(),
        "verification": "artifact-references-verified",
        "identity_attestation": "NOT_PROVIDED", "execution_authorization": "NONE",
        "benefit": "UNKNOWN",
    }


def verify_feedback(comparison, receipt):
    tool = module("eval")
    tool.require(isinstance(receipt, dict) and set(receipt) == {
        "schema", "feedback", "recorded_at", "verification", "identity_attestation",
        "execution_authorization", "benefit",
    } and receipt["schema"] == "skill-eval-feedback/1", "FEEDBACK_RECEIPT")
    moment = datetime.fromisoformat(receipt["recorded_at"])
    tool.require(moment.utcoffset() is not None, "FEEDBACK_TIMEZONE")
    refreshed = record_feedback(comparison, receipt["feedback"])
    refreshed["recorded_at"] = receipt["recorded_at"]
    tool.require(refreshed == receipt, "FEEDBACK_RECEIPT_CHANGED")
    return receipt


def prepare_reuse(case_id, output, baseline, environment, allowed_changes, candidate=None,
                  sample_id="one"):
    """中文：从现有公开复用样例生成相同输入，复用原验收器，不复制隐藏答案。
    English: Prepare identical inputs from existing public reuse fixtures and reuse their verifier without copying answer keys.
    """
    tool, fixture, reuse = module("eval"), module("fixture"), module("reuse")
    found = [case for case in reuse.catalog() if case["id"] == case_id]
    tool.require(len(found) == 1, "REUSE_CASE")
    case = found[0]
    tool.require(isinstance(allowed_changes, list) and allowed_changes
                 and len(set(allowed_changes)) == len(allowed_changes), "REUSE_ALLOWED_CHANGES")
    tool.require(not set(allowed_changes) & {"old.test.mjs", "test_old.py", "oracle.json"},
                 "REUSE_PROTECTED_INPUT")
    artifacts = [*allowed_changes, "oracle.json"]
    suite = {
        "schema": "skill-eval-suite/1", "suite_id": "reuse-" + case_id,
        "data_classification": "public-synthetic",
        "cases": [{
            "id": case_id, "task": case["task"], "skills": list(reuse.SKILLS), "files": case["files"],
            "allowed_changes": artifacts, "artifacts": artifacts,
            "checks": [{"id": "oracle", "kind": "json_equal", "path": "oracle.json",
                        "expected": {"behavior_passed": True, "protected_inputs_intact": True}}]
                      + [{"id": "artifact-" + str(i), "kind": "nonempty", "path": name,
                          "expected": None} for i, name in enumerate(allowed_changes)],
        }],
    }
    result = fixture.prepare(suite, case_id, output, baseline, environment, candidate, sample_id)
    target = tool.external(output)
    frozen = {
        "schema": "skill-reuse-binding/1", "case": case_id,
        "catalog_digest": tool.digest(tool.canonical(case)),
        "verifier_digest": tool.digest(tool.bounded_read(ROOT / "scripts/reuse-eval.py", tool.MAX_FILE_BYTES)),
        "oracle_digest": tool.digest(tool.bounded_read(ROOT / "tests/reuse-oracles.json", tool.MAX_JSON_BYTES)),
    }
    for variant in ("baseline", "candidate"):
        run = target / variant
        inputs = tool.read_json(run / "input.json")
        legacy = {
            "case": case_id, "runtime": case["runtime"], "baseline": inputs["source_sha"],
            "locale": "zh-CN", "task": case["task"],
            "initial_files": {**inputs["initial_files"], **inputs["rule_files"]},
        }
        tool.write_new(run / "input-manifest.json", tool.canonical(legacy) + b"\n")
        tool.write_new(run / "reuse-binding.json", tool.canonical(frozen) + b"\n")
    return result


def verify_reuse(run_directory):
    """中文：显式执行现有样例验收，保存不可覆盖的结果；不是通用命令执行接口。
    English: Explicitly run the existing fixture verifier and preserve non-overwriting results; not a general command runner.
    """
    tool, reuse = module("eval"), module("reuse")
    run = tool.external(run_directory)
    binding = tool.read_json(run / "reuse-binding.json")
    tool.require(set(binding) == {"schema", "case", "catalog_digest", "verifier_digest", "oracle_digest"}
                 and binding["schema"] == "skill-reuse-binding/1", "REUSE_BINDING")
    case = next((item for item in reuse.catalog() if item["id"] == binding["case"]), None)
    tool.require(case is not None and tool.digest(tool.canonical(case)) == binding["catalog_digest"],
                 "REUSE_CATALOG_CHANGED")
    for field, path in (("verifier_digest", ROOT / "scripts/reuse-eval.py"),
                        ("oracle_digest", ROOT / "tests/reuse-oracles.json")):
        tool.require(tool.digest(tool.bounded_read(path, tool.MAX_JSON_BYTES)) == binding[field],
                     "REUSE_VERIFIER_CHANGED")
    inputs = tool.validate_input(tool.read_json(run / "input.json"))
    tool.require(inputs["initial_files"] == {
        name: tool.digest(text.encode("utf-8")) for name, text in case["files"].items()
    }, "REUSE_CATALOG_INPUT_CHANGED")
    tool.require(not set(inputs["allowed_changes"]) & {"old.test.mjs", "test_old.py"},
                 "REUSE_PROTECTED_INPUT")
    legacy = tool.read_json(run / "input-manifest.json")
    tool.require(legacy == {
        "case": binding["case"], "runtime": case["runtime"], "baseline": inputs["source_sha"],
        "locale": "zh-CN", "task": case["task"],
        "initial_files": {**inputs["initial_files"], **inputs["rule_files"]},
    }, "REUSE_INPUT_BINDING")
    root = run / "workspace"
    files = tool.snapshot(root)
    tool.require(not (root / "oracle.json").exists() and not (run / "oracle-receipt.json").exists(),
                 "REUSE_ALREADY_VERIFIED")
    protected = {**inputs["initial_files"], **inputs["rule_files"]}
    tool.require(all(files.get(name, {}).get("sha256") == sha for name, sha in protected.items()
                     if name not in inputs["allowed_changes"]), "REUSE_PROTECTED_INPUT_CHANGED")
    tool.require(set(files) <= set(protected) | set(inputs["allowed_changes"]), "REUSE_EXTRA_FILES")
    result = reuse.verify(run)
    tool.require(tool.snapshot(root) == files, "REUSE_WORKSPACE_CHANGED")
    oracle = {key: result[key] for key in ("behavior_passed", "protected_inputs_intact")}
    tool.write_new(root / "oracle.json", tool.canonical(oracle) + b"\n")
    receipt = {
        "schema": "skill-reuse-receipt/1", "case": case["id"], "binding": binding,
        "input_digest": tool.digest(tool.canonical(inputs)),
        "program_result_digest": tool.digest(tool.canonical(result)),
        "oracle": oracle, "semantic_reuse_review": "UNKNOWN",
    }
    tool.write_new(run / "oracle-receipt.json", tool.canonical(receipt) + b"\n")
    return receipt
