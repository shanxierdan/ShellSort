#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_ROOT"

PROFILE="${1:-smoke}"
DEVICE="${DEVICE:-auto}"
RUN_FINAL="${RUN_FINAL:-0}"
MAX_PARALLEL="${MAX_PARALLEL:-5}"
RUN_ID="${RUN_ID:-${PROFILE}-$(date +%Y%m%d-%H%M%S)}"
RUN_ROOT="${RUN_ROOT:-result/${RUN_ID}}"

case "$PROFILE" in
  smoke)
    SEEDS=(0)
    ITERATIONS=1
    EPISODES=2
    SIMULATIONS=4
    GRADIENT_STEPS=1
    PRETRAIN_STEPS=1
    TRAIN_POINTS=3
    TRAIN_MAX_N=128
    TRAIN_DISTRIBUTIONS=(random reversed)
    TRAIN_SEEDS=(0)
    MAX_NODES=8
    VALIDATE=0
    ;;
  pilot)
    SEEDS=(0 1 2)
    ITERATIONS=10
    EPISODES=8
    SIMULATIONS=16
    GRADIENT_STEPS=16
    PRETRAIN_STEPS=100
    TRAIN_POINTS=24
    TRAIN_MAX_N=100000
    TRAIN_DISTRIBUTIONS=(random reversed nearly_sorted duplicates blocks)
    TRAIN_SEEDS=(0 1)
    MAX_NODES=20
    VALIDATE=1
    ;;
  full)
    SEEDS=(0 1 2 3 4)
    ITERATIONS=100
    EPISODES=32
    SIMULATIONS=32
    GRADIENT_STEPS=64
    PRETRAIN_STEPS=1000
    # The universe contains 128 n values; each iteration samples an 8x2x1
    # Screen panel. The full Confirm panel is run only on frozen candidates.
    TRAIN_POINTS=128
    TRAIN_MAX_N=100000
    TRAIN_DISTRIBUTIONS=(random reversed nearly_sorted duplicates blocks)
    TRAIN_SEEDS=(0 1 2 3 4)
    MAX_NODES=32
    VALIDATE=1
    ;;
  *)
    echo "Usage: bash scripts/run_experiments.sh [smoke|pilot|full]" >&2
    exit 2
    ;;
esac

mkdir -p "$RUN_ROOT"

echo "[1/5] Environment and tests"
python -c 'import sys, torch; print("python", sys.version.split()[0]); print("torch", torch.__version__); print("cuda_visible", torch.cuda.is_available())'
python -m unittest discover -s tests -v

echo "[2/5] Baseline sanity benchmark"
python scripts/benchmark_baselines.py --n 128 --seed 7 > "$RUN_ROOT/baselines.txt"

echo "[3/5] Neural-guided searches: profile=$PROFILE seeds=${SEEDS[*]}"
BASELINE_CACHE="$RUN_ROOT/baseline-cache.sqlite"

run_seed() {
  local SEED="$1"
  local GPU_INDEX="$2"
  SEED_DIR="$RUN_ROOT/seed-$SEED"
  mkdir -p "$SEED_DIR"

  local EFFECTIVE_DEVICE="$DEVICE"
  if [ "$DEVICE" = "auto" ] || [ "$DEVICE" = "cuda" ]; then
    export CUDA_VISIBLE_DEVICES="$GPU_INDEX"
    EFFECTIVE_DEVICE="cuda"
  fi

  python scripts/run_neural_search.py \
    --run-dir "$SEED_DIR" \
    --device "$EFFECTIVE_DEVICE" \
    --seed "$SEED" \
    --iterations "$ITERATIONS" \
    --episodes "$EPISODES" \
    --simulations "$SIMULATIONS" \
    --gradient-steps "$GRADIENT_STEPS" \
    --pretrain-steps "$PRETRAIN_STEPS" \
    --max-nodes "$MAX_NODES" \
    --hidden-size 128 \
    --layers 3 \
    --heads 4 \
    --train-min-n 32 \
    --train-max-n "$TRAIN_MAX_N" \
    --train-points "$TRAIN_POINTS" \
    --panel-points 8 \
    --panel-distributions 2 \
    --panel-seeds 1 \
    --train-distributions "${TRAIN_DISTRIBUTIONS[@]}" \
    --train-seeds "${TRAIN_SEEDS[@]}" \
    --baseline-cache "$BASELINE_CACHE" \
    --resume

  python scripts/analyze_candidates.py \
    "$SEED_DIR/candidates.json" \
    --output "$SEED_DIR/analysis.json" > /dev/null

  if [ "$VALIDATE" = "1" ]; then
    python scripts/validate_candidates.py \
      "$SEED_DIR/candidates.json" \
      --stage train \
      --points 24 \
      --distributions random reversed nearly_sorted duplicates blocks \
      --seed-limit 2 \
      --baseline-cache "$BASELINE_CACHE" \
      --output "$SEED_DIR/promotion.json" > /dev/null

    if [ "$PROFILE" = "full" ]; then
      python scripts/validate_candidates.py \
        "$SEED_DIR/candidates.json" \
        --stage train \
        --points 128 \
        --distributions random reversed nearly_sorted duplicates blocks \
        --seed-limit 5 \
        --baseline-cache "$BASELINE_CACHE" \
        --output "$SEED_DIR/confirm.json" > /dev/null
    fi

    python scripts/validate_candidates.py \
      "$SEED_DIR/candidates.json" \
      --stage validation \
      --points 8 \
      --distributions random reversed nearly_sorted duplicates blocks \
      --seed-limit 2 \
      --baseline-cache "$BASELINE_CACHE" \
      --output "$SEED_DIR/validation.json" > /dev/null

    python scripts/validate_candidates.py \
      "$SEED_DIR/candidates.json" \
      --stage extrapolation \
      --points 4 \
      --distributions random reversed \
      --seed-limit 1 \
      --baseline-cache "$BASELINE_CACHE" \
      --output "$SEED_DIR/extrapolation.json" > /dev/null
  fi

  if [ "$RUN_FINAL" = "1" ]; then
    python scripts/validate_candidates.py \
      "$SEED_DIR/candidates.json" \
      --stage final_test \
      --allow-final-test \
      --points 4 \
      --distributions random reversed nearly_sorted duplicates blocks \
      --baseline-cache "$BASELINE_CACHE" \
      --output "$SEED_DIR/final-test.json" > /dev/null
  fi
}

GPU_COUNT="$(nvidia-smi --query-gpu=index --format=csv,noheader 2>/dev/null | wc -l || true)"
if [ "$DEVICE" = "cpu" ]; then
  GPU_COUNT=1
fi
if [ "$GPU_COUNT" -lt 1 ]; then
  echo "No visible GPU; falling back to CPU and one parallel seed."
  DEVICE=cpu
  GPU_COUNT=1
  MAX_PARALLEL=1
fi

PIDS=()
cleanup_jobs() {
  if [ "${#PIDS[@]}" -gt 0 ]; then
    kill "${PIDS[@]}" 2>/dev/null || true
  fi
}
trap cleanup_jobs INT TERM EXIT
for INDEX in "${!SEEDS[@]}"; do
  SEED="${SEEDS[$INDEX]}"
  GPU_INDEX=$((INDEX % GPU_COUNT))
  SEED_DIR="$RUN_ROOT/seed-$SEED"
  mkdir -p "$SEED_DIR"
  echo "Launching seed=$SEED on gpu=$GPU_INDEX; log=$SEED_DIR/run.log"
  (PYTHONUNBUFFERED=1 run_seed "$SEED" "$GPU_INDEX") > "$SEED_DIR/run.log" 2>&1 &
  PIDS+=("$!")
  while [ "${#PIDS[@]}" -ge "$MAX_PARALLEL" ]; do
    wait "${PIDS[0]}"
    PIDS=("${PIDS[@]:1}")
  done
done
for PID in "${PIDS[@]}"; do
  wait "$PID"
done
PIDS=()
trap - INT TERM EXIT

echo "[4/5] Aggregate results"
python scripts/summarize_experiments.py "$RUN_ROOT" --output "$RUN_ROOT/aggregate.json" > /dev/null

echo "[5/5] Complete"
echo "Results: $RUN_ROOT"
echo "Summary: $RUN_ROOT/aggregate.json"
if [ "$RUN_FINAL" != "1" ]; then
  echo "Final test was kept sealed. Run with RUN_FINAL=1 only for the final reported experiment."
fi
