"""中文：默认迁移要求冻结的完整矩阵，不能使用调用方任意挑选的卡片。

English: Default migration requires a frozen complete matrix, not caller-picked cards.
"""
from pathlib import Path

from .common import parse_iso, verify_record
from .event_v2 import stable_repo_fingerprint
from .qualification_study import load_study_sources
from .routing_context_contract import safe_file
from .routing_contract import exact, fail, hex_digest, identity, policy, policy_digest, profile_spec, read_document, ref, sha

FIELDS = {'schema_version', 'identity', 'policy_digest', 'candidate_payload_digest', 'created_at',
          'selected', 'screening_sources', 'review_evidence'}
ROW_FIELDS = {'role', 'phase', 'scenario_ref', 'protocol_ref', 'baseline_profile', 'selected_profile'}


def expected_cells():
    return {(role, phase) for role in policy()['reviewer_roles'] for phase in ('pre', 'post', 'repair')}


def scope(value):
    return ref({key: value[key] for key in FIELDS - {'review_evidence'}})


def validate_plan(value):
    exact(value, FIELDS, 'DEFAULT_QUALIFICATION_PLAN_FIELDS')
    if value['schema_version'] != 'default-qualification-plan/1' or value['policy_digest'] != policy_digest():
        fail('DEFAULT_QUALIFICATION_PLAN_VERSION')
    identity(value['identity']); hex_digest(value['candidate_payload_digest']); parse_iso(value['created_at'])
    if not isinstance(value['selected'], list) or len(value['selected']) != len(expected_cells()):
        fail('DEFAULT_QUALIFICATION_MATRIX_INCOMPLETE')
    cells, scenarios, protocols = set(), set(), set()
    for row in value['selected']:
        exact(row, ROW_FIELDS, 'DEFAULT_QUALIFICATION_SELECTION_FIELDS')
        cell = (row['role'], row['phase'])
        if cell not in expected_cells() or cell in cells:
            fail('DEFAULT_QUALIFICATION_MATRIX_INCOMPLETE')
        cells.add(cell)
        for field, seen in (('scenario_ref', scenarios), ('protocol_ref', protocols)):
            digest = sha(row[field])
            if digest in seen:
                fail('DEFAULT_QUALIFICATION_SELECTION_DUPLICATE')
            seen.add(digest)
        if profile_spec(row['baseline_profile'])['generation'] != '5.6' or profile_spec(row['selected_profile'])['generation'] != '6':
            fail('DEFAULT_QUALIFICATION_PROFILE_GENERATION')
    sources = value['screening_sources']
    if not isinstance(sources, list) or not sources or len(sources) > 100 or len({ref(s) for s in sources}) != len(sources):
        fail('DEFAULT_QUALIFICATION_SCREENING_SOURCES')
    return value


def _document(pointer):
    exact(pointer, {'path', 'sha256'}, 'DEFAULT_QUALIFICATION_DOCUMENT')
    sha(pointer['sha256'])
    value, digest = read_document(safe_file(Path(pointer['path'])), maximum=8_388_608)
    if digest != pointer['sha256']:
        fail('DEFAULT_QUALIFICATION_DOCUMENT_CHANGED')
    return value


def _problems(study):
    from .qualification_study import study_plan
    study=study_plan(study) if study.get('schema_version')=='qualification-study/2' else study
    proof = study['independence']['cases']
    return ({('problem', p['source_problem_ref']) for p in proof}
            | {('cause', p['root_cause_ref']) for p in proof}
            | {('cluster', p['cluster_id']) for p in proof}
            | {('prompt', p['prompt_ref']) for plan in study['evaluations'] for p in plan['cases']})


def verify_plan(pointer, definition, *, now):
    value = validate_plan(_document(pointer))
    if value['identity'] != definition['identity'] or {r['scenario_ref'] for r in value['selected']} != set(definition['required_scenarios']):
        fail('DEFAULT_QUALIFICATION_SCOPE_CHANGED')
    manifest = _document(definition['installation']['manifest'])
    if manifest['payload_digest'] != value['candidate_payload_digest']:
        fail('DEFAULT_QUALIFICATION_PAYLOAD_CHANGED')
    evidence = _document(value['review_evidence'])
    verify_record(evidence, 'Default qualification plan')
    repo = Path(evidence.get('baseline', {}).get('repo_path', ''))
    if (evidence.get('status') != 'valid' or evidence.get('kind') != 'review'
            or evidence.get('source') != 'parent-reviewed-default-qualification-plan'
            or evidence.get('project_id') != value['identity']['project_id']
            or not repo.is_absolute() or stable_repo_fingerprint(str(repo)) != value['identity']['repo_fingerprint']
            or 'qualification-plan:' + scope(value) not in evidence.get('scope_refs', [])
            or parse_iso(evidence['recorded_at']) > parse_iso(value['created_at'])):
        fail('DEFAULT_QUALIFICATION_FREEZE_REVIEW_REQUIRED')
    selected = {(r['role'], r['phase']): r for r in value['selected']}
    covered, problems = set(), set()
    from . import budget_v5
    for source in value['screening_sources']:
        study, _, audit = load_study_sources(source, now=now)
        from .qualification_study import study_plan
        study=study_plan(study) if study.get('schema_version')=='qualification-study/2' else study
        if study['identity'] != value['identity'] or not audit['complete']:
            fail('DEFAULT_QUALIFICATION_SCREENING_IDENTITY')
        for segment in study['segments']:
            events = budget_v5._read_events(Path(segment['ledger_path']))
            if parse_iso(events[-1]['recorded_at']) > parse_iso(value['created_at']):
                fail('DEFAULT_QUALIFICATION_FREEZE_BEFORE_SCREENING_FINISHED')
        for plan in study['evaluations']:
            scenario = plan['scenario']; cell = (scenario['role'], scenario['phase'])
            if cell not in selected or cell in covered or ref(scenario) != selected[cell]['scenario_ref']:
                fail('DEFAULT_QUALIFICATION_SCREENING_SCOPE')
            if {c['profile_id'] for c in plan['costs']} != set(policy()['profiles']):
                fail('DEFAULT_QUALIFICATION_SCREENING_CATALOG_INCOMPLETE')
            covered.add(cell)
        problems.update(_problems(study))
    if covered != expected_cells():
        fail('DEFAULT_QUALIFICATION_SCREENING_MATRIX_INCOMPLETE')
    return {'plan': value, 'screening_problems': problems}


def verify_confirmation(checked, experiments, qualified):
    plan = checked['plan']; selected = {r['protocol_ref']: r for r in plan['selected']}
    seen, studies = set(), {}
    for experiment in experiments:
        protocol = experiment['protocol_ref']
        if protocol not in selected or protocol in seen:
            fail('DEFAULT_QUALIFICATION_CONFIRMATION_SCOPE')
        row = selected[protocol]; scenario = experiment['scenario']
        if (scenario['role'], scenario['phase']) != (row['role'], row['phase']) or ref(scenario) != row['scenario_ref']:
            fail('DEFAULT_QUALIFICATION_CONFIRMATION_SCOPE')
        if experiment['baseline_profile'] != row['baseline_profile'] or experiment['comparisons'] != [
                {'anchor': row['baseline_profile'], 'challenger': row['selected_profile']}]:
            fail('DEFAULT_QUALIFICATION_FROZEN_COMPARISON_CHANGED')
        if {s['profile_id'] for s in experiment['samples']} != {row['baseline_profile'], row['selected_profile']}:
            fail('DEFAULT_QUALIFICATION_FROZEN_COMPARISON_CHANGED')
        if row['selected_profile'] not in qualified.get(row['scenario_ref'], []):
            fail('DEFAULT_QUALIFICATION_SELECTED_PROFILE_NOT_QUALIFIED')
        source = experiment['qualification_source']['study']
        key = ref(source)
        if key not in studies:
            from .qualification_study import study_plan
            study = _document(source)
            if study.get('schema_version')=='qualification-study/2':study=study_plan(study)
            if study['identity'] != plan['identity'] or parse_iso(study['created_at']) < parse_iso(plan['created_at']):
                fail('DEFAULT_QUALIFICATION_CONFIRMATION_NOT_PREREGISTERED')
            if _problems(study) & checked['screening_problems']:
                fail('DEFAULT_QUALIFICATION_HOLDOUT_OVERLAP')
            if any(p['protocol_ref'] not in selected for p in study['evaluations']):
                fail('DEFAULT_QUALIFICATION_UNREGISTERED_CONFIRMATION')
            studies[key] = study
        seen.add(protocol)
    if seen != set(selected):
        fail('DEFAULT_QUALIFICATION_CONFIRMATION_MATRIX_INCOMPLETE')
