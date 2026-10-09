"""中文：第三版激活仅消费完整已发布矩阵，叶子统计使用模拟。

English: Activation/3 consumes only the complete published matrix; leaf stats mocked.
"""
import contextlib,copy,io,json,sys,unittest
from pathlib import Path
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'runtime'))
from cp_runtime import desktop_default_activation as activation,research_publication as publication
from cp_runtime.payload_integrity import load_manifest,write_manifest
from cp_runtime.routing_context_contract import CONTEXT_64K,MODE_V2,create_bundle,runtime,validate_runtime
from cp_runtime.routing_contract import ref,policy_digest,resource_need
import test_desktop_default_activation as fixture

class MatrixActivationConsumers(unittest.TestCase):
    def setUp(self):
        self.f=fixture.ActivationTests(methodName='runTest');self.f.setUp()
        self.actual_cards=self.f.cards.temp_original
        self.definition=copy.deepcopy(self.f.definition)
        self.definition.update(schema_version='desktop-default-activation/3',consumer_version='qualification-study/2',context_profile=CONTEXT_64K,delivery_contract='same-call-notify/2',cards=[],required_scenarios=[ref(f'matrix-cell-{i}') for i in range(21)],research_matrix={'source':{'path':str(self.f.root/'matrix-source.json'),'sha256':ref('source')},'publication':{'path':str(self.f.root/'matrix-publication.json'),'sha256':ref('publication')}})
        self.matrix={'identity':self.f.identity,'qualification':{s:['g6-sol-medium'] for s in self.definition['required_scenarios']},'experiments':[{'synthetic':True}],'candidate_payload_digest':load_manifest(self.f.manifest)['payload_digest']}
    def tearDown(self):self.f.tearDown()
    def test_activation3_requires_matrix_only_and_all_required_scenarios(self):
        activation.validate_definition(self.definition)
        activation.verify_root_card_sources(self.definition,[])
        with self.assertRaisesRegex(ValueError,'LEAF_SOURCE_DENIED'):
            activation.verify_root_card_sources(self.definition,[{'bundle':'fake'}])
        def synthetic_file(pointer):return {'schema_version':'research-matrix-source/1' if pointer['path'].endswith('source.json') else 'research-matrix-publication/1'}
        with patch.object(publication,'_file',side_effect=synthetic_file),patch.object(publication,'verify_matrix_publication',return_value=self.matrix),patch('cp_runtime.default_qualification_plan.verify_plan',return_value={'plan':'synthetic'}),patch('cp_runtime.default_qualification_plan.verify_confirmation',return_value=None):
            self.assertEqual(self.matrix['qualification'],self.actual_cards(self.definition,now=self.definition['created_at'],consumer_task_id='fixture'))
            incomplete=copy.deepcopy(self.matrix);incomplete['qualification'].pop(next(iter(incomplete['qualification'])))
            with patch.object(publication,'verify_matrix_publication',return_value=incomplete),self.assertRaisesRegex(ValueError,'IDENTITY_OR_SCOPE'):
                self.actual_cards(self.definition,now=self.definition['created_at'],consumer_task_id='fixture')
    def test_old_definition_cannot_smuggle_new_matrix(self):
        older=copy.deepcopy(self.definition);older.update(schema_version='desktop-default-activation/2',consumer_version='qualification-study/1')
        older.pop('delivery_contract')
        with self.assertRaisesRegex(ValueError,'MATRIX_VERSION_REQUIRED'):
            activation.validate_definition(older)
    def test_matrix_definition_requires_exact_delivery_and_preserves_ordinary_workers(self):
        from cp_runtime.ordinary_routing_v5 import enabled as ordinary_enabled
        from cp_runtime.notify_wire import enabled as wire_enabled
        for field,bad in (('context_profile',None),('delivery_contract',None),('delivery_contract','same-call-notify/1')):
            changed=copy.deepcopy(self.definition)
            if bad is None:changed.pop(field)
            else:changed[field]=bad
            with self.subTest(field=field,bad=bad),self.assertRaisesRegex(ValueError,'DELIVERY_REQUIRED'):
                activation.validate_definition(changed)
        configured=runtime(ROOT/'hooks/review_context_reader.py',Path(sys.executable),transport_mode=MODE_V2,context_profile=CONTEXT_64K,ordinary_contract=self.definition['ordinary_contract'],delivery_contract=self.definition['delivery_contract'])
        state={'root_binding':{'context_runtime':validate_runtime(configured)}}
        self.assertTrue(wire_enabled(state))
        self.assertTrue(ordinary_enabled(configured,'worker'))
        self.assertTrue(ordinary_enabled(configured,'explorer'))
    def test_new_default_root_creates_wire_program_and_rejects_delivery_drift(self):
        from cp_runtime import budget_v5 as budget,routing_cli_v5 as cli,routing_context_v5
        from cp_runtime.common import atomic_write_json,repo_snapshot
        from cp_runtime.context_tool_surface import reader_program
        from test_routing_v4_selection_phase import plan,slot,capacity
        from unittest.mock import patch
        for name in ('research_documents.py','research_claim_scope.py','research_campaign.py','research_audit.py','research_negative.py','research_publication.py','notify_wire.py'):
            relative=Path('runtime/cp_runtime')/name
            for root in (self.f.source,self.f.managed,self.f.cache,self.f.home):
                path=root/relative
                path.parent.mkdir(parents=True,exist_ok=True)
                path.write_text('# synthetic installed study/2 module\n',encoding='utf8')
        write_manifest(self.f.source,'codex-cross-project-engineering-assistant','fixture',self.f.manifest)
        self.definition['installation']['manifest']['sha256']=self.f.file_ref(self.f.manifest)
        self.f.definition=self.definition
        source,_=self.f.activate()
        task='matrix-new-root';session='matrix-session'
        envelope=self.f.root/'matrix-root-envelope.json'
        atomic_write_json(envelope,{'schema_version':5,'task_id':task,'repo_path':str(self.f.repo),
            'routing':{'reviewer_policy':{'policy_id':'reviewer-matrix-v4','policy_digest':policy_digest()},'desktop_default_activation':source},
            'project':{'binding_status':'BOUND','project_id':self.f.project.project_id,'profile_path':str(self.f.project.profile_path),'profile_sha256':self.f.project.profile_sha256,'state_path':str(self.f.project.state_path)}})
        phase=plan([slot('review',[{'profile_id':'g6-sol-medium','qualification_ref':ref('fixture-qualified'),'cost_ref':ref('fixture-cost'),'resources':resource_need('g6-sol-medium',10)}])])
        phase['identity']=self.f.identity
        phase['slots'][0]['scenario'].update(context_bucket='bounded-review-64k',tools_profile='desktop-context-reader-64k-v1')
        capability=self.f.root/'matrix-capability.json'
        atomic_write_json(capability,{'schema_version':'desktop-capability/1','host_surface':'codex-desktop','source':'host-tool-metadata','root_session_ref':ref(session),'revision':1,'available_profiles':['g6-sol-medium'],'created_at':self.definition['created_at'],'expires_at':self.definition['expires_at'],'wallclock_enforced':False})
        config=self.f.root/'matrix-root-config.json'
        atomic_write_json(config,{'budget_id':'matrix-root-budget','sources':{'root_envelope':str(envelope),'capability':str(capability),'card_sets':[],'evaluation_costs':'','evaluation_ref':'','evidence_paths':{}},'execution_mode':'PRODUCTION','capacity':capacity(),'role_capacity':{'reviewer':100,'worker':100,'explorer':100},'phase_capacity':{'pre':100,'post':100,'repair':100},'phase_plan':phase,'max_parallel':1,'max_depth':1})
        ledger=self.f.root/'matrix-root-budget.jsonl'
        argv=['routing-v5','init','--config',str(config),'--root-envelope',str(envelope),'--reader',str(self.f.home/'cp-assistant-hooks/review_context_reader.py'),'--python',str(Path(sys.executable)),'--ledger',str(ledger),'--host-session-id',session]
        with patch.object(sys,'argv',argv),contextlib.redirect_stdout(io.StringIO()):cli.main()
        state=budget.read_budget(ledger)
        active_runtime=state['root_binding']['context_runtime']
        self.assertEqual(CONTEXT_64K,active_runtime['context_profile'])
        self.assertEqual('same-call-notify/2',active_runtime['delivery_contract'])
        self.assertEqual(self.definition['ordinary_contract'],active_runtime['ordinary_contract'])
        prompt=self.f.root/'matrix-prompt.txt';prompt.write_text('bounded reviewer input',encoding='utf8')
        baseline=repo_snapshot(self.f.repo)['sha256']
        bundle=create_bundle(self.f.root/'matrix-bundle.json',repo=self.f.repo,business_prompt=prompt,packet_sha256='a'*64,baseline_sha256=baseline,artifacts={},context_profile=CONTEXT_64K)
        request={'schema_version':'routing-request/2','task_id':task,'identity':self.f.identity,'policy_digest':policy_digest(),'scenario':phase['slots'][0]['scenario'],'execution_mode':'PRODUCTION','mode':'economy','slot_id':'review','baseline_sha256':baseline,'packet_sha256':'a'*64,'business_prompt_sha256':json.loads(Path(bundle['path']).read_text(encoding='utf8'))['business_prompt_sha256'],'context_bundle':bundle,'evaluation_case_ref':'','constraints':{'allowed_profiles':['g6-sol-medium'],'deadline_ms':None,'strict_wallclock':False},'evidence':{'ready':True,'independence_required':True,'inline_sufficient':False,'refs':[]},'expected':{}}
        program=reader_program(ledger,state,request,session,'fixture-child')
        self.assertTrue(program.startswith('// @exec: {"max_output_tokens":2000}'))
        self.assertIn('same-call-notify/2',program)
        self.assertLess(len(program),20000)
        for value in (None,'same-call-notify/1'):
            changed=copy.deepcopy(state)
            if value is None:changed['root_binding']['context_runtime'].pop('delivery_contract')
            else:changed['root_binding']['context_runtime']['delivery_contract']=value
            with self.subTest(value=value),self.assertRaisesRegex(ValueError,'ROOT_SCOPE_MISMATCH|NOTIFY_DELIVERY_CONTRACT'):
                routing_context_v5.load_snapshot(changed,request,self.definition['created_at'],cwd=str(self.f.repo),host_session_id=session)
        small_bundle=create_bundle(self.f.root/'ordinary-small-bundle.json',repo=self.f.repo,business_prompt=prompt,packet_sha256='a'*64,baseline_sha256=baseline,artifacts={})
        ordinary_request={**request,'scenario':{**phase['slots'][0]['scenario'],'role':'worker','phase':'pre','context_bucket':'small','tools_profile':'readonly'},'context_bundle':small_bundle,'business_prompt_sha256':json.loads(Path(small_bundle['path']).read_text(encoding='utf8'))['business_prompt_sha256'],'constraints':{'allowed_profiles':['g56-luna-medium'],'deadline_ms':None,'strict_wallclock':False}}
        with patch('cp_runtime.research_publication.production_snapshot',return_value={'ordinary_fixture':True}):
            self.assertEqual({'ordinary_fixture':True},routing_context_v5.load_snapshot(state,ordinary_request,self.definition['created_at'],cwd=str(self.f.repo),host_session_id=session))
        from cp_runtime import routing_hook_v5 as hook
        ordinary_state=copy.deepcopy(state)
        ordinary_state['permits']={'ordinary-permit':{'permit_id':'ordinary-permit','dispatch_ref':ref('ordinary_task'),'request':ordinary_request}}
        args={'task_name':'ordinary_task','agent_type':'worker','model':'gpt-5.6-luna','reasoning_effort':'medium','fork_turns':'none','message':prompt.read_text(encoding='utf8')}
        data={'session_id':session,'cwd':str(self.f.repo),'tool_use_id':'ordinary-host-call'}
        with patch.object(budget,'read_budget',return_value=ordinary_state),patch.object(hook,'verify_root'),patch.object(hook,'admission',return_value=contextlib.nullcontext(lambda _:None)),patch.object(budget,'approve_and_reserve',return_value={'ordinary_fixture':True}):
            self.assertEqual({'ordinary_fixture':True},hook.pretool(ledger,data,args))
        from cp_runtime.routing_context_contract import select as select_policy
        from cp_runtime.routing_v4 import snapshot_references
        from cp_runtime.ordinary_routing_v5 import option as ordinary_option
        from cp_runtime.routing_cards import derived_cards,protocol_reference
        import v4_fixtures as vf
        experiment=vf.experiment(30)
        experiment['identity']=self.f.identity
        experiment['protocol_ref']=protocol_reference(experiment)
        rows,gains=derived_cards(experiment)
        matrix={'identity':self.f.identity,'qualified_rows':rows,'gains':gains,'costs':vf.costs(experiment)}
        cap=json.loads(capability.read_text(encoding='utf8'))
        cap['revision']=2
        cap['available_profiles']+=['g56-luna-low','g56-luna-medium']
        atomic_write_json(capability,cap)
        from cp_runtime import research_publication as pub
        def matrix_file(pointer):
            return {'schema_version':'research-matrix-source/1' if pointer['path'].endswith('source.json') else 'research-matrix-publication/1'}
        for role,profile_id in (('worker','g56-luna-medium'),('explorer','g56-luna-low')):
            scenario={**phase['slots'][0]['scenario'],'role':role,'phase':'pre','context_bucket':'small','tools_profile':'readonly'}
            ordinary_slot=slot('ordinary',[ordinary_option(profile_id,scenario)],role=role,phase='pre')
            ordinary_slot['scenario']=scenario
            prepared_phase=plan([ordinary_slot]);prepared_phase['identity']=self.f.identity
            routed_state=copy.deepcopy(state);routed_state['phase_plan']=prepared_phase
            routed_request={**ordinary_request,'scenario':scenario,'slot_id':'ordinary','constraints':{'allowed_profiles':[profile_id],'deadline_ms':None,'strict_wallclock':False},'evidence':{'ready':True,'independence_required':True,'inline_sufficient':False,'refs':[ref('ordinary-evidence')]}}
            with self.subTest(role=role),patch.object(pub,'_file',side_effect=matrix_file),patch.object(pub,'verify_matrix_publication',return_value=matrix),patch('cp_runtime.routing_context_v4._requirement_evidence',return_value=routed_request['evidence']):
                snapshot=routing_context_v5.load_snapshot(routed_state,routed_request,self.definition['created_at'],cwd=str(self.f.repo),host_session_id=session)
                selected=select_policy({**routed_request,'expected':snapshot_references(snapshot)},snapshot,ordinary_contract=self.definition['ordinary_contract'])
                self.assertEqual('CANDIDATE_SELECTED',selected['status'])
                self.assertEqual(profile_id,selected['approved_profile'])
                self.assertEqual('frozen-v3-four-tier/1',selected['selection_basis'])

if __name__=='__main__':unittest.main()
