# Research Integrity Layer（v1.4.0 规则总纲）

> 定位：把 Skill 从"高保真毕业论文文档生成器"升级为"具有研究逻辑、证据链、数据可追溯能力的毕业论文 Agent"。
> 本层**只增不破**：不修改任何既有 QA 脚本语义；与既有交付链并联，接入 Delivery Gate。
> 与 `integrity.md` 的关系：integrity.md 定义诚信红线（禁止事项）；本文件定义**结构化的证据与可追溯机制**（怎么做到可追溯）。

## 1. 架构分层

```
User Materials → Material Layer（materials.yaml，L1–L5）
     → Research Planning（RQ Registry + Research Plan）
     → Evidence Layer（Evidence Registry：文献/标准/手册/材料/实验/计算/模拟/假设）
     → Analysis Layer（Analysis Registry：S5/S6 分析产物）
     → Claim Layer（Claim Registry：正文关键论断）
     → Writing Layer（S7 写作；Conclusion Registry）
     → Document Layer（S8 图表：FIG/TABLE 链接注册）
     → QA / Delivery Gate（RQG + 既有 Format/Visual/Citation/Data QA）
```

## 2. 注册表总则

- 存储位置：`.aeromech/research/`（与 state.yaml 平行，不改 state schema）
- 文件清单：`rq.yaml` `methods.yaml` `evidence.yaml` `datasets.yaml` `analyses.yaml` `computations.yaml` `claims.yaml` `conclusions.yaml` `figures.yaml` `conflicts.yaml`；追踪图由引擎生成 `traceability.json`（不手写）
- ID 规则：`RQ-01`／`M-001`／`E-001`／`DS-001`／`AN-001`／`CALC-001`／`CL-001`／`CON-001`／`FIG-001`／`TABLE-001`／`CONFLICT-001`（数字 2–3 位，全项目唯一，一经分配不得复用）
- 所有跨注册表引用一律用 ID（禁止以文字描述充当链接）
- 引擎：`scripts/research_integrity.py`（读写/校验/追踪/覆盖率）；检查器：`scripts/research_quality_qa.py`（RQG-01~15）
- **渐进可选**：旧项目未建注册表时，RQG 整层标记 `not_initialized`（WARN，不阻塞交付）；新项目自 S1 起按本文件建立

## 3. Research Question Registry（rq.yaml）

```yaml
RQs:
  - id: RQ-01
    question: "……"                 # 必填，研究问题（可回答、可验证）
    objective: "……"                # 必填，与研究问题对应的目标（确定/建立/提出/评价…）
    related_methods: [M-001]        # 必填 ≥1，指向 methods.yaml
    related_chapters: [3, 4]        # 必填 ≥1，章节号
    related_data: [DS-001]          # 可选（无数据型 RQ 可空，但需 analysis 链接）
    related_analyses: [AN-001]      # 必填 ≥1
    related_conclusions: [CON-001]  # 必填 ≥1（阶段推进时补齐；S7 前至少 1）
    notes: ""
```

规则：
1. 每条 RQ 必须满足链：`RQ → M（方法）→ AN（分析）→ CON（结论）`；缺任一环 → RQG 记 High。
2. RQ 的 `related_methods` 所指方法必须能回答该问题（方法描述与问题在文本上可关联；由 RQG-03 检查）。
3. RQ 由 S1/S3 建立；S9 前必须完成注册与回填。

## 4. Evidence Registry（evidence.yaml）

```yaml
evidence:
  - id: E-001
    source_type: literature      # literature|standard|manual|official_document|project_material|experiment|calculation|simulation|assumption
    source: "……"                 # 来源描述（题录/标准号/材料名/计算 ID 等）
    source_location: "……"        # 可定位信息（页码/章节/文件路径/注册表引用）；simulation/assumption 记"构造"
    claim_supported: [CL-001]    # 该证据支持的核心论断（可多）
    reliability: "……"            # 可靠性描述（如【待核实】【已核实】）+ 局限
    verification_status: verified  # verified|partial|pending|simulated
    used_in: [3.2]               # 使用位置（章节/图表号）
    notes: ""
```

规则：
1. **状态映射（与 integrity.md 对齐，不得混用）**：
   - 【已核实】→ `verified`；【用户提供·未核实】→ `partial`；【待核实】→ `pending`；【假设/模拟·仅演示方法】→ `simulated`
2. **禁止伪装**：`simulation`/`assumption` 类型证据的 `verification_status` 必须为 `simulated`；不得以 `verified` 标记模拟/假设。
3. 一证据可支持多个 Claim；一 Claim 可引用多个证据（多对多，由引擎校验互通性）。
4. `experiment` 类型仅在真实实验证据存在时使用；模拟数据一律 `simulation` + `simulated`。

## 5. Method Registry（methods.yaml）

```yaml
methods:
  - id: M-001
    name: "故障树分析（FTA）"
    description: "……实施步骤与输出"
    basis: "……"                  # 必填：为什么选择该方法（适配性论证）
    alternatives_considered: "……" # 记录被排除的备选方法与否决理由
    related_rqs: [RQ-01]
    applied_in_chapters: [4, 5]
```

## 6. Dataset Ledger（datasets.yaml，含 Synthetic Data Ledger）

```yaml
datasets:
  - id: DS-001
    name: "……"
    type: simulated              # real|public|user_provided|literature|simulated|assumption
    source: "……"                 # 真实数据：出处；simulated：'构造模拟（无真实来源）'
    source_location: "……"
    reason: "……"                 # 必填（simulated/assumption）：为什么必须用模拟数据
    assumptions: "……"            # 必填（simulated/assumption）：构造假设
    generation_method: "……"      # 必填（simulated/assumption）：生成方法（含随机种子/参数）
    parameters: "……"             # 关键参数
    used_in: [TABLE-04, CALC-001, "4.8"]
    limitations: "……"            # 必填：不能代表什么（如'不代表真实机队统计特征'）
    label: "【假设/模拟·仅演示方法】"  # simulated/assumption 必填
    verification_status: simulated  # real→verified；public→verified/partial；user_provided→partial
```

**模拟身份传播规则（不得丢失）**：
1. 模拟数据进入正文/表格/图/统计结果/结论/摘要的任何位置，都必须保持 `simulated provenance`；
2. 文档层标注要求：数据集 label 必须在其使用位置（正文段落/表题或表注/图题）出现 ≥1 次（RQG-06 校验）；
3. **不得在后续写作中升级身份**：模拟数据不得被表述为"实测/试验/机队统计/实际运行"（RQG-09/RQG-10 校验）。

## 7. Analysis Registry（analyses.yaml）

```yaml
analyses:
  - id: AN-001
    name: "……分析"
    method: M-001
    inputs:                     # 必填 ≥1；kind ∈ evidence|dataset|computation|reasoning
      - {kind: dataset, ref: DS-001}
      - {kind: evidence, ref: E-003}
    operation: "……"              # 做了什么（步骤）
    outputs: [TABLE-04, "4.6"]
    supports_rqs: [RQ-01]
    artifact: "artifacts/analysis/fault-analysis.md"   # 产物文件
```

## 8. Computation Registry（computations.yaml，扩展 CALC-XXX）

```yaml
computations:
  - id: CALC-001
    description: "……"
    inputs: [{kind: dataset, ref: DS-001}]   # 必填：输入必须指向注册实体
    formula: "……"                            # 必填
    substitution: "……"                       # 代入过程
    output: "……"                             # 结果（数值/表）
    unit: "……"
    verification: "独立重算脚本 + 蒙特卡洛（seed=42）"   # 必填：复核方式
    script: "transcripts/calc001_verify.py"  # 复核脚本（若有）
    used_in: [TABLE-04, FIG-05, CL-003]      # 下游（表/图/结论）
    verified: true
```

规则：计算必须"可重新执行或至少完整解释"（formula+substitution+verification 三件套齐备，RQG-14 校验）。

## 9. Claim Registry（claims.yaml）

```yaml
claims:
  - id: CL-001
    claim: "……"                    # 关键事实性论断原文（或概要）
    claim_type: fact               # fact|interpretation|calculation_result|engineering_judgement|assumption|simulation_result
    evidence_ids: [E-001]          # 支持证据（与 evidence.claim_supported 互证）
    analysis_ids: [AN-001]         # 派生分析（可选）
    chapter: 3
    location: "3.2 第3段"
    confidence: high               # high|medium|low
    status: supported              # supported|partial|unsupported|pending
    evidence_required: true        # 可显式覆盖；缺省按 claim_type 推断
```

规则：
1. **需要证据的核心 Claim 类型**（缺省）：`fact`、`calculation_result`；建议有证据：`interpretation`、`engineering_judgement`；`assumption`/`simulation_result` 必须链接 DS（模拟数据）。
2. `evidence_required: true` 且无任何证据/数据/计算链接 → RQG-07/08 记 High。
3. 引用链规则沿用 `agents/citation.md`：支持/部分支持/不支持/强度检查。

## 10. Conclusion Registry（conclusions.yaml）

```yaml
conclusions:
  - id: CON-001
    conclusion: "……"               # 核心结论原文
    claims: [CL-001]               # 必填 ≥1
    analyses: [AN-001]             # 必填 ≥1
    evidence: [E-001]              # 结论级证据回链（可为 claims 的并集）
    chapter: "结论"
    strength: "……"                 # 表述强度与证据能力匹配说明
    limitations: "……"              # 该结论的适用边界
```

**结论可追溯硬规则**：
- `CON → Analysis` 与 `Analysis → Evidence` 任一断链 → High；
- 结论表述明显超出证据能力（如：模拟 50 条样本 → "该故障在航空公司机队中的发生率为…"）→ **Critical（证据越界）**；由 RQG-10 以"强断言模式 × 证据类型"检测。

## 11. Figure / Table Evidence Link（figures.yaml）

```yaml
figures:
  - id: FIG-001
    name: "图4.1 正常刹车功能失效故障树"
    related_rqs: [RQ-02]
    related_analyses: [AN-002]
    related_claims: [CL-003]       # 至少其一（rq/analysis/claim）非空
  - id: TABLE-004
    name: "表4.4 T1 最小割集"
    related_analyses: [AN-002]
```

规则：每张正式图/表应有 ≥1 论证链接（参与论证）；完全无链接的图表 → WARN；半数以上无链接 → High（装饰性图表过多）。

## 12. Conflict Resolution（conflicts.yaml）

```yaml
conflicts:
  - id: CONFLICT-001
    source_a: "……"      # 冲突方 A（含出处）
    source_b: "……"      # 冲突方 B
    conflict: "……"      # 冲突内容
    resolution: "……"    # 处置（采用哪方/降级标注）
    reason: "……"        # 依据（优先级规则见 §14）
    status: resolved    # resolved|pending
```

规则：**绝对禁止静默选择**；无法判断时 `status: pending` 且在文档中标注【待核实】。

## 13. Research Traceability Graph

有向链：

```
RQ → M → E → DS → AN → FIG/TABLE → CL → CON → ABSTRACT
```

- 引擎由注册表生成 `traceability.json`（nodes + edges），并校验：
  1. **引用完整**：所有 `*_ids`/`ref` 指向存在的实体（无悬空引用）；
  2. **上溯可达**：每个 CL 至少可达 1 个 AN 或 E；每个 CON 至少可达 1 个 AN；每个 AN 至少可达 1 个输入（E/DS/CALC）；
  3. **图无环**：层级方向固定（RQ 在上，ABSTRACT 在下），不得出现反向环；
  4. **无孤儿核心节点**：不在任何链上的核心 Claim/Conclusion → High。
- 不要求所有自然语言句子注册；**核心事实、核心计算结果、核心工程判断、核心研究结论**必须具备 traceability。

## 14. Research Quality Gate（RQG-01~15）

| 编号 | 检查项 | 判定要点 | 缺省严重度 |
|---|---|---|---|
| RQG-01 | 研究问题明确 | 注册表存在且每条 RQ 的 question/objective 非空 | High |
| RQG-02 | 目标与问题对应 | objective 与 question 文本关联（共享实词）且一一对应 | High |
| RQG-03 | 方法能回答研究问题 | 每 RQ 方法链接存在且方法名出现在研究文本 | High |
| RQG-04 | 方法有明确选择依据 | 每方法 basis 非空且文本含选择论证 | High |
| RQG-05 | 核心数据有来源 | 每数据集 source 非空；真实数据须有可定位出处 | High |
| RQG-06 | 模拟数据有明确标记 | simulated 必有 label 且 label 出现在文档使用位置 | Critical |
| RQG-07 | 核心分析有数据/证据支撑 | 每 AN inputs 非空且引用有效 | High |
| RQG-08 | 核心结论可追溯到分析 | 每 CON claims/analyses 非空且引用有效 | High |
| RQG-09 | 摘要结论与正文结论一致 | 摘要数值⊆正文；结论关键词覆盖；摘要无"实测"式越界措辞 | High/Critical |
| RQG-10 | 不存在超出证据范围的结论 | 强断言模式 × 证据类型（全模拟/假设 → 禁强断言） | Critical |
| RQG-11 | 图表参与论证 | 每图表 ≥1 论证链接；无链接占比统计 | High（>50%）/Medium |
| RQG-12 | 关键参考文献确实被正文使用 | 注册为支持证据的文献编号在正文出现 | High（全未用）/Medium |
| RQG-13 | 正文重要数字可追溯 | 正文数值段落含引用/标注/可匹配计算输出 | Medium |
| RQG-14 | 计算结果可追溯到输入 | 每 CALC inputs/formula/verification 齐备且引用有效 | High |
| RQG-15 | 研究限制与证据能力匹配 | 存在限制论述；simulated 数据必须在限制中被声明 | Medium |

评分输出：`PASS / WARN / FAIL`；严重度 `Critical / High / Medium / Low`。
**门禁规则：存在 Critical/High 的 FAIL → RI Gate FAIL，阻止 Delivery Gate**；Medium/Low → 披露放行。

## 15. Evidence Coverage Ratio

```
evidence_coverage_ratio = 有证据支持的核心 Claim 数 / 需要证据的核心 Claim 数
```

- "需要证据"：`evidence_required: true` 或 claim_type ∈ {fact, calculation_result}；
- "有证据支持"：至少 1 条 `evidence_ids`/`analysis_ids`/数据集链路有效且 status ∈ {supported, partial}（partial 计入覆盖但单列）；
- 覆盖率输出按证据状态四分类计数：`verified / partial / pending / simulated`；
- **绝不能把 simulated 当 verified**（分类只按证据自身 verification_status，不做升级）。

## 16. Research Material Priority（证据优先级）

1. 学校正式要求 → 2. 导师明确要求 → 3. 用户项目材料 → 4. 官方技术资料 → 5. 可靠学术文献 → 6. 公开行业资料 → 7. 模板样例 → 8. Skill 默认知识

- 编号越小优先级越高；低优先级来源与高优先级冲突时，按 §17 记录 CONFLICT 并按高优先级处置；
- **模板样例只能用于格式与表达参考**，不得继承其数据、结果、结论、案例、引用事实。

## 17. 与既有 QA / Delivery Gate 集成

```
Format QA + Visual QA + Content Purity + Citation Integrity + Data Integrity
+ Research Quality（RQG-01~15） + Evidence Traceability（§13）
→ 统一进入 Delivery Gate
```

- RQG 检查器：`python scripts/research_quality_qa.py --project <root> [--pdf <final.pdf>] --out <dir>`
- 退出码：0 = PASS / PASS_WITH_HUMAN_REVIEW；1 = 存在 Critical/High（RI Gate FAIL）；
  2 = 注册表未初始化（WARN 级，旧项目兼容）；3 = ERROR（内部异常/注册表损坏，绝不伪造 PASS）
- RI 问题映射 open_issue（state.md §7）：category 按类别（citation/data/engineering/structure/integrity），severity 沿 RQG 定级，target_stage 按 §8 映射表
- Delivery Gate 接入：RI Gate FAIL（Critical/High）**禁止正式终稿交付**；
  `PASS_WITH_HUMAN_REVIEW` 允许交付流程继续，但交付前必须完成人工复核（§19）；Medium/Low 在交付报告中披露

## 18. 通用性纪律（v1.4 硬约束）

1. 引擎与检查器不得硬编码任何学校、题目、专业或测试项目名；
2. 全部规则参数化/结构化（注册表驱动），test-5.0/6.0 之外的任何项目可同样使用；
3. 不得以"通过测试"为由降低检查强度或删除检查项；
4. 模拟数据、假设、工程判断、文献事实的身份不得互相伪装（integrity.md 红线在本层的结构化落实）。

## 19. 状态模型与人工复核（v1.4.1 Stability & Production Hardening）

### 19.1 统一状态词表（所有 RI 层输出）

| 状态 | 含义 | 处置 |
|---|---|---|
| `PASS` | 机械判定通过（或语义检查已由人工裁决通过） | 继续 |
| `WARN` | 软问题（如覆盖不足、复核记录未匹配） | 披露，不阻断 |
| `FAIL` | 存在实质问题（含 Critical/High） | 阻断交付（Delivery Gate FAIL），按 remediation 修复 |
| `NEEDS_HUMAN_REVIEW` | **启发式无法可靠判定的 Critical 级语义问题**（弱证据语境下的 RQG-09/RQG-10） | 不阻断流程但**交付前必须人工复核**（§19.2），Gate 记 `PASS_WITH_HUMAN_REVIEW` |
| `NOT_APPLICABLE` | 当前项目条件下该项无法执行（如无模板项目的模板对照项） | 不计 FAIL、不伪造 PASS；报告如实列出 |
| `SKIPPED_WITH_REASON` | 依赖缺失导致跳过（如未提供 PDF） | 记录原因；不计 FAIL |
| `ERROR` | 内部异常/注册表损坏 | 退出码 3，绝不产生 PASS 结论 |

### 19.2 人工复核回路（RQG-09 / RQG-10 的语义项）

1. 生成：弱证据（全 simulated/pending）语境下，RQG-09/RQG-10 未命中模式时输出 `NEEDS_HUMAN_REVIEW`，
   并在 `artifacts/qa/human-review-checklist.md` 给出 **claim / evidence / reason / uncertainty**；
2. 复核：按 `references/research-human-review.md` 七维逐项裁决；
3. 回填：裁决写入 `.aeromech/research/human-review.yaml`（`decision: ok | violation`）；
4. 重跑：全部 ok → Gate `PASS`；任一 violation → Gate `FAIL`（Critical）；未裁决保持 `PASS_WITH_HUMAN_REVIEW`。

### 19.3 错误模型（不伪造 PASS）

- 注册表损坏：`validate` 记 `RI-CORRUPT`（critical，附 remediation），退出码 1；
  `trace`/`coverage` 退出码 3；RQG 整体记 `ERROR`（退出码 3）。
- 检查器内部异常：捕获后写 ERROR 报告（`gate=ERROR`），退出码 3——**任何异常路径都不得留下 PASS 结论**。
- 每个 FAIL/问题项必须携带：稳定状态码（RI-*/RQG-*/TF-*）+ severity + reason + remediation。
