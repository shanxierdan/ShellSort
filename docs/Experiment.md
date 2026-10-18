# Experiment: executable gap discovery and final evaluation

## Objective

The experiment asks whether execution-guided self-supervision can discover one
compact Shellsort gap generator that generalizes across input sizes and remains
mathematically analyzable.  The optimization target is the exact number of
comparisons and moves; classical sequences never serve as labels.

## Discovery

The search evaluates complete, valid-by-construction generator programs on a
common panel of sizes and distributions.  The learned proposal model receives
program tokens, realized gaps, per-pass costs, and deletion counterfactuals.
Its losses predict absolute cost, useful mutation classes, ranking, and local
gap contribution.  Random proposals remain active throughout search.

Five independent seeds run for 120 iterations.  Validation uses unseen sizes
and seeds to select one program per run, after which extrapolation tests the
selected programs at larger sizes.  The frozen source program is stored in
`result/discovery/selected-programs.json`.

## Proof-constrained finite-prefix tuning

The discovered rational-geometric tail is held fixed.  The tuner changes only
the smallest eight gaps, so every candidate is legal, executable, and covered
by the same asymptotic proof.  It uses no baseline-relative reward.

| Stage | Sizes | Seed | Role |
|---|---:|---:|---|
| Search | 100,000--3,000,000 | 300 | optimize the finite prefix |
| Validation | 3,000,001--10,000,000 | 400 | freeze one candidate |
| Test | 10,000,001--100,000,000 | 1999 | one-time evaluation |

Every size contains random, reversed, nearly sorted, duplicate-heavy, and block
inputs.  Exact comparisons and moves are cached in SQLite.  Evaluation files
carry a signature over the candidate, task panel, array generator, and baseline
sequences; a sealed test with a different signature cannot be overwritten.

## Metrics and decision rule

For task \(t\), total work is

\[
C_t=C_{\mathrm{cmp},t}+C_{\mathrm{move},t}.
\]

Cross-size reporting uses the equal-task mean log ratio

\[
R_b=\frac1{|\mathcal T|}\sum_{t\in\mathcal T}
\log\frac{C_t+1}{C_{b,t}+1}.
\]

The frozen candidate passes when no task is censored and \(R_b<0\) separately
for Sedgewick, Tokuda, and Ciura.  A broader report additionally includes Shell,
Hibbard, Knuth, and Pratt.

## Reproduction

```bash
bash scripts/run_discovery.sh smoke
bash scripts/run_tuning.sh smoke
TUNING_TEST_DRY_RUN=1 bash scripts/run_final_test.sh
python scripts/summarize_paper_broad_test.py
```

The authoritative task definitions are `data/discovery_manifest.json` and
`data/experiment_manifest.json`.
