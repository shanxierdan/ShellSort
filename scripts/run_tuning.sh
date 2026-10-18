#!/usr/bin/env bash
set -euo pipefail

TUNING_PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$TUNING_PROJECT_ROOT"

TUNING_PROFILE="${1:-smoke}"
TUNING_MANIFEST="${TUNING_MANIFEST:-data/experiment_manifest.json}"
TUNING_SOURCE="${TUNING_SOURCE:-result/discovery/selected-programs.json}"

case "$TUNING_PROFILE" in
  smoke)
    TUNING_SEARCH_STAGE=smoke_search
    TUNING_VALIDATION_STAGE=smoke_validation
    TUNING_ITERATIONS=2
    TUNING_POPULATION=5
    TUNING_ELITES=2
    TUNING_CHILDREN=1
    TUNING_EXPORT_LIMIT=5
    TUNING_DEFAULT_RUN_ROOT=result/final-smoke
    ;;
  pilot)
    TUNING_SEARCH_STAGE=pilot_search
    TUNING_VALIDATION_STAGE=pilot_validation
    TUNING_ITERATIONS=10
    TUNING_POPULATION=14
    TUNING_ELITES=4
    TUNING_CHILDREN=2
    TUNING_EXPORT_LIMIT=12
    TUNING_DEFAULT_RUN_ROOT=result/final-pilot
    ;;
  full)
    TUNING_SEARCH_STAGE=search
    TUNING_VALIDATION_STAGE=validation
    TUNING_ITERATIONS=24
    TUNING_POPULATION=20
    TUNING_ELITES=5
    TUNING_CHILDREN=2
    TUNING_EXPORT_LIMIT=16
    TUNING_DEFAULT_RUN_ROOT=result/final
    ;;
  *)
    echo "Usage: bash scripts/run_tuning.sh [smoke|pilot|full]" >&2
    exit 2
    ;;
esac

TUNING_RUN_ROOT="${TUNING_RUN_ROOT:-$TUNING_DEFAULT_RUN_ROOT}"

mkdir -p "$TUNING_RUN_ROOT"
TUNING_STATUS="$TUNING_RUN_ROOT/tuning_status.json"
tuning_write_status() {
  local tuning_status_value="$1"
  printf '{"schema_version":1,"status":"%s","profile":"%s"}\n' \
    "$tuning_status_value" "$TUNING_PROFILE" > "$TUNING_STATUS.tmp"
  mv "$TUNING_STATUS.tmp" "$TUNING_STATUS"
}
tuning_failed() {
  local tuning_exit_code=$?
  tuning_write_status failed
  exit "$tuning_exit_code"
}
trap tuning_failed ERR
trap 'tuning_write_status interrupted; exit 130' INT TERM

python -m unittest tests.test_tuning tests.test_discovery_evaluation tests.test_fast_shellsort
tuning_write_status searching

python scripts/run_tuning.py \
  --run-dir "$TUNING_RUN_ROOT" \
  --manifest "$TUNING_MANIFEST" \
  --source "$TUNING_SOURCE" \
  --stage "$TUNING_SEARCH_STAGE" \
  --seed 0 \
  --iterations "$TUNING_ITERATIONS" \
  --population "$TUNING_POPULATION" \
  --elite-parents "$TUNING_ELITES" \
  --children-per-parent "$TUNING_CHILDREN" \
  --export-limit "$TUNING_EXPORT_LIMIT" \
  --cache "$TUNING_RUN_ROOT/cost.sqlite" \
  --resume \
  2>&1 | tee "$TUNING_RUN_ROOT/search.log"

tuning_write_status validating
python scripts/evaluate_final.py "$TUNING_RUN_ROOT/candidates.json" \
  --manifest "$TUNING_MANIFEST" \
  --stage "$TUNING_VALIDATION_STAGE" \
  --cache "$TUNING_RUN_ROOT/validation_cost.sqlite" \
  --output "$TUNING_RUN_ROOT/validation.json" \
  2>&1 | tee "$TUNING_RUN_ROOT/validation.log"

python scripts/select_final.py \
  --candidates "$TUNING_RUN_ROOT/candidates.json" \
  --validation "$TUNING_RUN_ROOT/validation.json" \
  --output "$TUNING_RUN_ROOT/selected.json"

tuning_write_status complete
trap - ERR INT TERM
echo "tuning complete: $TUNING_RUN_ROOT/selected.json"
echo "test remains sealed."
