"""Prepare V4 blank review artifacts or validate completed receipts without import."""
import argparse
import json
from pathlib import Path
from taxonomy_discovery import unresolved_review_packet as review
from taxonomy_discovery.unresolved_gold_review import ROOT


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--validate-receipts',type=Path)
    args=parser.parse_args(argv)
    packet=review.build_packet()
    if args.validate_receipts:
        result=review.validate_decisions(packet,json.loads(args.validate_receipts.read_text(encoding='utf-8')))
        print(json.dumps(result,ensure_ascii=True,indent=2));return result
    outputs=[ROOT/'docs/unresolved_gold_review_packet_v4.md',ROOT/'reports/unresolved_gold_review_packet_v4.json',
             ROOT/'reports/unresolved_gold_review_receipts_template_v4.json']
    if any(p.exists() for p in outputs):parser.error('Preserve existing review packets; no overwrite')
    for p,value in zip(outputs,[review.markdown(packet),json.dumps(packet,ensure_ascii=True,indent=2)+'\n',
                               json.dumps(review.template(packet),ensure_ascii=True,indent=2)+'\n']):
        p.parent.mkdir(parents=True,exist_ok=True);p.write_text(value,encoding='utf-8')
    print(json.dumps(packet['summary'],indent=2));return packet


if __name__=='__main__':main()
