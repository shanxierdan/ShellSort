# Reproducibility guide

This repository separates inexpensive verification from the computationally
heavy discovery runs. Benchmark arrays are generated deterministically from
the manifests in `data/`; no private dataset is required.

## Environment

Python 3.11 or newer is supported. A CPU-only environment is enough for exact
evaluation and prefix tuning. CUDA is optional for the neural discovery stage.

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e '.[dev,train,perf]'
```

## Fast checks

Run all unit, integration, and proof-completion tests:

```bash
python -m pytest
```

Reconstruct the broad empirical table from the frozen task-level counts:

```bash
python scripts/summarize_paper_broad_test.py
```

The authoritative inputs are:

- `result/v3/selected-v3.json`: validation-frozen V3 programs;
- `result/v3_tune/v3_tune_selected.json`: frozen finite prefix;
- `result/v3_tune/v3_tune_validation.json`: independent validation results;
- `result/v3_tune/v3_tune_test.json`: one-time test against the three strongest
  practical baselines;
- `result/v3_tune/v3_tune_broad_test.json`: task-level counts for all seven
  classical baselines in the paper.

## Generator discovery

Use a smoke run to verify the complete V3 pipeline:

```bash
bash scripts/run_experiments_v3.sh smoke
```

The five-seed discovery experiment is:

```bash
DEVICE=cuda RUN_ROOT=result/v3-reproduction \
  bash scripts/run_experiments_v3.sh full
```

This stage is computationally expensive and writes checkpoints and SQLite
caches under `result/`; those generated files are ignored by Git.

## Frozen-tail prefix tuning

The smoke and full tuning workflows are:

```bash
bash scripts/run_experiments_v3_tune.sh smoke
V3_TUNE_RUN_ROOT=result/v3_tune_reproduction \
  bash scripts/run_experiments_v3_tune.sh full
```

The one-time paper test used the immutable panel in
`data/v3_tune_manifest.json`. The repository publishes its frozen output; do
not use the test panel for candidate selection.

## Proof-oriented checks

The executable checks supporting the exact sequence definition and algebraic
identities are available through:

```bash
python -m pytest tests/test_proof_completion.py \
  tests/test_v3_carry_intervals.py \
  tests/test_v3_generalized_holes.py \
  tests/test_v3_lattice_relations.py
```

Finite diagnostics can be regenerated with:

```bash
python scripts/analyze_v3_complexity.py
python scripts/analyze_v3_number_theory.py
python scripts/analyze_v3_carry_intervals.py --include-small-model-demo
```

These computations check identities and finite instances; the asymptotic proof
is in `paper/theory_summary.tex` and `paper/theory.tex`.

## Artifact policy

Committed JSON files contain frozen programs, manifests, and task-level counts
needed to audit the paper. Generated arrays, model checkpoints, logs, and
SQLite caches are excluded because they are large and reproducible. No secret
test data or proprietary dependency is required.
