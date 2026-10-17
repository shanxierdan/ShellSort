#!/usr/bin/env bash
set -euo pipefail

V3_TUNE_BROAD_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$V3_TUNE_BROAD_ROOT"

python scripts/evaluate_v3_tune.py result/v3_tune/v3_tune_candidates.json \
  --manifest data/v3_tune_manifest.json \
  --stage v3_tune_broad_test \
  --candidate-hash 0bf3db481aa61fb5ae5203fa45913e781307e22acd0f1771a5761d443de13f6b \
  --cache result/v3_tune/v3_tune_test_cost.sqlite \
  --output result/v3_tune/v3_tune_broad_test.json
