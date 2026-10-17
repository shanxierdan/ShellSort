# Experiment V3：开放形式生成器程序发现

## 1. 核心问题

> 在不固定生成器函数族的条件下，V3 能否直接发现一个完整程序 G，使其在大量训练 n 上减少 Shellsort 操作，并在未见更大 n 上保持优势和可分析结构？

V1/V2 的最终结论见 [实验结果](实验结果.md)。

## 2. 数据划分

| 阶段 | n 区间 | 规模点 | 是否参与搜索 |
|---|---:|---:|---|
| Search | [32, 10^5] | 128 universe / full 使用 16 点公共 panel | 是 |
| Validation | (10^5, 10^6] | 32 universe | 只选候选 |
| Extrapolation | (10^6, 10^7] | 24 universe | 否 |
| Final Test | [10,000,001, 100,000,000] | 5 个对数规模 × 5 分布 × 1 seed | 最终一次开启 |

输入包含 random、reversed、nearly_sorted、duplicates、blocks。若 G 只观察 n，任何基线也不得根据输入分布动态切换。

## 3. 搜索协议

正式默认：

| 参数 | 值 |
|---|---:|
| seed | 5 |
| iterations | 120 |
| population | 48 |
| elite parents | 12 |
| children / parent | 6 |
| random mutation fraction | 0.35 |
| gradient steps / iteration | 64 |
| replay capacity | 200,000 |
| Search tasks | 16 n × 5 distributions × 2 seeds = 160 |

所有候选使用同一公共 panel。明显昂贵但合法的程序在超过 50 倍 n log n 归一化预算时确定性截断，避免拖垮搜索。

## 4. 评价指标

训练阶段报告：

- 真实评测的语义唯一程序数；
- best-so-far 绝对归一化成本；
- comparisons/moves/pass/program-size Pareto archive；
- 程序结构与行为多样性；
- 最后一次性能改进轮次。

冻结后逐条比较 Shell、Hibbard、Knuth、Pratt、Sedgewick、Tokuda、Ciura：

```text
Delta_B(G)
=mean over T of log((C(G,T)+1)/(C(B,T)+1))。
```

负值表示 G 更好。Validation 对每个 seed 的冻结 archive 使用如下预注册规则选择一个程序：

1. 优先排除出现预算截断的程序；
2. 对 Sedgewick、Tokuda、Ciura 分别计算 `Delta_B`；
3. 最小化三者中的最坏值，均值、总操作数、复杂度和程序 hash 依次用于确定性破同分。

五个 seed 因此至多产生五个冻结程序；相同程序 hash 合并。Extrapolation 只评价这些 Validation 冻结程序，不允许根据 Extrapolation 重新挑选。

## 5. 成功条件

1. 生成器形式没有坍缩到单一行为；
2. 五 seed 在搜索后期仍产生语义唯一且更优程序；
3. 至少一个 Validation 冻结程序在 Extrapolation 上稳定超过 Ciura/Tokuda/Sedgewick 中的强基线；
4. 程序在更大 n 上保持终止、动态 gap 和受控 pass 数；
5. 最终 G 可以被规范化为可陈述的状态更新/emit 规律。

## 6. 运行阶段

- `smoke`：验证 IR、模型、搜索、缓存、冻结和 checkpoint；
- `pilot`：3 seed、25 轮，确认表达空间能产生多种程序结构和持续改进；
- `full`：5 seed、120 轮；
- `run_evaluations_v3.sh`：共享缓存地恢复 Validation，冻结每 seed winner，再统一 Extrapolation；
- Final Test 默认封闭，只有预注册最终实验设置 `RUN_FINAL=1`。

### Final Test 冻结协议

Final Test 只测 Validation 已确定的 seed 4 主候选，不再比较或选择其他神经搜索候选：

```text
program hash = f8e20407ede6a625fff7e6fb2c9f093bb026fc0ea8ddd87cea821525891e731c
n range      = [10,000,001, 100,000,000]
n points     = 5 个确定性对数间隔点
distributions= random, reversed, nearly_sorted, duplicates, blocks
task seed    = 999
baselines    = Sedgewick, Tokuda, Ciura-extension
```

主要成功规则预先固定为：候选没有 censored task，并且相对三条强基线各自的平均 log 操作数比都小于 0。Final Test 使用版本化的 `numpy_pcg64_v1` 紧凑数组生成器和精确 Numba comparisons/moves 计数；每项成本立即写入独立 SQLite 缓存，允许中断恢复，但已有不同签名的 Final Test 结果绝不覆盖。

一键运行：

```bash
RUN_FINAL=1 bash scripts/run_final_test_v3.sh
```

该实验只验证有限区间上的经验性能，不参与、也不验证渐近证明。理论补全的首个辅助 gap 被固定在 (s_0=2724)，超过 (10^{1000})，所以 Final Test 的实际 gap 列表与原始 seed 4 候选逐项完全相同。

V3 full、Validation、Extrapolation 和一次性 Final Test 均已完成。Final Test 零截断；候选相对 Sedgewick 减少 1.579%，相对 Tokuda、Ciura 分别增加 0.113%、0.122%，因此没有通过“逐条超过三条强基线”的严格规则。完整原始记录为 `result/v3/final-test-v3.json`。

后续不重新开放 V3 程序空间，而是在完全保留证明所用几何尾部的条件下微调有限低位 gaps。新协议见 [v3_tune](v3_tune.md)；它不会使用已经开启的 seed 999。

`v3_tune` 也已全部完成并归档。24轮搜索和 seed 400 Validation 冻结出前缀 `1,3,8,20,47,116,300,585`；seed 1999 一次性 Test 零截断，并按预注册等任务平均规则相对 Sedgewick、Tokuda、Ciura分别减少1.793%、0.079%、0.086%。严格规则通过。各分布和最大规模拆分用于解释综合收益来源，不是额外的逐项全胜要求。完整结论见 [v3_tune 实验归档](../result/v3_tune/exp_v3_tune.md)。
