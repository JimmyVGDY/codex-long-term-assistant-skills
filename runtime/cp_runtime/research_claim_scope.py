"""中文：冻结完整必需范围；叶子证据不能授权部分范围晋升。

English: Frozen all-required claim; leaf evidence is never a subset promotion permit.
"""
from .routing_contract import exact,fail,ref,sha,profile_spec,policy
FIELDS={'schema_version','stage','claim','cells'}
DEV_CELL={'role','phase','scenario_ref','protocol_ref','profiles'}
CONFIRM_CELL={'role','phase','scenario_ref','protocol_ref','baseline_profile','candidate_profile','confirmation_case_refs'}
def validate(value,evaluations,*,complete=True):
    stage=value.get('stage') if isinstance(value,dict) else None
    exact(value,FIELDS|({'development_manifest'} if stage=='CONFIRMATION' else set()),'RESEARCH_CLAIM_FIELDS')
    if value['schema_version']!='research-comparison-scope/1' or stage not in {'DEVELOPMENT_SCREEN','CONFIRMATION'}:fail('RESEARCH_CLAIM_VERSION')
    expected='AUDIT_ONLY' if stage=='DEVELOPMENT_SCREEN' else 'ALL_REQUIRED_NO_SIMULTANEOUS_CI'
    if value['claim']!=expected:fail('RESEARCH_CLAIM_TYPE')
    from .default_qualification_plan import expected_cells
    required=expected_cells();cells=value['cells']
    if not isinstance(cells,list) or not 1<=len(cells)<=len(required):fail('RESEARCH_CLAIM_CELLS')
    leaf={(p['scenario']['role'],p['scenario']['phase']):p for p in evaluations}
    if len(leaf)!=len(evaluations):fail('RESEARCH_LEAF_CELL_REUSED')
    seen=set()
    for cell in cells:
        exact(cell,DEV_CELL if stage=='DEVELOPMENT_SCREEN' else CONFIRM_CELL,'RESEARCH_CLAIM_CELL_FIELDS')
        key=(cell['role'],cell['phase']);plan=leaf.get(key)
        if key not in required or key in seen or plan is None or cell['scenario_ref']!=ref(plan['scenario']) or cell['protocol_ref']!=plan['protocol_ref']:fail('RESEARCH_CLAIM_LEAF_BINDING')
        seen.add(key);sha(cell['scenario_ref']);sha(cell['protocol_ref'])
        if stage=='DEVELOPMENT_SCREEN':
            profiles=cell['profiles']
            if not isinstance(profiles,list) or len(profiles)!=len(set(profiles)) or set(profiles)!={c['profile_id'] for c in plan['costs']} or complete and set(profiles)!=set(policy()['profiles']):fail('RESEARCH_DEVELOPMENT_CATALOG')
            for p in profiles:profile_spec(p)
        else:
            baseline=cell['baseline_profile'];candidate=cell['candidate_profile'];b=profile_spec(baseline);c=profile_spec(candidate)
            if not b['model'].startswith('gpt-5.6-') or not c['model'].startswith('gpt-6-') or plan['baseline_profile']!=baseline or plan['comparisons']!=[{'anchor':baseline,'challenger':candidate}] or plan['family_intervals']!=4:fail('RESEARCH_CONFIRMATION_FIXED_PAIR')
            cases=cell['confirmation_case_refs']
            if not isinstance(cases,list) or len(cases)!=len(set(cases)) or set(cases)!=set(plan['case_plan']):fail('RESEARCH_CONFIRMATION_CASE_SET')
            for case in cases:sha(case)
    if seen!=set(leaf) or complete and seen!=required:fail('RESEARCH_REQUIRED_MATRIX_INCOMPLETE')
    if stage=='CONFIRMATION':
        from .research_documents import FILE
        exact(value['development_manifest'],FILE,'RESEARCH_DEVELOPMENT_MANIFEST')
    return value
def problems(plans):
    result=set()
    for plan in plans:
        for proof in plan['independence']['cases']:
            for label,key in (('problem','source_problem_ref'),('cause','root_cause_ref'),('cluster','cluster_id')):result.add((label,proof[key]))
        for evaluation in plan['evaluations']:
            for case in evaluation['cases']:result.add(('prompt',case['prompt_ref']))
    return result
def check_independent_confirmation(scope,plans):
    if scope['stage']!='CONFIRMATION':return
    from .research_documents import read_file,read_manifest
    manifest=read_file(scope['development_manifest']);header=read_file(manifest['campaign_plan'])
    if header.get('comparison_scope',{}).get('stage')!='DEVELOPMENT_SCREEN':fail('RESEARCH_CONFIRMATION_DEVELOPMENT_STAGE')
    campaign,development,_,_=read_manifest(manifest)
    if campaign['comparison_scope']['stage']!='DEVELOPMENT_SCREEN' or any(p['identity']!=campaign['identity'] for p in plans):fail('RESEARCH_CONFIRMATION_DEVELOPMENT_BINDING')
    if problems(plans).intersection(problems(development)):fail('RESEARCH_DEVELOPMENT_CONFIRMATION_OVERLAP')
