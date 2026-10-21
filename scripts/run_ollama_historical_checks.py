"""Explicit historical inventory/prerequisite lane. Never starts a provider.

Exit 2 = BLOCKED, never a successful experiment. --list returns inventory only.
Historical execution needs a separately reviewed source/dependency recipe.
"""
import argparse
import json
from pathlib import Path
from scripts.ollama_test_lanes import ROOT, inventory, historical_preconditions


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--list', action='store_true', help='Inventory only, not historical reproduction')
    parser.add_argument('--bundle-root',type=Path,default=ROOT)
    args=parser.parse_args(argv)
    if args.list:
        result=inventory()
        print(json.dumps({'status':'INVENTORY_ONLY_NOT_REPRODUCTION',
                          'historical_test_ids':result['historical_test_ids'],
                          'attempted':False,'validated':False},indent=2))
        return 0
    result=historical_preconditions(args.bundle_root)
    print(json.dumps(result,indent=2))
    return 2


if __name__ == '__main__':
    raise SystemExit(main())
