# V3 实施状态

## 1. 紧凑架构

```text
core/       执行器、DSL、V3 程序 IR、评测与搜索
model/      V1/V2 legacy 模型和 V3 联合编码器
data/       冻结任务 manifest
scripts/    V1/V2 重放入口与 V3 主入口
result/     版本化实验档案
tests/      正确性和端到端测试
docs/       当前 V3 方法与历史结论
```

不增加新的顶层目录。V1/V2 文件保留用于重放，但当前主入口统一带 `v3` 后缀。

## 2. V3 已实现

### `core/program_v3.py`

- 统一 `GeneratorProgram`，无生成器模板选择；
- 1–4 个寄存器；
- assign/emit/predicate 语句；
- 有界动态 fuel；
- 完整 JSON round-trip 和稳定 hash；
- 8 类完整程序 mutation；
- 所有程序合法终止并输出合法 H。

### `core/search_v3.py`

- 完整程序 population；
- 公共 panel 评测；
- 程序与语义双重去重；
- performance/moves/passes/program-size Pareto archive，并强制纳入训练标量目标最优程序；
- learned mutation + random exploration；
- V3 replay 和恢复状态。

### `model/program_model_v3.py`

- 程序结构 Transformer；
- H/逐 gap trace Transformer；
- 融合 mutation、cost 和 contribution heads。

### `model/training_v3.py`

- 合法程序 replay；
- 改进 mutation 样本平衡；
- cost/ranking/mutation 联合 loss；
- schema 3 原子 checkpoint 和 `.prev` 回退。

### 运行脚本

```text
scripts/run_v3.py
scripts/evaluate_v3.py
scripts/select_v3.py
scripts/run_evaluations_v3.sh
scripts/run_experiments_v3.sh
```

支持 smoke/pilot/full、多 GPU seed、共享 SQLite 缓存、断点恢复、Validation/Extrapolation 和封闭 Final Test。冻结评测按 task + gap 语义缓存精确成本，固定 baseline 每个 task 只计算一次；每完成一个候选即原子写出 progress，进程中断后可从候选和任务成本两级恢复。每个 seed 另写出 `status-v3.json`，总脚本等待并汇总所有 seed，任一训练或评测失败都会以非零状态退出。

`candidates-v3.json` 同时记录 `train_best_program_hash` 与候选的 `selection_roles`。因此即使训练标量最优不在 raw comparisons/moves/passes 的 Pareto 前沿中，它仍会进入 Validation，不会再出现日志最优与导出最优不一致。Validation 按每 seed 的强基线最坏 log ratio 冻结至多五个程序，只有这些程序进入 Extrapolation。

## 3. 保留的成熟工程

- Python/Numba 计数严格一致；
- 逐 gap comparisons/moves trace；
- operation budget；
- SQLite WAL 缓存；
- 固定 manifest；
- common panel hash；
- 原子 JSON/checkpoint；
- V1/V2/V3 schema 隔离；
- 冻结后逐条 baseline 比较。

## 4. Full 完成后的状态

五个 seed 的 120 轮 full、Validation 和 Extrapolation 均已完成。V3 不再处于“等待 pilot”的实现阶段，完整归档见 `result/v3/exp_v3.md`。

冻结 winner 全部化简为简单几何递推，未显示继续增加寄存器、嵌套 block 或语句上限的必要性。因此这些表达能力增强不再是默认下一步。

当前增强顺序改为：

1. 程序规范化和精确符号常数定义；
2. 逐 n 经验复杂度指数与不确定性估计（首版已完成，可复现输出为 `result/v3/complexity-estimate-v3.json`）；
3. gcd、广义 Frobenius 数、模分布和格结构诊断（精确 5000 项 gcd 与有限 Apéry 审计已完成）；
4. 理论主线已经通过有限前缀保持的单位伴随补全闭合，完整证明见 `docs/proof.md`；
5. seed 4 原始 Final Test 和 `v3_tune` 均已完成。`v3_tune` 冻结前缀 `1,3,8,20,47,116,300,585`，seed 1999 Test 通过预注册平均规则；本版本已归档，不再调参或重开 Test。

## 5. 验证状态

当前测试覆盖：

- V1/V2 全部回归测试；
- V3 统一程序多支 emit；
- 连续 500 次程序 mutation 仍可在多个 n 上执行并合法；
- 程序序列化/token 稳定；
- V3 模型训练；
- 搜索、语义 archive、checkpoint 和 resume；
- 一键 smoke 端到端产出候选。
- `v3_tune` 尾部不可变约束、24轮恢复、独立冻结和不可覆盖 Test。

正式研究顺序已经闭合：V3 full 与冻结外推 → 理论证明 → 原始候选 FINAL → `v3_tune` 有限前缀微调 → 独立 Validation 冻结 → seed 1999 一次性 Test → 归档。
