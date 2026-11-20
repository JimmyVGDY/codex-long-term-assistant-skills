"""中文：当前 Desktop 默认解析独立于冻结的 V3/V4 激活回放。

English: Current Desktop default resolver, separate from frozen V3/V4 activation replay.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from . import g6_budget_v1, g6_catalog, g6_task_scope, research_campaign
from .g6_route_settings import selected_digest
from .g6_flexible_policy import policy
from .routing_contract import ref


def resolve(*, session_id: str, cwd: Path) -> dict[str, Any]:
    """中文：只读当前会话的有效路由，不改动任何根。
    
    English: Read the effective route for this session without changing any root.
    """
    policy()
    binding = g6_task_scope.read(session_id)
    if binding is not None:
        digest = g6_budget_v1.read_budget(Path(binding["new_ledger_path"]))["root"]["policy_digest"]
        return {"policy_id": g6_catalog.policy_id(digest), "policy_digest": digest,
                "selection_mode": "script-first-flexible-v1" if digest == g6_catalog.LEGACY else "role-cost-v2", "status": "NEW_ROOT_BOUND",
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
    digest = selected_digest(cwd)
    return {"policy_id": g6_catalog.policy_id(digest), "policy_digest": digest,
            "selection_mode": "script-first-flexible-v1" if digest == g6_catalog.LEGACY else "role-cost-v2", "status": "NEW_TASK_DEFAULT",
            "session_ref": ref(session_id), "root_path": None}
