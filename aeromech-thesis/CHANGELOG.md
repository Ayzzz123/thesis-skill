# CHANGELOG — aeromech-thesis

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
