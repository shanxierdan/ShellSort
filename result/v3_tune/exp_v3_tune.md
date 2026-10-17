# v3_tune 实验归档：证明约束下的有限前缀微调

## 1. 归档结论

`v3_tune` 已完成24轮正式搜索、独立 Validation、候选冻结和一次性 Test。全部任务零截断，最终状态为 `complete`。

正式结论是：

> 在完全固定 V3 精确几何尾部和渐近增广结构的条件下，只微调最小8个 gaps，能够稳定降低原始 V3 的 comparisons 与 moves。冻结候选在从未参与搜索或选择的 seed 1999 Test 上，相对 Sedgewick、Tokuda、Ciura 的等任务平均 log 操作数比均为负，因此通过预注册成功规则。

综合评价是本实验预先确定的目标，而不是要求每个子分布逐项支配。候选相对 Tokuda、Ciura 的平均优势约为0.08%；不同分布上的正负差异构成性能画像，不改变综合指标已经获胜的主结论。

本版本至此归档。seed 1999 Test 已消费，不再用它调整前缀、选择候选或覆盖结果；任何新的搜索目标必须使用新版本和新测试面板。

---

## 2. 从 V3 到 v3_tune

原始 V3 候选的正 gaps 为：

```text
1, 3, 8, 20, 47, 111, 260, 607, 1416, 3303,
7703, 17963, 41887, 97670, 227746, 531052, ...
```

其精确几何骨架为：

```text
h_t = floor(alpha * (A/B)^t)
alpha = 420574650882923 / 7668945023518835
A/B   = 582942583375009 / 250000000000000
```

原始 FINAL 在 seed 999 上相对 Sedgewick 减少1.579%，但相对 Tokuda、Ciura分别增加0.113%、0.122%。分项显示它相对 Tokuda comparisons 少0.177%，moves 却多2.015%。因此 `v3_tune` 不重新搜索生成器形式，只处理有限低位 gaps 的移动成本。

候选族固定为：

```text
H_tune = P_8 union {h_t : h_t >= 1416}
P_8 = (1, p_1, ..., p_7), strictly increasing, p_7 < 1416
```

从 `1416` 起的整个无限尾部、精确 `alpha`、`A/B` 和 `10^1000` 后的证明增广均不可修改。

---

## 3. 方法与数据隔离

搜索目标是公共任务上的真实自监督成本：

```text
mean_T log((comparisons(H,T) + moves(H,T)) / (n log2(n+1)))
```

Tokuda、Ciura、Sedgewick 不参与训练目标，只用于冻结后的报告。由于参数空间只有7个有序整数，正式实现使用可恢复的约束进化搜索，而不继续训练 V3 Transformer。

| 阶段 | n | seed | 任务数 | 是否参与选择 |
|---|---:|---:|---:|---|
| Search | 100,000–3,000,000，6点 | 300 | 30 | 是 |
| Validation | 3,000,001–10,000,000，4点 | 400 | 20 | 冻结唯一候选 |
| Test | 10,000,001–100,000,000，5点 | 1999 | 25 | 否，一次性报告 |

每个规模均包含 random、reversed、nearly_sorted、duplicates、blocks。所有阶段使用 `numpy_pcg64_v1` 紧凑数组和精确 Numba comparisons/moves 计数。

Test 的预注册成功规则为：

```text
zero censored tasks
and mean_T log((cost(candidate,T)+1)/(cost(B,T)+1)) < 0
for every B in {Sedgewick, Tokuda, Ciura}
```

每个任务等权；百分比统一按 `100 * (exp(mean_log_ratio) - 1)` 换算。

---

## 4. 搜索与收敛

正式搜索完成24/24轮，共真实评价311个候选，即 `311 × 30 = 9,330` 个候选—任务成本。全部无 censor。

| 首次出现轮次 | 当前 Search winner 前缀 | Search 目标 |
|---:|---|---:|
| 1 | `1,3,8,20,47,111,260,607` | 0.816322390 |
| 7 | `1,3,8,18,47,111,260,607` | 0.815957723 |
| 9 | `1,3,8,19,47,111,260,607` | 0.815755601 |
| 12 | `1,3,8,20,47,116,300,585` | 0.814521854 |
| 18 | `1,3,8,19,47,116,299,585` | 0.814235845 |

第20轮 mutation jitter 达到设计下限1.5%，第18轮后连续6轮未刷新 Search winner。第18轮 Search winner 在 Validation 上比第12轮候选高0.040%总操作数；Validation 因此拒绝该轻微 Search 过拟合，仍选择第12轮候选。这给出了比单纯训练平台更强的停止依据。

---

## 5. 冻结候选

```text
candidate hash = 0bf3db481aa61fb5ae5203fa45913e781307e22acd0f1771a5761d443de13f6b
source V3 hash = f8e20407ede6a625fff7e6fb2c9f093bb026fc0ea8ddd87cea821525891e731c
```

最终无限序列为：

```text
1, 3, 8, 20, 47, 116, 300, 585, 1416, 3303,
7703, 17963, 41887, 97670, 227746, 531052, ...
```

只发生三项有限修改：

```text
111 -> 116
260 -> 300
607 -> 585
```

Validation panel hash：

```text
b38f99208a48d800493d46030254dad14096bfc933bcc151142b34beaf2df297
```

Validation signature：

```text
15693527dd4780f2143a8d76734ecb9b6a6d1d9d3d834d415256ce8901b94274
```

---

## 6. 独立 Validation

20个 Validation 任务的等任务几何平均结果：

| 对手 | 相对操作数 | 胜出任务 |
|---|---:|---:|
| 原始 V3 | **-0.304%** | 16/20 |
| Sedgewick | **-1.390%** | 16/20 |
| Tokuda | **-0.678%** | 4/20 |
| Ciura | **-0.592%** | 9/20 |

相对原始 V3 的直接汇总结果为 comparisons -0.180%、moves -0.399%、总操作数 -0.271%。微调没有用更多移动换取更少比较，而是同时改善两项。

Validation 同时表明收益在不同输入结构间并不均匀：相对 Tokuda 的4次胜出来自 reversed。该分解用于解释综合收益来源；正式选择规则仍是预注册的等任务平均，而不是逐任务胜率。

---

## 7. 一次性 Test

Test panel hash：

```text
dafb7ca38590551e5ffbd6323e7f79bace251399e84186942cfe259fa7c61469
```

Test signature：

```text
8f49bf76496ebd18db3f84f4263cf2fde6c22cff81fee3170c7c2af42fd592f6
```

评测完成125个新成本项：25个任务 ×（原始 V3、Sedgewick、Tokuda、Ciura、冻结候选），缓存命中为0，零截断。预注册主结果为：

| 对手 | 等任务几何平均相对操作数 | 胜出任务 |
|---|---:|---:|
| 原始 V3 | **-0.271%** | 23/25 |
| Sedgewick | **-1.793%** | 21/25 |
| Tokuda | **-0.079%** | 5/25 |
| Ciura | **-0.086%** | 4/25 |

因此：

```text
success = true
zero_censored_tasks = true
beats_every_strong_baseline = true
```

相对原始 V3，Test 汇总 comparisons 下降0.199%、moves下降0.397%、总操作数下降0.282%。微调效果从 seed 400 Validation 泛化到完全未见的 seed 1999。

### 按分布

| 分布 | vs 原始 V3 | vs Sedgewick | vs Tokuda | vs Ciura |
|---|---:|---:|---:|---:|
| random | -0.394% | -1.567% | +1.187% | +0.561% |
| reversed | -0.422% | -1.239% | -4.843% | -3.995% |
| nearly_sorted | -0.444% | -1.734% | +0.872% | +0.226% |
| duplicates | -0.040% | +0.878% | +0.773% | +1.402% |
| blocks | -0.056% | -5.205% | +1.766% | +1.482% |

相对 Tokuda、Ciura 的综合优势主要由 reversed 上的大幅收益贡献；其他分布提供了互补的性能画像。实验目标从未要求各子分布分别获胜。

### 大规模与加权汇总

在 `n = 100,000,000` 的5分布等权平均上，候选相对原始 V3、Sedgewick、Tokuda、Ciura分别为：

```text
-0.281%, -2.030%, +0.302%, +1.071%
```

若不再让任务等权，而把25个任务的所有操作直接相加，大 n 将获得更高权重，结果为：

| 对手 | 汇总总操作数差异 |
|---|---:|
| 原始 V3 | -0.282% |
| Sedgewick | -2.317% |
| Tokuda | +0.538% |
| Ciura | +0.433% |

这不是预注册主指标，只是一项权重敏感性分析。正式结论仍由预先冻结的等任务平均给出；若未来改用“大 n 权重更高”的目标，那应当被视为不同实验问题。

### 冻结后的广基线补充评测

论文写作阶段，在不改变候选、任务、数组生成器和原始 Test 判据的前提下，补测了 Shell、Hibbard、Knuth、Pratt。原始缓存中的125项成本全部复用，新增100项精确成本；候选没有重新选择。下表中的正数表示该序列比最终候选使用更多操作：

| 序列 | comparisons | moves | 全部任务总操作 | reversed总操作 |
|---|---:|---:|---:|---:|
| 最终候选 | +0.000% | +0.000% | +0.000% | +0.000% |
| Tokuda | +0.715% | -0.758% | +0.079% | +5.089% |
| Ciura | +0.116% | +0.146% | +0.086% | +4.161% |
| 原始 V3 | +0.183% | +0.413% | +0.272% | +0.424% |
| Sedgewick | +4.054% | -1.708% | +1.826% | +1.255% |
| Hibbard | +137.700% | +172.234% | +153.074% | +8.416% |
| Knuth | +139.971% | +209.087% | +168.024% | -2.034% |
| Shell | +160.168% | +218.418% | +183.549% | +44.726% |
| Pratt | +481.099% | -19.733% | +280.814% | +400.424% |

最终候选在25任务等权总操作指标上优于全部七条经典基线。完整产物为 `result/v3_tune/v3_tune_broad_test.json`，复现入口为 `scripts/run_v3_tune_broad_test.sh`。

---

## 8. 理论状态

`v3_tune` 没有改变精确几何尾部，只替换有限个 early gaps。对渐近补全后的算法，每个固定 early pass 在单位伴随层生效后具有固定 conductor，成本为 O(N)；有限求和仍为 O(N)。因此有限前缀替换不改变 `docs/proof.md` 的主指数：

```text
O(N^1.024296451657... * polylog(N))
```

该结论仍属于带零密度单位伴随层的有限前缀保持渐近补全，不应误写成未经增广的纯序列上界。Test 只执行实际有限前缀，不执行 `10^1000` 后的证明辅助 gaps。

---

## 9. 最终判断与停止条件

### 已经成立

- 证明兼容的有限前缀微调可以同时降低 comparisons 与 moves；
- 改进在独立 Validation 和一次性 Test 上都超过原始 V3；
- 按预注册等任务平均规则，Test 同时超过三条强基线；
- 精确几何尾部和已证明渐近指数不变。

### 口径说明

- 本实验评价的是预注册的跨规模、跨分布综合平均，不采用逐任务全胜标准；
- 分布表和大 n 加权汇总用于描述优势来源与权重敏感性，不是否决综合胜出的第二套门槛；
- 有限区间实验与渐近上界分别提供经验和理论证据，不相互替代；
- 操作计数是冻结主指标，墙钟时间属于另一套实现相关评价。

### 归档决定

当前 `v3_tune` 不再增加轮数、修改前缀或重开 Test。若未来目标改为“跨分布逐项鲁棒”或“大 n 加权最优”，那是不同目标函数和新的实验版本，不能用 seed 1999 继续选择。

---

## 10. 权威产物

```text
result/v3_tune/v3_tune_config.json
result/v3_tune/v3_tune_metrics.json
result/v3_tune/v3_tune_checkpoint.json
result/v3_tune/v3_tune_candidates.json
result/v3_tune/v3_tune_validation.json
result/v3_tune/v3_tune_selected.json
result/v3_tune/v3_tune_test.json
result/v3_tune/v3_tune_broad_test.json
result/v3_tune/v3_tune_status.json
result/v3_tune/v3_tune_test_status.json
result/v3_tune/v3_tune_archive.json
```

代码与协议说明见 `docs/v3_tune.md`。原始 V3 发现实验见 `result/v3/exp_v3.md`，理论证明见 `docs/proof.md`。
