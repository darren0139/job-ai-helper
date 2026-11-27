"""Bounded technology proficiency policy, independent of candidate or employer.

No JD decomposition, weight changes, inferred skill unions, or model calls.
A named alternative must itself be supported; one visible row proves at most
one alternative. Generic database proficiency is not DBA expertise.
"""
from __future__ import annotations
import re
from copy import deepcopy

VERSION = 'v312b219b-technology-database-v1'
# Small, explicit supported vocabulary. Unknown alternatives abstain, not guess.
FRONT = {'react': ('react js','react.js','reactjs','react'), 'angular': ('angularjs','angular.js','angular'), 'html5': ('html5','html 5'), 'vue': ('vue.js','vuejs','vue'), 'svelte': ('svelte',)}
BACK = {'java': ('java',), 'python': ('python',), 'dotnet': ('.net','dotnet'), 'php': ('php',), 'csharp': ('c#','c sharp'), 'nodejs': ('node.js','nodejs','node js'), 'ruby': ('ruby',), 'go': ('golang','go'), 'javascript': ('javascript',), 'typescript': ('typescript',)}
DB = {'sql': ('sql',), 'postgresql': ('postgresql','postgres'), 'sqlite': ('sqlite','sqlite3'), 'mysql': ('mysql',), 'mariadb': ('mariadb',), 'sqlserver': ('sql server','mssql'), 'oracle': ('oracle database','oracle db'), 'mongodb': ('mongodb',), 'redis': ('redis',), 'dynamodb': ('dynamodb',)}
ALL = {**FRONT, **BACK}
LABELS = {'none': (0.0,0), 'weak': (0.20,2), 'transferable': (0.55,3), 'direct': (1.0,5)}

def norm(s):
    return ' '.join(str(s or '').casefold().replace('–','-').replace('—','-').split())

def has(s, alias):
    return bool(re.search(r'(?<![\w.+#])'+re.escape(alias)+r'(?![\w+#])',s))

def tokens(s, choices):
    return [k for k, aliases in choices.items() if any(has(s,a) for a in aliases)]

def exact_name(s, choices):
    s=norm(s)
    return next((k for k,aliases in choices.items() if s in aliases),None)

def requirement(text):
    s=norm(text).rstrip('.')
    s=re.sub(r'\s+(?:will be an added advantage|is an added advantage|is preferred|preferred|is a plus)$','',s)
    # Restrict this release to explicit minimum-one alternative groups and
    # generic database proficiency, not broader experience or administration.
    if re.fullmatch(r'(?:proficiency|practical experience|hands-on experience|experience) (?:in|with) (?:relational )?databases?',s):
        return ('database', tuple(DB) if 'relational' not in s else tuple(k for k in DB if k in {'sql','postgresql','sqlite','mysql','mariadb','sqlserver','oracle'}))
    m=re.fullmatch(r'(?:proficiency|experience|hands-on experience) (?:in|with) (?:at least one|one or more|one) (?:of (?:the following )?)?(front[- ]?end frameworks?|back[- ]?end (?:programming )?languages?)\s*\(([^()]*)\)',s)
    if m:
        domain='frontend' if m[1].startswith('front') else 'backend'
        pool=FRONT if domain=='frontend' else BACK
        parts=re.split(r'\s*(?:/|,\s*(?:or\s+)?|\bor\b)\s*',m[2])
    else:
        m=re.fullmatch(r'(?:proficiency|experience|hands-on experience) (?:in|with) ([^():]+)',s)
        if not m or ' or ' not in m[1]:return None
        parts=re.split(r'\s+or\s+',m[1]);pool=ALL;domain='language_or_framework'
    found=[exact_name(x,pool) for x in parts]
    if len(found)<2 or any(x is None for x in found) or len(set(found))!=len(found):return None
    return (domain,tuple(found))

# Reject mixed ownership and uncertain/negative clauses rather than taking an
# attractive technology mention out of context. Conservative by design.
BLOCK=re.compile(r"\b(?:no|not|never|without|planned|planning|intend(?:ed)?|would|will|learning|learned|familiaris\w*|observed|shadowed|third[- ]party|vendor[- ]provided|provided by|built by|developed by|implemented by|maintained by|others|other team|team (?:built|developed|implemented)|tutorial|coursework|hypothetical|example only)\b|\b(?:didn't|haven't|hasn't|wasn't|weren't)\b")
ACTION=re.compile(r'^(?:(?:independently|jointly|successfully) )?(?:built|developed|implemented|engineered|created|designed|maintained|enhanced|wrote|refactored|configured|integrated|set up|connected|used|applied|optimized|optimised|managed|migrated|queried|deployed)\b')
FRONT_ACTIVITY=re.compile(r'\b(?:front[- ]?end|ui|user interface|user-facing|components?|web (?:app|application|page)|full[- ]?stack|ticket-management|dashboard)\b')
BACK_ACTIVITY=re.compile(r'\b(?:back[- ]?end|rest api endpoints?|api endpoints?|server[- ]side|web services?|service endpoints?|http endpoints?|request handlers?)\b')
DB_ACTIVITY=re.compile(r'\b(?:schema|tables?|queries|query|indexes|indices|migrations?|transactions?|persistence|persistent|saved application sessions|database operations|data access|stored procedures?|row[- ]level security|crud|database-backed|sqlite-backed|postgresql-backed)\b')
STRONG=re.compile(r'^(?:(?:independently|jointly|successfully) )?(?:built|developed|implemented|engineered|created|designed|maintained|enhanced|wrote|refactored|optimized|optimised|migrated|queried|applied)\b')
CONSUME=re.compile(r'\b(?:consum\w*|calling|called|client (?:of|for|to)|connect(?:ed|ing)? to|integrat\w* with|access(?:ed|ing)? (?:an? |the )?(?:existing|external))\b')

def visible(row, raw):
    if not raw:return True # profile-only callers still use their own supplied evidence
    s=norm(row.get('text'));lines=[norm(x).lstrip('-•* ') for x in raw.splitlines()]
    if row.get('section')=='skills':
        return any(has(line,s) and not BLOCK.search(line) and (line==s or not ACTION.search(line)) for line in lines)
    return any(s and s in line and not BLOCK.search(line) for line in lines)

def evaluate(spec,row,raw=''):
    domain,allowed=spec;s=norm(row.get('text')).lstrip('-•* ');section=row.get('section');source=str(row.get('source',''))
    if not s or BLOCK.search(s) or not visible(row,raw):return None
    if section not in {'skills','projects','experience','raw_text'}:return None
    pool=DB if domain=='database' else ALL
    named=[k for k in tokens(s,pool) if k in allowed]
    if not named:return None
    if section=='skills' or (section=='raw_text' and exact_name(s,pool)):
        k=exact_name(s,pool)
        if k in allowed:return ('weak' if domain=='database' else 'transferable',k,'explicit_skill_only')
        return None
    if section in {'projects','experience'} and '.bullets[' not in source:return None
    if not ACTION.search(s):return None
    # Keep evidence within a single action clause. Multiple unrelated clauses
    # are not allowed to manufacture proficiency through token union.
    if re.search(r';|\b(?:but|whereas|while|however)\b',s):return None
    authored_object=re.split(r'\b(?:using|with|via|through|against)\b',s,maxsplit=1)[0]
    for k in named:
        kind=domain if domain!='language_or_framework' else ('frontend' if k in FRONT else 'backend')
        bound = any(re.search(r'\b(?:using|with|in|via|on) '+re.escape(a)+r'(?![\w+#])',s) or re.search(r'^(?:independently |jointly |successfully )?\w+ '+re.escape(a)+r'(?![\w+#])',s) for a in pool[k])
        if kind=='frontend' and bound and FRONT_ACTIVITY.search(authored_object) and not CONSUME.search(s):
            return ('direct' if STRONG.search(s) else 'transferable',k,'demonstrated_frontend_implementation')
        if kind=='backend' and bound and BACK_ACTIVITY.search(authored_object) and not CONSUME.search(s):
            return ('direct' if STRONG.search(s) else 'transferable',k,'demonstrated_backend_implementation')
        if domain=='language_or_framework' and k in BACK and bound and not CONSUME.search(s) and re.search(r'\b(?:scripts?|programs?|applications?|data[- ]processing|datasets?|automation|algorithms?|libraries|modules?|pipelines?)\b',s):
            return ('direct' if STRONG.search(s) else 'transferable',k,'demonstrated_general_programming')
        if kind=='database':
            # Explicit concrete persistence/data operations, not a stack list.
            if DB_ACTIVITY.search(s) and re.search(r'\b(?:schema|tables?|queries|query|indexes|indices|migrations?|transactions?|persistence|persistent|saved application sessions|database operations|data access|stored procedures?|row[- ]level security|crud)\b',s) and STRONG.search(s) and not CONSUME.search(s):
                return ('direct',k,'demonstrated_database_operation')
            if DB_ACTIVITY.search(s) or re.search(r'\b(?:database|data store|storage|backend|service)\b',s):
                return ('transferable',k,'demonstrated_database_integration')
    return None

def apply_policy(rows,evidence_index,raw_resume_text=''):
    output=deepcopy(rows);audit=[]
    for row in output:
        if row.get('score_eligible') is False or row.get('evidence_eligible') is False or row.get('explicit_only_requirement') or row.get('credential_policy'):continue
        # Use the full canonical text. Never infer an alternative from a clipped focus.
        spec=requirement(row.get('text'))
        if spec is None:continue
        candidates=[]
        for ev in evidence_index:
            hit=evaluate(spec,ev,raw_resume_text)
            if hit:candidates.append((hit,ev))
        candidates.sort(key=lambda x:(-LABELS[x[0][0]][0],str(x[1].get('evidence_id','')),str(x[1].get('source',''))))
        before=row.get('match_label','none')
        if candidates:
            (label,tech,reason),ev=candidates[0]
            evidence=[{**deepcopy(ev),'reason':'One visible evidence row supports the bounded technology requirement.','capability_evidence_reason':reason}]
        else:
            label,tech,reason,evidence='none',None,'no_eligible_technology_evidence',[]
        value,strength=LABELS[label]
        row.update(match_label=label,match_value=value,evidence_strength=strength,evidence=evidence,match_source='v312b219b_technology_database' if evidence else 'missing')
        # Earlier recovery metadata is historical for this targeted decision.
        for k in ('capability_none_recovery','capability_taxonomy_cap_reason','capability_evidence_reselection'):
            row.pop(k,None)
        receipt={'policy_version':VERSION,'domain':spec[0],'mode':'any' if spec[0]!='database' else 'generic_database','accepted_technologies':list(spec[1]),'matched_technology':tech,'reason':reason,'previous_label':before,'label':label,'selected_evidence_id':evidence[0].get('evidence_id') if evidence else None,'combined_evidence_rows':False}
        row['v312b219b_policy_audit']=receipt;audit.append({'requirement_id':row.get('requirement_id'),**receipt})
    return output,audit
