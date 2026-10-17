# Method V3：排序轨迹引导的可执行生成器程序发现

## 1. 方法目标

直接发现一个跨规模、可执行且可分析的 Shellsort gap generator：

```text
G:n -> H_G(n)，
n>h_1>...>h_k=1。
```

V3 不搜索固定 gap 表，不从独立 H 事后回归公式，也不限制为 Recursive、Enumerative 或 LogPosition 函数族。搜索对象从始至终就是完整生成器程序 G。

```text
完整可执行程序 G
      ↓
在多个 n 上生成 H_G(n)
      ↓
Shellsort 逐 gap 轨迹与绝对成本
      ↓
程序级语义 mutation
      ↓
新的完整可执行程序 G'
```

---

## 2. Valid-by-construction 生成语义

程序执行时维护集合：

```text
S={1}。
```

所有 `emit(e)` 将整数值加入 S。最终统一解释为：

```text
H_G(n)
= sort_descending({h in S : 1<=h<n} union {1})。
```

排序、去重、范围过滤和补 1 是公开的语言语义，不是错误修复。因此任何终止程序都产生合法 H，网络无需从大量无效终局中学习合法性。

---

## 3. 统一有界命令式 IR

每个程序包含：

- 1–4 个数值寄存器；
- 只依赖 n 与公共变量的寄存器初始化式；
- 1–32 条有序语句；
- 根据 log n 增长的统一执行 fuel；
- 最多 256 个输出 gap。

概念执行器：

```text
S = {1}
r = initialize(n)
for t in range(fuel(n)):
    execute assignments and conditional emits
return normalize(S, n)
```

fuel 为：

```text
F(n)=b+c ceil(log_2(n+1))。
```

其中 b、c 也是可变程序参数。fuel 限制计算资源而不规定 gap 的数学形式。

### 表达式

变量：

```text
n,t,last,k,r_0,r_1,r_2,r_3。
```

运算包括算术、保护除法、mod、min/max、sqrt、log、pow、取整、比较和条件。实常数可以连续变异。

### 语句

```text
r_i = expression
emit(expression)
if predicate: r_i = expression
if predicate: emit(expression)
```

多个 emit、状态更新和条件可以在同一循环中任意组合，所以递推、枚举、分支并集和混合状态机都属于同一个程序空间。

---

## 4. 程序级动作空间

每个动作把完整程序变为另一个完整程序：

1. `replace_expression`：替换 initializer 或语句中的完整表达式；
2. `insert_emit`：插入新的条件或无条件输出；
3. `insert_assign`：插入寄存器状态更新；
4. `delete_statement`：删除不必要语句，同时保证仍有 emit；
5. `toggle_predicate`：增加、替换或删除分支条件；
6. `mutate_constant`：连续调整表达式常数；
7. `change_fuel`：改变动态循环预算；
8. `duplicate_statement`：复制结构以发展多支规律。

动作粒度是完整语义单元，不再需要几十个 AST token 才形成一个可评测变化。随机探索始终保留，神经策略只改变 proposal 分布，不限制可达程序。

---

## 5. 真实性能目标

训练不使用 baseline oracle。对任务 T：

```text
C(G,T)
=(C_cmp,C_move,abs(H_G(n)))。
```

用于跨 n 排名的绝对归一化统计为：

```text
Y(G,T)
=log((C_cmp+C_move+1)/(n log_2(n+1)))。
```

archive 分别保留 comparisons、moves、pass 数和程序复杂度的 Pareto 前沿。经典序列只在冻结后的 Validation/Extrapolation/Final Test 中逐条比较。

---

## 6. 程序、行为和轨迹联合表示

模型同时编码：

### 程序结构

程序 token 包含 statement、operator、variable、predicate、register 和 fuel 信息。

### 生成行为

程序在 probe n 上实际产生的 H，包括：

```text
log(h_i)/log(n)，
log(h_i/h_(i+1))，
abs(H)。
```

### Shellsort 轨迹

对每个 gap 记录 comparisons、moves 和相对贡献。

两路 Transformer 编码程序与行为/轨迹，再融合预测：

- 下一类程序级 mutation；
- 候选绝对成本；
- gap 局部贡献。

改进 mutation 的标签来自父程序到子程序的真实成本下降，不使用 MCTS visit imitation。

---

## 7. 群体程序搜索

V3 维护完整生成器 population：

```text
随机产生多样、完整、有界程序
          ↓
公共跨 n 任务面板真实评测
          ↓
按性能、程序复杂度和行为新颖性选择 parents
          ↓
learned + random 程序级 mutations
          ↓
语义去重、真实确认、更新 Pareto archive
```

不同结构但在所有训练 n 上生成相同 H 的程序共享语义缓存，优先保留更短程序。所有 archive 分数必须具有相同 panel hash。

---

## 8. 理论分析接口

冻结结果本身就是 G，不需要符号回归。系统输出：

- 初始寄存器表达式；
- 状态转移与 emit 公式；
- 条件分支；
- fuel 和 gap 数量上界；
- 多个 n 上的完整 H；
- 相邻关系与程序依赖图。

先证明程序终止、H 合法和 |H(n)| 上界，再分析 gap 的递推/集合结构以及 Shellsort 平均或最坏复杂度。经验优势不能替代理论证明。
