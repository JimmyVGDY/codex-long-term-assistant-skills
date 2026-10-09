"""中文：报告完整研究的尝试和费用，不按幸存样本宣称资格。

English: Campaign-wide attempts and fees, never a survivor-only qualification claim.
"""
from pathlib import Path
from .routing_contract import exact,fail,ref,sha,read_document,add_vectors,fits,assert_current_window
from .routing_context_contract import safe_file
from .research_documents import read_manifest
def audit_campaign(manifest,trial_manifest,*,now):
    campaign,plans,envelopes,bindings=read_manifest(manifest)
    assert_current_window(campaign,now)
    exact(trial_manifest,{'schema_version','manifest_ref','studies'},'RESEARCH_TRIAL_MANIFEST_FIELDS')
    if trial_manifest['schema_version']!='research-campaign-trials/1' or trial_manifest['manifest_ref']!=ref(manifest):fail('RESEARCH_TRIAL_MANIFEST_CHANGED')
    rows=trial_manifest['studies']
    if not isinstance(rows,list) or len(rows)!=len(envelopes):fail('RESEARCH_TRIAL_STUDY_COVERAGE')
    from .qualification_study import audit_study
    reports=[];sources=[];seen=set()
    for envelope,row in zip(envelopes,rows):
        exact(row,{'study_ref','trials'},'RESEARCH_TRIAL_STUDY_FIELDS')
        if row['study_ref']!=ref(envelope) or row['study_ref'] in seen:fail('RESEARCH_TRIAL_STUDY_ORDER')
        seen.add(row['study_ref']);pointer=exact(row['trials'],{'path','sha256'},'RESEARCH_TRIAL_FILE_FIELDS');sha(pointer['sha256'])
        value,digest=read_document(safe_file(Path(pointer['path'])),maximum=8388608)
        if digest!=pointer['sha256']:fail('RESEARCH_TRIAL_FILE_CHANGED')
        trials=exact(value,{'trials'},'RESEARCH_TRIAL_LIST_FIELDS')['trials']
        reports.append(audit_study(envelope,trials,now=now,campaign_manifest=manifest));sources.append(trials)
    resources=add_vectors(*(r['resources'] for r in reports))
    if not fits(resources,campaign['capacity']):fail('RESEARCH_ACTUAL_RESOURCES_OVERDRAWN')
    count_keys=set(reports[0]['counts'])
    if any(set(r['counts'])!=count_keys for r in reports):fail('RESEARCH_AUDIT_COUNT_VERSION_MIXED')
    counts={key:sum(r['counts'][key] for r in reports) for key in count_keys}
    report={'schema_version':'research-campaign-audit/1','campaign_ref':ref(campaign),'manifest_ref':ref(manifest),'trial_manifest_ref':ref(trial_manifest),'identity':campaign['identity'],'comparison_scope_ref':ref(campaign['comparison_scope']),'complete':all(r['complete'] for r in reports),'counts':counts,'resources':resources,'billing':'UNKNOWN','source_study_audits':[{ 'study_ref':ref(e),'audit_ref':ref(a),'ledger_heads':a['source_ledger_heads']} for e,a in zip(envelopes,reports)],'qualification_granted':False,'global_simultaneous_ci_claim':False}
    return report,reports,sources
