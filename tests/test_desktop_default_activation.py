"""中文：使用本地文件系统与事务夹具，不授予真实模型资格。

English: Local filesystem/transaction fixtures. No real model qualification is granted.
"""
import copy
import hashlib
import json
import os
import runpy
import shutil
import subprocess
import sys
import tempfile
import unittest
from datetime import datetime,timedelta,timezone
from pathlib import Path
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'runtime'))
from cp_runtime import desktop_default_activation as activation
from cp_runtime.approval import issue_approval,load_approval
from cp_runtime.common import atomic_write_json,utc_now
from cp_runtime.event_v2 import stable_repo_fingerprint
from cp_runtime.payload_integrity import PayloadIntegrityError,write_manifest
from cp_runtime.project import onboard_project
from cp_runtime.routing_contract import RoutingError,policy_digest,ref


class ActivationTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.root=Path(self.temp.name)
        self.repo=self.root/'repo';self.repo.mkdir()
        subprocess.run(['git','init','-q',str(self.repo)],check=True,capture_output=True)
        (self.repo/'README.md').write_text('Synthetic default activation fixture.\n',encoding='utf8')
        subprocess.run(['git','-C',str(self.repo),'add','README.md'],check=True,capture_output=True)
        subprocess.run(['git','-C',str(self.repo),'-c','user.name=Fixture','-c','user.email=fixture@example.invalid',
                        '-c','commit.gpgsign=false','commit','-qm','fixture'],check=True,capture_output=True)
        self.project=onboard_project(self.repo,'activation-test','Synthetic activation',self.root/'profile')
        self.home=self.root/'home';self.home.mkdir()
        self.env=patch.dict(os.environ,{'CODEX_HOME':str(self.home)})
        self.env.start()
        self.identity={'project_id':self.project.project_id,'repo_fingerprint':stable_repo_fingerprint(str(self.repo))}
        self.source=self.root/'source';self.source.mkdir()
        for name in ('.codex-plugin','skills','hooks','runtime'):(self.source/name).mkdir()
        library=self.source/'runtime/cp_runtime';library.mkdir()
        for name in activation.REQUIRED_RUNTIME+activation.REQUIRED_ORDINARY_RUNTIME:(library/name).write_text('# synthetic payload\n',encoding='utf8')
        for name in activation.REQUIRED_HOOKS:(self.source/'hooks'/name).write_text('# synthetic hook\n',encoding='utf8')
        (self.source/'.codex-plugin/plugin.json').write_text('{}\n',encoding='utf8')
        self.managed=self.root/'managed';self.cache=self.root/'cache'
        shutil.copytree(self.source,self.managed);shutil.copytree(self.source,self.cache)
        shutil.copytree(self.source/'runtime',self.home/'runtime')
        shutil.copytree(self.source/'hooks',self.home/'cp-assistant-hooks')
        self.manifest=self.root/'frozen-payload.json'
        write_manifest(self.source,'codex-cross-project-engineering-assistant','fixture',self.manifest)
        self.hooks=[]
        for event in ('PreToolUse','PostToolUse'):
            self.hooks.extend([{'event':event,'matcher':'.*','command':'python cp_context.py '+event},
                {'event':event,'matcher':'spawn_agent','command':'python cp_hook.py '+event}])
        for event in ('SubagentStart','SubagentStop'):
            self.hooks.append({'event':event,'matcher':'','command':'python cp_hook.py'})
        config={'hooks':{}}
        for item in self.hooks:
            config['hooks'].setdefault(item['event'],[]).append({'matcher':item['matcher'],
                'hooks':[{'type':'command','command':item['command']}]})
        atomic_write_json(self.home/'hooks.json',config)
        # 中文：Linux 的 sys.executable 可能是符号链接；安装证据绑定真实解释器文件。
        # English: Linux sys.executable may be a symlink; bind the actual interpreter file.
        self.python_executable=Path(sys.executable).resolve(strict=True)
        now=datetime.now(timezone.utc)
        self.expires=(now+timedelta(days=1)).isoformat()
        self.definition={'schema_version':'desktop-default-activation/2','activation_id':'fixture-default',
            'ordinary_contract':'frozen-v3-four-tier/1','qualification_plan':{'path':str(self.root/'qualification-plan.json'),'sha256':ref('synthetic-plan')},
            'identity':self.identity,'policy_id':'reviewer-matrix-v4','policy_digest':policy_digest(),
            'transport_mode':'desktop-authoritative-context/2','consumer_version':'qualification-study/1',
            'created_at':now.isoformat(),'expires_at':self.expires,'required_scenarios':[ref('scope')],
            'cards':[{'bundle':str(self.root/'bundle.json'),'experiment':str(self.root/'experiment.json'),
                'publication':str(self.root/'publication.json'),'trace_ledgers':[str(self.root/'budget.jsonl')],
                'bundle_ref':ref('bundle'),'experiment_ref':ref('experiment'),'publication_ref':ref('publication'),
                'publication_revision':1}],
            'installation':{'manifest':{'path':str(self.manifest),'sha256':self.file_ref(self.manifest)},
                'source_root':str(self.source),'managed_root':str(self.managed),'cache_root':str(self.cache),
                'enhancement_home':str(self.home),'required_hooks':self.hooks,
                'python':{'path':str(self.python_executable),'sha256':self.file_ref(self.python_executable)}}}
        self.pointer=activation.pointer_for(self.identity)
        # 中文：事务测试隔离资格验证，后者由完整研究集成测试覆盖；此模拟不离开夹具。
        # English: Transaction tests isolate qualification validation, which has separate
        # complete-study integration tests. This mock never leaves the fixture.
        self.cards=patch.object(activation,'_cards',return_value={ref('scope'):['g6-sol-medium']})
        self.cards.start()

    def tearDown(self):
        self.cards.stop();self.env.stop();self.temp.cleanup()

    @staticmethod
    def file_ref(path):return 'sha256:'+hashlib.sha256(path.read_bytes()).hexdigest()

    def prepare(self):
        return activation.prepare(self.root/'state/activation.json',self.definition,repo_path=self.repo,
                                  task_id='activation-task',now=utc_now())

    def approve(self,source):
        target=self.root/'approval.json'
        issue_approval(target,'activate-default',self.project.profile_path,'activation-task',['make-effective'],'local',
                       self.repo,self.expires,note=activation.approval_note(source))
        return target

    def activate(self):
        source=self.prepare()
        activation.verify_installation(source,repo_path=self.repo,now=utc_now())
        approval=self.approve(source)
        activation.activate(source,pointer_path=self.pointer,approval_path=approval,repo_path=self.repo,
                            task_id='activation-task',now=utc_now())
        return source,approval

    def test_no_activation_keeps_legacy_default_and_prepared_is_not_effective(self):
        self.assertEqual('reviewer-matrix-v3',activation.resolve_default(self.pointer,expected_identity=self.identity,
                        task_id='new-task',now=utc_now())['policy_id'])
        source=self.prepare()
        with self.assertRaisesRegex(RoutingError,'NOT_ACTIVE'):
            activation.verify_active(source,expected_identity=self.identity,now=utc_now(),consumer_task_id='new-task')
        self.assertFalse(self.pointer.exists())

    def test_verified_transaction_selects_new_default_and_consumes_approval_once(self):
        source,approval=self.activate()
        selected=activation.resolve_default(self.pointer,expected_identity=self.identity,task_id='new-task',now=utc_now())
        self.assertEqual('reviewer-matrix-v4',selected['policy_id'])
        self.assertEqual(source,selected['desktop_default_activation'])
        self.assertEqual('consumed',load_approval(approval)['status'])
        again=activation.activate(source,pointer_path=self.pointer,approval_path=approval,repo_path=self.repo,
                                  task_id='activation-task',now=utc_now())
        self.assertEqual(source,again['source'])
        self.assertEqual(3,len(activation._read(source)['history']))

    def test_unverified_install_and_wrong_approval_cannot_write_default(self):
        source=self.prepare();approval=self.approve(source)
        with self.assertRaisesRegex(RoutingError,'INSTALLATION_REQUIRED'):
            activation.activate(source,pointer_path=self.pointer,approval_path=approval,repo_path=self.repo,
                                task_id='activation-task',now=utc_now())
        activation.verify_installation(source,repo_path=self.repo,now=utc_now())
        with self.assertRaisesRegex(RoutingError,'APPROVAL_REQUIRED'):
            activation.activate(source,pointer_path=self.pointer,approval_path=approval,repo_path=self.repo,
                                task_id='foreign-task',now=utc_now())
        self.assertFalse(self.pointer.exists())
        self.assertEqual('active',load_approval(approval)['status'])

    def test_source_edits_do_not_disguise_or_damage_the_verified_installed_runtime(self):
        source,_=self.activate()
        (self.source/'runtime/cp_runtime/budget_v5.py').write_text('# next development change\n',encoding='utf8')
        activation.verify_active(source,expected_identity=self.identity,now=utc_now(),consumer_task_id='next-task')
        (self.cache/'runtime/cp_runtime/budget_v5.py').write_text('# corrupted installed cache\n',encoding='utf8')
        with self.assertRaises(PayloadIntegrityError):
            activation.verify_active(source,expected_identity=self.identity,now=utc_now(),consumer_task_id='next-task')

    def test_new_default_cannot_omit_ordinary_delegation_contract(self):
        definition=copy.deepcopy(self.definition)
        definition.pop('ordinary_contract')
        with self.assertRaisesRegex(RoutingError,'ORDINARY_COMPAT_REQUIRED'):
            activation.prepare(self.root/'without-ordinary.json',definition,repo_path=self.repo,
                               task_id='activation-task',now=utc_now())

    def test_ordinary_module_must_be_part_of_the_frozen_installed_payload(self):
        relative='runtime/cp_runtime/ordinary_delegation_v5.py'
        for directory in (self.source,self.managed,self.cache):
            (directory/relative).unlink()
        (self.home/relative).unlink()
        write_manifest(self.source,'codex-cross-project-engineering-assistant','fixture',self.manifest)
        self.definition['installation']['manifest']['sha256']=self.file_ref(self.manifest)
        source=self.prepare()
        with self.assertRaisesRegex(RoutingError,'PAYLOAD_INCOMPLETE'):
            activation.verify_installation(source,repo_path=self.repo,now=utc_now())

    def test_revocation_and_missing_pointer_never_silently_fall_back(self):
        source,_=self.activate()
        activation.revoke(source,repo_path=self.repo,reason_ref=ref('authorized rollback fixture'),now=utc_now())
        with self.assertRaisesRegex(RoutingError,'NOT_ACTIVE'):
            activation.resolve_default(self.pointer,expected_identity=self.identity,task_id='new-task',now=utc_now())
        self.assertTrue(self.pointer.resolve().is_relative_to(self.home.resolve()))
        self.pointer.unlink()
        with self.assertRaisesRegex(RoutingError,'POINTER_MISSING'):
            activation.resolve_default(self.pointer,expected_identity=self.identity,task_id='new-task',now=utc_now())
        self.assertTrue(Path(source['path']).exists())

    def test_missing_hook_or_live_runtime_change_rejects(self):
        source=self.prepare()
        live=self.home/'runtime/cp_runtime/review_v5.py'
        raw=live.read_bytes();live.write_bytes(b'changed')
        with self.assertRaisesRegex(RoutingError,'LIVE_FILE_CHANGED'):
            activation.verify_installation(source,repo_path=self.repo,now=utc_now())
        live.write_bytes(raw)
        atomic_write_json(self.home/'hooks.json',{'hooks':{}})
        with self.assertRaisesRegex(RoutingError,'HOOK_MISSING'):
            activation.verify_installation(source,repo_path=self.repo,now=utc_now())

    def test_required_runtime_and_hook_surface_cannot_be_omitted(self):
        bad=copy.deepcopy(self.definition)
        bad['installation']['required_hooks']=[self.hooks[0]]
        with self.assertRaisesRegex(RoutingError,'HOOK_COVERAGE'):activation.validate_definition(bad)
        self.cards.stop()
        with self.assertRaises(OSError):self.prepare()
        self.cards.start()

    def test_project_activation_can_cover_all_roles_and_phases_without_widening_a_task(self):
        definition=copy.deepcopy(self.definition)
        definition['cards']=[]
        definition['required_scenarios']=[]
        for number in range(21):
            source=copy.deepcopy(self.definition['cards'][0])
            source['bundle_ref']=ref('bundle-'+str(number))
            definition['cards'].append(source)
            definition['required_scenarios'].append(ref('scope-'+str(number)))
        activation.validate_definition(definition)
        activation.verify_root_card_sources(definition,definition['cards'][3:6])
        for invalid in ([],definition['cards'][:11],[definition['cards'][0]]*2):
            with self.subTest(size=len(invalid)),self.assertRaisesRegex(RoutingError,'ROOT_SCOPE_MISMATCH'):
                activation.verify_root_card_sources(definition,invalid)
        foreign=copy.deepcopy(definition['cards'][0])
        foreign['publication_revision']=2
        with self.assertRaisesRegex(RoutingError,'ROOT_SCOPE_MISMATCH'):
            activation.verify_root_card_sources(definition,[foreign])
        definition['cards']*=5
        with self.assertRaisesRegex(RoutingError,'ACTIVATION_CARDS'):
            activation.validate_definition(definition)

    def test_new_envelope_resolves_default_and_explicit_legacy_stays_frozen(self):
        source,_=self.activate()
        script=ROOT/'skills/engineering-quality-delivery/scripts/execution_guard.py'
        guard=runpy.run_path(str(script))
        for task_id,policy in (('automatic',None),('compatibility','reviewer-matrix-v3')):
            directory=self.root/task_id
            args=[str(script),'init','--state-dir',str(directory),'--task-id',task_id,
                  '--repo-path',str(self.repo),'--project-profile',str(self.project.profile_path)]
            if policy:args.extend(['--reviewer-policy',policy])
            with patch.object(sys,'argv',args):guard['main']()
            state=guard['load_state'](directory)
            expected='reviewer-matrix-v3' if policy else 'reviewer-matrix-v4'
            self.assertEqual(expected,state['routing']['reviewer_policy']['policy_id'])
            self.assertEqual('luna-low',state['routing']['delegation_budget']['default_model_profile'])
            if policy:self.assertNotIn('desktop_default_activation',state['routing'])
            else:self.assertEqual(source,state['routing']['desktop_default_activation'])

    def test_explicit_rollback_restores_old_default_without_deleting_history(self):
        source,_=self.activate()
        reason=ref('explicit rollback')
        approval=self.root/'rollback.json'
        note='desktop-default-restore-legacy:'+ref({'source':source,'reason_ref':reason})
        issue_approval(approval,'rollback-default',self.project.profile_path,'rollback-task',['make-effective'],
                       'local',self.repo,self.expires,note=note)
        activation.restore_legacy(source,approval_path=approval,repo_path=self.repo,task_id='rollback-task',
                                  reason_ref=reason,now=utc_now())
        selected=activation.resolve_default(self.pointer,expected_identity=self.identity,task_id='next-task',now=utc_now())
        self.assertEqual('reviewer-matrix-v3',selected['policy_id'])
        self.assertIn('explicit_restore_ref',selected)
        self.assertTrue(Path(source['path']).exists())
        self.assertEqual(4,len(activation._read(source)['history']))
        activation.revoke(source,repo_path=self.repo,reason_ref=ref('already rolled back'),now=utc_now())
        self.assertEqual('LEGACY_RESTORED',activation._read(source)['status'])
        with self.assertRaisesRegex(RoutingError,'NOT_ACTIVE'):
            activation.verify_active(source,expected_identity=self.identity,now=utc_now(),consumer_task_id='old-root')

    def test_forged_history_or_foreign_restored_pointer_is_rejected(self):
        source,_=self.activate()
        path=Path(source['path'])
        state=activation._read(source)
        state['status']='LEGACY_RESTORED'
        atomic_write_json(path,state,seal=True)
        with self.assertRaisesRegex(RoutingError,'ACTIVATION_HISTORY'):
            activation.resolve_default(self.pointer,expected_identity=self.identity,task_id='next-task',now=utc_now())
        state['history'].append({'action':'LEGACY_RESTORED','at':utc_now(),'reason_ref':ref('fixture')})
        atomic_write_json(path,state,seal=True)
        foreign={**self.identity,'project_id':'foreign-project'}
        # 中文：重新贴标签的指针不得改变另一个项目的查询目标。
        # English: A relabelled pointer must not redirect another project's lookup.
        atomic_write_json(self.pointer,{'schema_version':'desktop-default-pointer/1','identity':foreign,'source':source},seal=True)
        atomic_write_json(self.pointer.with_suffix('.enrollment.json'),
            {'schema_version':'desktop-default-enrollment/1','identity':foreign},seal=True)
        with self.assertRaisesRegex(RoutingError,'NOT_ACTIVE_OR_FOREIGN'):
            activation.resolve_default(self.pointer,expected_identity=foreign,task_id='foreign-task',now=utc_now())

    def test_interrupted_activation_keeps_a_fail_closed_enrollment(self):
        source=self.prepare()
        activation.verify_installation(source,repo_path=self.repo,now=utc_now())
        approval=self.approve(source)
        write=activation.atomic_write_json
        def interrupted(path,value,**kwargs):
            if Path(path)==Path(source['path']) and value.get('status')=='ACTIVE':
                raise OSError('synthetic interrupted activation')
            return write(path,value,**kwargs)
        with patch.object(activation,'atomic_write_json',interrupted),self.assertRaises(OSError):
            activation.activate(source,pointer_path=self.pointer,approval_path=approval,repo_path=self.repo,
                                task_id='activation-task',now=utc_now())
        self.assertEqual('consumed',load_approval(approval)['status'])
        self.assertFalse(self.pointer.exists())
        with self.assertRaisesRegex(RoutingError,'POINTER_MISSING'):
            activation.resolve_default(self.pointer,expected_identity=self.identity,task_id='next-task',now=utc_now())


if __name__=='__main__':unittest.main()
