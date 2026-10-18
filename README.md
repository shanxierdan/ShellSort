# Shellsort Gap Discovery

This repository contains the complete implementation and frozen artifacts for
the paper **A New Gap Sequence for Shellsort: RL-Driven Algorithm Discovery
Beyond \(N^{4/3}\)**.

The system searches directly over bounded executable gap-generator programs,
evaluates them with exact Shellsort comparison and move counts, and learns its
proposal policy from execution traces.  After discovery, a proof-constrained
self-supervised tuner changes only a finite low-gap prefix while preserving the
geometric tail used by the complexity proof.

The final practical sequence starts with

```text
1, 3, 8, 20, 47, 116, 300, 585, 1416, 3303, ...
```

For larger terms it uses the exact rational-geometric backbone defined in
[`core/tuning.py`](core/tuning.py).  The proof-only unit companions begin above
the guard threshold \(10^{1000}\), so they never occur in practical evaluation.

## Results

On the frozen panel of 25 tasks with \(10^7 < N \le 10^8\), the final candidate
has the lowest equal-task geometric-mean total operation count among Shell,
Hibbard, Knuth, Pratt, Sedgewick, Tokuda, and Ciura.  Against the three strongest
practical baselines, its mean log operation ratios correspond to reductions of
1.793% versus Sedgewick, 0.079% versus Tokuda, and 0.086% versus Ciura.

The frozen task-level measurements are in
[`result/final/benchmark.json`](result/final/benchmark.json).  Reconstruct the
paper table with:

```bash
python scripts/summarize_paper_broad_test.py
```

## Installation

Python 3.11 or newer is required.

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e '.[train,dev,perf]'
```

CUDA is optional.  Neural search uses it when available; exact sorting and
final evaluation are CPU workloads.

## Reproduction

Run the test suite:

```bash
PYTHONPATH=. pytest -q
```

Run a small end-to-end discovery check:

```bash
bash scripts/run_discovery.sh smoke
```

Run proof-constrained prefix tuning:

```bash
bash scripts/run_tuning.sh smoke
```

The frozen final test is protected against accidental execution and overwrite:

```bash
TUNING_TEST_DRY_RUN=1 bash scripts/run_final_test.sh
RUN_TUNING_TEST=1 bash scripts/run_final_test.sh
```

The full commands, expected files, and resource notes are in
[`REPRODUCIBILITY.md`](REPRODUCIBILITY.md).

## Repository structure

```text
core/       executable program language, search, tuning, and exact evaluation
model/      program/trace encoder and self-supervised training
scripts/    discovery, tuning, final evaluation, and proof audits
data/       frozen task-panel manifests
result/     selected programs and frozen final measurements
docs/       method, experiment protocol, and complete proof
paper/      manuscript source
tests/      unit and integration tests for the released pipeline
```

The main method is documented in [`docs/Method.md`](docs/Method.md), the final
experimental protocol in [`docs/Experiment.md`](docs/Experiment.md), and the
complexity proof in [`docs/proof.md`](docs/proof.md).

## License

Released under the [MIT License](LICENSE).
