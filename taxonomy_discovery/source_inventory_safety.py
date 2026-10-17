"""Closed nested payload validation for the documented V1 export meanings.

The JSON schema is deliberately unchanged. Opaque schema objects are NOT an
extension mechanism: only native JD diagnostic fields are admissible here.
No heuristic can establish that arbitrary text in a valid JD text field is
actually a JD; trusted source references and fingerprints remain necessary.
"""
SCALAR = None


def closed(value, spec, path):
    if value is None:
        return
    if isinstance(spec, dict):
        if not isinstance(value, dict) or set(value)-set(spec):
            raise ValueError('Unsupported nested export fields at '+path)
        for key, item in value.items():
            closed(item, spec[key], path+'.'+key)
    elif isinstance(spec, list):
        if not isinstance(value, list):
            raise ValueError('Expected export array at '+path)
        for item in value:
            closed(item, spec[0], path+'[]')
    elif isinstance(value, (dict, list)) or not isinstance(value,(str,int,float,bool)):
        raise ValueError('Expected scalar export field at '+path)


def validate_safe_payload(export, jd_fields, parent_fields):
    grounding = dict.fromkeys(('kind','span_id','line_index','section','section_heading',
        'section_detection','section_reason','jd_structure_inference_version','sentence_index',
        'sentence_text','admission_method','list_item_count','list_structure'))
    grounding['list_item_span_ids']=[SCALAR]
    parent=dict.fromkeys(parent_fields);parent['grounding']=grounding
    requirement=dict.fromkeys(jd_fields)
    requirement['source_provenance']=[parent]
    requirement['sources']=[SCALAR]
    requirement['structured_match_required_terms']=[SCALAR]
    rule=dict.fromkeys(('rule_id','rule_version','kind','precedence','source_scope'))
    requirement['capability_recognition_rule']=rule
    structure=dict.fromkeys(('mode','source','parent_weight_preserved','scoring_children_created',
                             'parent_resolution_inferred'))
    registry=dict.fromkeys(('status','registry_version','technology_id','technology_label',
        'matched_alias','matched_term','capability_id','relationship_type','reason'))
    component=dict(requirement);component['registry_resolution']=registry
    structure['components']=[component]
    registry['native_component_resolution']=structure
    rejected=dict.fromkeys(('capability_id','phrase','product_context_guard','guard_contract_version',
        'raw_phrase_matched','guarded_phrase_matched','reason','scope_policy'))
    rejected['excluded_product_spans']=[SCALAR]
    diagnostics=dict.fromkeys(('normalized_requirement_text','taxonomy_version','capability_id',
        'capability_label','matched_phrase','matched_taxonomy_rule_type','contextual_phrase_rule',
        'product_context_guard','guard_contract_version','reason'))
    diagnostics.update(excluded_product_spans=[SCALAR],rejected_candidate_rules=[rejected],
        recognition_rule=rule,requirement_scope_proof={'functions':[SCALAR],'scope':SCALAR,
                                                     'provenance_required':SCALAR})
    identity=dict.fromkeys(('category','reason','identity_resolved','capability_id','knowledge_outcome'))
    identity.update(structure=structure,identities=[registry])
    for record in export['records']:
        closed(record['requirement'],requirement,'requirement')
        closed(record['native_structure'],structure,'native_structure')
        native=record['native_resolution']
        closed(native['taxonomy_diagnostics'],diagnostics,'taxonomy_diagnostics')
        closed(native['registry_diagnostics'],registry,'registry_diagnostics')
        closed(native['identity_scope'],identity,'identity_scope')
        receipt=record['evidence']['stored_receipt']
        closed(receipt,dict.fromkeys(('label','value','selected_row_count','meaning')),'stored_receipt')
        if receipt is not None and set(receipt)!= {'label','value','selected_row_count','meaning'}:
            raise ValueError('Incomplete historical receipt')
        if receipt is not None and (receipt['label'] not in ('none','weak','transferable','direct')
                or type(receipt['selected_row_count']) is not int or receipt['selected_row_count']<0
                or (receipt['value'] is not None and
                    (type(receipt['value']) not in (int,float) or not 0<=receipt['value']<=1))
                or receipt['meaning']!='STORED_RECEIPT_ONLY_NOT_CURRENT_EVIDENCE_EVALUATION'):
            raise ValueError('Invalid historical receipt scalars')
    version_keys=('match_version','match_contract_version','scoring_version','taxonomy_version',
        'capability_taxonomy_version','technology_registry_version','technology_registry_resolution_version',
        'capability_none_recovery_policy_version','credential_evidence_policy_version',
        'jd_structure_inference_version','non_requirement_filter_version','semantic_eligibility_version',
        'canonical_requirement_decomposition_version')
    closed(export['knowledge_identity']['versions'],dict.fromkeys(version_keys),'knowledge_versions')
    paths=('taxonomy/capability_taxonomy_v1.json','taxonomy/technology_registry_v1.json',
        'tailoring/production_requirement_resolver.py','tailoring/requirement_scope.py',
        'tailoring/capability_taxonomy.py','tailoring/phase6d6_structured_matching.py',
        'analysis_stability/stable_evidence_scoring.py')
    closed(export['knowledge_identity']['artifact_sha256'],dict.fromkeys(paths),'knowledge_artifacts')
    closed(export['counts'],dict.fromkeys(('unique_jobs','distinct_source_views','records',
                                          'duplicate_input_views')),'counts')
    for view in export['views']:
        closed(view['source_versions'],dict.fromkeys(version_keys),'source_versions')
