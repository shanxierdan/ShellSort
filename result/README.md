# Results

Each experiment writes to `result/<run_id>/`. Generated checkpoints, caches and metrics are ignored by Git; promote only compact frozen candidate programs and final reports deliberately.

`v3_tune` profiles use isolated defaults: `result/v3_tune_smoke/`, `result/v3_tune_pilot/`, and `result/v3_tune/` for the formal run. Their artifacts consistently use the `v3_tune` prefix and never overwrite `result/v3/`. The formal run and one-time Test are complete; its authoritative narrative is `result/v3_tune/exp_v3_tune.md`.
