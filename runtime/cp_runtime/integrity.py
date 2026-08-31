"""中文：宿主绑定的完整性密钥环与独立事件链封印。

English: Host-bound integrity keyring and detached event-chain seals.
"""
from __future__ import annotations

import base64
import ctypes
import getpass
import hashlib
import hmac
import json
import os
import platform
import secrets
import stat
import tempfile
from ctypes import wintypes
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional

from .event_v2 import (EventContractError, OwnerTokenLock, ZERO_HASH, _read_event_files_unlocked,
                       _verify_events, canonical_json, event_segment_paths)
from .atomic_io import replace_with_retry

KEYRING_SCHEMA = 1
SEAL_SCHEMA = 1
PURPOSES = ("event-hmac", "release-attestation")


class IntegrityError(RuntimeError):
    pass


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")


def _sha(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _codex_home() -> Path:
    raw = os.environ.get("CODEX_HOME", "").strip()
    if os.name == "nt" and raw.startswith("/mnt/") and len(raw) > 6 and raw[5].isalpha() and raw[6] == "/":
        raw = raw[5].upper() + ":\\" + raw[7:].replace("/", "\\")
    return Path(raw).expanduser() if raw else Path.home() / ".codex"


def default_keyring_path() -> Path:
    override = os.environ.get("CP_ASSISTANT_KEYRING_PATH", "").strip()
    return Path(override).expanduser() if override else _codex_home() / "integrity" / "cp-assistant-keyring.json"


def _binding_id() -> str:
    return "sha256:" + _sha("%s|%s|%s" % (os.name, platform.node(), getpass.getuser()))


def _backend() -> str:
    return "windows-dpapi" if os.name == "nt" else "posix-0600"


def _native_path(path: Path) -> Path:
    absolute = str(Path(path).absolute())
    if os.name == "nt" and not absolute.startswith("\\\\?\\"):
        return Path("\\\\?\\" + absolute)
    return Path(absolute)


def _dpapi(data: bytes, protect: bool, entropy: bytes) -> bytes:
    if os.name != "nt":
        raise IntegrityError("BACKEND_UNAVAILABLE: Windows DPAPI is unavailable")
    class Blob(ctypes.Structure):
        _fields_ = [("cbData", wintypes.DWORD), ("pbData", ctypes.POINTER(ctypes.c_byte))]
    def blob(value: bytes):
        buf = ctypes.create_string_buffer(value)
        return Blob(len(value), ctypes.cast(buf, ctypes.POINTER(ctypes.c_byte))), buf
    source, source_buf = blob(data)
    entropy_blob, entropy_buf = blob(entropy)
    output = Blob()
    crypt32 = ctypes.windll.crypt32
    fn = crypt32.CryptProtectData if protect else crypt32.CryptUnprotectData
    description = wintypes.LPWSTR()
    if protect:
        ok = fn(ctypes.byref(source), None, ctypes.byref(entropy_blob), None, None, 0,
                ctypes.byref(output))
    else:
        ok = fn(ctypes.byref(source), ctypes.byref(description), ctypes.byref(entropy_blob),
                None, None, 0, ctypes.byref(output))
    _ = source_buf, entropy_buf
    if not ok:
        raise IntegrityError("DPAPI operation failed")
    try:
        return ctypes.string_at(output.pbData, output.cbData)
    finally:
        ctypes.windll.kernel32.LocalFree(output.pbData)


def _protect(secret: bytes, purpose: str) -> str:
    if os.name == "nt":
        protected = _dpapi(secret, True, ("cp-assistant-v6.5|" + purpose).encode("utf-8"))
    else:
        protected = secret
    return base64.b64encode(protected).decode("ascii")


def _unprotect(value: str, purpose: str, backend: str) -> bytes:
    if backend != _backend():
        raise IntegrityError("BACKEND_UNAVAILABLE: keyring backend does not match this host")
    try:
        data = base64.b64decode(value, validate=True)
    except (ValueError, TypeError) as exc:
        raise IntegrityError("key material encoding is invalid") from exc
    return _dpapi(data, False, ("cp-assistant-v6.5|" + purpose).encode("utf-8")) if os.name == "nt" else data


def _atomic_json(path: Path, value: Mapping[str, Any]) -> None:
    native = _native_path(path)
    native.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix=path.name + ".", suffix=".tmp", dir=str(native.parent))
    try:
        if os.name != "nt":
            os.fchmod(fd, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
            json.dump(value, handle, ensure_ascii=False, sort_keys=True, indent=2)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        if os.environ.get("CP_ASSISTANT_TEST_KEYRING_HARD_CRASH_POINT") == "AFTER_TEMP_FSYNC":
            os._exit(93)
        if os.environ.get("CP_ASSISTANT_TEST_KEYRING_HARD_CRASH_POINT") == "BEFORE_REPLACE":
            os._exit(93)
        replace_with_retry(name, native)
        if os.environ.get("CP_ASSISTANT_TEST_KEYRING_HARD_CRASH_POINT") == "AFTER_REPLACE":
            os._exit(93)
        if os.name != "nt":
            os.chmod(native, 0o600)
    finally:
        try:
            os.unlink(name)
        except FileNotFoundError:
            pass


def _new_key(purpose: str) -> Dict[str, Any]:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return {"key_id": "%s-%s" % (stamp, secrets.token_hex(4)), "status": "ACTIVE",
            "created_at": _now(), "protected_secret": _protect(secrets.token_bytes(32), purpose)}


def init_keyring(path: Optional[Path] = None) -> Dict[str, Any]:
    target = Path(path or default_keyring_path())
    with OwnerTokenLock(target, timeout=10.0):
        if _native_path(target).exists():
            return keyring_status(target)
        value = {"schema_version": KEYRING_SCHEMA, "backend": _backend(), "binding_id": _binding_id(),
                 "created_at": _now(), "purposes": {purpose: [_new_key(purpose)] for purpose in PURPOSES}}
        _atomic_json(target, value)
    return keyring_status(target)


def load_keyring(path: Optional[Path] = None, decrypt: bool = False) -> Dict[str, Any]:
    target = Path(path or default_keyring_path())
    native = _native_path(target)
    try:
        if native.is_symlink() or (native.exists() and bool(getattr(native.lstat(), "st_file_attributes", 0) & 0x400)):
            raise IntegrityError("keyring must not be a reparse point")
        if os.name != "nt" and native.exists() and stat.S_IMODE(native.stat().st_mode) & 0o077:
            raise IntegrityError("keyring permissions must be 0600")
        value = json.loads(native.read_text(encoding="utf-8"))
    except IntegrityError:
        raise
    except (OSError, ValueError) as exc:
        raise IntegrityError("keyring could not be read") from exc
    if not isinstance(value, dict) or value.get("schema_version") != KEYRING_SCHEMA:
        raise IntegrityError("keyring schema is invalid")
    if value.get("backend") != _backend() or value.get("binding_id") != _binding_id():
        raise IntegrityError("BACKEND_UNAVAILABLE: keyring is bound to another host/account")
    for purpose in PURPOSES:
        keys = (value.get("purposes") or {}).get(purpose)
        if not isinstance(keys, list) or sum(1 for key in keys if key.get("status") == "ACTIVE") != 1:
            raise IntegrityError("keyring must contain exactly one ACTIVE key per purpose")
        seen = set()
        for key in keys:
            key_id = str(key.get("key_id") or "")
            if not key_id or key_id in seen or key.get("status") not in {"ACTIVE", "RETIRED"}:
                raise IntegrityError("keyring key metadata is invalid")
            seen.add(key_id)
            if decrypt:
                secret = _unprotect(str(key.get("protected_secret") or ""), purpose, value["backend"])
                if len(secret) != 32:
                    raise IntegrityError("key secret length is invalid")
                key["_secret"] = secret
    return value


def keyring_status(path: Optional[Path] = None) -> Dict[str, Any]:
    value = load_keyring(path, decrypt=False)
    return {"ok": True, "schema_version": value["schema_version"], "backend": value["backend"],
            "binding_id": value["binding_id"], "purposes": {
                purpose: {"active_key_id": next(key["key_id"] for key in keys if key["status"] == "ACTIVE"),
                          "key_count": len(keys), "statuses": [key["status"] for key in keys]}
                for purpose, keys in value["purposes"].items()}}


def verify_keyring(path: Optional[Path] = None) -> Dict[str, Any]:
    load_keyring(path, decrypt=True)
    return keyring_status(path)


def rotate_key(purpose: str, path: Optional[Path] = None) -> Dict[str, Any]:
    if purpose not in PURPOSES:
        raise IntegrityError("unknown key purpose")
    target = Path(path or default_keyring_path())
    with OwnerTokenLock(target, timeout=10.0):
        value = load_keyring(target, decrypt=True)
        for keys in value["purposes"].values():
            for key in keys:
                key.pop("_secret", None)
        for key in value["purposes"][purpose]:
            if key["status"] == "ACTIVE":
                key["status"] = "RETIRED"
                key["retired_at"] = _now()
        value["purposes"][purpose].append(_new_key(purpose))
        _atomic_json(target, value)
    return keyring_status(target)


def active_secret(purpose: str, path: Optional[Path] = None) -> tuple[Dict[str, Any], bytes, str]:
    value = load_keyring(path, decrypt=True)
    key = next(item for item in value["purposes"][purpose] if item["status"] == "ACTIVE")
    return value, key["_secret"], key["key_id"]


def secret_by_id(purpose: str, key_id: str, path: Optional[Path] = None) -> tuple[Dict[str, Any], bytes]:
    value = load_keyring(path, decrypt=True)
    for key in value["purposes"][purpose]:
        if key["key_id"] == key_id:
            return value, key["_secret"]
    raise IntegrityError("unknown key id")


def default_seal_path(event_path: Path) -> Path:
    return Path(str(event_path) + ".seals.jsonl")


def _load_seals(path: Path) -> List[Dict[str, Any]]:
    if not path.exists():
        return []
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
        seals = [json.loads(line) for line in lines if line.strip()]
    except (OSError, ValueError) as exc:
        raise IntegrityError("seal chain is invalid JSONL") from exc
    if not all(isinstance(item, dict) for item in seals):
        raise IntegrityError("seal chain contains a non-object")
    return seals


def _atomic_seals(path: Path, seals: List[Mapping[str, Any]]) -> None:
    """中文：发布完整封印链，使中断后仍保留旧状态或新状态中的有效版本。

    English: Publish a complete seal chain so interruption leaves either the old or the new state valid.
    """
    native = _native_path(path)
    native.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix=path.name + ".", suffix=".tmp", dir=str(native.parent))
    try:
        if os.name != "nt":
            os.fchmod(fd, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
            for seal in seals:
                handle.write(canonical_json(seal) + "\n")
            handle.flush()
            os.fsync(handle.fileno())
        if os.environ.get("CP_ASSISTANT_TEST_SEAL_HARD_CRASH_POINT") == "AFTER_TEMP_FSYNC":
            os._exit(95)
        if os.environ.get("CP_ASSISTANT_TEST_SEAL_HARD_CRASH_POINT") == "BEFORE_REPLACE":
            os._exit(95)
        replace_with_retry(name, native)
        if os.environ.get("CP_ASSISTANT_TEST_SEAL_HARD_CRASH_POINT") == "AFTER_REPLACE":
            os._exit(95)
        if os.name != "nt":
            os.chmod(native, 0o600)
    finally:
        try:
            os.unlink(name)
        except FileNotFoundError:
            pass


def _verify_seals(seals: List[Dict[str, Any]], event_heads: List[str], event_log_id: str,
                  keyring_path: Optional[Path]) -> Dict[str, Any]:
    previous = ZERO_HASH
    max_count = 0
    key_ids: List[str] = []
    for index, seal in enumerate(seals, 1):
        if seal.get("schema_version") != SEAL_SCHEMA or seal.get("previous_seal_hash") != previous:
            raise IntegrityError("seal chain linkage is invalid at record %d" % index)
        supplied_hash = str(seal.get("seal_hash") or "")
        supplied_hmac = str(seal.get("hmac_sha256") or "")
        unsigned = {key: value for key, value in seal.items() if key not in {"seal_hash", "hmac_sha256"}}
        expected_hash = _sha(previous + "\n" + canonical_json(unsigned))
        if not hmac.compare_digest(supplied_hash, expected_hash):
            raise IntegrityError("seal hash mismatch at record %d" % index)
        if seal.get("event_log_id") != event_log_id:
            raise IntegrityError("seal event log identity mismatch")
        count = int(seal.get("event_record_count", -1))
        if count < 0 or count >= len(event_heads) or event_heads[count] != seal.get("event_chain_head"):
            raise IntegrityError("seal references an unknown event chain head")
        ring, secret = secret_by_id("event-hmac", str(seal.get("key_id") or ""), keyring_path)
        if seal.get("issuer_id") != ring["binding_id"]:
            raise IntegrityError("seal issuer does not match keyring binding")
        signed = dict(unsigned)
        signed["seal_hash"] = supplied_hash
        expected_hmac = hmac.new(secret, canonical_json(signed).encode("utf-8"), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(supplied_hmac, expected_hmac):
            raise IntegrityError("seal HMAC mismatch at record %d" % index)
        previous = supplied_hash
        max_count = max(max_count, count)
        key_ids.append(str(seal["key_id"]))
    current_count = len(event_heads) - 1
    status = "UNSEALED" if not seals else ("SEALED_CURRENT" if max_count == current_count
                                             else "VALID_SEALED_PREFIX_WITH_UNSEALED_TAIL")
    return {"ok": True, "seal_status": status, "seal_count": len(seals),
            "sealed_record_count": max_count, "event_record_count": current_count,
            "key_ids": sorted(set(key_ids)), "seal_head": previous}


def verify_event_seals(event_path: Path, seal_path: Optional[Path] = None,
                       keyring_path: Optional[Path] = None) -> Dict[str, Any]:
    event_path = Path(event_path)
    with OwnerTokenLock(event_path):
        _files, events, _tail = _read_event_files_unlocked(event_path)
        chain = _verify_events(events, None, allow_duplicate_ids=True)
        heads = [ZERO_HASH] + [str(item.get("record_hash") or "") for item in events]
        seals = _load_seals(Path(seal_path or default_seal_path(event_path)))
        return {**_verify_seals(seals, heads, _sha(event_path.name), keyring_path),
                "event_chain_head": chain["head_hash"]}


def seal_event_chain(event_path: Path, seal_path: Optional[Path] = None,
                     keyring_path: Optional[Path] = None) -> Dict[str, Any]:
    event_path = Path(event_path)
    target = Path(seal_path or default_seal_path(event_path))
    with OwnerTokenLock(event_path):
        _files, events, _tail = _read_event_files_unlocked(event_path, recover_active_tail=True)
        chain = _verify_events(events, None, allow_duplicate_ids=True)
        heads = [ZERO_HASH] + [str(item.get("record_hash") or "") for item in events]
        seals = _load_seals(target)
        state = _verify_seals(seals, heads, _sha(event_path.name), keyring_path)
        if state["seal_status"] == "SEALED_CURRENT":
            return {**state, "event_chain_head": chain["head_hash"]}
        ring, secret, key_id = active_secret("event-hmac", keyring_path)
        unsigned = {"schema_version": SEAL_SCHEMA, "seal_id": "SEAL_" + secrets.token_hex(16),
                    "created_at": _now(), "event_log_id": _sha(event_path.name),
                    "event_chain_head": chain["head_hash"], "event_record_count": chain["record_count"],
                    "event_segment_count": len(event_segment_paths(event_path)),
                    "previous_seal_hash": state["seal_head"], "issuer_id": ring["binding_id"],
                    "key_id": key_id}
        seal_hash = _sha(state["seal_head"] + "\n" + canonical_json(unsigned))
        signed = dict(unsigned, seal_hash=seal_hash)
        signed["hmac_sha256"] = hmac.new(secret, canonical_json(signed).encode("utf-8"), hashlib.sha256).hexdigest()
        seals.append(signed)
        _atomic_seals(target, seals)
        return {**_verify_seals(seals, heads, _sha(event_path.name), keyring_path),
                "event_chain_head": chain["head_hash"]}
