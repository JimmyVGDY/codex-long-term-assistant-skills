"""中文：冻结触发评测集合，复用旧宿主评分器，不启动模型或修改描述。
English: Freeze trigger studies and reuse host scoring without running models or changing descriptions.
"""
from __future__ import annotations

import json
import tempfile
from pathlib import Path

from skill_eval_fixture import EVAL, ROOT, git_bytes, resolve_commit
from cp_runtime.capability_store import bounded_read, safe_path

GROUPS = {"documents", "design", "browser", "mcp"}
META = {"group", "split", "polarity", "intent_family", "repeats"}
BASE = {"id", "prompt", "required", "optional", "forbidden", "max_active"}


def validate_suite(data, legacy):
    EVAL.require(set(data) == {"schema", "suite_id", "data_classification", "cases"}
                 and data["schema"] == "routing-study-cases/1"
                 and data["data_classification"] == "public-synthetic", "STUDY_SUITE")
    cases = data["cases"]
    EVAL.require(isinstance(cases, list) and len(cases) == 24, "STUDY_CASE_COUNT")
    legacy.validate_cases({"schema_version": 1, "cases": cases})
    known = {row["name"] for row in EVAL.read_json(ROOT / "manifest.json")["skills"]}
    families = {}
    for row in cases:
        EVAL.require(BASE | META <= set(row) and set(row) <= BASE | META | {"phases"}, "STUDY_CASE_FIELDS")
        EVAL.require(row["group"] in GROUPS and row["split"] in {"development", "final"}
                     and row["polarity"] in {"positive", "negative"}, "STUDY_CASE_GROUP")
        EVAL.require(type(row["repeats"]) is int and row["repeats"] in {1, 3}, "STUDY_REPEATS")
        EVAL.text_value(row["intent_family"], 100)
        EVAL.text_value(row["prompt"], 4000)
        EVAL.require(row["intent_family"] not in families or families[row["intent_family"]] == row["split"],
                     "STUDY_FAMILY_LEAK")
        families[row["intent_family"]] = row["split"]
        used = set(row["required"]) | set(row["optional"]) | set(row["forbidden"])
        EVAL.require(used <= known and not set(row["optional"]) & set(row["forbidden"])
                     and len(row["required"]) <= row["max_active"], "STUDY_SKILL_CONFLICT")
        EVAL.require(not any(name in row["prompt"] for name in known), "STUDY_EXPLICIT_SKILL_PROMPT")
    for group in GROUPS:
        rows = [row for row in cases if row["group"] == group]
        EVAL.require(len(rows) == 6 and sum(row["polarity"] == "positive" for row in rows) == 3
                     and sum(row["split"] == "development" for row in rows) == 4, "STUDY_BALANCE")
        for split in ("development", "final"):
            EVAL.require({row["polarity"] for row in rows if row["split"] == split} == {"positive", "negative"},
                         "STUDY_SPLIT_COVERAGE")
    return cases


def _rule_entries(commit, locale="zh-CN"):
    raw = git_bytes(["show", commit + ":manifest.json"]) if commit else bounded_read(ROOT / "manifest.json", EVAL.MAX_JSON_BYTES)
    manifest = json.loads(raw)
    entries = {}
    for row in manifest["skills"]:
        name = row["name"]
        relative = "skills/" + name + "/SKILL.md"
        EVAL.relative(relative)
        source = ("locales/en/" if locale == "en" else "") + relative
        entries[relative] = (git_bytes(["show", commit + ":" + source], EVAL.MAX_FILE_BYTES)
                             if commit else bounded_read(ROOT / source, EVAL.MAX_FILE_BYTES))
    return manifest["version"], entries


def prepare(suite, output, environment, baseline, legacy, candidate=None, locale="zh-CN"):
    cases = validate_suite(suite, legacy)
    EVAL.require(locale in {"zh-CN", "en"}, "STUDY_LOCALE")
    EVAL.require(isinstance(environment, dict) and set(environment) == EVAL.ENV_FIELDS, "ENVIRONMENT_SCHEMA")
    for item in environment.values():
        EVAL.text_value(item, 200)
    EVAL.require(EVAL.HASH.fullmatch(environment["permissions_digest"]), "PERMISSION_DIGEST")
    root = EVAL.external(output)
    EVAL.require(not root.exists(), "STUDY_OUTPUT_EXISTS")
    old, new = resolve_commit(baseline), resolve_commit(candidate or "HEAD")
    protected, rules, payloads, trials = {}, {}, {}, []
    suite_bytes = EVAL.canonical(suite)
    payloads["suite.json"] = suite_bytes
    suite_digest = EVAL.digest(suite_bytes)
    for variant, commit in (("baseline", old), ("candidate", new if candidate else None)):
        version, entries = _rule_entries(commit, locale)
        digests = {name: EVAL.digest(raw) for name, raw in entries.items()}
        rules[variant] = {"source_sha": old if variant == "baseline" else new,
                          "source_kind": "commit" if commit else "working-tree",
                          "plugin_version": version, "entry_digests": digests,
                          "rule_digest": EVAL.digest(EVAL.canonical(digests))}
        for name, raw in entries.items():
            payloads["rules/" + variant + "/" + name] = raw
        for case in cases:
            for repeat in range(1, case["repeats"] + 1):
                trial = "trial-" + EVAL.digest(EVAL.canonical([suite_digest, variant, case["id"], repeat]))[:24]
                request = {"schema": "routing-study-prompt/1", "trial_id": trial, "prompt": case["prompt"]}
                input_name = "prompts/" + trial + ".json"
                payloads[input_name] = EVAL.canonical(request)
                trials.append({"trial_id": trial, "case_id": case["id"], "variant": variant,
                               "split": case["split"], "repeat": repeat, "input_file": input_name,
                               "input_sha256": EVAL.digest(payloads[input_name])})
    EVAL.require(len(payloads) <= 150 and sum(map(len, payloads.values())) <= EVAL.MAX_TOTAL_BYTES, "STUDY_SIZE")
    protected = {name: EVAL.digest(raw) for name, raw in sorted(payloads.items())}
    manifest = {"schema": "routing-study/1", "locale": locale, "suite_digest": suite_digest, "environment": environment,
                "rules": rules, "trials": trials, "protected_files": protected,
                "evidence_level": "host_final_report", "description_changes": False,
                "final_set_policy": "Do not tune descriptions against final cases; rebuild a leaked final set."}
    manifest["record_digest"] = EVAL.digest(EVAL.canonical(manifest))
    for name, raw in payloads.items():
        EVAL.write_new(root / name, raw)
    EVAL.write_new(root / "study.json", EVAL.canonical(manifest))
    return {"study_file": str(root / "study.json"), "cases": len(cases), "trials": len(trials),
            "rule_digests": {key: value["rule_digest"] for key, value in rules.items()},
            "execution_authorization": "NONE", "benefit": "UNKNOWN"}


def verify(study_file, legacy):
    path = safe_path(Path(study_file))
    manifest = EVAL.read_json(path)
    unsigned = dict(manifest)
    seal = unsigned.pop("record_digest", None)
    EVAL.require(seal == EVAL.digest(EVAL.canonical(unsigned))
                 and manifest.get("schema") == "routing-study/1"
                 and manifest.get("locale") in {"zh-CN", "en"}, "STUDY_DIGEST")
    files = manifest.get("protected_files")
    EVAL.require(isinstance(files, dict) and 1 <= len(files) <= 150, "STUDY_FILES")
    total = 0
    for name, expected in files.items():
        EVAL.relative(name)
        raw = bounded_read(path.parent / name, EVAL.MAX_FILE_BYTES)
        total += len(raw)
        EVAL.require(total <= EVAL.MAX_TOTAL_BYTES, "STUDY_SIZE")
        EVAL.require(EVAL.digest(raw) == expected, "STUDY_INPUT_CHANGED")
    suite = EVAL.read_json(path.parent / "suite.json")
    EVAL.require(EVAL.digest(EVAL.canonical(suite)) == manifest["suite_digest"], "STUDY_SUITE_CHANGED")
    cases = validate_suite(suite, legacy)
    expected = {(case["id"], variant, repeat)
                for case in cases for variant in ("baseline", "candidate")
                for repeat in range(1, case["repeats"] + 1)}
    trials = manifest["trials"]
    EVAL.require(isinstance(trials, list) and len(trials) == len(expected)
                 and {(row["case_id"], row["variant"], row["repeat"]) for row in trials} == expected
                 and len({row["trial_id"] for row in trials}) == len(trials), "STUDY_TRIALS")
    for row in trials:
        request = EVAL.read_json(path.parent / EVAL.relative(row["input_file"]))
        case = next(case for case in cases if case["id"] == row["case_id"])
        EVAL.require(request == {"schema": "routing-study-prompt/1", "trial_id": row["trial_id"], "prompt": case["prompt"]}
                     and EVAL.digest(EVAL.canonical(request)) == row["input_sha256"], "STUDY_PROMPT_CHANGED")
    for variant, rule in manifest["rules"].items():
        EVAL.require(variant in {"baseline", "candidate"} and rule["rule_digest"] ==
                     EVAL.digest(EVAL.canonical(rule["entry_digests"])), "STUDY_RULE_DIGEST")
        for name, digest in rule["entry_digests"].items():
            EVAL.require(files.get("rules/" + variant + "/" + name) == digest, "STUDY_RULE_CHANGED")
    return manifest, cases


def evaluate(study_file, index_file, split, legacy):
    manifest, cases = verify(study_file, legacy)
    EVAL.require(split in {"development", "final"}, "STUDY_SPLIT")
    index = EVAL.read_json(index_file)
    EVAL.require(set(index) == {"schema", "study_digest", "runs"}
                 and index["schema"] == "routing-study-results/1"
                 and index["study_digest"] == manifest["record_digest"]
                 and isinstance(index["runs"], list) and len(index["runs"]) <= len(manifest["trials"]),
                 "STUDY_RESULTS")
    trials = {row["trial_id"]: row for row in manifest["trials"] if row["split"] == split}
    seen, tasks, rows = set(), set(), []
    evidence_bytes = 0
    directory = safe_path(Path(index_file)).parent
    for run in index["runs"]:
        EVAL.require(set(run) == {"trial_id", "results_file", "evidence_dir"}
                     and run["trial_id"] in trials and run["trial_id"] not in seen, "STUDY_RUN_ID")
        seen.add(run["trial_id"])
        trial = trials[run["trial_id"]]
        result_file = directory / EVAL.relative(run["results_file"])
        evidence = safe_path(directory / EVAL.relative(run["evidence_dir"]))
        result = EVAL.read_json(result_file)
        EVAL.require(result.get("host", {}).get("plugin_version") == manifest["rules"][trial["variant"]]["plugin_version"],
                     "STUDY_HOST_VERSION")
        EVAL.require(result["host"].get("platform") == manifest["environment"]["platform"], "STUDY_HOST_PLATFORM")
        EVAL.require(result["host"].get("codex_version") == manifest["environment"]["runtime"], "STUDY_HOST_RUNTIME")
        EVAL.require(len(result.get("observations", [])) == 1
                     and all(item.get("evidence_source") == "codex_desktop_task" for item in result["observations"]),
                     "STUDY_DESKTOP_ONLY")
        item = result["observations"][0]
        EVAL.require(item.get("task_id") not in tasks, "STUDY_TASK_REUSE")
        tasks.add(item.get("task_id"))
        # 中文：新入口在调用旧评分器前约束路径；旧 v1/v2 的解析与评分保持原样。
        # English: Bound paths before calling the old scorer; legacy v1/v2 parsing and scoring stay unchanged.
        captured = {}
        for name in (result["host"].get("readback_file"), item.get("report_file")):
            raw = bounded_read(evidence / EVAL.relative(name), 1_048_576)
            evidence_bytes += len(raw)
            EVAL.require(evidence_bytes <= EVAL.MAX_TOTAL_BYTES, "STUDY_EVIDENCE_SIZE")
            captured[name] = raw
        raw = captured[item["report_file"]]
        text = raw.decode("utf-8")
        EVAL.require(legacy._marker(text, "TRIAL_ID", "study report") == trial["trial_id"]
                     and legacy._marker(text, "INPUT_SHA256", "study report") == trial["input_sha256"],
                     "STUDY_REPORT_INPUT")
        readback = captured[result["host"]["readback_file"]].decode("utf-8")
        EVAL.require(legacy._marker(readback, "RULE_DIGEST", "study host") ==
                     manifest["rules"][trial["variant"]]["rule_digest"], "STUDY_HOST_RULES")
        EVAL.require(legacy._marker(readback, "ENVIRONMENT_DIGEST", "study host") ==
                     EVAL.digest(EVAL.canonical(manifest["environment"])), "STUDY_HOST_ENVIRONMENT")
        profile = {"schema_version": 1, "profile_id": trial["trial_id"], "required_case_ids": [trial["case_id"]],
                   "minimum_pass_rate": 1.0, "minimum_independent_tasks": 1,
                   "required_evidence_level": "host_final_report"}
        # 中文：旧评分器只读取已限额捕获的临时副本，避免再次读取变化或过大的原始文件。
        # English: Give the old scorer bounded captured copies, not mutable or oversized originals.
        with tempfile.TemporaryDirectory(prefix="routing-evidence-") as temporary:
            for name, raw in captured.items():
                target = Path(temporary) / name
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(raw)
            report = legacy.evaluate_host_acceptance(
                cases, legacy.validate_host_profile(profile, cases), result, Path(temporary))
        row = report["cases"][0]
        case = next(case for case in cases if case["id"] == trial["case_id"])
        rows.append({**trial, **row, "group": case["group"], "polarity": case["polarity"]})
    groups = {}
    for variant in ("baseline", "candidate"):
        groups[variant] = {}
        for group in sorted(GROUPS):
            group_rows = [row for row in rows if row["variant"] == variant and row["group"] == group]
            expected = sum(trial["variant"] == variant and next(
                case for case in cases if case["id"] == trial["case_id"])["group"] == group
                for trial in trials.values())
            groups[variant][group] = {
                "expected": expected, "observed": len(group_rows),
                "passed": sum(row["status"] == "PASS" for row in group_rows),
                "missed_trigger": sum(bool(row.get("missing_required")) for row in group_rows),
                "false_activation": sum(bool(row.get("activated_forbidden") or row.get("activated_unrecognized")) for row in group_rows),
                "overload": sum(row.get("active_count", 0) > row.get("max_active", 0) for row in group_rows),
                "phase_errors": sum(bool(row.get("phase_findings")) for row in group_rows)}
    status = "FAILED" if any(row["status"] == "FAILED" for row in rows) else "PARTIAL" if len(seen) < len(trials) else "PASS"
    return {"schema": "routing-study-evaluation/1", "study_digest": manifest["record_digest"],
            "split": split, "status": status, "groups": groups, "trials": rows,
            "missing_trials": sorted(set(trials) - seen), "benefit": "UNKNOWN",
            "description_changes": False, "router_trace_observed": False,
            "limitations": ["Host final reports, not independently signed router traces.",
                            "Counts are descriptive; repeats are not new intent families.",
                            "Logical holdout only; do not tune against exposed final cases."]}


def add_commands(sub, legacy):
    def run(args):
        if args.command == "prepare-study":
            source = args.study_cases or str(ROOT / ("locales/en/" if args.locale == "en" else "")
                                             / "tests/skill-routing-study-cases.json")
            value = prepare(EVAL.read_json(source), args.output, EVAL.read_json(args.environment),
                            args.baseline, legacy, candidate=args.candidate, locale=args.locale)
        else:
            value = evaluate(args.study, args.results, args.split, legacy)
            if args.output:
                EVAL.write_new(args.output, EVAL.canonical(value))
        print(json.dumps(value, ensure_ascii=False, indent=2))
        if args.command == "evaluate-study" and value["status"] != "PASS":
            raise SystemExit(1)
    prepare_parser = sub.add_parser("prepare-study")
    prepare_parser.add_argument("--study-cases")
    prepare_parser.add_argument("--locale", choices=("zh-CN", "en"), default="zh-CN")
    prepare_parser.add_argument("--output", required=True)
    prepare_parser.add_argument("--environment", required=True)
    prepare_parser.add_argument("--baseline", required=True)
    prepare_parser.add_argument("--candidate")
    prepare_parser.set_defaults(func=run)
    evaluate_parser = sub.add_parser("evaluate-study")
    evaluate_parser.add_argument("--study", required=True)
    evaluate_parser.add_argument("--results", required=True)
    evaluate_parser.add_argument("--split", choices=("development", "final"), required=True)
    evaluate_parser.add_argument("--output")
    evaluate_parser.set_defaults(func=run)
