"""Disposable deterministic observations, independent of classification oracles.

Run via scripts/run_offline_release_checks.py with this module name. Original
frozen JD text is the only corpus input; every version receives empty evidence.
"""
from collections import Counter
import json
from pathlib import Path
import tempfile
import unittest

from analysis_stability import stable_evidence_scoring as n,jd_metadata_policy as v22,jd_metadata_v123 as v23
from analysis_stability.coordinated_integration import build_coordinated_analysis
from scripts.preview_jd_metadata_admission import native_inputs,summary

ROOT=Path(__file__).resolve().parents[1]


def affected_rows(analysis,line,text):
    wanted=n._normalise_basic(text.lstrip('-*\u2022 '))
    return [r for r in analysis['canonical_requirements'] if any(
        s.get('grounding',{}).get('line_index')==line or
        (wanted and wanted in n._normalise_basic(s.get('raw_parent_text','')))
        for s in r.get('source_provenance',[]))]


def row_impact(rows):
    return [{'id':r['requirement_id'],'text':r['text'],'allocation':r['group_weight_fraction'],
             'importance':r['importance'],'label':r['match_label'],
             'parent_occurrence':r['scoring_parent_occurrence_id']} for r in rows]


def markdown_audit(audit):
    lines=['# v1.23 original-span audit','',
        'Generated observations plus separately authored analyst judgments. Native output is not an oracle. '
        'The 83 v1.22 ambiguous lines and eight additional required boundary controls are all included. '
        'No real candidate evidence is used. Character intervals are zero-based, end-exclusive; line numbers are one-based.','']
    for a in audit:
        lines.extend([f"## Job {a['job_id']} · line {a['line']} · [{a['raw_span'][0]}, {a['raw_span'][1]})",'',
            '> '+a['original_text'].replace('\n','\n> '),'',
            f"- Source: `raw_jd.lines[{a['line']}]`; v1.22 ambiguity: **{a['was_v22_ambiguous']}**.",
            '- Preceding section: '+json.dumps(a['preceding_section'],ensure_ascii=False)+'.',
            '- Following section: '+json.dumps(a['following_section'],ensure_ascii=False)+'.',
            '- Immediately preceding line: '+json.dumps(a['previous_line'],ensure_ascii=False)+'.',
            '- Immediately following line: '+json.dumps(a['next_line'],ensure_ascii=False)+'.',
            '- Native spans: '+json.dumps(a['native_span_classification'],ensure_ascii=False)+'.',
            '- v1.22: **'+a['v22']['classification']+'**; '+a['v22']['reason']+'.',
            '- Analyst judgment: **'+a['human_category']+'**; '+a['independent_justification'],
            '- v1.23: **'+a['v23']['classification']+'**; '+a['v23']['reason']+'.',
            '- Score-bearing rows (ID, original parent, importance and allocation): '+json.dumps(a['rows_by_version'],ensure_ascii=False)+'.',
            '- Packet score availability: '+json.dumps(a['availability_by_version'])+'.',
            '- v1.22 → v1.23 packet row/allocation change: '+json.dumps(a['packet_geometry_delta'])+'.',
            '- Automation: '+('Unresolved; source is retained and aggregate withheld.' if a['v23']['classification']=='AMBIGUOUS_CONTENT' else 'Resolved only by the reported bounded rule; classification does not assert candidate evidence.'),''])
    return '\n'.join(lines)+'\n'


class MetadataV123Diagnostics(unittest.TestCase):
    def test_export_all_30_and_every_original_ambiguous_span(self):
        corpus=json.loads((ROOT/'tests/fixtures/per_jd_scoring_audit.json').read_text(encoding='utf-8'))
        review=json.loads((ROOT/'tests/fixtures/jd_metadata_v123_span_review.json').read_text())['cases']
        focus=json.loads((ROOT/'tests/fixtures/jd_metadata_v123_expectations.json').read_text())['cases']
        by_source={(r['job_id'],r['line']):r for r in review}
        for row in focus:
            by_source.setdefault((row['job_id'],row['line']),dict(row,human_category=row['expected']))
        comparisons=[];audit=[]
        for job in corpus['snapshot']['audit']['corpus']['jobs']:
            jid=job['job_id'];raw=job['frozen_inputs']['raw_jd_text'];lines=raw.splitlines()
            inputs=native_inputs(raw,{})
            analyses={'v17':n.build_stable_analysis(**inputs),'v20':build_coordinated_analysis(**inputs),
                      'v22':v22.build_metadata_preview(developer_enabled=True,**inputs),
                      'v23':v23.build_metadata_preview(developer_enabled=True,**inputs)}
            receipts={key:analyses[key]['jd_metadata_classification'] for key in ('v22','v23')}
            versions={key:summary(value) for key,value in analyses.items()}
            old={r['id']:r for r in versions['v22']['rows']};new={r['id']:r for r in versions['v23']['rows']}
            changes=[{'id':k,'text':new[k]['text'],'before':{f:old[k][f] for f in ('importance','allocation')},
                      'after':{f:new[k][f] for f in ('importance','allocation')}} for k in sorted(old.keys()&new.keys())
                     if any(old[k][f]!=new[k][f] for f in ('importance','allocation'))]
            geometry={'counts':[len(old),len(new)],'allocations':[versions[k]['allocation'] for k in ('v22','v23')]}
            comparison={'job_id':jid,'versions':versions,'v22_classification':receipts['v22'],
                'v23_classification':receipts['v23'],'retained_ids':sorted(old.keys()&new.keys()),
                'recovered_rows':[new[k] for k in sorted(new.keys()-old.keys())],
                'removed_rows':[old[k] for k in sorted(old.keys()-new.keys())],
                'changed_existing_allocation_or_importance':changes,
                'administrative_exclusions':[r for r in receipts['v23']['lines'] if r['classification']=='ADMINISTRATIVE_METADATA'],
                'unresolved_count':len(receipts['v23']['unresolved_classifications'])}
            comparisons.append(comparison)
            native_spans=n._raw_jd_content_spans(raw)
            headings=[r for r in receipts['v23']['lines'] if r['classification'] in ('STRUCTURAL_HEADING','AMBIGUOUS_HEADING') or r['reason']=='controlled_admin_boundary']
            for (job_id,index),judgment in sorted(by_source.items()):
                if job_id!=jid:continue
                text=judgment['original_text'];self.assertEqual(lines[index-1],text)
                records={k:receipts[k]['lines'][index-1] for k in ('v22','v23')}
                matching=[s for s in native_spans if s['line_index']==index or
                    (s['line_index']<index and n._normalise_basic(text.lstrip('-*\u2022 ')) in n._normalise_basic(s['raw_text']))]
                def heading_record(r):return {'line':r['line_index'],'text':r['raw_text'],'section':r['section'],'classification':r['classification']}
                before=[r for r in headings if r['line_index']<index];after=[r for r in headings if r['line_index']>index]
                audit.append({'job_id':jid,'line':index,'original_text':text,'raw_span':records['v22']['raw_span'],
                    'previous_line':lines[index-2] if index>1 else None,'next_line':lines[index] if index<len(lines) else None,
                    'preceding_section':heading_record(before[-1]) if before else None,
                    'following_section':heading_record(after[0]) if after else None,
                    'native_span_classification':[{'line':s['line_index'],'section':s['section'],'heading':s['section_heading'],'detection':s['section_detection']} for s in matching],
                    'v22':records['v22'],'v23':records['v23'],'human_category':judgment['human_category'],
                    'independent_justification':judgment['independent_justification'],
                    'was_v22_ambiguous':records['v22']['classification']=='AMBIGUOUS_CONTENT',
                    'rows_by_version':{k:row_impact(affected_rows(v,index,text)) for k,v in analyses.items()},
                    'availability_by_version':{k:v['deterministic_alignment_score'] is not None for k,v in analyses.items()},
                    'packet_geometry_delta':geometry})
        self.assertEqual(len(comparisons),30)
        self.assertEqual(sum(a['was_v22_ambiguous'] for a in audit),83)
        stats={key:{'withheld':sum(j['versions'][key]['alignment'] is None for j in comparisons),
                    'rows':sum(len(j['versions'][key]['rows']) for j in comparisons)} for key in ('v17','v20','v22','v23')}
        stats['v23_ambiguity']=dict(Counter(a['v23']['classification'] for a in audit if a['was_v22_ambiguous']))
        target=Path(tempfile.gettempdir())/'jd_metadata_v123_diagnostics.json'
        target.write_text(json.dumps({'evidence':'Identical empty synthetic candidate evidence for all versions; no historical candidate score inference.',
            'comparisons':comparisons,'span_audit':audit,'stats':stats},sort_keys=True,ensure_ascii=True,indent=2,allow_nan=False)+'\n',encoding='utf-8')
        (target.parent/'jd_metadata_v123_span_audit.md').write_text(markdown_audit(audit),encoding='utf-8')
        print('V123 diagnostic JSON: '+str(target),flush=True)
        print('V123 observations: '+json.dumps(stats,sort_keys=True),flush=True)
