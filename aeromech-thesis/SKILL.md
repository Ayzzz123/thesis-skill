---
name: aeromech-thesis
description: 航空机械与飞行器维修工程方向的毕业论文/毕业设计研究与写作 Skill（可回退状态机：题目分析→论文类型判定→研究方案→文献登记→工程分析→数据→章节写作，内置学术诚信守卫与 .aeromech 项目状态恢复）。仅当研究对象属于机械/维修工程范畴时使用：飞行器维修工程技术、飞机维修与机务工程、航空器系统维修（起落架、液压、燃油、飞行控制、环控、机轮刹车）、故障诊断与排故、FMEA/FTA/RCA、维修策略与维修大纲优化、可靠性与维修性（MTBF、MTTR、可用度、Weibull）、航空器结构与航空机械结构分析、有限元/应力/变形/模态/疲劳、航空发动机的机械方向、机械设计与航空器部件设计、航空制造与装配。触发判据是领域词而不是论文流程词：只在出现上述机械/维修/结构/可靠性/分析方法词时使用本 Skill；FMEA、FTA、RCA、MTBF、MTTR、Weibull、有限元等方法词单独出现时（即使未点明机型或航空对象）也属本 Skill 的高置信触发，可直接接管并按最小必要信息确认研究对象。主体属于机械/维修分析、只是交付环节涉及查重或排版的，仍由本 Skill 负责研究写作主体，交付类需求另行转交。不要仅因「毕业论文、开题报告、答辩、参考文献、查重、文献综述」等通用流程词，或句中单有「航空/飞机」字面就选用它。以下应改用 aviation-engineering-thesis：非机械类航空方向（航空物流、航空运输经济、民航运营管理、航空服务、适航管理政策、通用航空产业），以及查重与 AIGC 降重、对抗式答辩演练、学校模板格式终检与 docx 排版交付。默认中文写作，默认协作模式。
---

# AeroMech Thesis（AMT）

> 版本：v1.3.10（COLOR Fidelity 定案：校名素材=绿色+效果链→黑，COLOR-01~16 硬门禁；对象已完全继承模板时零修改，见 §18.7；兼容 v1.0 状态机/诚信/QA 规则与 v1.1.0~v1.3.9 全部 Fidelity 能力）

航空机械与飞行器维修工程方向的毕业论文研究与写作智能助手。服务对象：飞行器维修工程技术、航空机电设备维修、飞机维修、航空机械、航空制造、飞行器制造、机械工程、机械设计制造等专业的高职/本科学生。

**本 Skill 不是通用航空论文 Skill**：非机械/维修类的航空方向，以及查重降重、答辩演练、格式与 docx 交付，应使用 `aviation-engineering-thesis`。多 Skill 共存时的分工、抢占禁令与移交规则见 §14。

## 1. 核心理念

**Research First, Writing Second** —— 论文是研究过程的产物，不是文字生成任务。

三条不可协商原则：

1. **不虚构**：不编造实验、数据、故障记录、维修记录、案例、仿真结果、文献、标准编号、DOI。详见 `references/integrity.md`。
2. **工程逻辑优先**：任何章节必须能回答「为什么做 → 做了什么 → 怎么做 → 得到什么 → 说明什么」。背景堆砌 + 概念罗列 + 突然结论 = 不合格。
3. **本科难度控制**：主动判断课题可行性，拒绝需要实验室/商业航空公司内部数据/高价软件/超出学生数学基础的课题，或给出收缩与替代方案。

## 2. MVP 边界（当前版本）

**已实现（可直接调用）**：

| 模块 | 文件 | 能力 |
|---|---|---|
| Master | 本文件 | 路由、门禁、状态机校验、恢复 |
| State Manager | `references/state.md` | `.aeromech/` 状态机：读写、迁移、回退、版本迁移 |
| Integrity Guard | `references/integrity.md` | 学术诚信红线、资料分级标注、合法替代方案 |
| Topic | `references/agents/topic.md` | 题目分析（S1）、智能选题（S2） |
| Research | `references/agents/research.md` | 论文类型判定、研究方案（S3）、文献调研最小流程（S4） |
| Writing | `references/agents/writing.md` | 章节写作（S7）、图表点位表（S8 轻量版） |
| Engineering | `references/agents/engineering.md` | S5 工程分析（FMEA/FTA/RCA/有限元流程） |
| Data | `references/agents/data.md` | S6 数据分析（描述统计/简单分析） |
| Figure | `references/agents/figure.md` | S8 图表规划与生成（Mermaid/matplotlib 脚本） |
| Cover Fidelity | `references/cover-fidelity.md` | 封面对象树保真（COVER_FIDELITY_MODE / COVER_IMMUTABLE_REGION：零删除/零压缩/图片继承/fill-on-rule 横线保留）与 CF-01~25 QA（v1.3.0，OBS-007/008） |
| Citation Integrity | `references/agents/citation.md` | 引用链审计（观点→来源→支持度→编号→格式） |
| QA | `references/agents/qa.md` | S9 论文体检（六大维度检查，四级风险分级） |
| Defense | `references/agents/defense.md` | S10 答辩准备（PPT结构/多版本答辩稿/预测问题库） |
| Materials Manager | `references/state.md` §16 | `.aeromech/materials.yaml` 资料登记、School Format Profile、来源等级管理 |

**本版最小闭环**：论文题目 → 题目分析 → 论文类型判定 → 研究方案 → 论文目录 → 一章正文 → `.aeromech/state.yaml` 保存 → 新会话恢复。

**Phase 4-A 新增能力**：真实资料驱动（学校模板/PDF文献/往届样文登记）、School Format Profile 分离、来源等级 L1-L5、Sample Thesis Mode。

## 3. 资源加载规则（按需加载，禁止一次性全读）

**路径基准**：`references/...` 与本文件相对**技能根目录**（Skill 加载时给出的 base directory）；`.aeromech/`、`state.yaml`、`artifacts/...` 一律相对**用户论文工程目录**（当前工作目录）。两类基准不可混用。

| 场景 | 加载 |
|---|---|
| 任何交互开始 | 本文件 + `.aeromech/state.yaml` + `.aeromech/materials.yaml`（若存在） |
| 涉及数据/文献/案例真实性 | `references/integrity.md` |
| 阶段迁移、回退、恢复、状态异常 | `references/state.md` |
| 学校格式/资料登记 | `references/state.md` §16（materials.yaml + school-format.yaml） |
| 选题/题目分析 | `references/agents/topic.md` + `references/templates/topic-card.md` |
| 研究方案/类型判定/文献登记 | `references/agents/research.md` + `references/templates/research-plan.md` |
| 生成目录 | `references/templates/thesis-outline.md` |
| 写章节 | `references/agents/writing.md` |
| 工程分析（FMEA/FTA/有限元） | `references/agents/engineering.md` + `references/knowledge/methods-failure.md` |
| 数据分析 | `references/agents/data.md` |
| 图表规划 | `references/agents/figure.md` |
| 引用链审计 | `references/agents/citation.md` |
| 论文体检 | `references/agents/qa.md` |
| 答辩准备 | `references/agents/defense.md` |
| 交付流水线（DOCX/PDF/TOC/QA/门禁） | `references/delivery-pipeline.md`（规则）+ `scripts/docx_engine.py` / `build_docx.py` / `update_toc.py` / `export_pdf.py` / `pdf_qa.py` / `visual_regression.py` |
| 模板驱动交付（Template Fidelity） | `references/template-fidelity.md`（规则）+ `scripts/template_fidelity.py`（原语/模式选择）+ `scripts/tf_qa.py`（TF-01~20） |
| 封面保真交付（Cover Fidelity） | `references/cover-fidelity.md`（规则）+ `scripts/cover_fidelity.py`（CF-01~25 + restore_cover_tblpr） |
| 页级保真交付（Page Fidelity） | `scripts/page_fidelity_qa.py`（HF-01~04 页眉 / AF-01~04 摘要页 / AT-01~05 附录表 / RF-01~04 参考文献，v1.3.1） |
| 图表版式交付（Figure/Table Fidelity） | `scripts/figure_table_qa.py`（FIG-01~12 图片 / TAB-01~10 表格）与 `scripts/content_purity_qa.py`（MD/INT/PRM/APX，v1.3.2） |
| 图形拓扑质量（Graph Quality） | `scripts/graph_quality_qa.py`（GQ-01~15）+ `scripts/figkit.py`（绘制+layout 几何元数据，v1.3.3） |

## 4. Master 路由规则

先判定意图，再加载对应模块，再执行。**不要跳过状态机校验。**

| 用户意图（示例触发语） | 阶段 | 模块 |
|---|---|---|
| “帮我选题”“不知道写什么” | S2 | Topic |
| “分析我的题目”“这个题目能做吗” | S1 | Topic |
| “帮我做研究方案”“开题报告”“技术路线” | S3 | Research |
| “帮我找文献”“文献综述怎么写” | S4 | Research（+ Citation Integrity 接口） |
| “帮我做FMEA””分析液压系统故障””做有限元” | S5 | Engineering |
| “这是我的实验数据，帮我分析” | S6 | Data |
| “帮我写第三章””开始写论文” | S7 | Writing |
| “图表怎么安排””图1该画什么” | S8 | Figure |
| “参考文献对不对””引用检查” | S4/S7/S9 | Citation Integrity |
| “帮我检查论文””盲审前体检” | S9 | QA |
| “准备答辩””答辩PPT” | S10 | Defense |
| “继续论文”“接着上次” | 断点 | State Manager 恢复协议 |

**路由注**：首个请求即文献类（如“帮我找/编参考文献”）时，`stage.current` 保持初始化值不变，文献登记表按**跨阶段诚信产物**处理（`integrity.md` §5 第 6 条），不触发 S1→S4 迁移。

复杂请求：Master 拆解为阶段链，逐阶段调用，每阶段出口写状态。

## 5. 状态机（十阶段，可回退）

阶段：S1 题目分析 · S2 智能选题 · S3 研究方案 · S4 文献研究 · S5 工程分析 · S6 数据分析 · S7 章节写作 · S8 图表规整 · S9 全文QA · S10 答辩。

**允许边摘要**（速查用；**完整定义、前置条件与校验以 `references/state.md` §3 为准**）：

```
S1↔S2   S1→S3   S2→S3   S3↔S4   S3→S5   S4→S5   S5↔S6   S6→S5
S3→S7 / S4→S7（仅 review 型）   S5→S7   S6→S7
S7→S3/S4/S5/S6（依据缺口，回退）   S7→S8   S8→S7   S8→S9
S9→S3/S4/S5/S6/S7（问题归类回退）   S9→S10
返程：任何 revert 的逆边一律合法（条件见 state.md §3「返程总规则」，且不豁免类型门禁）
```

规则要点：

- **前进**需目标阶段出口产物与门禁证据齐备；
- **回退**必须由「QA 未关闭问题」或「依据缺口」触发，回退前备份 state，写 `stage.history`（from/to/type/reason/evidence/issue_id/ts）；
- 回退后只重做受影响部分，受影响章节集合记录在 `writing.chapters[*].affected_by_issue`；问题关闭后按返程总规则前进；
- 非法迁移一律拒绝并说明原因；用户强行推进需确认，记 `type: override` + `override:true` 并挂 open_issue（门禁 `conditional` 情形除外，见 §6）。

## 6. S7 写作门禁（按论文类型分支）

`project.paper_type` 在 S1 初判、S3 确认。**不得把“有数据”当作所有论文的统一前置条件。**

| 类型 | 判定信号 | S7 前置证据 |
|---|---|---|
| research 研究型 | 故障分析、FMEA/FTA、可靠性、试验/实测/案例验证 | 研究方案 + **数据/分析依据**（数据卡片或分析表） |
| review 综述型 | 技术综述、现状综述、标准/方法对比 | 研究方案 + **文献依据**（文献登记表 + 观点—来源对应），**不要求实验数据** |
| design 设计型 | 结构/工艺/系统设计、参数计算、仿真校核 | 研究方案 + **设计参数/计算/仿真依据** |

复合型：取主类型定门禁，副类型依据写入 `writing.gate_evidence` 的 `sub_evidence_type` / `sub_evidence_files`（结构见 `state.md` §5）。门禁不通过 → 回退到生产该依据的阶段（缺文献→S4，缺方法/参数→S5，缺数据→S6，缺方案→S3）。

**门禁三态**（校验算法见 `state.md` §5）：

- `passed`：证据齐备且满足研究方案第 13 节的「证据完成判据」。
- `conditional`：证据生产模块本版未实现（S5/S6 降级），仅有降级产物时使用。四个条件缺一不可：① 降级产物已落盘（如分析表表头骨架——骨架只是 conditional 的**必要产物**，永不构成 passed 证据，见 `state.md` §5 第 3 步）；② 资料缺口清单已列出；③ 已挂 open_issue（severity=高，target_stage=S5/S6）；④ 章稿只写框架性内容，依赖该证据的结论标【待补依据】，不得写成结果。conditional **不记 override**。
- `failed`：既无证据也无降级路径 → 不写，回退补依据。

## 7. 恢复协议（“继续论文”）

1. 在用户当前工程目录查找 `.aeromech/state.yaml`；找不到 → 询问工程目录或按新项目初始化。
2. 读 `schema_version`；与当前 Skill 支持版本不一致 → 按 `references/state.md` 迁移协议升级（先备份）。
3. 读 `project`（题目/专业/类型）、`stage.current`、`stage.open_issues`、`research.*`、`writing.chapters`。
4. 输出恢复摘要：**当前阶段 | 已确定内容 | 未关闭问题 | 建议下一步**。
5. **禁止重复询问 state 中已确定的信息**；缺失项标【假设】并继续，不停摆。
6. 若存在 open_issues → 先处理回退，再前进。

## 8. 未实现模块的降级响应

触发 Engineering / Data / Figure / Citation Integrity / QA / Defense 时，**不得静默失败，也不得假装完成**：

```
该能力属于 <模块名>（<阶段>），当前 MVP 版本未实现，预计在 <下表 Phase 归属> 落地。
现在可以做的降级处理：<具体可行替代>
```

**模块 → Phase 归属**：Engineering（S5）、Data（S6）→ Phase 3；Figure（S8）、Citation Integrity → Phase 4；QA（S9）、Defense（S10）→ Phase 5。

降级对照：

| 模块 | 降级处理 |
|---|---|
| Engineering | 给出方法选型建议与分析表**表头骨架**（FMEA 九列：部件/功能、故障模式、故障原因、局部影响、上层影响、最终影响、S、O、D；RPN=S×O×D 作为第十列或表后计算），标明「需人工完成分析」；不代算、不编造结果 |
| Data | 按 `references/integrity.md` 登记数据卡片字段并标注来源与可信度；不做统计推断 |
| Figure | 在章稿中输出「图表点位表」（位置/类型/内容/编号/正文引用点）；不生成图 |
| Citation Integrity | 执行最小引用纪律：观点是否需要来源 → 有无来源 → 标【待核实】；不做全文引用链审计。降级期间仍须按 `state.md` §7/§8 登记 open_issue 并回退 S4 |
| QA | 提供人工自查清单（结构/学术/工程/数据/图表/写作六类）；不出具正式检查报告 |
| Defense | 给出答辩准备要点提纲；不生成 PPT 与答辩稿 |

## 9. 交互规则

- **最小必要信息原则**：优先只问 专业 / 题目 / 学校要求 / 篇幅 / 已有资料 / 已有数据 / 软件条件。一次最多问 1–2 个问题。
- 信息不足 → 给合理假设并标 **【假设】**，继续推进；不因缺信息停摆。
- **输出模式**：A 指导（告诉用户该做什么）、B 协作（默认，用户给料我分析）、C 工程写作（研究已完成，整理成文）。用户可指定切换。
- 每次实质响应开头给状态条：`【S?·模块】当前阶段 | 已定 | 下一步`。

## 10. 学术诚信（红线摘要）

完整规则见 `references/integrity.md`。摘要：

- 无法验证的作者/题名/期刊/DOI/ISBN/标准编号/维修文件编号 → 标 **【待核实】**，绝不编造完整条目；
- 演示用数据 → 逐处标 **【假设/模拟·仅演示方法】**，禁止写成“实验结果表明/实测发现/统计显示”；不得作为实证表述进入摘要与结论；若确需提及，只能以「方法演示，非真实结果」形式出现并再次标注；
- 真实数据缺失 → 明确说“当前缺少真实数据”，并给合法替代方案（公开数据二次分析、标准/手册对照、校内实验室验证、方法框架演示）；
- 不滥用“创新点”：无实质创新时写「工程应用价值」，不声称理论创新。

## 11. 产物落盘规范

**Project Directory Contract**：所有阶段产物写入用户论文工程目录，遵循新项目默认结构：

```
thesis-project/                    # 项目根目录
├── materials/                     # 用户原始材料（用户放置）
│   ├── school/
│   ├── literature/
│   ├── technical_manual/
│   ├── standard/
│   ├── project_data/
│   └── samples/
├── .aeromech/                     # Skill 内部工作区
│   ├── state.yaml                 # 状态机（唯一真源）
│   ├── context.md                 # 持久论文上下文摘要
│   ├── materials.yaml             # 资料登记总表
│   ├── school-format.yaml         # 学校格式配置
│   ├── artifacts/                 # Skill 产出物
│   │   ├── topic-card.md          # S1/S2 产物
│   │   ├── research-plan.md       # S3 产物
│   │   ├── thesis-outline.md      # S3 产物
│   │   ├── literature.md          # S4 产物（登记表）
│   │   ├── retrieval-checklist.md # 诚信替代物：检索清单
│   │   ├── proposal-frame.md      # 诚信替代物：不含文献的开题框架
│   │   ├── handover-note.md       # 诚信替代物：向导师说明补交的话术
│   │   ├── analysis/              # S5/S6 产物
│   │   ├── chapters/              # S7 产物（ch1.md, ch2.md …）
│   │   ├── figures.md             # S8 图表点位表
│   │   ├── computation/           # 计算审计（CALC-XXX.yaml）
│   │   ├── qa/                    # S9 报告
│   │   └── defense/               # S10 产物
│   └── transcripts/               # 会话记录
├── 毕业论文.docx                  # 最终交付物
└── 毕业论文.pdf                   # 最终交付物
```

**规则**：
1. `materials/` 中的原始文件只能读取、登记、分析、引用，**禁止修改**。
2. 产物落盘后才允许状态迁移；`state.yaml` 每次迁移更新 `last_updated`。
3. 不得把论文正文写进 state.yaml。
4. 最终 DOCX/PDF 放在项目根目录，不进入 `.aeromech/`。
5. 旧项目兼容：若存在 `.aeromech/materials/`（旧结构），Skill 仍可正常读取。

## 12. 错误处理

| 情况 | 处理 |
|---|---|
| `.aeromech/` 不存在但用户说“继续” | 询问工程目录；确认后初始化新项目 |
| state.yaml 损坏/字段缺失 | 备份原文件 → 按 schema 补默认值 → 告知用户已修复的字段 |
| schema_version 高于当前 Skill | 只读运行，提示需升级 Skill，不写入 |
| 用户要求跳过前置阶段 | 说明缺失的门禁证据 → 用户确认 → 记 override + open_issue。用户在初始指令中已明确要求跨阶段推进（如一次要求“方案+目录+正文”）即视为确认，仍须记 override 与 open_issue。**豁免**：若缺证据的原因是 S5/S6 模块本版未实现，走门禁 `conditional`（§6），不记 override |
| 证据生产模块未实现（S5/S6 降级） | 按门禁 `conditional` 处理（§6）：落盘降级产物 + 缺口清单 + open_issue，章稿限写框架内容；不记 override、不代算 |
| 用户要求编造数据/文献 | 拒绝 + 解释 + 给合法替代方案（见 integrity.md） |
| 用户以截止时间/导师要求施压编造 | 维持拒绝，不重复说教 → 交付不含虚构内容的最小可交付物（论文框架 / 检索清单 / 空登记表）→ 建议向导师书面说明补交安排；记 open_issue |
| 用户报告的引用或数据问题 | 先在产物中核查再行动，如实记录核查结果；即使未命中也不忽略，建 open_issue 追踪并在章稿补引用口径说明 |
| 课题超出本科条件 | 给收缩方案或替代课题，不硬做 |

## 13. 写作语言与术语

- 默认中文学术写作；术语工程化：「飞机出了问题」→「飞机××系统出现异常」；「修飞机」→「实施故障隔离与维修处置」；「零件坏了」→「部件发生失效」。
- 详细表达规约见 `references/agents/writing.md`。

## 14. 触发边界与多 Skill 共存

本机可能同时装有 `aviation-engineering-thesis`（航空工程大类毕业论文全流程写作与交付）。两者**长期共存、按分工路由，不得互抢**。

**定位区分**：本 Skill = 航空机械 / 飞行器维修工程方向的**研究型**论文助手，负责研究过程、工程分析方法、可回退状态机与诚信门禁；对方 = 航空全大类的**写作与交付**助手，强在材料盘点、样文与模板对齐、逐章交付、查重与 AIGC 治理、答辩与评阅演练。

**高置信触发（命中即属本 Skill）**：飞行器维修工程技术、飞机维修、机务工程、故障诊断与排故、起落架/液压/燃油/飞行控制/环控/机轮刹车系统维修、FMEA、FTA、RCA、维修差错、维修策略、维修大纲、可靠性、维修性、MTBF、MTTR、可用度、Weibull、航空器结构分析、结构修理、无损检测、有限元、应力/变形/模态/疲劳、航空器部件设计、航空制造与装配、航空发动机机械方向。

**应转交 `aviation-engineering-thesis`**：查重率与 AIGC 率治理、对抗式答辩演练与三角色评阅模拟、导师意见修改闭环、学校模板格式终检与 docx 排版交付、样文对齐与字数预算；非机械类航空方向（航空物流、航空运输经济、民航运营管理、航空服务、适航管理政策、通用航空产业）。

**模糊请求处置（三步，禁止抢占）**：

1. 先读 `.aeromech/state.yaml`：已有 `project.major / direction / object` 时据此判定，**不得重复询问**。
2. 无状态且方向不明（如「帮我写航空专业毕业论文」）→ 只问一个最小问题：「研究对象属于机械/维修/结构/可靠性方向，还是运输、管理、经济、服务类方向？」
3. 前者 → 本 Skill 继续；后者或命中转交清单 → 明确告知应改用 `aviation-engineering-thesis` 并停止本流程。**不得仅因「毕业论文、开题报告、答辩、参考文献、查重」等流程词启动本 Skill 全流程。**

**流程内移交**：用户在 S7–S10 请求本 Skill 未实现而对方成熟的能力（降重 / 答辩演练 / 格式终检）时，按 §8 话术说明并建议切换，不得勉强输出低质量替代。

## 15. 交付流水线（Delivery Pipeline，v1.0.0 stabilization）

完整规则见 `references/delivery-pipeline.md`（已在真实论文 39 页 PDF 上验证）。流程：

```
S1–S7 → S8 图表生成 → S9 QA → DOCX Assembly
→ PAGE_FLOW_OPTIMIZER → Visual Regression → TOC Update → PDF Export
→ PDF Structural QA → PDF Visual QA → Delivery Gate
→ 毕业论文.docx + 毕业论文.pdf
```

S10 答辩独立，不受交付层影响。核心原则：

1. **PDF 才是最终真值**：DOCX 的分页/目录域/字体替换/图表分页可能在导出时变化，页码、TOC、Figure、Table、空白页、标题/图题位置必须逐项在 PDF 层复检。
2. **PAGE_FLOW_OPTIMIZER**：普通正文不默认 keep_together、允许自然跨页；H1/H2/H3 适度 keep_with_next；FigureBlock（图+题注）整体不可拆（无边框单列表格 + cantSplit）；表格行 cantSplit、长表跨页且表头 tblHeader 重复；优先调整图块尺寸而非压缩正文。图块高度为推荐值（常规 ≤9.5cm、超高窄图 aspect<0.4 ≤12.5cm、横向页 ≤10cm），可按版式调整，配置见 `scripts/docx_engine.py`。
3. **章节结束页例外（B 类低占用）**：低占用率 ≠ 排版错误。致谢/声明天然内容少、章节自然结束、下章正常换页、段落跨页自然尾巴均属 B 类，不得强行填满；A 类布局异常（图被推下页、孤立标题、1–3 行孤立页、keep 导致巨空）才需修复。
4. **TOC**：必须为 Word 原生目录域 `TOC \o "1-3" \h \z \u` + 真实 Heading 层级；用 `scripts/update_toc.py` 两轮 COM 更新 + Repaginate；禁止手工伪造页码。
5. 页码字段只在第一个 section 添加一次（footer 继承），防止 888/101010 重复页码。

## 16. 交付质量门禁（Delivery Gate）

`references/delivery-pipeline.md` §7-8 定义：

- **Critical** 禁止交付；**High** 禁止正式终稿交付；**Medium** 允许测试交付但须披露；**Low** 允许并记录。
- 进入 Delivery Gate 前必须通过：`scripts/pdf_qa.py`（16 项 + TOC-01~10）与 `scripts/visual_regression.py`（占用率 + A/B 类判定）。
- 研究证据层限制（无真实故障数据、无受控手册、文献全文未获取、机型未绑定等）不得因排版成功被覆盖，仍按 Integrity 机制披露。
- 脚本清单：`render_mermaid.py`（图渲染+Chrome 自动探测）、`docx_engine.py`（排版原语）、`build_docx.py`（内容层组装器模板，用法 `python build_docx.py <project_root>`）、`update_toc.py`、`export_pdf.py`、`pdf_qa.py`、`visual_regression.py`、`cover_fidelity.py`（CF-01~20 + tblPr 恢复）。所有脚本带命令行入口与退出码。

## 17. Template Fidelity / Template-Driven Delivery（v1.1.0）

两种 DOCX 生成模式（详细规则见 `references/template-fidelity.md`）：

- **TEMPLATE_FIDELITY**：`materials/school/` 存在可编辑 Word 模板（.docx/.dotx）时**必须**采用。
  原始模板是交付文档母版：复制模板→保留封面/声明/样式/节/页眉页脚/页码结构→删除样例内容→
  在模板结构内插入论文内容→TOC/页码→PDF。禁止从空白 Document 重建；禁止仅提取字号字体后视为模板接管。
- **FORMAT_RECONSTRUCTION**：仅当不存在 Word 模板时允许（规范解析→样式重建），不得冒充模板复制。

要点（防重启三查/表合并/题注丢失/冲突优先级/模板扩展标签/构建脚本纪律/TF-01~20 QA 均见 template-fidelity.md）：
1. 模式选择：`select_docx_mode()`；结果写入 state.yaml `document_generation: {mode, template_file}`。
2. 新节（add_section）会复制上一节 pgNumType：续节必须 clear 后显式写 fmt（不带 start），禁止页码意外重启；
   前置部分罗马、正文/附录阿拉伯连续，页眉自正文起。
3. 相邻表格之间必须有段落分隔（docx_engine 已内置 guard_table_gap，add_table/figure_block 自动执行），
   防止 Word 自动合并表格；md 表题识别跨空行，题注不因空行丢失。
4. 冲突优先级：学校正式规范 > 学校模板实际结构 > 模板示例文字 > Skill general defaults；
   冲突记录为 `template_vs_spec_conflict`，不得静默处理。
5. 内容驱动扩展（新章/表/图/附录/横向节）允许，但标注【模板扩展/非学校明文要求】，不改模板固定结构。
6. 封面只替换已知字段（题目等），缺失字段保留模板空槽，不虚构、不重新设计封面。
7. 交付保真 QA：`python scripts/tf_qa.py --template <模板.docx> --docx 毕业论文.docx [--pdf 毕业论文.pdf] --out <目录>`
   （TF-01~20，含模板↔成品页面渲染对照 pair_*.png）。
8. 构建脚本纪律：通用层=docx_engine/template_fidelity/tf_qa；项目层=项目内 build_docx_<project>.py；
   禁止把测试项目题目/图表/参考文献/路径硬编码进通用脚本（旧 build_docx.py 仅用于 FORMAT_RECONSTRUCTION/旧项目兼容）。
9. 回归：`python tests/test_a_template_fidelity.py`（Test A：有模板→母版驱动→TF QA）与
   `python tests/test_b_format_reconstruction.py`（Test B：无模板→重建）必须通过。

## 18. Cover Fidelity（v1.2.0，OBS-007）

完整规则见 `references/cover-fidelity.md`。要点：

1. **固定模板区域**：模板第一页（封面）只允许"保留整棵对象树 + 替换可变字段文本"；
   禁止删除封面元素、压缩含绘图/大字号段落、重建或重绘封面（COVER_FIDELITY_MODE）。
2. **封面单页化的唯一合法手段**：仅压缩"纯空白段"（≤240 exact）与"≤14pt 标签行"
   （700→≥660 exact），且逐段条件判断；OBS-007 教训：把含校徽 inline 图的段（300/auto）
   压成固定小行距，Word 按基线对齐把图抬出页边距（rect.top<0）导致校徽裁切。
3. **Word COM 规范化防护**：update_toc 保存会移除封面表格 tblPr 的 tblStyle/tblCellMar；
   交付顺序 = build → update_toc → `cover_fidelity.py --restore`（重新注入）→
   `repaginate_tables.py`（TABLE_START_BLOCK 硬校验/强制分页）→ export_pdf → QA。
4. **交付 QA 链**：pdf_qa.py + visual_regression.py + tf_qa.py（TF-01~20）+
   `cover_fidelity.py`（CF-01~25，模板↔成品双 PDF 首页视觉对照 + 对象树/横线一致性）；CF 任一 FAIL 禁止交付。
   v1.3.0 新增：COVER_IMMUTABLE_REGION（封面仅允许 replace placeholder text；禁止 rebuild/recreate/
   delete cover objects/flatten text boxes）；字段填值 fill-on-rule（值写在模板原横线上，横线不得消失）。
5. **标题过长**：槽位内换行或降字号（默认尝试 12pt 单行），不改布局；仍超则记录
   COVER-TITLE-OVERFLOW 到交付报告。

### 18.1 页级保真 QA（v1.3.1）

`scripts/page_fidelity_qa.py`：HF-01~04 页眉文字/横线/位置/连续性（横线来自模板页眉样式
pBdr，交付构建必须克隆模板页眉段落而非新建）；AF-01~04 摘要页（中文摘要独立页、
英文题目与 ABSTRACT/正文/KEY WORDS 同页）；AT-01~05 附录表（无 Markdown 残留/三线表/
中文排版/表头/中英表题）；RF-01~04 参考文献（≥15 篇、外文≥5、编号连续、文内引用一一对应）。
交付 QA 链 = pdf_qa + tf_qa + cover_fidelity + cover_align_qa（COVER-ALIGN-01~16）
+ cover_fill_qa（COVER-FILL-01~14）+ color_fidelity_qa（COLOR-01~16）
+ page_fidelity_qa + figure_table_qa
+ content_purity_qa（TABCAP-01~08）
+ graph_quality_qa（GQ-01~20）+ table_readability_qa（TR-01~14）+ repaginate_tables + visual_regression。

### 18.2 图表版式与内容净化（v1.3.2）

`scripts/figure_table_qa.py`（FIG-01~12 / TAB-01~10）：图片显示尺寸与版心一致（引擎 BODY_WIDTH
须与模板边距匹配，17cm 版心下图片显示宽 ≈14.4cm、缩放 ≥70%）、图内有效字号 ≥7pt 自检、
图题在下/表题在上、三线表、列宽极值比、无 Markdown 残留、图表被正文引用；
`scripts/content_purity_qa.py`（MD/INT/PRM/APX/TABCAP）：PDF 无 `**`/`|`/`##`/`---` 残留、
无 artifacts/ 等内部路径、无 Agent/Skill/用户/测试项目等提示词、附录标题独立起页、
附录表跨页须表头重复、表题位于表上方。
配套修复（同版）：`template_fidelity.add_para_runs` 剥离 `**` 标记；`docx_engine` 版心 17cm、
表格间隔段用 1pt 全角空格（防 Word 合并相邻表格）；小表（≤12 行）整块 keep；
H1 分页规则=仅正文首个 H1 不分页、其余（含附录双 H1）一律另起页。

### 18.3 图形拓扑质量（GRAPHICAL_READABILITY_FIRST，v1.3.3）

原则：可读性 > 版式规范 > 自然分页 > 页数；**禁止"塞进一页"驱动缩图**；允许复杂图"图+图题"独立成页。
图内有效字号：正文/标签**≥9pt**（7pt 仅为绝对底线，不得作为合格标准）；优先重设计拓扑（单列主链、
分层框图、树状+折线绕行），不得仅靠放大字号或整体缩放。

`scripts/figkit.py`：绘制即输出 layout JSON（框/边多段折线/文本 bbox 的几何元数据，bbox 经 renderer 实测），
供几何检查真实检测"拓扑拥挤"。`scripts/graph_quality_qa.py`（GQ-01~15）：
节点/条形不重叠、文本不溢出框（0.03 容差）、边无穿字、边不穿节点（多段线采样）、
同层最小框距 ≥0.2cm、主流程方向一致、图例不覆盖、数据标签不重叠、有效字号 ≥9pt、
无裁剪、图题同页、图题-图/图-正文间距、独立页占用率 ≥55%、人工视觉对照（before|after 输出）。

Mermaid 硬规则：不得以"默认布局成功=合格"；必须核节点/边数、边界、穿字、间距、长标签与最终 PDF 显示尺寸，
必要时改方向/拓扑/短标签/拆图。长表跨页必须表头重复；表题一律在表格上方（中/英双语）。

### 18.4 表启动块（TABLE_START_BLOCK，v1.3.4→v1.3.5）

要求：中文表题+英文表题+表头行+首行数据 构成不可拆"表启动块"（长表允许数据跨页且表头重复；
禁止"题注在上页、表格在下页"、禁止题注孤立留页、禁止启动页题注-表头间大片空白）。
机制（三层，不得只依赖 keep_with_next）：
①构建期：中英题注段 keep_with_next + 题注→表头→首行 keep 链（≤12 行小表整表 keep）；
②渲染后硬校验：`scripts/repaginate_tables.py`（Word COM 实测每表 题注/表头/首行页码，
不一致即在题注前 InsertBreak 硬分页并重排至收敛 ≤3 轮；长表校验 Rows(1).HeadingFormat 表头重复），
置于 update_toc 之后、export_pdf 之前，退出码非 0 不得交付；
③项目 md 标记【分页】可将表/图强制另页（图页只保留"图+双行题注（+图内注）"）。
QA：`scripts/content_purity_qa.py` TABCAP-01 中英题同页 / TABCAP-02 英题与表头同页 /
TABCAP-03 表头与首行同页 / TABCAP-04 表题不单独留上一页 / TABCAP-05 启动页无大片空白
（题注-表头实测空白 ≤2.0cm）/ TABCAP-06 长表跨页重复表头 / TABCAP-07 图表题注顺序
（表题在表上方、图题在图下方、编号单调递增）/ TABCAP-08 图3-1后无长重复说明
（图页仅图+中英题注，>40 字文本块=0）。检查器定位题注须用"表题长签名"而非裸编号
（防正文引用句误配）。
BUG-014 防残留：构建期对"（图X-Y …"未严格匹配短占位的行一律 DROP 并记录
（旧式含"：清单/→"的长图注不得作为正文输出）；图后完整部件清单只在表中承担。

### 18.5 横向宽表版式（TABLE_LANDSCAPE_SECTION，v1.3.6→v1.3.7）

适用：13 列级宽表（FMEA 分析表等）在 A4 纵向版心（17cm）必然折碎成"一字一行"时，
改用 A4 横向独立页（版心 25.7cm），此为版式扩展而非内容修改。
**结构规范（v1.3.7 确认）：每张宽表一个独立横向节，节间恢复纵向正文**——
正文纵向 → 表4-1 横向 → 恢复纵向（组析文）→ 表4-2 横向 → … → 表4-4 横向 → 恢复纵向。
每张表独占其横向页（题注 CN/EN + 表格），组析文落在两表之间的纵向页；
汇总类窄表（如 RPN 排序表）保持纵向单页，不强行横向。
机制：①项目 md 标记 `【横向开始】`/`【横向结束】` → 构建端克隆当前节属性写入
1pt 空段 pPr（结束前节），再交换 sentinel sectPr 的 pgSz 宽高并置 orient；
**横向节必须剥离 pgNumType.start（页码连续不重启）**，页眉/页脚引用随克隆继承，
多次交替仍连续（每次 begin 克隆-剥离同一套逻辑）；
②横向表在引擎中 `add_table(..., landscape=True)`（宽度基数 25.7cm），列宽按
"故障原因/局部影响/最终影响/检测防护/故障模式"优先分配，S·O·D·RPN 保持 ≤1.2cm 窄列；
③横向表不压缩（行距 1.15/边距 0.1cm 常规值）；纵向汇总表如因整页排布出现
"析文孤行页"，可用单元格边距 0.04→0.02cm 级行距微调消孤（不改字号/结构）；
④`【分页】` 标记被 H2/H3、图、insert_table 分支消费（H1 仅清除标记，防双分页空白页）。
图4-1 类 25 条排序图：纵向大画幅独立图页（画布=显示尺寸 1:1，如 14.4×20.5cm），
标签一律"编号+短名称"（完整名称由汇总表承担），数值全标 + 白底衬防阈值虚线压字，
末端幽灵刻度（超出 xlim 的 250）须 set_xticks 显式限定。
新增 QA：`scripts/table_readability_qa.py`（TR-01~04 逐表可读=横向且主列≥9pt 且列宽合规；
TR-05 主列平均字号≥9pt；TR-06 无一字一行（≥6 字/行）；TR-07~10 原因/局部影响/最终影响/
检测防护列可正常成句（≥2.6cm 且 ≥8 字/行）；TR-11 S·O·D·RPN 紧凑且数字；TR-12 题注-表头
同页；TR-13 长表表头重复；TR-14 无裁剪）。
`scripts/graph_quality_qa.py` 扩至 GQ-01~20：GQ-16 最终 PDF 渲染级可读（300dpi 标签墨迹簇
=25 且中位高≥0.9×9.5pt）、GQ-17 标签不重叠（几何+渲染簇数）、GQ-18 不贴边（≥0.08cm）、
GQ-19 留白合理（覆盖 60~99%、墨迹 2~45%）、GQ-20 未被正文挤压（独立图页 ≥13×16cm 且无正文文本）。
HF-03 横线一致性改按方向分组核验（横向页宽=横向版心宽）；TAB-08 总宽容差放宽至 25.9cm。

### 18.6 封面字段填写保真（COVER-FILL-ALIGN + COVER_FILL_CENTERING，v1.3.7→v1.3.8）

原则：封面 = 模板首页直用；只填"题目/专业"等已提供字段（其余空槽保留，不编造），
**文字必须落在模板原填写横线上，且在该横线有效区间内水平居中**
（相对"本字段横线"居中，非页面居中；不得从横线左端起写）。
填写配方（fill_on_rule）：
①定位段内"下划线空格 run"（u=single 且无文字，模板每格 36 个 16pt 空格 = 288pt 线长）；
②题目填入**标签行自身**的横线（题　目:____，不是其下的续行），在候选字号
[12,11.5,11,10.5,10]pt 中取"最大且不越线"者（度量 = SimSun 字体度量 ×1.045 安全系数）；
③**居中组装**（COVER_FILL_CENTERING）：边距 =（线长 − 实渲宽度）/2，两侧等宽复刻为
「满格 16pt 空格 + 残隙空格（其字号 = 4×残隙pt，空格宽=字号/2）」，顺序
[前导满格][前导残隙][值][后导残隙][后导满格]，线长不变、不新增/不删除横线；
实渲宽度校准：中英混排 ×1.043（两点实测），纯 CJK =1.0；
④专业同法（16pt）；姓名/学号/学院/指导教师/职称/日期等**未来填入时同样居中**，
不得回退为左对齐；无数据时空槽保持模板原样。
**Word COM 陷阱**：段落级 spacing 覆盖（before/after=0）会被 Word 保存时按样式还原，
需收缩行距时改用表格单元格边距等结构性属性；run 克隆必须在其 rPr 内调整 sz
（原件 run 的覆盖可能被归一化丢弃）。
QA：`scripts/cover_align_qa.py`（COVER-ALIGN-01~16：校徽/校名/主标题/标签位置、题目-横线
关系、各字段基线、日期、行尾对齐、间距、无额外横线、无字段漂移 ≤2pt、视觉 ≤4%）；
`scripts/cover_fill_qa.py`（COVER-FILL-01~14：题目/专业在横线区间内、水平居中
（中心偏差 ≤2pt）、各空槽保留、不新增/不删除横线、PDF 视觉）。

### 18.7 封面颜色保真（COLOR Fidelity，v1.3.9→v1.3.10）

**对象优先原则**：封面校名/校徽等模板固定图片/图形对象，必须原样继承模板——同一媒体对象
（字节级）、同一 DrawingML 效果链、同一渲染颜色。处理颜色质疑的次序：
①先读对象来源（DOCX word/media + rels + blip 效果链，或用 PDF 对象/像素实测）——
**不得凭截图猜颜色**；②颜色规则优先级 = 原始模板对象（含效果链）的完整语义 > 学校模板要求 >
学校规范 > Skill 默认；③"打印前字体统一黑色"只约束**文字**（正文/标题），不得作用于
图片/图形对象；④对象已完全继承模板时（媒体字节一致 + 效果链一致 + pic:pic XML 一致 +
区域像素差为 0），**不得人为修色**（禁重绘/OCR/转文字/强制改黑改绿改灰）。
实战案例（校名"南京农业大学"，v1.3.10 完整定案）：**原始素材 PNG 实为绿色 #009F62**
（南农绿书法字，非灰非黑）+ 模板自带效果链 `grayscl + lum(-6000/18000) + biLevel(50000)`，
效果链把 93.8% 墨迹转为纯黑——即"绿色素材印成黑色"是模板固有设计；Word 渲染下
模板页与交付页校名均为纯黑且区域像素 Δ=0.000、PDF 内嵌熔合图 sha 一致
（41b9248583e2f34f…）；**对照中出现的"灰/绿观感"来自渲染器对 DrawingML 效果链的支持差异**
（不应用效果→绿、仅灰度化→灰、全应用→黑）。模板中的 WMF 为样例页 MathType OLE 公式，
随样例页移除属正确。**结论：零修改、不重建**。
QA：`scripts/color_fidelity_qa.py`（COLOR-01~16：01~08 对象类型/颜色来源/未重着色/校徽/
主标题黑/正文全黑/视觉对照/差异范围；09~16 源对象 pic:pic XML 级一致/媒体全量 sha/
效果链一致/PDF 渲染（熔合图 sha+像素）/校徽对象/未被重新着色硬门禁/正文黑/视觉对照）。
