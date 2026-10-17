# v3_tune：证明约束下的有限前缀微调

## 1. 目标

`v3_tune` 不重新搜索生成器形式，也不继续训练 V3 Transformer。它固定 seed 4 候选已经证明的精确几何尾部：

```text
h_t = floor(alpha * (A/B)^t)
alpha = 420574650882923 / 7668945023518835
A/B   = 582942583375009 / 250000000000000
```

只把最小的 8 个正 gaps 替换为一个严格递增、包含 1 的有限前缀：

```text
P_8 = (1, p_1, ..., p_7),  p_7 < 1416
H_tune = P_8 union {h_t: h_t >= 1416}
```

原始前缀为：

```text
1, 3, 8, 20, 47, 111, 260, 607
```

`1416, 3303, 7703, ...` 以及其后的整个无限几何尾部不可修改。序列仍然是一个对所有 n 通用的固定无限序列，不按 n、输入分布或 baseline 动态切换。

## 2. 为什么不破坏证明

有限前缀替换只改变有限个 early passes。`docs/proof.md` 已把任意固定数量的 early passes 吸收到 O(N) 项；证明主导项来自完全不变的几何尾部和 10^1000 之后的单位伴随层。因此 `v3_tune` 候选继续拥有相同的：

```text
O(N^1.024296451657... * polylog(N))
```

渐近上界。代码会把精确 alpha、A/B、源程序 hash 和尾部写入每个候选；反序列化时任何尾部改动都会直接报错。

## 3. 自监督信号

微调目标仍然是每个公共任务上的真实成本：

```text
mean_T log((comparisons(H,T) + moves(H,T)) / (n log2(n+1)))
```

它不模仿 Tokuda、Ciura 或 Sedgewick，也不把 FINAL 结果作为标签。三条 baseline 和原始 V3 只在 Validation/Test 中报告相对差异。

当前参数空间只有 7 个有序整数，不再使用神经网络。约束进化搜索直接评价真实排序成本，逐轮缩小 mutation jitter，并使用 JSON checkpoint 与 SQLite 成本缓存恢复。

## 4. 数据隔离

| 阶段 | n | seed | 用途 |
|---|---:|---:|---|
| `v3_tune_search` | 100,000–3,000,000，6 点 | 300 | 微调 |
| `v3_tune_validation` | 3,000,001–10,000,000，4 点 | 400 | 冻结唯一候选 |
| `v3_tune_test` | 10,000,001–100,000,000，5 点 | 1999 | 新的一次性盲测 |

每个规模覆盖 random、reversed、nearly_sorted、duplicates、blocks。已经使用过的 FINAL seed 999 不参与 `v3_tune` 的搜索或选择。

## 5. 运行

完整链路检查：

```bash
bash scripts/run_experiments_v3_tune.sh smoke
```

中等规模检查：

```bash
bash scripts/run_experiments_v3_tune.sh pilot
```

正式微调与独立 Validation：

```bash
bash scripts/run_experiments_v3_tune.sh full
```

正式配置运行 24 轮；这是在首轮 16 轮结果的平台期之后继续 8 轮，使 mutation jitter 到达设计下限并检查局部收敛。

保持同一个 `V3_TUNE_RUN_ROOT` 重复运行会从 `v3_tune_checkpoint.json` 和两个 SQLite 缓存恢复。该流程主要运行 Numba Shellsort 计数，使用 CPU 与内存，不依赖 GPU。

一次性 Test 已经完成。以下命令现在只用于核对冻结候选和协议：

```bash
V3_TUNE_TEST_DRY_RUN=1 bash scripts/run_v3_tune_test.sh
```

正式运行命令及其签名已经消费，不应通过修改候选或 manifest 再次打开：

```bash
RUN_V3_TUNE_TEST=1 bash scripts/run_v3_tune_test.sh
```

## 6. 产物

正式默认目录为 `result/v3_tune/`：

```text
v3_tune_config.json
v3_tune_checkpoint.json
v3_tune_metrics.json
v3_tune_candidates.json
v3_tune_validation.json
v3_tune_selected.json
v3_tune_cost.sqlite
v3_tune_validation_cost.sqlite
v3_tune_test.json
v3_tune_test_cost.sqlite
v3_tune_test_status.json
```

`v3_tune_selected.json` 只由独立 Validation 冻结；baseline 不参与其训练目标。`v3_tune_test.json` 一旦以某个签名生成，代码拒绝用不同候选或协议覆盖。

## 7. 最终结果与归档状态

冻结候选为：

```text
1, 3, 8, 20, 47, 116, 300, 585, 1416, 3303, 7703, ...
candidate hash = 0bf3db481aa61fb5ae5203fa45913e781307e22acd0f1771a5761d443de13f6b
```

seed 1999 一次性 Test 完成25个任务，零截断。按预注册等任务几何平均指标：

| 对手 | 相对操作数 | 胜出任务 |
|---|---:|---:|
| 原始 V3 | -0.271% | 23/25 |
| Sedgewick | -1.793% | 21/25 |
| Tokuda | -0.079% | 5/25 |
| Ciura | -0.086% | 4/25 |

`success=true`。相对 Tokuda/Ciura 的综合收益主要来自 reversed；分布拆分和 `n=10^8` 数据作为性能画像与权重敏感性分析，不构成额外否决条件。完整口径、分布表、加权汇总和停止决定见 [v3_tune 实验归档](../result/v3_tune/exp_v3_tune.md)。本版本已经归档，不再使用 seed 1999 调参。
