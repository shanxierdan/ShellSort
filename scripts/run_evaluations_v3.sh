#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_ROOT"
RUN_ROOT="${RUN_ROOT:-result/v3}"
EVAL_CACHE="${EVAL_CACHE:-$RUN_ROOT/evaluation-cost-v3.sqlite}"
RUN_FINAL="${RUN_FINAL:-0}"
SEEDS=(0 1 2 3 4)
PIDS=()
PID_SEEDS=()

write_seed_status() {
  local seed="$1" status="$2" stage="$3"
  local path="$RUN_ROOT/seed-$seed/status-v3.json"
  printf '{"schema_version":3,"seed":%s,"status":"%s","stage":"%s"}\n' \
    "$seed" "$status" "$stage" > "$path.tmp"
  mv "$path.tmp" "$path"
}

write_root_status() {
  local status="$1" stage="$2"
  printf '{"schema_version":3,"status":"%s","stage":"%s"}\n' \
    "$status" "$stage" > "$RUN_ROOT/evaluation-status-v3.json.tmp"
  mv "$RUN_ROOT/evaluation-status-v3.json.tmp" "$RUN_ROOT/evaluation-status-v3.json"
}

cleanup_jobs() {
  if [ "${#PIDS[@]}" -gt 0 ]; then kill "${PIDS[@]}" 2>/dev/null || true; fi
}
trap cleanup_jobs INT TERM EXIT

python - "$RUN_ROOT" <<'PY'
import json, sys
from pathlib import Path
root=Path(sys.argv[1])
for seed in range(5):
    seed_dir=root/f"seed-{seed}"
    metrics=json.loads((seed_dir/"metrics-v3.json").read_text())
    candidates=json.loads((seed_dir/"candidates-v3.json").read_text())
    if len(metrics) != 120 or metrics[-1]["iteration"] != 120:
        raise SystemExit(f"seed {seed} training is not complete")
    hashes={item["program_hash"] for item in candidates["candidates"]}
    if candidates.get("train_best_program_hash") not in hashes:
        raise SystemExit(f"seed {seed} training winner is absent from candidates")
print("training artifacts verified for seeds 0..4")
PY

write_root_status running validation_baselines
python scripts/evaluate_v3.py "$RUN_ROOT/seed-0/candidates-v3.json" \
  --stage validation --points 8 --distributions random reversed nearly_sorted duplicates blocks \
  --cache "$EVAL_CACHE" --baseline-only > "$RUN_ROOT/validation-baselines-v3.log" 2>&1

write_root_status running validation
for SEED in "${SEEDS[@]}"; do
  SEED_DIR="$RUN_ROOT/seed-$SEED"
  write_seed_status "$SEED" evaluating validation
  python scripts/evaluate_v3.py "$SEED_DIR/candidates-v3.json" \
    --stage validation --points 8 --distributions random reversed nearly_sorted duplicates blocks \
    --cache "$EVAL_CACHE" --output "$SEED_DIR/validation-v3.json" \
    > "$SEED_DIR/validation-v3.log" 2>&1 &
  PIDS+=("$!")
  PID_SEEDS+=("$SEED")
done

FAILURES=0
for INDEX in "${!PIDS[@]}"; do
  if wait "${PIDS[$INDEX]}"; then
    write_seed_status "${PID_SEEDS[$INDEX]}" validation_complete validation
    echo "V3 seed=${PID_SEEDS[$INDEX]} Validation complete"
  else
    STATUS=$?
    write_seed_status "${PID_SEEDS[$INDEX]}" failed validation
    echo "V3 seed=${PID_SEEDS[$INDEX]} Validation failed (exit=$STATUS)" >&2
    FAILURES=$((FAILURES + 1))
  fi
done
PIDS=(); PID_SEEDS=()
if [ "$FAILURES" -gt 0 ]; then
  write_root_status failed validation
  exit 1
fi

python scripts/select_v3.py --run-root "$RUN_ROOT" --output "$RUN_ROOT/selected-v3.json" \
  > "$RUN_ROOT/selection-v3.log" 2>&1

write_root_status running extrapolation_baselines
python scripts/evaluate_v3.py "$RUN_ROOT/selected-v3.json" \
  --stage extrapolation --points 4 --distributions random reversed \
  --cache "$EVAL_CACHE" --baseline-only > "$RUN_ROOT/extrapolation-baselines-v3.log" 2>&1

write_root_status running extrapolation
python scripts/evaluate_v3.py "$RUN_ROOT/selected-v3.json" \
  --stage extrapolation --points 4 --distributions random reversed \
  --cache "$EVAL_CACHE" --output "$RUN_ROOT/extrapolation-v3.json" \
  > "$RUN_ROOT/extrapolation-v3.log" 2>&1

for SEED in "${SEEDS[@]}"; do write_seed_status "$SEED" complete extrapolation; done
write_root_status complete extrapolation
trap - INT TERM EXIT
echo "V3 frozen evaluation complete: $RUN_ROOT"
if [ "$RUN_FINAL" = "1" ]; then
  RUN_ROOT="$RUN_ROOT" EVAL_CACHE="$RUN_ROOT/final-test-cost-v3.sqlite" \
    RUN_FINAL=1 bash scripts/run_final_test_v3.sh
else
  echo "Final test remains sealed."
fi
