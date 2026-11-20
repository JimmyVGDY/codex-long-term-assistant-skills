"""中文：跨进程偏好修改、过期、撤销和原操作保护。
English: Cross-process preference changes, expiration, revocation and action protection.
"""

import json
import os
import subprocess
import sys
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

from cp_runtime import gate_preferences as prefs
from cp_runtime.gate_contract import write_failure
from cp_runtime.routing_contract import RoutingError


class DesktopPreferenceTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.repo = Path(__file__).resolve().parents[1]
        env = patch.dict(os.environ, CODEX_HOME=self.tmp.name)
        env.start()
        self.addCleanup(env.stop)
        self.expires = (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat()
        self.project = prefs.project_binding(self.repo)["identity"]

    def update(self, values, revision=0, task="sample"):
        args = dict(action="write", task=task, revision=revision, values=values, expires_at=self.expires)
        view = prefs.manage(self.repo, "preview", **args)
        return prefs.manage(self.repo, "apply", confirmation=view["request_ref"], **args)

    def test_scope_expiry_revocation_invalid_fields_and_hard_actions(self):
        self.assertFalse(prefs.location(self.repo).exists())
        self.update({"retry_limit": 2}, task=None)
        self.update({"retry_limit": 0, "verify_optional_index": True}, 1)
        self.assertEqual(prefs.effective(self.repo, self.project, "sample", "write")["retry_limit"], 0)
        self.assertEqual(prefs.effective(self.repo, self.project, "another", "write"), {"retry_limit": 2})
        self.assertEqual(prefs.effective(self.repo, self.project, "sample", "dispatch"), {})
        self.assertEqual(prefs.effective(self.repo, self.project, "sample", "write", at=self.expires), {})
        self.update({}, 2)
        self.assertEqual(prefs.effective(self.repo, self.project, "sample", "write"), {"retry_limit": 2})
        with self.assertRaises(RoutingError):
            self.update({"allow_write": True}, 3)
        with self.assertRaises(RoutingError):
            self.update({"retry_limit": 3}, 3)
        self.assertEqual(write_failure("PATH_ESCAPE")["decision"], "STOP_AFFECTED_ACTION")
        self.assertEqual(
            write_failure("LEGACY_WRITE_ORIGIN_UNAVAILABLE")["next_action"],
            "prepare_supported_native_patch_in_the_same_project",
        )

    def test_two_processes_same_revision_and_crash_recovery(self):
        base = [
            sys.executable,
            "-B",
            str(self.repo / "scripts/cp-runtime.py"),
            "gate-settings",
            "apply",
            "--repo-path",
            str(self.repo),
            "--action",
            "write",
            "--revision",
            "0",
            "--expires-at",
            self.expires,
        ]
        commands = []
        for limit in [0, 2]:
            preview = prefs.manage(
                self.repo,
                "preview",
                action="write",
                revision=0,
                values={"retry_limit": limit},
                expires_at=self.expires,
            )
            commands.append([*base, "--retry-limit", str(limit), "--confirm", preview["request_ref"]])
        with ThreadPoolExecutor(2) as pool:
            results = list(pool.map(lambda c: subprocess.run(c, capture_output=True, timeout=30), commands))
        self.assertEqual(sorted(p.returncode for p in results), [0, 1])
        winner = 0 if results[0].returncode == 0 else 1
        repeated = subprocess.run(commands[winner], capture_output=True, timeout=30)
        self.assertTrue(json.loads(repeated.stdout)["idempotent"])
        path = prefs.location(self.repo)
        saved = path.read_bytes()
        code = "from cp_runtime.event_v2 import OwnerTokenLock\nimport sys,time\nfrom pathlib import Path\nwith OwnerTokenLock(Path(sys.argv[1])):\n print('locked',flush=True)\n time.sleep(20)\n"
        env = dict(os.environ, PYTHONPATH=str(self.repo / "runtime"))
        owner = subprocess.Popen(
            [sys.executable, "-B", "-c", code, str(path)], env=env, stdout=subprocess.PIPE
        )
        try:
            self.assertEqual(owner.stdout.readline().strip(), b"locked")
        finally:
            owner.kill()
            owner.wait(timeout=10)
            owner.stdout.close()
        self.assertEqual(path.read_bytes(), saved)
        self.update({"backoff_ms": 100}, revision=1, task=None)
        self.assertEqual(prefs.manage(self.repo, "show", action="write")["revision"], 2)

    def test_full_page_archives_active_scope_and_keeps_rollback_available(self):
        with patch.object(prefs, "MAX_EVENTS", 2):
            first = self.update({"retry_limit": 1}, 0, task=None)
            self.update({"retry_limit": 2}, 1)
            self.update({}, 2)
            self.assertEqual(prefs.effective(self.repo, self.project, "sample", "write"), {"retry_limit": 1})
            repeated = prefs.manage(
                self.repo,
                "apply",
                action="write",
                revision=0,
                task=None,
                values={"retry_limit": 1},
                expires_at=self.expires,
                confirmation=first["request_ref"],
            )
            self.assertTrue(repeated["idempotent"])
            self.update({}, 3, task=None)
            self.assertEqual(prefs.effective(self.repo, self.project, "sample", "write"), {})
