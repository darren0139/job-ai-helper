"""Default-CI registration check; historical reproduction is always separate."""
import json
from scripts.ollama_test_lanes import inventory


def main():
    result = inventory()
    print(json.dumps({'current_source_registered':len(result['current_test_ids']),
                      'historical_registered_not_executed':len(result['historical_test_ids']),
                      'historical_reproduction':'NOT_RUN',
                      'check':'REGISTRATION_ONLY_NOT_REPRODUCTION'},sort_keys=True))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
