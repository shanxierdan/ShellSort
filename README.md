# ShellSort Generator Discovery

Reference implementation and frozen evaluation artifacts for **A New Gap
Sequence for Shellsort: RL-Driven Algorithm Discovery Beyond $N^{4/3}$**
([arXiv:2609.29881](https://arxiv.org/abs/2609.29881)).

The repository contains the executable generator-search system, the final
finite-prefix tuner, exact comparison/move evaluation, classical baselines,
proof diagnostics, tests, immutable task manifests, and the compact artifacts
used to produce the paper's empirical tables. Large generated arrays,
checkpoints, and SQLite caches are intentionally excluded.

## Quick verification

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e '.[dev,train,perf]'
python -m pytest
python scripts/summarize_paper_broad_test.py
```

The test suite checks the search representation, exact Shellsort counters,
frozen candidate protocol, and executable identities used by the proof. The
summary command reconstructs the values in the paper's broad-test table from
`result/v3_tune/v3_tune_broad_test.json`.

For the complete artifact map and commands for discovery, tuning, evaluation,
and proof checks, see [REPRODUCIBILITY.md](REPRODUCIBILITY.md).

## Project structure

- `core/`: Shellsort, baselines, generator language, search, and evaluation.
- `model/`: learned proposal and program--behavior models.
- `scripts/`: discovery, tuning, evaluation, and analysis entry points.
- `data/`: immutable task and seed manifests; arrays are generated on demand.
- `result/`: compact frozen outputs used by the paper (large caches excluded).
- `tests/`: unit, integration, and proof-completion tests.
- `docs/`: method, experiment, result, and proof records.
- `paper/`: manuscript source.

The code is released under the MIT License.

## Development history (Chinese)

本项目研究如何从 Shellsort 执行轨迹中发现可泛化、可解释的 gap generator。V3 已完成开放形式发现并冻结；当前 `v3_tune` 在不改变已证明几何尾部的条件下微调有限低位 gaps。研究方法见 [Method](docs/Method.md)，实验协议见 [Experiment](docs/Experiment.md)，微调协议见 [v3_tune](docs/v3_tune.md)，V1/V2/V3 结论见 [实验结果](docs/实验结果.md)。最终理论入口是 [有限前缀保持的完整上界证明](docs/proof.md)，引用审计见 [proof citation map](docs/proof_citation_map.md)。

## 架构

- `core/`：Shellsort、基线、DSL、生成器、评测与搜索；
- `model/`：V1/V2 legacy 网络和 V3 程序—行为联合模型；
- `data/`：数据划分与 seed manifest；
- `scripts/`：命令行入口；
- `result/`：实验产物；
- `tests/`：单元测试与集成测试。

## V1 复现入口

```bash
python -m unittest discover -s tests -v
python scripts/benchmark_baselines.py --n 128 --seed 7
python scripts/run_search.py --budget 100 --seed 7 --run-dir result/smoke
python scripts/run_neural_search.py --run-dir result/neural --device auto
```

以下命令属于已经归档的 V1 AST/PUCT 实现，用于重放而不是当前方法定义。`--device auto` 在运行环境可见 CUDA 时使用 GPU，否则使用 CPU。

冻结候选可以独立验证和分析：

```bash
python scripts/validate_candidates.py result/neural/candidates.json --stage validation
python scripts/analyze_candidates.py result/neural/candidates.json --output result/neural/analysis.json
```

## V1 一键实验（历史）

```bash
# 数秒级全链路检查
bash scripts/run_experiments.sh smoke

# 正式训练前的三 seed pilot
bash scripts/run_experiments.sh pilot

# 五 seed 主实验；运行时间可能很长
bash scripts/run_experiments.sh full
```

通过环境变量选择设备和输出位置：

```bash
DEVICE=cuda RUN_ROOT=result/main bash scripts/run_experiments.sh full
```

Final Test 默认保持封闭。只有最终论文实验才执行：

```bash
RUN_FINAL=1 DEVICE=cuda bash scripts/run_experiments.sh full
```

运行中可查看每个 seed 的逐轮日志：

```bash
tail -f result/<run-id>/seed-0/run.log
```

实验每轮保存 checkpoint；使用相同 `RUN_ROOT` 重新执行会自动从已完成的 iteration 继续。正式配置会将 5 个 seed 自动分配到不同的可见 GPU，并共享 `baseline-cache.sqlite`。

在 8×RTX 3090 宿主机上的单元吞吐测试中，2 个 episode、每步32次 MCTS simulation 约需21秒。当前 `full` 配置预计5个 seed 并行约需9–15小时，另加冻结候选的 Promote/Confirm/外推时间。实际时间取决于合法候选数量和共享缓存命中率。

## V2 运行入口

V2 已实现合法 gap sequence 编辑、Numba 逐 pass trace、绝对成本缓存、sequence 多任务模型、公共面板群体搜索、跨规模候选、符号蒸馏和原子 checkpoint：

```bash
# CPU 数十秒级全链路检查
bash scripts/run_experiments_v2.sh smoke

# 三 seed pilot
DEVICE=cuda RUN_ROOT=result/v2-pilot bash scripts/run_experiments_v2.sh pilot

# 五 seed 正式搜索
DEVICE=cuda RUN_ROOT=result/v2-main bash scripts/run_experiments_v2.sh full
```

恢复运行只需保持相同的 `RUN_ROOT`。Final Test 默认封闭，仅在最终预注册实验中设置 `RUN_FINAL=1`。

单独执行、蒸馏和验证：

```bash
python scripts/run_v2.py --run-dir result/v2-debug --device auto --resume
python scripts/distill_v2.py result/v2-debug/candidates-v2.json --output result/v2-debug/distilled-v2.json
python scripts/evaluate_v2.py result/v2-debug/candidates-v2.json --stage validation --output result/v2-debug/validation-v2.json
```

V2 已归档，不再作为当前正式搜索入口。

## V3 当前入口

```bash
# CPU 全链路检查
bash scripts/run_experiments_v3.sh smoke

# 三 seed pilot
DEVICE=cuda RUN_ROOT=result/v3-pilot bash scripts/run_experiments_v3.sh pilot

# pilot 审查通过后再运行五 seed full
DEVICE=cuda RUN_ROOT=result/v3-main bash scripts/run_experiments_v3.sh full
```

保持同一 `RUN_ROOT` 重复命令即可恢复。Final Test 默认封闭。

若训练已经完成而只需恢复冻结评测：

```bash
RUN_ROOT=result/v3 bash scripts/run_evaluations_v3.sh
```

最终盲测有独立入口，不会重新训练、重新 Validation 或重新选择候选。它只评测冻结的 seed 4 主候选，在 1,000 万到 1 亿规模上与三条强基线比较：

```bash
RUN_FINAL=1 RUN_ROOT=result/v3 bash scripts/run_final_test_v3.sh
```

该流程使用紧凑大数组、逐成本 SQLite 恢复和不可覆盖的评测签名。完整冻结协议见 [Experiment](docs/Experiment.md)。

评测使用跨 seed 共享的 SQLite 成本缓存，并在每个候选后原子保存进度。Validation 对每个 seed 冻结一个候选；Extrapolation 只评这些冻结候选，不会重新评完整 archive。

V3 已归档。复现冻结后的经验复杂度和有限数论诊断：

```bash
python scripts/analyze_v3_complexity.py
python scripts/analyze_v3_number_theory.py
python scripts/analyze_v3_carry_intervals.py --include-small-model-demo
```

这些命令只读取已完成结果或精确符号序列，不开启 Final Test。有限诊断不承担渐近证明；完整证明见 [proof.md](docs/proof.md)。

## v3_tune 归档与复现入口

`v3_tune` 固定 V3 的精确 `alpha`、`A/B` 和整个几何尾部，只搜索最小 8 个 gaps。正式开发规模扩展到 300 万，独立 Validation 扩展到 1000 万：

```bash
# 完整流程检查
bash scripts/run_experiments_v3_tune.sh smoke

# 正式微调；可用相同目录自动恢复
bash scripts/run_experiments_v3_tune.sh full
```

seed 1999 一次性 Test 已经完成；以下 dry-run 只核对冻结协议，正式结果不得通过更换候选或 manifest 覆盖：

```bash
V3_TUNE_TEST_DRY_RUN=1 bash scripts/run_v3_tune_test.sh
RUN_V3_TUNE_TEST=1 bash scripts/run_v3_tune_test.sh
```

最终候选前缀为 `1,3,8,20,47,116,300,585`。它在一次性 Test 的预注册综合平均指标上相对 Sedgewick、Tokuda、Ciura分别减少1.793%、0.079%、0.086%，严格规则通过。分布与规模拆分用于解释收益来源，不另设逐项全胜门槛。搜索使用精确 Numba 操作计数和 SQLite 缓存，主要消耗 CPU 与内存，不使用 GPU。协议见 [v3_tune](docs/v3_tune.md)，完整结论见 [v3_tune 实验归档](result/v3_tune/exp_v3_tune.md)。
