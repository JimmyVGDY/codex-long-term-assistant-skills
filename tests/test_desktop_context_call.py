"""中文：执行生成的 JavaScript，并在 Windows 上运行实际的有界 Python 读取器。

English: Execute the generated JS and (on Windows) the actual bounded Python reader.
"""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "runtime"))
from cp_runtime.desktop_context_call import reader_call


class DesktopContextCallTests(unittest.TestCase):
    @unittest.skipUnless(shutil.which("node"), "JavaScript runtime unavailable")
    def test_generated_program_recovers_pending_and_valid_json_truncation(self):
        request = self.call(recovery=True, expected_output_chars=3)
        script = "let calls=[];let texts=[];const tools={exec_command:async p=>{calls.push(p);"
        script += "if(calls.length===1)throw Error('CONTEXT_V2_RETRY_RECEIPT');"
        script += "return {exit_code:0,output:calls.length===2?'{}':'{}\\n'};}};const text=x=>texts.push(x);"
        script += "(async()=>{\n" + request["javascript"] + "\nprocess.stdout.write(JSON.stringify({calls,texts}));})();"
        run = subprocess.run([shutil.which("node"), "-"], input=script.encode(), capture_output=True, check=True, timeout=10)
        observed = json.loads(run.stdout)
        self.assertEqual([request["parameters"]] * 3, observed["calls"])
        self.assertEqual([{"exit_code": 0, "output": "{}\n"}], observed["texts"])

    @unittest.skipUnless(shutil.which("node"), "JavaScript runtime unavailable")
    def test_generated_program_does_not_retry_permission_or_exhaustion(self):
        request = self.call(recovery=True)
        for reason, expected in (("CONTEXT_V2_RETRY_RECEIPT", 3), ("PERMISSION_DENIED", 1)):
            script = "let calls=0;const tools={exec_command:async p=>{calls++;throw Error(" + json.dumps(reason) + ");}};const text=x=>{};"
            script += "(async()=>{try{\n" + request["javascript"] + "\n}catch(e){}process.stdout.write(JSON.stringify({calls}));})();"
            run = subprocess.run([shutil.which("node"), "-"], input=script.encode(), capture_output=True, check=True, timeout=10)
            self.assertEqual(expected, json.loads(run.stdout)["calls"])

    def call(self, **changes):
        return reader_call(**{"python_path": "D:\\Apps\\Python314\\python.exe",
                             "reader_path": "C:\\Users\\Tester\\插件 目录\\review_context_reader.py",
                             "grant_path": "D:\\Tasks\\试验 目录\\grant.json", **changes})

    @unittest.skipUnless(shutil.which("node"), "JavaScript runtime unavailable")
    def test_serialized_javascript_round_trips_exact_arguments(self):
        for grant in ("D:\\Tasks\\new\\test\\bundle.json", "D:\\目录 with spaces\\材料.json",
                      "\\\\server\\share\\grant.json", "\\\\?\\C:\\long\\grant.json"):
            request = self.call(grant_path=grant)
            script = "const tools={exec_command:async x=>x}; const text=x=>process.stdout.write(JSON.stringify(x));\n"
            script += "(async()=>{\n" + request["javascript"] + "\n})().catch(e=>{throw e});"
            result = subprocess.run([shutil.which("node"), "-"], input=script.encode("utf-8"),
                                    capture_output=True, check=True, timeout=10)
            with self.subTest(grant=grant):
                self.assertEqual(request["parameters"], json.loads(result.stdout))
                self.assertNotIn("\n", json.loads(result.stdout)["cmd"])
                self.assertNotIn("\t", json.loads(result.stdout)["cmd"])

    def test_ordinary_windows_paths_do_not_need_javascript_backslash_escaping(self):
        request = self.call()
        self.assertNotIn("\\", request["parameters"]["cmd"])
        self.assertIn("C:/Users/Tester/插件 目录/review_context_reader.py", request["parameters"]["cmd"])

    def test_paths_cannot_add_shell_code_or_traverse(self):
        for path in ("relative.json", "C:/root/../foreign.json", "C:/root/a' ; whoami ; '.json",
                     "C:/root/a\n.json", "C:/root/a\r.json", "C:/root/a\0.json"):
            with self.subTest(path=path), self.assertRaisesRegex(ValueError, "COMMAND_PATH"):
                self.call(grant_path=path)

    @unittest.skipUnless(os.name == "nt" and shutil.which("node"), "Native Windows Desktop transport")
    def test_js_to_powershell_to_python_preserves_complete_output_bytes(self):
        with tempfile.TemporaryDirectory(prefix="context 汉字 with spaces ") as directory:
            grant = Path(directory) / "回执 grant.json"
            output = json.dumps({"context_receipt": "a" * 64, "context": {"text": "汉字\\n\nactual newline"}},
                                ensure_ascii=False, separators=(",", ":")) + "\n"
            grant.write_text(json.dumps({"output": output, "output_sha256": hashlib.sha256(output.encode()).hexdigest()}),
                             encoding="utf-8")
            request = reader_call(python_path=sys.executable, reader_path=str(ROOT / "hooks/review_context_reader.py"),
                                  grant_path=str(grant))
            script = "const cp=require('child_process'); const tools={exec_command:async p=>{"
            script += "const r=cp.spawnSync('powershell.exe',['-NoLogo','-NoProfile','-NonInteractive','-Command',p.cmd]);"
            script += "if(r.status!==0)throw Error(String(r.stderr));return {bytes:r.stdout.toString('base64')};}};"
            script += "const text=x=>process.stdout.write(JSON.stringify(x));(async()=>{\n" + request["javascript"] + "\n})();"
            result = subprocess.run([shutil.which("node"), "-"], input=script.encode(), capture_output=True,
                                    check=True, timeout=20)
            import base64
            self.assertEqual(output.encode("utf-8"), base64.b64decode(json.loads(result.stdout)["bytes"]))


if __name__ == "__main__":
    unittest.main()
