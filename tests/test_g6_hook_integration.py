"""中文：以一条合成 Desktop Hook 链路覆盖默认决策到回执。

English: One synthetic Desktop Hook slice from default decision through receipt.
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from cp_runtime import g6_budget_v1
from cp_runtime.g6_fact_collector import read_metric_receipt
from cp_runtime.capability_gate import GatePolicy
from cp_runtime.capability_operation import CapabilityOperation
from cp_runtime.capability_operation_workflow import OperationWorkflow
from cp_runtime.capability_store import CapabilityStore
from cp_runtime.g6_hook_v1 import preview
from cp_runtime.project import onboard_project
from cp_runtime.routing_contract import ref


class G6HookIntegrationTests(unittest.TestCase):
    def test_projectless_desktop_scope_uses_unknown_baseline_default(self):
        package = Path(__file__).resolve().parents[1]
        hook = package / "hooks" / "cp_hook.py"
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            workspace = base / "plain-workspace"
            workspace.mkdir()
            home = base / "codex-home"
            session = "g6-projectless-session"
            with mock.patch.dict(os.environ, CODEX_HOME=str(home)):
                plan = preview(session_id=session, cwd=workspace, agent_type="explorer",
                               task_name="plain_check", message="Read this local folder.")
            self.assertEqual(plan["approved_profile"], "g6-sol-medium")
            self.assertIn("baseline_sha256", plan["missing_evidence"])
            event = {"hook_event_name": "PreToolUse", "session_id": session,
                     "task_id": "plain-task", "cwd": str(workspace), "tool_name": "spawn_agent",
                     "tool_use_id": "plain-call", "tool_input": plan["exact_tool_parameters"]}
            env = dict(os.environ, CODEX_HOME=str(home), PLUGIN_ROOT=str(package))
            proc = subprocess.run([sys.executable, "-B", str(hook), "PreToolUse"],
                                  input=json.dumps(event), text=True, capture_output=True,
                                  cwd=workspace, env=env, timeout=30)
            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertEqual(proc.stdout.strip(), "")

    def test_enabled_optional_write_gate_keeps_safe_parent_and_child_path(self):
        package = Path(__file__).resolve().parents[1]
        hook = package / "hooks" / "cp_hook.py"
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            repo = base / "repo"
            repo.mkdir()
            def git(*args):
                subprocess.run(["git", "-C", str(repo), *args], check=True,
                               capture_output=True)
            git("init", "-q")
            git("config", "user.name", "Test")
            git("config", "user.email", "test@example.invalid")
            (repo / "app.py").write_text("def public():\n    return 1\n", encoding="utf8")
            git("add", ".")
            git("commit", "-qm", "baseline")
            profile = onboard_project(repo, "G6CAP", "Gate test", base / "context")
            store = CapabilityStore(profile.profile_path, repo)
            gate_root = base / "gate-config"
            gate_policy = GatePolicy(store, gate_root)
            gate_policy.set_enabled(True, None)
            home = base / "codex-home"
            session = "g6-enabled-gate-session"
            env = dict(os.environ, CODEX_HOME=str(home), PLUGIN_ROOT=str(package),
                       CP_CAPABILITY_GATE_ROOT=str(gate_root))
            env.pop("CP_DELEGATION_BUDGET_PATH", None)
            def invoke(kind, data):
                return subprocess.run([sys.executable, "-B", str(hook), kind],
                                      input=json.dumps(data), text=True, capture_output=True,
                                      cwd=repo, env=env, timeout=30)
            spawn = {"hook_event_name": "PreToolUse", "session_id": session,
                     "task_id": "g6-cap-task", "turn_id": "turn-1", "cwd": str(repo),
                     "tool_name": "spawn_agent", "tool_use_id": "spawn-1",
                     "tool_input": {"task_name": "g6_child", "agent_type": "worker",
                                    "model": "gpt-6-sol", "reasoning_effort": "medium",
                                    "fork_turns": "none", "message": "Inspect this fixture."}}
            first = invoke("PreToolUse", spawn)
            self.assertEqual(first.returncode, 0, first.stderr)
            self.assertEqual(first.stdout.strip(), "")
            ledger = home / "cp-assistant" / "g6-routing" / "roots" / (ref(session)[7:] + ".jsonl")
            state = g6_budget_v1.read_budget(ledger)
            prepared = next(iter(state["permits"].values()))
            metric_ref = prepared["facts"]["source_refs"][0]
            with mock.patch.dict(os.environ, CODEX_HOME=str(home)):
                metrics = read_metric_receipt(metric_ref, identity=state["root"]["identity"],
                                              host_session_ref=state["root"]["host_session_ref"],
                                              baseline_sha256=prepared["facts"]["baseline_sha256"])
            self.assertEqual(metrics["metrics"]["changed_files"]["value"], 0)
            created = invoke("PostToolUse", {**spawn, "hook_event_name": "PostToolUse",
                         "tool_response": {"task_name": "/root/g6_child"}})
            self.assertEqual(created.returncode, 0, created.stderr)
            child_id = "g6-cap-child-1"
            transcript = home / "sessions" / "2026" / "10" / "09" / ("rollout-" + child_id + ".jsonl")
            transcript.parent.mkdir(parents=True)
            transcript.write_text(json.dumps({"type": "session_meta", "payload": {
                "id": child_id, "cwd": str(repo), "source": {"subagent": {"thread_spawn": {
                    "parent_thread_id": session, "depth": 1, "agent_role": "worker",
                    "agent_path": "/root/g6_child"}}}}}) + "\n", encoding="utf8")
            write = {"hook_event_name": "PreToolUse", "session_id": session,
                     "task_id": "g6-cap-task", "turn_id": "turn-1", "cwd": str(repo),
                     "tool_name": "Write", "tool_use_id": "write-1",
                     "tool_input": {"file_path": str(repo / "app.py"), "content": "x"}}
            for payload in (write, {**write, "agent_id": child_id, "agent_type": "worker",
                                    "transcript_path": str(transcript), "tool_use_id": "write-2"}):
                with self.subTest(child=bool(payload.get("agent_id"))):
                    result = invoke("PreToolUse", payload)
                    self.assertEqual(result.returncode, 0, result.stderr)
                    response = json.loads(result.stdout)
                    self.assertEqual(response["hookSpecificOutput"]["permissionDecision"], "deny")
                    self.assertIn("next_action=use_supervised_apply_patch_operation_v2",
                                  response["hookSpecificOutput"]["permissionDecisionReason"])
            patch_text = ("*** Begin Patch\n*** Update File: app.py\n@@\n"
                          "-    return 1\n+    return 2\n*** End Patch\n")
            patch_event = {**write, "tool_name": "apply_patch", "tool_use_id": "patch-a",
                           "tool_input": {"command": patch_text}}
            first_patch = invoke("PreToolUse", patch_event)
            self.assertEqual(first_patch.returncode, 0, first_patch.stderr)
            self.assertIn("permissionDecision", first_patch.stdout)
            operation_ref = re.search(r"OP2-[0-9a-f]{16}-[0-9a-f]{32}", first_patch.stdout).group(0)
            operation = CapabilityOperation.open(gate_policy, operation_ref)
            OperationWorkflow(operation).prepare(operation_ref, term="public")
            allowed = invoke("PreToolUse", {**patch_event, "tool_use_id": "patch-b"})
            self.assertEqual(allowed.returncode, 0, allowed.stderr)
            self.assertEqual(allowed.stdout.strip(), "")

    def test_unknown_evidence_default_reserves_once_and_consumes_native_receipt(self):
        repo = Path(__file__).resolve().parents[1]
        hook = repo / "hooks" / "cp_hook.py"
        session = "g6-hook-integration-session"
        with tempfile.TemporaryDirectory() as home:
            env = dict(os.environ, CODEX_HOME=home, PLUGIN_ROOT=str(repo))
            with mock.patch.dict(os.environ, CODEX_HOME=home):
                plan = preview(session_id=session, cwd=repo, agent_type="worker",
                               task_name="g6_smoke", message="Inspect one bounded task.")
            self.assertEqual(plan["approved_profile"], "g6-sol-medium")
            args = plan["exact_tool_parameters"]
            event = {"hook_event_name": "PreToolUse", "tool_name": "spawn_agent",
                     "tool_input": args, "tool_use_id": "g6-call-1",
                     "session_id": session, "task_id": "g6-task-1", "cwd": str(repo)}
            proc = subprocess.run([sys.executable, "-B", str(hook), "PreToolUse"],
                                  input=json.dumps(event), text=True, capture_output=True,
                                  cwd=repo, env=env, timeout=30)
            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertEqual(proc.stdout.strip(), "", proc.stdout)
            root = Path(home) / "cp-assistant" / "g6-routing" / "roots" / (ref(session)[7:] + ".jsonl")
            state = g6_budget_v1.read_budget(root)
            self.assertEqual(len(state["reservations"]), 1)
            self.assertEqual(state["root"]["task_id"], "g6-task-1")
            self.assertEqual(state["permits"][next(iter(state["permits"]))]["approved_profile"],
                             "g6-sol-medium")
            post = {**event, "hook_event_name": "PostToolUse",
                    "tool_response": {"task_name": "/root/g6_smoke"}}
            proc = subprocess.run([sys.executable, "-B", str(hook), "PostToolUse"],
                                  input=json.dumps(post), text=True, capture_output=True,
                                  cwd=repo, env=env, timeout=30)
            self.assertEqual(proc.returncode, 0, proc.stderr)
            state = g6_budget_v1.read_budget(root)
            self.assertEqual(len(state["receipts"]), 1)
            self.assertEqual(next(iter(state["receipts"].values()))["disposition"], "created")
            continuation = {"hook_event_name": "PreToolUse", "tool_name": "followup_task",
                            "tool_input": {"target": "g6_smoke", "message": "Continue"},
                            "tool_use_id": "g6-followup-1", "session_id": session,
                            "task_id": "g6-task-1", "cwd": str(repo)}
            proc = subprocess.run([sys.executable, "-B", str(hook), "PreToolUse"],
                                  input=json.dumps(continuation), text=True, capture_output=True,
                                  cwd=repo, env=env, timeout=30)
            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertIn("G6_CONTINUATION_HOST_BINDING_UNAVAILABLE", proc.stdout)
            self.assertEqual(len(g6_budget_v1.read_budget(root)["reservations"]), 1)
            message_event = {**continuation, "tool_name": "send_message",
                             "tool_use_id": "g6-message-1"}
            proc = subprocess.run([sys.executable, "-B", str(hook), "PreToolUse"],
                                  input=json.dumps(message_event), text=True, capture_output=True,
                                  cwd=repo, env=env, timeout=30)
            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertEqual(proc.stdout.strip(), "")
            child_id = "g6-native-child-1"
            transcript = Path(home) / "sessions" / "2026" / "10" / "09" / (
                "rollout-" + child_id + ".jsonl")
            transcript.parent.mkdir(parents=True)
            header = {"type": "session_meta", "payload": {"id": child_id,
                      "cwd": str(repo), "source": {"subagent": {"thread_spawn": {
                          "parent_thread_id": session, "depth": 1,
                          "agent_role": "worker", "agent_path": "/root/g6_smoke"}}}}}
            complete = {"type": "event_msg", "payload": {"type": "task_complete"}}
            transcript.write_text(json.dumps(header) + "\n", encoding="utf-8")
            child_message = {"hook_event_name": "PreToolUse", "session_id": session,
                             "agent_id": child_id, "agent_type": "worker", "cwd": str(repo),
                             "transcript_path": str(transcript),
                             "tool_name": "collaborationsend_message",
                             "tool_input": {"target": "/root", "message": "Read-only status."},
                             "tool_use_id": "child-message-1"}
            before_message = root.read_bytes()
            proc = subprocess.run([sys.executable, "-B", str(hook), "PreToolUse"],
                                  input=json.dumps(child_message), text=True, capture_output=True,
                                  encoding="utf-8", errors="replace",
                                  cwd=repo, env=env, timeout=30)
            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertEqual(proc.stdout.strip(), "")
            self.assertEqual(root.read_bytes(), before_message)
            for target in ("g6_smoke", "/root/g6_smoke"):
                with self.subTest(active_child_target=target):
                    allowed = {**child_message, "tool_input": {"target": target,
                                                                "message": "Existing active target."}}
                    proc = subprocess.run([sys.executable, "-B", str(hook), "PreToolUse"],
                                          input=json.dumps(allowed), text=True, capture_output=True,
                                          encoding="utf-8", errors="replace", cwd=repo, env=env, timeout=30)
                    self.assertEqual(proc.returncode, 0, proc.stderr)
                    self.assertEqual(proc.stdout.strip(), "")
                    self.assertEqual(root.read_bytes(), before_message)
            for target in ("", "/root/foreign"):
                with self.subTest(child_target=target):
                    denied = {**child_message, "tool_input": {"target": target,
                                                                "message": "No forwarding."}}
                    proc = subprocess.run([sys.executable, "-B", str(hook), "PreToolUse"],
                                          input=json.dumps(denied), text=True,
                                          capture_output=True, encoding="utf-8", errors="replace",
                                          cwd=repo, env=env, timeout=30)
                    self.assertEqual(proc.returncode, 0, proc.stderr)
                    self.assertIn('"permissionDecision": "deny"', proc.stdout)
                    self.assertEqual(root.read_bytes(), before_message)
            foreign_header = {"type": "session_meta", "payload": {"id": "foreign-child",
                              "cwd": str(repo), "source": {"subagent": {"thread_spawn": {
                                  "parent_thread_id": "other-session", "depth": 1,
                                  "agent_role": "worker", "agent_path": "/root/foreign"}}}}}
            foreign_transcript = transcript.with_name("rollout-foreign-child.jsonl")
            foreign_transcript.write_text(json.dumps(foreign_header) + "\n", encoding="utf-8")
            foreign = {**child_message, "agent_id": "foreign-child",
                       "transcript_path": str(foreign_transcript)}
            proc = subprocess.run([sys.executable, "-B", str(hook), "PreToolUse"],
                                  input=json.dumps(foreign), text=True, capture_output=True,
                                  encoding="utf-8", errors="replace",
                                  cwd=repo, env=env, timeout=30)
            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertIn('"permissionDecision": "deny"', proc.stdout)
            self.assertEqual(root.read_bytes(), before_message)
            unknown_header = json.loads(json.dumps(header))
            unknown_header["payload"]["id"] = "unknown-child"
            unknown_header["payload"]["source"]["subagent"]["thread_spawn"][
                "agent_path"] = "/root/unbound"
            unknown_transcript = transcript.with_name("rollout-unknown-child.jsonl")
            unknown_transcript.write_text(json.dumps(unknown_header) + "\n", encoding="utf-8")
            unknown = {**child_message, "agent_id": "unknown-child",
                       "transcript_path": str(unknown_transcript)}
            proc = subprocess.run([sys.executable, "-B", str(hook), "PreToolUse"],
                                  input=json.dumps(unknown), text=True, capture_output=True,
                                  encoding="utf-8", errors="replace",
                                  cwd=repo, env=env, timeout=30)
            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertIn('"permissionDecision": "deny"', proc.stdout)
            self.assertEqual(root.read_bytes(), before_message)
            child_write = {"hook_event_name": "PreToolUse", "session_id": session,
                           "agent_id": child_id, "agent_type": "worker", "cwd": str(repo),
                           "transcript_path": str(transcript), "tool_name": "Write",
                           "tool_input": {"file_path": str(repo / "tmp.txt"), "content": "x"},
                           "tool_use_id": "child-write-1"}
            proc = subprocess.run([sys.executable, "-B", str(hook), "PreToolUse"],
                                  input=json.dumps(child_write), text=True, capture_output=True,
                                  cwd=repo, env=env, timeout=30)
            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertNotIn("V5_CHILD_ONLY_FIXED_READER", proc.stdout)
            with transcript.open("a", encoding="utf-8") as stream:
                stream.write(json.dumps(complete) + "\n")
            stop = {"hook_event_name": "SubagentStop", "session_id": session,
                    "agent_id": child_id, "agent_type": "worker", "cwd": str(repo),
                    "agent_transcript_path": str(transcript), "terminal_outcome": "PASS"}
            proc = subprocess.run([sys.executable, "-B", str(hook), "SubagentStop"],
                                  input=json.dumps(stop), text=True, capture_output=True,
                                  cwd=repo, env=env, timeout=30)
            self.assertEqual(proc.returncode, 0, proc.stderr)
            state = g6_budget_v1.read_budget(root)
            self.assertEqual(len(state["terminals"]), 1)
            self.assertEqual(next(iter(state["terminals"].values()))["outcome"], "PASS")
            after_stop = root.read_bytes()
            proc = subprocess.run([sys.executable, "-B", str(hook), "PreToolUse"],
                                  input=json.dumps(child_message), text=True, capture_output=True,
                                  encoding="utf-8", errors="replace",
                                  cwd=repo, env=env, timeout=30)
            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertIn("G6_MESSAGE_SOURCE_NOT_ACTIVE_IN_ROOT", proc.stdout)
            self.assertEqual(root.read_bytes(), after_stop)
            adjusted = {"task_name": "g6_adjust", "agent_type": "worker",
                        "model": "gpt-6-sol", "reasoning_effort": "high",
                        "fork_turns": "none", "message": "Analyze a different bounded task."}
            next_event = {**event, "tool_input": adjusted, "tool_use_id": "g6-call-2"}
            proc = subprocess.run([sys.executable, "-B", str(hook), "PreToolUse"],
                                  input=json.dumps(next_event), text=True, capture_output=True,
                                  cwd=repo, env=env, timeout=30)
            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertEqual(proc.stdout.strip(), "")
            state = g6_budget_v1.read_budget(root)
            self.assertEqual(len(state["reservations"]), 2)
            self.assertTrue(any(p["approved_profile"] == "g6-sol-high"
                                for p in state["permits"].values()))
            self.assertEqual(g6_budget_v1.snapshot(state,
                             work_item_id=next(p["work_item_id"] for p in state["permits"].values()
                                               if p["task_name"] == "g6_adjust"), depth=0)
                             ["upward_adjustments_used"], 1)


if __name__ == "__main__":
    unittest.main()
