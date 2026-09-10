"""中文：首次项目询问和有界扫描任务的独立原子状态；不保存用户正文或外部权限。

English: Independent atomic first-use offer and bounded scan-job state; no user text or external authority.
"""
from __future__ import annotations

import copy
import hashlib
import json
import secrets
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable, Mapping

from .atomic_io import native_path
from .capability_gate import _write, worktree_key
from .capability_store import CapabilityError, CapabilityStore, bounded_read, fields, integer, require, safe_path, unique_json_object
from .common import RuntimeContractError, canonical_json, require_external_state, validate_identifier, verify_record
from .event_v3 import OwnerTokenLock

OFFER_SCHEMA = "onboarding/1"
SCAN_SCHEMA = "onboarding-scan/1"
STATE_LIMIT = 256 * 1024
CHOICES = {"ACCEPTED", "DECLINED"}
SOURCES = {"MODEL_INTERPRETED_USER_REPLY", "HOST_STRUCTURED_REPLY"}
SCAN_TERMINAL = {"COMPLETED", "PARTIAL", "CANCELLED", "FAILED"}


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(value: datetime) -> str:
    require(value.tzinfo is not None, "ONBOARDING_CLOCK")
    return value.astimezone(timezone.utc).isoformat(timespec="milliseconds")


def _time(value: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value)
    except (TypeError, ValueError):
        raise CapabilityError("ONBOARDING_CLOCK") from None
    require(parsed.tzinfo is not None, "ONBOARDING_CLOCK")
    return parsed.astimezone(timezone.utc)


def _text(value: Any, code: str, limit: int = 256) -> str:
    require(isinstance(value, str) and 0 < len(value.encode("utf-8")) <= limit, code)
    return value


def scope_digest(scopes: list[str]) -> str:
    require(isinstance(scopes, list) and 0 < len(scopes) <= 128, "ONBOARDING_SCOPE")
    normalized = []
    for value in scopes:
        _text(value, "ONBOARDING_SCOPE", 1024)
        require(value == "." or (not value.startswith(("/", "\\")) and "\\" not in value and ":" not in value
                                 and all(part not in {"", ".", ".."} for part in value.split("/"))), "ONBOARDING_SCOPE")
        if value not in normalized:
            normalized.append(value)
    return hashlib.sha256(canonical_json(normalized).encode("utf-8")).hexdigest()


def _lease_hash(token: str) -> str:
    return hashlib.sha256(token.encode("ascii")).hexdigest()


class OnboardingStore:
    def __init__(self, profile_path: Path, repo_path: Path, *, clock: Callable[[], datetime] = utc_now):
        self.store = CapabilityStore(profile_path, repo_path)
        self.clock = clock
        self.root = safe_path(profile_path.parent / "onboarding" / worktree_key(repo_path))
        require_external_state(self.root, repo_path)
        self.offer_path = self.root / "offer.json"
        self.scan_path = self.root / "scan.json"

    def _now(self, previous: str | None = None) -> datetime:
        now = self.clock().astimezone(timezone.utc)
        if previous is not None:
            require(now >= _time(previous), "CLOCK_ROLLBACK")
        return now

    def _read(self, path: Path, kind: str) -> dict[str, Any] | None:
        self.store._guard()
        if not native_path(path).exists():
            return None
        try:
            value = json.loads(bounded_read(native_path(path), STATE_LIMIT), object_pairs_hook=unique_json_object)
            fields(value.get("integrity"), {"algorithm", "sha256"})
            verify_record(value, kind)
            self._validate_offer(value) if kind == "OnboardingOffer" else self._validate_scan(value)
        except (ValueError, UnicodeError, RecursionError, RuntimeContractError, OSError):
            raise CapabilityError("ONBOARDING_RECORD_INVALID") from None
        self.store._guard()
        return value

    def _validate_offer(self, value: dict[str, Any]) -> None:
        fields(value, {"schema_version", "revision", "identity", "contract_version", "offer_ref", "nonce",
                       "scope", "scope_digest", "owner", "created_at", "expires_at", "last_observed_at",
                       "state", "choice", "response", "persistence_status", "integrity"})
        require(value["schema_version"] == OFFER_SCHEMA and value["contract_version"] == OFFER_SCHEMA, "ONBOARDING_SCHEMA")
        require(value["identity"] == self.store.identity, "ONBOARDING_IDENTITY")
        integer(value["revision"], 2**63 - 1)
        require(value["scope_digest"] == scope_digest(value["scope"]), "ONBOARDING_SCOPE")
        validate_identifier(value["owner"], "owner")
        validate_identifier(value["offer_ref"], "offer reference")
        validate_identifier(value["nonce"], "nonce")
        created, expires, observed = _time(value["created_at"]), _time(value["expires_at"]), _time(value["last_observed_at"])
        require(created <= observed and created < expires, "ONBOARDING_CLOCK")
        require(value["state"] in {"OFFERED", *CHOICES}, "ONBOARDING_STATE")
        require((value["state"] == "OFFERED" and value["choice"] is None and value["response"] is None)
                or (value["state"] in CHOICES and value["choice"] == value["state"] and isinstance(value["response"], dict)),
                "ONBOARDING_STATE")
        require(value["persistence_status"] in {"OFFER_PERSISTED", "ACCEPTED_PERSISTED", "DECLINED_PERSISTED"}, "ONBOARDING_PERSISTENCE")
        if value["response"] is not None:
            fields(value["response"], {"source", "reference", "idempotency_key", "responded_at"})
            require(value["response"]["source"] in SOURCES, "ONBOARDING_SOURCE")
            validate_identifier(value["response"]["reference"], "response reference")

    def _validate_scan(self, value: dict[str, Any]) -> None:
        fields(value, {"schema_version", "revision", "identity", "offer_ref", "offer_revision", "scope_digest",
                       "state", "cursor", "coverage", "cancel_epoch", "attempts", "lease", "reason",
                       "last_observed_at", "integrity"})
        require(value["schema_version"] == SCAN_SCHEMA and value["identity"] == self.store.identity, "ONBOARDING_SCAN_SCHEMA")
        integer(value["revision"], 2**63 - 1); integer(value["offer_revision"], 2**63 - 1)
        integer(value["cancel_epoch"], 2**63 - 1); integer(value["attempts"], 3)
        require(value["state"] in {"QUEUED", "RUNNING", *SCAN_TERMINAL}, "ONBOARDING_SCAN_STATE")
        require(value["cursor"] is None or isinstance(value["cursor"], str), "ONBOARDING_SCAN_CURSOR")
        require(isinstance(value["coverage"], dict), "ONBOARDING_SCAN_COVERAGE")
        require((value["state"] == "RUNNING") == isinstance(value["lease"], dict), "ONBOARDING_SCAN_LEASE")
        if value["lease"] is not None:
            fields(value["lease"], {"token_sha256", "generation", "owner", "expires_at"})
            require(len(value["lease"]["token_sha256"]) == 64, "ONBOARDING_SCAN_LEASE")
            integer(value["lease"]["generation"], 2**63 - 1)
            _text(value["lease"]["owner"], "ONBOARDING_OWNER", 160)
            _time(value["lease"]["expires_at"])

    def offer_status(self) -> dict[str, Any]:
        current = self._read(self.offer_path, "OnboardingOffer")
        return current if current is not None else {"schema_version": OFFER_SCHEMA, "state": "UNSEEN", "persisted": False}

    def create_offer(self, scopes: list[str], owner: str, ttl_seconds: int = 86400) -> dict[str, Any]:
        digest = scope_digest(scopes)
        owner = validate_identifier(owner, "owner")
        require(type(ttl_seconds) is int and 60 <= ttl_seconds <= 604800, "ONBOARDING_TTL")
        with OwnerTokenLock(self.offer_path):
            current = self._read(self.offer_path, "OnboardingOffer")
            if current is not None:
                require(current["scope_digest"] == digest and current["owner"] == owner, "ONBOARDING_OWNER_CONFLICT")
                return current
            now = self._now()
            value = {"schema_version": OFFER_SCHEMA, "revision": 0, "identity": copy.deepcopy(self.store.identity),
                     "contract_version": OFFER_SCHEMA, "offer_ref": "ONB_" + secrets.token_hex(16),
                     "nonce": secrets.token_hex(24), "scope": list(dict.fromkeys(scopes)), "scope_digest": digest,
                     "owner": owner, "created_at": _iso(now), "expires_at": _iso(now + timedelta(seconds=ttl_seconds)),
                     "last_observed_at": _iso(now), "state": "OFFERED", "choice": None, "response": None,
                     "persistence_status": "OFFER_PERSISTED"}
            result = _write(self.offer_path, value, STATE_LIMIT)
            self._validate_offer(result)
            return result

    def renew_offer(self, expected_revision: int, nonce: str, ttl_seconds: int = 86400) -> dict[str, Any]:
        require(type(ttl_seconds) is int and 60 <= ttl_seconds <= 604800, "ONBOARDING_TTL")
        with OwnerTokenLock(self.offer_path):
            current = self._read(self.offer_path, "OnboardingOffer")
            require(current is not None and current["state"] == "OFFERED", "ONBOARDING_RENEW_UNAVAILABLE")
            require(current["revision"] == expected_revision and current["nonce"] == nonce, "ONBOARDING_REVISION_CONFLICT")
            now = self._now(current["last_observed_at"])
            require(now >= _time(current["expires_at"]), "ONBOARDING_NOT_EXPIRED")
            value = {**{key: copy.deepcopy(current[key]) for key in current if key != "integrity"},
                     "revision": current["revision"] + 1, "offer_ref": "ONB_" + secrets.token_hex(16),
                     "nonce": secrets.token_hex(24), "created_at": _iso(now),
                     "expires_at": _iso(now + timedelta(seconds=ttl_seconds)), "last_observed_at": _iso(now)}
            result = _write(self.offer_path, value, STATE_LIMIT)
            self._validate_offer(result)
            return result

    def respond(self, choice: str, nonce: str, expected_revision: int, source: str, response_ref: str) -> dict[str, Any]:
        require(choice in CHOICES and source in SOURCES, "ONBOARDING_RESPONSE")
        response_ref = validate_identifier(response_ref, "response reference")
        with OwnerTokenLock(self.offer_path):
            current = self._read(self.offer_path, "OnboardingOffer")
            require(current is not None and current["nonce"] == nonce, "ONBOARDING_NONCE_MISMATCH")
            now = self._now(current["last_observed_at"])
            if current["state"] == choice:
                return current
            require(current["revision"] == expected_revision, "ONBOARDING_REVISION_CONFLICT")
            if current["state"] == "OFFERED":
                require(now < _time(current["expires_at"]), "ONBOARDING_EXPIRED")
            idempotency = hashlib.sha256(canonical_json([current["offer_ref"], nonce, choice]).encode("utf-8")).hexdigest()
            value = {**{key: copy.deepcopy(current[key]) for key in current if key != "integrity"},
                     "revision": current["revision"] + 1, "last_observed_at": _iso(now), "state": choice,
                     "choice": choice, "response": {"source": source, "reference": response_ref,
                     "idempotency_key": idempotency, "responded_at": _iso(now)},
                     "persistence_status": choice + "_PERSISTED"}
            result = _write(self.offer_path, value, STATE_LIMIT)
            self._validate_offer(result)
            if choice == "DECLINED":
                self._cancel_scan_locked("USER_DECLINED")
            return result

    def queue_scan(self) -> dict[str, Any]:
        with OwnerTokenLock(self.offer_path):
            offer = self._read(self.offer_path, "OnboardingOffer")
            require(offer is not None and offer["state"] == "ACCEPTED"
                    and offer["persistence_status"] == "ACCEPTED_PERSISTED", "ONBOARDING_NOT_ACCEPTED")
            with OwnerTokenLock(self.scan_path):
                current = self._read(self.scan_path, "OnboardingScan")
                if current is not None and current["offer_ref"] == offer["offer_ref"] \
                        and current["offer_revision"] == offer["revision"]:
                    return current
                require(current is None or current["state"] in SCAN_TERMINAL, "ONBOARDING_SCAN_ACTIVE")
                now = self._now(current["last_observed_at"] if current else None)
                value = {"schema_version": SCAN_SCHEMA, "revision": current["revision"] + 1 if current else 0,
                         "identity": copy.deepcopy(self.store.identity), "offer_ref": offer["offer_ref"],
                         "offer_revision": offer["revision"], "scope_digest": offer["scope_digest"],
                         "state": "QUEUED", "cursor": None, "coverage": {},
                         "cancel_epoch": current["cancel_epoch"] if current else 0, "attempts": 0,
                         "lease": None, "reason": "", "last_observed_at": _iso(now)}
                result = _write(self.scan_path, value, STATE_LIMIT)
                self._validate_scan(result)
                return result

    def scan_status(self) -> dict[str, Any] | None:
        return self._read(self.scan_path, "OnboardingScan")

    def claim_scan(self, owner: str, lease_seconds: int = 120) -> dict[str, Any]:
        owner = validate_identifier(owner, "owner")
        require(type(lease_seconds) is int and 5 <= lease_seconds <= 300, "ONBOARDING_SCAN_LEASE")
        with OwnerTokenLock(self.scan_path):
            current = self._read(self.scan_path, "OnboardingScan")
            require(current is not None, "ONBOARDING_SCAN_MISSING")
            now = self._now(current["last_observed_at"])
            takeover = current["state"] == "RUNNING" and now >= _time(current["lease"]["expires_at"])
            require(current["state"] == "QUEUED" or takeover, "ONBOARDING_SCAN_NOT_CLAIMABLE")
            require(current["attempts"] < 3, "ONBOARDING_SCAN_ATTEMPTS")
            token = secrets.token_hex(24)
            generation = (current["lease"]["generation"] + 1) if takeover else (current["attempts"] + 1)
            value = {**{key: copy.deepcopy(current[key]) for key in current if key != "integrity"},
                     "revision": current["revision"] + 1, "state": "RUNNING", "attempts": current["attempts"] + 1,
                     "lease": {"token_sha256": _lease_hash(token), "generation": generation, "owner": owner,
                               "expires_at": _iso(now + timedelta(seconds=lease_seconds))},
                     "last_observed_at": _iso(now), "reason": ""}
            result = _write(self.scan_path, value, STATE_LIMIT)
            self._validate_scan(result)
            return {"scan": result, "lease_token": token}

    def checkpoint(self, lease_token: str, generation: int, cancel_epoch: int, cursor: str,
                   coverage: Mapping[str, Any], commit: Callable[[], Any] | None = None,
                   lease_seconds: int = 120) -> dict[str, Any]:
        cursor = validate_identifier(cursor, "scan cursor")
        require(isinstance(coverage, Mapping), "ONBOARDING_SCAN_COVERAGE")
        with OwnerTokenLock(self.scan_path):
            current = self._read(self.scan_path, "OnboardingScan")
            require(current is not None and current["state"] == "RUNNING", "ONBOARDING_SCAN_NOT_RUNNING")
            now = self._now(current["last_observed_at"])
            lease = current["lease"]
            require(lease["token_sha256"] == _lease_hash(lease_token) and lease["generation"] == generation,
                    "LEASE_FENCED")
            require(current["cancel_epoch"] == cancel_epoch, "SCAN_CANCELLED")
            require(now < _time(lease["expires_at"]), "LEASE_EXPIRED")
            projection = commit() if commit is not None else None
            value = {**{key: copy.deepcopy(current[key]) for key in current if key != "integrity"},
                     "revision": current["revision"] + 1, "cursor": cursor, "coverage": dict(coverage),
                     "lease": {**lease, "expires_at": _iso(now + timedelta(seconds=lease_seconds))},
                     "last_observed_at": _iso(now)}
            result = _write(self.scan_path, value, STATE_LIMIT)
            self._validate_scan(result)
            return {"scan": result, "projection": projection}

    def finish_scan(self, lease_token: str, generation: int, cancel_epoch: int, state: str,
                    coverage: Mapping[str, Any], reason: str = "") -> dict[str, Any]:
        require(state in {"COMPLETED", "PARTIAL", "FAILED"}, "ONBOARDING_SCAN_TERMINAL")
        require(isinstance(coverage, Mapping), "ONBOARDING_SCAN_COVERAGE")
        reason = validate_identifier(reason, "scan reason") if reason else ""
        if state == "COMPLETED":
            require(coverage.get("complete") is True, "ONBOARDING_SCAN_INCOMPLETE")
        with OwnerTokenLock(self.scan_path):
            current = self._read(self.scan_path, "OnboardingScan")
            require(current is not None, "ONBOARDING_SCAN_MISSING")
            if current["state"] == state and current["coverage"] == dict(coverage):
                return current
            require(current["state"] == "RUNNING", "ONBOARDING_SCAN_NOT_RUNNING")
            lease = current["lease"]
            require(lease["token_sha256"] == _lease_hash(lease_token) and lease["generation"] == generation,
                    "LEASE_FENCED")
            require(current["cancel_epoch"] == cancel_epoch, "SCAN_CANCELLED")
            now = self._now(current["last_observed_at"])
            require(now < _time(lease["expires_at"]), "LEASE_EXPIRED")
            value = {**{key: copy.deepcopy(current[key]) for key in current if key != "integrity"},
                     "revision": current["revision"] + 1, "state": state, "coverage": dict(coverage),
                     "lease": None, "reason": reason, "last_observed_at": _iso(now)}
            result = _write(self.scan_path, value, STATE_LIMIT)
            self._validate_scan(result)
            return result

    def _cancel_scan_locked(self, reason: str) -> dict[str, Any] | None:
        reason = validate_identifier(reason, "scan reason")
        with OwnerTokenLock(self.scan_path):
            current = self._read(self.scan_path, "OnboardingScan")
            if current is None or current["state"] not in {"QUEUED", "RUNNING"}:
                return current
            now = self._now(current["last_observed_at"])
            value = {**{key: copy.deepcopy(current[key]) for key in current if key != "integrity"},
                     "revision": current["revision"] + 1, "state": "CANCELLED",
                     "cancel_epoch": current["cancel_epoch"] + 1, "lease": None,
                     "reason": reason, "last_observed_at": _iso(now)}
            result = _write(self.scan_path, value, STATE_LIMIT)
            self._validate_scan(result)
            return result

    def cancel_scan(self, reason: str = "USER_CANCELLED") -> dict[str, Any] | None:
        return self._cancel_scan_locked(reason)
