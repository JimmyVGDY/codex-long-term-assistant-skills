"""中文：Windows 公开载荷部署必须保留继承的只读访问。

English: Windows public payload deployment must retain inherited read-only access.
"""
from __future__ import annotations

import ctypes
import os
import subprocess
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import package_manager as manager


class PublicPayloadContentTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory(prefix="cp-public-content-")
        self.addCleanup(self.directory.cleanup)
        self.base = Path(self.directory.name)
        self.source = self.base / "source"
        self.source.mkdir()
        (self.source / "module.py").write_text("VALUE = 1\n", encoding="utf-8")
        cache = self.source / "__pycache__"
        cache.mkdir()
        (cache / "module.cpython-314.pyc").write_bytes(b"generated fixture")
        (self.source / "legacy.pyo").write_bytes(b"generated fixture")

    def test_public_install_matches_existing_plugin_payload_filter(self):
        expected, actual = self.base / "expected", self.base / "actual"
        manager._copy_plugin_payload_tree(self.source, expected)
        manager.copy_atomic(self.source, actual, readable_payload=True)
        self.assertEqual(manager.tree_sha256(actual), manager.tree_sha256(expected))
        self.assertFalse((actual / "__pycache__").exists())
        self.assertFalse((actual / "legacy.pyo").exists())

    def test_default_state_copy_preserves_opaque_files(self):
        actual = self.base / "restored-state"
        manager.copy_atomic(self.source, actual)
        self.assertEqual(manager.tree_sha256(actual), manager.tree_sha256(self.source))


@unittest.skipUnless(os.name == "nt", "Requires real Windows DACL inheritance")
class WindowsPayloadPermissionTests(unittest.TestCase):
    READER_SID = "S-1-1-0"
    WRITE_RIGHTS = 0x2 | 0x4 | 0x10 | 0x100 | 0x10000 | 0x40000 | 0x80000

    def setUp(self):
        self.directory = tempfile.TemporaryDirectory(prefix="cp-payload-acl-")
        self.addCleanup(self.directory.cleanup)
        self.base = Path(self.directory.name)
        self.source = self.base / "source"
        self.source.mkdir()
        (self.source / "module.py").write_text("VALUE = 1\n", encoding="utf-8")
        self.destination = self.base / "installed"
        self.destination.mkdir()
        # 中文：仅一次性夹具增加额外读取者，不修改账户 ACL。
        # English: Only a disposable fixture gains an extra reader; no account ACL changes.
        subprocess.run(
            ["icacls.exe", str(self.destination), "/grant", "*S-1-1-0:(OI)(CI)(RX)"],
            check=True, capture_output=True, timeout=15,
        )

    def reader_rules(self, path: Path):
        class AclHeader(ctypes.Structure):
            _fields_ = [("revision", ctypes.c_ubyte), ("reserved", ctypes.c_ubyte),
                        ("size", ctypes.c_ushort), ("count", ctypes.c_ushort),
                        ("reserved2", ctypes.c_ushort)]

        security = ctypes.WinDLL("advapi32", use_last_error=True)
        kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        pointer = ctypes.POINTER(ctypes.c_void_p)
        security.GetNamedSecurityInfoW.argtypes = [ctypes.c_wchar_p, ctypes.c_int,
            ctypes.c_uint32, pointer, pointer, pointer, pointer, pointer]
        security.GetNamedSecurityInfoW.restype = ctypes.c_uint32
        security.GetAce.argtypes = [ctypes.c_void_p, ctypes.c_uint32, pointer]
        security.GetAce.restype = ctypes.c_int
        security.ConvertSidToStringSidW.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_wchar_p)]
        security.ConvertSidToStringSidW.restype = ctypes.c_int
        kernel.LocalFree.argtypes = [ctypes.c_void_p]
        kernel.LocalFree.restype = ctypes.c_void_p
        acl, descriptor = ctypes.c_void_p(), ctypes.c_void_p()
        error = security.GetNamedSecurityInfoW(str(path), 1, 4, None, None,
                                              ctypes.byref(acl), None, ctypes.byref(descriptor))
        if error:
            raise ctypes.WinError(error)
        try:
            self.assertTrue(acl.value, "A null DACL is not a read-only grant")
            rules = []
            for index in range(ctypes.cast(acl, ctypes.POINTER(AclHeader)).contents.count):
                ace = ctypes.c_void_p()
                if not security.GetAce(acl, index, ctypes.byref(ace)):
                    raise ctypes.WinError(ctypes.get_last_error())
                # 中文：零表示 ACCESS_ALLOWED_ACE_TYPE。
                # English: Zero denotes ACCESS_ALLOWED_ACE_TYPE.
                if ctypes.c_ubyte.from_address(ace.value).value != 0:
                    continue
                sid = ctypes.c_wchar_p()
                if not security.ConvertSidToStringSidW(ace.value + 8, ctypes.byref(sid)):
                    raise ctypes.WinError(ctypes.get_last_error())
                try:
                    if sid.value == self.READER_SID:
                        rules.append({"rights": ctypes.c_uint32.from_address(ace.value + 4).value})
                finally:
                    kernel.LocalFree(ctypes.cast(sid, ctypes.c_void_p))
            return rules
        finally:
            kernel.LocalFree(descriptor)

    def assert_reader_without_writer(self, path: Path):
        rules = self.reader_rules(path)
        self.assertTrue(rules, "Destination lost its parent's read-only principal")
        rights = 0
        for rule in rules:
            rights |= rule["rights"]
        self.assertEqual(rights & 0x1200A9, 0x1200A9)
        self.assertEqual(rights & self.WRITE_RIGHTS, 0)

    def test_public_file_preserves_parent_reader_without_granting_write(self):
        target = self.destination / "hook.py"
        manager.copy_atomic(self.source / "module.py", target, readable_payload=True)
        self.assertEqual(target.read_text(encoding="utf-8"), "VALUE = 1\n")
        self.assert_reader_without_writer(target)
        self.assertEqual(list(self.destination.glob(".cp-*")), [])

    def test_public_directory_and_children_preserve_parent_reader(self):
        nested = self.source / "nested"
        nested.mkdir()
        (nested / "data.json").write_text("{}\n", encoding="utf-8")
        target = self.destination / "runtime"
        manager.copy_atomic(self.source, target, readable_payload=True)
        for path in (target, target / "module.py", target / "nested", target / "nested/data.json"):
            with self.subTest(path=path.relative_to(self.destination)):
                self.assert_reader_without_writer(path)

    def test_default_copy_does_not_opt_private_state_into_public_permissions(self):
        private_probe = Path(tempfile.mkdtemp(prefix="private-", dir=self.destination))
        if self.reader_rules(private_probe):
            self.skipTest("This Python does not apply a private Windows mkdtemp DACL")
        target = self.destination / "state.json"
        manager.copy_atomic(self.source / "module.py", target)
        self.assertEqual(self.reader_rules(target), [])

    def test_staging_collision_never_reuses_or_deletes_existing_directory(self):
        collision = self.destination / ".cp-deadbeef"
        collision.mkdir()
        marker = collision / "unrelated.txt"
        marker.write_text("preserve", encoding="utf-8")
        with patch.object(manager.uuid, "uuid4", return_value=types.SimpleNamespace(hex="deadbeef" * 4)):
            with self.assertRaises(manager.InstallError):
                manager.copy_atomic(self.source, self.destination / "runtime", readable_payload=True)
        self.assertEqual(marker.read_text(encoding="utf-8"), "preserve")
        self.assertFalse((self.destination / "runtime").exists())

    def test_failed_public_copy_preserves_existing_target_and_cleans_stage(self):
        target = self.destination / "runtime"
        target.mkdir()
        marker = target / "old.txt"
        marker.write_text("old", encoding="utf-8")
        with patch.object(manager.shutil, "copytree", side_effect=OSError("fixture copy failure")):
            with self.assertRaises(OSError):
                manager.copy_atomic(self.source, target, readable_payload=True)
        self.assertEqual(marker.read_text(encoding="utf-8"), "old")
        self.assertEqual(list(self.destination.glob(".cp-*")), [])


if __name__ == "__main__":
    unittest.main()
