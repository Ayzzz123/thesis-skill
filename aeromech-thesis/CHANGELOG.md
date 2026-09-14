# CHANGELOG — aeromech-thesis

## v1.5.0 — Research Intelligence & Agent Loop

**目标：在 v1.4.1 稳定基线之上新增研究智能层（发现→诊断→根因→修复→重分析→再验证闭环），只增不破：不改既有 RQG/QA 语义，旧项目（无 design/scope/repairs）全部 NOT_APPLICABLE / 不阻塞。**

**新增**

- Research Intelligence 规则总纲 `references/research-intelligence.md`（设计注册表 Schema、RF-01~10、
  C1~C4×ES1~ES4、issue_type×severity×auto/queue/block 矩阵、白名单与 recompute 受控执行模型、
  Loop 契约、8 维评分规范、Delivery Gate 集成、条款映射表）。
- 三个注册表（`.aeromech/research/`，随 research_integrity.py 引擎）：`design.yaml`（DESIGN-XXX：
  rq_requirements 的 needs/evidence_requirement）、`scope.yaml`（SCOPE-XXX：included/excluded/assumptions）、
  `repairs.yaml`（REP-XXX：diagnosis_id/operation/before/after/payload/rationale/risk/status）。
- `scripts/research_design.py`：设计一致性审计（needs⊆provides → RQ_METHOD_MISMATCH；
  evidence_requirement×实际数据 → DESIGN_EVIDENCE_MISMATCH；方法候选≥2+理由 → METHOD_SELECTION_WEAK）
  + Research Feasibility Gate RF-01~10 → FEASIBLE / CONDITIONALLY_FEASIBLE / INFEASIBLE（rc 0/1/2/3）。
- `scripts/research_diagnosis.py`：统一诊断引擎——合并设计审计/可行性/范围控制/数字一致性/冲突/RQG 结果
  为 DIAG-XXX 条目（severity 归一小写；稳定 ID 含 severity+payload 消歧），19 类 issue_type，
  disposition 三通道（auto=白名单可修 / queue=人工判定（含 CITATION_GAP 派生自 RQG-12）/ block=完整性失败）。
- `scripts/research_repair.py`：Repair Plan Registry + 白名单自动修复执行器——仅 4 操作
  （downgrade_wording 强度降级变换 / number_sync 摘要数字同步 / recompute 受控执行 / fix_synth_label 标签回填），
  全部 before/after 留痕 + 复检（applied→verified/rejected）；`apply-human` 消费 human-review-queue.yaml
  （approve/modify→注册表/文本执行并记 verified REP；reject→rejected_by_human；非文本→deferred，不静默）。
- `scripts/research_agent_loop.py`：PLAN→ANALYZE→DETECT→DIAGNOSE→REPAIR→RE-ANALYZE→VALIDATE→ACCEPT；
  MAX_ITERATIONS=5（1~20 可调）；签名无改善即停；每轮 loop-log 记录 issues_before/repairs/issues_after/
  improvement/remaining + 规则命中/严重度依据/修复选择（仅事实与规则，不含内部推理）；
  终态 BLOCK(rc=1) / PASS_WITH_HUMAN_REVIEW / WARN / PASS_WITH_WARNINGS / PASS；已裁决条目持久保留。
- `scripts/research_quality_score.py`：8 维（Research Design/Evidence/Data/Analysis/Argumentation/
  Conclusion/Citation/Coherence）各 0~100，扣分来自诊断未解决项 + Evidence Coverage 折算；
  未映射类型兜底计入 Coherence（标 UNMAPPED）；Critical/High 未解决 → blocked=True，总分不构成交付依据。
- 集成：SKILL.md §3 加载表 / §4 路由表 / §16 Delivery Gate v1.5 条款 / 新增 §20；
  `references/state.md` §17.1（S3 feasibility 前置、S7/S9 loop 门禁，不改 schema）；
  `references/delivery-pipeline.md` §8.3；`references/research-human-review.md` §6（双队列衔接）。
- `tests/v1_5/`：13 个测试文件（418 断言，PASS/FAIL/boundary/repair 四段式）+ _fixtures（14 缺陷变体）
  + run_all；`tests/v1_5/v1.5-baseline-report.md` / `v1.5-bugfix-log.md` / `v1.5-regression-report.md`。
- **test-7.0 端到端验收**（`Desktop\thesis-test-7.0`）：冷启动完整论文（3 RQ/主辅 3 方法/10 证据/模拟数据集
  /4 计算/4 论断/4 结论/3 图 3 表），植入 7 类缺陷（A 方法不匹配+real 数据声明、B 模拟写实测、C 结论断链越界、
  D 摘要 450 vs 正文 425.4、E scope creep 飞控×3、F 手册300/教材500 冲突、G AN-003 空 inputs）——
  全部被诊断捕获并正确分流：自动修复 REP-001/002（verified，含 before/after）、人工队列 7 项裁决
  （approve/modify/reject 三通道）、BLOCK→解除路径（blockdemo 副本：Critical 未解 → BLOCK score76；
  仅补证据仍 BLOCK；补人工设计决策后解除）；终态 loop PASS、score 100、交付链全 PASS（无模板→tf N/A）、
  污染扫描 0 命中。`thesis-test-7.0-blockdemo/` 为 BLOCK 演示证据副本。

**修复（发布前审计 B1~B10，均有回归锁）**

- B1 Citation 评分维恒 100：RQG-12 派生改产出独立 CITATION_GAP 并计入 Citation 维（v1_5 +3 断言）。
- B2 REDUNDANT_CONTENT 被评分静默丢弃：显式映射 Coherence + 未映射类型兜底（标 UNMAPPED 不丢失）。
- B3 research_repair `--diagnosis-json` 死参数接线（文件缺失=rc 3）；fix_synth_label 补 _verify（4/4 操作可复检）。
- B4 docstring `--quiet-rqg` 改 `--no-rqg`；research-intelligence.md 加条款映射表（§4/§13/§24 等编号可追溯）。
- B5 color_fidelity_qa 头注释 COLOR 范围与实现对齐。
- B6 pdf_qa：环境/配置错误（缺 PDF/缺依赖/参数）退出码改 3（不占用内容码 1/2）；docstring 写明旧 0/1/2 语义。
- B7 recompute shell=True → **受控执行模型**：仅 `python <项目内相对路径>.py`、解释器强制 sys.executable、
  拒绝 shell 元字符/绝对路径/越界/-c 入口、cwd=项目根、180s 超时、失败留痕不伪标 verified（v1_5 +8 断言）。
- B8 RQG-14 不识别文档词表 `computation`（与 `calculation` 同义）→ 等价接受且不降标（v1_4 +2 断言）。
- B9/B9b diagnosis_id 哈希键补 severity+payload（同规则不同严重度/不同越界词可分别裁决，v1_5 +2 断言）。
- B10 agent loop 重建队列丢弃已裁决关闭条目 → rejected/deferred 条目持久保留（人工驳回不再复活）。
- 伴生：diagnosis severity 入口统一小写（RQG 派生 "Critical/High" 不再漏计）；
  QC-01 数字同步基准改为"计算出处优先、相对差最小"（不再取先遇到的近似值）；
  apply_human 未知 decision 从队列消失改为 needs_input 留队可修。

**交付门禁变更**

- Delivery Gate 追加 Research Intelligence 门禁（delivery-pipeline.md §8.3）：design.yaml 存在时
  loop 终态 BLOCK 禁止交付、PASS_WITH_HUMAN_REVIEW 须队列清零后交付、评分随报告输出不作放行依据；
  旧项目 not_initialized 不阻塞。
- sync.py v1.5.0 加固（2026-09-12 事故后）：删除仅限目标树+逐条断言、>10 删除需 --force、
  空源拒绝、--dry-run；四道护栏经负例测试。开发仓初始化 git（v1.4.1 基线 9826193 → v1.5.0）。

**验证汇总**：tests/v1_4 11/11 + v1_4_1 5/5 + v1_5 13/13（418 断言）+ test_a/b 全绿；
t30~t60 交付链逐项与 v1.4.1 基线一致（tf 20/20/15+5N/A/15+5N/A，pdf_qa/visual/cover/gq/ft 全 PASS）；
test-7.0 端到端 PASS；dev↔install IDENTICAL。

## v1.4.1 — Stability & Production Hardening

**目标：不新增大型功能，将 v1.4.0 的 Research Integrity / QA 能力产品化、稳定化。**

**新增**

- `references/research-human-review.md`：研究语义人工复核规程（七维复核清单：
  结论证据支持/工程判断边界/模拟身份/方法与问题匹配/摘要准确/数字可信/文献支持；
  NHR 队列机制与 human-review.yaml 裁决格式）。
- `tests/v1_4_1/`（5 个测试文件 + run_all）：
  `test_not_applicable_qa` / `test_human_review` / `test_gate_state` / `test_dev_install_sync` / `test_false_pass_prevention`。
- 开发/安装目录规程：`Desktop\thesis-skill\aeromech-thesis`（权威开发源）+
  `sync.py`（--check / --to-install / --to-dev，镜像语义；逐字节比较）
  + `DEV_SYNC.md` / `INSTALL_SYNC.md`。

**状态模型（v1.4.1）**

- 统一状态词表：`PASS / WARN / FAIL / NEEDS_HUMAN_REVIEW / NOT_APPLICABLE / SKIPPED_WITH_REASON / ERROR`；
  FAIL 输出携带 severity + reason + remediation；退出码：0=PASS/PASS_WITH_HUMAN_REVIEW、1=FAIL、
  2=not_initialized（旧项目兼容）、3=ERROR。
- RQG-09/RQG-10（Critical 级语义项）：弱证据（全 simulated/pending）语境下未命中强断言模式时
  **不得自动 PASS** → `NEEDS_HUMAN_REVIEW` + `human-review-checklist.md`
  （claim/evidence/reason/uncertainty）+ Gate `PASS_WITH_HUMAN_REVIEW`；
  `human-review.yaml` 裁决（ok→PASS；violation→FAIL Critical；未裁决保持 NHR）。
- tf_qa：`--template` 可省略（或 none）→ 模板对照项（TF-01~04、TF-19）记 `NOT_APPLICABLE`（附 reason），
  自含检查照常执行，退出码 0；`--template` 指向不存在文件 = 配置错误（退出码 3，不静默降级）。
- research_integrity：注册表损坏 → `RI-CORRUPT`（critical + remediation，validate rc 1；
  trace/coverage rc 3）；全部问题项补齐 reason/remediation 字段。

**修复**

- `tf_qa` TF-13：无页眉时消息 f-string 提前求值导致 TypeError 崩溃（hdr=None）→ 延迟构造消息
  （由 test_false_pass_prevention 捕获）。
- `sync.py`：`filecmp` 缓存（键不含 mtime）导致同尺寸文件覆盖后仍报差异 → 改逐字节比较
  （由 test_dev_install_sync 负例捕获）。
- `research_quality_qa`：人工复核清单字段改双语标注（claim/evidence/reason/uncertainty 可直接检索）。

## v1.4.0 — Research Integrity & Evidence Traceability

**新增（研究完整性层，不破坏既有能力）**

- `references/research-integrity.md`：研究完整性规则总纲（架构分层、10 类注册表 Schema、ID 规则、
  RQG-01~15 定义表、Evidence Coverage 公式、材料优先级、冲突处理、通用性纪律）。
- `scripts/research_integrity.py`：注册表引擎（init/validate/trace/coverage，退出码 0/1/2）。
  - 结构校验：ID 唯一/格式、必填字段、悬空引用、`RI-E-DISGUISE`（simulation/assumption 证据伪装 verified → Critical）、
    模拟数据集 label 强制（`RI-DS-LABEL` → Critical）。
  - Research Traceability Graph：RQ→Method→Evidence/Data→Analysis→Figure/Table→Claim→Conclusion 边的构建与
    orphans（无链路核心论断/结论）检测，输出 `traceability.json`。
  - Evidence Coverage Ratio：核心 Claim 覆盖率 + verified/partial/pending/simulated 四分类
    （simulated 单列，不并入 verified）。
- `scripts/research_quality_qa.py`：Research Quality Gate 检查器（RQG-00 注册表校验 + RQG-01~15），
  Evidence Coverage 汇总、摘要↔正文一致性（数值域/身份措辞/结论覆盖，否定语境豁免）、
  证据越界检测（强断言口径 × 全模拟/未核实证据 → Critical）、正文数字可追溯率（≥50%）、
  图表论证链接统计（可选 PDF 题注数交叉核对）。退出码 0=PASS / 1=Critical/High FAIL / 2=未初始化（旧项目兼容，不阻塞）。
- `tests/v1_4/`：11 个专项测试文件（PASS/FAIL/boundary，共 162 项断言）+ `_fixtures.py`（含 26 种变异）
  + `run_all.py`；覆盖 RQ/Evidence/Claim/Traceability/SyntheticData/Computation/Conclusion/Abstract/Coverage/Gate/Conflict。
- SKILL.md §19 + 路由/加载/交付门禁集成；`references/state.md` §17 阶段职责（S3 起注册，
  S9 前 RQG 全量；`writing.gate_evidence` 升级前不得有 Critical/High）。

**修复**

- `research_integrity._require`：空列表/空字典此前不被视为"缺失字段"（`inputs: []` 可通过校验）；
  现按缺失处理（由 tests/v1_4/test_computation_provenance.py 捕获）。
- `research_quality_qa` RQG-09：数值不一致（High）曾被覆盖度软检查降级为 Medium 致 Gate 误放行；
  现仅当无硬问题时才降级。
- `research_quality_qa` numbers_of：英文单位正则过度捕获（"213 flight" → "213fligh"）；改英文单位白名单 + 词边界。
- `figure_table_qa` TAB-06：实现提示语承诺的"等级列合法单字豁免"（等级/级别/风险组/组别/评分/评级列）。
- `figure_table_qa` FIG-12：正文图引用匹配改为分隔符/空白归一化（图1-1 ≡ 图1.1 ≡ 图 1-1），消除全图"缺引用"误报。
- `page_fidelity_qa` AT-03/AT-04：无附录数据表时与 AT-02/AT-05 一致 SKIP（原为空集误 FAIL）。
- `table_readability_qa` TR-10：英文题注定位兼容 Tab.2.1 / Tab. 2-1 / Tab2-1 分隔符风格（原仅认点号无空格）。
- `cover_fidelity` 自检 CF-05：去除题名关键词硬编码（原绑定 test-5.0 题目短语），改为封面最长文本行题名候选判定。
- 封面下划线槽：新增 `w:ulTrailSpace` 兼容设置说明（`docx_engine`/项目组装器层面），确保"学号/密级"空格槽下划线在 Word 渲染中被绘制。

**交付门禁变更**

- Delivery Gate 增加 RI Gate：项目存在 `.aeromech/research/` 时，RQG Critical/High 阻止交付；
  注册表缺失的旧项目记 `not_initialized`，不阻塞（回归兼容）。

## v1.3.11

- Legacy `.doc` 学校材料处理：`detect_legacy_docs` / `convert_legacy_doc`（Word COM 转换，见 `references/template-fidelity.md` §11）。
- QA 通用化修复批次：`guard_table_gap` 过滤 body 级 sectPr（修复相邻表合并守卫失效）；
  `tf_qa` / `page_fidelity_qa` / `figure_table_qa` / `content_purity_qa` / `graph_quality_qa` 泛化（去除硬编码）；
  cover 系列（cover_align/cover_fill/cover_fidelity/color_fidelity）支持无母版自检模式。
- 新增 `scripts/finalize_metadata.py`（交付前 DOCX/PDF 元数据中性化）。

## v1.3.0 ~ v1.3.10

- v1.3.0 Cover Fidelity（COVER_FIDELITY_MODE / COVER_IMMUTABLE_REGION / CF-01~25）。
- v1.3.1 页级保真（page_fidelity_qa：HF/AF/AT/RF）。
- v1.3.2 图表版式与内容净化（figure_table_qa FIG/TAB、content_purity_qa MD/INT/PRM/APX）。
- v1.3.3 图形拓扑质量（graph_quality_qa GQ-01~15 + figkit.py layout 几何元数据）。
- v1.3.4~v1.3.5 TABLE_START_BLOCK；v1.3.6~v1.3.7 横向宽表独立节（TABLE_LANDSCAPE_SECTION）。
- v1.3.7~v1.3.8 封面字段填写保真（COVER-FILL-ALIGN + COVER_FILL_CENTERING）。
- v1.3.9~v1.3.10 封面颜色保真（COLOR Fidelity COLOR-01~16；效果链语义 > 学校要求 > 默认）。

## v1.2.0

- Cover Fidelity 引入（封面对象树保真、零删除/零压缩、图片继承、fill-on-rule 横线保留）。

## v1.1.0

- Template Fidelity 双模式（TEMPLATE_FIDELITY / FORMAT_RECONSTRUCTION）、模板母版驱动、
  页码防重启/表格分隔/题注跨空行纪律、tf_qa.py（TF-01~20）、Test A/B。

## v1.0.x

- Delivery stabilization：`docx_engine.py`、`update_toc.py`、`export_pdf.py`、`pdf_qa.py`、`visual_regression.py`、
  Delivery Gate 分级、PDF 为最终真值原则（真实 39 页论文 PDF 验证）。
