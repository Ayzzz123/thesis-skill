# AeroMech Thesis — 能力矩阵（维护审计版）

> Status：PASS=已实现且有通过证据；PARTIAL=实现但文档/接入有缺口；PLANNED=仅计划；UNKNOWN=无法确认。
> 证据基线：dev==install（逐字节）；tests/v1_4_1/regression/regression-report.md（2026-09-12 全量回归）；各 final-report。

## A. 交付保真能力（v1.0–v1.3.x）

| Capability | Status | Implementation | Tests / 证据 | Risk |
|---|---|---|---|---|
| Delivery Pipeline（DOCX→TOC→PDF） | PASS | scripts/docx_engine.py, build_docx.py, update_toc.py, export_pdf.py | test-1.0~6.0 真实交付；v1.4.1 回归 | LOW |
| PDF 为最终真值 + PDF QA（16项+TOC-01~10） | PASS | scripts/pdf_qa.py | t30/t40/t50/t60 pdf_qa 回归全 PASS；⚠test-1/2.0 legacy FAIL 已披露（页码带历史问题，非回归） | LOW |
| Visual Regression（占用率+A/B类） | PASS | scripts/visual_regression.py | 同上；⚠EXEMPT 硬编码 {0,3}+6章检测=泛化限制 | MEDIUM(泛化) |
| Template Fidelity 双模式 | PASS | scripts/template_fidelity.py(select_docx_mode)+references/template-fidelity.md | tests/test_a/test_b + t30~t60 tf_qa 全 PASS | LOW |
| tf_qa TF-01~20 | PASS | scripts/tf_qa.py | 回归：t30/40 20/0，t50 18+2SKIP，t60 15+5N/A | LOW |
| Template Fidelity 无模板运行（NOT_APPLICABLE，v1.4.1） | PASS | tf_qa.py --template none；配置错误 rc=3 | v1_4_1/test_not_applicable_qa.py（191行） | LOW |
| Cover Fidelity CF-01~25 | PASS | scripts/cover_fidelity.py + cover-fidelity.md | t40-cov 回归 PASS；OBS-007/008 防回归 | LOW |
| Cover Alignment COVER-ALIGN-01~16 | PASS | scripts/cover_align_qa.py | v1_4_1 回归 t40 链 | LOW |
| Cover Fill（fill-on-rule+居中）COVER-FILL-01~14 | PASS | scripts/cover_fill_qa.py | 同上（OBS-008 案例） | LOW |
| Color Fidelity COLOR-01~16 | PARTIAL | scripts/color_fidelity_qa.py | 功能经 test-4.0 验证；⚠文档头写 01~08 与报告题 01~16 不一致（文档债） | LOW |
| Page Fidelity HF/AF/AT/RF | PASS | scripts/page_fidelity_qa.py | v1_4 修复批次（AT-03/04 空集误FAIL）后回归 PASS | LOW |
| Figure/Table QA FIG-01~12/TAB-01~10 | PASS | scripts/figure_table_qa.py | t40-ft/t50-ft 回归；FIG-12/TAB-06 已修 | LOW |
| Wide Table QA TR-01~14（横向节） | PASS | scripts/table_readability_qa.py + repaginate_tables.py | t50-tr 回归；test-5.0 28项验收 | LOW |
| Graphical Readability GQ-01~20 + figkit layout | PASS | scripts/graph_quality_qa.py + figkit.py | t40-gq/t50-gq 回归 | LOW |
| Content Purity MD/INT/PRM/APX/TABCAP-01~08 | PASS | scripts/content_purity_qa.py | test-5.0 污染扫描 0 命中 | LOW |
| TABLE_START_BLOCK 三层机制 | PASS | 构建keep链+repaginate_tables硬校验+TABCAP | BUG-014 防残留已闭 | LOW |
| Legacy .doc 学校材料（v1.3.11） | PASS | template_fidelity.detect/convert_legacy_doc + tf.md §11 | test-5.0（哈工程2013 .doc 泛化验证） | LOW |
| 元数据中性化 | PASS | scripts/finalize_metadata.py | test-5.0 BUG-030 案例 | LOW |
| DOCX 引擎原语（图块/三线表/防合并/节页码） | PASS | docx_engine.py（guard_table_gap 修复后） | 全链依赖 | LOW |

## B. 研究完整性（v1.4.0/1.4.1）

| Capability | Status | Implementation | Tests | Risk |
|---|---|---|---|---|
| Research Question Registry | PASS | research_integrity.py + research-integrity.md §3 | v1_4/test_research_questions.py | LOW |
| Evidence Registry（4态映射+反伪装） | PASS | 同上 §4；RI-E-DISGUISE Critical | v1_4/test_evidence_registry.py | LOW |
| Claim Registry | PASS | 同上 §9 | v1_4/test_claim_registry.py | LOW |
| Conclusion Registry | PASS | 同上 §10 | v1_4/test_conclusion_traceability.py | LOW |
| Research Traceability Graph | PASS | build_traceability→traceability.json | v1_4/test_traceability.py；t60 35节点/76边/orphans=[] | LOW |
| Synthetic Data Ledger | PASS | datasets §6 + SYNTH_LABEL 强制 | v1_4/test_synthetic_data.py | LOW |
| Computation Provenance | PASS | computations §8 三件套 | v1_4/test_computation_provenance.py（含空列表=缺失修复） | LOW |
| Research Quality Gate RQG-00~15 | PASS | research_quality_qa.py | v1_4/test_research_quality_gate.py；162断言 | LOW |
| Evidence Coverage | PASS | coverage（simulated 单列） | v1_4/test_evidence_coverage.py | LOW |
| Abstract Consistency | PASS | RQG-09（数值/身份/覆盖+否定豁免） | v1_4/test_abstract_consistency.py | LOW |
| Conflict Resolution | PASS | conflicts.yaml §12 + 优先级 §16 | v1_4/test_conflict_resolution.py | LOW |
| NOT_APPLICABLE 状态码 | PASS | tf_qa/loop 消费；rc=3 配置错误不降级 | v1_4_1/test_not_applicable_qa.py | LOW |
| NEEDS_HUMAN_REVIEW + 队列 | PASS | RQG-09/10 弱证据→NHR；checklist+human-review.yaml 裁决 | v1_4_1/test_human_review.py | LOW |
| Human Review Queue（v1.5 loop 版） | PARTIAL | human-review-queue.yaml 由 loop 生成/消费 | 代码在 research_agent_loop.py；v1_5/test_human_review_loop.py 存在但无运行证据 | MEDIUM |
| 错误模型（7态+severity/reason/remediation，ERROR绝不伪造PASS） | PASS | research-integrity.md §19 + 各脚本 run() wrapper | v1_4_1/test_gate_state.py, test_false_pass_prevention.py（TF-13崩溃捕获） | LOW |
| 安全状态码/退出码 | PARTIAL | RI 层 0/1/2/3 统一；⚠旧交付脚本不一致（pdf_qa rc2=Critical；export/update_toc 0/1） | — | MEDIUM（跨层混用时） |
| sync safety（4护栏+dry-run+--force+逐字节比较） | PASS(静态) | sync.py `_assert_dst_only`/DELETE_CAP=10/空源拒绝/--dry-run | v1_4_1/test_dev_install_sync.py；⚠事故根因未定位=按最坏假设加固 | MEDIUM（见风险#1） |

## C. 研究智能（v1.5 —— 代码存在、未发布、未接入）

| Capability | Status | Implementation | Tests | Risk |
|---|---|---|---|---|
| Research Design Registry（design.yaml） | PARTIAL | research_integrity.py REGISTRY_SPECS + research_design.analyze() | v1_5/test_research_design.py（未运行） | HIGH（未接入路由） |
| Method Selection Intelligence | PARTIAL | research_design.py selection 审计（≥2候选+取舍理由） | v1_5/test_method_selection.py（未运行） | HIGH |
| Research Feasibility Gate RF-01~10 | PARTIAL | research_design.py feasibility（三态判定，阈值公开常量） | v1_5/test_feasibility.py（未运行） | HIGH |
| Claim Strength Model C1~C4×ES1~ES4 | PARTIAL | research_diagnosis.py CLAIM_RANK/MAX_CLAIM_BY_ES | v1_5/test_claim_strength.py（未运行） | MEDIUM |
| Research Diagnosis Engine（19 issue_type） | PARTIAL | research_diagnosis.py（DIAG 稳定ID、disposition auto/queue/block） | v1_5/test_diagnosis.py（未运行） | MEDIUM |
| Root Cause Analysis | PARTIAL | diagnosis 条目 root_cause/impact/repair_options | v1_5/test_root_cause.py（未运行） | MEDIUM |
| Repair Plan Registry（REP-XXX before/after） | PARTIAL | research_repair.py plan/status | v1_5/test_repair_plan.py（未运行） | MEDIUM |
| Auto Repair Policy（白名单4操作） | PARTIAL | research_repair.py（downgrade_wording/number_sync/recompute/fix_synth_label；⚠fix_synth_label 无verify；recompute shell=True 信任假设未文档化） | v1_5/test_auto_repair.py（未运行） | HIGH |
| Research Agent Loop（≤5轮，终态5种） | PARTIAL | research_agent_loop.py | v1_5/test_agent_loop.py（未运行）；⚠仅在 test-6.0 手工跑过一次（2026-09-12 loop-log 终态 PASS_WITH_HUMAN_REVIEW, Score 96） | HIGH |
| Research Quality Score（8维） | PARTIAL | research_quality_score.py（⚠Citation 维无 issue 映射恒100；REDUNDANT_CONTENT 漏映射） | v1_5/test_quality_score.py（未运行） | MEDIUM |
| Coherence Engine（重复分析/冗余段落检测） | PARTIAL | diagnosis §E-F（DUPLICATE_ANALYSIS/REDUNDANT_CONTENT） | v1_5（间接） | MEDIUM |
| Quantitative Consistency（425.4≡425.40≡425） | PARTIAL | diagnosis _num_close 0.5%/10% 带 | v1_5/test_quantitative_consistency.py（未运行） | MEDIUM |
| Research Scope Control（scope creep） | PARTIAL | diagnosis scope 检测 + scope.yaml | v1_5/test_scope_control.py（未运行） | MEDIUM |
| Human Review Loop（approve/reject/modify 驱动修复） | PARTIAL | research_repair.apply_human | v1_5/test_human_review_loop.py（未运行） | MEDIUM |
| Delivery Gate 集成（Loop 终态→Gate） | MISSING | research-intelligence.md §9 有规格；SKILL.md §16 未写入；交付文档不提 loop 要求 | — | HIGH |
| SKILL.md §3/§4/§19 路由与加载集成 | MISSING | v1.5 五脚本+规则书不在加载表/路由表 | — | HIGH |
| v1.5 端到端项目验证（test-7.0） | MISSING | 无任何 thesis-test-7.0 目录；v1_5/run_all 无运行痕迹（无 pycache/log/report）；⚠v1.5 断言"162→v1_5 13 文件"设计自 gap-analysis 后未验证 | — | HIGH |
| v1.5 发布记录（CHANGELOG/README/SKILL 版本行） | MISSING | 三文档均停在 v1.4.1；仅 sync.py/DEV_SYNC.md/references 出现 v1.5.0 字样 | — | MEDIUM（版本漂移） |

## D. 流程层（S1–S10 Agent 能力）

| Capability | Status | Implementation | Risk |
|---|---|---|---|
| Topic 分析/选题（S1/S2） | PASS | references/agents/topic.md | LOW |
| 研究方案/类型判定/文献登记（S3/S4） | PASS | research.md + templates | LOW |
| Engineering FMEA/FTA/RCA/FEM（S5） | PARTIAL（设计内降级） | engineering.md（表头骨架，不代算——SKILL.md §8 明示降级为特性） | LOW |
| Data 分析（S6） | PARTIAL（同上） | data.md | LOW |
| Writing（S7） | PASS | writing.md + 门禁三态 | LOW |
| Figure 生成（S8） | PASS | figure.md + render_mermaid.py(4级fallback)+figkit.py | MEDIUM（Chrome探测环境依赖） |
| Citation Integrity | PASS | agents/citation.md | LOW |
| QA 六维体检（S9） | PASS | agents/qa.md | LOW |
| Defense（S10） | PARTIAL | defense.md（PPT结构/答辩稿/问题库；MVP降级话术仍在SKILL §8——文档滞后） | LOW |
| 多 Skill 共存路由（vs aviation-engineering-thesis） | PASS | SKILL.md §14 | MEDIUM（两 skill description 领域词有重叠面：本机仍装有 aviation-engineering-thesis v1.3） |

## E. 总览判定

- v1.0~v1.4.1 声明的全部能力：**与代码/测试对得上，PASS**（文档与代码冲突处已在表内⚠标注）。
- v1.5：**实现程度远高于旧 Prompt 假设的"未开始"**——约 85% 代码已写完且 1 次真实项目试运行；
  缺的是**验证（13 个测试从未执行）、集成（路由/Gate/加载表）、发布（版本号/CHANGELOG）**三件事，
  而不是设计或编码。详见 capability 表 C 段与 v1.5-implementation-plan.md。
