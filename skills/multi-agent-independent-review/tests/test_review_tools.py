#!/usr/bin/env python3
"""Regression tests for V5.0 inherited review packet, budgets and model routing."""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PACKET = ROOT / "scripts" / "review_packet.py"
CONTROLLER = ROOT / "scripts" / "review_controller.py"


def run(script: Path, *args: str, cwd: Path | None = None, expected: int = 0) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(
        [sys.executable, str(script), *args],
        cwd=str(cwd) if cwd else None,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if result.returncode != expected:
        raise AssertionError(
            "unexpected return code {} != {}\nSTDOUT:\n{}\nSTDERR:\n{}".format(
                result.returncode, expected, result.stdout, result.stderr
            )
        )
    return result


def git(repo: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=repo, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)


def prepare_repo(path: Path) -> None:
    path.mkdir()
    git(path, "init", "-q")
    git(path, "config", "user.email", "test@example.com")
    git(path, "config", "user.name", "test")
    (path / "a.txt").write_text("a\n", encoding="utf-8")
    git(path, "add", ".")
    git(path, "commit", "-qm", "init")
    (path / "a.txt").write_text("b\n", encoding="utf-8")
    (path / "new.py").write_text("print(1)\n", encoding="utf-8")
    (path / ".env").write_text("TOKEN=secret\n", encoding="utf-8")


def create_confirmed_result(packet_dir: Path, output: Path, reviewer: str, profile: str) -> None:
    run(
        PACKET,
        "result-template",
        "--packet-dir",
        str(packet_dir),
        "--reviewer",
        reviewer,
        "--model-profile",
        profile,
        "--output",
        str(output),
    )
    payload = json.loads(output.read_text(encoding="utf-8"))
    payload["status"] = "pass"
    requested = payload["model_assignment"]
    requested["runtime_model"] = requested["requested_model"]
    requested["runtime_reasoning_effort"] = requested["requested_reasoning_effort"]
    requested["status"] = "confirmed"
    payload["summary"] = "no findings"
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


with tempfile.TemporaryDirectory(prefix="review-tools-v50-") as temp:
    work = Path(temp)
    repo = work / "repo"
    packet = work / "packet"
    review = work / "review"
    prepare_repo(repo)

    run(
        PACKET,
        "create",
        "--repo-path",
        str(repo),
        "--output-dir",
        str(packet),
        "--boundary-id",
        "FB1",
        "--effort-tier",
        "balanced",
    )
    assert (packet / "packet-summary.md").is_file()
    assert (packet / "diff-stat.txt").is_file()
    assert (packet / "name-status.txt").is_file()
    assert (packet / "untracked" / "new.py").is_file()
    assert not (packet / "untracked" / ".env").exists()

    manifest = json.loads((packet / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["schema_version"] == 3
    assert manifest["default_model_profile"] == "luna-medium"
    assert any(
        item["path"] == ".env" and item["reason"] == "excluded-sensitive-path"
        for item in manifest["untracked_files"]
    )
    run(PACKET, "validate", "--packet-dir", str(packet))
    run(PACKET, "freshness", "--packet-dir", str(packet), "--repo-path", str(repo))

    # A workspace change invalidates the packet; exit code 2 is the stale signal.
    (repo / "later.txt").write_text("changed after packet\n", encoding="utf-8")
    run(PACKET, "freshness", "--packet-dir", str(packet), "--repo-path", str(repo), expected=2)
    (repo / "later.txt").unlink()
    run(PACKET, "freshness", "--packet-dir", str(packet), "--repo-path", str(repo))

    packet_hash = (packet / "PACKET_SHA256").read_text(encoding="utf-8").strip()
    result_file = work / "result.json"
    create_confirmed_result(packet, result_file, "cp_review_functional_business", "luna-medium")
    run(
        PACKET,
        "validate-result",
        "--packet-dir",
        str(packet),
        "--result-file",
        str(result_file),
        "--reviewer",
        "cp_review_functional_business",
    )

    run(CONTROLLER, "init", "--review-dir", str(review), "--boundary-id", "FB1", "--risk-level", "high")
    state = json.loads((review / "review-state.json").read_text(encoding="utf-8"))
    assert state["limits"]["max_parallel_reviewers"] == 3
    assert state["limits"]["max_total_reviewers"] == 6
    assert state["limits"]["max_post_review_rounds"] == 2
    assert state["limits"]["max_terra_high_reviewers"] == 1

    run(
        CONTROLLER,
        "isolation",
        "--review-dir",
        str(review),
        "--review-mode",
        "independent-agent",
        "--parent-sandbox",
        "read-only",
        "--declared-sandbox",
        "read-only",
        "--probe-result",
        "write-succeeded",
        "--agent-config-confirmed",
        "--runtime-agent-confirmed",
    )
    state = json.loads((review / "review-state.json").read_text(encoding="utf-8"))
    assert state["isolation"]["isolation_level"] == "logical-readonly"

    run(
        CONTROLLER,
        "plan",
        "--review-dir",
        str(review),
        "--phase",
        "post",
        "--depth",
        "1",
        "--reviewers",
        "cp_review_functional_business",
        "--purpose",
        "test",
        "--packet-sha256",
        packet_hash,
        "--effort-tier",
        "balanced",
    )
    run(
        CONTROLLER,
        "dispatch",
        "--review-dir",
        str(review),
        "--phase",
        "post",
        "--round",
        "1",
        "--reviewer",
        "cp_review_functional_business",
        "--scope",
        "assigned diff",
    )
    state = json.loads((review / "review-state.json").read_text(encoding="utf-8"))
    dispatch = state["phases"]["post"]["rounds"]["1"]["dispatch"]["cp_review_functional_business"]
    assert dispatch["model_profile"] == "luna-medium"
    assert dispatch["requested_model"] == "gpt-5.6-luna"
    assert dispatch["requested_reasoning_effort"] == "medium"

    run(
        CONTROLLER,
        "result",
        "--review-dir",
        str(review),
        "--phase",
        "post",
        "--round",
        "1",
        "--reviewer",
        "cp_review_functional_business",
        "--status",
        "pass",
        "--blocking-count",
        "0",
        "--nonblocking-count",
        "0",
        "--summary",
        "ok",
        "--result-file",
        str(result_file),
    )
    run(
        CONTROLLER,
        "merge",
        "--review-dir",
        str(review),
        "--phase",
        "post",
        "--round",
        "1",
        "--blocking-count",
        "0",
        "--nonblocking-count",
        "0",
        "--root-cause-groups",
        "0",
        "--summary",
        "ok",
    )

    # A clean round on the same packet must stop mechanical additional rounds.
    failed = run(
        CONTROLLER,
        "plan",
        "--review-dir",
        str(review),
        "--phase",
        "post",
        "--depth",
        "2",
        "--reviewers",
        "cp_review_test_delivery",
        "--purpose",
        "duplicate",
        "--packet-sha256",
        packet_hash,
        "--effort-tier",
        "economy",
        expected=1,
    )
    assert "相同审查包无问题通过" in failed.stderr

    # Terra High is allowed only for high/critical risk and with an explicit reason.
    high_review = work / "high-review"
    run(CONTROLLER, "init", "--review-dir", str(high_review), "--boundary-id", "FB2", "--risk-level", "high")
    run(
        CONTROLLER,
        "plan",
        "--review-dir",
        str(high_review),
        "--phase",
        "post",
        "--depth",
        "1",
        "--reviewers",
        "cp_review_security_access",
        "--purpose",
        "security",
        "--packet-sha256",
        packet_hash,
        "--effort-tier",
        "deep",
    )
    no_reason = run(
        CONTROLLER,
        "dispatch",
        "--review-dir",
        str(high_review),
        "--phase",
        "post",
        "--round",
        "1",
        "--reviewer",
        "cp_review_security_access",
        "--scope",
        "auth boundary",
        "--model-profile",
        "terra-high",
        expected=1,
    )
    assert "escalation-reason" in no_reason.stderr
    run(
        CONTROLLER,
        "dispatch",
        "--review-dir",
        str(high_review),
        "--phase",
        "post",
        "--round",
        "1",
        "--reviewer",
        "cp_review_security_access",
        "--scope",
        "auth boundary",
        "--model-profile",
        "terra-high",
        "--escalation-reason",
        "认证与租户隔离属于高风险权限边界",
    )

print("review tools tests passed")
