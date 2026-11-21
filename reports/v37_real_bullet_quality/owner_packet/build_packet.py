"""Offline review packet from immutable audit JSON; no application imports or calls."""
import argparse
import csv
import hashlib
import html
import json
from collections import Counter, defaultdict
from pathlib import Path

OPTIONS = ('Base better', 'Library better', 'Equivalent', 'Complementary', 'Insufficient evidence')
PREDICTIONS = {
    'Base has stronger supported JD relevance.': 'Base better',
    'Library has stronger supported JD relevance.': 'Library better',
    'Comparable relevance / tie.': 'Equivalent',
    'Different complementary evidence — no clear replacement winner.': 'Complementary',
    'Insufficient verified evidence to determine a preference.': 'Insufficient evidence',
}
# Reviewer prompts based on distinct literal activities, never expected labels.
PROMPTS = {
    'R01': 'Specific progression UI versus a broader team/release introduction.',
    'R02': 'Specific progression UI versus a broader team/release introduction.',
    'R03': 'Specific progression UI versus a broader team/release introduction.',
    'R06': 'Testing/CI versus cover-letter generation: distinct activities.',
    'R11': 'GPS Android frontend leadership versus image attachments/Coil.',
    'R13': 'Build integration versus image attachments/Coil.',
    'R17': 'User workflows versus backend access/security detail.',
    'R18': 'Testing/CI versus a broad application introduction.',
    'R19': 'Corpus audit/CI versus cover-letter generation.',
    'R20': 'Asset manager implementation versus cross-team engine integration.',
}


def digest(value):
    return hashlib.sha256(value.encode('utf-8')).hexdigest()


def pair_id(case):
    # Exact wording, roles preserved. JD contexts remain distinct rows.
    return 'P-' + digest(json.dumps([case['base']['bullet'], case['library']['bullet']], ensure_ascii=False))[:12]


def malformed_links(case):
    return sorted({x for role in ('base', 'library') for x in case[role].get('saved_jd_ids', [])
                   if not isinstance(x, str) or not x.startswith('req_')})


def reasons(case):
    if not case['diagnostic']['outcome'].startswith('Insufficient'):
        return []
    native = any(case[r].get('native_requirement_ids') for r in ('base', 'library'))
    if native:
        return ['Diagnostic rule restriction despite a recorded native citation']
    if case['source_receipt'].get('verification_row') is None:
        return ['Saved document authority unavailable']
    return ['Document-bound observation has no attributed citation for either wording']


def review_rows(cases):
    groups = defaultdict(list)
    for c in cases:
        groups[pair_id(c)].append(c['case_id'])
    rows = []
    for c in cases:
        reqs = '\n'.join(f"[{q['importance']}] {q['text']} ({q['id']})" for q in c['jd_requirements'])
        rows.append(dict(case_id=c['case_id'], application=c['application'], project=c['project'],
            jd_sha256=c['source_receipt']['jd_sha256'], wording_pair_id=pair_id(c),
            repeated_in_cases=', '.join(groups[pair_id(c)]),
            base_wording=c['base']['bullet'], library_wording=c['library']['bullet'],
            base_provenance='; '.join(s for s in c['base']['sources'] if s != 'Current final'), library_provenance='; '.join(s for s in c['library']['sources'] if s != 'Current final'),
            recorded_requirement_links=reqs or 'No linked requirement recorded; see full original JD in review.html.',
            base_citations=citations(c['base']), library_citations=citations(c['library']),
            base_lexical_cues=', '.join(c['base'].get('jd_wide_term_cues', [])),
            library_lexical_cues=', '.join(c['library'].get('jd_wide_term_cues', [])),
            native_impact='Unmeasured for this bullet pair', original_jd=c['jd_text'],
            substitution_review_prompt=PROMPTS.get(c['case_id'], 'Same project does not establish substitution equivalence.'),
            evidence_report=f"review.html#{c['case_id']}",
            allowed_outcomes=' | '.join(OPTIONS), owner_outcome='', reviewer_notes=''))
    return rows


def citations(row):
    return '\n'.join(f"[{link['importance']}] {link['text']}: {native.get('excerpt', '')} (grade={native.get('match_label')}, strength={native.get('strength')}; recorded native observation, not independent attestation)"
        for link in row.get('jd_links', []) for native in link.get('native_evidence', {}).values()) or 'Unavailable; not disproven'


def compare_labels(cases, label_path):
    expected = {r['case_id']: r for r in review_rows(cases)}
    with label_path.open(encoding='utf-8-sig', newline='') as f:
        labels = list(csv.DictReader(f))
    seen = set()
    records = []
    by_id = {c['case_id']: c for c in cases}
    for label in labels:
        cid = label.get('case_id')
        if cid not in expected or cid in seen:
            raise ValueError('Unknown or duplicate case ID: ' + str(cid))
        seen.add(cid)
        for key in ('jd_sha256', 'wording_pair_id', 'base_wording', 'library_wording'):
            if label.get(key) != str(expected[cid][key]):
                raise ValueError(f'Stale/edited context for {cid}: {key}')
        value = label.get('owner_outcome', '').strip()
        if value and value not in OPTIONS:
            raise ValueError(f'Invalid owner outcome for {cid}: {value}')
        records.append({'case_id': cid, 'owner_label': value or None,
            'diagnostic_prediction': PREDICTIONS[by_id[cid]['diagnostic']['outcome']],
            'agreement': None if not value else value == PREDICTIONS[by_id[cid]['diagnostic']['outcome']],
            'reviewer_notes': label.get('reviewer_notes', '')})
    if seen != set(expected):
        raise ValueError('Review CSV must retain all case rows, including unlabelled rows.')
    return {'labelled': sum(bool(x['owner_label']) for x in records),
            'awaiting_review': sum(not x['owner_label'] for x in records),
            'semantic_accuracy': None,
            'limit': 'Labels are supplied by the reviewer, not generated here. Raw agreement is not independently established semantic accuracy; repeated wording pairs are correlated.',
            'cases': records}


def render(cases):
    e = lambda x: html.escape(str(x))
    rows = review_rows(cases)
    parts = ['<!doctype html><html lang="en"><meta charset="utf-8"><title>Blind real bullet review</title>',
        '<style>body{max-width:1100px;margin:2em auto;padding:0 1em;font:17px/1.5 system-ui;color:#182332}pre{white-space:pre-wrap;overflow-wrap:anywhere}article{border-top:3px solid #567;margin-top:3em}.pair{display:grid;grid-template-columns:1fr 1fr;gap:1em}.card{background:#f1f4f8;padding:1em;min-width:0}li,p{overflow-wrap:anywhere}@media(max-width:800px){.pair{grid-template-columns:1fr}}</style>',
        '<h1>Independent owner review — 20 real JD contexts</h1><p>Diagnostic predictions and saved selection flags are intentionally omitted. Review the evidence first, then fill owner_review.csv. A source record proves recorded provenance, not independent truth. Native citations show what the scorer observed, not a causal bullet contribution. An unavailable citation does not disprove either wording. Exact wording pairs recur across JDs; assess each JD independently.</p>',
        '<p>Allowed owner outcomes: '+e(' | '.join(OPTIONS))+'. Leave uncertain cases unlabelled or select Insufficient evidence; add notes. Potential complementarity prompts are literal differences, not expected answers. Full JD importance is shown only where recorded; unclassified source text is not assigned new weights.</p>',
        '<nav>'+ ' · '.join(f'<a href="#{e(c["case_id"])}">{e(c["case_id"])}</a>' for c in cases)+'</nav>']
    for c, row in zip(cases, rows):
        parts += [f'<article id="{e(c["case_id"])}"><h2>{e(c["case_id"])} — App {c["application"]}: {e(c["project"])}</h2>',
            f'<p>{e(c["source_receipt"]["company"])} / {e(c["source_receipt"]["job"])}<br>Exact wording group {e(pair_id(c))}; contexts: {e(row["repeated_in_cases"])}. Each context remains a separate review.</p>',
            '<p><b>Substitution check:</b> '+e(row['substitution_review_prompt'])+' Consider whether replacing either would lose a different contribution; no equivalence has been established.</p><div class="pair">']
        for role in ('base', 'library'):
            b = c[role]
            parts += [f'<section class="card"><h3>{role.title()} wording</h3><p>{e(b["bullet"])}</p>',
                '<p><b>Recorded source provenance:</b> '+e('; '.join(s for s in b['sources'] if s != 'Current final'))+'.</p>',
                '<p><b>Lexical cues only:</b> '+e(', '.join(b.get('jd_wide_term_cues', [])) or 'None recorded')+'. Technology cues: '+e(', '.join(b.get('jd_wide_technology_cues', [])) or 'None recorded')+'. These do not establish performed work or whole-requirement satisfaction.</p>',
                f'<p>Word count: {b["words"]}. Per-bullet native impact: <b>unmeasured</b>.</p>']
            cited = False
            for link in b.get('jd_links', []):
                parts.append('<p><b>Recorded link:</b> '+e(link['text'])+' ['+e(link['importance'])+']; status: '+e(link['status'])+'</p>')
                for doc, n in link.get('native_evidence', {}).items():
                    cited = True
                    parts.append('<blockquote>'+e(n.get('excerpt', ''))+'</blockquote><p>Native document citation ('+e(doc)+'): grade '+e(n.get('match_label'))+', strength '+e(n.get('strength'))+'. A recorded scorer observation, not independent source attestation or measured score delta.</p>')
            if not cited:
                parts.append('<p><b>Citation unavailable for this wording.</b> It may be absent from the observed document or uncited within it. This is not evidence of inferiority or falsity.</p>')
            parts.append('</section>')
        parts += ['</div><h3>Actual linked JD requirements</h3>']
        if not c['jd_requirements']:
            parts.append('<p>No linked requirement recorded. This is not a finding of no JD relevance. Consult the full original JD below; importance for unlinked text is not supplied by this pair record.</p>')
        for q in c['jd_requirements']:
            parts += ['<p><b>'+e(q['importance'])+'</b>: '+e(q['text'])+'<br>ID '+e(q['id'])+'; preserved parent: '+e(q.get('parent', ''))+'</p>',
                '<details><summary>Saved requirement provenance</summary><pre>'+e(json.dumps(q.get('source_provenance', []),ensure_ascii=False,indent=2))+'</pre></details>']
        if malformed_links(c):
            parts.append('<p><b>Data-quality warning:</b> saved-link identifiers include individual characters rather than valid requirement IDs. They are unusable for coverage claims. Original values are preserved in cases.json; native citations are a separate evidence channel.</p>')
        src=c['source_receipt']
        parts += ['<details><summary>Full original JD and frozen identity</summary><pre>'+e(c['jd_text'])+'</pre><p>JD SHA-256: '+e(src['jd_sha256'])+'<br>Generation: '+e(src['generation_id'])+'<br>Observed DOCX SHA-256: '+e(src['docx_sha256'])+'<br>Verification row: '+e(src['verification_row'])+'<br>Binding: '+e(c['native_binding'])+'</p></details>',
            '<p><b>Your review:</b> '+e(' | '.join(OPTIONS))+'<br>Record owner_outcome and reviewer_notes in the CSV. No default answer is supplied.</p></article>']
    return '\n'.join(parts)+'</html>'


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--labels', type=Path, help='Reviewed CSV; only writes separate comparison outputs.')
    args = ap.parse_args()
    out = Path(__file__).resolve().parent
    source = out.parent/'cases.json'
    cases = json.loads(source.read_text(encoding='utf-8'))
    if args.labels:
        report = compare_labels(cases, args.labels)
    else:
        rows = review_rows(cases)
        target = out/'owner_review.csv'
        # Never overwrite an owner-reviewed CSV.
        if target.exists() and target.read_text(encoding='utf-8-sig'):
            raise FileExistsError('Review packet already exists; preserve owner labels. Use --labels for comparison.')
        with target.open('w',encoding='utf-8-sig',newline='') as f:
            w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
        (out/'review.html').write_text(render(cases),encoding='utf-8')
        report=compare_labels(cases,target)
    (out/'comparison.json').write_text(json.dumps(report,indent=2,ensure_ascii=False),encoding='utf-8')
    lines=['# Diagnostic comparison — open after independent review',
        f"Reviewed: {report['labelled']}; awaiting: {report['awaiting_review']}. Semantic accuracy: not calculated.",
        report['limit'], '', '| Case | Diagnostic prediction | Owner label | Agreement |', '|---|---|---|---|']
    for x in report['cases']:
        lines.append(f"| {x['case_id']} | {x['diagnostic_prediction']} | {x['owner_label'] or 'Awaiting review'} | {x['agreement'] if x['agreement'] is not None else 'Not assessed'} |")
    (out/'comparison.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    withheld=Counter(reason for c in cases for reason in reasons(c))
    (out/'packet_summary.json').write_text(json.dumps({'cases':len(cases),'unique_exact_wording_pairs':len({pair_id(c) for c in cases}),
        'withheld_primary_categories':dict(withheld),'malformed_link_cases':[c['case_id'] for c in cases if malformed_links(c)],
        'complementarity_review_prompts':PROMPTS,'source_cases_sha256':hashlib.sha256(source.read_bytes()).hexdigest(),
        'owner_labelled':report['labelled'],'semantic_accuracy':None},indent=2),encoding='utf-8')
    print(f"Saved packet/comparison: {report['labelled']} labelled, {report['awaiting_review']} awaiting; no accuracy calculated.")


if __name__ == '__main__':
    main()
