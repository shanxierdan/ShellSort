#!/usr/bin/env bash
set -euo pipefail

TUNING_BROAD_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$TUNING_BROAD_ROOT"

python scripts/evaluate_final.py result/final/candidates.json \
  --manifest data/experiment_manifest.json \
  --stage benchmark \
  --candidate-hash 88c74cbecc0d3181ad6f51459f4fb7d84ba4da2e6358e4545756599f7bfa74d7 \
  --cache result/final/test_cost.sqlite \
  --output result/final/benchmark.json
