"""中文：仅处理综合复审语义，不授予派发、消耗或资格权限。

English: Integrated review semantics only; no dispatch, spending or qualification authority.
"""
from __future__ import annotations

import copy
from .context_semantics_v2 import expand_semantics
from .common import canonical_json
from .routing_contract import exact, fail, ref, sha

VERSION = 'review-vector/1'
DIMENSIONS = ('functional_business', 'compatibility_regression', 'security_access',
              'performance_resources', 'data_contract', 'state_concurrency', 'test_delivery')
APPLICABILITY = {'applicable', 'not-applicable', 'unknown'}
ROW_FIELDS = {'dimension', 'status', 'findings', 'checked_scope', 'unverified_items', 'summary'}


def validate_scope(value):
    """中文：范围由控制器拥有；引用表示结构来源，本身不是事实证明。
    
    English: Controller-owned scope. References are structural provenance, not proof by themselves.
    """
    exact(value, set(DIMENSIONS), 'VECTOR_SCOPE_DIMENSIONS')
    for row in value.values():
        exact(row, {'state', 'evidence_refs'}, 'VECTOR_SCOPE_FIELDS')
        if not isinstance(row['state'], str) or row['state'] not in APPLICABILITY:
            fail('VECTOR_SCOPE_STATE')
        refs = row['evidence_refs']
        if not isinstance(refs, list) or len(refs) > 32:
            fail('VECTOR_SCOPE_REFS')
        for source in refs:
            sha(source)
        if len(refs) != len(set(refs)):
            fail('VECTOR_SCOPE_REFS')
        if row['state'] != 'unknown' and not refs:
            fail('VECTOR_SCOPE_EVIDENCE_REQUIRED')
    return copy.deepcopy(value)


def _texts(value, code, *, limit=256):
    if not isinstance(value, list) or len(value) > limit or any(
            not isinstance(item, str) or not item.strip() or len(item) > 4096 for item in value):
        fail(code)


def validate_vector(payload, scope):
    """中文：投影前验证全部维度，不能让模型决定适用性。
    
    English: Validate all dimensions before projection. The model cannot decide applicability.
    """
    scope = validate_scope(scope)
    exact(payload, {'schema_version', 'dimensions', 'summary'}, 'VECTOR_FIELDS')
    if payload['schema_version'] != VERSION:
        fail('VECTOR_VERSION')
    if len(canonical_json(payload).encode('utf-8')) > 1048576:
        fail('VECTOR_RESPONSE_SIZE')
    rows = payload['dimensions']
    if not isinstance(rows, list) or len(rows) != len(DIMENSIONS):
        fail('VECTOR_DIMENSION_COVERAGE')
    if not isinstance(payload['summary'], str) or not payload['summary'].strip() or len(payload['summary']) > 16384:
        fail('VECTOR_SUMMARY')
    seen, finding_ids, normalized = set(), set(), []
    for row in rows:
        exact(row, ROW_FIELDS, 'VECTOR_ROW_FIELDS')
        dimension = row['dimension']
        if not isinstance(dimension, str) or dimension not in DIMENSIONS or dimension in seen:
            fail('VECTOR_DIMENSION_COVERAGE')
        seen.add(dimension)
        state = scope[dimension]['state']
        _texts(row['checked_scope'], 'VECTOR_CHECKED_SCOPE')
        _texts(row['unverified_items'], 'VECTOR_UNVERIFIED_SCOPE')
        if not isinstance(row['summary'], str) or not row['summary'].strip() or len(row['summary']) > 16384:
            fail('VECTOR_ROW_SUMMARY')
        if state == 'not-applicable':
            if row['status'] != 'not-applicable' or row['findings'] or row['checked_scope'] or row['unverified_items']:
                fail('VECTOR_NOT_APPLICABLE_CONFLICT')
            normalized.append(copy.deepcopy(row))
            continue
        if not isinstance(row['status'], str):
            fail('VECTOR_ROW_STATUS')
        if row['status'] == 'not-applicable' or (state == 'unknown' and row['status'] != 'incomplete'):
            fail('VECTOR_APPLICABILITY_FORGERY')
        if row['unverified_items'] and row['status'] != 'incomplete':
            fail('VECTOR_UNVERIFIED_CANNOT_COMPLETE')
        if row['status'] != 'incomplete' and not row['checked_scope']:
            fail('VECTOR_COMPLETED_SCOPE_REQUIRED')
        semantic = expand_semantics({key: copy.deepcopy(row[key]) for key in ROW_FIELDS - {'dimension'}})
        for finding in semantic['findings']:
            if finding['dimension'] != dimension or finding['id'] in finding_ids:
                fail('VECTOR_FINDING_IDENTITY')
            finding_ids.add(finding['id'])
        if len(finding_ids) > 64:
            fail('VECTOR_FINDING_LIMIT')
        normalized.append({'dimension': dimension, **semantic})
    normalized.sort(key=lambda row: DIMENSIONS.index(row['dimension']))
    applicable = [row for row in normalized if scope[row['dimension']]['state'] != 'not-applicable']
    statuses = {row['status'] for row in applicable}
    overall = next((status for status in ('incomplete', 'blocking', 'nonblocking', 'pass') if status in statuses), 'incomplete')
    return {'schema_version': 'validated-review-vector/1', 'model_payload_ref': ref(payload),
            'scope_ref': ref(scope), 'dimensions': normalized, 'summary': payload['summary'],
            'overall_status': overall,
            'has_blocking_findings': any(finding['blocking'] for row in applicable for finding in row['findings']),
            'qualification_granted': False}


def project_dimensions(payload, scope):
    """中文：展示与评分视图共享同一来源，不冒充原生回执或旧结果。
    
    English: Display/scoring views share one source. These are not native receipts or old results.
    """
    value = validate_vector(payload, scope)
    source_ref = ref(value)
    return [{'schema_version': 'review-dimension-view/1', 'vector_ref': source_ref,
             'model_payload_ref': value['model_payload_ref'], 'scope_ref': value['scope_ref'],
             'semantic': row, 'independent_model_call': False, 'qualification_granted': False}
            for row in value['dimensions']]


def audit_matrix(cases, *, min_clean=252, min_defect=100, min_critical=20):
    """中文：按独立问题簇报告适用覆盖，不推断准入或质量。
    
    English: Report applicable coverage by independent cluster, never infer admission or quality.
    """
    if not isinstance(cases, list) or len(cases) > 10000:
        fail('VECTOR_MATRIX_LIMIT')
    for threshold in (min_clean, min_defect, min_critical):
        if type(threshold) is not int or threshold < 1:
            fail('VECTOR_MATRIX_THRESHOLD')
    records, problem_clusters, cause_clusters = set(), {}, {}
    buckets = {(phase, dimension): {} for phase in ('pre', 'post', 'repair') for dimension in DIMENSIONS}
    unknown = {key: set() for key in buckets}
    for case in cases:
        exact(case, {'case_ref', 'cluster_id', 'source_problem_ref', 'root_cause_ref', 'phase', 'scope', 'labels'},
              'VECTOR_MATRIX_CASE_FIELDS')
        sha(case['case_ref']); sha(case['source_problem_ref']); sha(case['root_cause_ref'])
        if case['case_ref'] in records or not isinstance(case['phase'], str) or case['phase'] not in {'pre', 'post', 'repair'}:
            fail('VECTOR_MATRIX_CASE_IDENTITY')
        if not isinstance(case['cluster_id'], str) or not case['cluster_id'] or len(case['cluster_id']) > 160:
            fail('VECTOR_MATRIX_CLUSTER')
        records.add(case['case_ref'])
        for source, mapping in (('source_problem_ref', problem_clusters), ('root_cause_ref', cause_clusters)):
            if mapping.setdefault(case[source], case['cluster_id']) != case['cluster_id']:
                fail('VECTOR_MATRIX_CLUSTER_ALIAS')
        scope = validate_scope(case['scope'])
        exact(case['labels'], set(DIMENSIONS), 'VECTOR_MATRIX_LABEL_DIMENSIONS')
        for dimension in DIMENSIONS:
            label = case['labels'][dimension]
            exact(label, {'clean', 'critical'}, 'VECTOR_MATRIX_LABEL_FIELDS')
            key = (case['phase'], dimension)
            if scope[dimension]['state'] != 'applicable':
                if label != {'clean': None, 'critical': None}:
                    fail('VECTOR_MATRIX_INAPPLICABLE_LABEL')
                if scope[dimension]['state'] == 'unknown':
                    unknown[key].add(case['cluster_id'])
                continue
            if type(label['clean']) is not bool or type(label['critical']) is not bool:
                fail('VECTOR_MATRIX_LABEL_BOOLEAN')
            prior = buckets[key].get(case['cluster_id'])
            if prior is not None and prior != label:
                fail('VECTOR_MATRIX_VARIANT_SELECTION_REQUIRED')
            buckets[key][case['cluster_id']] = copy.deepcopy(label)
    result = []
    for (phase, dimension), rows in buckets.items():
        clean = sum(row['clean'] for row in rows.values())
        defect = len(rows) - clean
        critical = sum(row['critical'] for row in rows.values())
        gaps = {'clean': max(0, min_clean-clean), 'defect': max(0, min_defect-defect),
                'critical': max(0, min_critical-critical)}
        result.append({'phase': phase, 'dimension': dimension, 'independent_clusters': len(rows),
                       'clean': clean, 'defect': defect, 'critical': critical,
                       'unknown_clusters': len(unknown[(phase, dimension)]), 'gaps': gaps})
    return {'schema_version': 'case-applicability-audit/1', 'matrix_ref': ref(cases), 'coverage': result,
            'coverage_complete': all(not any(row['gaps'].values()) and not row['unknown_clusters'] for row in result),
            'formal_admission_verified': False, 'qualification_granted': False,
            'native_model_calls_created': 0}
