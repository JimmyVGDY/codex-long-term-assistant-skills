"""中文：V5 宿主校验；English: V4 pure policy inputs with explicitly new transport."""
from __future__ import annotations
import copy
from pathlib import Path
from . import routing_context_v4 as prior
from .path_identity import same_path
from .routing_contract import fail
from .routing_context_contract import load_bundle, policy_request, validate_runtime

def build_root_binding(envelope_path, host_session_id, context_runtime):
    identity, binding = prior.build_root_binding(envelope_path, host_session_id)
    binding["schema_version"] = "dispatch-root/3"
    binding["context_runtime"] = validate_runtime(context_runtime, live=True)
    return identity, binding

def verify_root(state, *, cwd, host_session_id):
    identity, binding = build_root_binding(Path(state["sources"]["root_envelope"]),
        host_session_id, state["root_binding"]["context_runtime"])
    if any(state["identity"][k] != v for k, v in identity.items()) \
            or state["root_binding"] != binding or not same_path(Path(cwd), Path(binding["repo_path"])):
        fail("V5_ROOT_BINDING_MISMATCH")

def load_snapshot(state, request, now, *, cwd, host_session_id):
    verify_root(state, cwd=cwd, host_session_id=host_session_id)
    bundle = load_bundle(request)
    if state["execution_mode"] == "EVALUATION" and bundle["artifacts"]:
        # 中文：冻结的案例摘要须覆盖全部评测输入，代码快照须放入正文。
        # English: The preregistered prompt digest must cover every evaluation input.
        fail("V5_EVALUATION_REQUIRES_SELF_CONTAINED_PROMPT")
    if state["execution_mode"] != "EVALUATION":
        # 中文：工具覆盖证明不足时禁止生产启用。
        # English: Production remains unavailable until tool-surface coverage is proven.
        fail("V5_PRODUCTION_HOST_COVERAGE_UNQUALIFIED")
    projection = copy.deepcopy(state)
    projection["root_binding"]["schema_version"] = "dispatch-root/2"
    projection["root_binding"].pop("context_runtime")
    return prior.load_snapshot(projection, policy_request(request), now, cwd=cwd, host_session_id=host_session_id)

def loader(*, cwd, host_session_id):
    return lambda state, request, now: load_snapshot(state, request, now, cwd=cwd, host_session_id=host_session_id)
