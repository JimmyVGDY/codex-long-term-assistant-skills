from __future__ import annotations

import importlib.util
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _load_module():
    spec = importlib.util.spec_from_file_location(
        "runtime_localization", ROOT / "scripts" / "runtime_localization.py")
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class RuntimeLocalizationTests(unittest.TestCase):
    def test_repository_runtime_mapping_is_complete(self) -> None:
        module = _load_module()
        findings = module.mapping_findings(ROOT, module.load_mapping())
        self.assertEqual([], findings)

    def test_extract_skips_bilingual_docstring_and_finds_runtime_literals(self) -> None:
        module = _load_module()
        with tempfile.TemporaryDirectory(prefix="cp-runtime-i18n-") as temporary:
            path = Path(temporary) / "sample.py"
            path.write_text(
                '"""中文：说明。\n\nEnglish: Description.\n"""\n'
                'plain = "运行失败"\n'
                'detail = f"任务 {task_id} 失败"\n',
                encoding="utf-8",
            )
            rows = module.extract_literals(path)
        self.assertEqual(["plain", "fstring"], [row["kind"] for row in rows])
        self.assertEqual("运行失败", rows[0]["source"])

    def test_localize_file_preserves_code_and_replaces_plain_and_fstring(self) -> None:
        module = _load_module()
        with tempfile.TemporaryDirectory(prefix="cp-runtime-i18n-") as temporary:
            path = Path(temporary) / "sample.py"
            path.write_text(
                '"""中文：说明。\n\nEnglish: Description.\n"""\n'
                'task_id = "T-1"\n'
                'plain = "运行失败"\n'
                'detail = f"任务 {task_id} 失败"\n',
                encoding="utf-8",
            )
            module.localize_file(path, {
                "plain": {"运行失败": "Execution failed"},
                "fstring": {'f"任务 {task_id} 失败"': 'f"Task {task_id} failed"'},
            })
            rendered = path.read_text(encoding="utf-8")
        self.assertIn('plain = "Execution failed"', rendered)
        self.assertIn('detail = f"Task {task_id} failed"', rendered)
        self.assertIn("中文：说明", rendered)


if __name__ == "__main__":
    unittest.main()
