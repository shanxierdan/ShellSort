# Data

Benchmark arrays are generated on demand from immutable `(n, distribution, seed)` manifests. Large arrays should not be committed here.

Search、Validation 和 Extrapolation 沿用 `python_v1` 数据生成器。Final Test 的协议完整冻结在 `manifests.json`：只测 seed 4 主候选，使用 `numpy_pcg64_v1` 紧凑 `int64` 数组，在 10,000,001 到 100,000,000 的五个对数规模上评测五种分布，并只比较 Sedgewick、Tokuda、Ciura 三条预注册强基线。

`v3_tune_manifest.json` 与历史 manifest 隔离。Search 使用 seed 300，Validation 使用 seed 400，新的封闭 Test 使用 seed 1999；三阶段均使用 `numpy_pcg64_v1`，且不会复用已开启 FINAL 的 seed 999。
