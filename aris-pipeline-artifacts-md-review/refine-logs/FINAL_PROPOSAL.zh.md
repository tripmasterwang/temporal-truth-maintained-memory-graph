# 定稿方案：CalLB — 面向长对话记忆的**经校准的承重证据选择**（Calibrated Load-Bearing Evidence Selection）

**状态：** READY（第 4 轮评分 9.0/10）— 可交接至 `/experiment-plan`。  
**审稿人：** GPT-5.4 xhigh（经 Codex MCP）。精炼轨迹：6.7（RETHINK）→ 7.6（REVISE）→ 8.5（REVISE）→ **9.0（READY）**。  
**审稿线程 ID：** `019dcdd2-8a56-7c51-8017-9ac14ad3038e`。  
**日期：** 2026-04-27。

## 问题锚点（四轮内不变）

- **底线问题。** 当 LLM 智能体依据累积的长对话记忆作答时，*读者（reader）*会犯两类系统性错误，而截至 2026 年尚无系统用**经校准的机制**同时处理：(i) **过度具体化（over-specification）** — 在已正确锚定到合适证据后，仍用相邻、无支撑的细节填充答案（在 LongMemEval-S 上占 Path D 错误答案的 47%）；(ii) **错误内容检索（wrong-content retrieval）** — 即使干草堆中存在正确证据，仍浮出错误的会话/轮次（占错误答案的 41%）。这两类读者侧失败合计占 Path D **错误答案的 88.2%**，从经验上否定了「写者（writer）是瓶颈」假设。来源：对 `results/gating_decomposition.json` 中 186 道错题的门控分解（2026-04-27）。
- **必须解决的瓶颈。** 需要一种机制同时：(a) 利用跨底物（substrate）信号融合（不仅是同意票数，还包括**单条 raw-turn** 与**实体重叠**等信号，以免低共识但正确的事实被丢掉）降低 *B 类*（错误内容检索）；(b) 通过给读者一个**干净**的承重层（load-bearing tier），且该层以**高概率**不含干扰项 —— 不仅是平均污染有界，而是对「**任一干扰项出现**」的概率有经校准的上界 —— 从而降低 *C 类*（过度具体化）。
- **非目标。** 非新记忆架构；非写时流水线；非 LoCoMo 精度 SOTA；非按查询的弃权规则；非写者微调项目。
- **约束。** 1–2 张 RTX-4090；写者/读者/裁判经 MAAS API（`deepseek-v3.2`、`Kimi-K2`、`glm-5.1`）；3 周；复用 `ttmg/` 底物；目标 NeurIPS / ICML 主会；共享主机负载波动 → 默认 MAAS 顺序调用。

## 方法论点

> *对每条检索到的记忆项，将语义 + 词汇 + 主张图 + raw-turn 等底物信号融合为可学习的可靠性分数；在**干净集指示风险**上对单一阈值 `λ̂_α` 做 **Conformal Risk Control（CRC）** 校准，使得以概率 ≥ 1 − α，承重层 `L_λ̂_α(q) = {item : score ≥ λ̂_α}` 中**不含任何干扰项**；将 `L` 与 `S = top-3 \ L` 作为不同层暴露给读者，并指示其承重事实仅使用 `L`。*

贡献在于：在**读者可见的承重上下文**上给出**经校准的概率性干净集保证** —— 动机来自 2026 年前沿系统上 B+C 门控证据占错题 88.2% —— 同时针对错误内容检索（B 类，经多底物信号融合）与读者过度具体化（C 类，经概率性排除干扰项）。

## 贡献焦点

- **主贡献。** 通过以干净集指示风险做 **Conformal Risk Control（CRC）**，对**读者可见的承重证据层**给出*经校准的概率性干净集保证* —— 首个带此类保证的记忆算子。
- **可选支撑贡献。** 面向记忆系统的门控证据驱动错误分解方法（A/B/C/D 类）— 以脚本 + 186 题参考标签发布。
- **明确非贡献。** 非新记忆存储；非按查询停止规则（MiCP / Stop-RAG 各自覆盖）；非写者微调（Memory-R1 / MemBuilder 各自覆盖）；非 LoCoMo SOTA；**非底物无关**（与 TTMG 耦合；可迁移子集由消融界定上界）。

## 拟定方法

### 复杂度预算

- **冻结 / 复用。** Path D 的 `ttmg/` 底物：主张图（含 supersede 边 + 有效区间 + `active` 标志）、`raw_turn_fallback` 索引、BM25 词汇索引、`all-MiniLM-L6-v2` 嵌入器。读者 = `deepseek-v3.2`。MAAS 端点不变。
- **新增（三处增量，均较小）。**
  1. *特征提取器*（`ttmg/lb_features.py`，约 150 行）：每条 (query, item) 的 13 维特征向量。
  2. *可学习重排器*（`ttmg/lb_model.py`，约 80 行）：MLP（输入 13，隐层 32，输出 1 个 logit），用交叉熵预测 `P(load-bearing)`，标签将 3 档塌缩为二值 `1[label = LB]`。
  3. *CRC 校准层*（`ttmg/lb_crc.py`，约 120 行）：在 100 点 λ 网格上做 Clopper-Pearson UCB + union bound；输出各 α 对应阈值 `λ̂_α`。
- **有意不做的「诱人加法」。** 无 e-process / 序贯检验（Idea 1 数学不成立）。无按查询弃权（β 失败模式）。无新记忆写者（门控表明写者仅占瓶颈 11%，非 70%）。无 cross-encoder 微调（过重；MLP 足够）。无按题型分模型（题型仅作报告分层，不分模型）。

### 特征集（13 维：5 可迁移 + 3 鲁棒 + 5 项 TTMG 专用）

| 分组 | 特征 | 来源 | 动机 |
|---|---|---|---|
| **可迁移** | `semantic_sim(q, item.content)` | 嵌入器余弦 | 底物无关。 |
| **可迁移** | `lexical_sim_bm25(q, item.content)` | raw turn 上 BM25 | 底物无关。 |
| **可迁移** | `cross_substrate_agreement(item)` | 在各自 top-k 中包含该 item 的底物数 ∈ {sem, lex, raw, claim} | 多信号之一（相对 R2 叙事已降风险）。 |
| **可迁移** | `recency_baseline` = `Δt_since_creation` | 原始时间新近性 | 消融对照。 |
| **可迁移** | `source_type` | one-hot {raw-turn, structured-claim} | 底物先验。 |
| **鲁棒** | `max_substrate_score(item)` | 四个归一化底物分数上的 max | 挽救「共识低但单底物很强」的项。 |
| **鲁棒** | `singleton_raw_turn_hit(item)` | 1 当 item ∈ raw-turn top-k 且 ∉ 任一其他底物 top-k | 直接保护门控例「I've got three of them」。 |
| **鲁棒** | `entity_overlap(q, item.content)` | spaCy NER 重叠（归一化） | 补 BM25 漏掉的实体级匹配。 |
| **TTMG 专用** | `claim_graph_relevance(q, item.claim_id)` | 主张表示上余弦；raw-turn 为 0 | 子底物信号。 |
| **TTMG 专用** | `supersede_edge_count(item)` | 指向该项的 hard-supersede 边数 | KU 切片的漂移信号。 |
| **TTMG 专用** | `validity_interval_freshness(item, τ_q)` | 若 `valid_at(item, τ_q)` 则为 `1`，否则指数衰减 | 时间有效性。 |
| **TTMG 专用** | `contradiction_count(item)` | 与 item 关联的 hard-contradict 边数 | 噪声信号。 |
| **TTMG 专用** | `time_volatility(item)` = `Δt_since_creation × topic_volatility(item.subject)` | 漂移分数 | KU 上 B 类修复。 |

`portable_features_only` 消融使用 8 维特征（5 可迁移 + 3 鲁棒，无 TTMG 专用）— 界定贡献中底物无关部分的上界。

### 三档标签

对每个 (query, candidate item) 对：`label ∈ {LB, S, D}`。

- **LB**（承重 load-bearing）：从读者上下文中去掉该项很可能改变答案正确性。必要证据。
- **S**（支撑 supporting）：主题相关但非必要；可安全纳入。
- **D**（干扰 distractor）：会主动误导读者（错误实体、离题但诱人、提及错误实体的近义复述、诱发过度具体化的混淆相邻上下文）。

**LLM 裁判提示**（deepseek-v3.2）：
```
GIVEN:
  - Question: {q}
  - Gold answer: {gold}
  - Candidate retrieved item: {item.content}

Classify the item:
(A) LOAD-BEARING — necessary evidence; removing it likely breaks the answer.
(B) SUPPORTING — topically related but unnecessary; safe to include.
(C) DISTRACTOR — would actively mislead the reader.

Return strict JSON:
{ "label": "LB" | "S" | "D",
  "rationale": "one sentence",
  "confidence": "high" | "low" }
```

**验证门**（任何测试跑之前的内在门）：
- **100 题分层审计**，对 `confidence=low`（边界）过采样 30%。
- 三分类完全一致上 Cohen **κ ≥ 0.7**（门；0.65–0.7 → 3 次自洽 + 再审计；低于 0.65 → 退回二值 `LB` vs `not-LB`）。
- D 对 非-D 二分类一致：**κ ≥ 0.75**（风险仅依赖 D 的检出）。
- 论文报告完整 3×3 混淆矩阵 + D 的条件精度/召回。

### CRC 数学（Clopper-Pearson 精确二项 UCB）

**风险函数（干净集指示量）。**
```
L_λ(q) = { item ∈ candidates(q) : MLP_score(item) ≥ λ }
R(λ; q) = 𝟙[ ∃ item ∈ L_λ(q) with label = D ]   ∈ {0, 1}
R(λ)    = E_q[R(λ; q)] = Pr_q[L_λ(q) contains any distractor]   ∈ [0, 1]
```

对每个 q，R 关于 λ 单调非增（因而在平均意义下亦然），因为 `λ_1 ≤ λ_2` 时 `L_{λ_2} ⊆ L_{λ_1}`。

**定理（Clopper-Pearson CRC，经审稿人 R4 核验）。**

> 固定与校准样本**独立**选取的 λ 网格 `Λ = {λ_1, ..., λ_m}`，m = 100。对每个 `λ_j ∈ Λ`，令 `R̂(λ_j) = (1/n_cal) Σ_{q ∈ cal} R(λ_j; q)`，并令 `U_j = U_{CP}(R̂(λ_j); n_cal, δ/m)` 为置信度 `1 − δ/m` 下 Bernoulli 均值的**单侧 Clopper-Pearson 上界**。
>
> 定义 `λ̂_α = inf { λ_j ∈ Λ : U_j ≤ α }`（若无满足者则为 +∞）。
>
> 在 cal 与 test 查询可交换假设下：
> ```
> Pr_{cal split} [ R(λ̂_α) ≤ α ] ≥ 1 − δ
> ```
> 其中外层概率对随机校准划分；`R(λ̂_α) = Pr_{q ∼ test}[L_λ̂_α(q) contains any distractor]` 为测试时干净集失败概率。

**两层「干净」置信度。**
- `1 − δ = 0.95`：对随机校准划分的置信度（split-conformal 层级）。
- `1 − α`：给定所选阈值后，测试查询上干净集概率（主文 headline 取 α* = 0.20）。

**紧致性。** 当 n_cal = 600，δ/m = 0.0005：
- Hoeffding 松弛：≈ 0.083（常数、与数据无关）。
- **`R̂ = 0.05` 时 Clopper-Pearson：UCB ≈ 0.078**（松弛 0.028，在小风险处紧得多）。
- `R̂ = 0.20` 时 CP：UCB ≈ 0.245（松弛 0.045）。

这使 α = 0.10 **可操作**（需 `R̂ ≤ ~0.04` 方可认证），α = 0.20 较舒适。

### 关于 L 的非空虚 / 效用指标（强制报告）

若 L 恒为空，则干净集保证空虚成立。预先承诺的报告：

| 指标 | 定义 | 主文目标（α* = 0.20） | 失败 |
|---|---|---|---|
| `non_empty_fraction(L)` | Pr_q[|L| ≥ 1] | **≥ 0.85** | < 0.70 → 空虚，F2 |
| `mean_size(L)` | E_q[|L|] | **∈ [2, 5]** | < 1.0 → 过激进 |
| `LB_recall(L)` | Pr_q[L 含 ≥ 1 个标为 LB 的项] | **≥ 0.75** | < 0.50 → 训练失当，F2 |
| `LB_precision(L)` | E_q[#LB / max(1,|L|)] | 描述性 | — |
| L 中干扰项比例均值 | 描述性（曾为 R2 的风险） | 描述性 | — |

### 系统总览

```
WRITE-time  (不变): writer → claims → linker → supersede edges
                         → 主张图 + raw-turn 索引

CALIBRATION（离线、一次性）:
  从 2K 查询 × 每条约 30 候选中分层子采样 10K 个 (q, item) 对
    （40% LongMemEval-S train + 40% Memora train）
  经 LLM 裁判（deepseek-v3.2）自动标注每对为 {LB, S, D}
    对 100 个分层边界样本做人工审计；κ ≥ 0.7（三分类）、κ ≥ 0.75（D 对 非-D）
  训练 MLP：输入 13 维 → 隐层 32 → 输出 1 logit
    损失：对 `1[label = LB]` 的 BCE；5 epoch；Adam LR 1e-3；按查询 80/20 划分（无泄漏）
  留出 30% 校准查询（~600）→ cal-of-cal
  对每个 α ∈ {0.10, 0.20, 0.30, 0.40}:
    对每个 λ_j（100 点网格）：计算 R̂(λ_j) 与 U_j = U_CP(R̂; 600, 0.05/100)
    λ̂_α = inf { λ_j : U_j ≤ α }
  锁定 λ̂ 表；提交 git hash；论文中打印。

INFERENCE:
  在时刻 τ_q 处理查询 q
    → Path D 检索汇总候选集（≤ 30 项）
  对每个候选:
    features = extract_features(q, item)        # 13 维
    s = MLP(features)
  主文 headline α* = 0.20 下的分层:
    L = { item : s ≥ λ̂_0.20 }                   # 承重（以概率 ≥ 80% 的干净层）
    S = top-3 且不在 L 中，按 s 排序              # 支撑性回退
  读者提示（最小增强）:
    [LOAD-BEARING]（答案中的承重事实请仅用这些）:
      {L 中条目}
    [SUPPORTING]（仅作背景；勿作承重事实使用）:
      {S 中条目}
    "Answer using ONLY load-bearing items for the answer's facts. Do not
     include details only present in supporting items unless directly asked."
  → 读者调用（模型不变：deepseek-v3.2；无弃权规则）
```

### 集成

- **涉及文件。** 新建：`ttmg/lb_features.py`、`ttmg/lb_model.py`、`ttmg/lb_crc.py`、`scripts/calibrate_lb.py`、`scripts/audit_judge_labels.py`、`experiments/eval_callb.py`。修改：`ttmg/system.py`（增加 `enable_callb` 标志 + 在 `answer()` 中分层提示路径）。
- **冻结文件。** Path D 全部底物（`schema.py`、`writer_temporal.py`、`conflict_linker.py`、`truth_retriever.py`、`graph.py`、`maas_client.py`、`baseline_amem.py`）。

## 基线与消融

### 外部基线（必选）

| 基线 | 内容 | 数据集 |
|---|---|---|
| Path D `ttmg` | 同底物、无 CalLB 的现有读者 | LME-S, Memora |
| MiCP-on-Path-D | MiCP 按查询停止迁移到候选集 | LongMemEval-S |
| Stop-RAG-on-Path-D | Stop-RAG 迭代检索 + RL 停止迁移 | LongMemEval-S |
| Flat hybrid-RAG | Sem + lex RRF，无主张图 | LongMemEval-S |
| A-Mem | 自 `competitors/A-mem-main` 复现 | Memora |
| Mem0 | 尽力复现 | Memora |
| LightMem | 尽力复现 | Memora |
| EverMemOS | 尽力复现，**仅附录** | Memora（若可移植） |
| SmartSearch | 仅 LoCoMo | LoCoMo |

### 归因基线（必选）

| 消融 | 定义 | 检验 |
|---|---|---|
| `prompt-only` | Path D 现有 top-k + 相同承重提示；无 MLP/CRC | 是否仅靠提示重构驱动 |
| `rerank-only` | CalLB MLP 排序；扁平读者提示（无分层） | 是否分层解决 C 类 |
| `agreement-heuristic-only` | 无 MLP；按同意数排序 + sem-sim 决胜；承重提示 | 是否必须可学习 MLP |
| `no_CRC`（重定义） | 相同 MLP 分数 + 开发集调参固定阈值 | CRC 是否超越单纯重排 |

### 机制消融（3）+ 泛化消融（1）

| 消融 | 定义 | 检验 |
|---|---|---|
| `no_cross_substrate_agreement` | MLP 去掉 `cross_substrate_agreement` | B 类修复归因 |
| `no_drift_features` | MLP 去掉 {time_volatility, supersede_edge_count, validity_interval_freshness, contradiction_count} | KU 切片归因 |
| `no_robustness_features` | MLP 去掉 {max_substrate_score, singleton_raw_turn_hit, entity_overlap} | 新鲁棒特征是否挽救低共识 B 类 |
| `portable_features_only` | MLP 仅用 5 可迁移 + 3 鲁棒 = 8 维 | 贡献中底物无关部分 |

**消融合计：8**（4 归因 + 3 机制 + 1 泛化）。

### 预先登记的 B 类挽救分析

在 `results/gating_decomposition.json` 的 **77 个 B 类样例**上：

1. 运行 CalLB 增强的 Path D 读者；统计多少变为正确。
2. 对每个被挽救问题，按 `cross_substrate_agreement` 计数与 `singleton_raw_turn_hit` 标志对挽救项分类。
3. 报告比例：
   - 高共识挽救（计数 ≥ 3）：若 > 50%，则同意机制是承重机制。
   - 低共识（计数 ≤ 1）且 `singleton_raw_turn_hit = 1`：若 > 30%，鲁棒特征关键。
   - 低共识且无 singleton-hit：若 > 30%，则 MLP 学到细微权重 — 同意叙事不成立。
4. **叙事重构触发。** 若高共识挽救占总挽救 < 30%，论文定位从「跨底物同意是 B 类修复」转为「**可学习的多底物信号融合**是 B 类修复」。

## 主会录用接受逻辑（预先承诺）

CalLB 作为 NeurIPS / ICML 主会贡献被接受 **当且仅当至少满足以下之一**：

- **路径 (A) — 相对固定阈值的下游提升**：CalLB 在 B+C 易感切片精度上相对 `no_CRC`（相同 MLP + 开发集固定阈值）提升 ≥ **1 个百分点**，且在 {LongMemEval-S, Memora-FAMA} 至少其一上 **bootstrap 配对 p < 0.05**。
- **路径 (B) — 跨数据集鲁棒**：当 `λ̂_α` 在一个语料上校准、在另一语料上测试（LongMemEval-S ↔ Memora）**不重新校准**时，CalLB 的污染保证在 held-out 语料上落在 `α + 0.06` 内，而 `no_CRC` 固定阈值违反 > `0.10`。（CRC 阈值可迁移；固定 dev 阈值不可。）

**若两者皆不成立：**
- **选项 F1**：转向 workshop / findings 类 venue（更小范围主张：「记忆上的经校准承重选择；首个形式化保证」）。
- **选项 F2**：放弃形式化保证论点。改框为纯经验论文：「可学习多底物融合 + 分层提示读者用于长对话记忆」，CRC 作补充附录。仅当经验主文 B+C 切片提升 ≥ 5 pp 时再投主会。

团队**事先**承诺；禁止事后合理化 venue。（审稿人在 READY 结论下的唯一操作提醒：「遵守预先承诺的 venue 逻辑」。）

## 成功条件（合并）

1. **测试上概率性干净集保证（形式对象）。** 经验上 Memora test + LongMemEval-S test 上，对 α ∈ {0.10, 0.20, 0.30, 0.40} 有 `R̂_test(λ̂_α) ≤ α + 0.04`（Clopper-Pearson CRC 界成立）。
2. **L 上非空 / 效用。** 在 α* = 0.20：`non_empty_fraction ≥ 0.85`，`mean |L| ∈ [2, 5]`，`LB_recall ≥ 0.75`。
3. **LongMemEval-S 上 B+C 易感切片提升（主文）。** 相对 Path D `ttmg`，在 B 易感（KU、单会话偏好）∪ C 易感（单会话用户、多会话、KU）切片并集上 ≥ **3 pp**；任一切片无 > 1 pp 回退。
4. **主会接受逻辑。** 路径 (A) 或路径 (B)。若皆无 → 选项 F1 或 F2。
5. **归因因果。** `prompt-only` < 50%，`rerank-only` < 70%，`agreement-heuristic-only` < 70%，及 `no_CRC`（路径 A）— 见上文接受逻辑。
6. **机制因果。** `no_cross_substrate_agreement` 或 `no_robustness_features` 使 B 类修复提升下降 ≥ 50%；`no_drift_features` 使 KU 提升下降 ≥ 30%。
7. **可迁移子集。** `portable_features_only`（8 维）达到 CalLB 切片提升的 ≥ 50%。
8. **B 类挽救分析。** 无论结果均报告；叙事按预先登记触发调整。
9. **FAMA 次要持平。** 在 Memora-temporal-forgetting 子集上与最强基线相差 ≤ 3 pp。
10. **LoCoMo 持平。** 与 {Path D, A-Mem, SmartSearch} 中最优相差 ≤ 2 pp。

## 失败条款（终止条件）

| ID | 检测 | 动作 |
|---|---|---|
| F1 | ≥ 4 个 α 中有 ≥ 2 个满足 `R̂(λ̂_α) > α + 0.06` | 检查 CP 计算；若持续 → 放弃形式主张 → 触发选项 F2 |
| F1' | `non_empty < 0.70` 或 `LB_recall < 0.50` | L 空虚 → 选项 F2 |
| F2 | `prompt-only` ≥ 切片提升的 70% | 改框为提示工程论文 |
| F3 | ≥ 2 个切片上 B+C 提升 < 1 pp | 换方向 |
| F4 | D 对 非-D 的 κ < 0.65 | 二值塌缩为 `LB` vs `not-LB` 并重推 |
| F9 | 无路径 A 且无路径 B | 选项 F1（workshop）或 F2（仅经验且 ≥ 5 pp 门槛） |

## 算力与时间线

- **算力。** 约 30 GPU·小时当量（1–2× RTX-4090，推理经 MAAS；MLP CPU < 5 分钟）。
- **标注。** 10K LLM 裁判标签 @ ~3 s = **8.3 hr** 顺序 MAAS + **1 hr** 作者审计 100 个分层项。

### 评测矩阵（第 2 周，31 次运行 / ~16 hr）

| 块 | 方法 × 种子 × 基准 | 次数 | 时间 |
|---|---|---:|---:|
| 主文 headline | {CalLB, Path D ttmg} × 3 seeds × LongMemEval-S 全量 | 6 | 3 hr |
| 必选基线 | {MiCP, Stop-RAG, Flat-RAG} × 3 seeds × LongMemEval-S 全量 | 9 | 4.5 hr |
| 归因 + 机制 + 泛化 | 8 × 1 seed × LongMemEval-S 全量 | 8 | 4 hr |
| Memora-FAMA 次要 | 5 × 1 seed × Memora 全量 | 5 | 2.5 hr |
| LoCoMo 持平 | 3 × 1 seed × LoCoMo 全量 | 3 | 1.5 hr |
| **合计** | | **31** | **~16 hr** |

### 时间线

- **第 1 周 — 构建与校准。** 特征 + MLP + CRC + LLM 裁判标注脚本。自动标注 10K 校准对。人工审计 100 个分层边界样本。训练 MLP。对 4 个 α 计算 Clopper-Pearson CRC 表。锁定并提交 hash。所有内在门通过（κ ≥ 0.7 / 0.75；AUC ≥ 0.75；各 α 在 dev 上覆盖成立）。
- **第 2 周 — 评测。** 上表 31 次矩阵。生成各 α 覆盖曲线、B+C 切片提升柱状图、归因图、机制消融图、可迁移 vs 全文、B 类挽救分析、FAMA 柱、LoCoMo 持平表。
- **第 3 周 — 论文。** 写作 + 图。引用 Conformal Risk Control（Angelopoulos 2022, Bates et al. 2021）、Conformal-RAG（2506.20978）、MiCP（2604.01413）、Stop-RAG（2510.14337）、BMAM（2601.20465）、HiGMem（2604.18349）、Path D 底层 TTMG 论文。

## 新颖性与简洁性论证

| 论文 | 统计对象 | 粒度 | 是否覆盖我们 |
|---|---|---|---|
| Conformal-RAG (2506.20978) | 输出子主张事实性 | 每输出主张 | 否 — 不同侧面（输出，非输入证据） |
| MiCP (2604.01413) | 按查询停止的覆盖 | 每查询 | 否 — 粒度错误 |
| Stop-RAG (2510.14337) | 按查询停止（RL） | 每查询 | 否 — 非统计 + 粒度错误 |
| BMAM (2601.20465) | 无（RRF 启发式） | 每底物融合 | 否 — 无校准、无学习 |
| HiGMem (2604.18349) | 无 | 架构级 | 否 — 无校准 |
| Conformal Risk Control (2208.02814) | 通用风险控制 | 通用 | 提供我们的**工具**，非应用本身 |

**精确差异。** 每 (query, item) 的**承重**标签 + 以**干净集指示风险**做 Conformal Risk Control，控制**读者可见承重层含任一干扰项**的概率 + 多底物信号融合（同意 + max 分数 + singleton-hit + 实体重叠 + TTMG 漂移特征）作为可学习 MLP 特征。

**为何是机制级而非堆叠。** 一个 MLP + 一个 CRC 阈值 + 一处提示更新。Path D 底物冻结。读者冻结。贡献可概括为**一条不等式**：`Pr_test[L_λ̂_α(q) contains distractor] ≤ α`，且对 cal 划分以概率 ≥ 1 − δ 成立。

## 实验计划交接输入（供 `/experiment-plan`）

- **必须证明的主张。** (1) 4 个 α 上 Clopper-Pearson CRC 干净集保证 + 非空目标；(2) LongMemEval-S 上 B+C 切片提升 ≥ 3 pp；(3) 路径 (A) 相对 `no_CRC` 下游提升 ≥ 1 pp 且 p<0.05，**或** 路径 (B) 跨数据集 CRC 阈值迁移。
- **必须跑的基线。** Path D `ttmg`、MiCP-on-Path-D、Stop-RAG-on-Path-D、Flat hybrid-RAG（LongMemEval-S）；A-Mem、Mem0、LightMem（Memora）；EverMemOS 附录；SmartSearch（LoCoMo）。
- **必须跑的消融。** 4 归因（`prompt-only`、`rerank-only`、`agreement-heuristic-only`、`no_CRC`）+ 3 机制（`no_cross_substrate_agreement`、`no_drift_features`、`no_robustness_features`）+ 1 泛化（`portable_features_only`）= **共 8 个**。
- **关键数据集 / 指标。** Memora train/test、LongMemEval-S train/test（全量 N=500）、LoCoMo 全量；各 α 的 Clopper-Pearson 经验风险；非空效用指标；cluster-bootstrap 置信区间；路径 A 的 bootstrap 配对 p 检验。
- **最高风险假设。** (i) LLM 裁判在 100 题审计上 κ ≥ 0.7 / 0.75。(ii) Cal/test 可交换成立。(iii) MLP 在 dev 上 AUC ≥ 0.75。(iv) 第 2 周末路径 A 或 B 至少其一成立（否则按预先承诺触发选项 F1/F2）。
