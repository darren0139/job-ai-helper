"""Produce V3 read-only source proof and pending human decisions; no benchmark run."""
import json
from taxonomy_discovery import unresolved_source_review as source_review
from taxonomy_discovery.unresolved_gold_review import ROOT


def main():
    outputs = [ROOT/'docs/unresolved_gold_decision_review_v3.md', ROOT/'reports/unresolved_gold_decision_review_v3.json']
    if any(p.exists() for p in outputs): raise ValueError('Preserve existing reviews; outputs must be new')
    report = source_review.build_report()
    for p,value in zip(outputs,[source_review.markdown(report),json.dumps(report,ensure_ascii=True,indent=2)+'\n']):
        p.parent.mkdir(parents=True,exist_ok=True)
        p.write_text(value,encoding='utf-8')
    print(json.dumps(report['summary'],indent=2))


if __name__ == '__main__': main()
