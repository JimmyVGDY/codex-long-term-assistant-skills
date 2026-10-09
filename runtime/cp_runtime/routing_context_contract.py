"""中文：V5 独立上下文合同；English: authoritative bytes, distinct from opaque transport."""
from __future__ import annotations

import copy
import hashlib
import os
import stat
from pathlib import Path
from typing import Any, Mapping

from .common import atomic_write_bytes, canonical_json, require_external_state
from .routing_contract import exact, fail, hex_digest, read_document, ref, sha
from .routing_v4 import REQUEST_FIELDS, select as select_policy

MAX_BUNDLE_BYTES = 8_000
MODE = "desktop-authoritative-context/1"
MODE_V2 = "desktop-authoritative-context/2"
CONTEXT_64K = "bounded-review-64k/1"
ISOLATED_PHASES = "isolated-review-phases/1"
ISOLATED_PHASES_V2 = "isolated-review-phases/2"
MAX_LARGE_BUNDLE_BYTES = 64_000
REQUEST = (REQUEST_FIELDS - {"message_sha256"}) | {"business_prompt_sha256", "context_bundle"}
RUNTIME_FIELDS = {"reader_path", "reader_sha256", "python_path", "python_sha256", "transport_mode"}

def context_limits(context_runtime: Mapping[str, Any]) -> tuple[int, int, int]:
    if context_runtime.get("context_profile") == CONTEXT_64K:
        return MAX_LARGE_BUNDLE_BYTES, 65536, 50000
    return MAX_BUNDLE_BYTES, 8192, 10000

def bundle_profile(value: Mapping[str, Any]) -> str | None:
    return value.get("context_profile")

def digest(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()

def safe_file(path: Path) -> Path:
    """中文：读取前拒绝链接、联接点和备用数据流。English: Reject symlinks, junctions and ADS before resolving a source."""
    if not path.is_absolute() or ".." in path.parts:
        fail("V5_ABSOLUTE_PATH_REQUIRED")
    if os.name == "nt" and any(":" in part for part in path.parts[1:]):
        fail("V5_ALTERNATE_STREAM_DENIED")
    for part in (path, *path.parents):
        info = part.lstat()
        if stat.S_ISLNK(info.st_mode) or getattr(info, "st_file_attributes", 0) & 0x400:
            fail("V5_REPARSE_PATH_DENIED")
    if not path.is_file():
        fail("V5_FILE_REQUIRED")
    return path.resolve(strict=True)

def bounded_bytes(path: Path, maximum: int) -> bytes:
    safe = safe_file(path)
    with safe.open("rb") as stream:
        raw = stream.read(maximum + 1)
    if len(raw) > maximum:
        fail("V5_ARTIFACT_TOO_LARGE")
    return raw

def validate_runtime(value: Any, *, live: bool = False) -> dict[str, Any]:
    fields = RUNTIME_FIELDS | ({k for k in ('context_profile','ordinary_contract','evaluation_contract','review_contract','bootstrap_contract','delivery_contract','research_contract') if k in value} if isinstance(value,dict) else set())
    exact(value, fields, "V5_RUNTIME_FIELDS")
    if value["transport_mode"] not in {MODE, MODE_V2}:
        fail("V5_TRANSPORT_MODE")
    if "context_profile" in value and (value["context_profile"] != CONTEXT_64K or value["transport_mode"] != MODE_V2):
        fail("V5_CONTEXT_PROFILE")
    if 'ordinary_contract' in value:
        from .ordinary_routing_v5 import CONTRACT
        if value['ordinary_contract']!=CONTRACT or value['transport_mode']!=MODE_V2:
            fail('V5_ORDINARY_CONTRACT')
    if 'evaluation_contract' in value and (value['evaluation_contract'] not in {ISOLATED_PHASES, ISOLATED_PHASES_V2} or value['transport_mode'] != MODE_V2):
        fail('V5_EVALUATION_CONTRACT')
    if 'review_contract' in value:
        from .review_vector_transport import CONTRACT
        if value['review_contract'] != CONTRACT or value['transport_mode'] != MODE_V2 or 'ordinary_contract' in value:
            fail('V5_REVIEW_CONTRACT')
    if 'bootstrap_contract' in value:
        from .research_seed import CONTRACT
        if value['bootstrap_contract'] != CONTRACT or value['transport_mode'] != MODE_V2 or any(k in value for k in ('ordinary_contract','evaluation_contract','review_contract')):
            fail('V5_BOOTSTRAP_CONTRACT')
    if 'research_contract' in value:
        from .research_campaign import CONTRACT, SUPPORTED_CONTRACTS
        if value['research_contract'] not in SUPPORTED_CONTRACTS or value['transport_mode']!=MODE_V2 or value.get('context_profile')!=CONTEXT_64K or any(k in value for k in ('bootstrap_contract','ordinary_contract','review_contract')):
            fail('V5_RESEARCH_CONTRACT')
        if value['research_contract']==CONTRACT and (value.get('delivery_contract')!='same-call-notify/2' or value.get('evaluation_contract')!=ISOLATED_PHASES_V2):
            fail('V5_RESEARCH_V2_RUNTIME')
    if 'delivery_contract' in value:
        from .notify_delivery import CONTRACT
        if value['delivery_contract'] not in {CONTRACT,'same-call-notify/2'} or value['transport_mode'] != MODE_V2 or value.get('context_profile') != CONTEXT_64K or 'review_contract' in value or ('ordinary_contract' in value and value['delivery_contract']!='same-call-notify/2'):
            fail('V5_NOTIFY_DELIVERY_CONTRACT')
    for name in ("reader", "python"):
        hex_digest(value[name + "_sha256"])
        path = Path(value[name + "_path"])
        if not path.is_absolute() or any(c in str(path) for c in "'\r\n\0"):
            fail("V5_RUNTIME_PATH")
        if live and digest(bounded_bytes(path, 64 * 1024 * 1024)) != value[name + "_sha256"]:
            fail("V5_RUNTIME_CHANGED")
    return copy.deepcopy(value)

def runtime(reader: Path, python: Path, *, transport_mode: str = MODE, context_profile: str | None = None,
            ordinary_contract: str | None = None, evaluation_contract: str | None = None,
            review_contract: str | None = None, delivery_contract: str | None = None) -> dict[str, Any]:
    result = {"transport_mode": transport_mode}
    if context_profile is not None:
        result["context_profile"] = context_profile
    if ordinary_contract is not None:result['ordinary_contract']=ordinary_contract
    if evaluation_contract is not None:result['evaluation_contract']=evaluation_contract
    if review_contract is not None:result['review_contract']=review_contract
    if delivery_contract is not None:result['delivery_contract']=delivery_contract
    for name, path in (("reader", reader), ("python", python.resolve(strict=True))):
        result[name + "_path"] = str(safe_file(path))
        result[name + "_sha256"] = digest(bounded_bytes(path, 64 * 1024 * 1024))
    return validate_runtime(result)

def validate_request(value: Any) -> dict[str, Any]:
    exact(value, REQUEST, "V5_REQUEST_FIELDS")
    if value["schema_version"] != "routing-request/2":
        fail("V5_REQUEST_VERSION")
    hex_digest(value["business_prompt_sha256"])
    bundle = exact(value["context_bundle"], {"path", "sha256"}, "V5_CONTEXT_SOURCE")
    sha(bundle["sha256"])
    if not isinstance(bundle["path"], str) or not Path(bundle["path"]).is_absolute():
        fail("V5_CONTEXT_SOURCE_PATH")
    return copy.deepcopy(value)

def policy_request(value: Mapping[str, Any]) -> dict[str, Any]:
    """中文：仅投影纯选择输入，不调用旧传输准入。English: Pure selection projection, never V4 transport admission or persistence."""
    result = validate_request(dict(value))
    result["schema_version"] = "routing-request/1"
    result["message_sha256"] = result.pop("business_prompt_sha256")
    result.pop("context_bundle")
    return result

def select(request: Mapping[str, Any], snapshot: Mapping[str, Any], *, ordinary_contract: str | None = None) -> dict[str, Any]:
    from .ordinary_routing_v5 import CONTRACT,select as ordinary_select
    use_ordinary=ordinary_contract==CONTRACT and request['scenario']['role'] in {'worker','explorer'}
    result = ordinary_select(policy_request(request), snapshot) if use_ordinary else select_policy(
        policy_request(request), snapshot, ordinary_contract=ordinary_contract)
    if "decision_ref" in result:
        result["request_ref"] = ref(request)
        result["decision_ref"] = ref({k: v for k, v in result.items() if k != "decision_ref"})
    return result

def create_bundle(destination: Path, *, repo: Path, business_prompt: Path,
                  packet_sha256: str, baseline_sha256: str, artifacts: Mapping[str, Path],
                  context_profile: str | None = None) -> dict[str, str]:
    """中文：控制器显式复制已批准材料。English: Explicit controller operation; Hooks never harvest arbitrary source files."""
    import re
    require_external_state(destination, repo)
    hex_digest(packet_sha256); hex_digest(baseline_sha256)
    if context_profile not in {None, CONTEXT_64K}:
        fail("V5_CONTEXT_PROFILE")
    maximum = MAX_LARGE_BUNDLE_BYTES if context_profile == CONTEXT_64K else MAX_BUNDLE_BYTES
    prompt = bounded_bytes(business_prompt, maximum).decode("utf-8").replace("\r\n", "\n").replace("\r", "\n")
    if not prompt.strip() or len(artifacts) > 64:
        fail("V5_BUNDLE_CONTENT")
    materials = []
    for artifact_id, source in sorted(artifacts.items()):
        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,79}", artifact_id):
            fail("V5_ARTIFACT_ID")
        content = bounded_bytes(source, maximum)
        materials.append({"id": artifact_id, "sha256": digest(content), "text": content.decode("utf-8")})
    value = {"schema_version": "review-context-bundle/1", "business_prompt": prompt,
             "business_prompt_sha256": digest(prompt.encode("utf-8")),
             "packet_sha256": packet_sha256, "baseline_sha256": baseline_sha256, "artifacts": materials}
    if context_profile is not None:
        value.update(schema_version="review-context-bundle/2", context_profile=context_profile)
    raw = (canonical_json(value) + "\n").encode("utf-8")
    if len(raw) > maximum:
        fail("V5_BUNDLE_TOO_LARGE")
    if destination.exists() and bounded_bytes(destination, maximum) != raw:
        fail("V5_BUNDLE_IMMUTABLE")
    if not destination.exists():
        destination.parent.mkdir(parents=True, exist_ok=True)
        atomic_write_bytes(destination, raw)
    return {"path": str(destination.resolve()), "sha256": "sha256:" + digest(raw)}

def load_bundle(request: Mapping[str, Any], context_runtime: Mapping[str, Any] | None = None) -> dict[str, Any]:
    validate_request(dict(request))
    raw = bounded_bytes(Path(request["context_bundle"]["path"]), MAX_LARGE_BUNDLE_BYTES)
    if "sha256:" + digest(raw) != request["context_bundle"]["sha256"]:
        fail("V5_BUNDLE_HASH")
    from .routing_contract import _object, _constant
    import json
    value = json.loads(raw, object_pairs_hook=_object, parse_constant=_constant)
    large = isinstance(value,dict) and value.get("schema_version") == "review-context-bundle/2"
    exact(value, {"schema_version", "business_prompt", "business_prompt_sha256", "packet_sha256",
                  "baseline_sha256", "artifacts"} | ({"context_profile"} if large else set()), "V5_BUNDLE_FIELDS")
    if value["schema_version"] not in {"review-context-bundle/1","review-context-bundle/2"} \
            or (large and value["context_profile"] != CONTEXT_64K) or not isinstance(value["business_prompt"], str):
        fail("V5_BUNDLE_VERSION")
    if not large and len(raw) > MAX_BUNDLE_BYTES:
        fail("V5_BUNDLE_TOO_LARGE")
    if context_runtime is not None and bundle_profile(value) != context_runtime.get("context_profile"):
        fail("V5_BUNDLE_RUNTIME_PROFILE_MISMATCH")
    if digest(value["business_prompt"].encode("utf-8")) != request["business_prompt_sha256"] \
            or any(value[k] != request[k] for k in ("business_prompt_sha256", "packet_sha256", "baseline_sha256")):
        fail("V5_BUNDLE_BINDING")
    if not isinstance(value["artifacts"], list) or len(value["artifacts"]) > 64:
        fail("V5_BUNDLE_ARTIFACTS")
    import re
    seen = set()
    for item in value["artifacts"]:
        exact(item, {"id", "sha256", "text"}, "V5_ARTIFACT_FIELDS")
        if not isinstance(item["id"], str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,79}", item["id"]) \
                or item["id"] in seen or not isinstance(item["text"], str) \
                or digest(item["text"].encode("utf-8")) != item["sha256"]:
            fail("V5_ARTIFACT_INTEGRITY")
        seen.add(item["id"])
    return value
