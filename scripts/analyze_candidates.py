#!/usr/bin/env python3
"""Create a compact structural report for frozen candidates."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core.discovery import load_candidates


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("candidates", type=Path)
    parser.add_argument("--sizes", type=int, nargs="+", default=(32, 128, 512, 2048, 8192))
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    reports = []
    for frozen in load_candidates(args.candidates):
        generator = frozen.verify()
        sequences = {str(n): generator.generate(n) for n in args.sizes}
        reports.append(
            {
                "program_id": frozen.program_id,
                "template": frozen.program["template"],
                "program": frozen.program,
                "complexity": generator.complexity,
                "sequences": sequences,
                "gap_counts": {n: len(gaps) for n, gaps in sequences.items()},
            }
        )
    text = json.dumps({"reports": reports}, indent=2)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text, encoding="utf-8")
    print(text)


if __name__ == "__main__":
    main()

