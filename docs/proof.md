# 冻结几何骨架的有限前缀保持渐近补全

## 一个带稀疏单位破障层的 Shellsort 最坏情况上界证明

> **证明状态。** 本文给出完整的项目内证明。无条件渐近结论针对有限前缀保持的补全序列 \(\mathcal H^+\)；\(\mathcal H^+\) 与搜索得到的纯几何骨架 \(\mathcal H\) 在任意预先指定的有限阈值以内逐项相同。本文固定一个远超实际计算范围的保护阈值 \(N_{\rm guard}=10^{1000}\)，所以原始 V3 的 Search、Validation、Extrapolation、Final Test 以及任何现实可分配数组上的执行都不包含单位伴随 gaps。后续 v3_tune 只替换8项有限前缀并保持同一几何尾部；第 16 节给出它保持增强上界的正式推论。单位伴随层只处理 \(N\to\infty\) 时的同余障碍，是渐近证明装置，不是有限实验中的性能技巧。本文中的 directed-carry 整数化和单位破障构造尚未经过同行评审，因此对外发表前仍应接受独立数学审阅。

---

## 1. 研究对象与最终结论

搜索冻结得到的几何骨架为

\[
h_t=\left\lfloor \alpha\left(\frac AB\right)^t\right\rfloor,
\]

其中

\[
\alpha=\frac{420574650882923}{7668945023518835},
\qquad
A=582942583375009,
\qquad
B=250000000000000,
\]

且

\[
\gcd(A,B)=1,
\qquad
R:=\frac AB=2.331770333500036\ldots>1.
\]

定义

\[
\kappa:=\log_A R
=0.024901468995116044855\ldots.
\]

忽略有限多个为零或重复的早期项，并保证 gap \(1\) 被包含。有限修改不影响任何渐近结论。记原始正 gap 集为

\[
\mathcal H=\{h_t:t\ge 0,\ h_t\ge1\}.
\]

给定任意有限保持阈值 \(N_0\)，本文构造一组索引

\[
s_0<s_1<s_2<\cdots
\]

并定义增广 gap 集

\[
\mathcal H^+
=
\mathcal H\cup\{h_{s_r}+1:r\ge0\}.
\]

主结果如下。

### 定理 1（有限前缀保持的无条件上界）

可以选择 \(s_0,s_1,\ldots\)，使得：

1. 对所有 \(N\le N_0\)，
   \[
   \mathcal H^+\cap[1,N)=\mathcal H\cap[1,N),
   \]
   因而两个 Shellsort 在这些规模上的全部 passes、比较、移动与访存行为完全相同；
2. 原始 gaps 少于 \(N\) 的数量为 \(\Theta(\log N)\)，新增辅助 gaps 少于 \(N\) 的数量仅为 \(O(\log\log N)\)；
3. 使用 \(\mathcal H^+\) 的 Shellsort 最坏情况运行时间满足
   \[
   T_{\mathcal H^+}(N)
   =O\!\left(
   N^{\beta}\operatorname{polylog}N
   \right),
   \]
   其中
   \[
   \beta
   =1+\frac{2\kappa}{1+2\kappa}
   =1.04744027301502511325\ldots.
   \]

因此

\[
\boxed{
T_{\mathcal H^+}(N)
=O\!\left(
N^{1.04744027301502511325\ldots}
\operatorname{polylog}N
\right).
}
\]

特别地，若计算模型的最大可表达输入规模为 \(N_{\max}\)，取 \(N_0=N_{\max}\)，则任何该模型上能够实际执行的排序都只会使用原始几何 gaps；单位破障层只存在于数学上的不可达无穷尾部。

本文后续需要区分两个完全不同的对象：

- **有限执行对象**：在 \(N\le N_0\) 时实际运行的 gap 列表，它与搜索冻结候选完全相同；
- **渐近证明对象**：为讨论 \(N\to\infty\) 而固定一次的无限补全 \(\mathcal H^+\)。

补全不会修改、替换或近似任何有限前缀。因而对有限实验的所有经验结论仍直接属于原始候选；上界定理则属于拥有同一有限前缀的完整无限序列。

后文依次证明该定理。

---

## 2. 从 Shellsort pass 成本到乘子半群

Shellsort 按 gap 从大到小依次执行插入排序。固定某个当前 gap \(d\)。在执行 \(d\)-pass 之前，设已经执行过的较大 gaps 为

\[
a_1,\ldots,a_m.
\]

定义乘子半群

\[
M_d(a_1,\ldots,a_m)
:=
\left\{
 k\in\mathbb Z_{\ge0}:
 kd=\sum_{i=1}^m c_i a_i,
 \ c_i\in\mathbb Z_{\ge0}
\right\}.
\]

若其补集有限，记正整数空洞数为

\[
U_d(a_1,\ldots,a_m)
:=
\#\bigl(\mathbb Z_{>0}\setminus M_d(a_1,\ldots,a_m)\bigr).
\]

若补集无限，则令 \(U_d=\infty\)。

Incerpi--Sedgewick 把 \(n_d(a_1,\ldots,a_m)\) 定义为不能由 \(a_1,\ldots,a_m\) 非负表示的 \(d\) 的正倍数个数，并证明一个已经被这些较大 gaps 排序的数组再执行 \(d\)-sort 时，每个插入位置至多跨过这么多个不可表示倍数；对全部位置求和即得 generalized Frobenius pass 界 [1, Lemma 1, pp. 212--213]：

\[
\operatorname{cost}_d(N)
=O\bigl(N(U_d+1)\bigr).
\tag{2.1}
\]

另一方面，直接把 \(d\)-sort 看成 \(d\) 个长度约为 \(N/d\) 的插入排序，可得平凡界

\[
\operatorname{cost}_d(N)
=O\!\left(\frac{N^2}{d}\right).
\tag{2.2}
\]

所以

\[
\boxed{
\operatorname{cost}_d(N)
=O\!\left(
\min\left\{
\frac{N^2}{d},
N(U_d+1)
\right\}
\right).
}
\tag{2.3}
\]

因此整个问题被转化为：对每个当前 gap \(d\)，证明先前已执行的较大 gaps 能表示除少量乘子之外的所有 \(kd\)。

### 引理 2（conductor 控制空洞数）

若存在 \(K\)，使所有 \(k\ge K\) 均属于 \(M_d\)，则

\[
U_d\le K-1.
\]

证明立即成立，因为所有空洞都位于 \(1,\ldots,K-1\)。这样的最小 \(K\) 称为乘子半群的 conductor。

---

## 3. 为什么窗口必须随 gap 增长

固定数量的 future gaps 不能给出所需的次线性空洞界。直观原因是：

\[
h_{t+i}\approx R^i h_t,
\]

但清除分母后，固定长度窗口保留了一个随 \(h_t\) 增长的同余障碍；在足够小的乘子范围中，大量 \(kh_t\) 不能由固定的 future gaps 非负表示。

因此需要让窗口长度随当前 gap 增长。为避免实数对数造成定义歧义，本文精确定义

\[
m(t):=\min\{m\in\mathbb Z_{\ge0}:A^m\ge h_t\}
=\left\lceil\log_A h_t\right\rceil.
\tag{3.1}
\]

因为

\[
h_t=\alpha R^t+O(1),
\]

所以

\[
\log_Ah_t
=
\log_A\alpha+t\log_AR+o(1)
=
\kappa t+O(1).
\]

故

\[
\boxed{m(t)=\kappa t+O(1).}
\tag{3.2}
\]

同时，在 \(m=\lceil\log_A d\rceil\) 时，

\[
A^m=\Theta(d),
\tag{3.3}
\]

并且因为

\[
\log_A B=1-\kappa,
\]

有

\[
B^m=\Theta(d^{1-\kappa}),
\qquad
\frac d{B^m}=\Theta(d^\kappa),
\qquad
R^m=\Theta(d^\kappa).
\tag{3.4}
\]

式 (3.4) 是最终指数换算的核心。

---

## 4. 二维清分母恒等式

固定当前原始 gap

\[
d=h_t,
\]

并取长度为 \(m\) 的 future gaps

\[
a_i=h_{t+i},
\qquad 1\le i\le m.
\]

定义

\[
E_i:=B^i a_i-A^i d,
\tag{4.1}
\]

\[
q_i:=A^iB^{m-i},
\tag{4.2}
\]

\[
v_i:=B^{m-i}E_i.
\tag{4.3}
\]

由 (4.1)，

\[
B^i a_i=A^i d+E_i.
\]

乘以 \(B^{m-i}\)，得到

\[
B^m a_i=dq_i+v_i.
\tag{4.4}
\]

因此对任意系数向量 \(c=(c_1,\ldots,c_m)\)，

\[
B^m\sum_{i=1}^m c_i a_i
=
 d\sum_{i=1}^m c_iq_i
+
\sum_{i=1}^m c_iv_i.
\tag{4.5}
\]

于是

\[
kd=\sum_i c_i a_i
\tag{4.6}
\]

等价于存在整数 \(D\)，使

\[
\sum_i c_iq_i=kB^m-D,
\tag{4.7}
\]

\[
\sum_i c_iv_i=Dd.
\tag{4.8}
\]

这里：

- \(q\)-坐标是主要的几何尺度；
- \(v\)-坐标是取整误差；
- \(D\) 是把两个坐标重新耦合的整数进位。

这个变换是严格双向等价，不是近似或松弛。

### 4.1 取整误差与统一斜率界

令

\[
x_t:=\alpha R^t,
\qquad
\theta_t:=x_t-\lfloor x_t\rfloor\in[0,1).
\]

因为 \(x_{t+i}=x_tA^i/B^i\)，所以

\[
E_i
=B^i\lfloor x_{t+i}\rfloor-A^i\lfloor x_t\rfloor
=A^i\theta_t-B^i\theta_{t+i}.
\tag{4.9}
\]

因此后文使用的斜率可以写成

\[
\sigma_i:=\frac{v_i}{q_i}
=\frac{E_i}{A^i}
=\theta_t-R^{-i}\theta_{t+i}.
\tag{4.10}
\]

特别地，对所有 \(t,i\) 都有统一界

\[
-R^{-i}<\sigma_i<1,
\qquad
|\sigma_i|<1.
\tag{4.11}
\]

若当前 pass 是辅助 gap \(d=h_t+1\)，则所有 \(E_i\) 同时减少 \(A^i\)，故所有 \(\sigma_i\) 同时平移 \(-1\)。斜率区间的宽度完全不变，并且仍有统一界 \(|\sigma_i|<2\)。这说明第 7--9 节中吸收到常数里的斜率范围确实只依赖固定的 \(A,B\)，与 \(t,m,d\) 无关。

---

## 5. compound 主坐标

所有 \(q_i\) 含公共因子 \(A\)。令

\[
w_i:=\frac{q_i}{A}=A^{i-1}B^{m-i},
\qquad 1\le i\le m.
\tag{5.1}
\]

所以

\[
(w_1,\ldots,w_m)
=
(B^{m-1},AB^{m-2},\ldots,A^{m-1}).
\]

它们满足相邻关系

\[
Aw_i=Bw_{i+1}.
\tag{5.2}
\]

记 compound 数值半群

\[
\mathcal S_m:=\langle w_1,\ldots,w_m\rangle.
\]

### 引理 3（compound 正规形）

这是 compound sequence 正规形、Apéry 集与 Frobenius 数公式在常比率情形 \(a_i=B,b_i=A\) 下的特例 [3, Proposition 12, Theorem 15, Corollary 16]。为使证明自包含，下面直接给出本情形的归约。

每个 \(N\in\mathcal S_m\) 都有唯一表示

\[
N=\sum_{i=1}^m c_iw_i,
\]

满足

\[
0\le c_i<B,
\qquad 2\le i\le m.
\tag{5.3}
\]

证明：从最高下标开始，利用 \(Bw_{i+1}=Aw_i\)，把 \(c_{i+1}\) 除以 \(B\)，余数保留在第 \(i+1\) 位，商乘以 \(A\) 传给第 \(i\) 位。逐层得到 (5.3)。唯一性可从最高位依次模 \(B\) 确定。

相对于最小生成元 \(w_1=B^{m-1}\)，Apéry 集为

\[
\operatorname{Ap}(\mathcal S_m,w_1)
=
\left\{
\sum_{i=2}^m c_iw_i:
0\le c_i<B
\right\}.
\]

因此 Frobenius 数为

\[
F_m
=(B-1)\sum_{i=2}^m w_i-w_1.
\tag{5.4}
\]

对固定 \(A,B\)，有

\[
F_m=O(A^{m-1}).
\tag{5.5}
\]

所以每个

\[
N>F_m
\tag{5.6}
\]

都属于 \(\mathcal S_m\)。

这解决了主坐标是否存在整数非负参考表示的问题。

---

## 6. carry 核与其真实含义

定义相邻 carry 向量

\[
r_i=A\mathbf e_i-B\mathbf e_{i+1},
\qquad 1\le i<m,
\tag{6.1}
\]

其中 \(\mathbf e_i\) 是第 \(i\) 个标准基向量。

由 (5.2)，

\[
w\cdot r_i=0,
\qquad
q\cdot r_i=0.
\tag{6.2}
\]

### 命题 3A（相邻 carries 生成完整整数核）

\[
\ker_{\mathbb Z}(q)
=\left\{x\in\mathbb Z^m:q\cdot x=0\right\}
=\bigoplus_{i=1}^{m-1}\mathbb Zr_i.
\tag{6.3}
\]

#### 证明

因为 \(q=Aw\)，两者的整数核相同。取任意 \(x\in\ker_{\mathbb Z}(w)\)。在

\[
w_1x_1+w_2x_2+\cdots+w_mx_m=0
\]

两边模 \(A\)。除 \(w_1=B^{m-1}\) 外，其余 \(w_i\) 都被 \(A\) 整除；又因 \(\gcd(A,B)=1\)，\(w_1\) 在模 \(A\) 下可逆，所以 \(A\mid x_1\)。写 \(x_1=Az_1\)，并令

\[
x^{(1)}:=x-z_1r_1.
\]

则 \(x^{(1)}_1=0\)，且 \(x^{(1)}\) 仍在整数核中。删去第一个零坐标并除去剩余权重的公共因子 \(A\)，得到同型的长度 \(m-1\) 问题

\[
(B^{m-2},AB^{m-3},\ldots,A^{m-2}).
\]

重复这一模 \(A\) 归纳，依次得到整数 \(z_2,\ldots,z_{m-1}\)，最终

\[
x=\sum_{i=1}^{m-1}z_ir_i.
\]

另一方面，\(r_1,ldots,r_{m-1}\) 线性无关：若 \(\sum z_ir_i=0\)，从第一坐标起依次得到 \(Az_1=0,Az_2=0,\ldots\)，故所有 \(z_i=0\)。所以这里确为直和，命题得证。∎

于是同一主坐标中的任意两个整数表示都且仅能通过整数次相邻 carry 相互转化。

定义局部取整误差

\[
e_i:=Ba_{i+1}-Aa_i,
\qquad 1\le i<m.
\tag{6.4}
\]

由 floor 定义可知

\[
-B<e_i<A,
\tag{6.5}
\]

故 \(e_i\) 来自只依赖固定 \(A,B\) 的有限整数集合。

由 (4.1)--(4.3) 直接计算：

\[
Av_i-Bv_{i+1}=-B^m e_i.
\tag{6.6}
\]

因此一个相邻 carry 对实际 gap 和的改变为

\[
\frac{v\cdot r_i}{B^m}=-e_i.
\tag{6.7}
\]

### 6.1 关键直观

链式 carry 约束不应被理解成一个神秘的动态系统。固定主坐标

\[
Q=q\cdot c
\]

后，所有非负实表示形成单纯形切片

\[
\mathcal P_Q
=
\{c\in\mathbb R_{\ge0}^m:q\cdot c=Q\}.
\]

令

\[
\sigma_i:=\frac{v_i}{q_i}.
\]

对任意 \(c\in\mathcal P_Q\)，

\[
\frac{v\cdot c}{Q}
=
\sum_i\frac{q_ic_i}{Q}\sigma_i,
\]

且权重非负、和为 \(1\)。所以实误差像精确等于凸包区间

\[
\left\{v\cdot c:c\in\mathcal P_Q\right\}
=Q[\sigma_-,\sigma_+],
\tag{6.8}
\]

其中

\[
\sigma_-:=\min_i\sigma_i,
\qquad
\sigma_+:=\max_i\sigma_i.
\]

因此实数层面的可行性只是一维区间问题。

---

## 7. 实内点到整数点：directed-carry 整数化

本节给出后续单位破障证明需要的整数化机制。

### 引理 4（带裕量的实表示）

设目标斜率 \(\tau\) 位于斜率区间内部，并与两端至少相距 \(\eta>0\)：

\[
\sigma_-+\eta
\le\tau\le
\sigma_+-\eta.
\tag{7.1}
\]

给定裕量 \(S>0\)。若主质量 \(Q\) 满足

\[
Q\ge C\frac{S}{\eta}\sum_iq_i,
\tag{7.2}
\]

其中可取只依赖统一斜率界的固定常数 \(C=8\)，则存在实向量 \(c^*\)，使

\[
q\cdot c^*=Q,
\qquad
v\cdot c^*=\tau Q,
\qquad
c_i^*\ge S\quad\forall i.
\tag{7.3}
\]

#### 证明

先给每一坐标放置基线 \(S\)：

\[
c^*=S\mathbf1+y,
\qquad y\ge0.
\]

减去基线后，剩余主质量为

\[
Q'=Q-S\sum_iq_i.
\]

记

\[
W:=S\sum_iq_i,
\qquad
Z:=S\sum_iv_i,
\qquad
\bar\sigma:=\frac ZW.
\]

由于 \(\bar\sigma\) 是各 \(\sigma_i\) 的 \(q_i\)-加权平均，它属于 \([\sigma_-,\sigma_+]\)。剩余部分所需斜率为

\[
\tau'
:=\frac{\tau Q-Z}{Q-W},
\]

并且

\[
|\tau'-\tau|
=\frac{W|\tau-\bar\sigma|}{Q-W}
\le
\frac{2W}{Q-W}.
\tag{7.3a}
\]

这里使用了第 4.1 节的统一斜率界；原始与辅助当前 gap 的斜率区间宽度都小于 \(2\)。又因为 \(0<\eta<1\)，条件 (7.2) 与 \(C=8\) 保证右侧不超过 \(\eta/2\)。所以 \(\tau'\) 仍位于 \([\sigma_-,\sigma_+]\) 内。取达到 \(\sigma_-\) 和 \(\sigma_+\) 的两个坐标，以非负实系数分配质量 \(Q-W\)，即可构造 \(y\ge0\)，满足

\[
q\cdot y=Q-W,
\qquad
v\cdot y=\tau Q-Z.
\]

于是 \(c^*=S\mathbf1+y\) 满足 (7.3)。∎

### 引理 5（carry 坐标逐项舍入不累积）

设 \(c^{(0)}\) 是同一主坐标 \(Q\) 中的一个整数参考点，\(c^*\) 是实点。存在唯一实 carry 向量 \(z^*\in\mathbb R^{m-1}\)，使

\[
c^*=c^{(0)}+\sum_{i=1}^{m-1}z_i^*r_i.
\]

逐坐标取最近整数

\[
\widehat z_i=\operatorname{round}(z_i^*),
\]

并令

\[
\widehat c
=c^{(0)}+\sum_i\widehat z_ir_i.
\]

则

\[
q\cdot\widehat c=Q,
\qquad
\widehat c\in\mathbb Z^m,
\]

且

\[
\|\widehat c-c^*\|_\infty
\le\frac{A+B}{2}.
\tag{7.4}
\]

#### 证明

第一个坐标只受 \(A(\widehat z_1-z_1^*)\) 影响；中间坐标只受

\[
-B(\widehat z_{i-1}-z_{i-1}^*)
+A(\widehat z_i-z_i^*)
\]

影响；最后坐标只受 \(-B(\widehat z_{m-1}-z_{m-1}^*)\) 影响。每个舍入误差绝对值至多 \(1/2\)，于是得到 (7.4)。∎

### 引理 6（舍入后的实际和值误差仅为 \(O(m)\)）

若实点 \(c^*\) 精确满足

\[
\sum_i c_i^*a_i=kd,
\]

则 \(\widehat c\) 的实际整数误差

\[
r:=\sum_i\widehat c_i a_i-kd
\]

满足

\[
|r|
\le\frac12\sum_{i=1}^{m-1}|e_i|
=O_{A,B}(m).
\tag{7.5}
\]

#### 证明

由 (6.7)，

\[
r
=-\sum_i e_i(\widehat z_i-z_i^*).
\]

每个舍入误差至多 \(1/2\)，再用 (6.5) 即得。∎

这三个引理说明：只要实斜率区间足够宽，就能先构造远离非负边界的实表示，然后在不破坏主坐标的情况下整数化；整数化留下的缺口只有线性于窗口长度的整数误差。

原始纯几何序列的困难是：如何保证该整数误差所在的剩余类可以被普通 carries 消除。单位破障层将直接提供一个改变实际和值恰好为 \(1\) 的核方向，从而彻底消除这个困难。

---

## 8. 单位破障对

假设某个 future 位置 \(j\) 同时包含两个 gaps

\[
a_j,
\qquad
a_j+1.
\]

在系数空间中把它们视为两个不同坐标。它们拥有相同的主坐标 \(q_j\)，因为

\[
B^m(a_j+1)
=dq_j+(v_j+B^m).
\tag{8.1}
\]

所以它们的误差坐标分别为

\[
v_j,
\qquad
v_j+B^m.
\]

相应斜率相差

\[
\frac{B^m}{q_j}
=
\frac{B^m}{A^jB^{m-j}}
=
\left(\frac BA\right)^j
=R^{-j}.
\tag{8.2}
\]

因此增广实纤维的斜率宽度至少为

\[
\boxed{\Delta^+\ge R^{-j}.}
\tag{8.3}
\]

更重要的是，定义单位交换方向

\[
s:=-\mathbf e_{a_j}+\mathbf e_{a_j+1}.
\tag{8.4}
\]

它保持主坐标不变，因为两个坐标的 \(q\) 相同；但它使实际 gap 和增加

\[
-(a_j)+(a_j+1)=1.
\tag{8.5}
\]

因此

\[
q\cdot s=0,
\qquad
\text{实际和值改变}=1.
\]

式 (8.5) 是整个破障构造的最内核：任何舍入后剩余的整数误差，都能沿这个方向逐单位修正，而不再需要证明任何 gcd 或模逃逸性质。

### 命题 6A（增广核的完整生成）

把伴随 gap 的坐标记为 \(u\)，其主权重与原第 \(j\) 坐标同为 \(q_j\)。则增广权重向量 \(q^+\) 的完整整数核为

\[
\ker_{\mathbb Z}(q^+)
=\left(\bigoplus_{i=1}^{m-1}\mathbb Zr_i\right)
\oplus\mathbb Zs.
\tag{8.6}
\]

#### 证明

取任意增广整数核向量

\[
x=(x_1,\ldots,x_m,x_u).
\]

把伴随坐标的系数并回原第 \(j\) 坐标，定义

\[
y=(x_1,\ldots,x_j+x_u,\ldots,x_m).
\]

因为两个坐标的主权重相同，\(q\cdot y=q^+\cdot x=0\)。由命题 3A，存在唯一整数 \(z_1,\ldots,z_{m-1}\)，使

\[
y=\sum_{i=1}^{m-1}z_ir_i.
\]

恢复伴随坐标便得到

\[
x=(y,0)+x_u(-\mathbf e_{a_j}+\mathbf e_{a_j+1})
=\sum_{i=1}^{m-1}z_ir_i+x_us.
\]

反向包含关系由 \(q\cdot r_i=0\) 和 \(q^+\cdot s=0\) 立即成立。最后，普通 carries 的伴随坐标为零，而 \(s\) 的伴随坐标为 \(1\)，结合命题 3A 的线性无关性可知该和为直和。∎

---

## 9. 单位破障 conductor 定理

现在把第 5--8 节组合起来。

### 定理 7（单位破障 conductor 界）

固定当前 gap \(d\)，取 \(m\) 个较大原始 gaps

\[
a_i=h_{t+i},
\qquad 1\le i\le m.
\]

假设某个 \(1\le j\le m\) 处同时有 \(a_j\) 和 \(a_j+1\) 已在当前 pass 之前执行。令 \(M_d^+(m)\) 为由这些 future gaps 定义的乘子半群。则存在只依赖固定 \(A,B\) 的常数 \(C_{A,B}\)，使

\[
\operatorname{cond}M_d^+(m)
\le
C_{A,B}\,mR^j
\left(\frac d{B^m}+1\right).
\tag{9.1}
\]

#### 证明

固定乘子 \(k\)。我们证明只要右侧尺度足够大，\(kd\) 就可表示。

**第一步：选择主坐标。**

令

\[
Q=kB^m-D=AN,
\]

其中 \(N\) 是整数变量。目标斜率为

\[
\tau(N)
:=\frac{Dd}{Q}
=
\frac{dkB^m}{AN}-d.
\tag{9.2}
\]

其反函数为

\[
N(\tau)
=
\frac{dkB^m}{A(d+\tau)}.
\tag{9.3}
\]

在所有斜率绝对值被固定常数控制的区间内，

\[
\left|\frac{dN}{d\tau}\right|
=\Theta_{A,B}\!\left(\frac{kB^m}{d}\right).
\tag{9.4}
\]

由 (8.3)，单位对的两个斜率相距恰为 \(R^{-j}\)。取这两个斜率之间的闭区间，并删去两端各三分之一，得到长度 \(R^{-j}/3\) 的中央子区间；该子区间到完整斜率区间两端的距离至少为 \(R^{-j}/3\)。第 4.1 节给出 \(|\tau|<2\)，而 \(d\to\infty\)，所以在所有充分大的 \(d\) 上都有 \(d+\tau\asymp d\)。由 (9.3) 的单调性和中值定理，它在 \(N\)-轴上的原像长度为

\[
\Omega_{A,B}\!\left(
\frac{kB^m}{d}R^{-j}
\right).
\tag{9.5}
\]

当

\[
k\ge C_{A,B}R^j\left(\frac d{B^m}+1\right),
\tag{9.6}
\]

该原像长度至少为 \(2\)，因而包含整数 \(N\)。同时，(9.3) 在该区间上一致给出

\[
N=\Theta_{A,B}(kB^m).
\]

由 \(F_m=O_{A,B}(A^{m-1})\)、\(A^{m-1}<d\le A^m\) 以及 (9.6)，再把只依赖 \(A,B\) 的常数放大，可保证整个中央原像中的整数满足

\[
N>F_m,
\]

于是由 compound Frobenius 界，\(N\in\mathcal S_m\)，从而主坐标 \(Q=AN\) 存在非负整数参考表示。

**第二步：构造带裕量的实表示。**

取中央子区间与两端的距离

\[
\eta=\Theta(R^{-j}).
\]

由引理 4，只要

\[
Q\ge C_{A,B}\frac{S}{\eta}\sum_iq_i,
\]

就能得到所有坐标至少为 \(S\) 的精确实表示。因为

\[
\sum_iq_i=O_{A,B}(A^m)
\]

且 \(Q=\Theta(kB^m)\)，该条件等价于

\[
k
\ge
C_{A,B}S R^jR^m.
\tag{9.7}
\]

利用

\[
R^m=\Theta\!\left(\frac d{B^m}+1\right)
\]

并取

\[
S=C_{A,B}m,
\tag{9.8}
\]

得到 (9.1) 的尺度。

**第三步：整数化。**

把上述原始整数参考表示扩展到伴随坐标为零的增广整数表示 \(c^{(0)}\)。由命题 6A，实差 \(c^*-c^{(0)}\) 唯一写成普通 carries 与单位方向的实线性组合：

\[
c^*-c^{(0)}
=\sum_{i=1}^{m-1}z_i^*r_i+z_u^*s.
\]

分别把 \(z_1^*,\ldots,z_{m-1}^*,z_u^*\) 取到最近整数。普通 carry 的局部性给出每个原坐标 \(O_{A,B}(1)\) 的扰动；单位方向只额外改变单位对的两个坐标至多 \(1/2\)。所以所有坐标仍只发生 \(O_{A,B}(1)\) 的局部扰动。普通 carries 对实际和值造成的舍入误差由引理 6 控制为 \(O_{A,B}(m)\)，单位方向的舍入误差绝对值至多 \(1/2\)。因为舍入前后实际和值都是整数，最终留下的整数误差满足

\[
|r|=O_{A,B}(m).
\tag{9.9}
\]

**第四步：逐单位消除误差。**

由 (8.5)，沿单位交换方向移动 \(-r\) 次，使实际和值改变 \(-r\)，从而精确变成 \(kd\)。普通舍入在任一坐标消耗 \(O_{A,B}(1)\)，最终单位修正在单位对的两个坐标各消耗至多 \(|r|=O_{A,B}(m)\)。先固定足够大的常数 \(C_{A,B}\)，再取 \(S=C_{A,B}m\)，即可保证所有最终系数仍为非负整数。

所以每个满足 (9.1) 右侧阈值的 \(k\) 都可表示，即得到 conductor 界。∎

### 备注

定理 7 不要求

\[
\gcd(a_1,\ldots,a_m)\mid d,
\]

也不要求局部误差 \(e_i\) 的 gcd 为 \(1\)。单位差 \(1\) 已经从根本上消除了所有剩余类障碍。

---

## 10. 稀疏放置单位破障对

对抽象定理，可从任意给定的有限 \(N_0\) 之后开始放置辅助层。为把本项目的最终算法固定成一个不依赖实验结果的单一无限序列，本文预先取

\[
N_{\rm guard}:=10^{1000}.
\tag{10.1}
\]

这个阈值远大于 IEEE-754 binary64 最大有限数的数量级，也远大于任何现实机器能够寻址、分配并排序的数组长度。它不是“浮点近似阈值”，而是一个精确定义的整数。

由

\[
h_t
=\left\lfloor
\frac{420574650882923\,A^t}
{7668945023518835\,B^t}
\right\rfloor
\]

作纯整数交叉相乘可验证

\[
h_{2723}\le10^{1000}<h_{2724}.
\tag{10.2}
\]

等价地，第二个不等式可写成

\[
420574650882923\,A^{2724}
\ge
(10^{1000}+1)\,7668945023518835\,B^{2724},
\]

前一个索引则不满足该式。因此项目固定

\[
\boxed{s_0:=2724.}
\tag{10.3}
\]

由于 \(x_t=\alpha R^t\) 且 \(R>1\)，

\[
h_{t+1}-h_t
\ge (R-1)x_t-1.
\]

在 \(t\ge2724\) 时右侧远大于 \(2\)，所以从 \(s_0\) 起原始 gaps 严格递增，并且 \(h_t+1\) 不会与 \(h_t\) 或 \(h_{t+1}\) 重合。更一般地，对于任意有限保持阈值 \(N_0\)，只需选择足够大的 \(s_0\)，使：

1. \(h_{s_0}>N_0\)；
2. \(h_t\) 在 \(t\ge s_0\) 后严格递增；
3. \(h_{t+1}\ge h_t+2\)，保证 \(h_t+1\) 是新的合法 gap。

递归定义

\[
s_{r+1}
=
 s_r+
 \max\left\{
 1,
 \left\lfloor\frac{m(s_r)}2\right\rfloor
 \right\}.
\tag{10.4}
\]

并在每个 \(s_r\) 处加入

\[
b_r:=h_{s_r}+1.
\tag{10.5}
\]

### 引理 8（每个充分大窗口都含一个单位对）

对每个充分大的当前索引 \(t\)，存在某个 \(r\)，使

\[
t<s_r\le t+m(t).
\tag{10.6}
\]

#### 证明

取满足

\[
s_r\le t<s_{r+1}
\]

的 \(r\)。选取下一破障点 \(s=s_{r+1}\)。因为 \(m(t)\) 最终单调不减，

\[
s-t
\le s_{r+1}-s_r
\le\frac{m(s_r)}2
\le\frac{m(t)}2
\le m(t).
\]

所以 (10.6) 成立。∎

这意味着：在执行 \(h_t\)-pass 或位于同一尺度的辅助 \((h_t+1)\)-pass 之前，长度 \(m(t)\) 的已执行较大 gaps 中一定存在

\[
h_{s_r},
\qquad
h_{s_r}+1.
\]

### 引理 9（辅助 gaps 数量）

小于 \(N\) 的辅助 gaps 数量为

\[
O(\log\log N).
\]

#### 证明

由 (3.2)，对充分大 \(s\)，存在常数 \(c>0\)，使

\[
m(s)\ge cs.
\]

于是

\[
s_{r+1}
\ge
\left(1+\frac c3\right)s_r
\]

（把有限初始误差吸收入常数）。所以 \(s_r\) 至少按几何速度增长。

另一方面，满足 \(h_t<N\) 的最大原始索引为

\[
T=\Theta(\log N).
\]

在索引区间 \([s_0,T]\) 中，几何增长的 \(s_r\) 只有

\[
O(\log T)=O(\log\log N)
\]

个。∎

---

## 11. 内部 passes 的空洞界

固定具有完整 future window 的当前 gap \(d\)，即当前尺度之后至少还有 \(m=m(t)\) 个原始 gaps 小于 \(N\)。由引理 8，某个位置 \(j\le m\) 存在单位对。

定理 7 给出

\[
\operatorname{cond}M_d^+(m)
\le
C_{A,B}\,mR^j
\left(\frac d{B^m}+1\right).
\]

由于 \(j\le m\)，

\[
R^j\le R^m.
\]

再由 (3.4)，

\[
R^m=\Theta(d^\kappa),
\qquad
\frac d{B^m}+1=O(d^\kappa+1).
\]

且

\[
m=O(\log d).
\]

所以

\[
\boxed{
U_d
=O\bigl(d^{2\kappa}\log d\bigr).
}
\tag{11.1}
\]

该结论适用于原始 pass \(d=h_t\)，也适用于辅助 pass \(d=h_t+1\)：二者同阶，清分母恒等式对任意整数当前 gap \(d\) 仍成立，所有误差界只改变固定常数。

把 (11.1) 代入 (2.3)：

\[
\operatorname{cost}_d(N)
=O\!\left(
\min\left\{
\frac{N^2}{d},
N d^{2\kappa}\log d
\right\}
\right).
\tag{11.2}
\]

---

## 12. 顶部 future window 不足的 passes

令 \(T\) 是满足

\[
h_T<N
\]

的最大原始索引。若当前索引 \(t\) 不具有完整长度 \(m(t)\) 的 future window，则

\[
t+m(t)>T.
\tag{12.1}
\]

由

\[
m(t)=\kappa t+O(1),
\]

式 (12.1) 推出

\[
t>\frac{T}{1+\kappa}-O(1).
\tag{12.2}
\]

因为

\[
h_t=\Theta(R^t),
\qquad
h_T=\Theta(N),
\]

所以

\[
h_t
\ge
\Omega\!\left(N^{1/(1+\kappa)}\right).
\tag{12.3}
\]

这些顶部 passes 使用平凡界 \(O(N^2/d)\)。由于 gaps 按几何速度增长，顶部原始 passes 与辅助 passes 的总成本由最小顶部 gap 主导：

\[
O\!\left(
\frac{N^2}{N^{1/(1+\kappa)}}
\right)
=
O\!\left(
N^{2-1/(1+\kappa)}
\right).
\]

而

\[
2-\frac1{1+\kappa}
=1+\frac\kappa{1+\kappa}
=1.02429645165747606869\ldots.
\tag{12.4}
\]

所以顶部成本为

\[
O\!\left(
N^{1.024296451657\ldots}
\right),
\]

严格低于后面内部 passes 的 \(1.04744\) 主指数。

---

## 13. 内部 passes 求和与最终指数

由 (11.2)，单个内部 pass 的两种界在

\[
\frac{N^2}{d}
\asymp
Nd^{2\kappa}
\]

处平衡。忽略对数因子，得到

\[
d^{1+2\kappa}\asymp N,
\]

即

\[
d\asymp N^{1/(1+2\kappa)}.
\tag{13.1}
\]

代回任一项：

\[
\frac{N^2}{d}
=
N^{2-1/(1+2\kappa)}.
\]

因此内部主指数为

\[
\beta
=2-\frac1{1+2\kappa}
=1+\frac{2\kappa}{1+2\kappa}.
\tag{13.2}
\]

代入

\[
\kappa=0.024901468995116044855\ldots,
\]

得到

\[
\boxed{
\beta
=1.04744027301502511325\ldots.
}
\tag{13.3}
\]

原始 gaps 形成几何尺度，总数 \(\Theta(\log N)\)；辅助 gaps 只有 \(O(\log\log N)\) 个。把每个 pass 的最大界乘以至多对数数量，只增加 \(\operatorname{polylog}N\) 因子，不改变多项式指数。

结合内部 passes、顶部 passes 和有限多个早期 passes，得到

\[
\boxed{
T_{\mathcal H^+}(N)
=O\!\left(
N^{1.04744027301502511325\ldots}
\operatorname{polylog}N
\right).
}
\]

定理 1 的第三项得证。

---

## 14. 有限前缀完全保持

选择 \(s_0\) 时要求

\[
h_{s_0}>N_0.
\]

所有新增 gaps 都不小于

\[
h_{s_0}+1>N_0.
\]

所以对任意 \(N\le N_0\)，Shellsort 只使用小于 \(N\) 的 gaps，从而

\[
\mathcal H^+\cap[1,N)
=
\mathcal H\cap[1,N).
\]

这不是“性能近似不变”，而是算法执行轨迹逐项完全相同：

- gap 列表相同；
- passes 次序相同；
- 每一步比较对象相同；
- 比较次数、移动次数和访存次数相同。

对本文固定的 \(N_{\rm guard}=10^{1000}\) 与 \(s_0=2724\)，上述等式对每个

\[
N\le10^{1000}
\]

同时成立。特别地，原始 V3 Final Test 的最大规模 \(10^8\) 与保护阈值之间仍相差 \(992\) 个十进制数量级。因此该 Test 实际执行的就是搜索冻结的 seed 4 几何序列；它不生成、读取或受益于任何单位伴随 gap。Test 测量有限区间上的经验性能，单位伴随层只负责把同一有限前缀补成可证明的无穷对象。后续 v3_tune Test 同样不执行单位伴随 gap，只把这里的有限前缀换成第 16 节推论中的 \(P_8\)。

有限个 \(t<s_0\) 的早期 passes 不影响渐近结论。当 \(N\) 足够大、首个单位破障对已经被执行后，每个固定早期 gap 对应的乘子半群具有固定 conductor，因此每个早期 pass 成本为 \(O(N)\)；有限求和仍为 \(O(N)\)。

于是定理 1 的第一项得证。

### 固定字长计算模型

若某个计算模型使用固定 \(w\)-bit 无符号整数表示输入规模，则

\[
N_{\max}=2^w-1.
\]

对一般定理可取

\[
N_0=N_{\max}
\]

并选择

\[
h_{s_0}>N_{\max}.
\]

那么在该模型上不存在任何能够触发辅助 gap 的合法输入。本文采用更强的固定保护阈值 \(10^{1000}\)：它无需依赖某一台机器的字长，也统一覆盖当前实验、常见整数/浮点格式和现实地址空间。对所有这些可执行规模，算法就是原始纯几何序列；增广只在数学上研究 \(N\to\infty\) 时出现。

若使用任意精度整数，则不存在固定的机器上限，但仍可以令 \(N_0\) 超过全部预定实验、实际部署和盲测规模，从而严格保持整个可观测前缀。

---

## 15. 原始序列与增广序列必须严格区分

本文证明的是：

\[
\boxed{
\text{几何骨架}
+
\text{零密度单位破障层}
\Longrightarrow
O\!\left(N^{1.047440273\ldots}\operatorname{polylog}N\right).
}
\]

没有证明未经增广的纯几何序列本身满足同一无条件上界。

对原始序列，现有 directed-carry 定理还要求局部模相容性

\[
\gcd(h_{t+1},\ldots,h_{t+m(t)})\mid h_t
\]

最终恒成立。最弱的失败情形已经包括：当前 gap 为奇数、未来整个对数窗口全部为偶数。该命题等价于指定 rational-base 轨道的确定性局部模逃逸问题，目前没有被本文证明。

单位破障层不是对这一未解命题作假设，而是通过

\[
(h_s+1)-h_s=1
\]

从构造上彻底消除它。

因此最终序列应当被准确称为：

> **有限前缀保持的渐近补全序列**（finite-prefix-preserving asymptotic completion）。

其性能主体仍是搜索得到的几何骨架；辅助层只负责无穷尾部的理论认证。

---

## 16. 更密破障层的增强结论

主定理优先最小化辅助 gaps 的数量。本节给出另一条同样保持全部有限前缀、但以稍密的零密度辅助层换取更强指数的正式结论。

### 定理 8（零密度增强补全）

仍取固定 \(s_0=2724\)，改用递推

\[
s_{r+1}
=s_r+\left\lceil\log(s_r+2)\right\rceil,
\tag{16.1}
\]

其中 \(\log\) 为自然对数，并在每个 \(s_r\) 加入 \(h_{s_r}+1\)。所得补全记为 \(\mathcal H^\sharp\)。则：

1. 对所有 \(N\le10^{1000}\)，\(\mathcal H^\sharp\cap[1,N)=\mathcal H\cap[1,N)\)；
2. 小于 \(N\) 的辅助 gaps 数量为
   \[
   O\!\left(\frac{\log N}{\log\log N}\right)
   =o(\log N);
   \]
3. 最坏情况运行时间满足
   \[
   \boxed{
   T_{\mathcal H^\sharp}(N)
   =O\!\left(
   N^{1.024296451657\ldots}\operatorname{polylog}N
   \right).
   }
   \tag{16.2}
   \]

#### 证明

给定充分大的当前索引 \(t\)，取 \(s_r\le t<s_{r+1}\)。下一辅助索引满足

\[
j:=s_{r+1}-t
\le\left\lceil\log(s_r+2)\right\rceil
\le\left\lceil\log(t+2)\right\rceil.
\tag{16.3}
\]

另一方面 \(m(t)=\kappa t+O(1)\)，所以充分大时 \(j<m(t)\)，每个完整 future window 仍含单位对。又因为 \(t=\Theta(\log d)\)，

\[
R^j
\le R(t+2)^{\log R}
=\operatorname{polylog}d.
\tag{16.4}
\]

定理 7 因而给出

\[
U_d
=O\bigl(d^\kappa\operatorname{polylog}d\bigr).
\tag{16.5}
\]

将它与 \(N^2/d\) 平衡：

\[
\frac{N^2}{d}\asymp Nd^\kappa,
\qquad
d\asymp N^{1/(1+\kappa)}.
\]

故内部 passes 的指数为

\[
2-\frac1{1+\kappa}
=1+\frac{\kappa}{1+\kappa}
=1.024296451657\ldots.
\]

第 12 节的顶部 passes 已经具有同一指数上界，所有对数损失统一吸收到 \(\operatorname{polylog}N\) 中，得到 (16.2)。

最后证明辅助层仍为零密度。设 \(T=\Theta(\log N)\) 是小于 \(N\) 的最大原始索引。在任意二进区间 \([T/2^{\ell+1},T/2^\ell]\) 内，步长至少为该区间左端对数的常数倍，所以该区间含有

\[
O\!\left(
\frac{T/2^\ell}{\log(T/2^{\ell+1})}
\right)
\]

个辅助索引。对所有非平凡二进区间求和，并把有限尾部吸入常数，得到总数 \(O(T/\log T)\)。代入 \(T=\Theta(\log N)\)，即为 \(O(\log N/\log\log N)=o(\log N)\)。有限前缀保持性仍由 \(s_0=2724\) 立即成立。∎

因此本文有两种严格权衡：

- \(\mathcal H^+\)：只加 \(O(\log\log N)\) 个辅助 gaps，上界指数 \(1.047440273\ldots\)；
- \(\mathcal H^\sharp\)：加 \(o(\log N)\) 个辅助 gaps，上界指数 \(1.024296451\ldots\)。

两者在 \(N\le10^{1000}\) 的所有实际执行中都与搜索候选完全相同。

### 推论：v3_tune 有限前缀替换

最终实验冻结的 v3_tune 前缀为

\[
P_8=\{1,3,8,20,47,116,300,585\}.
\]

它替换原始几何骨架小于 \(1416\) 的有限前缀，而从 \(1416\) 起保留全部精确几何 gaps。对增强补全定义

\[
\mathcal H_{\rm tune}^{\sharp}
=P_8\cup\bigl(\mathcal H^{\sharp}\cap[1416,\infty)\bigr).
\]

则 \(\mathcal H_{\rm tune}^{\sharp}\) 与 \(\mathcal H^{\sharp}\) 只相差有限多个固定 early gaps。第 14 节的 conductor 论证逐项适用于替换后的每个固定 early pass，因此差异总成本仍为 \(O(N)\)，不改变本节的主指数。于是

\[
\boxed{
T_{\mathcal H_{\rm tune}^{\sharp}}(N)
=O\!\left(
N^{1.024296451657\ldots}\operatorname{polylog}N
\right).
}
\]

同时，对所有 \(N\le10^{1000}\)，新增单位伴随 gaps 仍不可见，实际执行序列恰为 v3_tune 冻结候选。该推论只使用有限修改不影响渐近主项，不把 seed 1999 的经验结果引入证明。

---

## 17. 证明链总结

完整逻辑可以压缩为以下链条：

1. Shellsort 的单次 \(d\)-pass 成本由不可表示乘子数 \(U_d\) 控制；
2. 选择 \(m(t)=\lceil\log_Ah_t\rceil\)，使 compound 主坐标的自然尺度为 \(d^\kappa\)；
3. 清分母后，表示问题分解为 compound 主坐标与取整误差坐标；
4. compound 主坐标具有显式正规形和 \(O(A^m)\) Frobenius 阈值；
5. 固定主坐标的非负实表示，其误差像只是一个斜率凸包区间；
6. 命题 3A 证明相邻 carries 构成完整整数核，carry 坐标逐项舍入时每个最终系数只受两个局部 carry 影响；
7. 舍入留下的实际和值误差只有 \(O(m)\)；
8. 在稀疏位置同时加入 \(h_s\) 与 \(h_s+1\)，产生保持主坐标、实际和值改变 \(1\) 的单位核方向；命题 6A 证明普通 carries 与该方向生成完整增广整数核；
9. 单位核方向逐单位消除所有舍入误差，同时完全消除 gcd/剩余类障碍；
10. 每个长度 \(m(t)\) 的窗口中放置一个单位对，得到
    \[
    U_d=O(d^{2\kappa}\log d);
    \]
11. 与平凡界 \(N^2/d\) 平衡，得到指数
    \[
    1+\frac{2\kappa}{1+2\kappa}
    =1.047440273015\ldots;
    \]
12. 把第一个辅助 gap 固定在 \(s_0=2724\)，严格保留 \(N\le10^{1000}\) 的全部有限实验和现实机器上的原始执行行为；
13. 若采用 (16.1) 的零密度增强放置，则 \(R^j\) 只有 polylog 损失，并把指数进一步降为 \(1.024296451657\ldots\)。
14. 把有限低位前缀替换为 v3_tune 冻结的 \(P_8\)，只新增 \(O(N)\) 的有限 early-pass 项，增强补全的主指数保持不变。

---

## 18. 参考文献

1. Janet Incerpi and Robert Sedgewick. [**Improved Upper Bounds on Shellsort**](https://sedgewick.io/wp-content/themes/sedgewick/papers/1985Improved.pdf). *Journal of Computer and System Sciences*, 31(2):210--224, 1985. DOI: [10.1016/0022-0000(85)90042-X](https://doi.org/10.1016/0022-0000(85)90042-X).
2. Robert Sedgewick. [**A New Upper Bound for Shellsort**](https://sedgewick.io/wp-content/themes/sedgewick/papers/1986Shellsort.pdf). *Journal of Algorithms*, 7(2):159--173, 1986. DOI: [10.1016/0196-6774(86)90001-5](https://doi.org/10.1016/0196-6774(86)90001-5).
3. Claire Kiers, Christopher O'Neill, and Vadim Ponomarenko. [**Numerical Semigroups on Compound Sequences**](https://arxiv.org/abs/1503.05993). *Communications in Algebra*, 44(9):3842--3852, 2016. DOI: [10.1080/00927872.2015.1087013](https://doi.org/10.1080/00927872.2015.1087013).
4. Zhenghan Zang. [**Improved Lower Bounds of the Time Complexity of Shellsort**](https://arxiv.org/abs/2607.08997). arXiv: `2607.08997`, 2026. 该预印本仅用于下界背景，不参与本文上界证明。

---

## 19. 最终可引用表述

可以在论文中使用如下严格表述：

> Starting from the learned rational-geometric backbone
> \[
> h_t=\lfloor\alpha(A/B)^t\rfloor,
> \]
> we construct a finite-prefix-preserving asymptotic completion by adding the unit companion \(h_s+1\) only beyond the fixed guard threshold \(10^{1000}\). The added increments therefore leave all reported and physically executable runs unchanged. The unit companions create a kernel direction of exact value one, removing every congruence obstruction in the generalized Frobenius representation. Combining the compound normal form, a complete integer-kernel decomposition, an interior-to-integral carry argument, and the Incerpi--Sedgewick pass bound yields an \(O(\log\log N)\)-auxiliary completion with
> \[
> T(N)=O\!\left(N^{1.047440273015\ldots}\operatorname{polylog}N\right).
> \]
> A denser but still zero-density placement of \(O(\log N/\log\log N)\) unit companions strengthens the bound to
> \[
> T(N)=O\!\left(N^{1.024296451657\ldots}\operatorname{polylog}N\right).
> \]

中文对应表述：

> 在学习得到的有理几何骨架
> \[
> h_t=\lfloor\alpha(A/B)^t\rfloor
> \]
> 上，我们构造一个有限前缀保持的渐近补全：单位伴随 gap \(h_s+1\) 只从固定保护阈值 \(10^{1000}\) 之后出现，因此不改变任何已报告实验或现实可执行排序。单位伴随对提供了实际值恰为 \(1\) 的核方向，从而消除 generalized Frobenius 表示中的全部同余障碍。结合 compound 正规形、完整整数核分解、实内点到整数 carry 的整数化定理以及 Incerpi--Sedgewick pass 界，\(O(\log\log N)\) 辅助层得到
> \[
> T(N)=O\!\left(N^{1.047440273015\ldots}\operatorname{polylog}N\right).
> \]
> 若采用 \(O(\log N/\log\log N)\) 个、但相对原始 \(\Theta(\log N)\) gaps 仍为零密度的辅助层，则进一步得到
> \[
> T(N)=O\!\left(N^{1.024296451657\ldots}\operatorname{polylog}N\right).
> \]
