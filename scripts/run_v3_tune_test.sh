#!/usr/bin/env bash
set -euo pipefail

V3_TUNE_PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$V3_TUNE_PROJECT_ROOT"

V3_TUNE_TEST_DRY_RUN="${V3_TUNE_TEST_DRY_RUN:-0}"
if [ "${RUN_V3_TUNE_TEST:-0}" != "1" ] && [ "$V3_TUNE_TEST_DRY_RUN" != "1" ]; then
  echo "v3_tune_test is sealed. Use RUN_V3_TUNE_TEST=1 only after selection is frozen." >&2
  exit 2
fi

V3_TUNE_RUN_ROOT="${V3_TUNE_RUN_ROOT:-result/v3_tune}"
V3_TUNE_MANIFEST="${V3_TUNE_MANIFEST:-data/v3_tune_manifest.json}"
V3_TUNE_SELECTED="$V3_TUNE_RUN_ROOT/v3_tune_selected.json"
V3_TUNE_TEST_OUTPUT="$V3_TUNE_RUN_ROOT/v3_tune_test.json"
V3_TUNE_TEST_STATUS="$V3_TUNE_RUN_ROOT/v3_tune_test_status.json"

python - "$V3_TUNE_SELECTED" <<'PY'
import json
import sys
from pathlib import Path

from core.v3_tune import V3TuneCandidate

selected = json.loads(Path(sys.argv[1]).read_text())
if selected.get("selection_stage") != "v3_tune_validation":
    raise SystemExit("v3_tune_test requires the full v3_tune_validation winner")
if len(selected.get("candidates", [])) != 1:
    raise SystemExit("v3_tune test needs exactly one selected candidate")
item = selected["candidates"][0]
candidate = V3TuneCandidate.from_dict(item["candidate"])
if candidate.candidate_hash != selected.get("primary_candidate_hash"):
    raise SystemExit("v3_tune selected hash mismatch")
print(f"v3_tune_test preflight: candidate={candidate.candidate_hash} prefix={candidate.prefix}")
PY

if [ "$V3_TUNE_TEST_DRY_RUN" = "1" ]; then
  echo "v3_tune_test dry-run complete; sealed tasks were not evaluated."
  exit 0
fi

v3_tune_test_write_status() {
  local v3_tune_test_status_value="$1"
  printf '{"schema_version":1,"status":"%s","stage":"v3_tune_test"}\n' \
    "$v3_tune_test_status_value" > "$V3_TUNE_TEST_STATUS.tmp"
  mv "$V3_TUNE_TEST_STATUS.tmp" "$V3_TUNE_TEST_STATUS"
}
v3_tune_test_failed() {
  local v3_tune_test_exit_code=$?
  v3_tune_test_write_status failed
  exit "$v3_tune_test_exit_code"
}
trap v3_tune_test_failed ERR
trap 'v3_tune_test_write_status interrupted; exit 130' INT TERM

v3_tune_test_write_status running

python scripts/evaluate_v3_tune.py "$V3_TUNE_SELECTED" \
  --manifest "$V3_TUNE_MANIFEST" \
  --stage v3_tune_test \
  --allow-v3-tune-test \
  --cache "$V3_TUNE_RUN_ROOT/v3_tune_test_cost.sqlite" \
  --output "$V3_TUNE_TEST_OUTPUT" \
  2>&1 | tee "$V3_TUNE_RUN_ROOT/v3_tune_test.log"

v3_tune_test_write_status complete
trap - ERR INT TERM
echo "v3_tune_test complete: $V3_TUNE_TEST_OUTPUT"
