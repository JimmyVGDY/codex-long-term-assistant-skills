"""中文：显式 64KB 配置不扩大既有 8KB 根，也不隐藏截断。

English: Explicit 64KB profile does not widen existing 8KB roots or hide truncation.
"""
import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'runtime'))
from cp_runtime.common import canonical_json
from cp_runtime.desktop_context_call import reader_call
from cp_runtime.routing_context_contract import (CONTEXT_64K,MODE,MODE_V2,REQUEST,
    create_bundle,load_bundle,runtime,context_limits)
from cp_runtime.routing_contract import RoutingError


class LargeContextTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.root=Path(self.temp.name)
        self.repo=self.root/'repo';self.repo.mkdir()
        self.prompt=self.root/'prompt.txt'
        self.reader=ROOT/'hooks/review_context_reader.py'
        self.python=Path(sys.executable)

    def tearDown(self):self.temp.cleanup()

    def bundle(self,text,profile=None):
        self.prompt.write_bytes(text.encode('utf8'))
        pointer=create_bundle(self.root/'bundle.json',repo=self.repo,business_prompt=self.prompt,
            packet_sha256='a'*64,baseline_sha256='b'*64,artifacts={},context_profile=profile)
        request={key:None for key in REQUEST}
        request.update(schema_version='routing-request/2',business_prompt_sha256=hashlib.sha256(text.encode()).hexdigest(),
                       packet_sha256='a'*64,baseline_sha256='b'*64,context_bundle=pointer)
        return request

    def test_large_payload_requires_explicit_profile_and_matching_root(self):
        with self.assertRaises(RoutingError):self.bundle('x'*16000)
        request=self.bundle('x'*16000,CONTEXT_64K)
        large=runtime(self.reader,self.python,transport_mode=MODE_V2,context_profile=CONTEXT_64K)
        small=runtime(self.reader,self.python,transport_mode=MODE_V2)
        self.assertEqual('x'*16000,load_bundle(request,large)['business_prompt'])
        with self.assertRaisesRegex(RoutingError,'RUNTIME_PROFILE_MISMATCH'):load_bundle(request,small)
        with self.assertRaisesRegex(RoutingError,'CONTEXT_PROFILE'):
            runtime(self.reader,self.python,transport_mode=MODE,context_profile=CONTEXT_64K)

    def test_large_reader_output_is_exact_and_old_grants_keep_their_limit(self):
        request=self.bundle('review context\n'*3000,CONTEXT_64K)
        context=load_bundle(request)
        output=canonical_json({'schema_version':'context-reader-output/1','context_receipt':'0'*64,'context':context})+'\n'
        grant={'output':output,'output_sha256':hashlib.sha256(output.encode()).hexdigest(),
               'reservation_id':'synthetic','call_ref':'synthetic','context_profile':CONTEXT_64K}
        path=self.root/'grant.json';path.write_text(json.dumps(grant),encoding='utf8')
        result=subprocess.run([sys.executable,'-I','-B',str(self.reader),str(path)],capture_output=True,timeout=10)
        self.assertEqual(0,result.returncode,result.stderr)
        self.assertEqual(output.encode(),result.stdout)
        grant.pop('context_profile');path.write_text(json.dumps(grant),encoding='utf8')
        result=subprocess.run([sys.executable,'-I','-B',str(self.reader),str(path)],capture_output=True,timeout=10)
        self.assertNotEqual(0,result.returncode)
        self.assertEqual(b'',result.stdout)

    def test_total_serialized_bound_not_just_source_size(self):
        with self.assertRaisesRegex(RoutingError,'BUNDLE_TOO_LARGE'):
            self.bundle('x'*64000,CONTEXT_64K)

    def test_output_budget_and_code_mode_pragma_are_controller_owned(self):
        config=runtime(self.reader,self.python,transport_mode=MODE_V2,context_profile=CONTEXT_64K)
        _,limit,tokens=context_limits(config)
        call=reader_call(python_path=str(self.python),reader_path=str(self.reader),grant_path=str(self.root/'grant.json'),
                         recovery=True,expected_output_chars=64000,output_limit=limit,output_tokens=tokens)
        self.assertEqual(50000,call['parameters']['max_output_tokens'])
        self.assertTrue(call['javascript'].startswith('// @exec: {"max_output_tokens":50000}\n'))
        with self.assertRaisesRegex(RoutingError,'OUTPUT_PROFILE'):
            reader_call(python_path=str(self.python),reader_path=str(self.reader),grant_path=str(self.root/'grant.json'),
                        output_limit=65536,output_tokens=10000)


if __name__=='__main__':unittest.main()
