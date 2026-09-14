# Research Intelligence & Agent Loop（v1.5.0）

> **条款映射（脚本内注释引用的 §N 编号 → 本文节）**：脚本/测试注释沿用 v1.5 设计稿的条款编号，
> 本文正式编号以节号为准。对照：§4 设计注册表→本文 §2；§6 可行性→§3；§7 Claim 强度→§4；
> §8 诊断类型→§5；§9 根因分析→§5；§10/§11 修复计划与白名单→§6；§12/§13/§20 循环与优先级→§5/§7；
> §14 评分→§8；§16 数字一致性→§5；§17 范围控制→§5；§24 人工裁决→§6；§26 Gate 集成→§9。

**定位**：在研究完整性层（v1.4，`research-integrity.md`）之上，建立"理解研究设计 → 发现研究缺陷 →
诊断根因 → 制定修复 → 执行修复 → 重新验证"的闭环能力。全部机制通用：不得为任何题目/学校/测试硬编码。

## 1. 架构

```
Research Question → Research Design → Method Selection → Evidence → Data → Analysis
→ Claims → Conclusions → Abstract                （既有：注册表 + RQG）
        ↓
Research Diagnosis → Repair Planning → Repair Execution → Re-analysis → Re-validation
        ↓
Research Agent Loop: PLAN→ANALYZE→DETECT→DIAGNOSE→REPAIR→RE-ANALYZE→VALIDATE→ACCEPT
```

工具链：`research_design.py`（设计/方法/可行性）→ `research_diagnosis.py`（诊断）→
`research_repair.py`（修复计划+执行）→ `research_agent_loop.py`（闭环）→ `research_quality_score.py`（评分）。

## 2. Research Design Registry（design.yaml）

每项目一条（多条时取首条为当前设计），字段：

```yaml
designs:
- id: DESIGN-001
  research_questions: [RQ-01, RQ-02]        # 覆盖全部 RQ（缺口 → TRACEABILITY_GAP/DSG-01）
  objectives: ["…"]
  methods: [M-001, M-002]                    # 与 methods.yaml 引用一致
  rq_requirements:                           # 每个 RQ 的声明式能力需求（关键）
  - {id: RQ-01, needs: [fault_modes, priority_ranking],
     evidence_requirement: simulated_ok}     # real_world_data|verified_evidence|simulated_ok|literature_only
  evidence_plan: […]; data_plan: […]         # 引用 DS-/E- 条目
  analysis_plan: [AN-001, AN-002]; expected_outputs: [TABLE-001, FIG-001]
  constraints: […]; assumptions: […]; limitations: […]
```

**设计一致性（research_design.analyze）**：
1. `needs ⊆ provides`：RQ 声明需求必须被所选方法能力覆盖（methods[].provides）→ 违者 `RQ_METHOD_MISMATCH`(high)。
2. `evidence_requirement` × 实际数据/证据：
   - `real_world_data`：datasets 中必须有 real/public/user_provided/literature 类型；
   - `verified_evidence`：evidence 中必须有 verification_status=verified；
   - `literature_only`：需要 verified/partial 的 literature 证据；
   - 违者 `DESIGN_EVIDENCE_MISMATCH`(high)——**不得假装设计成立**。
3. 方法选择审计：候选 ≥2、selected 有 selection_reason（≥1 句）、候选有取舍理由 → 违者 `METHOD_SELECTION_WEAK`。

## 3. Research Feasibility Gate（RF-01~10）

`research_design.py feasibility` → **FEASIBLE / CONDITIONALLY_FEASIBLE / INFEASIBLE**；

| 规则 | 判据（结构化，非关键词） | 失败级别 |
|---|---|---|
| RF-01 问题可回答 | 每个 RQ ≥1 条分析链接 | FAIL |
| RF-02 目标可实现 | expected_outputs 落到 analyses.outputs/figures | WARN |
| RF-03 数据足够 | 有数据集；real_world_data 需求可满足 | FAIL |
| RF-04 证据足够 | Coverage ≥0.8 且无 uncovered | WARN |
| RF-05 方法匹配 | 无 RQ_METHOD_MISMATCH | FAIL |
| RF-06 计算可执行 | CALC formula/verification 齐备 | WARN |
| RF-07 结论可支持 | 结论有 claims/analyses 链 | FAIL |
| RF-08 范围过大 | included ≤6 且 RQ ≤5（阈值见脚本常量） | WARN |
| RF-09 范围过小 | included/分析/预期产出 ≥1 | WARN |
| RF-10 假设合理 | assumptions 非空；用模拟数据时必须声明 limitations | FAIL |

**INFEASIBLE → 不得继续正常论文生成**；诊断引擎将其记为 `FEASIBILITY_BLOCK`(critical) → Agent Loop BLOCK，
修复途径仅限人工设计决策（REFRAME/LIMIT/ADD，见 §6）。

## 4. Claim Strength × Evidence Strength

- Claim Strength：**C1** 可能/可以（推测）｜**C2** 表明/提示/说明（有依据的推断）｜**C3** 支持/证明（较强）｜**C4** 确定/必然/显著导致（强断言）。
- Evidence Strength：**ES1** 弱（simulated/assumption/pending）｜**ES2** 中（partial）｜**ES3** 强（verified）｜**ES4** 直接实验/高可信。
- 规则：**Claim Strength ≤ Evidence Strength**。弱证据（ES1/ES2）+ C3/C4 → `CLAIM_OVERSTRENGTH`，
  自动建议降级（例："必然导致制动失效" → "可能导致制动性能下降"）；**禁止在降级中改变技术事实**
  （仅替换强度/口径词，见 §7 白名单变换）。

## 5. Diagnosis（research_diagnosis.py）

诊断条目：`diagnosis_id`（稳定哈希 ID，跨轮可复用）/ severity / issue_type / disposition /
affected_nodes / root_cause / evidence / recommended_repair / repair_options / confidence /
auto_repairable / human_review_required / rule。

issue_type（≥ §8 清单）：RQ_METHOD_MISMATCH、DESIGN_EVIDENCE_MISMATCH、METHOD_SELECTION_WEAK、
SCOPE_OVERFLOW、SCOPE_UNDERFLOW、EVIDENCE_GAP、CITATION_GAP（v1.5.0：RQG-12 派生，注册文献
未被正文使用，计入评分 Citation 维）、DATA_GAP、UNRESOLVED_CONFLICT、CLAIM_OVERSTRENGTH、
CONCLUSION_OVERREACH、ABSTRACT_MISMATCH、CALCULATION_GAP、QUANTITATIVE_INCONSISTENCY、
TRACEABILITY_GAP、ORPHAN_FIGURE、ORPHAN_TABLE、DUPLICATE_ANALYSIS、REDUNDANT_CONTENT、
FEASIBILITY_BLOCK。
**severity 词表统一为小写**（critical/high/medium/low）；诊断引擎入口处归一（RQG 派生项携带
首字母大写形态时同样归一），评分/循环/Gate 的 lowercase 比较因此不会漏计。
**评分兜底**：ISSUE_DIMENSION 未登记的新类型自动计入 Coherence 维并标 `(UNMAPPED)`，
Critical/High 阻断照常生效——"诊断发现问题但评分不认识"结构性不可能。

**disposition**：`auto`（白名单可修）｜`queue`（人工判定类：设计/方法/范围/冲突 → 待裁决期记 NHR）｜
`block`（其余 critical/high 未解决 = Integrity Failure → BLOCK）。

**优先级（§13）**：Research validity(0) > Evidence integrity(1) > Conclusion integrity(2) >
Data integrity(3) > Structural coherence(4) > Visual(5)；同级按 severity。

**范围控制**：`scope.excluded` 项在正文出现 ≥2 次 → SCOPE_OVERFLOW(high)；1 次 → (medium)；
`scope.included` 项全文未出现 → SCOPE_UNDERFLOW(medium)。设计更新（scope/design 修改）方可解除。

**数字一致性**：摘要数字与正文数字：相对差 ≤0.5% 视为**同一结果**（425.4 ≡ 425.40 ≡ 425）；
0.5%~10% → `QUANTITATIVE_INCONSISTENCY`(high，可自动同步到正文/计算基准)；>10% 或无对应 → 人工核对。

## 6. Repair（research_repair.py）

Repair Plan Registry（repairs.yaml）：`REP-XXX {diagnosis_id, target_nodes, repair_type, operation,
before, after, payload, rationale, expected_effect, risk, auto, status∈proposed/applied/verified/rejected}`。

**Auto Repair Policy（§11，白名单，全部留痕 before/after）**：

| 允许 | operation | 说明 |
|---|---|---|
| 论断强度降级 | downgrade_wording | C3/C4 → C2/C1；模拟语境自动加限定；仅替换强度/口径词 |
| 摘要数字同步 | number_sync | 摘要数字 → 正文/计算基准值 |
| 计算重新执行 | recompute | 执行 CALC.recompute.cmd（须输出 `OUTPUT=<值>`），更新 output/verification |
| 模拟标签回填 | fix_synth_label | datasets.label 缺省时回填 `【假设/模拟·仅演示方法】` |

**禁止（必须人工）**：捏造数据/文献/实验；扩大研究范围；更换核心方法；创建"真实"证据；
把模拟改真实；解决来源冲突（只登记 CONFLICT + NHR）。

**recompute 受控执行模型（v1.5.0 信任边界）**：自动重算存在执行外部代码的风险面，因此执行器
只接受一种命令形态——`python <项目根内相对路径>.py [参数]`：解释器一律替换为当前运行解释器
（登记值被忽略）；拒绝 shell 元字符（无 shell=True）、绝对路径、`..` 越界、`-c`/模块入口与
不存在的脚本；工作目录固定为项目根；超时 180s；退出码非零/无 OUTPUT 行为一律记失败并留痕，
绝不静默标 verified。命令文本的唯一来源是项目自身 computations.yaml（用户/Agent 登记，属
项目内可信数据），该信任边界到此为止，不得扩展到外部输入。

**人工裁决（§24）**：`human-review-queue.yaml`（由 loop 生成）逐项填写
`decision: approve|reject|modify` + `payload.replacement`（如需改文）+ reviewer/date/note；
`research_repair.py apply-human` 执行：approve/modify → 文本/注册表替换（记录 REP，status=verified）；
reject → 诊断关闭（rejected_by_human）；不可文本化的选项（ADD_EVIDENCE 等）→ deferred（诊断记
deferred_by_human，按待复核处理）。**不静默解决任何冲突**。

## 7. Agent Loop（research_agent_loop.py）

- `MAX_ITERATIONS = 5`（可调 1~20）；每轮：inspect → feasibility → diagnosis → rank →
  plan → classify(auto/human/block) → execute safe repairs → re-analyze → compare；
  问题签名无改善即停（防死循环）。
- 终态：`BLOCK`（有 block 类 critical/high 未解决；退出码 1）｜`PASS_WITH_HUMAN_REVIEW`
  （judgment 类待裁决 / RQG NHR）｜`WARN`（medium 未解决）｜`PASS_WITH_WARNINGS`（仅 low）｜`PASS`。
- 日志 `artifacts/analysis/research-loop-log.md`（+json）：每轮记录 issues_before/repairs/issues_after/
  improvement/remaining + why（规则命中/严重度依据/修复选择/自动或人工原因）+ 修复前后状态；
  **只记录事实与规则，不输出内部推理链**。

## 8. Research Quality Score（research_quality_score.py）

8 维各 0–100（起始 100 − Σ 未解决 findings 扣分：critical −60 / high −30 / medium −10 / low −3；
Evidence 维度另按 Coverage 折算 −(1−cov)×40）：
Research Design / Evidence / Data / Analysis / Argumentation / Conclusion / Citation / Coherence。
Overall = 8 维均值。**Critical/High 未解决时 blocked=True——总分仅为展示值，不得作为交付依据。**

## 9. Delivery Gate 集成（§26）

```
Format + Visual + Citation + Data + Research Integrity (RQG) + Research Intelligence (Loop)
Critical unresolved → BLOCK ｜ High unresolved → BLOCK ｜ Medium unresolved → WARN
Low unresolved → PASS_WITH_WARNINGS ｜ NEEDS_HUMAN_REVIEW → PASS_WITH_HUMAN_REVIEW
前提：没有 Critical/High integrity failure。
```

旧项目（无 design/scope/repairs 注册表）：全部 v1.5 工具输出 `NOT_APPLICABLE`/不阻塞（兼容规则）。

## 10. 阶段职责（写入时点）

| 阶段 | v1.5 动作 |
|---|---|
| S1-S2 | 题目分析后建立 scope.yaml（included/excluded/assumptions）初稿 |
| S3 | 建 design.yaml（含 rq_requirements.needs/evidence_requirement）+ methods[].provides/selection；跑 feasibility，INFEASIBLE 先修设计 |
| S4 | 文献→evidence；按 evidence_requirement 检查设计-证据匹配 |
| S5-S6 | 数据/分析/计算注册；CALC 带 recompute（可选）；跑 diagnosis 首轮 |
| S7 | 写作期间跑 loop（auto 修复 + 人工队列）；scope creep/数字一致性随写随查 |
| S8-S9 | 交付前 loop 终态须为 PASS / PASS_WITH_WARNINGS / PASS_WITH_HUMAN_REVIEW（且复核完成）|

## 11. 通用性纪律（硬约束）

1. 一切判断基于**注册表声明**与**结构规则**，不得用固定关键词假装理解研究设计；
2. 不得为任何具体题目/学校/测试项目写特例；阈值（RF-08/09、0.5%/10% 等）为通用常量且公开于脚本；
3. 不得用随机文本改动冒充自动修复；自动修复 = 白名单 + before/after + 复检；
4. 不得降低/删除既有 QA（Template/Cover/Color/Table/Graph/PDF/RQG/Delivery Gate）；
5. 无限循环禁止（MAX_ITERATIONS）；冲突禁止静默解决；总分禁止覆盖 Critical。
