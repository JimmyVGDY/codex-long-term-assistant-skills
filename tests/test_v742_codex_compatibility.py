#!/usr/bin/env python3
"""中文：V7.4.4 稳定版兼容注册表契约测试。

English: V7.4.4 stable-release compatibility registry contract tests.
"""
from __future__ import annotations

import ast
import base64
import copy
import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from codex_compatibility import (  # noqa: E402
    CompatibilityError,
    canonical_digest,
    load_registry,
    normalize_plugin_list,
    parse_codex_version_output,
    profile_for_version,
    verify_artifact_file,
    validate_registry,
)


REGISTRY_PATH = ROOT / "config" / "codex-compatibility-v1.json"
EXPECTED_VERSIONS = [
    "0.153.2", "0.153.1", "0.153.0", "0.152.1", "0.152.0", "0.151.0",
    "0.150.1", "0.150.0", "0.149.1", "0.149.0", "0.148.0",
]


class RegistryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.registry = load_registry(REGISTRY_PATH, "7.4.4")

    def test_registry_is_exact_frozen_stable_window(self) -> None:
        self.assertEqual(EXPECTED_VERSIONS, [item["version"] for item in self.registry["versions"]])
        self.assertEqual("0.153.2", self.registry["window_policy"]["anchor"])
        self.assertEqual(10, self.registry["window_policy"]["preceding_stable_releases"])
        self.assertEqual(64, len(canonical_digest(self.registry)))

    def test_every_version_resolves_declared_profiles(self) -> None:
        for version in EXPECTED_VERSIONS:
            with self.subTest(version=version):
                profile = profile_for_version(self.registry, version)
                self.assertEqual(version, profile["version"])
                self.assertEqual(canonical_digest(self.registry), profile["registry_digest"])

    def test_unknown_and_prerelease_versions_fail_closed(self) -> None:
        with self.assertRaises(CompatibilityError):
            profile_for_version(self.registry, "0.145.0")
        for exited in ("0.147.0", "0.146.1"):
            with self.subTest(exited=exited):
                with self.assertRaises(CompatibilityError):
                    profile_for_version(self.registry, exited)
        for output in (
            "codex-cli 0.153.2\n", " codex-cli 0.153.2", "codex-cli 0.153.2-beta.1",
            "codex 0.153.2", "codex-cli v0.153.2", "codex-cli 0.153",
        ):
            with self.subTest(output=output):
                with self.assertRaises(CompatibilityError):
                    parse_codex_version_output(output)
        self.assertEqual("0.153.2", parse_codex_version_output("codex-cli 0.153.2"))

    def test_unknown_top_level_and_duplicate_version_fail_closed(self) -> None:
        invalid = copy.deepcopy(self.registry)
        invalid["future_default"] = {}
        with self.assertRaises(CompatibilityError):
            validate_registry(invalid)
        invalid = copy.deepcopy(self.registry)
        invalid["versions"][-1]["version"] = invalid["versions"][-2]["version"]
        with self.assertRaises(CompatibilityError):
            validate_registry(invalid)

    def test_unknown_and_unused_profile_fail_closed(self) -> None:
        invalid = copy.deepcopy(self.registry)
        invalid["versions"][0]["hook_profile"] = "future-hook"
        with self.assertRaises(CompatibilityError):
            validate_registry(invalid)

    def test_profile_values_and_types_fail_closed(self) -> None:
        mutations = [
            ("marketplace", "local-interface-v2", "emit_owner", 0),
            ("plugin_cli", "remote-capable-v2", "required_commands", ["plugin_add"]),
            ("plugin_json", "plugin-list-v1", "top_level_fields", ["installed"]),
            ("hook", "hook-json-v1", "deny_wire_fields", ["permissionDecision"]),
        ]
        for group, name, field, value in mutations:
            with self.subTest(group=group, field=field):
                invalid = copy.deepcopy(self.registry)
                invalid["profiles"][group][name][field] = value
                with self.assertRaises(CompatibilityError):
                    validate_registry(invalid)
        invalid = copy.deepcopy(self.registry)
        invalid["profiles"]["hook"]["unused"] = copy.deepcopy(
            invalid["profiles"]["hook"]["hook-json-v1"],
        )
        with self.assertRaises(CompatibilityError):
            validate_registry(invalid)

    def test_artifact_and_evidence_are_closed(self) -> None:
        invalid = copy.deepcopy(self.registry)
        invalid["versions"][0]["artifact"]["tarball"] = "https://example.invalid/codex.tgz"
        with self.assertRaises(CompatibilityError):
            validate_registry(invalid)

    def test_artifact_verifier_binds_sha256_and_npm_sri(self) -> None:
        payload = b"deterministic codex tarball fixture"
        registry = copy.deepcopy(self.registry)
        artifact = registry["versions"][0]["artifact"]
        artifact["tarball_sha256"] = hashlib.sha256(payload).hexdigest()
        artifact["npm_integrity"] = "sha512-" + base64.b64encode(
            hashlib.sha512(payload).digest(),
        ).decode("ascii")
        with tempfile.TemporaryDirectory(prefix="cp-v742-artifact-") as temporary:
            path = Path(temporary) / "codex.tgz"
            path.write_bytes(payload)
            report = verify_artifact_file(registry, "0.153.2", path)
            self.assertEqual(artifact["tarball_sha256"], report["tarball_sha256"])
            path.write_bytes(payload + b"tampered")
            with self.assertRaises(CompatibilityError):
                verify_artifact_file(registry, "0.153.2", path)

    def test_hook_alias_registry_matches_runtime_adapter(self) -> None:
        tree = ast.parse((ROOT / "hooks" / "cp_hook.py").read_text(encoding="utf-8"))
        assignment = next(
            node for node in tree.body
            if isinstance(node, ast.Assign)
            and any(isinstance(target, ast.Name) and target.id == "HOOK_ALIASES" for target in node.targets)
        )
        runtime_aliases = ast.literal_eval(assignment.value)
        registry_aliases = self.registry["profiles"]["hook"]["hook-json-v1"]["aliases"]
        self.assertEqual(
            {key: tuple(value) for key, value in registry_aliases.items()}, runtime_aliases,
        )
        invalid = copy.deepcopy(self.registry)
        invalid["versions"][0]["probe_evidence"]["real_host"] = "PASS"
        with self.assertRaises(CompatibilityError):
            validate_registry(invalid)


class PluginListNormalizerTests(unittest.TestCase):
    PACKAGE = "codex-cross-project-engineering-assistant"
    MARKETPLACE = "cp-assistant-local"
    VERSION = "7.4.4"

    def setUp(self) -> None:
        registry = load_registry(REGISTRY_PATH)
        self.profile = registry["profiles"]["plugin_json"]["plugin-list-v1"]
        self.target = {
            "pluginId": f"{self.PACKAGE}@{self.MARKETPLACE}",
            "name": self.PACKAGE,
            "marketplaceName": self.MARKETPLACE,
            "version": self.VERSION,
            "installed": True,
            "enabled": True,
            "source": {"source": "local"},
            "marketplaceSource": "local",
            "installPolicy": "AVAILABLE",
            "authPolicy": "ON_INSTALL",
        }

    def normalize(self, payload: object):
        return normalize_plugin_list(
            payload, self.PACKAGE, self.MARKETPLACE, self.VERSION, self.profile,
        )

    def test_empty_and_exact_target_normalize(self) -> None:
        self.assertIsNone(self.normalize({"installed": [], "available": []}))
        normalized = self.normalize({"installed": [self.target], "available": []})
        self.assertEqual(
            {
                "plugin_id": f"{self.PACKAGE}@{self.MARKETPLACE}",
                "name": self.PACKAGE,
                "marketplace_name": self.MARKETPLACE,
                "version": self.VERSION,
                "installed": True,
                "enabled": True,
                "install_policy": "AVAILABLE",
                "auth_policy": "ON_INSTALL",
            },
            normalized,
        )

    def test_unknown_top_level_wrong_types_and_unknown_target_fields_fail(self) -> None:
        bad_payloads = [
            {"installed": [], "available": [], "future": []},
            {"installed": {}, "available": []},
            {"installed": [{**self.target, "future": True}], "available": []},
            {"installed": [{**self.target, "installed": 1}], "available": []},
            {"installed": [{**self.target, "enabled": False}], "available": []},
        ]
        for payload in bad_payloads:
            with self.subTest(payload=json.dumps(payload, sort_keys=True)):
                with self.assertRaises(CompatibilityError):
                    self.normalize(payload)

    def test_identity_conflicts_duplicates_and_policy_drift_fail(self) -> None:
        bad_targets = [
            {**self.target, "name": "other"},
            {**self.target, "pluginId": "other@cp-assistant-local"},
            {**self.target, "marketplaceName": "other"},
            {**self.target, "version": "7.4.0"},
            {**self.target, "installPolicy": "UNKNOWN"},
            {**self.target, "authPolicy": "UNKNOWN"},
        ]
        for target in bad_targets:
            with self.subTest(target=json.dumps(target, sort_keys=True)):
                with self.assertRaises(CompatibilityError):
                    self.normalize({"installed": [target], "available": []})
        with self.assertRaises(CompatibilityError):
            self.normalize({"installed": [self.target], "available": [self.target]})


if __name__ == "__main__":
    unittest.main()
