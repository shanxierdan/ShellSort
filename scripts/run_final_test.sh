#!/usr/bin/env bash
set -euo pipefail

TUNING_PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$TUNING_PROJECT_ROOT"

TUNING_TEST_DRY_RUN="${TUNING_TEST_DRY_RUN:-0}"
if [ "${RUN_TUNING_TEST:-0}" != "1" ] && [ "$TUNING_TEST_DRY_RUN" != "1" ]; then
  echo "test is sealed. Use RUN_TUNING_TEST=1 only after selection is frozen." >&2
  exit 2
fi

TUNING_RUN_ROOT="${TUNING_RUN_ROOT:-result/final}"
TUNING_MANIFEST="${TUNING_MANIFEST:-data/experiment_manifest.json}"
TUNING_SELECTED="$TUNING_RUN_ROOT/selected.json"
TUNING_TEST_OUTPUT="$TUNING_RUN_ROOT/test.json"
TUNING_TEST_STATUS="$TUNING_RUN_ROOT/test_status.json"

python - "$TUNING_SELECTED" <<'PY'
import json
import sys
from pathlib import Path

from core.tuning import TunedCandidate

selected = json.loads(Path(sys.argv[1]).read_text())
if selected.get("selection_stage") != "validation":
    raise SystemExit("test requires the full validation winner")
if len(selected.get("candidates", [])) != 1:
    raise SystemExit("tuning test needs exactly one selected candidate")
item = selected["candidates"][0]
candidate = TunedCandidate.from_dict(item["candidate"])
if candidate.candidate_hash != selected.get("primary_candidate_hash"):
    raise SystemExit("tuning selected hash mismatch")
print(f"test preflight: candidate={candidate.candidate_hash} prefix={candidate.prefix}")
PY

if [ "$TUNING_TEST_DRY_RUN" = "1" ]; then
  echo "test dry-run complete; sealed tasks were not evaluated."
  exit 0
fi

test_write_status() {
  local test_status_value="$1"
  printf '{"schema_version":1,"status":"%s","stage":"test"}\n' \
    "$test_status_value" > "$TUNING_TEST_STATUS.tmp"
  mv "$TUNING_TEST_STATUS.tmp" "$TUNING_TEST_STATUS"
}
test_failed() {
  local test_exit_code=$?
  test_write_status failed
  exit "$test_exit_code"
}
trap test_failed ERR
trap 'test_write_status interrupted; exit 130' INT TERM

test_write_status running

python scripts/evaluate_final.py "$TUNING_SELECTED" \
  --manifest "$TUNING_MANIFEST" \
  --stage test \
  --allow-test \
  --cache "$TUNING_RUN_ROOT/test_cost.sqlite" \
  --output "$TUNING_TEST_OUTPUT" \
  2>&1 | tee "$TUNING_RUN_ROOT/test.log"

test_write_status complete
trap - ERR INT TERM
echo "test complete: $TUNING_TEST_OUTPUT"
