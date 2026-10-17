#!/usr/bin/env bash
set -euo pipefail

V3_TUNE_PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$V3_TUNE_PROJECT_ROOT"

V3_TUNE_PROFILE="${1:-smoke}"
V3_TUNE_MANIFEST="${V3_TUNE_MANIFEST:-data/v3_tune_manifest.json}"
V3_TUNE_SOURCE="${V3_TUNE_SOURCE:-result/v3/selected-v3.json}"

case "$V3_TUNE_PROFILE" in
  smoke)
    V3_TUNE_SEARCH_STAGE=v3_tune_smoke_search
    V3_TUNE_VALIDATION_STAGE=v3_tune_smoke_validation
    V3_TUNE_ITERATIONS=2
    V3_TUNE_POPULATION=5
    V3_TUNE_ELITES=2
    V3_TUNE_CHILDREN=1
    V3_TUNE_EXPORT_LIMIT=5
    V3_TUNE_DEFAULT_RUN_ROOT=result/v3_tune_smoke
    ;;
  pilot)
    V3_TUNE_SEARCH_STAGE=v3_tune_pilot_search
    V3_TUNE_VALIDATION_STAGE=v3_tune_pilot_validation
    V3_TUNE_ITERATIONS=10
    V3_TUNE_POPULATION=14
    V3_TUNE_ELITES=4
    V3_TUNE_CHILDREN=2
    V3_TUNE_EXPORT_LIMIT=12
    V3_TUNE_DEFAULT_RUN_ROOT=result/v3_tune_pilot
    ;;
  full)
    V3_TUNE_SEARCH_STAGE=v3_tune_search
    V3_TUNE_VALIDATION_STAGE=v3_tune_validation
    V3_TUNE_ITERATIONS=24
    V3_TUNE_POPULATION=20
    V3_TUNE_ELITES=5
    V3_TUNE_CHILDREN=2
    V3_TUNE_EXPORT_LIMIT=16
    V3_TUNE_DEFAULT_RUN_ROOT=result/v3_tune
    ;;
  *)
    echo "Usage: bash scripts/run_experiments_v3_tune.sh [smoke|pilot|full]" >&2
    exit 2
    ;;
esac

V3_TUNE_RUN_ROOT="${V3_TUNE_RUN_ROOT:-$V3_TUNE_DEFAULT_RUN_ROOT}"

mkdir -p "$V3_TUNE_RUN_ROOT"
V3_TUNE_STATUS="$V3_TUNE_RUN_ROOT/v3_tune_status.json"
v3_tune_write_status() {
  local v3_tune_status_value="$1"
  printf '{"schema_version":1,"status":"%s","profile":"%s"}\n' \
    "$v3_tune_status_value" "$V3_TUNE_PROFILE" > "$V3_TUNE_STATUS.tmp"
  mv "$V3_TUNE_STATUS.tmp" "$V3_TUNE_STATUS"
}
v3_tune_failed() {
  local v3_tune_exit_code=$?
  v3_tune_write_status failed
  exit "$v3_tune_exit_code"
}
trap v3_tune_failed ERR
trap 'v3_tune_write_status interrupted; exit 130' INT TERM

python -m unittest tests.test_v3_tune tests.test_evaluation_v3 tests.test_fast_shellsort
v3_tune_write_status searching

python scripts/run_v3_tune.py \
  --run-dir "$V3_TUNE_RUN_ROOT" \
  --manifest "$V3_TUNE_MANIFEST" \
  --source "$V3_TUNE_SOURCE" \
  --stage "$V3_TUNE_SEARCH_STAGE" \
  --seed 0 \
  --iterations "$V3_TUNE_ITERATIONS" \
  --population "$V3_TUNE_POPULATION" \
  --elite-parents "$V3_TUNE_ELITES" \
  --children-per-parent "$V3_TUNE_CHILDREN" \
  --export-limit "$V3_TUNE_EXPORT_LIMIT" \
  --cache "$V3_TUNE_RUN_ROOT/v3_tune_cost.sqlite" \
  --resume \
  2>&1 | tee "$V3_TUNE_RUN_ROOT/v3_tune_search.log"

v3_tune_write_status validating
python scripts/evaluate_v3_tune.py "$V3_TUNE_RUN_ROOT/v3_tune_candidates.json" \
  --manifest "$V3_TUNE_MANIFEST" \
  --stage "$V3_TUNE_VALIDATION_STAGE" \
  --cache "$V3_TUNE_RUN_ROOT/v3_tune_validation_cost.sqlite" \
  --output "$V3_TUNE_RUN_ROOT/v3_tune_validation.json" \
  2>&1 | tee "$V3_TUNE_RUN_ROOT/v3_tune_validation.log"

python scripts/select_v3_tune.py \
  --candidates "$V3_TUNE_RUN_ROOT/v3_tune_candidates.json" \
  --validation "$V3_TUNE_RUN_ROOT/v3_tune_validation.json" \
  --output "$V3_TUNE_RUN_ROOT/v3_tune_selected.json"

v3_tune_write_status complete
trap - ERR INT TERM
echo "v3_tune complete: $V3_TUNE_RUN_ROOT/v3_tune_selected.json"
echo "v3_tune_test remains sealed."
