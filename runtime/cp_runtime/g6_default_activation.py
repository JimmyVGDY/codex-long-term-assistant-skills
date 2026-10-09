"""中文：当前 Desktop 默认解析独立于冻结的 V3/V4 激活回放。

English: Current Desktop default resolver, separate from frozen V3/V4 activation replay.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from . import g6_handoff_v1, research_campaign
from .g6_flexible_policy import POLICY_ID, POLICY_SHA256, policy
from .routing_contract import ref


def resolve(*, session_id: str, cwd: Path) -> dict[str, Any]:
    """中文：只读当前会话的有效路由，不改动任何根。
    
    English: Read the effective route for this session without changing any root.
    """
    policy()
    binding = g6_handoff_v1.read(session_id)
    if binding is not None:
        return {"policy_id": POLICY_ID, "policy_digest": "sha256:" + POLICY_SHA256,
                "selection_mode": "script-first-flexible-v1", "status": "NEW_ROOT_BOUND",
                "session_ref": ref(session_id), "root_path": binding["new_ledger_path"]}
    if research_campaign._head(session_id).exists():
        return {"policy_id": None, "policy_digest": None,
                "selection_mode": "historical-root-owned", "status": "LEGACY_ROOT_BOUND",
                "session_ref": ref(session_id), "root_path": None}
    from .routing_registry_v4 import lookup as legacy_lookup
    from .routing_registry_v5 import lookup as v5_lookup
    if v5_lookup(host_session_id=session_id) is not None \
            or legacy_lookup(cwd=str(cwd), host_session_id=session_id) is not None:
        return {"policy_id": None, "policy_digest": None,
                "selection_mode": "historical-root-owned", "status": "LEGACY_ROOT_BOUND",
                "session_ref": ref(session_id), "root_path": None}
    return {"policy_id": POLICY_ID, "policy_digest": "sha256:" + POLICY_SHA256,
            "selection_mode": "script-first-flexible-v1", "status": "NEW_TASK_DEFAULT",
            "session_ref": ref(session_id), "root_path": None}
