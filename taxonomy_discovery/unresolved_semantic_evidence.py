"""Report-only, source-grounded semantic/evidence investigation.

These bounded discovery profiles are investigation hypotheses, not taxonomy,
parser output, match labels, skill verification or a claim-generation API.
No production caller, persistence, ranking or numerical relevance model.
"""
from copy import deepcopy
import hashlib
import re

from taxonomy_discovery.unresolved_adjudication import fingerprint

VERSION = 'unresolved-semantic-evidence-investigation-v1'
RELEVANCE = ('DIRECT_RELEVANCE_CANDIDATE', 'TRANSFERABLE_RELEVANCE_CANDIDATE',
             'ADJACENT_RELEVANCE_CANDIDATE', 'NO_SUPPORTED_RELEVANCE', 'UNKNOWN')
SUPPORT = ('EXACT_CLAIM_SUPPORTED', 'BOUNDED_CLAIM_SUPPORTED',
           'INSUFFICIENT_EVIDENCE', 'CONTRADICTED_OR_UNSUPPORTED', 'UNKNOWN')
CASES = ((10, 146, 'req_ba405c092a55', 'database'),
         (15, 50, 'req_12004e0f666c', 'ros'),
         (16, 50, 'req_b01957201b40', 'alternatives'),
         (35, 45, 'req_076aaad11115', 'llm'))


def sha(text):
    return hashlib.sha256(text.encode('utf-8')).hexdigest()


def observation(value, spans, text, basis='EXPLICIT_FROZEN_REQUIREMENT'):
    """Require exact grounding; never treat a proposed interpretation as fact."""
    if not spans or any(not s or s not in text for s in spans):
        raise ValueError('Semantic observation lacks exact source grounding')
    return {'value': deepcopy(value), 'exact_source_spans': list(spans), 'basis': basis}


def semantics(case):
    """Curated four-case source annotations, deliberately not a generic parser."""
    number = case['case_number']
    text = case['exact_frozen_requirement']
    expected = next((c for c in CASES if c[0] == number), None)
    if expected is None or case['key'] != [expected[1], expected[2]]:
        raise ValueError('Exact investigation identity required')
    patterns = {
        10: ('broad relational and non-relational database competency',
             ['Relational and non-relational databases'], [],
             ['MS SQL', 'PostgreSQL', 'MongoDB'], []),
        15: ('ROS-based robotics maintenance', ['ROS-based robotics solutions'],
             ['maintain'], [], []),
        16: ('advantageous alternative qualifications', ['Advantageous qualifications'],
             ['demonstrating your work'], [], [
                 'a GitHub portfolio demonstrating your work',
                 'experience with AI or ML technologies',
                 'expertise in SLAM and Motion Planning',
                 'familiarity with CI or CD pipelines and simulation environments']),
        35: ('mixed advantageous familiarity and development', ['is advantageous'],
             ['application development', 'system integration'], [], [
                 'Generative AI tools', 'AI/LLM application development', 'APIs', 'system integration']),
    }
    if number not in patterns:
        raise ValueError('Outside the four-case investigation scope')
    umbrella, scope, activities, examples, alternatives = patterns[number]
    result = {
        'umbrella_competency': observation(umbrella, scope, text, 'BOUNDED_DIAGNOSTIC_INTERPRETATION'),
        'explicit_activities': [observation(s, [s], text) for s in activities],
        'non_mandatory_examples': [observation(s, [s], text,
            'BOUNDED_DIAGNOSTIC_INTERPRETATION') for s in examples],
        'alternative_groups': [observation(s, [s], text,
            'BOUNDED_DIAGNOSTIC_INTERPRETATION') for s in alternatives],
        'conjunctive_groups': [],
        'technology_candidates': deepcopy(case['technology_candidates']),
        'qualification_structure': deepcopy(case['structure']),
        'proficiency_level': {'value': None, 'basis': 'NOT_ESTABLISHED'},
        'qualification_importance': {'value': 'source qualification only; native importance recorded separately',
                                    'basis': 'BOUNDED_DIAGNOSTIC_INTERPRETATION'},
        'source_scope': {'frozen_text': text,
            'additional_verified_parents': deepcopy(case['additional_verified_parent_context']),
            'additional_verified_headings': deepcopy(case['additional_verified_headings']),
            'parent_context_basis': 'VERIFIED_PARENT_ONLY'},
        'parent_occurrence_ids': [p['parent_occurrence_id'] for p in case['additional_verified_parent_context']],
        'frozen_input_fingerprint': case['input_fingerprint'],
        'parent_context_fingerprint': case['review_context_fingerprint'],
        'missing_context': [],
        'uncertainty': ['Semantic groups are hypotheses, not approved children or human gold.',
                        'Candidate technologies are not full native resolutions.'],
        'scoring_children_created': False,
        'allocations_changed': False,
    }
    if number == 10:
        headings = case['additional_verified_headings']
        if headings:
            heading = next(h['text'] for h in headings if h['text'].strip() == 'Proficiency in:')
            result['proficiency_level'] = observation('proficiency', [heading], heading, 'VERIFIED_PARENT_ONLY')
        else:
            result['missing_context'].append('Verified proficiency heading unavailable')
        result['uncertainty'].append('Breadth of required relational/non-relational proficiency needs human review.')
    if number == 15:
        parents = case['additional_verified_parent_context']
        parent = next((p['raw_parent_text'] for p in parents if 'develop and maintain' in p['raw_parent_text']), None)
        if parent:
            result['explicit_activities'].append(observation('develop', ['develop'], parent, 'VERIFIED_PARENT_ONLY'))
    if number == 16:
        result['conjunctive_groups'] = [observation(s, [s], text,
            'BOUNDED_DIAGNOSTIC_INTERPRETATION') for s in
            ['SLAM and Motion Planning', 'pipelines and simulation environments']]
    for term in ('Familiarity', 'familiarity', 'expertise'):
        if term in text:
            result.setdefault('proficiency_observations', []).append(observation(term, [term], text))
    return result


def discover(profile, requirement_id, records, *, parent_needed=False):
    """Inclusive bounded surface discovery with separate claim ceilings.

    An implementation verb is an observation in a saved assertion, not an
    independently verified achievement. No cross-record proof is aggregated.
    Raw private text stays in memory; report carries hashes, locations and
    technical categories only. 'Exact' full requirement proof is never inferred.
    """
    if profile not in ('database', 'postgres', 'ros', 'alternatives', 'llm',
                        'genai', 'kubernetes', 'api', 'cloud'):
        raise ValueError('Unsupported investigation profile')
    output = []
    for record in records:
        if not record.get('evidence_id') or not record.get('source') or not record.get('text'):
            raise ValueError('Evidence requires native ID, exact location and source text')
        text = record['text']
        low = text.lower()
        facts = []
        relevance = 'NO_SUPPORTED_RELEVANCE'
        action = bool(re.search(r'\b(built|implemented|integrated|created|developed|queried|maintained|set up)\b', low))
        tentative = bool(re.search(r'\b(planned|planning|proposed|discussed|not implemented|no experience|without)\b', low))
        relational = bool(re.search(r'\b(sql|postgresql|postgrest|sql server|sqlite)\b', low))
        nonrelational = bool(re.search(r'\b(mongodb|elasticsearch|chromadb)\b', low))
        llm = bool(re.search(r'\b(llm|rag|openai|litellm|chatgpt)\b', low))
        if profile in ('database', 'postgres') and (relational or nonrelational):
            facts = [x for x, hit in [('relational database surface', relational), ('non-relational storage surface', nonrelational)] if hit]
            relevance = 'DIRECT_RELEVANCE_CANDIDATE' if action else 'ADJACENT_RELEVANCE_CANDIDATE'
            if profile == 'postgres' and not re.search(r'\bpostgresql\b', low):
                relevance = 'TRANSFERABLE_RELEVANCE_CANDIDATE' if relational and action else 'ADJACENT_RELEVANCE_CANDIDATE'
        elif profile == 'ros':
            if re.search(r'\bros(?:2)?\b', low):
                facts = ['ROS surface']
                relevance = 'DIRECT_RELEVANCE_CANDIDATE' if action else 'ADJACENT_RELEVANCE_CANDIDATE'
            elif re.search(r'(?<!\w)(robotics|robot|middleware|python|c\+\+)(?!\w)', low):
                facts = ['related robotics/language/middleware surface; not ROS proof']
                relevance = 'ADJACENT_RELEVANCE_CANDIDATE'
        elif profile in ('llm', 'genai', 'alternatives'):
            if llm or (profile == 'alternatives' and re.search(r'\b(github|ci|cd|slam|motion planning|simulation|machine learning)\b', low)):
                facts = ['AI/tooling/alternative-branch surface']
                relevance = 'DIRECT_RELEVANCE_CANDIDATE' if action else 'ADJACENT_RELEVANCE_CANDIDATE'
            elif profile == 'llm' and re.search(r'\b(api|apis|postgrest|integration)\b', low):
                facts = ['API/integration alternative surface; not LLM proof']
                relevance = 'DIRECT_RELEVANCE_CANDIDATE' if action else 'ADJACENT_RELEVANCE_CANDIDATE'
        elif profile == 'kubernetes' and re.search(r'\b(docker|ci/cd|kubernetes)\b', low):
            facts = ['deployment surface']
            relevance = ('DIRECT_RELEVANCE_CANDIDATE' if 'kubernetes' in low and action
                         else 'ADJACENT_RELEVANCE_CANDIDATE')
        elif profile == 'api' and re.search(r'\b(node\.js|api|apis|postgrest)\b', low):
            facts = ['runtime/API surface']
            relevance = ('DIRECT_RELEVANCE_CANDIDATE' if action and re.search(r'\b(api|apis|postgrest)\b', low)
                         else 'ADJACENT_RELEVANCE_CANDIDATE')
        elif profile == 'cloud' and re.search(r'\b(aws|azure|gcp)\b', low):
            facts = ['cloud platform surface; architecture not established']
            relevance = 'ADJACENT_RELEVANCE_CANDIDATE'
        support = ('BOUNDED_CLAIM_SUPPORTED' if action and facts else 'INSUFFICIENT_EVIDENCE')
        if tentative:
            relevance = 'UNKNOWN'
            support = 'CONTRADICTED_OR_UNSUPPORTED'
        if not facts and not tentative:
            continue
        output.append({
            'requirement_id': requirement_id, 'evidence_id': record['evidence_id'],
            'source_location': record['source'], 'source_text_sha256': sha(text),
            'source_assertion_status': 'RECORDED_ASSERTION_NOT_INDEPENDENT_IMPLEMENTATION_VERIFICATION',
            'relevance': relevance, 'claim_support': support,
            'requested_scope': profile, 'observed_technical_categories': facts,
            'technical_source_tokens': sorted(set(re.findall(
                r'(?<!\w)(?:postgresql|postgrest|sql server|sql|sqlite|mongodb|elasticsearch|chromadb|ros2?|robotics|python|c\+\+|llm|rag|openai|litellm|chatgpt|github|ci/cd|ci|cd|slam|motion planning|simulation|node\.js|api|apis|docker|kubernetes|aws|azure|gcp)(?!\w)', low))),
            'action_source_spans': re.findall(r'\b(?:built|implemented|integrated|created|developed|queried|maintained|set up)\b', text, re.I),
            'demonstrated_activity': 'implementation verb in this record' if action else 'listing/familiarity only',
            'supports': 'Only the bounded saved source assertion; human review before claim use.',
            'does_not_prove': 'Full proficiency, every alternative, mandatory examples, unmentioned products, architecture, schema design, security, model training, SLAM/navigation or approved capability mappings.',
            'parent_context_needed': parent_needed,
            'native_discovery': 'not established by this surface discovery; compare native trace separately',
            'influences_scoring': False, 'claim_authorized': False,
        })
    return sorted(output, key=lambda r: (r['source_location'], r['evidence_id']))


def validate_connections(connections, records, requirement_id):
    index = {(r['evidence_id'], r['source']): r for r in records}
    for c in connections:
        row = index.get((c['evidence_id'], c['source_location']))
        if row is None or c['source_text_sha256'] != sha(row['text']):
            raise ValueError('Untraceable evidence connection')
        if c['requirement_id'] != requirement_id or c['relevance'] not in RELEVANCE or c['claim_support'] not in SUPPORT:
            raise ValueError('Invalid diagnostic identity/state')
        if c['claim_authorized'] or c['influences_scoring'] or c['claim_support'] == 'EXACT_CLAIM_SUPPORTED':
            raise ValueError('Report-only discovery cannot authorize claims or full proficiency')
    return True
