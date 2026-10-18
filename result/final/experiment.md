# Final experiment archive

## Frozen candidate

The complete search, independent validation, candidate freeze, sealed test, and
broad benchmark are finished.  The practical prefix is

```text
1, 3, 8, 20, 47, 116, 300, 585
```

and the exact rational-geometric tail is unchanged from the discovered source
program.  The released candidate hash is

```text
88c74cbecc0d3181ad6f51459f4fb7d84ba4da2e6358e4545756599f7bfa74d7
```

## Search behavior

The finite-prefix tuner completed 24 iterations and evaluated 311 candidates.
The selected prefix first became the search winner at iteration 12.  A nearby
candidate briefly improved the search objective at iteration 18, but independent
validation rejected that change and froze the prefix above.  The mutation scale
reached its minimum at iteration 20, and the remaining iterations did not change
the search winner.  These records are stored in `metrics.json` and
`candidates.json`.

## Independent validation

Validation used six sizes from 3,000,001 through 10,000,000, five distributions,
and seed 400.  All candidate tasks completed without censoring.  The frozen
prefix reduced aggregate comparisons by 0.180%, moves by 0.399%, and total
operations by 0.271% relative to the untuned geometric backbone.

## Sealed test

The one-time test used five logarithmic sizes with
\(10^7<N\le10^8\), five distributions, and seed 1999.  It contains 25 equal-
weight tasks and no censored result.

| Baseline | Mean total-operation reduction | Tasks won |
|---|---:|---:|
| Sedgewick | 1.793% | 21/25 |
| Tokuda | 0.079% | 16/25 |
| Ciura | 0.086% | 18/25 |
| Untuned geometric backbone | 0.271% | 23/25 |

The candidate therefore passes the preregistered rule: zero censoring and a
negative equal-task mean log operation ratio against each of Sedgewick, Tokuda,
and Ciura.  The rule evaluates the random task ensemble as a whole; distribution
and size splits are explanatory rather than additional all-win requirements.

## Broad comparison

The post-freeze benchmark evaluates the unchanged candidate on the same 25
tasks against seven classical sequences.  It has the lowest geometric-mean
total operation count among Shell, Hibbard, Knuth, Pratt, Sedgewick, Tokuda,
and Ciura.  All task-level comparisons and moves are in `benchmark.json` and
can be summarized with:

```bash
python scripts/summarize_paper_broad_test.py
```

## Theory compatibility

Only a finite prefix was changed.  The geometric tail and the proof-only unit
companions above the guard threshold remain fixed, so the asymptotic bound is
unchanged:

\[
\Omega\!\left(N^{1.024296451657\ldots}\right)
\le T(N)\le
O\!\left(N^{1.024296451657\ldots}\operatorname{polylog}N\right).
\]

The formal argument is in `docs/proof.md`.

## Released artifacts

- `config.json`: frozen search configuration;
- `metrics.json`: iteration-level search trajectory;
- `candidates.json`: exported candidates and exact search scores;
- `validation.json`: independent validation reports;
- `selected.json`: authoritative frozen candidate;
- `test.json`: sealed three-baseline test;
- `benchmark.json`: seven-baseline task-level comparison;
- `archive.json`: compact completion and decision record.
