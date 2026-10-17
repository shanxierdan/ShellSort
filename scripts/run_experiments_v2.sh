#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_ROOT"

PROFILE="${1:-smoke}"
DEVICE="${DEVICE:-auto}"
RUN_FINAL="${RUN_FINAL:-0}"
RUN_ID="${RUN_ID:-v2-${PROFILE}-$(date +%Y%m%d-%H%M%S)}"
RUN_ROOT="${RUN_ROOT:-result/${RUN_ID}}"

case "$PROFILE" in
  smoke)
    SEEDS=(0); ITERATIONS=2; POPULATION=6; ELITES=2; CHILDREN=2
    STEPS=2; POINTS=3; MAX_N=256; DISTRIBUTIONS=(random); TASK_SEEDS=(0)
    ;;
  pilot)
    SEEDS=(0 1 2); ITERATIONS=20; POPULATION=24; ELITES=8; CHILDREN=4
    STEPS=16; POINTS=8; MAX_N=100000; DISTRIBUTIONS=(random reversed nearly_sorted duplicates blocks); TASK_SEEDS=(0)
    ;;
  full)
    SEEDS=(0 1 2 3 4); ITERATIONS=100; POPULATION=48; ELITES=12; CHILDREN=6
    STEPS=64; POINTS=16; MAX_N=100000; DISTRIBUTIONS=(random reversed nearly_sorted duplicates blocks); TASK_SEEDS=(0 1)
    ;;
  *) echo "Usage: bash scripts/run_experiments_v2.sh [smoke|pilot|full]" >&2; exit 2 ;;
esac

mkdir -p "$RUN_ROOT"
python -c 'import sys, torch; print("python", sys.version.split()[0]); print("torch", torch.__version__); print("cuda_visible", torch.cuda.is_available())'
python -m unittest discover -s tests -v

CACHE="$RUN_ROOT/sequence-cost-v2.sqlite"
PIDS=()
cleanup_jobs() {
  if [ "${#PIDS[@]}" -gt 0 ]; then kill "${PIDS[@]}" 2>/dev/null || true; fi
}
trap cleanup_jobs INT TERM EXIT

GPU_COUNT="$(nvidia-smi --query-gpu=index --format=csv,noheader 2>/dev/null | wc -l || true)"
if [ "$DEVICE" = "cpu" ] || [ "$GPU_COUNT" -lt 1 ]; then GPU_COUNT=1; DEVICE=cpu; fi

for INDEX in "${!SEEDS[@]}"; do
  SEED="${SEEDS[$INDEX]}"
  GPU_INDEX=$((INDEX % GPU_COUNT))
  SEED_DIR="$RUN_ROOT/seed-$SEED"
  mkdir -p "$SEED_DIR"
  echo "Launching V2 seed=$SEED on device=$DEVICE gpu=$GPU_INDEX"
  (
    if [ "$DEVICE" != "cpu" ]; then export CUDA_VISIBLE_DEVICES="$GPU_INDEX"; fi
    python scripts/run_v2.py \
      --run-dir "$SEED_DIR" --device "$DEVICE" --seed "$SEED" --resume \
      --iterations "$ITERATIONS" --population "$POPULATION" \
      --elite-parents "$ELITES" --children-per-parent "$CHILDREN" \
      --gradient-steps "$STEPS" --points "$POINTS" --max-n "$MAX_N" \
      --distributions "${DISTRIBUTIONS[@]}" --task-seeds "${TASK_SEEDS[@]}" \
      --cache "$CACHE"
    if [ "$PROFILE" != "smoke" ]; then
      python scripts/evaluate_v2.py "$SEED_DIR/candidates-v2.json" \
        --stage validation --points 8 \
        --distributions random reversed nearly_sorted duplicates blocks \
        --output "$SEED_DIR/validation-v2.json" > /dev/null
      python scripts/evaluate_v2.py "$SEED_DIR/candidates-v2.json" \
        --stage extrapolation --points 4 --distributions random reversed \
        --output "$SEED_DIR/extrapolation-v2.json" > /dev/null
    fi
    if [ "$RUN_FINAL" = "1" ]; then
      python scripts/evaluate_v2.py "$SEED_DIR/candidates-v2.json" \
        --stage final_test --allow-final-test --points 4 \
        --distributions random reversed nearly_sorted duplicates blocks \
        --output "$SEED_DIR/final-test-v2.json" > /dev/null
    fi
  ) > "$SEED_DIR/run.log" 2>&1 &
  PIDS+=("$!")
done
for PID in "${PIDS[@]}"; do wait "$PID"; done
PIDS=()
trap - INT TERM EXIT
echo "V2 results: $RUN_ROOT"
if [ "$RUN_FINAL" != "1" ]; then echo "Final test remains sealed."; fi
