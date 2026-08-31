"""Verify future host-attested runtime model evidence.

Codex 0.150.1 does not provide this contract.  In the absence of an explicit
out-of-band trust anchor every observation is UNAVAILABLE; diagnostic rollout
records are intentionally handled elsewhere and can never enter this path.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import os
from datetime import datetime, timezone
from typing import Any, Dict, Mapping

SCHEMA = "1.0"
KNOWN_MODELS = {"gpt-5.6-luna", "gpt-5.6-terra", "gpt-5.6-sol", "gpt-5.5",
                "gpt-5.4", "gpt-5.4-mini", "gpt-5.3-codex-spark"}
KNOWN_EFFORTS = {"none", "minimal", "low", "medium", "high", "xhigh", "max", "ultra"}
FIELDS = {
    "schema_version", "issuer", "attestation_id", "issued_at", "expires_at",
    "hook_event_name", "session_id", "turn_id", "agent_id", "actual_model",
    "actual_reasoning_effort", "signature",
}


def _canonical(value: Mapping[str, Any]) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _unavailable(code: str) -> Dict[str, str]:
    return {"status": "UNAVAILABLE", "reason_code": code, "model": "", "reasoning_effort": "",
            "attestation_id": "", "issuer": ""}


def _time(value: Any) -> datetime:
    text = str(value or "")
    parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError("timezone required")
    return parsed.astimezone(timezone.utc)


def verify_hook_runtime_evidence(data: Mapping[str, Any], hook_name: str,
                                 now: datetime | None = None) -> Dict[str, str]:
    key = os.environ.get("CP_ASSISTANT_HOST_ATTESTATION_KEY", "")
    if not key:
        return _unavailable("TRUST_ANCHOR_UNAVAILABLE")
    proof = data.get("host_runtime_attestation")
    if not isinstance(proof, Mapping) or set(proof) != FIELDS:
        return _unavailable("ATTESTATION_SCHEMA_INVALID")
    issuers = {item.strip() for item in os.environ.get(
        "CP_ASSISTANT_TRUSTED_HOST_ISSUERS", "codex-host").split(",") if item.strip()}
    issuer = str(proof.get("issuer") or "")
    if proof.get("schema_version") != SCHEMA or issuer not in issuers:
        return _unavailable("ATTESTATION_ISSUER_UNTRUSTED")
    attestation_id = str(proof.get("attestation_id") or "")
    if len(attestation_id) < 16 or len(attestation_id) > 160:
        return _unavailable("ATTESTATION_ID_INVALID")
    bindings = {
        "hook_event_name": hook_name,
        "session_id": str(data.get("session_id") or data.get("sessionId") or ""),
        "turn_id": str(data.get("turn_id") or data.get("turnId") or ""),
        "agent_id": str(data.get("agent_id") or ""),
        "actual_model": str(data.get("actual_model") or ""),
        "actual_reasoning_effort": str(data.get("actual_reasoning_effort") or "").lower(),
    }
    if any(str(proof.get(name) or "") != value for name, value in bindings.items()):
        return _unavailable("ATTESTATION_BINDING_MISMATCH")
    if bindings["actual_model"] not in KNOWN_MODELS or bindings["actual_reasoning_effort"] not in KNOWN_EFFORTS:
        return _unavailable("ATTESTATION_VALUE_INVALID")
    try:
        issued = _time(proof.get("issued_at")); expires = _time(proof.get("expires_at"))
    except (TypeError, ValueError):
        return _unavailable("ATTESTATION_TIME_INVALID")
    current = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    if issued > current or expires < current or (expires - issued).total_seconds() > 300:
        return _unavailable("ATTESTATION_EXPIRED")
    unsigned = {name: proof[name] for name in sorted(FIELDS - {"signature"})}
    expected = hmac.new(key.encode("utf-8"), _canonical(unsigned).encode("utf-8"), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(str(proof.get("signature") or ""), expected):
        return _unavailable("ATTESTATION_SIGNATURE_INVALID")
    return {"status": "VERIFIED", "reason_code": "HOST_ATTESTATION_VERIFIED",
            "model": bindings["actual_model"], "reasoning_effort": bindings["actual_reasoning_effort"],
            "attestation_id": attestation_id, "issuer": issuer}

