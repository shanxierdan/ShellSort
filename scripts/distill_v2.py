#!/usr/bin/env python3
"""Re-distill frozen V2 families and emit structural reports."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core.generator_v2 import LogPositionGenerator
from core.sequence import GapSequence, SequenceFamily


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("candidates", type=Path)
    parser.add_argument("--sizes", type=int, nargs="+", default=(32, 128, 512, 2048, 8192, 100000))
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    payload = json.loads(args.candidates.read_text())
    reports = []
    for item in payload["candidates"]:
        family = SequenceFamily(tuple(GapSequence.from_dict(x) for x in item["sequences"]))
        generator = LogPositionGenerator.from_family(family)
        reports.append({"family_hash": family.family_hash, "generator_hash": generator.generator_hash,
                        "generator": generator.to_dict(), "report": generator.structural_report(tuple(args.sizes))})
    result = {"schema_version": 2, "reports": reports}
    text = json.dumps(result, indent=2)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text, encoding="utf-8")
    print(text)


if __name__ == "__main__":
    main()
