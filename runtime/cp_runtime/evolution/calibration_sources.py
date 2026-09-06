"""中文：显式绑定同项目校准数据源，逐样本验证所属账本。

English: Explicitly bind same-project calibration sources and verify each sample against its own ledger.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from ..common import atomic_write_json
from ..delegation_budget import read_budget
from ..delegation_calibration import offline_replay_many
from ..event_v3 import OwnerTokenLock
from .artifacts import ArtifactError, MAX_BYTES, load, project_identity, seal
from .contracts import sha256_hex
from .storage import safe_child

CONFIG = "evolution/calibration-sources.json"


def register_source(project_dir: Path, ledger_relative: str, samples_relative: str) -> dict[str, Any]:
    identity = project_identity(project_dir)
    ledger_path = safe_child(project_dir, ledger_relative)
    if not ledger_path.is_file() or ledger_path.stat().st_size > MAX_BYTES:
        raise ArtifactError("CALIBRATION_LEDGER_TOO_LARGE")
    budget = read_budget(ledger_path)
    if any(budget["identity"][key] != identity[key] for key in ("project_id", "repo_fingerprint")):
        raise ArtifactError("CALIBRATION_SOURCE_IDENTITY_MISMATCH")
    sample_path = safe_child(project_dir, samples_relative)
    if not sample_path.is_file() or sample_path.stat().st_size > MAX_BYTES:
        raise ArtifactError("CALIBRATION_SOURCE_INVALID")
    path = safe_child(project_dir, CONFIG)
    path.parent.mkdir(parents=True, exist_ok=True)
    with OwnerTokenLock(path, timeout=2):
        existing = load(project_dir, CONFIG, schema="calibration-sources/1") if path.exists() else None
        if existing and existing["identity"] != identity:
            raise ArtifactError("CALIBRATION_SOURCE_IDENTITY_MISMATCH")
        sources = list(existing["sources"]) if existing else []
        entry = {"budget_id": budget["identity"]["budget_id"], "ledger": ledger_relative, "samples": samples_relative}
        matching = [item for item in sources if item["budget_id"] == entry["budget_id"]]
        if matching and matching != [entry]:
            raise ArtifactError("CALIBRATION_SOURCE_CONFLICT")
        if not matching:
            sources.append(entry)
        if len(sources) > 100:
            raise ArtifactError("CALIBRATION_SOURCE_LIMIT")
        value = seal({"schema_version": "calibration-sources/1", "identity": identity,
                      "sources": sources, "execution_authorization": "NONE"})
        atomic_write_json(path, value)
    return value


def project_calibration(project_dir: Path, *, minimum_samples: int = 3, minimum_tasks: int = 3) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    if not safe_child(project_dir, CONFIG).exists():
        return [], {"comparisons": [], "sample_count": 0}
    config = load(project_dir, CONFIG, schema="calibration-sources/1")
    if config["identity"] != project_identity(project_dir, verify_live=False) or not 1 <= len(config["sources"]) <= 100:
        raise ArtifactError("CALIBRATION_SOURCE_IDENTITY_MISMATCH")
    ledgers, samples, annotated = {}, [], []
    total_bytes = 0
    for source in config["sources"]:
        if set(source) != {"budget_id", "ledger", "samples"} or source["budget_id"] in ledgers:
            raise ArtifactError("CALIBRATION_SOURCE_DUPLICATE")
        ledgers[source["budget_id"]] = safe_child(project_dir, source["ledger"])
        path = safe_child(project_dir, source["samples"])
        total_bytes += path.stat().st_size + ledgers[source["budget_id"]].stat().st_size
        if total_bytes > MAX_BYTES:
            raise ArtifactError("CALIBRATION_SOURCE_TOO_LARGE")
        for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if not line.strip():
                continue
            if len(samples) >= 10000:
                raise ArtifactError("CALIBRATION_SAMPLE_LIMIT")
            sample = json.loads(line)
            if sample["budget_id"] != source["budget_id"]:
                raise ArtifactError("CALIBRATION_SOURCE_BUDGET_MISMATCH")
            samples.append(sample)
            annotated.append({"sample": sample, "path": source["samples"], "line_number": line_number,
                              "record_hash": sha256_hex(sample)})
    replay = offline_replay_many(samples, ledger_paths=ledgers, minimum_samples_per_profile=minimum_samples,
                                 minimum_tasks_per_profile=minimum_tasks)
    if replay["identity"] and any(replay["identity"][key] != config["identity"][key] for key in ("project_id", "repo_fingerprint")):
        raise ArtifactError("CALIBRATION_SOURCE_IDENTITY_MISMATCH")
    return annotated, replay
