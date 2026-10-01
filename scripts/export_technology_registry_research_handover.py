from __future__ import annotations

import argparse
import json
from pathlib import Path

from taxonomy_discovery.research_proposals import (
    build_research_handover,
)
from taxonomy_discovery.triage import build_triage_report


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Export a TQ-D2.7 research handover JSON for another "
            "ChatGPT/Tavily research session."
        )
    )
    parser.add_argument(
        "--output",
        default="technology_registry_research_handover.json",
    )
    args = parser.parse_args()

    report = build_triage_report()
    handover = build_research_handover(report)

    output = Path(args.output).expanduser().resolve()
    output.write_text(
        json.dumps(
            handover,
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    print(f"wrote: {output}")
    print(
        "research_targets:",
        len(handover.get("research_targets", [])),
    )
    print(
        "proposal_contract_version:",
        handover.get("proposal_contract_version"),
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
