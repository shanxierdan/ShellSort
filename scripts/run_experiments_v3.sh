#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_ROOT"
PROFILE="${1:-smoke}"
DEVICE="${DEVICE:-auto}"
RUN_FINAL="${RUN_FINAL:-0}"
RUN_ID="${RUN_ID:-v3-${PROFILE}-$(date +%Y%m%d-%H%M%S)}"
RUN_ROOT="${RUN_ROOT:-result/${RUN_ID}}"

case "$PROFILE" in
  smoke)
    SEEDS=(0); ITERATIONS=2; POPULATION=6; ELITES=2; CHILDREN=2; STEPS=2
    POINTS=3; MAX_N=256; DISTRIBUTIONS=(random); TASK_SEEDS=(0)
    ;;
  pilot)
    SEEDS=(0 1 2); ITERATIONS=25; POPULATION=32; ELITES=8; CHILDREN=5; STEPS=16
    POINTS=8; MAX_N=100000; DISTRIBUTIONS=(random reversed nearly_sorted duplicates blocks); TASK_SEEDS=(0)
    ;;
  full)
    SEEDS=(0 1 2 3 4); ITERATIONS=120; POPULATION=48; ELITES=12; CHILDREN=6; STEPS=64
    POINTS=16; MAX_N=100000; DISTRIBUTIONS=(random reversed nearly_sorted duplicates blocks); TASK_SEEDS=(0 1)
    ;;
  *) echo "Usage: bash scripts/run_experiments_v3.sh [smoke|pilot|full]" >&2; exit 2 ;;
esac

mkdir -p "$RUN_ROOT"
python -m unittest discover -s tests -v
CACHE="$RUN_ROOT/sequence-cost.sqlite"
PIDS=()
PID_SEEDS=()
cleanup_jobs() { if [ "${#PIDS[@]}" -gt 0 ]; then kill "${PIDS[@]}" 2>/dev/null || true; fi; }
trap cleanup_jobs INT TERM EXIT
GPU_COUNT="$(nvidia-smi --query-gpu=index --format=csv,noheader 2>/dev/null | wc -l || true)"
if [ "$DEVICE" = "cpu" ] || [ "$GPU_COUNT" -lt 1 ]; then GPU_COUNT=1; DEVICE=cpu; fi

for INDEX in "${!SEEDS[@]}"; do
  SEED="${SEEDS[$INDEX]}"; GPU_INDEX=$((INDEX % GPU_COUNT)); SEED_DIR="$RUN_ROOT/seed-$SEED"
  mkdir -p "$SEED_DIR"
  printf '{"schema_version":3,"seed":%s,"status":"running"}\n' "$SEED" > "$SEED_DIR/status-v3.json"
  echo "Launching V3 seed=$SEED on device=$DEVICE gpu=$GPU_INDEX"
  (
    if [ "$DEVICE" != "cpu" ]; then export CUDA_VISIBLE_DEVICES="$GPU_INDEX"; fi
    if python scripts/run_v3.py --run-dir "$SEED_DIR" --device "$DEVICE" --seed "$SEED" --resume \
      --iterations "$ITERATIONS" --population "$POPULATION" --elite-parents "$ELITES" \
      --children-per-parent "$CHILDREN" --gradient-steps "$STEPS" --points "$POINTS" \
      --max-n "$MAX_N" --distributions "${DISTRIBUTIONS[@]}" --task-seeds "${TASK_SEEDS[@]}" --cache "$CACHE"; then
      run_status=0
    else
      run_status=$?
    fi
    if [ "$run_status" -eq 0 ]; then
      printf '{"schema_version":3,"seed":%s,"status":"trained","iterations":%s}\n' \
        "$SEED" "$ITERATIONS" > "$SEED_DIR/status-v3.json"
    else
      printf '{"schema_version":3,"seed":%s,"status":"failed","exit_code":%s}\n' \
        "$SEED" "$run_status" > "$SEED_DIR/status-v3.json"
      exit "$run_status"
    fi
  ) > "$SEED_DIR/run.log" 2>&1 &
  PIDS+=("$!")
  PID_SEEDS+=("$SEED")
done
FAILURES=0
for INDEX in "${!PIDS[@]}"; do
  if wait "${PIDS[$INDEX]}"; then
    echo "V3 seed=${PID_SEEDS[$INDEX]} complete"
  else
    STATUS=$?
    echo "V3 seed=${PID_SEEDS[$INDEX]} failed (exit=$STATUS); see $RUN_ROOT/seed-${PID_SEEDS[$INDEX]}/run.log" >&2
    FAILURES=$((FAILURES + 1))
  fi
done
PIDS=(); trap - INT TERM EXIT
if [ "$FAILURES" -gt 0 ]; then
  echo "V3 experiment failed: $FAILURES seed(s) did not complete." >&2
  exit 1
fi
if [ "$PROFILE" != "smoke" ]; then
  RUN_ROOT="$RUN_ROOT" RUN_FINAL="$RUN_FINAL" bash scripts/run_evaluations_v3.sh
else
  printf '{"schema_version":3,"seed":0,"status":"complete","iterations":%s}\n' \
    "$ITERATIONS" > "$RUN_ROOT/seed-0/status-v3.json"
fi
echo "V3 results: $RUN_ROOT"
if [ "$RUN_FINAL" != "1" ]; then echo "Final test remains sealed."; fi
