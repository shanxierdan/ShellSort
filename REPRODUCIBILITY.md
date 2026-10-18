# Reproducibility

## Environment

The supported runtime is Python 3.11 or newer.  Install all released components
with:

```bash
python -m pip install -e '.[train,dev,perf]'
```

PyTorch is required for discovery.  Numba accelerates exact operation counting.
CUDA is optional and is not used by the frozen final benchmark.

## Fast verification

```bash
PYTHONPATH=. pytest -q
python scripts/summarize_paper_broad_test.py
```

The first command verifies program generation, search, checkpointing, exact
cost caching, tuning constraints, sealed evaluation, and the proof-audit code.
The second reconstructs the empirical table directly from task-level counts.

## Frozen artifacts

- `result/discovery/selected-programs.json`: validation-selected executable
  generator programs;
- `result/final/candidates.json`: proof-compatible finite-prefix candidates;
- `result/final/selected.json`: candidate frozen by independent validation;
- `result/final/validation.json`: independent validation measurements;
- `result/final/test.json`: sealed test against the three strongest practical
  baselines;
- `result/final/benchmark.json`: task-level comparison with all seven classical
  baselines used in the paper.

## Discovery

Smoke test:

```bash
bash scripts/run_discovery.sh smoke
```

Full search:

```bash
DEVICE=cuda RUN_ROOT=result/discovery-reproduction \
  bash scripts/run_discovery.sh full
```

Each seed writes atomic checkpoints and uses a shared SQLite cost cache.  The
validation and extrapolation panels are defined in
`data/discovery_manifest.json`.

## Proof-constrained tuning

Smoke test:

```bash
bash scripts/run_tuning.sh smoke
```

Full tuning and independent validation:

```bash
TUNING_RUN_ROOT=result/final-reproduction bash scripts/run_tuning.sh full
```

The search, validation, test, and benchmark panels are fixed in
`data/experiment_manifest.json`.  Search and validation use distinct seeds.
Classical baselines are report-only and do not enter the tuning objective.

The one-time test is sealed by default:

```bash
TUNING_TEST_DRY_RUN=1 bash scripts/run_final_test.sh
RUN_TUNING_TEST=1 bash scripts/run_final_test.sh
```

If an existing test artifact has a different protocol signature, the evaluator
refuses to overwrite it.

## Proof audits

```bash
python scripts/analyze_complexity.py
python scripts/analyze_number_theory.py
python scripts/analyze_carry_intervals.py --include-small-model-demo
PYTHONPATH=. pytest -q tests/test_proof_completion.py \
  tests/test_carry_intervals.py \
  tests/test_generalized_holes.py \
  tests/test_lattice_relations.py
```

These finite audits support the formal argument but do not replace it.  The
complete proof and its citation map are in `docs/proof.md` and
`docs/proof_citation_map.md`.
