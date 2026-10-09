"""中文：V5 宿主校验；English: V4 pure policy inputs with explicitly new transport."""
from __future__ import annotations
import copy
from pathlib import Path
from . import routing_context_v4 as prior
from .path_identity import same_path
from .routing_contract import exact, fail, read_document, ref, sha
from .routing_context_contract import CONTEXT_64K, MODE_V2, load_bundle, policy_request, validate_runtime

def build_root_binding(envelope_path, host_session_id, context_runtime):
    identity, binding = prior.build_root_binding(envelope_path, host_session_id)
    binding["schema_version"] = "dispatch-root/3"
    binding["context_runtime"] = validate_runtime(context_runtime, live=True)
    envelope,_=read_document(Path(envelope_path))
    source=envelope.get("routing",{}).get("desktop_default_activation")
    if source is not None:
        exact(source,{"path","definition_ref"},"DEFAULT_ACTIVATION_SOURCE")
        sha(source["definition_ref"])
        if not isinstance(source["path"],str) or not Path(source["path"]).is_absolute():
            fail("DEFAULT_ACTIVATION_PATH")
        binding["envelope_identity_ref"]=ref({"legacy_projection":binding["envelope_identity_ref"],
                                              "desktop_default_activation":source})
    seed=envelope.get('routing',{}).get('research_seed')
    if seed is not None:
        exact(seed,{'source','ordinal'},'SEED_ENVELOPE_FIELDS')
        from .research_seed import definition, CONTRACT
        _,plan,_,_,_=definition(seed['source'])
        if context_runtime.get('bootstrap_contract') != CONTRACT or plan['host_session_ref'] != ref(host_session_id):fail('SEED_ENVELOPE_RUNTIME')
        binding['envelope_identity_ref']=ref({'prior':binding['envelope_identity_ref'],'research_seed':seed})
    elif context_runtime.get('bootstrap_contract'):fail('SEED_ENVELOPE_REQUIRED')
    research=envelope.get('routing',{}).get('research_campaign')
    if research is not None:
        exact(research,{'source','segment_binding_ref'},'RESEARCH_ENVELOPE_FIELDS')
        from .research_campaign import definition,SUPPORTED_CONTRACTS
        _,_,plan,_,_,bindings,_,_=definition(research['source'])
        matched=[b for b in bindings if ref(b)==research['segment_binding_ref']]
        if context_runtime.get('research_contract') not in SUPPORTED_CONTRACTS or plan['host_session_ref']!=ref(host_session_id) or plan['runtime_ref']!=ref(context_runtime) or len(matched)!=1 or identity['task_id']!=matched[0]['root_task_id']:fail('RESEARCH_ROOT_BINDING')
        binding['envelope_identity_ref']=ref({'prior':binding['envelope_identity_ref'],'research_campaign':research})
    elif context_runtime.get('research_contract'):fail('RESEARCH_ROOT_REQUIRED')
    return identity, binding

def verify_root(state, *, cwd, host_session_id):
    identity, binding = build_root_binding(Path(state["sources"]["root_envelope"]),
        host_session_id, state["root_binding"]["context_runtime"])
    if any(state["identity"][k] != v for k, v in identity.items()) \
            or state["root_binding"] != binding or not same_path(Path(cwd), Path(binding["repo_path"])):
        fail("V5_ROOT_BINDING_MISMATCH")

def load_snapshot(state, request, now, *, cwd, host_session_id):
    verify_root(state, cwd=cwd, host_session_id=host_session_id)
    context_runtime=state["root_binding"]["context_runtime"]
    if context_runtime.get('research_contract'):
        from .research_campaign import assert_dispatch
        envelope,_=read_document(Path(state['sources']['root_envelope']))
        assert_dispatch(envelope['routing']['research_campaign'],state,cwd=cwd,session=host_session_id,now=now)
    from .ordinary_routing_v5 import enabled
    ordinary=enabled(context_runtime,request['scenario']['role'])
    # 中文：已发布的复审传输配置不得改变冻结的普通 Worker/Explorer 提示包；后者不使用复审读取器。
    # English: The published reviewer wire profile must not change frozen ordinary
    # Worker/Explorer prompt bundles, which do not use the reviewer reader.
    ordinary_bundle_runtime=None if ordinary and context_runtime.get('delivery_contract')=='same-call-notify/2' else context_runtime
    bundle = load_bundle(request,ordinary_bundle_runtime)
    from .review_vector_transport import enabled as vector_enabled, input_for
    if vector_enabled(state):input_for(state,request)
    if not ordinary and context_runtime.get("context_profile")==CONTEXT_64K and (
            request["scenario"]["context_bucket"]!="bounded-review-64k"
            or request["scenario"]["tools_profile"]!="desktop-context-reader-64k-v1"):
        fail("V5_CONTEXT_SCENARIO_PROFILE_MISMATCH")
    if state["execution_mode"] == "EVALUATION" and bundle["artifacts"]:
        # 中文：冻结的案例摘要须覆盖全部评测输入，代码快照须放入正文。
        # English: The preregistered prompt digest must cover every evaluation input.
        fail("V5_EVALUATION_REQUIRES_SELF_CONTAINED_PROMPT")
    if state["execution_mode"] != "EVALUATION":
        if state["root_binding"]["context_runtime"]["transport_mode"] != MODE_V2:
            fail("V5_PRODUCTION_HOST_COVERAGE_UNQUALIFIED")
        envelope,_=read_document(Path(state["sources"]["root_envelope"]))
        source=envelope.get("routing",{}).get("desktop_default_activation")
        if not source:
            fail("V5_PRODUCTION_HOST_COVERAGE_UNQUALIFIED")
        from .desktop_default_activation import verify_active, verify_root_card_sources
        checked=verify_active(source,expected_identity={key:state["identity"][key]
            for key in ("project_id","repo_fingerprint")},now=now,consumer_task_id=state["identity"]["task_id"])
        definition=checked["definition"]
        verify_root_card_sources(definition,state["sources"]["card_sets"])
        runtime=state["root_binding"]["context_runtime"]
        installed=definition["installation"]
        if runtime.get("context_profile")!=definition.get("context_profile") \
                or runtime.get('ordinary_contract')!=definition.get('ordinary_contract') \
                or (definition['schema_version']=='desktop-default-activation/3'
                    and runtime.get('delivery_contract')!=definition['delivery_contract']) \
                or (not ordinary and ref(request["scenario"]) not in definition["required_scenarios"]) \
                or not same_path(Path(runtime["reader_path"]),Path(installed["enhancement_home"])/"cp-assistant-hooks/review_context_reader.py") \
                or not same_path(Path(runtime["python_path"]),Path(installed["python"]["path"])) \
                or "sha256:"+runtime["python_sha256"]!=installed["python"]["sha256"]:
            fail("DEFAULT_ACTIVATION_ROOT_SCOPE_MISMATCH")
    if state['execution_mode']=='PRODUCTION' and definition['schema_version']=='desktop-default-activation/3':
        from .research_publication import production_snapshot
        return production_snapshot(definition,state,request,now=now,cwd=cwd)
    if context_runtime.get('bootstrap_contract'):
        from .research_bootstrap import snapshot
        return snapshot(state,request,now,cwd=cwd,host_session_id=host_session_id)
    projection = copy.deepcopy(state)
    _,projection["root_binding"]=prior.build_root_binding(Path(state["sources"]["root_envelope"]),host_session_id)
    return prior.load_snapshot(projection, policy_request(request), now, cwd=cwd, host_session_id=host_session_id,
        context_transport=MODE_V2 if state["execution_mode"]=="PRODUCTION" else None,ordinary_compat=ordinary)

def loader(*, cwd, host_session_id):
    return lambda state, request, now: load_snapshot(state, request, now, cwd=cwd, host_session_id=host_session_id)
