"""中文：只有原生用户提示记录可以授予超出普通范围的选型。

English: Only a native user prompt record may grant an above-range profile choice.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from cp_runtime.g6_flexible_policy import PROFILES
from cp_runtime.g6_user_choice_v1 import observe_native_prompt, parse_direct_choice, read_choice
from cp_runtime.routing_contract import ref


class G6UserChoiceTests(unittest.TestCase):
    def test_exact_single_directive_parses_all_nine_without_general_list(self):
        for profile in PROFILES:
            with self.subTest(profile=profile):
                _, family, effort = profile.split("-")
                self.assertEqual(parse_direct_choice(f"请使用 gpt-6-{family} {effort}"), profile)
        self.assertIsNone(parse_direct_choice("升级默认 GPT-6 Luna/Sol/Astra 全九档"))
        self.assertIsNone(parse_direct_choice("不要使用 gpt-6-astra high"))
        self.assertIsNone(parse_direct_choice(
            "请解释这段配置，不要改变本任务模型：model = gpt-6-astra reasoning_effort = high"))
        self.assertIsNone(parse_direct_choice(
            "请审查以下代码示例：\n```text\nuse gpt-6-astra high\n```"))

    def test_quoted_or_negated_native_prompt_cannot_raise_hook_profile(self):
        package = Path(__file__).resolve().parents[1]
        hook = package / "hooks" / "cp_hook.py"
        with tempfile.TemporaryDirectory() as temporary:
            env = dict(os.environ, CODEX_HOME=temporary, PLUGIN_ROOT=str(package))
            prompts = (
                "请解释这段配置，不要改变本任务模型：model = gpt-6-astra reasoning_effort = high",
                "请审查以下代码示例：\n```text\nuse gpt-6-astra high\n```",
            )
            for number, prompt in enumerate(prompts, 1):
                session = f"g6-ambiguous-{number}"
                event = {"hook_event_name": "UserPromptSubmit", "session_id": session,
                         "turn_id": "turn-a", "cwd": str(package), "prompt": prompt}
                observed = subprocess.run([sys.executable, "-B", str(hook), "UserPromptSubmit"],
                                          input=json.dumps(event), text=True, capture_output=True,
                                          cwd=package, env=env, timeout=30)
                self.assertEqual(observed.returncode, 0, observed.stderr)
                call = {"hook_event_name": "PreToolUse", "session_id": session,
                        "turn_id": "turn-a", "task_id": session, "cwd": str(package),
                        "tool_name": "spawn_agent", "tool_use_id": "attempt-a",
                        "tool_input": {"task_name": "ambiguous_choice", "agent_type": "worker",
                                       "model": "gpt-6-astra", "reasoning_effort": "high",
                                       "fork_turns": "none", "message": "Bounded case."}}
                result = subprocess.run([sys.executable, "-B", str(hook), "PreToolUse"],
                                        input=json.dumps(call), text=True, capture_output=True,
                                        cwd=package, env=env, timeout=30)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(json.loads(result.stdout)["hookSpecificOutput"]["permissionDecision"],
                                 "deny")

    def test_record_stores_digest_not_prompt_and_binds_turn(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            data = {"hook_event_name": "UserPromptSubmit", "session_id": "session-a",
                    "turn_id": "turn-a", "cwd": str(directory),
                    "prompt": "请使用 gpt-6-astra high"}
            value = observe_native_prompt(data, directory=directory / "choices")
            self.assertEqual(value["profile_id"], "g6-astra-high")
            stored = next((directory / "choices").rglob("*.json")).read_text(encoding="utf8")
            self.assertNotIn(data["prompt"], stored)
            self.assertEqual(read_choice(session_id="session-a", turn_id="turn-a",
                                         cwd=directory, directory=directory / "choices")
                             ["profile_id"], "g6-astra-high")
            self.assertIsNone(read_choice(session_id="session-a", turn_id="other-turn",
                                          cwd=directory, directory=directory / "choices"))

    def test_native_hook_path_admits_all_nine_for_each_role(self):
        package = Path(__file__).resolve().parents[1]
        hook = package / "hooks" / "cp_hook.py"
        with tempfile.TemporaryDirectory() as temporary:
            home = Path(temporary) / "codex-home"
            env = dict(os.environ, CODEX_HOME=str(home), PLUGIN_ROOT=str(package))
            for agent_type in ("worker", "explorer", "cp_review_functional_business"):
                for profile in PROFILES:
                    with self.subTest(agent_type=agent_type, profile=profile):
                        _, family, effort = profile.split("-")
                        session = "g6-choice-" + agent_type + "-" + family + "-" + effort
                        turn = "turn-choice"
                        user_event = {"hook_event_name": "UserPromptSubmit", "session_id": session,
                                      "turn_id": turn, "cwd": str(package),
                                      "prompt": f"请使用 gpt-6-{family} {effort}"}
                        observed = subprocess.run([sys.executable, "-B", str(hook), "UserPromptSubmit"],
                                                  input=json.dumps(user_event), text=True,
                                                  capture_output=True, cwd=package, env=env, timeout=30)
                        self.assertEqual(observed.returncode, 0, observed.stderr)
                        task_name = "choice_task"
                        call = {"hook_event_name": "PreToolUse", "session_id": session,
                                "turn_id": turn, "task_id": session, "cwd": str(package),
                                "tool_name": "spawn_agent", "tool_use_id": "call-choice",
                                "tool_input": {"task_name": task_name, "agent_type": agent_type,
                                               "model": "gpt-6-" + family,
                                               "reasoning_effort": effort,
                                               "fork_turns": "none", "message": "Bounded case."}}
                        permitted = subprocess.run([sys.executable, "-B", str(hook), "PreToolUse"],
                                                   input=json.dumps(call), text=True, capture_output=True,
                                                   cwd=package, env=env, timeout=30)
                        self.assertEqual(permitted.returncode, 0, permitted.stderr)
                        self.assertEqual(permitted.stdout.strip(), "", permitted.stdout)


if __name__ == "__main__":
    unittest.main()
