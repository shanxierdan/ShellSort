# `proof.md` 引用与证明闭包清单

> **当前状态：已落实。** `proof.md` 已在 generalized Frobenius pass 界和 compound sequence 正规形处加入精确引用，并已把原整数核与增广整数核的完整生成证明写入正文。本文件保留为来源审计记录，不再列出待补逻辑步骤。

## 必须引用

### 1. Incerpi--Sedgewick (1985)

**用于：** 第 2 节式 (2.1)，即已被较大 gaps 排序后，当前 `d`-pass 的成本由不可表示的 `d` 的倍数数量控制。

正文已经落实为：

> Incerpi and Sedgewick define the generalized Frobenius quantity \(n_d(a_1,\ldots,a_m)\) and prove that a \(d\)-sorting pass on an array already sorted by \(a_1,\ldots,a_m\) requires \(O(Nn_d)\) steps \cite[Lemma 1, pp.~212--213]{incerpi1985improved}.

对应 `proof.md`：第 2 节，式 (2.1) 前后。

式 (2.2) 的 \(O(N^2/d)\) 可以自行证明，不必引用；若希望说明这是经典的双界平衡框架，可在第 13 节附加 `cf. \cite[Lemma 5]{incerpi1985improved}`。

### 2. Kiers--O'Neill--Ponomarenko (2016)

**用于：** 第 5 节 compound sequence 的正规形、Apéry 集与 Frobenius 数。

我们的

\[
B^{m-1},AB^{m-2},\ldots,A^{m-1}
\]

是该文 compound sequence 的几何特例（取其参数 \(a_i=B,b_i=A\)）。正文“引理 3”开头已经落实为等价表述：

> This is the geometric special case of the normal-factorization and Apéry-set description for numerical semigroups on compound sequences \cite[Proposition 12, Theorem 15, Corollary 16]{kiers2016compound}; a direct proof for the present constant-ratio case is included below.

对应来源：

- Proposition 12：唯一 normal factorization；
- Theorem 15：Apéry 集；
- Corollary 16：Frobenius 数。

当前文档已经给出特例证明，因此这属于“承认已有结果并给出自包含特化”，而不是把结论完全作为黑箱。

## 可选引用／背景引用

### 3. Sedgewick (1986)

只在下列内容出现时引用：

- 将结果与经典 \(O(N^{4/3})\) 上界比较；
- 介绍 Shellsort 与 Frobenius 问题的历史；
- 说明 \(O(\log N)\) gap 序列的经典理论位置。

它不参与本证明的逻辑闭包，因此不要在定理证明中写成依赖项。

### 4. Zang (2026)

只用于下界和动机背景，例如说明有理几何 gap 序列的已知下界，或与目标指数比较。它不参与增广序列的上界证明。提交前必须确认 arXiv 最新版本和最终指数表述。

### 5. Brauer--Shockley (1962)

若正文直接使用一般恒等式

\[
g(S)=\max\operatorname{Ap}(S;m)-m,
\]

可引用该文。若仅引用 Kiers 等人的 Theorem 15 与 Corollary 16，并在特例中自行求最大值，则可以不单独加入这条引用。

## 不需要外部引用、应明确作为本文证明的部分

以下部分在当前证明中属于项目的新构造或初等推导：

- 二维清分母恒等式；
- 固定主坐标实纤维的斜率凸包区间；
- directed-carry 内点与逐坐标舍入；
- 舍入误差仅为 \(O(m)\)；
- 单位伴随 gap \(h_s+1\) 产生值为 1 的 kernel 方向；
- 稀疏破障索引的覆盖与 \(O(\log\log N)\) 计数；
- 最终 \(1.047440273\ldots\) 指数换算；
- finite-prefix-preserving asymptotic completion 构造。

论文中不宜在未做更全面检索前声称这些结果是“首次”；可写成 “we prove” 或 “we introduce”。

## 已补齐的两处内部证明

1. 第 6 节命题 3A 已用逐坐标模 \(A\) 归纳证明 \(r_i=Ae_i-Be_{i+1}\) 生成完整整数核，并证明生成元线性无关。
2. 第 8 节命题 6A 已把伴随坐标并回原坐标，明确证明增广 kernel 是普通 carries 与单位交换方向的直和。

这两处均为自包含的初等格论证明，不依赖 Smith normal form 黑箱。

## 额外闭包

- 第 4.1 节已由小数部分恒等式证明斜率对所有 \(t,m\) 一致有界；
- 第 7 节已显式估计放置坐标基线后目标斜率的扰动；
- 第 9 节已写明中央斜率区间到整数主坐标的长度估计、Frobenius 阈值以及增广 carry 的逐坐标舍入；
- 第 10、14 节已固定 \(N_{\rm guard}=10^{1000}\) 与 \(s_0=2724\)，使理论补全成为单一确定序列；
- 第 16 节已把零密度增强放置写成显式递推并补齐计数与指数证明。
