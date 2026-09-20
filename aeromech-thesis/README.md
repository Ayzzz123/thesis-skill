# aeromech-thesis

面向飞行器维修工程技术及航空机械/可靠性/结构方向的毕业论文 Agent Skill。

## 1. Skill 简介

**解决什么问题**：帮助航空机械类本科生完成从选题、研究方案、工程分析、数据整理、章节写作、图表生成、引用审计、质量检查到答辩准备的全流程毕业论文工作。

**适合专业/方向**：
- 飞行器维修工程技术
- 飞机维修与机务工程
- 航空器系统维修（起落架、液压、燃油、飞控等）
- 故障诊断与排故
- 可靠性与维修性分析（MTBF、Weibull 等）
- 航空器结构与机械结构分析
- 有限元/应力/模态/疲劳分析
- 航空发动机机械方向

**与普通通用论文生成 Skill 的区别**：
- **Research First, Writing Second**：先建立研究框架和工程分析，再写论文正文，不是直接生成文字
- **学术诚信守卫**：严格禁止虚构文献、数据、标准编号；不确定内容标【待核实】，模拟数据标【假设/模拟·仅演示方法】
- **工程分析能力**：内置 FMEA/FTA/RCA、可靠性分析、有限元流程等航空机械专业方法
- **可回退状态机**：支持多轮中断/恢复，QA 发现问题可回退到对应阶段修复
- **学校模板适配**：有学校模板时严格按模板排版；无模板时使用通用默认格式，不阻塞论文生成

**核心定位**：航空机械类毕业论文研究与写作智能助手，不是通用文字生成工具。

## 2. 核心能力

当前已实现的能力：

| 能力 | 说明 |
|---|---|
| **选题分析** | 分析题目可行性、专业匹配度、难度、风险，给出修改建议 |
| **研究计划** | 生成研究方案、技术路线、论文目录 |
| **文献研究** | 文献登记表管理，GB/T 7714 格式校对，来源分类 |
| **工程分析** | FMEA/FTA/RCA 分析框架，故障链识别，维修策略优化 |
| **可靠性分析** | MTBF/MTTR/可用度计算，Weibull 分布拟合（需真实数据） |
| **结构/FEM 支持** | 有限元分析流程指导，静力/模态/疲劳分析方法说明 |
| **数据分析** | 描述统计（mean/median/std），数据清洗，单位统一，计算审计 |
| **图表生成** | Mermaid 技术路线图/流程图/故障树 → PNG；matplotlib 数据统计图 |
| **Mermaid 渲染** | 自动探测系统 Chrome，无需手动设置环境变量；失败时 fallback 到 matplotlib |
| **引用完整性** | 观点→来源→支持度→编号→格式全链审计，识别缺引用/部分支持/不支持 |
| **QA 论文体检** | 六大维度检查（结构/学术/工程/数据/图表/写作），四级风险分级 |
| **答辩准备** | PPT 结构推荐，5/8/10 分钟答辩稿，预测问题库 |
| **DOCX 生成** | 真正可编辑的 Word 文档（Text/Heading/Table/Image），非图片渲染 |
| **PDF 导出** | DOCX → PDF 转换，保持内容与格式一致 |

## 3. 如何调用

最简单的调用方式：

```
调用 aeromech-thesis
```

然后您可以继续提供以下材料（可选）：
- 论文题目
- 学校论文格式要求（Word 模板或 PDF）
- 任务书
- 参考文献（CNKI 导出的题录或 PDF）
- 技术手册（AMM/CMM/IPC/TSM/SRM 类别）
- 标准（GB/HB/MH/CCAR 等）
- 实验/维修数据
- 往届优秀论文（仅参考结构和版式）

**重要**：您不需要手动调用 Figure Agent / Data Agent / QA Agent 等内部模块，Skill 会自动按需加载。

## 4. 推荐使用流程

```
用户调用 Skill
    ↓
项目初始化（建立 .aeromech/ 工作区）
    ↓
S1 选题分析（分析题目可行性、专业匹配度）
    ↓
S2 选题确认（如无题目则智能推荐候选题目）
    ↓
S3 研究计划（生成研究方案、技术路线、论文目录）
    ↓
S4 文献研究（登记文献，GB/T 7714 格式校对）
    ↓
S5 工程分析（FMEA/FTA/RCA 分析框架，缺口清单）
    ↓
S6 数据分析（如有真实数据：清洗、统计、计算审计）
    ↓
S7 章节写作（按研究方案逐章撰写，依赖降级产物时标【待补依据】）
    ↓
S8 图表规划（Mermaid/matplotlib 生成图表，嵌入 DOCX）
    ↓
S9 QA 论文体检（六大维度检查，发现问题可回退修复）
    ↓
S10 答辩准备（PPT 结构、答辩稿、预测问题库）
    ↓
最终交付：毕业论文.docx + 毕业论文.pdf
```

每个阶段的用途：
- **S1-S2**：确定研究方向和题目
- **S3**：建立研究框架和技术路线
- **S4**：整理文献来源，确保引用有据
- **S5**：构建工程分析框架（如 FMEA 表骨架）
- **S6**：处理真实数据，生成统计结果
- **S7**：撰写论文正文
- **S8**：生成技术路线图、故障树、数据统计图等
- **S9**：全面检查论文质量，发现并修复问题
- **S10**：准备答辩材料

## 5. 项目目录结构

当您调用 Skill 后，会在您的工作目录下建立如下结构：

```
thesis-test-1.0/                    # 您的论文项目目录
├── README.md                       # 项目说明（可选）
├── materials/                      # 用户原始材料目录（您负责放置原始文件）
│   ├── school/                     # 学校文件（格式要求、模板）
│   ├── literature/                 # 文献 PDF / CNKI 题录
│   ├── technical_manual/           # 技术手册（AMM/CMM/IPC/TSM/SRM）
│   ├── standard/                   # 标准文件（GB/HB/MH/CCAR）
│   ├── project_data/               # 项目数据（实验数据、维修记录）
│   └── samples/                    # 往届样文（仅参考结构和版式）
├── .aeromech/                      # Skill 内部工作区（请勿手动修改）
│   ├── state.yaml                  # 项目状态机（记录当前阶段、历史迁移、未关闭问题）
│   ├── context.md                  # 项目上下文摘要（快速查看已确定内容）
│   ├── materials.yaml              # 资料登记总表（登记 materials/ 下的所有材料）
│   ├── school-format.yaml          # 学校格式配置（字体/字号/行距/页边距等）
│   ├── artifacts/                  # Skill 产出物
│   │   ├── analysis/               # 工程分析产物（FMEA 表、basis-notes 等）
│   │   ├── chapters/               # 论文章节（ch1.md ~ chN.md）
│   │   ├── figures/                # 图表（figure-plan.md、PNG 图片等）
│   │   ├── computation/            # 计算审计记录（CALC-XXX.yaml）
│   │   ├── qa/                     # QA 报告（qa-report.md、citation-audit.md）
│   │   └── defense/                # 答辩材料（PPT 结构、答辩稿、问题库）
│   └── transcripts/                # 会话记录
├── 毕业论文.docx                   # 最终交付物（真正可编辑的 Word 文档）
└── 毕业论文.pdf                    # 最终交付物（与 DOCX 内容一致的 PDF）
```

**各文件说明**：
- `state.yaml`：记录项目当前阶段、历史迁移记录、未关闭问题。**请勿手动修改**。
- `context.md`：项目上下文摘要，方便快速查看已确定的题目、专业、研究方向等。
- `materials.yaml`：登记所有提供的材料（学校模板、文献、手册、数据等），记录来源等级和验证状态。
- `school-format.yaml`：学校格式配置，包括字体、字号、行距、页边距、标题层级等。
- `materials/`：**您放置原始材料的文件夹**。Skill 会读取但不修改其中的文件。
- `.aeromech/`：**Skill 内部工作区**，由 Skill 自动管理。您通常不需要也不应该手动修改其中的任何文件。
- `artifacts/`：Skill 生成的中间产物，如图表、分析表、章节草稿等。
- `transcripts/`：会话记录，方便回溯之前的讨论。

**特别强调**：
- `materials/` 是您可见、您负责放置原始论文材料的目录。
- `.aeromech/` 是 Skill 内部工作区，普通用户**不需要也不应该**手动修改其中的任何文件。所有操作通过自然语言对话完成。
- 最终交付物（毕业论文.docx / 毕业论文.pdf）放在项目根目录，不在 `.aeromech/` 内。

## 6. 材料怎么提供

推荐将材料放入项目目录的 `materials/` 文件夹，Skill 会自动登记到 `.aeromech/materials.yaml`：

| 材料类型 | 文件夹 | 用途 |
|---|---|---|
| 学校格式要求/模板 | `materials/school/` | 解析字体、字号、行距、页边距等排版要求 |
| 参考文献 | `materials/literature/` | CNKI 导出的题录、PDF 文献 |
| 技术手册 | `materials/technical_manual/` | AMM/CMM/IPC/TSM/SRM 类别手册 |
| 标准 | `materials/standard/` | GB/HB/MH/CCAR 等标准文件 |
| 项目数据 | `materials/project_data/` | 实验数据、维修记录、故障统计数据 |
| 往届样文 | `materials/samples/` | 仅用于参考章节结构、标题层级、版式，**不得复制内容** |

**材料用途说明**：
- **学校模板**：决定最终 DOCX/PDF 的排版格式
- **文献**：作为论文引用的来源，需登记到文献登记表
- **技术手册**：提供系统结构、故障模式、维修方法等专业信息
- **标准**：提供规范依据（如 CCAR、GB/T 等）
- **项目数据**：用于数据分析和统计，必须有真实来源
- **往届样文**：仅参考结构和版式，**禁止复制其中的数据、结论、案例、文献**

## 7. 学校模板

### 有学校模板

如果您提供了学校论文格式要求（Word 模板或 PDF）：

```
学校模板 → 自动解析 → 建立/更新 school-format.yaml → 严格按照学校要求生成 DOCX/PDF
```

Skill 会从模板中提取：
- 正文字体/字号
- 标题层级格式
- 行距/段落间距
- 页边距
- 图题/表题格式
- 页码位置
- 参考文献格式
- 字数要求
- 摘要要求

### 没有学校模板

如果您暂时没有学校模板：

```
No-School-Template Mode
    ↓
使用通用工科论文默认格式（general_defaults）
    ↓
遵循通用结构原则（general_principles）
    ↓
学校特定字段标【学校格式待提供】（school_specific_unknown）
    ↓
不阻塞 S1-S10 全流程
    ↓
QA 报告提示待补学校格式项
```

**重要**：没有学校模板也可以正常完成论文。Skill 会使用通用默认格式（宋体、小四、1.5倍行距等）生成 DOCX/PDF，这些仅为 fallback 默认值，不代表任何学校正式要求。

**以后拿到学校模板后**：
1. 将学校模板放入 `materials/school/` 目录
2. 说"我提供了学校模板，请重新应用格式"
3. Skill 会：
   - 解析新模板 → 更新 school-format.yaml
   - **不改变**：论文正文内容、研究数据、引用内容
   - **重新执行**：DOCX 格式重应用 → 图表编号/题注检查 → 页码检查 → 参考文献格式检查 → QA → 重新导出 DOCX/PDF

## 8. 论文真实性与完整性规则

本 Skill 严格遵守学术诚信原则：

| 禁止行为 | 处理方式 |
|---|---|
| 虚构文献（作者/题名/期刊/DOI） | 拒绝生成，要求用户提供真实题录 |
| 虚构 DOI | 拒绝生成，标【待核实】 |
| 虚构标准编号（GB/HB/MH/CCAR 等） | 拒绝生成，标【待核实】 |
| 虚构维修手册内容（AMM/CMM/IPC 等） | 拒绝生成，标【待核实】 |
| 虚构实验数据 | 拒绝生成，要求用户提供真实数据 |
| 把测试/模拟数据直接作为真实论文数据 | 必须标【假设/模拟·仅演示方法】，不得进入正式结论 |
| 不确定内容 | 必须标【待核实】 |
| 模拟数据 | 必须标【假设/模拟·仅演示方法】 |

**示例**：
- ✅ 正确："A320 起落架典型故障模式包括收放作动筒内漏【待核实：需用户提供 AMM 或公开资料出处】"
- ❌ 错误："根据某航空公司 2020-2023 年维修记录，起落架故障率为 3.5%"（无真实来源）

## 9. 图表生成

### Mermaid 优先

对于技术路线图、流程图、故障树等结构化图表：

```
.mmd 源文件 → mmdc（Mermaid CLI）→ PNG/SVG → 嵌入 DOCX
```

**环境要求**：
- 系统需安装 Google Chrome
- Skill 会自动探测 Chrome 路径，**无需手动设置环境变量**

### Fallback 机制

如果 Mermaid CLI 不可用或渲染失败：

```
mmdc 失败 → matplotlib 生成真正可读的替代图（含流程图框/故障树节点）→ 嵌入 DOCX
```

**注意**：fallback 图是真正可读的结构化图表，不是空白占位图。

### FIGURE_ERROR

如果 Mermaid 和 matplotlib fallback 都失败：

```
返回 FIGURE_ERROR（退出码 2）→ QA 标记该图为"缺失/生成失败" → 阻止进入最终论文
```

### 图表类型区分

| 类型 | 说明 | 是否可进入最终论文 |
|---|---|---|
| diagram source | `.mmd` 源文件 | 否（内部文件） |
| rendered figure | mmdc 成功渲染的 PNG/SVG | 是 |
| fallback figure | matplotlib 生成的真正可读替代图 | 是 |
| placeholder | 测试用空白/文字占位图 | **否**（禁止进入最终论文） |

## 10. 输出文件

**最终用户默认只需要**：
- `毕业论文.docx`：真正可编辑的 Word 文档（正文=Text，标题=Heading，表格=Word Table，图片=Image）
- `毕业论文.pdf`：与 DOCX 内容一致的 PDF

**内部工作文件**（不作为默认最终交付物）：
- PNG/JPG/SVG 图片
- `.mmd` Mermaid 源文件
- Python 脚本
- YAML 配置文件（state.yaml、materials.yaml、school-format.yaml）
- Markdown 章节文件
- 计算审计文件（CALC-XXX.yaml）
- transcripts 会话记录

这些内部文件保留在项目目录中，方便后续修改和追溯，但普通用户无需关注。

## 11. 当前版本

**aeromech-thesis v1.6.5（Academic Figure Quality & User-Configured Image Provider）**

> v1.6.5 已发布（分支 feature-1.6.5-figure-optimization，经全回归 + test-8.0 全 QA +
> Delivery Gate=PASS + secret_leak_qa FAIL=0 后从 v1.6.0 升级）。学术图形质量与用户自配
> Image Model API（可选增强，零阻塞）——figure_style.py 学术视觉单一来源（3 轮量化验证的
> 调色板/字号阶梯/间距）、figkit role= 语义角色色、mermaid 回退 fail-closed 不伪造语义、
> Visual QA VIS-01~12 入构建链与 Delivery Gate、用户级 `~/.aeromech/.env` 凭据
> （SecretStr 全掩码，image_cli config/status/test/remove）、OpenAI 兼容外部生图
> （8 类错误分类，401 不伪装普通失败）、无 Key 自动回落既有 Figure Pipeline（UNAVAILABLE≠错误，
> 旧 spec 与 v1.6.0 字节一致）、Figure Plan 九字段受控生图（缺 Plan=FIGURE_PLAN_REQUIRED+零 HTTP，
> 确定性图类型恒 local 优先）、AI 生成视觉≠研究证据、secret_leak_qa 泄漏扫描。
> 发布验证：tests/v1_6_5 124 断言 + v1_4/v1_4_1/v1_5/v1_6/test_a/test_b 全绿 +
> test-8.0 全 QA PASS + delivery_gate=PASS。
> 已知限制：LIVE_SMOKE_TEST=NOT_RUN（REASON=USER_CREDENTIAL_NOT_PROVIDED，非阻塞——
> 外部 Provider 代码路径经可注入 transport 全覆盖测试；用户配置 Key 后 `aeromech image test`
> 一次冒烟即可补验，调用前明示费用）。

v1.6.5 在 v1.6.0 编排闭环之上聚焦图形质量与可选外部生图（编排层/研究层零改动，既有能力只增不破）。
v1.6.0 编排闭环基线（在 v1.5.0 研究智能基线之上把既有能力串成编排闭环，编排层只调度不重做业务：
注册表/RQG/诊断/修复/Loop/QA 全部复用原模块）：
- ✅ **StateIO / Checkpoint / Resume**（`thesis_state.py`）：state.md §3~§11 程序化迁移校验（非法边拒绝不落盘）；CK-XXX 检查点（artifacts+SHA256/注册表快照/qa_state）；resume from_start=false，禁止从 S1 重启
- ✅ **统一材料进入**（`material_ingestion.py`）：scan/SHA256 去重/类型推断注册——"不得重复读取材料"程序化
- ✅ **School Requirement Context**（`school_requirements.py`）：模板结构机械提取+逐字段 provenance（official/sample/default/unknown）；样文永不冒充 official；PDF 规范不猜测
- ✅ **Research Context 聚合**（`research_context.py`）：13 注册表只读统一视图（OK/NOT_APPLICABLE/ERROR）
- ✅ **阶段调度矩阵 + 交付五态**（`stage_routing.py`）：S1~S10 出口/前进边/AI 挂载点全配置化；route() 只判定不执行
- ✅ **Thesis Orchestrator**（`thesis_orchestrator.py`）：Action 模型 JSONL 留痕（禁止静默执行）；五策略 Failure Recovery；drift 检测不静默覆盖
- ✅ **Figure Provider 契约**（`figure_iface.py`）：plan/generate/validate + 生命周期 PLANNED→GENERATED→VALIDATED→EMBEDDED→VERIFIED；研究链接硬关卡；不复制 Figure Engine
- ✅ **统一 Thesis Build + Manifest**（`thesis_build.py`）：build-contract.yaml 七域；双模式组装；固定顺序 pipeline；失败四元组裁决；artifact-manifest content_identity
- ✅ **Delivery Gate 全聚合**（`delivery_gate.py`）：格式链+构建步+文档/manifest+图生命周期+研究侧+人工双队列 → 五态终局；缺证据=BLOCK、ERROR 不透 PASS

v1.5.0 在 v1.4.1 稳定基线之上新增研究智能层（发现→诊断→修复→再验证闭环），既有能力只增不破：
- ✅ **Research Design Registry**：design.yaml/scope.yaml/repairs.yaml 三注册表（随注册表引擎，缺省 N/A 兼容旧项目）
- ✅ **方法选择审计 + Research Feasibility Gate（RF-01~10）**：needs⊆provides、evidence_requirement×实际数据、
  候选≥2+选择理由；判定 FEASIBLE / CONDITIONALLY_FEASIBLE / INFEASIBLE（INFEASIBLE 不继续正常生成）
- ✅ **统一诊断引擎**：19 类 issue_type（诊断条目含根因/影响/修复选项/置信度），auto/queue/block 三通道分流，
  稳定 DIAG ID（severity+payload 消歧）；范围控制（scope creep）与数字一致性（425.4≡425.40≡425）检测
- ✅ **Repair Plan Registry + 白名单自动修复**：REP-XXX 全 before/after 留痕 + 复检；仅 4 操作
  （论断降级/摘要数字同步/受控 recompute/模拟标签回填）；recompute 受控执行模型（仅项目内 .py，无 shell）；
  白名单外一律人工（禁止捏造数据/扩范围/换方法/静默裁决冲突）
- ✅ **Research Agent Loop**：PLAN→ANALYZE→DETECT→DIAGNOSE→REPAIR→RE-ANALYZE→VALIDATE→ACCEPT；
  MAX_ITERATIONS=5（无改善即停）；迭代日志 loop-log（事实+规则，不含内部推理）；
  终态 BLOCK / PASS_WITH_HUMAN_REVIEW / PASS_WITH_WARNINGS / PASS；人工队列 approve/reject/modify 持久裁决
- ✅ **8 维 Research Quality Score**：Research Design/Evidence/Data/Analysis/Argumentation/Conclusion/Citation/Coherence；
  Critical/High 未解决时 blocked=True，总分不得作为交付依据
- ✅ **Delivery Gate 集成**：旧项目（无 design/scope）NOT_APPLICABLE 不阻塞；回归 tests/v1_5（418 断言）+
  test-7.0 端到端 + t30~t60 证据见 tests/v1_5/v1.5-regression-report.md

v1.4.1 在 v1.4.0 Research Integrity Layer 之上做稳定性与产品化（不新增大型功能）：
- ✅ **统一状态模型**：PASS / WARN / FAIL / NEEDS_HUMAN_REVIEW / NOT_APPLICABLE / SKIPPED_WITH_REASON / ERROR；
  FAIL 附 severity+reason+remediation；异常/注册表损坏 → ERROR（退出码 3），绝不伪造 PASS
- ✅ **NEEDS_HUMAN_REVIEW 人工复核回路**：弱证据语境下 RQG-09/RQG-10 不得自动 PASS——
  生成 `human-review-checklist.md`（claim/evidence/reason/uncertainty），Gate 记 `PASS_WITH_HUMAN_REVIEW`；
  裁决回填 `.aeromech/research/human-review.yaml`（ok→PASS；violation→FAIL）；规则见 `references/research-human-review.md`
- ✅ **无模板 QA**：`tf_qa` 可无模板运行——模板对照项记 `NOT_APPLICABLE`（不伪造 PASS、不阻塞 Delivery Gate）；
  模板路径不存在 = 配置错误（退出码 3），不得静默降级
- ✅ **开发/安装目录规程**：`Desktop\thesis-skill\aeromech-thesis`（权威开发源）⇄
  `.qoder-cn\skills\aeromech-thesis`（部署副本）经 `sync.py --check/--to-install/--to-dev` 同步
  （DEV_SYNC.md / INSTALL_SYNC.md）
- ✅ 新增 `tests/v1_4_1/`（5 个测试文件：NOT_APPLICABLE / 人工复核 / Gate 状态 / 目录同步 / 防伪 PASS）

v1.4.0 研究完整性与证据可追溯层（`.aeromech/research/` 注册表 + RQG-01~15 门禁）：
- ✅ RQ（研究问题）/ Method / Evidence / Dataset / Analysis / Computation / Claim / Conclusion / Figure-Table / Conflict 十类注册表
- ✅ Research Traceability Graph（RQ→Method→Evidence/Data→Analysis→Figure/Table→Claim→Conclusion→Abstract，orphans 检测）
- ✅ Synthetic Data Ledger（模拟数据身份保持：label 强制、不得伪装实测、覆盖正文/图表/结论）
- ✅ Computation Provenance（CALC-XXX：inputs/formula/verification/used_in，可复现可解释）
- ✅ Abstract ↔ Body 一致性（数值域包含、身份措辞、结论覆盖；否定语境豁免）
- ✅ 证据越界检测（模拟/未核实证据 × 强断言口径 → Critical，阻止 Delivery Gate）
- ✅ Evidence Coverage Ratio（verified/partial/pending/simulated 四分类，simulated 不并入 verified）
- ✅ Conflict Resolution（登记 source_a/source_b/resolution/reason，禁止静默选择）
- ✅ Delivery Gate 集成（研究完整性 Critical/High 阻止交付；旧项目注册表缺失不阻塞）

既有能力（v1.0~v1.3.11 持续保留）：

当前版本已完成的核心闭环：
- ✅ 十阶段状态机（S1-S10，支持回退和多轮恢复）
- ✅ 材料管理机制（materials.yaml + 来源等级 L1-L5）
- ✅ 学校模板可选机制（三层格式结构：general_principles / general_defaults / school_specific_unknown）
- ✅ 工程分析能力（FMEA/FTA/RCA 框架）
- ✅ 数据分析能力（描述统计 + 计算审计）
- ✅ 图表生成（Mermaid + matplotlib fallback）
- ✅ 引用完整性审计（claim → material_id → source）
- ✅ QA 论文体检（六大维度 + 四级风险分级）
- ✅ 答辩准备（PPT 结构 + 多版本答辩稿 + 预测问题库）
- ✅ DOCX/PDF 生成（真正可编辑，图表嵌入）

**v1.0.0 delivery pipeline stabilization**（真实 39 页论文 PDF 验证通过）：
- ✅ PAGE_FLOW_OPTIMIZER（整体页面流；图块高度分级；B 类低占用豁免）
- ✅ Native TOC update（Word COM 两轮更新，页码与正文一致 10/10）
- ✅ PDF TOC QA（TOC-01~10）
- ✅ PDF structural QA（16 项）
- ✅ PDF visual regression（占用率 + A/B 类判定）
- ✅ Delivery Gate（Critical/High/Medium/Low 分级）
- ✅ PDF 为最终真值原则

## 12. 已知限制

1. **学校正式模板缺失时**：只能使用通用默认格式（宋体、小四、1.5倍行距等），这些仅为 fallback 默认值，不代表任何学校正式要求。获取正式学校模板后将自动覆盖。
2. **Mermaid 依赖**：需要系统安装 Google Chrome。若 mmdc 不可用，会自动 fallback 到 matplotlib 生成替代图。
3. **FMEA 评分**：S/O/D/RPN 如果没有真实依据不能伪造，只能提供分析表骨架，需用户回填真实数据。
4. **参考文献**：Skill 不提供具体可引用的文献条目，只提供检索策略和文献登记表框架。用户需自行从 CNKI/万方等数据库检索真实文献。
5. **学校格式最终确认**：即使使用通用默认格式生成了 DOCX/PDF，最终仍应以学校正式发布的格式要求为准。建议在提交前对照学校模板进行最终检查。

## 13. 常见使用示例

### 示例 A：没有学校模板

```
用户：调用 aeromech-thesis，开始我的毕业论文项目。我是飞行器维修工程技术专业学生，题目是《基于FMEA的A320飞机起落架系统故障模式与维修策略研究》。

Skill：检测到无学校模板，进入 No-School-Template Mode。使用通用工科论文默认格式，学校特定字段标【学校格式待提供】。不阻塞后续流程。

[... 经过 S1-S10 全流程 ...]

Skill：论文生成完成。由于未提供学校模板，当前使用通用默认格式。如需应用学校正式格式，请提供学校模板后说"我提供了学校模板，请重新应用格式"。

最终交付：毕业论文.docx + 毕业论文.pdf
```

### 示例 B：提供学校模板

```
用户：我提供了学校模板，请重新应用格式。

Skill：检测到 materials/school/ 中有新的学校模板。正在解析...

解析完成：
- format_source: general_default → school_template
- format_status: partial → complete
- 更新 school-format.yaml 中的字体、字号、行距、页边距等字段

正在重新应用格式层：
- 读取现有论文章节（正文内容不变）
- 应用新学校格式生成 DOCX
- 检查图表编号/题注/页码/参考文献格式
- 运行 QA
- 重新导出 DOCX/PDF

完成！毕业论文.docx 和 毕业论文.pdf 已更新为学校格式。
```

### 示例 C：提供资料

```
用户：这些是我的参考文献、维修手册和任务书，请登记并开始分析。

Skill：正在登记材料...
- 文献：5 篇 CNKI 题录 → 建立文献登记表，标【待核实】直到用户确认可核实的来源
- 维修手册：AMM 32 章（起落架）→ 登记为 technical_manual，来源等级 L2（user_provided）
- 任务书：登记为 school 材料

材料登记完成。现在开始 S3 研究计划阶段...
```

## 14. 用户最重要的注意事项

**您不需要**：
- ❌ 编辑 SKILL.md
- ❌ 编辑 state.yaml
- ❌ 编辑 materials.yaml
- ❌ 编辑 school-format.yaml
- ❌ 编辑 Python 脚本
- ❌ 手动生成 Mermaid 图表
- ❌ 手动生成 DOCX/PDF
- ❌ 手动调用内部 Agent（Figure Agent / Data Agent / QA Agent 等）

**您主要负责**：
- ✅ 提供真实论文材料（学校模板、文献、手册、数据等）
- ✅ 确认选题和研究方向
- ✅ 对关键研究判断进行确认（如 FMEA 评分依据、数据来源等）
- ✅ 提供真实数据和资料（不得要求 Skill 虚构）
- ✅ 最终审核论文内容

**简单来说**：您只需通过自然语言对话提供材料和确认决策，Skill 会自动完成所有技术操作。

## 15. README 的原则

本 README 描述的是 **aeromech-thesis v1.6.5** 当前已实现的能力。任何未来功能必须先实现并通过测试，再更新 README，不得为了宣传而提前声明未实现功能。

如发现本文档与实际实现不一致，请以实际实现为准。欢迎反馈文档错误。

## 版本记录

- v1.6.5 — Academic Figure Quality & User-Configured Image Provider：figure_style.py（学术视觉单一来源：
  3 轮量化验证调色板/字号阶梯/间距/图类型）+ figkit.py role= 语义角色色 + style_fingerprint + mermaid 回退
  fail-closed（自证式 PASS 移除：FIG-05/06 删除、GQ-15→SKIP）；figure_visual_qa.py（VIS-01~12 入
  thesis_build QA 链 + Delivery Gate figure_visual 域）；image_config.py（process→skill→~/.aeromech/.env
  解析链 + SecretStr 全掩码 + image_cli config/status/test/remove）；image_backends.py（OpenAI 兼容
  b64 生图 + 8 类错误分类 + 可注入 transport）；ai_figure_gate.py（Figure Plan 九字段闸：缺 Plan=
  FIGURE_PLAN_REQUIRED+零 HTTP；确定性类型 local 优先；结构化提示词+prompt_hash；provenance 白名单；
  IMAGE_MAX_ATTEMPTS=3 成本闸+首次费用明示）；research_integrity ai_generated_visual 禁
  verified/partial；secret_leak_qa（repo/diff/artifacts，发布态 FAIL=0）；graph_quality 渲染测量校准
- v1.6.0 — Full-Stack Thesis Orchestration：thesis_state.py（StateIO 程序化迁移校验 + CK-XXX 检查点/SHA256 +
  resume from_start=false + drift 检测）；material_ingestion.py（统一材料进入，SHA256 去重"不得重复读取"）；
  school_requirements.py（字段级 provenance official/sample/default/unknown，PDF 规范不猜测）；
  research_context.py（13 注册表只读聚合）；stage_routing.py（S1~S10 调度矩阵 + 交付五态判定，route 只判定）；
  thesis_orchestrator.py（Action 模型 JSONL 禁止静默执行 + 五策略 Failure Recovery + Agent Loop 集成）；
  figure_iface.py（FigureProvider 契约 + 生命周期 PLANNED→VERIFIED，不复制 Figure Engine）；
  thesis_build.py（build-contract.yaml 七域 + 双模式组装 + 固定顺序 pipeline + artifact-manifest content_identity）；
  delivery_gate.py（全证据域聚合五态终局，缺证据=BLOCK、ERROR 不透 PASS）；references/orchestration.md 规则总纲；
  test-8.0 全栈冷启动验收（新校模板 TEMPLATE_FIDELITY、四断点恢复实测、隐藏缺陷自查含 2 项 DETECTION FAILED
  修复复验、人工复核 7/7、delivery_gate=PASS）；修复 8 类根因缺陷（表体静默丢失/契约 tables 未接通/生命周期
  TABLE 污染/封面检测器硬编码旧校口径/QA 章数附录数硬编码/COM 往返剥格式/正文级强断言与悬空图引用检测缺口/
  HTML 实体残留）；tests/v1_6（14 文件 395 断言 + test_document_contract 文档=代码一致性锁）。
- v1.5.0 — Research Intelligence & Agent Loop：design/scope/repairs 注册表；research_design.py（方法选择审计 +
  RF-01~10 可行性门禁）；research_diagnosis.py（19 类 issue_type 统一诊断+根因+auto/queue/block 分流+范围控制+数字一致性）；
  research_repair.py（REP 计划 + 白名单自动修复 + recompute 受控执行 + apply-human 裁决执行）；research_agent_loop.py
  （≤5 轮闭环 + loop-log + 终态）；research_quality_score.py（8 维评分，Critical 不被总分掩盖）；
  Delivery Gate/state.md §17.1/SKILL.md §20 集成；test-7.0 端到端验收（植入 7 类缺陷全部捕获）；
  修复 B1~B10（Citation 维可达、severity 归一、recompute 白名单、diagnosis_id 消歧、裁决持久化、
  数字基准选择、RQG-14 文档同义词、pdf_qa 环境码 3 等）；tests/v1_5（13 文件 418 断言）。
- v1.4.1 — Stability & Production Hardening：统一状态模型（PASS/WARN/FAIL/NEEDS_HUMAN_REVIEW/NOT_APPLICABLE/SKIPPED_WITH_REASON/ERROR + severity/reason/remediation）；RQG-09/RQG-10 语义项人工复核回路（human-review-checklist + human-review.yaml；PASS_WITH_HUMAN_REVIEW）；tf_qa 无模板运行（NOT_APPLICABLE，配置错误退出码 3）；开发/安装目录同步规程（DEV_SYNC/INSTALL_SYNC + sync.py）；tests/v1_4_1（5 测试）。
- v1.4.0 — Research Integrity & Evidence Traceability：Research Integrity Layer（`.aeromech/research/` 10 类注册表 +
  traceability.json）、research_integrity.py（注册表引擎：validate/trace/coverage）、research_quality_qa.py（RQG-01~15，
  Critical/High 阻止 Delivery Gate，旧项目 not_initialized 不阻塞）、Synthetic Data Ledger、Computation Provenance、
  Abstract↔Body 一致性、证据越界检测、Conflict Resolution；tests/v1_4/（11 个测试文件 + run_all.py）。
- v1.3.11 — Legacy .doc 材料处理（detect_legacy_docs/convert_legacy_doc）、QA 通用化修复、finalize_metadata.py。
- v1.3.0~v1.3.10 — Cover/Page/Figure/Table Fidelity、Table Landscape、Graph Quality、Cover Fill/Color Fidelity 各批次。
- v1.2.0 — Cover Fidelity introduced（COVER_FIDELITY_MODE / CF-01~25）。
- v1.1.0 — Template Fidelity introduced：双模式（TEMPLATE_FIDELITY / FORMAT_RECONSTRUCTION）、模板母版驱动、
  页码防重启/表格分隔/题注跨空行纪律、tf_qa.py（TF-01~20）、Test A/B。
- v1.0.x — delivery stabilization：docx_engine、update_toc、export_pdf、pdf_qa、visual_regression。
