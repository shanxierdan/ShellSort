# 排序轨迹引导的 Shellsort Gap Generator 程序发现

## 1. 研究目标

Shellsort 使用：

```text
H(n)=(h_1,...,h_k)，
n>h_1>...>h_k=1。
```

项目目标不是优化一张固定 H，也不是在预设递推式或指数族中调参数，而是自动发现生成机制：

```text
G:n -> H(n)。
```

最终 G 应同时满足：

- 跨不同 n 执行；
- 排序操作量小；
- 程序有限、可解释；
- 具备数学分析入口。

## 2. 历史教训

V1 直接搜索 AST，保留了形式探索能力，但长 token 轨迹、无效终局和不合理 oracle 让网络没有学到 gap 性能。V2 改为合法 H 和真实轨迹，搜索稳定改善，却把所有候选限制到固定分数幂表，违背开放发现目标。

V3 不在二者之间循环，而是结合其优势：

```text
直接搜索 G 的形式
+ valid-by-construction
+ 真实排序轨迹。
```

## 3. 核心假设

一个统一的有界命令式语言，可以在不预设生成器函数族的情况下组合：

- 递推状态；
- index enumeration；
- 多个 emit 支路；
- 条件和分段；
- 连续常数；
- 多尺度混合规律。

如果每次搜索动作都修改完整可执行程序，就能同时避免 V1 的稀疏无效轨迹和 V2 的固定函数族。

## 4. 方法概览

```text
完整有界 Generator Program
              ↓
在公共跨 n 面板生成合法 H
              ↓
Numba Shellsort 产生逐 gap 轨迹
              ↓
程序/行为联合神经编码
              ↓
完整程序级 mutation 与群体选择
              ↓
冻结可执行 G，独立外推与数学分析
```

训练目标是绝对 comparisons、moves 和 pass 数。历史 baseline 不参与 reward，只在冻结后比较。

## 5. 预期贡献

1. 一个无互斥生成器模板、所有程序合法终止的 gap generator IR；
2. 一个联合程序结构、实际 H 和排序轨迹的搜索模型；
3. 一个在完整可执行程序之间进行语义 mutation 的群体搜索算法；
4. 一个无需事后符号回归、可直接进行程序和复杂度分析的冻结 G；
5. 若实验成功，一个经验上超过强经典序列并产生新理论猜想的 gap family。

第 5 项不是预设结论。经验结果和理论证明必须分别陈述。

## 6. 当前状态

V1/V2/V3 均已归档，V3 五 seed full、Validation 和 Extrapolation 已完成。项目已经得到一个经验上有竞争力、可以精确定义的符号候选；继续堆叠同类训练不再是主线。

理论主线已经闭合：在 \(10^{1000}\) 之后加入不影响任何有限执行的零密度单位伴随层，完整整数核与 directed-carry 论证给出 \(O(N^{1.047440273\ldots}\operatorname{polylog}N)\) 上界；增强零密度放置进一步给出 \(O(N^{1.024296451\ldots}\operatorname{polylog}N)\)。该补全是处理无穷尾部同余障碍的证明装置，现有实验和实际候选序列完全不变。

项目入口统一为：[Method](Method.md)、[Experiment](Experiment.md)、[实验结果](实验结果.md) 和 [最终上界证明](proof.md)。引用与证明闭包见 [proof citation map](proof_citation_map.md)。
