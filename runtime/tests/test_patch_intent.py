import os
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from cp_runtime.capability_store import CapabilityError
from cp_runtime import patch_intent as patch_intent_module
from cp_runtime.patch_intent import PatchIntentError, parse_apply_patch, revalidate_intent


class PatchIntentTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        (self.root / "old.txt").write_text("old\n", encoding="utf-8")
        (self.root / "delete.txt").write_text("delete\n", encoding="utf-8")

    def tearDown(self):
        self.tmp.cleanup()

    def parse(self, body):
        return parse_apply_patch("*** Begin Patch\n" + body + "\n*** End Patch\n", self.root)

    def assertCode(self, code, command):
        with self.assertRaises(PatchIntentError) as caught:
            parse_apply_patch(command, self.root)
        self.assertEqual(code, caught.exception.code)

    def test_add_delete_update_and_multiple_targets(self):
        intent = self.parse("*** Add File: new.txt\n+hello\n*** Delete File: delete.txt\n*** Update File: old.txt\n@@\n-old\n+new")
        self.assertEqual("apply_patch", intent["tool_name"])
        self.assertEqual({"Add", "Delete", "Update"}, {item["action"] for item in intent["targets"]})
        self.assertEqual(3, len(intent["target_paths"]))
        self.assertTrue(all("hello" not in str(item) for item in intent["targets"]))

    def test_move_counts_source_and_destination_and_revalidates(self):
        intent = self.parse("*** Update File: old.txt\n*** Move to: moved.txt")
        target = intent["targets"][0]
        self.assertEqual("Move", target["action"])
        self.assertEqual({"old.txt", "moved.txt"}, set(intent["target_paths"]))
        self.assertTrue(revalidate_intent(intent, self.root))
        (self.root / "old.txt").write_text("changed\n", encoding="utf-8")
        with self.assertRaises(PatchIntentError) as caught:
            revalidate_intent(intent, self.root)
        self.assertEqual("INTENT_STALE_FILE", caught.exception.code)

    def test_move_can_include_update_hunks_and_destination_must_be_absent(self):
        intent = self.parse("*** Update File: old.txt\n*** Move to: moved.txt\n@@\n-old\n+new")
        self.assertEqual("Move", intent["targets"][0]["action"])
        (self.root / "moved.txt").write_text("already here\n", encoding="utf-8")
        with self.assertRaises(PatchIntentError) as caught:
            self.parse("*** Update File: old.txt\n*** Move to: moved.txt")
        self.assertEqual("TARGET_EXISTS", caught.exception.code)

    def test_operation_prestate_semantics(self):
        self.assertCode("TARGET_EXISTS", "*** Begin Patch\n*** Add File: old.txt\n+x\n*** End Patch")
        self.assertCode("TARGET_MISSING", "*** Begin Patch\n*** Delete File: missing.txt\n*** End Patch")
        self.assertCode("TARGET_MISSING", "*** Begin Patch\n*** Update File: missing.txt\n@@\n-x\n+y\n*** End Patch")

    def test_duplicate_path_uses_platform_case_semantics(self):
        command = "*** Begin Patch\n*** Add File: Case.txt\n+x\n*** Add File: case.txt\n+y\n*** End Patch"
        if os.name == "nt":
            self.assertCode("DUPLICATE_TARGET", command)
        else:
            intent = parse_apply_patch(command, self.root)
            self.assertEqual(2, len(intent["targets"]))

    def test_existing_file_digest_is_bounded(self):
        huge = self.root / "huge.bin"
        with huge.open("wb") as stream:
            stream.seek(8 * 1024 * 1024)
            stream.write(b"x")
        with self.assertRaises(PatchIntentError) as caught:
            self.parse("*** Update File: huge.bin\n@@\n-x\n+y")
        self.assertEqual("TOO_LARGE", caught.exception.code)

    def test_revalidate_rejects_unknown_or_inconsistent_fields(self):
        intent = self.parse("*** Update File: old.txt\n@@\n-old\n+new")
        tampered = dict(intent)
        tampered["unexpected"] = True
        with self.assertRaises(PatchIntentError) as caught:
            revalidate_intent(tampered, self.root)
        self.assertEqual("INTENT_INVALID", caught.exception.code)
        tampered = dict(intent)
        tampered["target_paths"] = []
        with self.assertRaises(PatchIntentError) as caught:
            revalidate_intent(tampered, self.root)
        self.assertEqual("INTENT_INVALID", caught.exception.code)
        tampered = json.loads(json.dumps(intent))
        tampered["targets"][0]["parent_fingerprint"] = "0" * 64
        unsigned = dict(tampered)
        unsigned["intent_sha256"] = ""
        from cp_runtime.patch_intent import _digest
        tampered["intent_sha256"] = _digest(unsigned)
        with self.assertRaises(PatchIntentError) as caught:
            revalidate_intent(tampered, self.root)
        self.assertEqual("INTENT_INVALID", caught.exception.code)

    def test_strict_markers_and_limits(self):
        self.assertCode("COMMAND_NOT_STRING", None)
        self.assertCode("MALFORMED_MARKER", "*** Begin Patch\n*** Add File: x\n+1")
        self.assertCode("DUPLICATE_TARGET", "*** Begin Patch\n*** Add File: x\n+1\n*** Add File: x\n+2\n*** End Patch")
        self.assertCode("PATH_ESCAPE", "*** Begin Patch\n*** Add File: ../x\n+1\n*** End Patch")
        self.assertCode("INVALID_PATH", "*** Begin Patch\n*** Add File: C:/x\n+1\n*** End Patch")
        self.assertCode("COMMAND_TOO_LARGE", "x" * (1024 * 1024 + 1))

    def test_utf8_bytes_and_path_bytes_limits(self):
        with self.assertRaises(PatchIntentError) as caught:
            parse_apply_patch("*** Begin Patch\n*** Add File: " + ("界" * 400) + "\n+1\n*** End Patch", self.root)
        self.assertEqual("PATH_TOO_LONG", caught.exception.code)
        # 中文：字节上限内的 Unicode 路径仍有效。 English: A Unicode path below the byte limit remains valid.
        path = "é.txt"
        intent = self.parse("*** Add File: " + path + "\n+ok")
        self.assertEqual(path, intent["targets"][0]["path"])

    def test_revalidation_detects_parent_replacement(self):
        parent = self.root / "nested"
        parent.mkdir()
        (parent / "file.txt").write_text("x", encoding="utf-8")
        intent = self.parse("*** Update File: nested/file.txt\n@@\n-x\n+y")
        moved = self.root / "nested-old"
        parent.rename(moved)
        parent.mkdir()
        (parent / "file.txt").write_text("x", encoding="utf-8")
        with self.assertRaises(PatchIntentError) as caught:
            revalidate_intent(intent, self.root)
        self.assertIn(caught.exception.code, {"INTENT_STALE_PARENT", "INTENT_STALE_FILE"})

    @unittest.skipUnless(os.name == "nt", "Windows reparse-point regression")
    def test_rejects_junction_or_symlink_parent(self):
        target = self.root / "target"
        target.mkdir()
        link = self.root / "link"
        try:
            link.symlink_to(target, target_is_directory=True)
        except (OSError, NotImplementedError):
            self.skipTest("symlink unavailable")
        with self.assertRaises(PatchIntentError) as caught:
            self.parse("*** Add File: link/file.txt\n+1")
        self.assertEqual("LINK_REJECTED", caught.exception.code)

    def test_normalizes_safe_path_link_rejection(self):
        original = patch_intent_module.safe_path

        def reject_target(path):
            if Path(path) == self.root:
                return original(path)
            raise CapabilityError("LINK_REJECTED")

        with patch.object(patch_intent_module, "safe_path", side_effect=reject_target):
            with self.assertRaises(PatchIntentError) as caught:
                self.parse("*** Add File: nested/file.txt\n+1")
        self.assertEqual("LINK_REJECTED", caught.exception.code)


if __name__ == "__main__":
    unittest.main()
