#!/usr/bin/env python3
"""Print the absolute broad-baseline table used by the paper.

Raw counts are equal-task geometric means in billions.  Parenthesized
percentages report the change obtained by replacing that row with our frozen
sequence; negative therefore means fewer operations for ours.
"""

from __future__ import annotations

import json
import math
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RESULT = ROOT / "result/v3_tune/v3_tune_broad_test.json"
DISPLAY = {
    "candidate": "Ours",
    "shell": "Shell",
    "hibbard": "Hibbard",
    "knuth": "Knuth",
    "pratt": "Pratt",
    "sedgewick": "Sedgewick",
    "tokuda": "Tokuda",
    "ciura": "Ciura",
}


def geometric_mean(values: list[int]) -> float:
    return math.exp(sum(math.log(value + 1) for value in values) / len(values)) - 1.0


def candidate_change(candidate: list[int], baseline: list[int]) -> float:
    return 100.0 * (
        math.exp(
            sum(math.log((c + 1) / (b + 1)) for c, b in zip(candidate, baseline))
            / len(candidate)
        )
        - 1.0
    )


def main() -> None:
    payload = json.loads(RESULT.read_text())
    report = payload["reports"][0]
    tasks = report["task_results"]
    labels = [
        "candidate", "tokuda", "ciura", "sedgewick", "hibbard", "knuth",
        "shell", "pratt",
    ]
    rows = []
    for label in labels:
        def cost(task: dict[str, object]) -> dict[str, int]:
            return task["candidate"] if label == "candidate" else task["baselines"][label]

        row = []
        for field, selected in (
            ("comparisons", tasks), ("moves", tasks), ("total", tasks),
            ("total", [task for task in tasks if task["distribution"] == "reversed"]),
        ):
            candidate_values = [int(task["candidate"][field]) for task in selected]
            baseline_values = [int(cost(task)[field]) for task in selected]
            row.append((
                geometric_mean(baseline_values) / 1_000_000_000,
                0.0 if label == "candidate" else candidate_change(candidate_values, baseline_values),
            ))
        rows.append((label, row))

    for label, row in rows:
        cells = []
        for raw, change in row:
            if label == "candidate":
                cells.append(f"{raw:.4f}")
            elif change < 0:
                cells.append(f"{raw:.4f} \\goodarrow{{{abs(change):.3f}\\%}}")
            else:
                cells.append(f"{raw:.4f} \\badarrow{{{abs(change):.3f}\\%}}")
        print(f"{DISPLAY[label]:12s} & " + " & ".join(cells) + " \\\\ ")


if __name__ == "__main__":
    main()
