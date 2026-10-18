# Proof-constrained finite-prefix tuning

The final tuning stage preserves the exact geometric tail

\[
h_s=\left\lfloor
\frac{420574650882923}{7668945023518835}
\left(\frac{582942583375009}{250000000000000}\right)^s
\right\rfloor
\]

and changes only the first eight positive gaps.  The frozen practical prefix is

```text
1, 3, 8, 20, 47, 116, 300, 585
```

Because the change is finite, it adds only finitely many early passes and does
not alter the proved asymptotic exponent.  The tuner performs constrained
integer mutations, evaluates exact comparisons and moves, and selects by
censoring count, mean normalized log cost, total operations, and a deterministic
hash tie-breaker.

Search, validation, and test use distinct seeds.  Sedgewick, Tokuda, and Ciura
are report-only baselines; they do not enter the search objective.  The final
candidate and all frozen measurements are in `result/final/`.

```bash
bash scripts/run_tuning.sh full
TUNING_TEST_DRY_RUN=1 bash scripts/run_final_test.sh
RUN_TUNING_TEST=1 bash scripts/run_final_test.sh
```

The one-time test refuses to overwrite an existing result when its protocol
signature differs.
