"""中文：先确认已安装读取器支持追加协议，再允许原生控制器写入新事件。

English: Verify the installed reader before a native controller writes extension events.
"""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

from .capability_store import bounded_read
from .common import resolve_codex_home
from .payload_integrity import load_manifest

RUNTIME_FILES = (
    "g6_allowance_authority.py", "g6_allowance_contract.py", "g6_budget_v1.py",
    "g6_continuation.py", "g6_flexible_policy.py", "g6_hook_v1.py", "g6_retry_v1.py",
    "g6_review_controller.py", "g6_review_receipt_v1.py", "g6_review_requests.py", "g6_runtime_support.py",
)


def installed_allowance_support() -> dict:
    result = {"schema_version": "g6-installed-allowance-support/1", "supported": False,
              "allowance_protocol": "g6-allowance/1", "reason_code": "INSTALLED_READER_UNAVAILABLE"}
    home = resolve_codex_home()
    try:
        state = json.loads(bounded_read(home / "cp-assistant-v6-state.json", 262_144))
        version = state.get("version")
        if state.get("mode") != "plugin" or not isinstance(version, str) or not re.fullmatch(r"\d+\.\d+\.\d+", version):
            return result
        transaction = home / "cp-assistant-v6-transaction.json"
        if transaction.exists():
            journal = json.loads(bounded_read(transaction, 1_048_576))
            if journal.get("stage") not in {"COMMITTED", "ROLLED_BACK"}:
                return {**result, "reason_code": "INSTALLATION_TRANSACTION_IN_PROGRESS"}
        cache = home / "plugins/cache/cp-assistant-local/codex-cross-project-engineering-assistant" / version
        manifest = load_manifest(cache / "PLUGIN_PAYLOAD_MANIFEST.json")
        if manifest["version"] != version or manifest["package"] != "codex-cross-project-engineering-assistant":
            return {**result, "reason_code": "INSTALLED_PAYLOAD_IDENTITY_MISMATCH"}
        entries = {row["path"]: row for row in manifest["files"]}
        caller = Path(__file__).resolve().parent
        for name in RUNTIME_FILES:
            relative = "runtime/cp_runtime/" + name
            expected = entries.get(relative, {}).get("sha256")
            for source in (cache / relative, home / relative, caller / name):
                if expected is None or hashlib.sha256(bounded_read(source, 1_048_576)).hexdigest() != expected:
                    return {**result, "reason_code": "INSTALLED_READER_OR_CALLER_MISMATCH"}
        expected = entries.get("hooks/cp_hook.py", {}).get("sha256")
        if expected is None or hashlib.sha256(bounded_read(home / "cp-assistant-hooks/cp_hook.py", 1_048_576)).hexdigest() != expected:
            return {**result, "reason_code": "INSTALLED_HOOK_MISMATCH"}
        return {**result, "supported": True, "reason_code": "MATCHING_INSTALLED_READERS",
                "version": version, "payload_digest": manifest["payload_digest"],
                "journal_versions": ["g6-budget-journal/1", "g6-budget-journal/2"]}
    except (OSError, ValueError, RuntimeError, KeyError, TypeError):
        return result
