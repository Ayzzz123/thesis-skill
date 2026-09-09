# State Manager（Thesis Project State Machine）

`.aeromech/state.yaml` **不是配置文件，而是论文项目的状态机真源**。它支撑：题目确定 → 方案确定 → 开始写作 → 发现问题 → 回退 → 修复 → 再前进，并保证跨会话不重复劳动。

目录布局见 `SKILL.md` §11；本文件定义字段、迁移规则与操作过程。

## 1. Schema v1.0 字段定义

| 字段 | 类型 | 必填 | 默认 | 说明 |
|---|---|---|---|---|
| `schema_version` | string | 是 | `"1.0"` | MAJOR.MINOR；加载时首读 |
| `project.title` | string | 是 | `""` | 已确定题目 |
| `project.major` | string | 否 | `""` | 专业 |
| `project.paper_type` | enum | S3 后必填 | `null` | `research` / `review` / `design`；S3 之前可填【假设】值并挂 open_issue 待 S3 确认 |
| `project.composite` | string | 否 | `""` | 复合型时的副类型说明 |
| `project.direction` | string | 否 | `""` | 研究方向 |
| `project.object` | string | 否 | `""` | 研究对象 |
| `project.question` | string | 否 | `""` | 核心研究问题 |
| `project.school_requirement` | string | 否 | `""` | 学校格式/篇幅要求 |
| `stage.current` | enum | 是 | `null` | `S1`…`S10` |
| `stage.history` | list | 是 | `[]` | 迁移记录，见 §6 |
| `stage.open_issues` | list | 是 | `[]` | 未关闭问题，见 §7 |
| `research.topic_card_file` | path | 否 | `""` | 相对 `.aeromech/` |
| `research.plan_file` | path | 否 | `""` | 研究方案 |
| `research.outline_file` | path | 否 | `""` | 论文目录 |
| `research.literature_file` | path | 否 | `""` | 文献登记表 |
| `research.literature_status` | enum | 否 | `none` | `none`/`tracking`/`collecting`/`reviewed`（tracking=仅建追踪表，检索未开始） |
| `research.notes` | string | 否 | `""` | 方案要点摘要（≤5 行） |
| `data.status` | enum | 否 | `none` | `none`/`collected`/`partial`/`analyzed` |
| `data.registry` | list | 否 | `[]` | 数据卡片：`{name,source,ts,unit,n,method,confidence,note,label}` |
| `writing.status` | enum | 否 | `not_started` | `not_started`/`in_progress`/`draft_done`/`final` |
| `writing.gate_evidence` | map | S7 前必填 | `{}` | 见 §5 |
| `writing.chapters` | map | 否 | `{}` | `{ch3:{file,status,affected_by_issue:[]}}` |
| `qa.reports` | list | 否 | `[]` | `{file,ts,summary}` |
| `qa.findings` | list | 否 | `[]` | 与 `stage.open_issues` 联动的索引 |
| `document_generation` | map | 否 | `{}` | DOCX 生成模式记录：`{mode: template_fidelity\|format_reconstruction, template_file: path\|null}`，S9 构建时由 `scripts/template_fidelity.select_docx_mode()` 写入 |
| `last_updated` | string | 是 | `""` | ISO 8601 |

约束：论文正文、文献全文、数据表**不得**写入 state.yaml，只写路径与摘要。

## 2. 阶段枚举

`S1` 题目分析 · `S2` 智能选题 · `S3` 研究方案 · `S4` 文献研究 · `S5` 工程分析 · `S6` 数据分析 · `S7` 章节写作 · `S8` 图表规整 · `S9` 全文QA · `S10` 答辩。

## 3. 允许边

| from → to | 类型 | 前置条件 |
|---|---|---|
| S1 ↔ S2 | 前进/微调 | 无 |
| S2 → S3 | 前进 | 题目已确定（`project.title` 非空） |
| S1 → S3 | 前进 | 用户自带题目且题目卡片已产出 |
| S3 ↔ S4 | 双向 | S3→S4：方案含文献需求或需建文献追踪表；S4→S3：文献促使方案修订 |
| S3 → S5 | 前进 | research/design 型方案齐备（可不经 S4） |
| S4 → S5 | 前进 | 方案齐备；文献依据按类型：review 型须有登记条目，research/design 型框架即可 |
| S5 ↔ S6 | 双向 | S5→S6：分析明确数据需求；S6→S5：数据可得性迫使方法调整 |
| S5 → S7 / S6 → S7 | 前进 | S7 门禁通过（§5） |
| S3 → S7 / S4 → S7 | 前进 | 仅 review 型且门禁通过（§5）；S4→S7 要求 `literature_status: reviewed` |
| S5/S6/S7/S8 → S3/S4/S5/S6 | **回退（依据缺口）** | 任一执行阶段发现上游依据缺口即可回退：缺方法/参数→S5、缺文献或资料登记→S4、缺数据→S6、缺方案→S3。目标阶段不得等于当前阶段；记 reason 与 issue_id |
| S7 → S8 | 前进 | 章稿完成且图表点位表已出 |
| S8 → S7 | **回退** | 图表编号/引用与正文不一致 |
| S8 → S9 | 前进 | 全稿与图表齐备 |
| S9 → S3/S4/S5/S6/S7 | **回退** | QA 问题按 §8 映射归类 |
| S9 → S10 | 前进 | `stage.open_issues` 中 severity ∈ {严重, 高} 全部 closed |

**返程总规则**：任何 `revert` 的逆边一律合法，无需逐条枚举。前置条件 = 触发该回退的 open_issue 全部 `closed` + 受影响产物已修订落盘。返程迁移 `type: forward`，reason 中写明关联 `issue_id`。

**优先级裁决**：返程条件**不豁免**目标阶段的类型门禁。例如 review 型由 S7 回退 S4 后返程进入 S7，仍须满足 §5 第 4 步（`literature_status: reviewed` 且至少 1 条非【待核实】条目）；两套条件同时校验，任一不满足即拒绝。

## 4. 迁移操作（transition）

1. 读 `state.yaml`，确认 `schema_version` 受支持（否则 §10）。
2. 校验目标边在 §3 中；不在 → §9 非法迁移处理。
3. 前进边：校验前置条件与门禁证据；缺失 → 拒绝并列出缺什么。
4. 回退边：必须有触发源（open_issue 或明确的依据缺口描述）。
5. 产物落盘（路径写入对应字段）后才允许改 `stage.current`。
6. 追加 `stage.history` 一条；更新 `last_updated`；同步 `.aeromech/context.md`。
7. 回退时：把受影响章节写入 `writing.chapters[*].affected_by_issue`。

## 5. 门禁证据（`writing.gate_evidence`）

策略见 `SKILL.md` §6；本节定义校验实现。

```yaml
# research 型
writing:
  gate_evidence:
    plan_file: artifacts/research-plan.md
    evidence_type: data_or_analysis      # data_or_analysis | literature | design_basis
    evidence_files: [artifacts/analysis/fmea-table.md]
    data_status: analyzed                # 或 collected/partial + 说明
    gate_passed: passed                  # passed | conditional | failed
    open_issues: []                      # conditional 时必填关联问题 id
# review 型
    evidence_type: literature
    evidence_files: [artifacts/literature.md]
    literature_status: reviewed          # 不要求 data
    gate_passed: passed
# design 型
    evidence_type: design_basis          # 参数/计算/仿真说明
    evidence_files: [artifacts/analysis/calc.md]
    gate_passed: conditional
# 复合型（主 design + 副 research）追加：
    sub_evidence_type: data_or_analysis
    sub_evidence_files: [artifacts/analysis/sim-result.md]
```

校验算法（逐项执行，任一不满足即降级或 failed）：

1. 按 `project.paper_type` 取 `evidence_type`；复合型再取 `sub_evidence_type`，**两者都要校验**。
2. `evidence_files` 存在且非空。
3. 对照研究方案第 13 节「证据完成判据」逐条核验。**仅有表头骨架、空模板、未回填的表格不计为通过证据**；此类情形只有在「证据生产模块本版未实现（S5/S6 降级）」时才可定为 `conditional`，否则一律 `failed`（例如 review 型的空登记表属用户未完成检索，判 `failed`）。
4. review 型追加：`literature_status == reviewed`，且登记表至少 1 条标注为【已核实】或【用户提供·未核实】的条目（全部【待核实】不算通过）。
5. design 型追加：参数来源已标注（【已核实】/【用户提供·未核实】），且计算书或仿真说明含公式与代入过程，不是纯文字描述。
6. 定态：三态判据见 `SKILL.md` §6。`conditional` 必须同时满足其四个条件并写 `open_issues`；`failed` → 回退到生产该证据的阶段。

**任何类型都不得因“没有实验数据”而被拒绝进入 S7。**

## 6. history 记录格式

```yaml
stage:
  history:
    - from: S3
      to: S7
      type: forward          # forward | revert | milestone | migrate | override
      reason: "研究方案与FMEA分析表齐备，门禁通过"
      evidence: [artifacts/research-plan.md, artifacts/analysis/fmea-table.md]
      issue_id: null         # revert 与“问题关闭后返程”迁移必填
      override: false
      ts: "2026-09-07T21:30:00+08:00"
```

规则：

- `from == to` 的迁移合法，`type: milestone`，用于阶段内里程碑（如“研究方案定稿”“第3章完成”），`stage.current` 不变但仍刷新 `last_updated`。
- 回退记录必须写清 `reason` 与 `issue_id`（无对应问题时写 `reason` 说明触发源）。
- `type: override` 与字段 `override: true` 必须同时出现、含义一致（用户强行推进）；`conditional` 门禁放行属正常迁移，`type: forward` 且 `override` 必须为 `false`。
- `ts` 取系统时间，history 内应单调递增；若系统时间早于上一条（时钟回拨或夹具数据），保留真实时间并在 `reason` 末尾标注「时钟异常」。

## 7. open_issues 格式与生命周期

```yaml
stage:
  open_issues:
    - id: ISS-001
      severity: 严重          # 严重 | 高 | 一般 | 建议
      category: citation      # structure|academic|citation|engineering|data|figure|writing|integrity
      target_stage: S4
      desc: "第三章引用了不存在的标准编号"
      close_condition: "用户补回可核实的标准出处，或正文改为『相关行业标准【待核实】』并列入章末清单"
      status: open            # open | in_progress | closed
      raised_at: S9
      closed_at: null
```

规则：新增问题即 append；处理中置 `in_progress` 并触发回退；关闭时写 `closed_at` 并在 history 记 forward（返程）迁移。severity=严重 的问题未关闭前禁止进入 S10。

**回退目标模块本版未实现时**（如 target_stage=S5/S6 而 Engineering/Data 尚未落地）：问题保持 `open`，产出降级指引文件（写清用户需人工完成什么、完成判据是什么、回填到哪个产物），不得代做，也不得以“无法处理”为由关闭。

**关闭路径**：用户按指引回填证据后，由 Agent 对照研究方案第 13 节「证据完成判据」与 `close_condition` 逐项核验，核验通过才置 `closed` 并写 `closed_at`；核验不通过则保持 `open` 并说明差在哪。禁止 Agent 代做分析后自行关闭问题。

**desc 快照规则**：`desc` 是问题**提出时**的事实快照，处置过程中不回写正文。若事实已变化（如登记表已建、某条边已开放），在关闭或 milestone 迁移的 `reason` 中写明更正，并在 `desc` 末尾追加【快照已过期，见 history】，避免 state 自相矛盾。

## 8. 问题类别 → 回退目标映射

| category | 典型问题 | target_stage |
|---|---|---|
| structure | 章节缺失、逻辑链断裂、方案与目录不符 | S3 |
| academic | 结论超出证据、抄袭风险 | S3 或 S7 |
| citation | 观点无来源、来源不支持观点、编号错、格式错、虚构条目 | S4 |
| engineering | 方法选错、术语/单位/参数错、分析不合对象 | S5 |
| data | 实测/试验数据来源不明、单位错、计算错、结果不一致、模拟数据混入结论 | S6（**设计参数、材料/载荷取值来源不明归 engineering → S5**） |
| figure | 图表编号/标题/正文引用不一致、图表与数据不符 | S7（S8 配套复核） |
| writing | 表述冗余、口语化、衔接差 | S7 |
| integrity | 触碰 `integrity.md` 红线 | 按具体类别映射，severity 一律「严重」 |

**类别重叠裁决**：同一问题同时命中 `citation` 与 `integrity`（如虚构文献条目）时，`category` 取具体类别 `citation`，`target_stage` 取 S4，severity 依 `integrity.md` §9 定为「严重」。

## 9. 非法迁移处理

- 边不存在 → 拒绝，输出：`当前 S?，请求 S?，该迁移不在允许边内。合法路径：…`
- 前置条件不满足 → 拒绝并列出缺失证据与生产该证据的阶段。
- 用户坚持 → 二次确认 → `type: override` 写入 history + 生成 open_issue（severity=高，status=open）→ 放行。
- 禁止静默跳转；禁止在未落盘产物时改 `stage.current`。
- **拒绝事件记录**：被拒绝的迁移不写入 `history`（history 只记实际发生的迁移），改写入 `context.md` 的「迁移拒绝记录」区，含：时间、请求的边、拒绝理由、缺失项、放行指引。

## 10. Schema 版本迁移协议

当前 Skill 支持：`1.0`。

| 旧版本 | 目标 | 迁移动作 |
|---|---|---|
| 无 `schema_version` 字段 | 1.0 | 视为 0.x：补 `schema_version:"1.0"`，缺失字段取 §1 默认值 |
| 1.0 | 1.x（未来） | 增量补字段，不改既有语义 |

规则：

1. 迁移前备份：`.aeromech/state.yaml.bak-v<旧版本>-<yyyymmddHHMM>`。
2. 只增不删不改语义；未识别字段**原样保留**（向前兼容）。
3. 逐级迁移，不跳级合并。
4. 迁移写入 history：`type: migrate, reason: "schema 0.x→1.0"`。
5. `schema_version` **高于**当前 Skill 支持版本 → 只读运行，提示升级 Skill，不写入。
6. 迁移失败 → 恢复备份，告知用户，不继续。

## 11. 备份规则

| 触发 | 备份文件 |
|---|---|
| schema 迁移前 | `state.yaml.bak-v<ver>-<ts>` |
| 检测到文件损坏/字段缺失并修复前 | `state.yaml.bak-corrupt-<ts>` |
| 执行 revert（回退）迁移前 | `state.yaml.bak-revert-<ts>` |
| S9 全文 QA 开始前 | `state.yaml.bak-preqa-<ts>` |

保留最近 5 份，超出删除最旧。禁止用 `state.yaml.bak` 单一文件名覆盖式备份。

## 12. 恢复协议（实现细节）

用户说“继续论文”/“接着上次”：

1. 定位工程目录：**用户或任务已指明工程目录时直接采用**；否则当前目录 → 向上最多 2 级查找 `.aeromech/`；多个候选 → 列出让用户选；找不到 → 询问是否新建。
2. 读 `state.yaml`；解析失败 → §11 备份后按 schema 补默认值并告知。
3. 版本不符 → §10 迁移。
4. 组装恢复摘要（固定四行）：

```
【恢复】题目：<title>（<paper_type>）
【阶段】当前 S? · 下一步建议：<...>
【已定】方案/目录/已完成章节：<列表>
【未关闭问题】<id + severity + desc>（无则写“无”）
```

5. 若 `open_issues` 非空：**可交互时**先问是否处理回退再前进；**不可交互时**（单轮指令、批处理、用户已明确要求继续推进）按 `SKILL.md` §9 选择降级路径并标【假设】，处置过程写入 history 的 reason。
6. **禁止**重新询问 state 中已确定的字段；缺失字段标【假设】并继续。
7. 同步刷新 `context.md`；**任何 state 写入都必须刷新 `last_updated`**，即使未发生阶段迁移。

## 13. context.md 规范

`.aeromech/context.md` 是人读的项目摘要（≤60 行），每次迁移后更新，含：题目与类型、研究问题与方法、技术路线一句话、已确认数据/文献要点、已完成章节与字数、未关闭问题、下一步。state.yaml 管机器状态，context.md 管快速对齐。

## 14. 初始化（新项目）

1. 在用户论文工程目录创建 `.aeromech/`、`.aeromech/artifacts/{analysis,chapters,qa,defense}`。
2. 写入 §15 骨架，`stage.current: S1`（用户自带题目）或 `S2`（需选题）。
3. history 记首条：`from: null, to: S1, type: forward, reason: "项目初始化"`。

## 15. state.yaml 骨架

```yaml
schema_version: "1.0"
project:
  title: ""
  major: ""
  paper_type: null
  composite: ""
  direction: ""
  object: ""
  question: ""
  school_requirement: ""
stage:
  current: null
  history: []
  open_issues: []
research:
  topic_card_file: ""
  plan_file: ""
  outline_file: ""
  literature_file: ""
  literature_status: none
  notes: ""
data:
  status: none
  registry: []
writing:
  status: not_started
  gate_evidence: {}
  chapters: {}
document_generation: {}   # S9 构建时写入（template-fidelity.md §2）
qa:
  reports: []
  findings: []
last_updated: ""
```

## 16. Thesis Materials 机制（Phase 4-A）

### 16.1 materials.yaml Schema

`.aeromech/materials.yaml` 记录用户提供的真实资料，字段如下：

```yaml
materials:
  - material_id: MAT-001        # 唯一标识，自增
    filename: "毕业论文格式要求.pdf"  # 若文件未上传则为 null
    availability: uploaded      # uploaded / pending / missing
    type: school_template       # 见下方类型枚举
    source: "XX大学教务处"       # 来源描述
    authority: school           # 见下方来源等级
    date: "2024-09-01"          # 文件日期或上传日期
    hash_or_identifier: ""      # SHA256 或 DOI/ISBN/标准号（若有）
    used_by: ["citation", "qa"] # 被哪些模块引用
    verification_status: verified  # verified / pending / unverified
    notes: "学校官方发布的2024版格式要求"
```

**availability 枚举**：
- `uploaded`：文件已存入 `.aeromech/materials/` 子目录
- `pending`：用户声称有文件但尚未上传
- `missing`：用户明确无此文件，仅口头描述内容

**规则**：若 `availability: missing`，则 `filename` 必须为 `null`，不得留空字符串。Citation/QA 在处理此类资料时需特别标注"来源不可追溯"。

**type 枚举**：`school_template` / `literature_pdf` / `sample_thesis` / `project_data` / `standard_doc` / `technical_manual`

**authority 来源等级**：
- `school`（Level 1）：学校正式文件（格式要求、任务书、模板）
- `user_provided`（Level 2）：用户提供的正式项目资料（维修记录、实习数据）
- `public_verified`（Level 3）：公开可验证文献/标准（CNKI 论文、GB/T 标准）
- `secondary`（Level 4）：往届论文/二手资料（仅参考结构与格式）
- `model_knowledge`（Level 5）：模型一般知识（不应作为具体事实的唯一证据）

**verification_status**：
- `verified`：来源可靠且内容已核验（如学校官网下载、用户确认）
- `pending`：待用户确认或等待进一步核实
- `unverified`：无法核实来源，仅作为参考

### 16.2 School Format Profile

`.aeromech/school-format.yaml` 记录学校排版要求，与研究结构分离。格式信息分为三层：

```yaml
# === 元数据 ===
format_source: general_default  # school_template | sample_thesis | general_default | unknown
format_status: partial          # complete | partial | missing

# === 第一层：general_principles（工科论文通用结构原则，不随学校变化）===
general_principles:
  - "图表必须有编号和题注"
  - "标题需要有层级（至少三级）"
  - "参考文献需要统一格式（如 GB/T 7714）"
  - "正文、图表、参考文献应保持一致性"
  - "摘要需包含研究背景、方法、结果、结论四要素"

# === 第二层：general_defaults（仅用于无学校模板时生成 DOCX 的临时默认排版值）===
# ⚠️ 以下仅为 fallback 生成默认值，不代表任何学校正式要求
general_defaults:
  font_body: "宋体"             # 【仅为生成默认值】
  font_size_body: "小四"        # 【仅为生成默认值】
  line_spacing: "1.5倍行距"     # 【仅为生成默认值】
  margin: "上2.5cm 下2.5cm 左3cm 右2.5cm"  # 【仅为生成默认值】
  heading_format:
    level1: "黑体三号 居中"     # 【仅为生成默认值】
    level2: "黑体四号 左对齐"   # 【仅为生成默认值】
    level3: "黑体小四 左对齐"   # 【仅为生成默认值】
  figure_format: "图号居中，标题五号宋体"       # 【仅为生成默认值】
  table_format: "三线表，表头五号黑体"         # 【仅为生成默认值】
  citation_style: "GB/T 7714-2015"            # 通用标准（非学校特定）
  page_number: "底部居中"                      # 【仅为生成默认值】
  abstract_requirement: "中文摘要300-500字，英文摘要对应翻译"  # 通用要求
  word_count_min: 10000         # 【仅为生成默认值】
  word_count_max: 15000         # 【仅为生成默认值】
  notes: "以上为通用工科论文默认格式，仅供无学校模板时生成 DOCX 使用，不代表任何学校正式要求。获取正式学校模板后将自动覆盖。"

# === 第三层：school_specific_unknown（学校模板未提供时记录的具体待确认项）===
school_specific_unknown:
  font_body: "【学校格式待提供】"
  font_size_body: "【学校格式待提供】"
  line_spacing: "【学校格式待提供】"
  margin: "【学校格式待提供】"
  heading_format:
    level1: "【学校格式待提供】"
    level2: "【学校格式待提供】"
    level3: "【学校格式待提供】"
  figure_format: "【学校格式待提供】"
  table_format: "【学校格式待提供】"
  page_number: "【学校格式待提供】"
  word_count_min: "【学校格式待提供】"
  word_count_max: "【学校格式待提供】"
  other_requirements: "【学校格式待提供】"
```

**format_source 枚举**：
- `school_template`：用户提供了正式学校模板
- `sample_thesis`：使用往届样文作为参考（仅结构/版式参考，非正式模板）
- `general_default`：无学校模板，使用通用默认值
- `unknown`：初始状态，尚未判断

**format_status 枚举**：
- `complete`：学校模板已提供且所有字段已解析
- `partial`：部分字段已知（如从样文推断），部分仍待确认
- `missing`：完全无学校格式信息

**重要原则**：
1. 研究结构（Research Structure）与学校格式（School Formatting）严格分离。
2. **general_defaults 中的具体值（宋体、小四、1.5倍行距等）仅为 DOCX 生成的 fallback 默认值，不得表述为"通用本科论文标准"或任何学校正式要求。**
3. 学校模板优先级最高（Level 1），与 Skill 默认格式冲突时以学校为准。
4. School Format Profile 只影响最终排版，不进入 Research/Writing Agent 的研究逻辑。
5. 当 format_status ≠ complete 时，QA 不得将 general_defaults 判定为学校要求，只能报告为"待确认项"。

### 16.3 Project Directory Contract（项目目录规范）

**新项目默认目录结构**：

```
thesis-project/                    # 项目根目录
├── README.md                      # 项目说明（可选）
├── materials/                     # 用户原始材料目录（用户可见、用户负责放置）
│   ├── school/                    # 学校文件（格式要求、模板）
│   ├── literature/                # 文献 PDF / CNKI 题录
│   ├── technical_manual/          # 技术手册（AMM/CMM/IPC/TSM/SRM）
│   ├── standard/                  # 标准文件（GB/HB/MH/CCAR）
│   ├── project_data/              # 项目数据（实验数据、维修记录）
│   └── samples/                   # 往届样文（仅参考结构/版式）
├── .aeromech/                     # Skill 内部工作区（由 Skill 管理，用户无需修改）
│   ├── state.yaml                 # 状态机
│   ├── context.md                 # 项目上下文摘要
│   ├── materials.yaml             # 资料登记总表（登记 materials/ 下的所有材料）
│   ├── school-format.yaml         # 学校格式配置
│   ├── artifacts/                 # Skill 产出物
│   │   ├── analysis/              # 工程分析产物
│   │   ├── chapters/              # 论文章节
│   │   ├── figures/               # 图表
│   │   ├── computation/           # 计算审计
│   │   ├── qa/                    # QA 报告
│   │   └── defense/               # 答辩材料
│   └── transcripts/               # 会话记录
├── 毕业论文.docx                  # 最终交付物（项目根目录）
└── 毕业论文.pdf                   # 最终交付物（项目根目录）
```

**旧项目兼容**：
- 若存在 `.aeromech/materials/`（旧结构），Skill 仍可正常读取，不破坏旧项目
- 但新项目统一使用新的标准结构（`materials/` 在项目根目录）

**路径约定**：
- 所有材料路径统一采用相对于项目根目录的路径，例如：
  - `materials/school/xxx.docx`
  - `materials/literature/xxx.pdf`
  - `materials/project_data/data.xlsx`
- `materials.yaml` 中记录的 `filename` 字段使用相对路径

**规则**：
1. `materials/` 是用户可见、用户负责放置原始论文材料的目录。用户可手动放入文件，Skill 会自动登记到 `materials.yaml`。
2. `.aeromech/` 是 Skill 内部工作区，仅由 Skill 管理。用户通常不需要也不应该修改其中的任何文件。
3. `materials/` 中的原始文件只能读取、登记、分析、引用，**禁止修改**。
4. `.aeromech/artifacts/` 继续保存 Skill 生成的内部成果，不要移动到 `materials/`。
5. `.aeromech/transcripts/` 继续保存过程记录。
6. 最终 DOCX/PDF 放在项目根目录，不进入 `.aeromech/`。
7. Knowledge 层（`references/knowledge/`）与 Project Materials 严格分离，用户资料不得写入 Knowledge。
8. Sample Thesis 只能用于结构/格式/研究方法参考，禁止直接复制表述、数据、结论、案例。

**学校模板检测逻辑**：
- 优先检测 `materials/school/` 目录
- 若不存在， fallback 到 `.aeromech/materials/school/`（旧项目兼容）

