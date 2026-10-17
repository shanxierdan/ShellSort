#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_ROOT"

FINAL_DRY_RUN="${FINAL_DRY_RUN:-0}"
if [ "${RUN_FINAL:-0}" != "1" ] && [ "$FINAL_DRY_RUN" != "1" ]; then
  echo "Final Test is sealed. Re-run with RUN_FINAL=1 after the protocol is frozen." >&2
  exit 2
fi

RUN_ROOT="${RUN_ROOT:-result/v3}"
MANIFEST="${MANIFEST:-data/manifests.json}"
EVAL_CACHE="${EVAL_CACHE:-$RUN_ROOT/final-test-cost-v3.sqlite}"
OUTPUT="$RUN_ROOT/final-test-v3.json"
LOG="$RUN_ROOT/final-test-v3.log"
STATUS="$RUN_ROOT/evaluation-status-v3.json"
RUN_PREFLIGHT_TESTS="${RUN_PREFLIGHT_TESTS:-1}"

write_status() {
  local status="$1"
  printf '{"schema_version":3,"status":"%s","stage":"final_test"}\n' "$status" > "$STATUS.tmp"
  mv "$STATUS.tmp" "$STATUS"
}

mark_failed() {
  local exit_code=$?
  write_status failed
  exit "$exit_code"
}
trap mark_failed ERR
trap 'write_status interrupted; exit 130' INT TERM

python - "$RUN_ROOT" "$MANIFEST" <<'PY'
import json
import sys
from pathlib import Path

from core.discovery import stage_tasks
from core.program_v3 import GeneratorProgram
from scripts.analyze_v3_number_theory import (
    ALPHA_DENOMINATOR,
    ALPHA_NUMERATOR,
    RATIO_DENOMINATOR,
    RATIO_NUMERATOR,
)

root = Path(sys.argv[1])
manifest_path = Path(sys.argv[2])
manifest = json.loads(manifest_path.read_text())
protocol = manifest["final_test"]
selected = json.loads((root / "selected-v3.json").read_text())
expected = protocol["primary_program_hash"]
matches = [item for item in selected["candidates"] if item["program_hash"] == expected]
if len(matches) != 1:
    raise SystemExit("frozen primary hash is absent or duplicated in selected-v3.json")
if protocol["primary_source_seed"] not in matches[0].get("source_seeds", []):
    raise SystemExit("frozen primary does not come from preregistered seed 4")
if selected.get("selection_stage") != "validation":
    raise SystemExit("primary candidate was not frozen by Validation")
if int(protocol["max_n"]) < int(protocol["min_n"]):
    raise SystemExit("invalid Final Test n range")
program = GeneratorProgram.from_dict(matches[0]["program"])
tasks = stage_tasks(
    manifest_path,
    "final_test",
    tuple(protocol["distributions"]),
    allow_final_test=True,
    points=int(protocol["points"]),
)
for n in sorted({task.n for task in tasks}):
    numerator = ALPHA_NUMERATOR
    denominator = ALPHA_DENOMINATOR
    exact = {1}
    while True:
        gap = numerator // denominator
        if gap >= n:
            break
        if gap >= 1:
            exact.add(gap)
        numerator *= RATIO_NUMERATOR
        denominator *= RATIO_DENOMINATOR
    if program.generate(n) != tuple(sorted(exact, reverse=True)):
        raise SystemExit(f"program/exact-symbolic sequence mismatch at n={n}")
memory = Path("/proc/meminfo")
if memory.exists():
    fields = {}
    for line in memory.read_text().splitlines():
        key, value = line.split(":", 1)
        fields[key] = int(value.strip().split()[0]) * 1024
    required = 4 * 8 * int(protocol["max_n"])
    if fields.get("MemAvailable", required) < required:
        raise SystemExit(
            f"Final Test needs at least {required / 2**30:.2f} GiB available RAM "
            "for the largest compact-array task"
        )
print(
    "Final Test preflight: "
    f"program={expected} n=[{protocol['min_n']},{protocol['max_n']}] "
    f"points={protocol['points']} distributions={len(protocol['distributions'])}"
)
PY

if [ "$RUN_PREFLIGHT_TESTS" = "1" ]; then
  python -m unittest tests.test_discovery tests.test_fast_shellsort tests.test_evaluation_v3
fi

if [ "$FINAL_DRY_RUN" = "1" ]; then
  echo "Final Test dry-run complete; sealed tasks were not evaluated."
  trap - ERR INT TERM
  exit 0
fi

write_status running
python scripts/evaluate_v3.py "$RUN_ROOT/selected-v3.json" \
  --stage final_test \
  --allow-final-test \
  --manifest "$MANIFEST" \
  --cache "$EVAL_CACHE" \
  --output "$OUTPUT" \
  2>&1 | tee "$LOG"
write_status complete

python - "$OUTPUT" <<'PY'
import json
import sys
from pathlib import Path

result = json.loads(Path(sys.argv[1]).read_text())
decision = result["final_test_decision"]
report = result["reports"][0]
print(f"Final Test complete: success={decision['success']}")
for name, value in report["fixed_baseline_log_ratios"].items():
    print(f"  {name}: mean_log_ratio={value:.9f}")
print(f"  censored_tasks={report['censored_tasks']}")
print(f"  output={sys.argv[1]}")
PY

trap - ERR INT TERM
